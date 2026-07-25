"""How close a generated answer stays to the passages it was given.

riv-ai-v2 was trained on the Revista Espírita and complementary writings, which
are deliberately not in our index. The failure mode that creates is ungrounded
prose under a correct-looking citation: the source chip is real, the excerpt is
real, and the text beside them came from the model's weights. Citation
validation cannot see it (no citation is written), so we measure distance to the
retrieved text instead.

Used by the A/B harness as a comparison between lanes — never as an absolute
threshold. `attribute_sources` (below) is also called from the live /chat
request path on the prose lane; `groundedness_score` itself remains
harness-only.
"""

import math

from src.core.config import settings
from src.ingestion.embeddings import encode


def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0.0 or nb == 0.0:
        return 0.0
    return dot / (na * nb)


def _similarities(answer: str, chunks: list[dict], encoder) -> list[float]:
    answer_vec = encoder([answer])[0]
    chunk_vecs = encoder([c["content"] for c in chunks])
    return [_cosine(answer_vec, v) for v in chunk_vecs]


def groundedness_score(answer: str, chunks: list[dict], encoder=encode) -> float:
    """Mean cosine between the answer embedding and each retrieved chunk
    embedding. Returns 0.0 when there is nothing to compare."""
    if not answer.strip() or not chunks:
        return 0.0
    sims = _similarities(answer, chunks, encoder)
    return sum(sims) / len(sims)


def per_chunk_similarities(
    answer: str, chunks: list[dict], encoder=encode
) -> list[float]:
    """Per-chunk answer-to-chunk cosines, in the same order as `chunks`.

    Public so the A/B harness (`scripts/compare_generators.py`) can print the
    raw distribution needed to calibrate `settings.source_min_similarity` —
    `groundedness_score`'s mean hides exactly the per-chunk spread a threshold
    needs. Not used on the live request path; `attribute_sources` computes its
    own similarities internally."""
    if not answer.strip() or not chunks:
        return []
    return _similarities(answer, chunks, encoder)


def attribute_sources(
    answer: str,
    chunks: list[dict],
    min_similarity: float | None = None,
    margin: float | None = None,
    max_sources: int | None = None,
    encoder=encode,
) -> list[dict]:
    """The retrieved chunks an answer actually draws on, ranked by similarity.

    This replaces the model-written [FONTES:] marker on the prose lane. Which
    passages become source chips is decided here, in code, from the vector
    store — the model contributes nothing to attribution. riv-ai-v2 was
    observed emitting question numbers instead of passage indices and inventing
    references outright, so its opinion on its own sources is not usable.

    The cut is **relative to the best chunk for this answer**, not an absolute
    similarity. The 2026-07-25 A/B run showed why: the similarity level tracks
    how dense the question's vocabulary is, not how relevant the passage is, so
    no fixed height separates the two. The worst chunk for "o que é o
    perispírito?" scored 0.744 while the best chunk for "o que a doutrina diz
    sobre o perdão?" scored 0.740 — one absolute threshold cannot be right for
    both. Within a single question the step is clear (mean 0.092 at the elbow),
    so `margin` cuts there and rides each question's own scale.

    `min_similarity` survives as an absolute floor: the margin alone would keep
    everything when retrieval is uniformly bad, since it only compares chunks to
    each other.

    Never returns empty while chunks exist: if nothing clears the bar the single
    closest chunk survives, so an answer is never shown sourceless.
    """
    if not answer.strip() or not chunks:
        return []
    if min_similarity is None:
        min_similarity = settings.source_min_similarity
    if margin is None:
        margin = settings.source_relative_margin
    if max_sources is None:
        max_sources = settings.source_max_count
    scored = sorted(
        zip(_similarities(answer, chunks, encoder), chunks),
        key=lambda pair: pair[0],
        reverse=True,
    )
    best = scored[0][0]
    kept = [
        c for sim, c in scored if sim >= best - margin and sim >= min_similarity
    ][:max_sources]
    return kept or [scored[0][1]]
