# Study Reminder over Web Push — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Bring the daily study reminder back as a real notification that arrives with the app closed, without the backend learning anything about anyone beyond a device endpoint and an hour.

**Architecture:** A Firestore collection holds one record per device. A Cloud Run Job — the same container image, a different command — runs every 15 minutes under Cloud Scheduler, finds the devices whose local time has just reached their chosen hour, sends through `pywebpush`, deletes anything the push service reports as gone, and sweeps records untouched for 90 days. The frontend registers a service worker that handles `push` and `notificationclick` and nothing else.

**Tech Stack:** Python 3.12, FastAPI, `google-cloud-firestore`, `pywebpush`, Cloud Run Jobs, Cloud Scheduler, Secret Manager; Astro + React on the frontend; pytest and `.mjs` guards.

**Spec:** [docs/superpowers/specs/2026-08-27-lembrete-push-design.md](../specs/2026-08-27-lembrete-push-design.md)

## Global Constraints

- **The stored record is exactly `{endpoint, keys, hour, timezone, last_seen}`.** No name, e-mail, IP, user-agent, or any identifier this project generated. Adding a sixth field requires re-opening the spec.
- **The subscription is never joined to anything** — not `session_id`, not the turn log, not `POST /feedback`, not a conversation. `src/rag/conversation_log.py` gains no field from this work.
- **The privacy copy moves before the store exists.** Task 1 ships first and is not reordered.
- **The service worker registers `push` and `notificationclick` only.** No `fetch` handler, no cache, no request interception — that is what reconciles this with [2026-08-27-pwa-instalavel-design](../specs/2026-08-27-pwa-instalavel-design.md).
- **On iOS the toggle is shown only when the app is installed** (`display-mode: standalone`). Where it cannot work, show the install path instead. Never a control that silently does nothing.
- **Astro exposes `PUBLIC_`-prefixed variables, not `VITE_`.** The VAPID public key reaches the bundle as `PUBLIC_VAPID_KEY`. Getting this wrong put `localhost:8000` into production on 2026-08-09; `scripts/check_api_base.mjs` exists because of it.
- **Deletion is on three triggers:** reader turns it off, push service answers `410`, and 90 days without `last_seen` being refreshed.
- Runtime dependencies only; nothing here goes near the `ingest` group.
- Code comments in Portuguese, matching the surrounding files. Commit messages in English.

---

### Task 1: Move the privacy copy before anything stores anything

**Files:**
- Modify: `frontend/src/constants/contact.js:26-31`
- Modify: `frontend/src/pages/sobre.astro`
- Test: manual read + `node scripts/check_discovery_assets.mjs`

**Interfaces:**
- Consumes: nothing
- Produces: `PRIVACY_NOTICE` mentioning the reminder — Task 7's guard greps for it

The standing rule is that the privacy copy may promise less than the code does, never more. Today it describes a system that stores nothing of the kind, so this task exists to be first. It is the only task in the plan whose ordering is load-bearing.

- [ ] **Step 1: Read the current copy**

Run: `sed -n '20,40p' frontend/src/constants/contact.js`
Note that `PRIVACY_NOTICE` currently ends at "Depois de 12 meses as mensagens serão apagadas."

- [ ] **Step 2: Extend `PRIVACY_NOTICE`**

In `frontend/src/constants/contact.js`, replace the `PRIVACY_NOTICE` export with:

```js
export const PRIVACY_NOTICE =
  'Guardo as conversas de forma anônima, só para entender o que precisa ' +
  'melhorar. Não fica nada que identifique você. Se você autorizar, as ' +
  'perguntas de uma mesma conversa ficam ligadas entre si enquanto a aba ' +
  'estiver aberta; isso ajuda quando uma resposta ruim só faz sentido junto ' +
  'com o que veio antes. Depois de 12 meses as mensagens serão apagadas. ' +
  'Se você ligar o lembrete diário, guardo o endereço de notificação do seu ' +
  'aparelho e a hora que você escolheu — só isso, separado das conversas e ' +
  'sem ligação com elas. Some quando você desliga o lembrete, quando o ' +
  'aparelho deixa de existir, ou depois de 90 dias sem uso.';
```

- [ ] **Step 3: Add the same promise to the Sobre page**

In `frontend/src/pages/sobre.astro`, inside the existing privacy/explanation prose, add one paragraph:

```html
<p>
  Se você ligar o lembrete diário, este site guarda o endereço de notificação
  do seu aparelho e a hora escolhida — nada além disso, e separado das
  conversas. Você desliga quando quiser, e o registro é apagado.
</p>
```

- [ ] **Step 4: Verify the page still builds and the guards pass**

Run: `cd frontend && npm run build && cd .. && node scripts/check_discovery_assets.mjs`
Expected: build succeeds, guard exits 0.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/constants/contact.js frontend/src/pages/sobre.astro
git commit -m "docs(frontend): promise the reminder's storage before it exists

The privacy copy may promise less than the code does, never more. Storing
first and editing after is the one way to actually break that rule, so this
lands before a single subscription can be written."
```

---

### Task 2: Settings for VAPID and the push store

**Files:**
- Modify: `src/core/config.py`
- Test: `tests/test_config.py`

**Interfaces:**
- Consumes: nothing
- Produces: `settings.vapid_public_key`, `settings.vapid_private_key`, `settings.vapid_subject`, `settings.push_collection`, `settings.push_expiry_days`, `settings.push_window_minutes`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_config.py`:

```python
def test_push_settings_have_safe_defaults():
    from src.core.config import Settings

    s = Settings(_env_file=None)
    # Sem chave configurada o push simplesmente não existe — o dispatch
    # verifica isto e sai, em vez de tentar enviar sem assinar.
    assert s.vapid_public_key == ""
    assert s.vapid_private_key == ""
    assert s.push_collection == "push_subscriptions"
    assert s.push_expiry_days == 90
    assert s.push_window_minutes == 15
```

- [ ] **Step 2: Run it and watch it fail**

Run: `uv run pytest tests/test_config.py::test_push_settings_have_safe_defaults -v`
Expected: FAIL — `AttributeError` / `ValidationError` on `vapid_public_key`.

- [ ] **Step 3: Add the fields**

In `src/core/config.py`, inside the `Settings` class, add:

```python
    # Web Push. Vazias por padrão: sem chave o dispatch não roda, em vez de
    # tentar enviar sem assinatura. Ver
    # docs/superpowers/specs/2026-08-27-lembrete-push-design.md
    vapid_public_key: str = ""
    vapid_private_key: str = ""
    # O "subject" do VAPID é um contato que o serviço de push usa se algo der
    # errado do lado dele. mailto: ou uma URL.
    vapid_subject: str = "mailto:contato@dialogandodoutrina.com.br"
    push_collection: str = "push_subscriptions"
    # Os três números da spec. 90 dias é o único arbitrado — os outros dois
    # saem de restrição real (fusos de quarto de hora).
    push_expiry_days: int = 90
    push_window_minutes: int = 15
```

- [ ] **Step 4: Run the test**

Run: `uv run pytest tests/test_config.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/core/config.py tests/test_config.py
git commit -m "feat(config): add VAPID and push store settings"
```

---

### Task 3: The due-time calculation, as a pure function

**Files:**
- Create: `src/push/__init__.py`
- Create: `src/push/schedule.py`
- Test: `tests/test_push_schedule.py`

