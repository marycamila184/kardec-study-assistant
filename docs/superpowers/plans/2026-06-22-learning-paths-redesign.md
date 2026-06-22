# Learning Paths Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the single `fundamentos-da-doutrina.json` path with six curated paths across two reading tracks (Livro dos Espíritos and Evangelho) and three progression levels (Curioso / Estudante / Aprofundado), plus extend the study endpoint to support chapter-scoped lookups needed by the Evangelho track.

**Architecture:** Task 1 adds an optional `chapter` field to `PathStep`, `StudyRequest`, `retrieve_by_item`, and `study()` — a backward-compatible extension with no schema migration. Tasks 2 and 3 create the six JSON path files using exact item numbers verified against the markdown sources. Existing tests for LE paths pass unchanged since `chapter=None` produces the same ChromaDB filter as before.

**Tech Stack:** FastAPI, Pydantic, ChromaDB, Python 3.12+, uv, pytest

## Global Constraints

- Python 3.12+; use `str | None` union syntax, not `Optional[str]`
- Run tests with: `uv run pytest`
- Format with: `uv run black src/ && uv run isort src/`
- Book name for Livro dos Espíritos: `"O Livro dos Espíritos"` (exact, as in `BOOK_NAME_MAP`)
- Book name for Evangelho: `"O Evangelho Segundo o Espiritismo"` (exact, capital S)
- Evangelho chapter strings come from the parser stripping `#` from headings: `"CAPÍTULO I"`, `"CAPÍTULO II"`, etc.
- Levels: `"curioso"`, `"estudante"`, `"aprofundado"` (lowercase, no accents)
- No LLM calls in tests; mock `retrieve_by_item`, `retrieve`, and `_get_client`

---

### Task 1: Extend schema, retriever, study, and route for chapter-scoped lookups

**Files:**
- Modify: `src/api/schemas.py` — add `chapter` to `PathStep` and `StudyRequest`
- Modify: `src/rag/retriever.py` — add optional `chapter` parameter to `retrieve_by_item`
- Modify: `src/rag/study.py` — accept and forward `chapter`
- Modify: `src/api/routes.py` — pass `request.chapter` to `study_item_fn`
- Modify: `tests/test_retriever.py` — add chapter-filter test
- Modify: `tests/test_study.py` — add chapter-forwarding test
- Modify: `tests/test_api.py` — add chapter-forwarding API test

**Interfaces:**
- Consumes: existing `retrieve_by_item(book, item_number)`, `study(book, item_number)`
- Produces:
  - `retrieve_by_item(book: str, item_number: str, chapter: str | None = None) -> list[dict]`
  - `study(book: str, item_number: str, chapter: str | None = None) -> dict | None`
  - `StudyRequest.chapter: str | None = None`
  - `PathStep.chapter: str | None = None`

- [ ] **Step 1: Write failing tests for the three new behaviors**

In `tests/test_retriever.py`, append at the end:

```python
def test_retrieve_by_item_with_chapter_adds_chapter_to_filter(monkeypatch):
    mock_store = MagicMock()
    mock_store.get_by_filter.return_value = [_MOCK_RESULTS[0]]
    monkeypatch.setattr("src.rag.retriever._get_store", lambda: mock_store)
    retrieve_by_item("O Evangelho Segundo o Espiritismo", "1", chapter="CAPÍTULO IV")
    mock_store.get_by_filter.assert_called_once_with(
        {"$and": [
            {"book": {"$eq": "O Evangelho Segundo o Espiritismo"}},
            {"item_number": {"$eq": "1"}},
            {"chapter": {"$eq": "CAPÍTULO IV"}},
        ]}
    )


def test_retrieve_by_item_without_chapter_omits_chapter_from_filter(monkeypatch):
    mock_store = MagicMock()
    mock_store.get_by_filter.return_value = [_MOCK_RESULTS[0]]
    monkeypatch.setattr("src.rag.retriever._get_store", lambda: mock_store)
    retrieve_by_item("O Livro dos Espíritos", "1")
    mock_store.get_by_filter.assert_called_once_with(
        {"$and": [{"book": {"$eq": "O Livro dos Espíritos"}}, {"item_number": {"$eq": "1"}}]}
    )
```

