"""How close a generated answer stays to the passages it was given.

riv-ai-v2 was trained on the Revista Espírita and complementary writings, which
are deliberately not in our index. The failure mode that creates is ungrounded
prose under a correct-looking citation: the source chip is real, the excerpt is
real, and the text beside them came from the model's weights. Citation
validation cannot see it (no citation is written), so we measure distance to the
retrieved text instead.

Used by the A/B harness as a comparison between lanes — never as an absolute
threshold. Nothing here runs on the live request path: `attribute_sources` did,
behind the prose-lane gate, and went with it on 2026-07-28.
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
    needs. Not used on the live request path; the A/B harness computes its
    own similarities internally."""
    if not answer.strip() or not chunks:
        return []
    return _similarities(answer, chunks, encoder)