**Interfaces:**
- Consumes: nothing
- Produces: `is_due(hour: str, timezone_name: str, now_utc: datetime, window_minutes: int) -> bool`
  (the parameter is `timezone_name`, not `timezone`: this module imports
  `datetime.timezone`, and a parameter of that name would shadow it)

This is the only real logic in the feature and it touches no network, so it is written first and tested exhaustively. Everything else is plumbing around it.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_push_schedule.py`:

```python
from datetime import datetime, timezone

from src.push.schedule import is_due

# 2026-08-27 11:00 UTC é 08:00 em São Paulo (UTC-3).
_ONZE_UTC = datetime(2026, 8, 27, 11, 0, tzinfo=timezone.utc)


def test_esta_na_janela_quando_a_hora_local_bate():
    assert is_due("08:00", "America/Sao_Paulo", _ONZE_UTC, 15)


def test_fora_da_janela_uma_hora_antes():
    assert not is_due("08:00", "America/Sao_Paulo",
                      datetime(2026, 8, 27, 10, 0, tzinfo=timezone.utc), 15)


def test_a_janela_pega_quem_ficou_alguns_minutos_para_tras():
    # O Job roda de 15 em 15; quem escolheu 08:10 tem de ser pego pela
    # execução das 08:00-08:15 local, senão nunca recebe.
    assert is_due("08:10", "America/Sao_Paulo",
                  datetime(2026, 8, 27, 11, 10, tzinfo=timezone.utc), 15)


def test_nao_dispara_duas_vezes_na_mesma_janela():
    # 08:00 está na janela que começa às 08:00, e não na seguinte.
    assert is_due("08:00", "America/Sao_Paulo", _ONZE_UTC, 15)
    assert not is_due("08:00", "America/Sao_Paulo",
                      datetime(2026, 8, 27, 11, 15, tzinfo=timezone.utc), 15)


def test_fuso_de_meia_hora():
    # Índia é UTC+5:30. 02:30 UTC é 08:00 lá.
    assert is_due("08:00", "Asia/Kolkata",
                  datetime(2026, 8, 27, 2, 30, tzinfo=timezone.utc), 15)


def test_fuso_desconhecido_nao_explode_e_nao_dispara():
    # Um fuso inválido vindo do cliente não pode derrubar o Job inteiro:
    # aquele registro simplesmente não é elegível.
    assert not is_due("08:00", "Nao/Existe", _ONZE_UTC, 15)


def test_hora_malformada_nao_dispara():
    assert not is_due("banana", "America/Sao_Paulo", _ONZE_UTC, 15)
```

- [ ] **Step 2: Run them and watch them fail**

Run: `uv run pytest tests/test_push_schedule.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'src.push'`.

- [ ] **Step 3: Write the implementation**

Create `src/push/__init__.py` (empty file).

Create `src/push/schedule.py`:

```python
"""Quem está na janela de envio agora.

Função pura, sem rede e sem Firestore, porque é a única lógica de verdade
desta funcionalidade: todo o resto é encanamento. Testar isto exige só um
relógio fixo.
"""

from datetime import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


def is_due(
    hour: str, timezone_name: str, now_utc: datetime, window_minutes: int
) -> bool:
    """True quando a hora local de `timezone_name` acabou de passar por `hour`.

    A janela é [início, início + window_minutes), fechada embaixo e aberta em
    cima — é isso que impede o mesmo registro de disparar em duas execuções
    consecutivas do Job.

    Entrada malformada (fuso inexistente, hora fora de HH:MM) devolve False em
    vez de levantar: os dados vêm do cliente, e um registro estragado não pode
    derrubar o envio de todos os outros.
    """
    try:
        alvo_h, alvo_m = (int(parte) for parte in hour.split(":"))
    except (ValueError, AttributeError):
        return False
    if not (0 <= alvo_h <= 23 and 0 <= alvo_m <= 59):
        return False

    try:
        local = now_utc.astimezone(ZoneInfo(timezone_name))
    except (ZoneInfoNotFoundError, ValueError):
        return False

    agora_min = local.hour * 60 + local.minute
    alvo_min = alvo_h * 60 + alvo_m
    # A distância à frente do alvo, dando a volta na meia-noite.
    desde_alvo = (agora_min - alvo_min) % (24 * 60)
    return desde_alvo < window_minutes
```

- [ ] **Step 4: Run the tests**

Run: `uv run pytest tests/test_push_schedule.py -v`
Expected: 7 passed.

- [ ] **Step 5: Commit**

```bash
git add src/push/__init__.py src/push/schedule.py tests/test_push_schedule.py
git commit -m "feat(push): decide who is due, as a pure function

The only real logic in the reminder, so it is written with no network and no
Firestore near it. A malformed timezone or hour from a client returns False
rather than raising: one bad record must not stop everyone else's reminder."
```

---

### Task 4: The store

**Files:**
- Create: `src/push/store.py`
- Test: `tests/test_push_store.py`

**Interfaces:**
- Consumes: `settings.push_collection`, `settings.push_expiry_days`
- Produces:
  - `Subscription(endpoint: str, keys: dict[str, str], hour: str, timezone: str, last_seen: date)`
  - `save(sub: Subscription) -> None`
  - `delete(endpoint: str) -> None`
  - `touch(endpoint: str, today: date) -> None`
  - `all_subscriptions() -> list[Subscription]`
  - `delete_stale(today: date, max_age_days: int) -> int`
  - `_client()` — the seam tests patch

- [ ] **Step 1: Write the failing tests**

Create `tests/test_push_store.py`:

```python
from datetime import date
from unittest.mock import patch

from src.push.store import Subscription, delete_stale, from_document, to_document


def _sub(**over):
    base = dict(
        endpoint="https://push.example/abc",
        keys={"p256dh": "chave-publica", "auth": "segredo"},
        hour="08:00",
        timezone="America/Sao_Paulo",
        last_seen=date(2026, 8, 27),
    )
    base.update(over)
    return Subscription(**base)


def test_o_documento_tem_exatamente_os_cinco_campos():
    # A regra dura da spec: um sexto campo exige reabrir a decisão. Este
    # teste é onde essa regra vira código.
    assert set(to_document(_sub())) == {
        "endpoint", "keys", "hour", "timezone", "last_seen",
    }


def test_ida_e_volta_preserva_o_registro():
    sub = _sub()
    assert from_document(to_document(sub)) == sub


def test_delete_stale_apaga_quem_passou_do_prazo():
    velho = _sub(endpoint="https://push.example/velho", last_seen=date(2026, 5, 1))
    novo = _sub(endpoint="https://push.example/novo", last_seen=date(2026, 8, 20))
    apagados = []

    with patch("src.push.store.all_subscriptions", return_value=[velho, novo]), \
         patch("src.push.store.delete", side_effect=apagados.append):
        n = delete_stale(today=date(2026, 8, 27), max_age_days=90)

    assert n == 1
    assert apagados == ["https://push.example/velho"]


def test_delete_stale_nao_apaga_exatamente_no_limite():
    # 90 dias exatos ainda está dentro; só o 91º sai.
    no_limite = _sub(last_seen=date(2026, 5, 29))
    with patch("src.push.store.all_subscriptions", return_value=[no_limite]), \
         patch("src.push.store.delete") as apagar:
        n = delete_stale(today=date(2026, 8, 27), max_age_days=90)

    assert n == 0
    apagar.assert_not_called()