In `tests/test_study.py`, append at the end:

```python
def test_study_forwards_chapter_to_retrieve_by_item():
    with patch("src.rag.study.retrieve_by_item") as mock_retrieve:
        mock_retrieve.return_value = []
        study("O Evangelho Segundo o Espiritismo", "1", chapter="CAPÍTULO IV")
    mock_retrieve.assert_called_once_with(
        "O Evangelho Segundo o Espiritismo", "1", "CAPÍTULO IV"
    )
```

In `tests/test_api.py`, append at the end:

```python
def test_study_with_chapter_passes_chapter_to_study_fn():
    with patch("src.api.routes.study_item_fn", return_value=_STUDY_RESULT) as mock_fn:
        client.post(
            "/study",
            json={
                "book": "O Evangelho Segundo o Espiritismo",
                "item_number": "1",
                "chapter": "CAPÍTULO IV",
            },
        )
    mock_fn.assert_called_once_with(
        "O Evangelho Segundo o Espiritismo", "1", "CAPÍTULO IV"
    )
```

- [ ] **Step 2: Run new tests to verify they fail**

```bash
uv run pytest tests/test_retriever.py::test_retrieve_by_item_with_chapter_adds_chapter_to_filter tests/test_retriever.py::test_retrieve_by_item_without_chapter_omits_chapter_from_filter tests/test_study.py::test_study_forwards_chapter_to_retrieve_by_item tests/test_api.py::test_study_with_chapter_passes_chapter_to_study_fn -v
```

Expected: FAIL — `TypeError: retrieve_by_item() got an unexpected keyword argument 'chapter'` (or similar)

- [ ] **Step 3: Add `chapter` field to `PathStep` and `StudyRequest` in `src/api/schemas.py`**

Replace the `PathStep` class (lines 29–33):

```python
class PathStep(BaseModel):
    book: str
    chapter: str | None = None
    item_number: str
    label: str
```

Replace the `StudyRequest` class (lines 63–66):

```python
class StudyRequest(BaseModel):
    book: str
    chapter: str | None = None
    item_number: str
    conversation_history: list[Message] = []
```

- [ ] **Step 4: Extend `retrieve_by_item` in `src/rag/retriever.py`**

Replace the `retrieve_by_item` function:

```python
def retrieve_by_item(book: str, item_number: str, chapter: str | None = None) -> list[dict]:
    conditions: list[dict] = [
        {"book": {"$eq": book}},
        {"item_number": {"$eq": item_number}},
    ]
    if chapter is not None:
        conditions.append({"chapter": {"$eq": chapter}})
    return _get_store().get_by_filter({"$and": conditions})
```

- [ ] **Step 5: Add `chapter` parameter to `study()` in `src/rag/study.py`**

Replace the function signature and the `retrieve_by_item` call (first two lines of `study`):

```python
def study(book: str, item_number: str, chapter: str | None = None) -> dict | None:
    chunks = retrieve_by_item(book, item_number, chapter)
```

(The rest of the function body is unchanged.)

- [ ] **Step 6: Pass `chapter` through the `/study` route in `src/api/routes.py`**

Find the line inside the `study` route that calls `study_item_fn` and replace it:

```python
result = study_item_fn(request.book, request.item_number, request.chapter)
```

- [ ] **Step 7: Run all new and existing tests to confirm everything passes**

```bash
uv run pytest tests/test_retriever.py tests/test_study.py tests/test_api.py -v
```

Expected: All tests PASS. The two new retriever tests pass, the new study test passes, the new API test passes, and all pre-existing tests continue to pass (because `chapter=None` produces the same filter as before).

- [ ] **Step 8: Commit**

```bash
git add src/api/schemas.py src/rag/retriever.py src/rag/study.py src/api/routes.py \
        tests/test_retriever.py tests/test_study.py tests/test_api.py
git commit -m "feat: extend study endpoint and path schema with optional chapter filter

Enables Evangelho learning paths to scope item lookups to a specific
chapter, since Evangelho item numbers reset to 1 at every chapter."
```

---

