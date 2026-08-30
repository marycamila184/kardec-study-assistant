# Morning Reminder and Cached Reflection — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Narrow the reminder to one notification a day, in the morning, carrying the day's chapter title and opening a reflection that is already written.

**Architecture:** The scheduler drops from every fifteen minutes to hourly, with the due-window widened to match so nobody is skipped; the hour picker offers whole hours only. The dispatch job computes the day's passage — which it already does to build the notification — ensures the day's explanation exists in a Firestore cache, and only then sends. `/study` reads that cache when the passage requested is today's, and fills it on a miss.

**Tech Stack:** Python 3.12, FastAPI, `google-cloud-firestore`, `pywebpush`, Cloud Run Jobs, Cloud Scheduler; Astro + React; pytest and `.mjs` guards.

**Spec:** [docs/superpowers/specs/2026-08-29-lembrete-de-manha-e-reflexao-em-cache-design.md](../specs/2026-08-29-lembrete-de-manha-e-reflexao-em-cache-design.md)

## Global Constraints

- **The window must equal the cadence.** Hourly runs with a 60-minute window. Hourly runs with a 15-minute window would silently never serve a reader in a broken-offset timezone — the failure this project refuses.
- **The subscription record stays exactly five fields** — `{endpoint, keys, hour, timezone, last_seen}` — and joins nothing. The reflection cache is a **second, separate collection**, never a field on the first.
- **Never cache a failure.** A withheld or failed generation writes nothing. A cached failure is served to every reader all day.
- **The cache key is the passage's identity plus the date**, never the date alone: an edit to `data/markdown_files/trecho_diario.md` must miss, not serve stale prose.
- **Warm before sending, and send even if the warm-up failed.** A cache miss is a slower reader; a suppressed notification is a reader who never knew.
- **The chapter title is not case-transformed.** The corpus stores it in capitals; lowercasing would need an exception list for `DEUS`, `JESUS`, `CRISTO`.
- **The notification body is the chapter title, never the passage text.** At ~517 characters the passage would be truncated, reproducing daily the error [2026-08-05](../specs/2026-08-05-curadoria-trecho-e-trilhas-design.md) fixed.
- Code comments in Portuguese, matching the surrounding files. Commit messages, branch names and specs in English.
- Verification after every task: `uv run pytest -q`, `uv run black --check src/ tests/ && uv run isort --check-only src/ tests/`, `cd frontend && npm run build`, and from the REPO ROOT the eight guards (`check_chat_current_mode`, `check_cited_text`, `check_followup_reply`, `check_discovery_assets`, `check_api_base`, `check_consent_prompt`, `check_pwa_manifest`, `check_push_service_worker`).

---

### Task 1: Hourly cadence, sixty-minute window

**Files:**
- Modify: `src/core/config.py` (the `push_window_minutes` field)
- Modify: `src/push/schedule.py` (the docstring only)
- Test: `tests/test_push_schedule.py`

**Interfaces:**
- Consumes: `is_due(hour, timezone_name, now_utc, window_minutes) -> bool` — unchanged signature
- Produces: `settings.push_window_minutes == 60`

The arithmetic in `is_due` does not change at all. Only the window it is given, and what that makes true.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_push_schedule.py`:

```python
def test_com_janela_de_60_o_brasil_recebe_no_minuto_exato():
    # Todo fuso do Brasil é hora cheia, então uma execução no minuto :00 de
    # UTC cai no minuto :00 local. Quem escolheu 08:00 é servido às 08:00,
    # não "até 14 minutos depois".
    onze_utc = datetime(2026, 8, 27, 11, 0, tzinfo=timezone.utc)  # 08:00 em SP
    assert is_due("08:00", "America/Sao_Paulo", onze_utc, 60)


def test_com_janela_de_60_ninguem_dispara_duas_vezes_no_mesmo_dia():
    # A janela é igual à cadência, então cada janela de 60 minutos contém
    # exatamente uma execução horária. Duas execuções seguidas não podem
    # ambas cair na mesma janela.
    primeira = datetime(2026, 8, 27, 11, 0, tzinfo=timezone.utc)
    seguinte = datetime(2026, 8, 27, 12, 0, tzinfo=timezone.utc)
    assert is_due("08:00", "America/Sao_Paulo", primeira, 60)
    assert not is_due("08:00", "America/Sao_Paulo", seguinte, 60)


def test_fuso_de_minuto_quebrado_recebe_atrasado_mas_recebe():
    # O motivo de a janela ser 60 e não 15. Com execução horária e janela de
    # 15, o Nepal (UTC+5:45) NUNCA seria servido: seu relógio local só é
    # olhado no minuto :45. Com janela de 60 ele recebe dentro da hora.
    # Tarde não é bom; silêncio é inaceitável.
    da_hora = datetime(2026, 8, 27, 2, 0, tzinfo=timezone.utc)  # 07:45 em Katmandu
    assert not is_due("08:00", "Asia/Kathmandu", da_hora, 15)
    assert is_due("08:00", "Asia/Kathmandu",
                  datetime(2026, 8, 27, 3, 0, tzinfo=timezone.utc), 60)
```

- [ ] **Step 2: Run them and watch the first two fail**

Run: `uv run pytest tests/test_push_schedule.py -v`
Expected: the three new tests pass already — `is_due` takes the window as an argument, so they exercise the new behaviour without any code change. **This is expected and is the point:** the arithmetic was already right; what changes is the number the system passes it. If any of the three fails, STOP and report — that would mean the spec's reasoning is wrong.

- [ ] **Step 3: Change the default**

In `src/core/config.py`, replace the `push_window_minutes` field and its comment:

```python
    # 60, igual à cadência do agendador. Igualar os dois é o que garante que
    # cada janela contenha exatamente uma execução: ninguém recebe duas vezes,
    # e ninguém — nem em fuso de minuto quebrado — deixa de receber. Era 15
    # quando o agendador rodava de 15 em 15. Ver
    # docs/superpowers/specs/2026-08-29-lembrete-de-manha-e-reflexao-em-cache-design.md
    push_window_minutes: int = 60