```

- [ ] **Step 2: Run them and watch them fail**

Run: `uv run pytest tests/test_push_store.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'src.push.store'`.

- [ ] **Step 3: Write the implementation**

Create `src/push/store.py`:

```python
"""O primeiro armazenamento da história deste projeto.

Cinco campos, num store que não cruza com nada: nunca com `session_id`, nunca
com o log de turnos, nunca com o feedback. Essa separação não é detalhe de
implementação — é a salvaguarda inteira. Ver
docs/superpowers/specs/2026-08-27-lembrete-push-design.md

`_client()` é a costura: os testes trocam ele, e nada aqui fala com o
Firestore fora desta função.
"""

from dataclasses import dataclass
from datetime import date, timedelta
from functools import lru_cache

from src.core.config import settings


@dataclass(frozen=True)
class Subscription:
    endpoint: str
    keys: dict[str, str]
    hour: str
    timezone: str
    last_seen: date

    # Sem __eq__ próprio: o do dataclass compara campo a campo e `keys` é um
    # dict, que compara por valor. Escrever um à mão aqui seria pior do que
    # inútil — com eq=True (o padrão) o dataclass instala o dele DEPOIS do
    # corpo da classe, e o escrito à mão sumiria sem aviso.


def to_document(sub: Subscription) -> dict:
    """O registro como vai para o Firestore — e só ele.

    Escrito à mão em vez de `asdict()` de propósito: um campo novo no
    dataclass não vaza para o store sem alguém passar por aqui e reler a
    regra acima.
    """
    return {
        "endpoint": sub.endpoint,
        "keys": sub.keys,
        "hour": sub.hour,
        "timezone": sub.timezone,
        "last_seen": sub.last_seen.isoformat(),
    }


def from_document(doc: dict) -> Subscription:
    return Subscription(
        endpoint=doc["endpoint"],
        keys=doc["keys"],
        hour=doc["hour"],
        timezone=doc["timezone"],
        last_seen=date.fromisoformat(doc["last_seen"]),
    )


@lru_cache(maxsize=1)
def _client():
    from google.cloud import firestore

    return firestore.Client()


def _doc_id(endpoint: str) -> str:
    """O id do documento é o hash do endpoint, não o endpoint.

    Endpoint tem barra e é longo demais para id de documento; o hash é
    estável e serve de chave sem precisar de índice.
    """
    from hashlib import sha256

    return sha256(endpoint.encode()).hexdigest()


def _colecao():
    return _client().collection(settings.push_collection)


def save(sub: Subscription) -> None:
    _colecao().document(_doc_id(sub.endpoint)).set(to_document(sub))


def delete(endpoint: str) -> None:
    _colecao().document(_doc_id(endpoint)).delete()


def touch(endpoint: str, today: date) -> None:
    """Carimba last_seen. Só a data — nada sobre a visita."""
    _colecao().document(_doc_id(endpoint)).update(
        {"last_seen": today.isoformat()}
    )


def all_subscriptions() -> list[Subscription]:
    return [from_document(d.to_dict()) for d in _colecao().stream()]


def delete_stale(today: date, max_age_days: int) -> int:
    """Apaga quem não aparece há mais de `max_age_days`. Devolve quantos.

    Existe porque desligar e o 410 não bastam: quem simplesmente parou de usar
    nunca aperta botão nenhum, e sem isto ficaria registrado para sempre. O
    apagamento não pode depender de a pessoa pedir.
    """
    limite = today - timedelta(days=max_age_days)
    apagados = 0
    for sub in all_subscriptions():
        if sub.last_seen < limite:
            delete(sub.endpoint)
            apagados += 1
    return apagados
```

- [ ] **Step 4: Run the tests**

Run: `uv run pytest tests/test_push_store.py -v`
Expected: 4 passed.

- [ ] **Step 5: Add the dependencies**

Run: `uv add google-cloud-firestore pywebpush`
Then confirm they landed in `[project] dependencies` (runtime), **not** in the `ingest` group:
Run: `sed -n '/^dependencies/,/^\]/p' pyproject.toml`

- [ ] **Step 6: Commit**

```bash
git add src/push/store.py tests/test_push_store.py pyproject.toml uv.lock
git commit -m "feat(push): add the subscription store

Five fields and a hand-written serializer rather than asdict(), so a new
field on the dataclass cannot reach the store without someone passing
through to_document() and re-reading the rule above it. delete_stale exists
because turning it off and 410 are not enough on their own: someone who just
stops using the app never presses a button, and deletion must not require
them to ask."
```

---

### Task 5: The sender

**Files:**
- Create: `src/push/sender.py`
- Test: `tests/test_push_sender.py`

**Interfaces:**
- Consumes: `Subscription` from Task 4, `settings.vapid_*`
- Produces: `Gone` (exception), `send(sub: Subscription) -> None`, `REMINDER_TITLE`, `REMINDER_BODY`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_push_sender.py`:

```python
from datetime import date
from unittest.mock import patch

import pytest

from src.push.sender import Gone, send
from src.push.store import Subscription

_SUB = Subscription(
    endpoint="https://push.example/abc",
    keys={"p256dh": "chave", "auth": "segredo"},
    hour="08:00",
    timezone="America/Sao_Paulo",
    last_seen=date(2026, 8, 27),
)


class _Resposta:
    def __init__(self, status_code):
        self.status_code = status_code


def test_410_vira_Gone():
    # O serviço de push dizendo 410 significa "este aparelho não existe
    # mais". Reenviar é inútil; o registro sai na hora.
    with patch("src.push.sender.webpush", return_value=_Resposta(410)):
        with pytest.raises(Gone):
            send(_SUB)


def test_404_tambem_vira_Gone():
    with patch("src.push.sender.webpush", return_value=_Resposta(404)):
        with pytest.raises(Gone):
            send(_SUB)


def test_201_passa_sem_erro():
    with patch("src.push.sender.webpush", return_value=_Resposta(201)):
        send(_SUB)


def test_a_notificacao_leva_titulo_corpo_e_destino():
    with patch("src.push.sender.webpush", return_value=_Resposta(201)) as enviar:
        send(_SUB)
    payload = enviar.call_args.kwargs["data"]
    assert "Dialogando" in payload
    assert "trecho" in payload
```

- [ ] **Step 2: Run them and watch them fail**

Run: `uv run pytest tests/test_push_sender.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'src.push.sender'`.

- [ ] **Step 3: Write the implementation**

Create `src/push/sender.py`:

```python
"""Envio de uma notificação, e o tratamento do aparelho que sumiu."""

import json

from pywebpush import webpush

from src.core.config import settings
from src.push.store import Subscription

REMINDER_TITLE = "Dialogando com a Doutrina 📖"
REMINDER_BODY = "É a hora do seu estudo. Que tal começar pelo trecho de hoje?"
# O mesmo destino que o card "☀️ Trecho do dia" da barra lateral já abre.
REMINDER_URL = "/?mode=trecho"


class Gone(Exception):
    """O serviço de push diz que este endpoint não existe mais."""


def send(sub: Subscription) -> None:
    """Envia o lembrete. Levanta Gone quando o registro deve ser apagado.

    410 e 404 são as duas respostas que significam "esse aparelho acabou" —
    qualquer outra falha é transitória e o Job simplesmente tenta de novo no
    dia seguinte, sem apagar nada.
    """
    resposta = webpush(
        subscription_info={"endpoint": sub.endpoint, "keys": sub.keys},
        data=json.dumps(
            {"title": REMINDER_TITLE, "body": REMINDER_BODY, "url": REMINDER_URL}
        ),
        vapid_private_key=settings.vapid_private_key,
        vapid_claims={"sub": settings.vapid_subject},
    )
    if resposta.status_code in (404, 410):
        raise Gone(sub.endpoint)
```