### Task 2: Replace and create Livro dos Espíritos path files

**Files:**
- Delete: `data/paths/fundamentos-da-doutrina.json`
- Create: `data/paths/fundamentos-espirita-curioso.json`
- Create: `data/paths/fundamentos-espirita-estudante.json`
- Create: `data/paths/fundamentos-espirita-aprofundado.json`

**Interfaces:**
- Consumes: `PathStep` (from Task 1) — `chapter` is omitted for all LE steps since item numbers are global
- Produces: three JSON files loadable by `load_all_paths` / `load_path`

All item numbers below are verified against `data/markdown_files/livro-espiritos.md`:
- LE 1: "Que é Deus? — Deus é a inteligência suprema, causa primária de todas as coisas"
- LE 13: "Quando dizemos que Deus é eterno, infinito, imutável, imaterial, único, onipotente…"
- LE 27: "Há então dois elementos gerais do Universo: a matéria e o Espírito… e acima de tudo Deus"
- LE 37: "Poderemos conhecer o modo de formação dos mundos?"
- LE 63: "O princípio vital reside nalgum agente particular…"
- LE 76: "Que definição se pode dar dos Espíritos?"
- LE 93: "O Espírito, propriamente dito, nenhuma cobertura tem…"
- LE 100: "A classificação dos Espíritos se baseia no grau de adiantamento deles…"
- LE 132: "Qual o objetivo da encarnação dos Espíritos?"
- LE 134: "Que é a alma? — Um Espírito encarnado."
- LE 135: "Há no homem alguma outra coisa além da alma e do corpo? — Há o laço que liga a alma ao corpo."
- LE 141: "A alma não se acha encerrada no corpo… A alma tem dois invólucros… perispírito"
- LE 149: "Que sucede à alma no instante da morte? — Volta a ser Espírito…"
- LE 150: "A alma, após a morte, conserva a sua individualidade? — Sim; jamais a perde."
- LE 163: "A alma tem consciência de si mesma imediatamente depois de deixar o corpo?"
- LE 166: "Como pode a alma… acabar de depurar-se? — Sofrendo a prova de uma nova existência."
- LE 167: "Qual o fim objetivado com a reencarnação? — Expiação, melhoramento progressivo…"
- LE 218: "Encarnado, conserva o Espírito algum vestígio das percepções que teve… — idéias inatas"
- LE 614: "A lei natural é a lei de Deus. É a única verdadeira para a felicidade do homem."
- LE 843: "Tem o homem o livre-arbítrio de seus atos? — Pois que tem a liberdade de pensar…"
- LE 886: "Qual o verdadeiro sentido da palavra caridade, como a entendia Jesus? — Benevolência…"

- [ ] **Step 1: Delete the old file**

```bash
git rm data/paths/fundamentos-da-doutrina.json
```

- [ ] **Step 2: Create `data/paths/fundamentos-espirita-curioso.json`**

```json
{
  "id": "fundamentos-espirita-curioso",
  "title": "Fundamentos da Doutrina Espírita",
  "description": "Para quem está começando. Os oito pilares do espiritismo em ordem natural.",
  "level": "curioso",
  "steps": [
    {"book": "O Livro dos Espíritos", "item_number": "1",   "label": "O que é Deus?"},
    {"book": "O Livro dos Espíritos", "item_number": "13",  "label": "Atributos da Divindade"},
    {"book": "O Livro dos Espíritos", "item_number": "76",  "label": "O que são os Espíritos?"},
    {"book": "O Livro dos Espíritos", "item_number": "134", "label": "O que é a alma?"},
    {"book": "O Livro dos Espíritos", "item_number": "132", "label": "Por que os Espíritos se encarnaram?"},
    {"book": "O Livro dos Espíritos", "item_number": "166", "label": "Como a alma se depura?"},
    {"book": "O Livro dos Espíritos", "item_number": "149", "label": "O que acontece após a morte?"},
    {"book": "O Livro dos Espíritos", "item_number": "614", "label": "O que é a lei de Deus?"}
  ]
}
```

- [ ] **Step 3: Create `data/paths/fundamentos-espirita-estudante.json`**