```

Update the assertion in `tests/test_config.py` from `== 15` to `== 60`.

- [ ] **Step 4: Update the DST note — do NOT delete the test**

In `src/push/schedule.py`, the docstring paragraph about daylight saving stays, because the behaviour has not changed: a reader in a DST zone whose hour falls in the repeated hour still fires twice. Only the audience changed. Replace that paragraph's last sentence with:

```
    Isso deixou de alcançar o público real: nenhum fuso do Brasil observa
    horário de verão desde 2019, e nenhum país lusófono tem fuso de minuto
    quebrado. O comportamento continua aqui, e o teste abaixo continua o
    fixando, porque quem estiver fora desses fusos ainda o encontra.
```

Leave `test_o_horario_de_verao_repete_o_lembrete_uma_vez_por_ano` exactly as it is.

- [ ] **Step 5: Run the suite and commit**

Run: `uv run pytest -q` then `uv run black --check src/ tests/ && uv run isort --check-only src/ tests/`

```bash
git add src/core/config.py src/push/schedule.py tests/test_push_schedule.py tests/test_config.py
git commit -m "feat(push): hourly cadence with a matching sixty-minute window

The arithmetic does not change; the number it is given does. Setting the
window equal to the cadence is what makes every device fire exactly once a
day whatever its offset — hourly runs with the old fifteen-minute window
would have silently never served a reader in a broken-offset timezone.

For Brazil, where every zone is a whole hour, delivery becomes exact to the
minute rather than up to fourteen minutes late."
```

---

### Task 2: The scheduler runs hourly

**Files:**
- Modify: `docs/deploy.md` (the `gcloud scheduler jobs create` command)

**Interfaces:**
- Consumes: nothing
- Produces: the deploy command a reader will run

- [ ] **Step 1: Find the schedule flag**

Run: `grep -n "schedule" docs/deploy.md`
You are looking for `--schedule '*/15 * * * *'`.

- [ ] **Step 2: Change it, and say why in the comment above it**

Replace the Scheduler block's comment and its `--schedule` flag so they read:

```bash
# 4. O Scheduler, de hora em hora.
#
# A cadência e a janela de envio (push_window_minutes, 60) têm de continuar
# iguais. Se uma mudar sem a outra: cadência menor que a janela manda o
# lembrete duas vezes, cadência maior que a janela faz alguém não receber
# nunca — em silêncio, que é pior.
gcloud scheduler jobs create http kardec-push-tick \
  --location us-central1 \
  --schedule '0 * * * *' \
```

Keep every other flag in that command exactly as it is.

- [ ] **Step 3: Check nothing else in the file still says fifteen minutes**

Run: `grep -n "15 minutos\|\*/15\|quinze" docs/deploy.md`
Expected: no output. If anything appears, fix it — a doc that contradicts itself is worse than one that is merely out of date.

- [ ] **Step 4: Commit**

```bash
git add docs/deploy.md
git commit -m "docs(deploy): run the reminder job hourly

The cadence and push_window_minutes must move together: a cadence shorter
than the window sends twice, a cadence longer than it means somebody is
never served, silently."
```

---

### Task 3: The hour picker offers whole hours only

**Files:**
- Modify: `frontend/src/components/modals/SettingsPanel.jsx`
- Test: `frontend/tests/smoke.spec.mjs`

**Interfaces:**
- Consumes: `useReminder()` → `{ supported, needsInstall, enabled, hour, setHour, enable, disable, busy, motivo }` — unchanged
- Produces: a `<select>` in place of `<input type="time">`

The input accepts `08:07` today and the system delivers `08:15` without saying so. A picker of whole hours stops the promise from outrunning the delivery.

- [ ] **Step 1: Read what is there now**

Run: `grep -n "type=\"time\"" -B6 -A14 frontend/src/components/modals/SettingsPanel.jsx`
Note the local `horaExibida` state and the `onBlur` commit added earlier — a `<select>` commits on change, so that local state and the blur handler are no longer needed for this control.

- [ ] **Step 2: Replace the input**

Replace the `<input type="time">` element (and the `horaExibida` local state that existed only to serve it) with:

```jsx
                {reminder.enabled && (
                  <select
                    value={reminder.hour}
                    disabled={reminder.busy}
                    onChange={(e) => reminder.setHour(e.target.value)}
                    style={{
                      width: '100%', background: theme.inputBg,
                      border: `1px solid ${theme.headerBorder}`,
                      borderRadius: 7, padding: '8px 10px', fontSize: 13,
                      color: theme.text, marginBottom: 4,
                    }}
                  >
                    {/* Whole hours only. The free field accepted 08:07 and
                        the reminder arrived at 08:15 without saying so — the
                        same rule that hides the toggle on an iPhone that
                        can't use it: don't offer what won't be delivered. */}
                    {Array.from({ length: 24 }, (_, h) => {
                      const valor = `${String(h).padStart(2, '0')}:00`;
                      return <option key={valor} value={valor}>{valor}</option>;
                    })}
                  </select>
                )}
```

A `<select>` fires `onChange` only on an actual selection, so it needs no debounce and no blur commit — one request per choice.

- [ ] **Step 3: Handle an hour already saved that is not a whole hour**

A reader who set `06:30` before this change has that value in `localStorage`, and a `<select>` with no matching `<option>` renders blank. In `frontend/src/hooks/useReminder.js`, normalise on read — add immediately after the `useStorage` line for the hour:

```js
  // A broken hour stored before the picker became whole-hours-only (06:30)
  // matches no option and would leave the field blank. Rounds down, to the
  // hour the person chose — 06:30 becomes 06:00, not 07:00: bringing a
  // reminder forward beats pushing it back.
  //
  // The validation isn't caution for its own sake: the value comes from
  // localStorage, which may have been written by an old version, another
  // tab, or by hand. A number stored there has no .slice and would crash the
  // whole Settings panel render — and "7:00" would become "7::00", which the
  // server rejects with a 422.
  const horaCheia = /^([01]\d|2[0-3]):[0-5]\d$/.test(hour)
    ? `${hour.slice(0, 2)}:00`
    : '08:00';