- [ ] **Step 4: Run the tests**

Run: `uv run pytest tests/test_push_sender.py -v`
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add src/push/sender.py tests/test_push_sender.py
git commit -m "feat(push): send one reminder, and recognise a dead endpoint

410 and 404 are the two answers meaning the device is gone, and they delete
the record on the spot. Every other failure is transient: the job tries again
tomorrow rather than throwing away a subscription over a bad minute."
```

---

### Task 6: The dispatch job

**Files:**
- Create: `src/push/dispatch.py`
- Test: `tests/test_push_dispatch.py`

**Interfaces:**
- Consumes: `is_due` (Task 3), store functions (Task 4), `send`/`Gone` (Task 5)
- Produces: `run(now_utc: datetime | None = None) -> dict[str, int]` returning `{"sent", "gone", "failed", "expired"}`, and `main() -> None`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_push_dispatch.py`:

```python
from datetime import date, datetime, timezone
from unittest.mock import patch

from src.push.dispatch import run
from src.push.sender import Gone
from src.push.store import Subscription

_AGORA = datetime(2026, 8, 27, 11, 0, tzinfo=timezone.utc)  # 08:00 em SP


def _sub(endpoint, hour="08:00"):
    return Subscription(
        endpoint=endpoint,
        keys={"p256dh": "c", "auth": "s"},
        hour=hour,
        timezone="America/Sao_Paulo",
        last_seen=date(2026, 8, 27),
    )


def test_envia_so_para_quem_esta_na_janela():
    na_hora = _sub("https://push.example/agora", "08:00")
    mais_tarde = _sub("https://push.example/depois", "20:00")
    enviados = []

    with patch("src.push.dispatch.store.all_subscriptions",
               return_value=[na_hora, mais_tarde]), \
         patch("src.push.dispatch.store.delete_stale", return_value=0), \
         patch("src.push.dispatch.sender.send", side_effect=lambda s: enviados.append(s.endpoint)):
        resultado = run(now_utc=_AGORA)

    assert enviados == ["https://push.example/agora"]
    assert resultado["sent"] == 1


def test_Gone_apaga_o_registro():
    sub = _sub("https://push.example/morto")
    apagados = []

    with patch("src.push.dispatch.store.all_subscriptions", return_value=[sub]), \
         patch("src.push.dispatch.store.delete_stale", return_value=0), \
         patch("src.push.dispatch.store.delete", side_effect=apagados.append), \
         patch("src.push.dispatch.sender.send", side_effect=Gone("x")):
        resultado = run(now_utc=_AGORA)

    assert apagados == ["https://push.example/morto"]
    assert resultado["gone"] == 1
    assert resultado["sent"] == 0


def test_uma_falha_nao_impede_os_outros():
    # Um endpoint com problema não pode custar o lembrete de todo mundo.
    ruim = _sub("https://push.example/ruim")
    bom = _sub("https://push.example/bom")
    enviados = []

    def enviar(sub):
        if sub.endpoint.endswith("ruim"):
            raise RuntimeError("timeout")
        enviados.append(sub.endpoint)

    with patch("src.push.dispatch.store.all_subscriptions", return_value=[ruim, bom]), \
         patch("src.push.dispatch.store.delete_stale", return_value=0), \
         patch("src.push.dispatch.sender.send", side_effect=enviar):
        resultado = run(now_utc=_AGORA)

    assert enviados == ["https://push.example/bom"]
    assert resultado["failed"] == 1
    assert resultado["sent"] == 1


def test_a_varredura_dos_90_dias_roda_junto():
    with patch("src.push.dispatch.store.all_subscriptions", return_value=[]), \
         patch("src.push.dispatch.store.delete_stale", return_value=3) as varrer:
        resultado = run(now_utc=_AGORA)

    assert resultado["expired"] == 3
    assert varrer.call_args.kwargs["max_age_days"] == 90
```

- [ ] **Step 2: Run them and watch them fail**

Run: `uv run pytest tests/test_push_dispatch.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'src.push.dispatch'`.

- [ ] **Step 3: Write the implementation**

Create `src/push/dispatch.py`:

```python
"""O que o Cloud Run Job executa a cada 15 minutos.

Roda a mesma imagem da API com outro comando, de propósito: um endpoint na
API exigiria validar OIDC numa superfície pública, e este Job não tem
superfície nenhuma.

Rode com: python -m src.push.dispatch
"""

import logging
from datetime import datetime, timezone

from src.core.config import settings
from src.push import sender, store
from src.push.schedule import is_due

logger = logging.getLogger(__name__)


def run(now_utc: datetime | None = None) -> dict[str, int]:
    """Envia a quem está na janela e varre os expirados. Devolve a contagem."""
    agora = now_utc or datetime.now(timezone.utc)
    contagem = {"sent": 0, "gone": 0, "failed": 0, "expired": 0}

    for sub in store.all_subscriptions():
        if not is_due(sub.hour, sub.timezone, agora, settings.push_window_minutes):
            continue
        try:
            sender.send(sub)
            contagem["sent"] += 1
        except sender.Gone:
            store.delete(sub.endpoint)
            contagem["gone"] += 1
        except Exception:
            # Um endpoint com problema não pode custar o lembrete de todos os
            # outros. Falha transitória: nada é apagado, tenta amanhã.
            logger.exception("falha ao enviar lembrete")
            contagem["failed"] += 1

    contagem["expired"] = store.delete_stale(
        today=agora.date(), max_age_days=settings.push_expiry_days
    )
    return contagem


def main() -> None:
    if not settings.vapid_private_key:
        logger.warning("VAPID não configurado — nada a enviar")
        return
    logger.info("dispatch: %s", run())


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()
```

- [ ] **Step 4: Run the tests**

Run: `uv run pytest tests/test_push_dispatch.py -v`
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add src/push/dispatch.py tests/test_push_dispatch.py
git commit -m "feat(push): the dispatch job

Runs the same image as the API under a different command, so the reminder
adds no public surface at all — an endpoint would have meant validating OIDC
on a service deployed --allow-unauthenticated. A failing endpoint costs only
its own reminder; nothing is deleted over a transient error."
```

---

### Task 7: The three API routes, and the rule that nothing joins

**Files:**
- Modify: `src/api/schemas.py`
- Modify: `src/api/routes.py`
- Test: `tests/test_api_push.py`

**Interfaces:**
- Consumes: store functions (Task 4)
- Produces: `POST /push/subscribe`, `POST /push/unsubscribe`, `POST /push/seen` — all 204, no body

- [ ] **Step 1: Write the failing tests**

Create `tests/test_api_push.py`:

```python
from unittest.mock import patch

from fastapi.testclient import TestClient

from src.api.main import app

client = TestClient(app)