```json
{
  "id": "fundamentos-espirita-estudante",
  "title": "Fundamentos da Doutrina Espírita",
  "description": "Para quem conhece o básico e quer aprofundar a compreensão doutrinária.",
  "level": "estudante",
  "steps": [
    {"book": "O Livro dos Espíritos", "item_number": "1",   "label": "O que é Deus?"},
    {"book": "O Livro dos Espíritos", "item_number": "13",  "label": "Atributos da Divindade"},
    {"book": "O Livro dos Espíritos", "item_number": "27",  "label": "A trindade universal — Deus, Espírito e matéria"},
    {"book": "O Livro dos Espíritos", "item_number": "76",  "label": "O que são os Espíritos?"},
    {"book": "O Livro dos Espíritos", "item_number": "100", "label": "A escala espírita — classificação dos Espíritos"},
    {"book": "O Livro dos Espíritos", "item_number": "132", "label": "Por que os Espíritos se encarnaram?"},
    {"book": "O Livro dos Espíritos", "item_number": "134", "label": "O que é a alma?"},
    {"book": "O Livro dos Espíritos", "item_number": "135", "label": "O perispírito — o laço entre alma e corpo"},
    {"book": "O Livro dos Espíritos", "item_number": "149", "label": "O que acontece após a morte?"},
    {"book": "O Livro dos Espíritos", "item_number": "163", "label": "A perturbação espiritual após a morte"},
    {"book": "O Livro dos Espíritos", "item_number": "166", "label": "Como a alma se depura?"},
    {"book": "O Livro dos Espíritos", "item_number": "167", "label": "A justiça da reencarnação"},
    {"book": "O Livro dos Espíritos", "item_number": "614", "label": "O que é a lei de Deus?"}
  ]
}
```

- [ ] **Step 4: Create `data/paths/fundamentos-espirita-aprofundado.json`**

```json
{
  "id": "fundamentos-espirita-aprofundado",
  "title": "Fundamentos da Doutrina Espírita",
  "description": "Para o espírita praticante. Cobertura completa das quatro partes do Livro dos Espíritos.",
  "level": "aprofundado",
  "steps": [
    {"book": "O Livro dos Espíritos", "item_number": "1",   "label": "O que é Deus?"},
    {"book": "O Livro dos Espíritos", "item_number": "13",  "label": "Atributos da Divindade"},
    {"book": "O Livro dos Espíritos", "item_number": "27",  "label": "A trindade universal — Deus, Espírito e matéria"},
    {"book": "O Livro dos Espíritos", "item_number": "37",  "label": "Como se formam os mundos?"},
    {"book": "O Livro dos Espíritos", "item_number": "63",  "label": "O princípio vital"},
    {"book": "O Livro dos Espíritos", "item_number": "76",  "label": "O que são os Espíritos?"},
    {"book": "O Livro dos Espíritos", "item_number": "93",  "label": "O invólucro semimaterial do Espírito"},
    {"book": "O Livro dos Espíritos", "item_number": "100", "label": "A escala espírita — classificação dos Espíritos"},
    {"book": "O Livro dos Espíritos", "item_number": "132", "label": "Por que os Espíritos se encarnaram?"},
    {"book": "O Livro dos Espíritos", "item_number": "134", "label": "O que é a alma?"},
    {"book": "O Livro dos Espíritos", "item_number": "141", "label": "Os dois invólucros da alma — o perispírito"},
    {"book": "O Livro dos Espíritos", "item_number": "149", "label": "O que acontece após a morte?"},
    {"book": "O Livro dos Espíritos", "item_number": "150", "label": "A alma conserva sua individualidade após a morte?"},
    {"book": "O Livro dos Espíritos", "item_number": "163", "label": "A perturbação espiritual após a morte"},
    {"book": "O Livro dos Espíritos", "item_number": "166", "label": "Como a alma se depura?"},
    {"book": "O Livro dos Espíritos", "item_number": "167", "label": "A justiça da reencarnação"},
    {"book": "O Livro dos Espíritos", "item_number": "218", "label": "As idéias inatas — vestígios de vidas anteriores"},
    {"book": "O Livro dos Espíritos", "item_number": "614", "label": "O que é a lei de Deus?"},
    {"book": "O Livro dos Espíritos", "item_number": "843", "label": "O livre-arbítrio"},
    {"book": "O Livro dos Espíritos", "item_number": "886", "label": "O verdadeiro sentido da caridade"}
  ]
}
```

