---
name: learning-paths-redesign
description: Redesign of Kardec study learning paths — 2 tracks (Livro dos Espíritos + Evangelho) × 3 levels (Curioso / Estudante / Aprofundado) + schema extension for chapter-scoped Evangelho items
metadata:
  type: project
---

# Learning Paths Redesign

## Context

The existing `data/paths/fundamentos-da-doutrina.json` is a single 6-step beginner path using only *O Livro dos Espíritos*. It has two incorrect citations and covers only the surface of the available material. The goal is to replace it with a structured set of paths that serve both newcomers and practicing Spiritists, across two reading traditions and three progression levels.

## Levels

| ID | Display | Target reader |
|---|---|---|
| `curioso` | Curioso | Never read Spiritism before; wants the essentials |
| `estudante` | Estudante | Familiar with basics; wants doctrinal depth |
| `aprofundado` | Aprofundado | Practicing Spiritist; wants complete systematic coverage |

Each level is **standalone** — not cumulative. A practicing Spiritist can go straight to Aprofundado without repeating Curioso.

## Tracks

### Track 1 — Livro dos Espíritos (technical/doctrinal)

Primary book: `O Livro dos Espíritos`. Item numbers are global (1–1019). No schema change needed.

**Fixes to the existing file:**
- Item 2 is labeled "Atributos da divindade" but its content is "O que se deve entender por infinito?" → replace with item 13 (the actual first question under the "Atributos da divindade" subsection).
- Item 219 is labeled "O que acontece após a morte?" but its content is about intuitive knowledge from past lives → replace with the correct item from the "A alma após a morte" section (items ~149–155; exact item confirmed during implementation).

**Curioso — 8 steps** (one anchor question per structural pillar)

| # | Item | Label |
|---|---|---|
| 1 | LE 1 | O que é Deus? |
| 2 | LE 13 | Atributos da Divindade |
| 3 | LE 76 | O que são os Espíritos? |
| 4 | LE 134 | O que é a alma? |
| 5 | LE 132 | Por que os Espíritos se encarnaram? |
| 6 | LE 166 | Como a alma se depura? |
| 7 | LE ~150 | O que acontece após a morte? |
| 8 | LE ~619 | O que é a lei moral? |

**Estudante — 13 steps** (adds orders of spirits, perispírito, perturbação, moral law depth)

Adds to Curioso:
- LE 27: A trindade universal (Deus, Espírito, matéria)
- LE ~100: Escala espírita — ordens de Espíritos
- LE 135: O perispírito
- LE 163–165: Perturbação espiritual após a morte
- LE 167: Justiça da reencarnação
- LE ~880: Caridade e justiça como leis morais (exact item confirmed during implementation)

**Aprofundado — 20 steps** (complete doctrinal map across all 4 Parts)

Adds to Estudante:
- Part 1 deeper: creation, vital principle (LE ~37, ~63)
- Multiple existences: idéias inatas (LE 218), reencarnação imediata ou tardia (LE 223)
- Full moral law coverage: freedom, equality, progress (Part 3 items; confirmed during implementation)
- Part 4: earthly pains, future pains/joys, future of humanity

**File names:**
- `fundamentos-espirita-curioso.json` (rename from `fundamentos-da-doutrina.json`)
- `fundamentos-espirita-estudante.json`
- `fundamentos-espirita-aprofundado.json`

---

### Track 2 — Evangelho segundo o Espiritismo (philosophical/moral)

Primary book: `O Evangelho segundo o Espiritismo`. Item numbers reset to 1 at each chapter, so **chapter is the primary reference unit** for this track. Each step points to a chapter, and `item_number` defaults to `"1"` (the opening Gospel verse).

**Curioso — 8 steps**

| # | Chapter | Label |
|---|---|---|
| 1 | CAPÍTULO I | As três revelações: Moisés, Cristo, Espiritismo |
| 2 | CAPÍTULO II | A vida futura e o reino de Jesus |
| 3 | CAPÍTULO IV | A reencarnação — nascer de novo |
| 4 | CAPÍTULO V | O sentido do sofrimento |
| 5 | CAPÍTULO VII | Humildade — os pobres de espírito |
| 6 | CAPÍTULO XI | Amar o próximo como a si mesmo |
| 7 | CAPÍTULO XV | Fora da caridade não há salvação |
| 8 | CAPÍTULO XIX | A fé |

**Estudante — 13 steps** (adds the Beatitudes and deeper moral teaching)

Adds to Curioso:
- CAPÍTULO III: Há muitas moradas na casa de meu pai (mundos)
- CAPÍTULO VIII: Bem-aventurados os que têm puro o coração
- CAPÍTULO X: Misericórdia e perdão
- CAPÍTULO XII: Amai os vossos inimigos
- CAPÍTULO XIII: Caridade sem ostentação
- CAPÍTULO XXVII: Pedi e obtereis (a prece)

**Aprofundado — 20 steps** (complete Gospel journey)

Adds to Estudante:
- CAPÍTULO VI: O Cristo consolador
- CAPÍTULO IX: Bem-aventurados os que são brandos e pacíficos
- CAPÍTULO XIV: Honrai a vosso pai e a vossa mãe
- CAPÍTULO XVI: Não se pode servir a Deus e a Mamon
- CAPÍTULO XVII: Sede perfeitos
- CAPÍTULO XVIII: Muitos os chamados, poucos os escolhidos
- CAPÍTULO XXV: Buscai e achareis
- CAPÍTULO XXVI: Dai gratuitamente o que gratuitamente recebestes

**File names:**
- `fundamentos-evangelico-curioso.json`
- `fundamentos-evangelico-estudante.json`
- `fundamentos-evangelico-aprofundado.json`

---

## Schema Change Required

The current path step schema:
```json
{"book": "...", "item_number": "1", "label": "..."}
```

Extended schema (backward-compatible — `chapter` is optional):
```json
{"book": "...", "chapter": "CAPÍTULO IV", "item_number": "1", "label": "..."}
```

All existing Livro dos Espíritos steps omit `chapter` (no change). All Evangelho steps include `chapter`.

### Code changes needed

1. **`data/paths/*.json`** — path step objects: add `chapter` field to Evangelho steps.
2. **`src/api/schemas.py`** — `StudyRequest`: add `chapter: str | None = None`.
3. **`src/rag/retriever.py`** — `retrieve_by_item`: add optional chapter filter to the `where` clause when chapter is provided.
4. **`src/rag/study.py`** — `study()`: accept and pass `chapter` to `retrieve_by_item`.
5. **`src/api/routes.py`** — `/study` route: pass `request.chapter` to `study_item_fn`.

---

## Future Work (not in scope)

- **Approach B (cross-referenced paths):** Evangelho Estudante/Aprofundado levels pulling LE items for doctrinal grounding, and vice versa. Deferred until a human reviewer curates the cross-references.
- **Céu e Inferno paths:** TBD — user has not decided yet.
- **Livro dos Médiuns paths:** not in scope for this iteration.