```

and return `hour: horaCheia` instead of `hour`. Leave the stored value alone — it is only read through this normalisation, and rewriting storage on read is a side effect nobody asked for.

**`enable()` must also subscribe with the normalised value, not the raw stored one** — `subscribe(horaCheia)`, not `subscribe(hour)`. This is the one call site the diff above does not touch: without this fix the panel shows `06:00` while the server is still told `06:30`, and with the 60-minute delivery window that fires at `07:00` — a reminder arrives at an hour nobody chose, which is the exact defect this task exists to remove.

- [ ] **Step 4: Add the smoke assertion**

Append to `frontend/tests/smoke.spec.mjs`. The test must actually open Settings — `SettingsPanel` returns `null` unless `open`, so an assertion made against `/` alone can never fail, whether or not the old input still exists. Dismiss the first-visit onboarding overlay (it covers the whole screen and intercepts the click) by pre-seeding `localStorage` before navigating, then click the Settings button via its accessible name (`aria-label="Abrir configurações"`, `TopBar.jsx`):

```js
test('não existe campo de hora livre em Configurações', async ({ page }) => {
  // The scheduler runs hourly, so a field that accepts 08:07 promises what it
  // doesn't deliver. This test fails if anyone brings back the
  // <input type="time">.
  //
  // What it does NOT reach, and it's better to say so than to pretend: the
  // hour picker only appears once the reminder is on, and turning it on
  // requires notification permission, which CI doesn't grant. What can be
  // asserted is the negative over everything the panel renders without that
  // permission — and that's where the old field lived.
  // The first-visit onboarding covers the whole screen and intercepts the
  // click on the Settings button; marking it as already seen before
  // navigating is the same state as someone who has already used the app.
  await page.addInitScript(() => localStorage.setItem('dialogando_onboarded', 'true'));
  await page.goto('/');
  await expect(page.locator('#conteudo-estatico')).toHaveCount(0, { timeout: 15_000 });

  await page.getByLabel('Abrir configurações').click();

  await expect(page.locator('input[type="time"]')).toHaveCount(0);
});
```

**Proof this test can fail:** temporarily reintroducing a stray `<input type="time" />` outside the `reminder.enabled` branch (so it always mounts) makes this test fail with `Expected: 0, Received: 1`; reverting makes it pass again. See the round-1 fix report for both transcripts.

- [ ] **Step 5: Verify and commit**

Run: `cd frontend && npm run build`, then the smoke suite with the agent environment stripped:

```bash
cd frontend && npx astro preview stop >/dev/null 2>&1
env -u CLAUDECODE -u CLAUDE_CODE_SESSION_ID -u AI_AGENT -u CLAUDE_CODE_CHILD_SESSION \
    -u CLAUDE_PID -u CLAUDE_CODE_ENABLE_TASKS -u CLAUDE_CODE_MESSAGING_SOCKET \
    npm run smoke
```

Then rebuild for production (`cd frontend && rm -rf dist && npm run build`) before running the guards from the repo root.

```bash
git add frontend/src/components/modals/SettingsPanel.jsx frontend/src/hooks/useReminder.js frontend/tests/smoke.spec.mjs
git commit -m "feat(frontend): offer whole hours only in the reminder picker

The free time field accepted 08:07 and the reminder arrived at 08:15 without
saying so. An hour already stored as 06:30 is rounded down on read rather
than rewritten — bringing a reminder forward beats pushing it back, and
rewriting someone's storage on read is a side effect nobody asked for."
```

---

### Task 4: The notification carries the day's chapter title

**Files:**
- Modify: `src/push/sender.py`
- Modify: `src/push/dispatch.py`
- Test: `tests/test_push_sender.py`, `tests/test_push_dispatch.py`

**Interfaces:**
- Consumes: `get_daily_passage() -> dict | None` from `src/rag/evangelho.py`, whose `["source"]["chapter_title"]` is the chapter's title as the corpus stores it, in capitals
- Produces: `send(sub: Subscription, chapter_title: str | None = None) -> None`

- [ ] **Step 1: Write the failing tests**

Replace `test_a_notificacao_leva_titulo_corpo_e_destino` in `tests/test_push_sender.py` with:

```python
def test_a_notificacao_leva_o_capitulo_do_dia():
    with patch("src.push.sender.webpush") as enviar:
        send(_SUB, chapter_title="BEM-AVENTURADOS OS QUE TÊM PURO O CORAÇÃO")
    payload = json.loads(enviar.call_args.kwargs["data"])
    assert payload["title"] == "Dialogando com a Doutrina"
    assert "BEM-AVENTURADOS OS QUE TÊM PURO O CORAÇÃO" in payload["body"]
    assert payload["url"] == "/?mode=trecho"


def test_sem_capitulo_a_notificacao_ainda_faz_sentido():
    # Se get_daily_passage falhar, o lembrete sai mesmo assim: melhor um
    # convite genérico que nenhum lembrete.
    with patch("src.push.sender.webpush") as enviar:
        send(_SUB)
    payload = json.loads(enviar.call_args.kwargs["data"])
    assert payload["body"]
    assert payload["url"] == "/?mode=trecho"


def test_o_titulo_do_capitulo_nao_e_transformado():
    # A caixa alta é a do corpus. Baixá-la exigiria uma lista de exceções
    # para DEUS, JESUS, CRISTO, e errar uma vez custa mais que a caixa alta.
    with patch("src.push.sender.webpush") as enviar:
        send(_SUB, chapter_title="AMAI OS VOSSOS INIMIGOS")
    assert "AMAI OS VOSSOS INIMIGOS" in json.loads(enviar.call_args.kwargs["data"])["body"]
```

`import json` at the top of that test file if it is not already there.

- [ ] **Step 2: Run and watch them fail**

Run: `uv run pytest tests/test_push_sender.py -v`
Expected: FAIL — `send()` takes no `chapter_title`.

- [ ] **Step 3: Change the sender**

In `src/push/sender.py`, replace the constants and `send`'s signature and payload:

```python
REMINDER_TITLE = "Dialogando com a Doutrina"
# Sem o capítulo do dia — só quando get_daily_passage falha.
REMINDER_FALLBACK = "A reflexão de hoje está esperando por você."
# O mesmo destino que o card "☀️ Trecho do dia" da barra lateral já abre.
REMINDER_URL = "/?mode=trecho"