_CORPO = {
    "endpoint": "https://push.example/abc",
    "keys": {"p256dh": "chave", "auth": "segredo"},
    "hour": "08:00",
    "timezone": "America/Sao_Paulo",
}


def test_subscribe_guarda_e_devolve_204():
    with patch("src.api.routes.push_store.save") as salvar:
        r = client.post("/push/subscribe", json=_CORPO)
    assert r.status_code == 204
    assert r.content == b""
    salvar.assert_called_once()


def test_subscribe_guarda_exatamente_os_cinco_campos():
    # A regra dura, conferida na fronteira da API e não só no store.
    with patch("src.api.routes.push_store.save") as salvar:
        client.post("/push/subscribe", json=_CORPO)
    sub = salvar.call_args.args[0]
    assert sub.endpoint == _CORPO["endpoint"]
    assert sub.hour == "08:00"
    assert sub.timezone == "America/Sao_Paulo"


def test_unsubscribe_apaga():
    with patch("src.api.routes.push_store.delete") as apagar:
        r = client.post("/push/unsubscribe",
                        json={"endpoint": _CORPO["endpoint"]})
    assert r.status_code == 204
    apagar.assert_called_once_with(_CORPO["endpoint"])


def test_seen_carimba_a_data():
    with patch("src.api.routes.push_store.touch") as carimbar:
        r = client.post("/push/seen", json={"endpoint": _CORPO["endpoint"]})
    assert r.status_code == 204
    carimbar.assert_called_once()


def test_o_push_nao_acrescenta_campo_nenhum_ao_log_de_turnos():
    # A salvaguarda inteira desta funcionalidade é o store não cruzar com
    # nada. Se alguém um dia acrescentar `endpoint` ou `subscription` ao log,
    # este teste cai — que é o único aviso que existiria.
    import inspect

    from src.rag import conversation_log

    fonte = inspect.getsource(conversation_log)
    for proibido in ("endpoint", "subscription", "push_"):
        assert proibido not in fonte, f"{proibido} apareceu no log de turnos"
```

- [ ] **Step 2: Run them and watch them fail**

Run: `uv run pytest tests/test_api_push.py -v`
Expected: FAIL — 404 on the routes (the last test should already pass).

- [ ] **Step 3: Add the schemas**

Append to `src/api/schemas.py`:

```python
class PushKeys(BaseModel):
    p256dh: str
    auth: str


class PushSubscribeRequest(BaseModel):
    endpoint: str
    keys: PushKeys
    hour: str
    timezone: str


class PushEndpointRequest(BaseModel):
    endpoint: str
```

- [ ] **Step 4: Add the routes**

In `src/api/routes.py`, add to the imports:

```python
from datetime import date

from src.push import store as push_store
```

and to the schema import block: `PushEndpointRequest, PushSubscribeRequest`.

Then append the routes:

```python
# --- Lembrete por push ---
#
# Três rotas, todas 204 e sem corpo, e nenhuma delas escreve no log de
# turnos: o store das subscriptions não cruza com nada. Ver
# docs/superpowers/specs/2026-08-27-lembrete-push-design.md


@router.post("/push/subscribe", status_code=204)
def push_subscribe(request: PushSubscribeRequest) -> Response:
    push_store.save(
        push_store.Subscription(
            endpoint=request.endpoint,
            keys={"p256dh": request.keys.p256dh, "auth": request.keys.auth},
            hour=request.hour,
            timezone=request.timezone,
            last_seen=date.today(),
        )
    )
    return Response(status_code=204)


@router.post("/push/unsubscribe", status_code=204)
def push_unsubscribe(request: PushEndpointRequest) -> Response:
    push_store.delete(request.endpoint)
    return Response(status_code=204)


@router.post("/push/seen", status_code=204)
def push_seen(request: PushEndpointRequest) -> Response:
    """Carimba last_seen quando alguém abre o app por um lembrete.

    Só a data. É o que permite os 90 dias existirem — sem nada registrando
    atividade, a expiração nunca dispararia.
    """
    push_store.touch(request.endpoint, date.today())
    return Response(status_code=204)
```

- [ ] **Step 5: Run the tests**

Run: `uv run pytest tests/test_api_push.py -v && uv run pytest -q`
Expected: 5 passed in the new file; the whole suite still green.

- [ ] **Step 6: Format and commit**

```bash
uv run black src/ tests/ && uv run isort src/ tests/
git add src/api/schemas.py src/api/routes.py tests/test_api_push.py
git commit -m "feat(api): subscribe, unsubscribe and seen

Three routes, all 204 with no body, none of which writes to the turn log.
The last test in the new file is the safeguard itself: it reads
conversation_log's source and fails if 'endpoint', 'subscription' or 'push_'
ever appears there, which is the only warning that would exist if someone
started joining the two stores."
```

---

### Task 8: The service worker, and the guard that keeps it small

**Files:**
- Create: `frontend/public/sw.js`
- Create: `scripts/check_push_service_worker.mjs`
- Modify: `.github/workflows/ci.yml`
- Test: the guard itself, plus a deliberate breakage

**Interfaces:**
- Consumes: the payload shape from `sender.py` (`{title, body, url}`)
- Produces: `/sw.js` at the site root; `POST /push/seen` called on `notificationclick`

- [ ] **Step 1: Write the service worker**

Create `frontend/public/sw.js`:

```js
// Service worker do lembrete — e SÓ do lembrete.
//
// Registra `push` e `notificationclick`. NÃO tem handler de `fetch`, não faz
// cache e não intercepta requisição nenhuma. Isso não é economia: é o que
// reconcilia este arquivo com a decisão de não ter service worker tomada em
// docs/superpowers/specs/2026-08-27-pwa-instalavel-design.md, que era contra
// um worker capaz de fixar uma versão velha no aparelho da pessoa em
// silêncio. Sem handler de `fetch`, isso é estruturalmente impossível.
//
// scripts/check_push_service_worker.mjs derruba o CI se um `fetch` aparecer
// aqui. A reconciliação só vale enquanto este arquivo continuar deste
// tamanho.

self.addEventListener('push', (event) => {
  const dados = event.data ? event.data.json() : {};
  event.waitUntil(
    self.registration.showNotification(dados.title || 'Dialogando com a Doutrina', {
      body: dados.body || '',
      icon: '/icons/icon-192.png',
      badge: '/icons/icon-192.png',
      data: { url: dados.url || '/' },
    }),
  );
});