- [ ] **Step 5: Run the paths tests**

```bash
uv run pytest tests/test_paths.py tests/test_api.py -v
```

Expected: All PASS. The new files are in `data/paths/` and the path loader picks up all `.json` files in that directory. Existing fixtures in `test_paths.py` use a `tmp_path`, so they are unaffected by the file changes.

- [ ] **Step 6: Commit**

```bash
git add data/paths/
git commit -m "feat: add Livro dos Espirítos paths (curioso, estudante, aprofundado)

Replaces fundamentos-da-doutrina.json with three standalone paths.
Fixes incorrect item citations: item 2→13 for Atributos da Divindade,
item 219→149 for O que acontece após a morte."
```

---

### Task 3: Create Evangelho path files

**Files:**
- Create: `data/paths/fundamentos-evangelico-curioso.json`
- Create: `data/paths/fundamentos-evangelico-estudante.json`
- Create: `data/paths/fundamentos-evangelico-aprofundado.json`

**Interfaces:**
- Consumes: `PathStep` with `chapter` (from Task 1) — every step here includes `chapter`
- Produces: three JSON files loadable by `load_all_paths` / `load_path`

Each step uses `"item_number": "1"` (the opening Gospel verse of each chapter). The `chapter` value is the exact string stored by the parser (e.g., `"CAPÍTULO I"` from `# CAPÍTULO I` stripped of `#`).

Chapters by number:
- CAPÍTULO I — Não vim destruir a lei (As três revelações: Moisés, Cristo, Espiritismo)
- CAPÍTULO II — Meu reino não é deste mundo (A vida futura)
- CAPÍTULO III — Há muitas moradas na casa de meu pai (Mundos e estados da alma)
- CAPÍTULO IV — Ninguém poderá ver o reino de Deus se não nascer de novo (A reencarnação)
- CAPÍTULO V — Bem-aventurados os aflitos (O sentido do sofrimento)
- CAPÍTULO VI — O Cristo consolador
- CAPÍTULO VII — Bem-aventurados os pobres de espírito (Humildade)
- CAPÍTULO VIII — Bem-aventurados os que têm puro o coração
- CAPÍTULO IX — Bem-aventurados os que são brandos e pacíficos
- CAPÍTULO X — Bem-aventurados os que são misericordiosos (Misericórdia e perdão)
- CAPÍTULO XI — Amar o próximo como a si mesmo
- CAPÍTULO XII — Amai os vossos inimigos
- CAPÍTULO XIII — Não saiba a vossa mão esquerda o que dê a vossa mão direita (Caridade sem ostentação)
- CAPÍTULO XV — Fora da caridade não há salvação
- CAPÍTULO XVI — Não se pode servir a Deus e a Mamon
- CAPÍTULO XVII — Sede perfeitos
- CAPÍTULO XIX — A fé transporta montanhas
- CAPÍTULO XXV — Buscai e achareis
- CAPÍTULO XXVI — Dai gratuitamente o que gratuitamente recebestes
- CAPÍTULO XXVII — Pedi e obtereis (A prece)

- [ ] **Step 1: Create `data/paths/fundamentos-evangelico-curioso.json`**