def _corpo(chapter_title: str | None) -> str:
    """O corpo da notificação: o capítulo do dia, sem transformação.

    A caixa alta vem do corpus e é como o app já exibe esses títulos. Baixá-la
    exigiria uma lista de exceções para DEUS, JESUS e CRISTO, e errar uma vez
    num app sobre esta doutrina custa mais do que a caixa alta custa.

    Não vai o texto do trecho: ele tem ~517 caracteres, seria cortado, e cortar
    passagem é o erro que a curadoria de 2026-08-05 consertou — 23 trechos
    estavam cortados antes do desfecho, que no Evangelho costuma ser a parte
    misericordiosa.
    """
    if not chapter_title:
        return REMINDER_FALLBACK
    return f"Reflexão de hoje — {chapter_title}"
```

and in `send`, add the parameter and use it:

```python
def send(sub: Subscription, chapter_title: str | None = None) -> None:
```

with the payload's `"body"` becoming `_corpo(chapter_title)`.

- [ ] **Step 4: Make the job pass it**

In `src/push/dispatch.py`, inside `run()`, before the loop:

```python
    # O capítulo do dia, para o corpo da notificação. get_daily_passage é
    # determinístico e não chama modelo nenhum. Se falhar, o lembrete sai com
    # o texto genérico: um convite sem tema é melhor que nenhum lembrete.
    try:
        passagem = get_daily_passage()
        capitulo = (passagem or {}).get("source", {}).get("chapter_title")
    except Exception:
        logger.exception("falha ao ler o trecho do dia")
        passagem, capitulo = None, None
```

with `from src.rag.evangelho import get_daily_passage` at the top, and the send call becoming `sender.send(sub, chapter_title=capitulo)`.

- [ ] **Step 5: Test the job's half**

Append to `tests/test_push_dispatch.py`:

```python
def test_o_capitulo_do_dia_chega_ao_envio():
    sub = _sub("https://push.example/a")
    recebidos = []

    with patch("src.push.dispatch.store.all_subscriptions", return_value=[sub]), \
         patch("src.push.dispatch.store.delete_stale", return_value=0), \
         patch("src.push.dispatch.get_daily_passage",
               return_value={"source": {"chapter_title": "OS AFLITOS"}}), \
         patch("src.push.dispatch.sender.send",
               side_effect=lambda s, chapter_title=None: recebidos.append(chapter_title)):
        run(now_utc=_AGORA)

    assert recebidos == ["OS AFLITOS"]


def test_o_lembrete_sai_mesmo_se_o_trecho_do_dia_falhar():
    # Falha ao ler o trecho não pode virar lembrete não enviado.
    sub = _sub("https://push.example/a")
    enviados = []

    with patch("src.push.dispatch.store.all_subscriptions", return_value=[sub]), \
         patch("src.push.dispatch.store.delete_stale", return_value=0), \
         patch("src.push.dispatch.get_daily_passage", side_effect=OSError("sem arquivo")), \
         patch("src.push.dispatch.sender.send",
               side_effect=lambda s, chapter_title=None: enviados.append(chapter_title)):
        resultado = run(now_utc=_AGORA)

    assert enviados == [None]
    assert resultado["sent"] == 1
```

- [ ] **Step 6: Run everything and commit**

Run: `uv run pytest -q` and the formatters.

```bash
git add src/push/sender.py src/push/dispatch.py tests/test_push_sender.py tests/test_push_dispatch.py
git commit -m "feat(push): put the day's chapter in the notification

It said 'time for your study' — a prod. It now carries the chapter title of
the day's passage, which a reader gets value from on the lock screen without
opening anything.

Not the passage text: at ~517 characters it would be truncated, reproducing
daily the error the 2026-08-05 curation fixed. Not lowercased: that needs an
exception list for DEUS, JESUS, CRISTO. And a failure to read the passage
still sends, with a generic invitation."
```

---

### Task 5: The reflection cache

**Files:**
- Create: `src/core/firestore.py`
- Modify: `src/push/store.py` (use the shared client)
- Create: `src/rag/reflection_cache.py`
- Test: `tests/test_reflection_cache.py`

**Interfaces:**
- Consumes: `settings` from `src/core/config.py`
- Produces:
  - `src/core/firestore.py`: `client()` — the single Firestore seam
  - `src/rag/reflection_cache.py`:
    - `cache_key(passage: dict) -> str`
    - `get(passage: dict) -> dict | None`
    - `put(passage: dict, answer: dict) -> None`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_reflection_cache.py`:

```python
from unittest.mock import MagicMock, patch

from src.rag.reflection_cache import cache_key, get, put

_PASSAGEM = {
    "date": "2026-08-29",
    "source": {
        "book": "O Evangelho Segundo o Espiritismo",
        "chapter": "CAPÍTULO VIII",
        "item_number": "2",
        "part": None,
    },
}
_RESPOSTA = {"contexto": "uma explicação", "sources": []}


def test_a_chave_muda_quando_a_passagem_muda():
    # A regra dura: chaveado pela IDENTIDADE da passagem, não só pela data.
    # Uma correção em trecho_diario.md tem de dar miss, não servir texto velho.
    outra = {**_PASSAGEM, "source": {**_PASSAGEM["source"], "item_number": "3"}}
    assert cache_key(_PASSAGEM) != cache_key(outra)


def test_a_chave_muda_quando_o_dia_muda():
    assert cache_key(_PASSAGEM) != cache_key({**_PASSAGEM, "date": "2026-08-30"})


def test_a_chave_e_estavel_para_a_mesma_passagem():
    assert cache_key(_PASSAGEM) == cache_key(dict(_PASSAGEM))


def test_put_grava_e_get_devolve():
    doc = MagicMock()
    doc.get.return_value.exists = True
    doc.get.return_value.to_dict.return_value = {"answer": _RESPOSTA}
    with patch("src.rag.reflection_cache._colecao") as colecao:
        colecao.return_value.document.return_value = doc
        put(_PASSAGEM, _RESPOSTA)
        assert get(_PASSAGEM) == _RESPOSTA
    doc.set.assert_called_once()


def test_get_devolve_None_quando_nao_existe():
    doc = MagicMock()
    doc.get.return_value.exists = False
    with patch("src.rag.reflection_cache._colecao") as colecao:
        colecao.return_value.document.return_value = doc
        assert get(_PASSAGEM) is None


def test_o_cache_nunca_derruba_uma_resposta():
    # Firestore fora do ar não pode custar a explicação de ninguém: get
    # devolve None e put engole, exatamente como o log de turnos faz.
    with patch("src.rag.reflection_cache._colecao", side_effect=RuntimeError("fora")):
        assert get(_PASSAGEM) is None
        put(_PASSAGEM, _RESPOSTA)  # não levanta
```