self.addEventListener('notificationclick', (event) => {
  event.notification.close();
  const destino = (event.notification.data && event.notification.data.url) || '/';

  event.waitUntil((async () => {
    // Carimba last_seen. É o que faz os 90 dias existirem — sem nada
    // registrando atividade, a expiração nunca dispararia. Só a data.
    try {
      const sub = await self.registration.pushManager.getSubscription();
      if (sub) {
        // A base da API vem na query do próprio worker: um service worker não
        // enxerga import.meta.env, e a API mora noutra origem (Cloud Run), de
        // modo que um fetch relativo bateria na Vercel e devolveria HTML.
        // Quem registra o worker põe o ?api= — ver services/push.js.
        const base = new URL(self.location.href).searchParams.get('api') || '';
        await fetch(`${base}/push/seen`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ endpoint: sub.endpoint }),
        });
      }
    } catch { /* carimbar é melhor-esforço; nunca impede de abrir o app */ }

    const abertas = await self.clients.matchAll({ type: 'window', includeUncontrolled: true });
    for (const cliente of abertas) {
      if ('focus' in cliente) return cliente.focus();
    }
    return self.clients.openWindow(destino);
  })());
});
```

- [ ] **Step 2: Write the guard**

Create `scripts/check_push_service_worker.mjs`:

```js
// Confere que o service worker do push continua sendo só do push.
// Rode com: node scripts/check_push_service_worker.mjs
//
// A spec do PWA decidiu não ter service worker, medindo que os assets já vêm
// `immutable` da Vercel e que o que um SW acrescentaria era a capacidade de
// fixar versão velha no aparelho em silêncio. O push obriga a ter um. As duas
// coisas convivem por um motivo estrutural e não por cuidado: um worker sem
// handler de `fetch` não pode servir nada velho, porque não serve nada.
//
// Esta guarda existe para que isso continue verdade. Um `fetch` aqui não
// quebraria teste nenhum e não apareceria na tela — reintroduziria em
// silêncio exatamente o risco que a outra spec recusou.
import { existsSync, readFileSync } from 'node:fs';

const SW = 'frontend/public/sw.js';
const CONTATO = 'frontend/src/constants/contact.js';

let falhou = false;
const check = (label, ok, detalhe = '') => {
  console.log(`${ok ? 'OK  ' : 'FALHA'} ${label}`);
  if (!ok && detalhe) console.log(`   ${detalhe}`);
  if (!ok) falhou = true;
};

check(`${SW} existe`, existsSync(SW));