```json
{
  "id": "fundamentos-evangelico-curioso",
  "title": "Fundamentos do Evangelho Espírita",
  "description": "Para quem está começando. Uma leitura filosófica das grandes verdades morais do Espiritismo.",
  "level": "curioso",
  "steps": [
    {"book": "O Evangelho Segundo o Espiritismo", "chapter": "CAPÍTULO I",    "item_number": "1", "label": "As três revelações: Moisés, Cristo, Espiritismo"},
    {"book": "O Evangelho Segundo o Espiritismo", "chapter": "CAPÍTULO II",   "item_number": "1", "label": "A vida futura e o reino de Jesus"},
    {"book": "O Evangelho Segundo o Espiritismo", "chapter": "CAPÍTULO IV",   "item_number": "1", "label": "A reencarnação — nascer de novo"},
    {"book": "O Evangelho Segundo o Espiritismo", "chapter": "CAPÍTULO V",    "item_number": "1", "label": "O sentido do sofrimento"},
    {"book": "O Evangelho Segundo o Espiritismo", "chapter": "CAPÍTULO VII",  "item_number": "1", "label": "Humildade — os pobres de espírito"},
    {"book": "O Evangelho Segundo o Espiritismo", "chapter": "CAPÍTULO XI",   "item_number": "1", "label": "Amar o próximo como a si mesmo"},
    {"book": "O Evangelho Segundo o Espiritismo", "chapter": "CAPÍTULO XV",   "item_number": "1", "label": "Fora da caridade não há salvação"},
    {"book": "O Evangelho Segundo o Espiritismo", "chapter": "CAPÍTULO XIX",  "item_number": "1", "label": "A fé"}
  ]
}
```

- [ ] **Step 2: Create `data/paths/fundamentos-evangelico-estudante.json`**

```json
{
  "id": "fundamentos-evangelico-estudante",
  "title": "Fundamentos do Evangelho Espírita",
  "description": "Para quem conhece o básico e quer ampliar o panorama moral e filosófico.",
  "level": "estudante",
  "steps": [
    {"book": "O Evangelho Segundo o Espiritismo", "chapter": "CAPÍTULO I",     "item_number": "1", "label": "As três revelações: Moisés, Cristo, Espiritismo"},
    {"book": "O Evangelho Segundo o Espiritismo", "chapter": "CAPÍTULO II",    "item_number": "1", "label": "A vida futura e o reino de Jesus"},
    {"book": "O Evangelho Segundo o Espiritismo", "chapter": "CAPÍTULO III",   "item_number": "1", "label": "Há muitas moradas na casa de meu pai"},
    {"book": "O Evangelho Segundo o Espiritismo", "chapter": "CAPÍTULO IV",    "item_number": "1", "label": "A reencarnação — nascer de novo"},
    {"book": "O Evangelho Segundo o Espiritismo", "chapter": "CAPÍTULO V",     "item_number": "1", "label": "O sentido do sofrimento"},
    {"book": "O Evangelho Segundo o Espiritismo", "chapter": "CAPÍTULO VII",   "item_number": "1", "label": "Humildade — os pobres de espírito"},
    {"book": "O Evangelho Segundo o Espiritismo", "chapter": "CAPÍTULO VIII",  "item_number": "1", "label": "Pureza do coração"},
    {"book": "O Evangelho Segundo o Espiritismo", "chapter": "CAPÍTULO X",     "item_number": "1", "label": "Misericórdia e perdão"},
    {"book": "O Evangelho Segundo o Espiritismo", "chapter": "CAPÍTULO XI",    "item_number": "1", "label": "Amar o próximo como a si mesmo"},
    {"book": "O Evangelho Segundo o Espiritismo", "chapter": "CAPÍTULO XIII",  "item_number": "1", "label": "Caridade sem ostentação"},
    {"book": "O Evangelho Segundo o Espiritismo", "chapter": "CAPÍTULO XV",    "item_number": "1", "label": "Fora da caridade não há salvação"},
    {"book": "O Evangelho Segundo o Espiritismo", "chapter": "CAPÍTULO XIX",   "item_number": "1", "label": "A fé"},
    {"book": "O Evangelho Segundo o Espiritismo", "chapter": "CAPÍTULO XXVII", "item_number": "1", "label": "Pedi e obtereis — a prece"}
  ]
}
```

- [ ] **Step 3: Create `data/paths/fundamentos-evangelico-aprofundado.json`**