- [ ] **Step 2: Run and watch them fail**

Run: `uv run pytest tests/test_reflection_cache.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'src.rag.reflection_cache'`.

- [ ] **Step 3: Extract the Firestore seam**

Create `src/core/firestore.py`:

```python
"""O único lugar do projeto que constrói um cliente do Firestore.

Existe porque agora há duas coleções — as inscrições de push e o cache da
reflexão do dia — e duas costuras separadas dariam dois `lru_cache`, dois
lugares para os testes trocarem, e a chance de as duas divergirem.

O import fica DENTRO da função de propósito: no topo, ele obrigaria a
biblioteca a ser importável na coleta de todo teste deste repositório.
"""

from functools import lru_cache


@lru_cache(maxsize=1)
def client():
    from google.cloud import firestore

    return firestore.Client()
```

In `src/push/store.py`, delete its local `_client()` and import the shared one:

```python
from src.core.firestore import client
```

replacing `_client()` with `client()` in `_colecao()`. Run `uv run pytest tests/test_push_store.py -v` and confirm the five store tests still pass — they patch `_colecao`, not the client, so they should be unaffected. If any fails, STOP and report.

- [ ] **Step 4: Write the cache**

Create `src/rag/reflection_cache.py`:

```python
"""A explicação do trecho do dia, guardada por um dia.

`streamStudy` não leva perfil nem histórico: a resposta é inteiramente
determinada pela passagem, logo é idêntica para todo leitor daquele dia. Sem
cache, isso custa uma chamada de LLM por leitor para produzir o mesmo texto.

Isto NÃO é prosa de modelo fora das guardas, no sentido que o CLAUDE.md
proíbe. Lá, a prosa vinha de outro caminho, sem guarda nenhuma. Aqui é a mesma
pipeline do /study, com max_distance e find_unsupported_quotes rodando como
sempre — uma vez em vez de N — e vive um dia, não anos. Ver
docs/superpowers/specs/2026-08-29-lembrete-de-manha-e-reflexao-em-cache-design.md

Coleção separada da de inscrições, e sem cruzar com ela: o que está aqui é a
mesma reflexão para todo mundo, sem nada de ninguém.
"""

import logging
from hashlib import sha256

from src.core.config import settings
from src.core.firestore import client

logger = logging.getLogger(__name__)


def cache_key(passage: dict) -> str:
    """A identidade da passagem mais a data — nunca a data sozinha.

    Chavear só pela data serviria texto velho depois de uma correção em
    data/markdown_files/trecho_diario.md, e aquele arquivo é curado à mão
    justamente porque é corrigido.
    """
    s = passage.get("source", {})
    cru = "|".join(
        str(x)
        for x in (
            passage.get("date"),
            s.get("book"),
            s.get("chapter"),
            s.get("part"),
            s.get("item_number"),
        )
    )
    return sha256(cru.encode()).hexdigest()


def _colecao():
    return client().collection(settings.reflection_collection)


def get(passage: dict) -> dict | None:
    """A explicação guardada, ou None. Nunca levanta.

    O cache é uma economia, não uma dependência: se o Firestore estiver fora
    do ar, o leitor espera o stream, como espera hoje.
    """
    try:
        doc = _colecao().document(cache_key(passage)).get()
        if not doc.exists:
            return None
        return doc.to_dict().get("answer")
    except Exception:
        logger.exception("falha ao ler o cache da reflexão")
        return None


def put(passage: dict, answer: dict) -> None:
    """Guarda a explicação do dia. Nunca levanta.

    Quem chama é responsável por NÃO chamar isto com uma falha: uma resposta
    retida pelo find_unsupported_quotes, ou um generation_failed, gravada aqui
    seria servida ao dia inteiro.
    """
    try:
        _colecao().document(cache_key(passage)).set({"answer": answer})
    except Exception:
        logger.exception("falha ao gravar o cache da reflexão")
```

- [ ] **Step 5: Add the setting**

In `src/core/config.py`, beside `push_collection`:

```python
    # Coleção separada da de inscrições, de propósito: o cache guarda a mesma
    # reflexão para todo mundo, e não pode nunca virar um campo no registro
    # de um aparelho.
    reflection_collection: str = "daily_reflection"
```

and assert it in `tests/test_config.py`'s existing defaults test.

- [ ] **Step 6: Run and commit**

Run: `uv run pytest tests/test_reflection_cache.py tests/test_push_store.py tests/test_config.py -v`, then `uv run pytest -q` and the formatters.

```bash
git add src/core/firestore.py src/core/config.py src/push/store.py src/rag/reflection_cache.py tests/test_reflection_cache.py tests/test_config.py
git commit -m "feat(rag): cache the day's reflection, keyed by the passage

The daily passage's explanation takes no profile and no history, so it is
identical for every reader that day — and today costs one LLM call per reader
to produce the same words.

Keyed by the passage's identity plus the date, never the date alone: a
correction to trecho_diario.md must miss rather than serve stale prose. Both
get and put swallow their exceptions, because the cache is a saving and not a
dependency: with Firestore down, the reader waits for the stream as they do
now.

The Firestore client moves to src/core/firestore.py now that two collections
need it."
```

---

### Task 6: `/study` reads the cache, and fills it on a miss