if (existsSync(SW)) {
  const sw = readFileSync(SW, 'utf8');
  check('o worker não escuta fetch',
    !/addEventListener\(\s*['"]fetch['"]/.test(sw),
    'um handler de fetch devolve ao worker a capacidade de servir versão velha');
  check('o worker não usa caches',
    !/\bcaches\b/.test(sw),
    'cache aqui é a falha silenciosa que a spec do PWA recusou');
  check('o worker escuta push', /addEventListener\(\s*['"]push['"]/.test(sw));
  check('o worker escuta notificationclick',
    /addEventListener\(\s*['"]notificationclick['"]/.test(sw));
}

// A cópia de privacidade tem de ter andado antes do store existir. Se
// src/push/ está no repositório, PRIVACY_NOTICE tem de falar do lembrete —
// senão o código promete menos do que faz, que é a única direção proibida.
if (existsSync('src/push/store.py')) {
  const copia = existsSync(CONTATO) ? readFileSync(CONTATO, 'utf8') : '';
  check('PRIVACY_NOTICE menciona o lembrete',
    /lembrete/i.test(copia),
    'o store existe em código e a cópia não o anuncia');
}

process.exit(falhou ? 1 : 0);
```

- [ ] **Step 3: Run the guard and watch it pass**

Run: `node scripts/check_push_service_worker.mjs`
Expected: all OK, exit 0.

- [ ] **Step 4: Prove it fails — the step that matters**

```bash
printf "\nself.addEventListener('fetch', (e) => e.respondWith(fetch(e.request)));\n" >> frontend/public/sw.js
node scripts/check_push_service_worker.mjs   # deve imprimir FALHA e sair 1
git checkout frontend/public/sw.js
node scripts/check_push_service_worker.mjs   # volta a passar
```

Expected: `FALHA o worker não escuta fetch`, then green again.

- [ ] **Step 5: Wire it into CI**

In `.github/workflows/ci.yml`, add to the `Frontend guards` run block, after `check_pwa_manifest.mjs`:

```yaml
          node scripts/check_push_service_worker.mjs
```

- [ ] **Step 6: Commit**

```bash
git add frontend/public/sw.js scripts/check_push_service_worker.mjs .github/workflows/ci.yml
git commit -m "feat(frontend): the push service worker, held to push only

Push requires a service worker; the PWA spec had decided against one. They
reconcile structurally rather than by care: a worker with no fetch handler
cannot serve a stale anything. The guard keeps it that way, and also refuses
to pass if src/push/ exists while the privacy copy has not moved."
```

---

### Task 9: Subscribing from the browser

**Files:**
- Create: `frontend/src/services/push.js`
- Rewrite: `frontend/src/hooks/useReminder.js`
- Test: manual, plus the guard from Task 8

**Interfaces:**
- Consumes: `POST /push/subscribe`, `/push/unsubscribe` (Task 7); `PUBLIC_VAPID_KEY`
- Produces: `useReminder()` returning `{ supported, needsInstall, enabled, hour, setHour, enable, disable, busy }`

- [ ] **Step 1: Write the service**

Create `frontend/src/services/push.js`:

```js
// A conversa do navegador com o push: registrar o worker, assinar, cancelar.
//
// O worker é registrado SÓ quando a pessoa liga o lembrete. Quem nunca liga
// nunca ganha um service worker — não há motivo para instalar um em todo
// visitante quando ele só serve para isto.
import { API_BASE } from './api';

const VAPID = import.meta.env.PUBLIC_VAPID_KEY || '';

// Astro expõe PUBLIC_, não VITE_. Trocar o prefixo foi o que gravou
// localhost:8000 no bundle de produção em 2026-08-09; scripts/check_api_base.mjs
// existe por causa disso.

export function isIOS() {
  return /iPad|iPhone|iPod/.test(navigator.userAgent);
}

export function isStandalone() {
  return window.matchMedia('(display-mode: standalone)').matches
    || window.navigator.standalone === true;
}

export function pushSupported() {
  return 'serviceWorker' in navigator
    && 'PushManager' in window
    && 'Notification' in window;
}

/** No iPhone, push só existe para app já instalado na tela de início. */
export function needsInstallFirst() {
  return isIOS() && !isStandalone();
}

function urlBase64ToUint8Array(base64) {
  const pad = '='.repeat((4 - (base64.length % 4)) % 4);
  const bruto = atob((base64 + pad).replace(/-/g, '+').replace(/_/g, '/'));
  return Uint8Array.from([...bruto].map((c) => c.charCodeAt(0)));
}

async function registration() {
  // O ?api= é como o worker descobre onde fica a API: ele não lê
  // import.meta.env, e a API está noutra origem. O scope continua sendo '/'
  // porque a query não muda o caminho do script.
  return navigator.serviceWorker.register(
    `/sw.js?api=${encodeURIComponent(API_BASE)}`, { scope: '/' });
}

export async function subscribe(hour) {
  if (!pushSupported() || needsInstallFirst()) return false;
  const permissao = await Notification.requestPermission();
  if (permissao !== 'granted') return false;

  const reg = await registration();
  const sub = await reg.pushManager.subscribe({
    userVisibleOnly: true,
    applicationServerKey: urlBase64ToUint8Array(VAPID),
  });
  const json = sub.toJSON();

  const r = await fetch(`${API_BASE}/push/subscribe`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      endpoint: sub.endpoint,
      keys: json.keys,
      hour,
      timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
    }),
  });
  return r.ok;
}

export async function unsubscribe() {
  if (!('serviceWorker' in navigator)) return;
  const reg = await navigator.serviceWorker.getRegistration();
  const sub = reg && (await reg.pushManager.getSubscription());
  if (!sub) return;
  await fetch(`${API_BASE}/push/unsubscribe`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ endpoint: sub.endpoint }),
  });
  await sub.unsubscribe();
}
```

- [ ] **Step 1b: Export the base URL from `api.js`**

`frontend/src/services/api.js` computes the base into a module-private
`const BASE` (line 26) and does **not** export it. Export it under a name,
rather than repeating the expression in `push.js`: a second copy of the
`PUBLIC_API_URL || 'http://localhost:8000'` fallback is a second place to get
the 2026-08-09 bug, and `scripts/check_api_base.mjs` scans the built bundle
for exactly that string.

In `frontend/src/services/api.js`, change line 26 from `const BASE =` to:

```js
export const API_BASE =
```

then update the in-file use at line 51 from `BASE + path` to `API_BASE + path`.
Run `grep -n '\bBASE\b' frontend/src/services/api.js` afterwards and confirm
no bare `BASE` remains.

- [ ] **Step 2: Rewrite the hook**

Replace the whole contents of `frontend/src/hooks/useReminder.js`:

```js
// O lembrete diário, agora por Web Push.
//
// A versão anterior era um setInterval dentro da página e só disparava com a
// aba aberta em primeiro plano — foi desligada em 2026-08-05 por não poder
// funcionar. Ver docs/superpowers/specs/2026-08-27-lembrete-push-design.md
import { useEffect, useState } from 'react';

import { needsInstallFirst, pushSupported, subscribe, unsubscribe } from '../services/push';
import { useStorage } from './useStorage';

export function useReminder() {
  // As duas chaves sobreviveram ao desligamento de 2026-08-05 de propósito:
  // quem tinha 06:30 guardado recupera o horário em vez de voltar ao padrão.
  const [enabled, setEnabled] = useStorage('dialogando_reminder_on', false);
  const [hour, setHourStored] = useStorage('dialogando_reminder_time', '08:00');
  const [busy, setBusy] = useState(false);
  const [supported, setSupported] = useState(false);
  const [needsInstall, setNeedsInstall] = useState(false);

  useEffect(() => {
    setSupported(pushSupported());
    setNeedsInstall(needsInstallFirst());
  }, []);

  const enable = async () => {
    setBusy(true);
    const ok = await subscribe(hour);
    setEnabled(ok);
    setBusy(false);
    return ok;
  };

  const disable = async () => {
    setBusy(true);
    await unsubscribe();
    setEnabled(false);
    setBusy(false);
  };

  // Trocar a hora com o lembrete ligado exige reassinar: a hora vive no
  // registro do servidor, não no navegador.
  const setHour = async (nova) => {
    setHourStored(nova);
    if (enabled) {
      setBusy(true);
      await subscribe(nova);
      setBusy(false);
    }
  };

  return { supported, needsInstall, enabled, hour, setHour, enable, disable, busy };
}
```

- [ ] **Step 3: Verify it builds**

Run: `cd frontend && npm run build`
Expected: build succeeds with no unresolved import.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/services/push.js frontend/src/hooks/useReminder.js
git commit -m "feat(frontend): subscribe to the reminder from the browser

The service worker is registered only when someone turns the reminder on.
Nobody who never enables it gets a worker installed — there is no reason to
put one on every visitor when it serves this and nothing else.

The two localStorage keys kept through the 2026-08-05 shutdown pay off here:
someone who had set 06:30 gets their hour back rather than the default."
```

---

### Task 10: The Settings section, with the iPhone path

**Files:**
- Modify: `frontend/src/components/modals/SettingsPanel.jsx:236-280`
- Modify: `frontend/src/App.jsx`
- Test: `npm run build`, plus manual

**Interfaces:**
- Consumes: `useReminder()` (Task 9)
- Produces: the visible feature

- [ ] **Step 1: Restore the section, changed**

In `frontend/src/components/modals/SettingsPanel.jsx`, replace the commented-out "Lembrete de Estudo" block (and its explanatory comment) with:

```jsx
          {/* Lembrete de Estudo — de volta por Web Push em 2026-08-27.
              O que mudou desde o desligamento de 2026-08-05: a entrega não
              depende mais da aba estar aberta, e o controle só aparece onde
              pode funcionar. Ver
              docs/superpowers/specs/2026-08-27-lembrete-push-design.md */}
          <Section title="Lembrete de Estudo" theme={theme}>
            {reminder.needsInstall ? (
              /* No iPhone, push só existe para app já na tela de início.
                 Mostrar o interruptor aqui seria repetir o defeito de
                 2026-08-05: um botão que não fazia nada, não dizia nada, e
                 continuava se oferecendo. O obstáculo vira o caminho. */
              <p style={{ fontSize: 12.5, lineHeight: 1.5, color: theme.subtext, margin: 0 }}>
                Para receber o lembrete no iPhone, primeiro adicione o app à tela
                de início: toque em <strong>Compartilhar</strong> na barra do
                Safari e escolha <strong>Adicionar à Tela de Início</strong>.
                Depois volte aqui.
              </p>
            ) : !reminder.supported ? (
              <p style={{ fontSize: 12.5, lineHeight: 1.5, color: theme.subtext, margin: 0 }}>
                Este navegador não permite lembretes.
              </p>
            ) : (
              <>
                <Row label="Ativar lembrete diário"
                     sublabel="Notificação no horário escolhido"
                     theme={theme}>
                  <Toggle
                    on={reminder.enabled}
                    onToggle={() => (reminder.enabled ? reminder.disable() : reminder.enable())}
                  />
                </Row>
                {reminder.enabled && (
                  <input
                    type="time"
                    value={reminder.hour}
                    disabled={reminder.busy}
                    onChange={(e) => reminder.setHour(e.target.value)}
                    style={{
                      width: '100%', background: theme.inputBg,
                      border: `1px solid ${theme.headerBorder}`,
                      borderRadius: 7, padding: '8px 10px', fontSize: 13,
                      color: theme.text, marginBottom: 4,
                    }}
                  />
                )}
              </>
            )}
          </Section>
```

- [ ] **Step 2: Pass the hook in**

In `frontend/src/App.jsx`, remove the commented-out reminder block (the `useReminder` import, `handleNotificationClick`, `requestNotif`, `notifPerm` and the two `useStorage` reminder keys) and replace with:

```jsx
import { useReminder } from './hooks/useReminder';
```

and inside the component:

```jsx
  const reminder = useReminder();
```

then pass `reminder={reminder}` to `<SettingsPanel ... />`, and accept `reminder` in `SettingsPanel`'s props.

- [ ] **Step 2b: Teach the deep link to open the daily passage**

`sender.py` sends `url: "/?mode=trecho"`, but `App.jsx`'s deep-link reader
accepts only `'duvida'` and `'estudar'` (around line 291) — `trecho` would be
ignored in silence and the notification would land on the home screen instead
of the passage, which is what Task 12 Step 1 checks for.

`handleStudyTrecho` already exists at `App.jsx:1028`. Extend the branch:

```jsx
    } else if (modeParam === 'duvida' || modeParam === 'estudar') {
      switchMode(modeParam);
    } else if (modeParam === 'trecho') {
      // O destino da notificação do lembrete. Sem este ramo o ?mode=trecho
      // é ignorado em silêncio e a pessoa cai na home — ver
      // src/push/sender.py, REMINDER_URL.
      handleStudyTrecho();
    }
```

Keep the existing branch text exactly as it is; only add the new `else if`.
Read the surrounding lines first — the real code may differ slightly from the
snippet above, and the existing branches must not be rewritten.

- [ ] **Step 3: Build and run every guard**

```bash
cd frontend && npm run build && cd ..
for g in check_chat_current_mode check_cited_text check_followup_reply \
         check_discovery_assets check_api_base check_pwa_manifest \
         check_push_service_worker; do
  node scripts/$g.mjs > /dev/null && echo "$g ok" || echo "$g FALHOU"
done
```

Expected: all seven ok.

- [ ] **Step 4: Run the smoke suite**

Run: `cd frontend && npm run smoke`
Expected: all tests pass. (Requires `fix/smoke-sob-agente` to be merged, or run it with the agent environment variables stripped.)

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/modals/SettingsPanel.jsx frontend/src/App.jsx
git commit -m "feat(frontend): bring the reminder section back

On an iPhone without the app installed the toggle is not shown at all — the
install instructions take its place. That is the direct lesson of the
2026-08-05 failure, which was not that the button did not work but that it
did nothing, said nothing, and went on offering."
```

---

### Task 11: Deploy, and the rules file

**Files:**
- Modify: `docs/deploy.md`
- Modify: `CLAUDE.md`
- Modify: `docs/superpowers/specs/README.md` (status → vale)

**Interfaces:**
- Consumes: everything above
- Produces: the commands the author runs once

- [ ] **Step 1: Add the deploy section**

Append to `docs/deploy.md`:

````markdown
## Lembrete por push

Uma vez só, no projeto GCP que já roda a API.

```bash
# 1. Firestore em modo nativo, na mesma região do Cloud Run.
gcloud services enable firestore.googleapis.com
gcloud firestore databases create --location=us-central1 --type=firestore-native

# 2. Chaves VAPID. A pública vai para o build do frontend; a privada, para o
#    Secret Manager, pelo mesmo caminho das chaves de LLM.
uv run python -c "from py_vapid import Vapid01; v=Vapid01(); v.generate_keys(); \
  print('PUBLIC =', v.public_key_urlsafe_base64); \
  print('PRIVATE=', v.private_key_urlsafe_base64)"

printf '%s' 'A_CHAVE_PRIVADA' | gcloud secrets create vapid-private-key --data-file=-
gcloud secrets add-iam-policy-binding vapid-private-key \
  --member="serviceAccount:$(gcloud projects describe $(gcloud config get-value project) \
    --format='value(projectNumber)')-compute@developer.gserviceaccount.com" \
  --role=roles/secretmanager.secretAccessor

# 3. O Job: mesma imagem da API, outro comando. Nenhuma superfície pública.
gcloud run jobs create kardec-push \
  --image us-central1-docker.pkg.dev/$(gcloud config get-value project)/kardec/api:latest \
  --region us-central1 \
  --command /app/.venv/bin/python --args -m,src.push.dispatch \
  --set-secrets 'VAPID_PRIVATE_KEY=vapid-private-key:latest' \
  --set-env-vars 'VAPID_PUBLIC_KEY=A_CHAVE_PUBLICA'

# 4. O Scheduler, de 15 em 15 minutos — o passo que cobre fusos de meia e de
#    quarto de hora.
gcloud scheduler jobs create http kardec-push-tick \
  --location us-central1 \
  --schedule '*/15 * * * *' \
  --uri "https://us-central1-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/$(gcloud config get-value project)/jobs/kardec-push:run" \
  --http-method POST \
  --oauth-service-account-email "$(gcloud projects describe $(gcloud config get-value project) --format='value(projectNumber)')-compute@developer.gserviceaccount.com"
```

E na Vercel, a variável de ambiente do frontend: **`PUBLIC_VAPID_KEY`** com a
chave pública. O prefixo é `PUBLIC_`, não `VITE_` — o Astro só expõe ao
cliente as variáveis com esse prefixo, e trocar isso foi o que gravou
`localhost:8000` dentro do bundle de produção em 2026-08-09.
````

- [ ] **Step 2: Fix the stale variable in the same file**

Still in `docs/deploy.md`, find the line instructing to set `VITE_API_URL` and change it to `PUBLIC_API_URL`. It has been wrong since the Astro migration.

- [ ] **Step 3: Add the rule to CLAUDE.md**

In `CLAUDE.md`, under **Rules**, add:

```markdown
- **The push subscription store is the only persistence in this project, and it joins nothing.** `src/push/store.py` holds exactly `{endpoint, keys, hour, timezone, last_seen}` per device — never a `session_id`, never a link to the turn log, to `/feedback` or to a conversation, and `conversation_log.py` gains no field from it. `last_seen` is a date and exists only so the 90-day expiry can fire; records also go on unsubscribe and on a `410` from the push service. The service worker (`frontend/public/sw.js`) registers `push` and `notificationclick` and **must never gain a `fetch` handler** — that absence is what reconciles it with the no-service-worker decision in the PWA spec, and `scripts/check_push_service_worker.mjs` enforces it. On iOS the toggle is shown only when the app is installed; where a control cannot work it is replaced by the install path, never left to fail silently. Reasoning: [the design](docs/superpowers/specs/2026-08-27-lembrete-push-design.md).
```

- [ ] **Step 4: Flip the spec's status**

In `docs/superpowers/specs/2026-08-27-lembrete-push-design.md`, change `**Status:** approved, pending implementation` to `**Status:** implemented`.
In `docs/superpowers/specs/README.md`, change the push row's `**pendente**` to `vale`.

- [ ] **Step 5: Full verification**

```bash
uv run black --check src/ tests/ && uv run isort --check-only src/ tests/
uv run pytest -q
cd frontend && npm run build && cd ..
for g in check_chat_current_mode check_cited_text check_followup_reply \
         check_discovery_assets check_api_base check_pwa_manifest \
         check_push_service_worker; do node scripts/$g.mjs > /dev/null \
  && echo "$g ok" || echo "$g FALHOU"; done
```

Expected: formatting clean, all tests pass, all seven guards ok.

- [ ] **Step 6: Commit**

```bash
git add docs/deploy.md CLAUDE.md docs/superpowers/specs/
git commit -m "docs: deploy and rules for the push reminder

Also corrects deploy.md's instruction to set VITE_API_URL, wrong since the
Astro migration, which exposes PUBLIC_-prefixed variables. That exact
mismatch put localhost:8000 into a production bundle once already."
```

---

### Task 12: The verification no automation replaces

**Files:** none

- [ ] **Step 1: Install on a real Android**

Open the site in Chrome, install it, turn the reminder on for two minutes ahead, lock the phone, and wait. The notification must arrive with the browser closed, and tapping it must open the daily passage.

- [ ] **Step 2: Install on a real iPhone**

Open in Safari, add to the Home Screen, open from the icon, and confirm the Settings section now shows the toggle instead of the install instructions. Turn it on, and repeat the wait.

- [ ] **Step 3: Confirm what happens without installing on iOS**

In Safari, *without* installing, open Settings and confirm the install instructions appear and no toggle does.

- [ ] **Step 4: Confirm deletion**

Turn the reminder off, then check in the Firestore console that the document is gone.

Every layer above this stops at a file, a mock or a browser under test. The only thing that proves a reminder works is a phone on a table, face down, that lights up.