```json
{
  "id": "fundamentos-evangelico-aprofundado",
  "title": "Fundamentos do Evangelho Espírita",
  "description": "Para o espírita praticante. Percurso completo pelas grandes lições morais do Evangelho.",
  "level": "aprofundado",
  "steps": [
    {"book": "O Evangelho Segundo o Espiritismo", "chapter": "CAPÍTULO I",     "item_number": "1", "label": "As três revelações: Moisés, Cristo, Espiritismo"},
    {"book": "O Evangelho Segundo o Espiritismo", "chapter": "CAPÍTULO II",    "item_number": "1", "label": "A vida futura e o reino de Jesus"},
    {"book": "O Evangelho Segundo o Espiritismo", "chapter": "CAPÍTULO III",   "item_number": "1", "label": "Há muitas moradas na casa de meu pai"},
    {"book": "O Evangelho Segundo o Espiritismo", "chapter": "CAPÍTULO IV",    "item_number": "1", "label": "A reencarnação — nascer de novo"},
    {"book": "O Evangelho Segundo o Espiritismo", "chapter": "CAPÍTULO V",     "item_number": "1", "label": "O sentido do sofrimento"},
    {"book": "O Evangelho Segundo o Espiritismo", "chapter": "CAPÍTULO VI",    "item_number": "1", "label": "O Cristo consolador"},
    {"book": "O Evangelho Segundo o Espiritismo", "chapter": "CAPÍTULO VII",   "item_number": "1", "label": "Humildade — os pobres de espírito"},
    {"book": "O Evangelho Segundo o Espiritismo", "chapter": "CAPÍTULO VIII",  "item_number": "1", "label": "Pureza do coração"},
    {"book": "O Evangelho Segundo o Espiritismo", "chapter": "CAPÍTULO IX",    "item_number": "1", "label": "Mansidão e paz"},
    {"book": "O Evangelho Segundo o Espiritismo", "chapter": "CAPÍTULO X",     "item_number": "1", "label": "Misericórdia e perdão"},
    {"book": "O Evangelho Segundo o Espiritismo", "chapter": "CAPÍTULO XI",    "item_number": "1", "label": "Amar o próximo como a si mesmo"},
    {"book": "O Evangelho Segundo o Espiritismo", "chapter": "CAPÍTULO XII",   "item_number": "1", "label": "Amai os vossos inimigos"},
    {"book": "O Evangelho Segundo o Espiritismo", "chapter": "CAPÍTULO XIII",  "item_number": "1", "label": "Caridade sem ostentação"},
    {"book": "O Evangelho Segundo o Espiritismo", "chapter": "CAPÍTULO XV",    "item_number": "1", "label": "Fora da caridade não há salvação"},
    {"book": "O Evangelho Segundo o Espiritismo", "chapter": "CAPÍTULO XVI",   "item_number": "1", "label": "Não se pode servir a Deus e a Mamon"},
    {"book": "O Evangelho Segundo o Espiritismo", "chapter": "CAPÍTULO XVII",  "item_number": "1", "label": "Sede perfeitos"},
    {"book": "O Evangelho Segundo o Espiritismo", "chapter": "CAPÍTULO XIX",   "item_number": "1", "label": "A fé"},
    {"book": "O Evangelho Segundo o Espiritismo", "chapter": "CAPÍTULO XXV",   "item_number": "1", "label": "Buscai e achareis"},
    {"book": "O Evangelho Segundo o Espiritismo", "chapter": "CAPÍTULO XXVI",  "item_number": "1", "label": "Dai gratuitamente o que gratuitamente recebestes"},
    {"book": "O Evangelho Segundo o Espiritismo", "chapter": "CAPÍTULO XXVII", "item_number": "1", "label": "Pedi e obtereis — a prece"}
  ]
}
```

- [ ] **Step 4: Run all tests**

```bash
uv run pytest -v
```

Expected: All tests PASS. The `load_all_paths` in `test_paths.py` uses a `tmp_path` fixture and is unaffected. The `_PATH_DETAIL` fixture in `test_api.py` also uses a hardcoded dict, not the real files.

- [ ] **Step 5: Commit**

```bash
git add data/paths/fundamentos-evangelico-curioso.json \
        data/paths/fundamentos-evangelico-estudante.json \
        data/paths/fundamentos-evangelico-aprofundado.json
git commit -m "feat: add Evangelho paths (curioso, estudante, aprofundado)

Philosophical track based on O Evangelho Segundo o Espiritismo.
Each step uses chapter-scoped lookups enabled by Task 1's chapter filter."
```