**Files:**
- Modify: `src/api/routes.py` (the `/study` and `/study/stream` routes)
- Test: `tests/test_api_push.py` is the wrong home — create `tests/test_reflection_route.py`

**Interfaces:**
- Consumes: `reflection_cache.get/put`, `get_daily_passage`, `study_item_fn`
- Produces: no new route and no schema change — the cache is invisible from outside

- [ ] **Step 1: Write the failing tests**

Create `tests/test_reflection_route.py`:

```python
from unittest.mock import patch

from fastapi.testclient import TestClient

from src.api.main import app

client = TestClient(app)

_HOJE = {
    "date": "2026-08-29",
    "source": {
        "book": "O Evangelho Segundo o Espiritismo",
        "chapter": "CAPÍTULO VIII",
        "item_number": "2",
        "part": None,
    },
}
_PEDIDO = {
    "book": "O Evangelho Segundo o Espiritismo",
    "chapter": "CAPÍTULO VIII",
    "item_number": "2",
}
_RESULTADO = {"contexto": "explicação", "sources": [], "related_items": []}


def test_a_passagem_do_dia_vem_do_cache_sem_chamar_o_modelo():
    with patch("src.api.routes.get_daily_passage", return_value=_HOJE), \
         patch("src.api.routes.reflection_cache.get", return_value=_RESULTADO), \
         patch("src.api.routes.study_item_fn") as modelo:
        r = client.post("/study", json=_PEDIDO)

    assert r.status_code == 200
    modelo.assert_not_called()


def test_um_miss_gera_e_guarda():
    with patch("src.api.routes.get_daily_passage", return_value=_HOJE), \
         patch("src.api.routes.reflection_cache.get", return_value=None), \
         patch("src.api.routes.reflection_cache.put") as guardar, \
         patch("src.api.routes.study_item_fn", return_value=_RESULTADO):
        r = client.post("/study", json=_PEDIDO)

    assert r.status_code == 200
    guardar.assert_called_once()


def test_uma_falha_nunca_e_guardada():
    # A regra dura: um generation_failed gravado seria servido o dia inteiro.
    falha = {"contexto": "", "sources": [], "generation_failed": True}
    with patch("src.api.routes.get_daily_passage", return_value=_HOJE), \
         patch("src.api.routes.reflection_cache.get", return_value=None), \
         patch("src.api.routes.reflection_cache.put") as guardar, \
         patch("src.api.routes.study_item_fn", return_value=falha):
        client.post("/study", json=_PEDIDO)

    guardar.assert_not_called()


def test_outra_passagem_nao_toca_o_cache():
    # /study serve qualquer item; só o do dia passa pelo cache.
    outro = {**_PEDIDO, "item_number": "9"}
    with patch("src.api.routes.get_daily_passage", return_value=_HOJE), \
         patch("src.api.routes.reflection_cache.get") as ler, \
         patch("src.api.routes.reflection_cache.put") as guardar, \
         patch("src.api.routes.study_item_fn", return_value=_RESULTADO):
        client.post("/study", json=outro)

    ler.assert_not_called()
    guardar.assert_not_called()
```

- [ ] **Step 2: Run and watch them fail**

Run: `uv run pytest tests/test_reflection_route.py -v`
Expected: FAIL — `src.api.routes` has no `reflection_cache` attribute.

- [ ] **Step 3: Add the helper and wire the route**

In `src/api/routes.py`, add the imports:

```python
from src.rag import reflection_cache
from src.rag.evangelho import get_daily_passage
```

(`get_daily_passage` may already be imported for `/evangelho` — check before adding a duplicate.)

Then add, near the other private helpers:

```python
def _passagem_do_dia_se_for(request: StudyRequest) -> dict | None:
    """A passagem do dia, quando o pedido é exatamente ela — senão None.

    Só o trecho do dia passa pelo cache. /study serve qualquer item do corpus,
    e cachear tudo é outra decisão, que ninguém tomou.
    """
    try:
        passagem = get_daily_passage()
    except Exception:
        return None
    if not passagem:
        return None
    s = passagem.get("source", {})
    mesmo = (
        s.get("book") == request.book
        and str(s.get("item_number")) == str(request.item_number)
        and (s.get("chapter") or None) == (request.chapter or None)
        and (s.get("part") or None) == (request.part or None)
    )
    return passagem if mesmo else None
```

and in `study()`, between the rate limit and the model call:

```python
    passagem = _passagem_do_dia_se_for(request)
    if passagem is not None:
        guardado = reflection_cache.get(passagem)
        if guardado is not None:
            return _study_response(
                request, guardado, started_at=started,
                session_id=session_id_from(http_request),
            )

    result = study_item_fn(
        request.book, request.item_number, request.chapter, request.part
    )
    if result is None:
        raise _item_not_found(request.item_number)

    # Nunca guardar falha: uma resposta retida ou um generation_failed
    # gravado aqui seria servido ao dia inteiro, para todo mundo.
    if passagem is not None and not result.get("generation_failed"):
        reflection_cache.put(passagem, result)
```

- [ ] **Step 4: Do the same for the streaming route**

`/study/stream` must stay identical to `/study` — a standing rule. In `study_stream()`, after `ctx` is prepared and before `events()` is defined:

```python
    passagem = _passagem_do_dia_se_for(request)
    guardado = reflection_cache.get(passagem) if passagem is not None else None
```

Then inside `events()`, the cache hit short-circuits after the `source` event, which still comes first because the reader reads the passage before its explanation:

```python
    def events():
        yield _sse(
            "source",
            {"original_text": ctx["original_text"], "sources": build_sources(ctx)},
        )
        if guardado is not None:
            # Nada a transmitir quando não há espera: o texto já existe, então
            # ele vai inteiro num `done`. O contrato do stream não muda — `done`
            # continua sendo a fonte da verdade, e continua idêntico ao que
            # POST /study devolve.
            yield _sse("done", _study_response(
                request, guardado, started_at=started, session_id=session_id
            ).model_dump())
            return
        for kind, payload in explicar_stream(ctx):
            if kind == "token":
                yield _sse("token", {"text": payload})
            else:
                response = _study_response(
                    request, payload, started_at=started, session_id=session_id
                )
                # Nunca guardar falha: servida o dia inteiro, para todo mundo.
                if passagem is not None and not payload.get("generation_failed"):
                    reflection_cache.put(passagem, payload)
                yield _sse("done", response.model_dump())
```

Add to `tests/test_reflection_route.py`:

```python
def test_o_stream_do_dia_em_cache_manda_source_e_done_sem_token():
    with patch("src.api.routes.get_daily_passage", return_value=_HOJE), \
         patch("src.api.routes.reflection_cache.get", return_value=_RESULTADO), \
         patch("src.api.routes.prepare_study",
               return_value={"original_text": "t", "chunks": []}), \
         patch("src.api.routes.build_sources", return_value=[]), \
         patch("src.api.routes.explicar_stream") as stream:
        r = client.post("/study/stream", json=_PEDIDO)

    corpo = r.text
    assert "event: source" in corpo
    assert "event: done" in corpo
    assert "event: token" not in corpo
    stream.assert_not_called()
```

- [ ] **Step 4b: Prove the cache cannot drift from the pipeline**

The spec asks for one comparison test, because a cache that silently diverges from what the pipeline would produce is worse than no cache. Add to `tests/test_reflection_route.py`:

```python
def test_a_resposta_em_cache_e_identica_a_resposta_viva():
    # A garantia que o cache existe para dar: mesma passagem, mesma resposta.
    # Se um dia /study passar a levar perfil ou histórico, esta premissa cai —
    # e este teste é o que avisa, em vez de o cache servir a resposta de
    # outra pessoa.
    with patch("src.api.routes.get_daily_passage", return_value=_HOJE), \
         patch("src.api.routes.reflection_cache.get", return_value=None), \
         patch("src.api.routes.reflection_cache.put"), \
         patch("src.api.routes.study_item_fn", return_value=_RESULTADO):
        viva = client.post("/study", json=_PEDIDO).json()

    with patch("src.api.routes.get_daily_passage", return_value=_HOJE), \
         patch("src.api.routes.reflection_cache.get", return_value=_RESULTADO), \
         patch("src.api.routes.study_item_fn") as modelo:
        do_cache = client.post("/study", json=_PEDIDO).json()

    modelo.assert_not_called()
    # `turn_id` é gerado por requisição e legitimamente difere.
    viva.pop("turn_id", None)
    do_cache.pop("turn_id", None)
    assert viva == do_cache
```

If `StudyResponse` has other per-request fields beyond `turn_id`, drop those too and say which in your report — but do NOT drop a field to make the test pass without understanding why it differs. A field that differs and should not is the bug this test exists to find.

- [ ] **Step 5: Verify and commit**

Run: `uv run pytest tests/test_reflection_route.py tests/test_api_study_stream.py -v`, then `uv run pytest -q` and the formatters.

```bash
git add src/api/routes.py tests/test_reflection_route.py
git commit -m "feat(api): serve the day's reflection from cache

Only the daily passage goes through the cache — /study serves any item in
the corpus, and caching all of it is a different decision nobody has taken.

A failure is never stored: a withheld answer or a generation_failed written
here would be served to every reader all day."
```

---

### Task 7: The job warms the cache before it sends

**Files:**
- Modify: `src/push/dispatch.py`
- Test: `tests/test_push_dispatch.py`

**Interfaces:**
- Consumes: `reflection_cache.get/put`, `study_item_fn`, `get_daily_passage`
- Produces: `run()` returns the same counts dict, with the warm-up done first

A lazy cache defeats itself precisely because the reminder works: at 08:00 everyone opens within seconds, everyone misses, and one call a day becomes dozens inside a minute.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_push_dispatch.py`:

```python
def test_o_cache_e_aquecido_antes_de_enviar():
    # A ordem é o desenho, não detalhe: se o envio viesse primeiro, todo mundo
    # abriria num cache frio e a economia inteira sumiria.
    ordem = []
    sub = _sub("https://push.example/a")

    with patch("src.push.dispatch.store.all_subscriptions", return_value=[sub]), \
         patch("src.push.dispatch.store.delete_stale", return_value=0), \
         patch("src.push.dispatch.get_daily_passage",
               return_value={"source": {"chapter_title": "X", "book": "b",
                                        "item_number": "1", "chapter": None,
                                        "part": None}}), \
         patch("src.push.dispatch.reflection_cache.get", return_value=None), \
         patch("src.push.dispatch.reflection_cache.put",
               side_effect=lambda *a: ordem.append("aqueceu")), \
         patch("src.push.dispatch.study_item_fn", return_value={"contexto": "c"}), \
         patch("src.push.dispatch.sender.send",
               side_effect=lambda *a, **k: ordem.append("enviou")):
        run(now_utc=_AGORA)

    assert ordem == ["aqueceu", "enviou"]


def test_cache_ja_quente_nao_chama_o_modelo():
    sub = _sub("https://push.example/a")
    with patch("src.push.dispatch.store.all_subscriptions", return_value=[sub]), \
         patch("src.push.dispatch.store.delete_stale", return_value=0), \
         patch("src.push.dispatch.get_daily_passage",
               return_value={"source": {"chapter_title": "X", "book": "b",
                                        "item_number": "1", "chapter": None,
                                        "part": None}}), \
         patch("src.push.dispatch.reflection_cache.get", return_value={"contexto": "c"}), \
         patch("src.push.dispatch.study_item_fn") as modelo, \
         patch("src.push.dispatch.sender.send"):
        run(now_utc=_AGORA)

    modelo.assert_not_called()


def test_um_aquecimento_que_falha_ainda_envia():
    # Cache frio é um leitor mais lento; lembrete suprimido é um leitor que
    # nunca soube.
    sub = _sub("https://push.example/a")
    enviados = []

    with patch("src.push.dispatch.store.all_subscriptions", return_value=[sub]), \
         patch("src.push.dispatch.store.delete_stale", return_value=0), \
         patch("src.push.dispatch.get_daily_passage",
               return_value={"source": {"chapter_title": "X", "book": "b",
                                        "item_number": "1", "chapter": None,
                                        "part": None}}), \
         patch("src.push.dispatch.reflection_cache.get", return_value=None), \
         patch("src.push.dispatch.study_item_fn", side_effect=RuntimeError("modelo fora")), \
         patch("src.push.dispatch.sender.send",
               side_effect=lambda *a, **k: enviados.append(1)):
        resultado = run(now_utc=_AGORA)

    assert enviados == [1]
    assert resultado["sent"] == 1
```

- [ ] **Step 2: Run and watch them fail**

Run: `uv run pytest tests/test_push_dispatch.py -v`
Expected: FAIL — `src.push.dispatch` has no `reflection_cache`.

- [ ] **Step 3: Implement the warm-up**

In `src/push/dispatch.py`, add the imports:

```python
from src.rag import reflection_cache
from src.rag.explicador import explicar as study_item_fn
```

and a helper, called from `run()` right after the passage is read and before the send loop:

```python
def _aquecer(passagem: dict | None) -> None:
    """Garante a explicação do dia no cache, antes de qualquer envio.

    Um cache preguiçoso se sabota justamente porque o lembrete funciona: às
    08:00 a notificação chega para todos ao mesmo tempo, todos abrem em
    segundos, todos encontram o cache vazio, e uma chamada por dia vira dezenas
    dentro de um minuto — cada uma delas esperando o stream que o cache existia
    para eliminar.

    Falhar aqui não pode segurar o lembrete: quem abrir cai no caminho normal,
    com o stream, como cai hoje.
    """
    if passagem is None:
        return
    if reflection_cache.get(passagem) is not None:
        return
    s = passagem.get("source", {})
    try:
        resultado = study_item_fn(
            s.get("book"), s.get("item_number"), s.get("chapter"), s.get("part")
        )
    except Exception:
        logger.exception("falha ao aquecer o cache da reflexão")
        return
    if resultado and not resultado.get("generation_failed"):
        reflection_cache.put(passagem, resultado)
```

- [ ] **Step 4: Run and commit**

Run: `uv run pytest tests/test_push_dispatch.py -v`, then `uv run pytest -q` and the formatters.

```bash
git add src/push/dispatch.py tests/test_push_dispatch.py
git commit -m "feat(push): warm the day's reflection before sending

A lazy cache defeats itself precisely because the reminder works: at 08:00
everyone opens within seconds, everyone misses, and one call a day becomes
dozens inside a minute — each of those readers waiting for the stream the
cache existed to remove.

The work was already in the right place: the job computes the day's passage
anyway, to build the notification body. A failed warm-up still sends."
```

---

### Task 8: Rules, deploy and status

**Files:**
- Modify: `CLAUDE.md`
- Modify: `docs/deploy.md`
- Modify: `docs/superpowers/specs/2026-08-29-lembrete-de-manha-e-reflexao-em-cache-design.md` (status)
- Modify: `docs/superpowers/specs/README.md` (state column)

- [ ] **Step 1: Extend the push rule in CLAUDE.md**

Find the bullet beginning "**The push subscription store is the only persistence in this project**" — that claim is now false. Rewrite its opening so it names both collections, and append:

```markdown
  The **second** collection caches the daily passage's explanation for a day, keyed by the passage's identity plus the date — never the date alone, or a correction to `trecho_diario.md` would serve stale prose. It is legitimate where a generated page is not: the text comes from the same `/study` pipeline with `max_distance` and `find_unsupported_quotes` running as always, once instead of N times, and it lives a day rather than years. **A failure is never cached** — a withheld answer served all day is the difference between saving a call and publishing a defect. The dispatch job warms it *before* sending, because a lazy cache defeats itself when everyone opens at once, and a failed warm-up still sends.
```

- [ ] **Step 2: Add the Firestore rule about the two collections**

In `docs/deploy.md`'s push section, after the Firestore creation command, add:

```markdown
São **duas** coleções, e a separação é a salvaguarda: `push_subscriptions`
guarda um registro por aparelho e não cruza com nada; `daily_reflection`
guarda a mesma explicação para todo mundo e não guarda nada de ninguém.
Nenhuma das duas ganha campo da outra.
```

- [ ] **Step 3: Flip the statuses**

In the spec, `**Status:** approved, pending implementation` becomes `**Status:** implemented`.
In `docs/superpowers/specs/README.md`, that row's `**pendente**` becomes `vale`.
Both are inside a git-ignored directory — stage with `git add -f`.

- [ ] **Step 4: Full verification**

```bash
uv run black --check src/ tests/ && uv run isort --check-only src/ tests/
uv run pytest -q
cd frontend && rm -rf dist && npm run build && cd ..
for g in check_chat_current_mode check_cited_text check_followup_reply \
         check_discovery_assets check_api_base check_consent_prompt \
         check_pwa_manifest check_push_service_worker; do
  node scripts/$g.mjs > /dev/null && echo "$g ok" || echo "$g FALHOU"; done
```

Then the smoke suite with the agent environment stripped, and rebuild for production afterwards.

- [ ] **Step 5: Commit**

```bash
git add CLAUDE.md docs/deploy.md
git add -f docs/superpowers/specs/
git commit -m "docs: two collections, and the rule that keeps them apart

CLAUDE.md said the push store was the only persistence in this project.
That is no longer true, and the replacement says what makes the second one
legitimate where a generated page is not: same pipeline, same guards, one day
rather than years — and never a cached failure."
```

---

### Task 9: The verification no automation replaces

**Files:** none

- [ ] **Step 1: Confirm the picker on a real phone**

Open Settings, turn the reminder on, and confirm the hour control offers whole hours only and shows the stored hour.

- [ ] **Step 2: Receive one**

Set the reminder for the next whole hour, lock the phone, and wait. The notification must read `Dialogando com a Doutrina` / `Reflexão de hoje — <CAPÍTULO>`, and the chapter must be the same one the app shows for today's passage.

- [ ] **Step 3: Tap it, and count the seconds**

The daily passage must open with its explanation **already there**, not streaming in. That is the whole point of the cache, and it is the one thing no test here can prove.

- [ ] **Step 4: Open it again from a different device**

The explanation must be identical, word for word. That is the shared-reflection property, and it is only observable with two devices.
