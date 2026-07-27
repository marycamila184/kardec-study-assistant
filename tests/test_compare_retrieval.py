"""The Gemini lane of the retrieval comparison harness.

The lane is an instrument, and the deployment decision rests on it, so the
parts that can silently corrupt a measurement get tests: batch splitting (the
API caps at 100 and rejects more), the document/query asymmetry (embedding a
query as a document degrades the model for reasons unrelated to the model),
and retry (a 429 mid-corpus must not leave half an index behind).
"""

import pytest

from scripts import compare_retrieval as cr


class FakeAPI:
    """Records every request body and replies with correctly-shaped vectors."""

    def __init__(self, fail_with: list[int] | None = None):
        self.bodies: list[dict] = []
        self.fail_with = list(fail_with or [])

    def __call__(self, body: dict) -> dict:
        self.bodies.append(body)
        if self.fail_with:
            raise cr.GeminiHTTPError(self.fail_with.pop(0), "{}")
        dim = body["requests"][0]["outputDimensionality"]
        return {"embeddings": [{"values": [0.0] * dim} for _ in body["requests"]]}


def test_batches_split_at_the_api_cap_of_100(monkeypatch):
    api = FakeAPI()
    monkeypatch.setattr(cr, "_gemini_post", api)

    vectors = cr.encode_gemini([f"t{i}" for i in range(250)], dim=1024)

    assert len(vectors) == 250
    assert [len(b["requests"]) for b in api.bodies] == [100, 100, 50]
    assert all(len(v) == 1024 for v in vectors)


def test_documents_and_queries_use_different_task_types(monkeypatch):
    api = FakeAPI()
    monkeypatch.setattr(cr, "_gemini_post", api)

    cr.encode_gemini(["passagem"], dim=1024)
    cr.encode_gemini(["consulta"], dim=1024, is_query=True)

    assert api.bodies[0]["requests"][0]["taskType"] == "RETRIEVAL_DOCUMENT"
    assert api.bodies[1]["requests"][0]["taskType"] == "RETRIEVAL_QUERY"


def test_dimension_is_passed_through(monkeypatch):
    api = FakeAPI()
    monkeypatch.setattr(cr, "_gemini_post", api)

    vectors = cr.encode_gemini(["t"], dim=3072)

    assert api.bodies[0]["requests"][0]["outputDimensionality"] == 3072
    assert len(vectors[0]) == 3072


def test_rate_limit_is_retried_without_sleeping(monkeypatch):
    api = FakeAPI(fail_with=[429, 503])
    monkeypatch.setattr(cr, "_gemini_post", api)
    slept: list[float] = []

    # Body must be shaped like a real one: FakeAPI's success path reads
    # requests[0] to size its reply.
    body = {"requests": [{"outputDimensionality": 1024}]}
    result = cr._post_with_retry(body, sleep=slept.append)

    assert "embeddings" in result
    assert len(api.bodies) == 3
    assert slept == [1, 2]


def test_bad_request_is_not_retried(monkeypatch):
    """A 400 is the oversize-document signal. Retrying it would spin, and
    swallowing it would silently drop passages from the index."""
    api = FakeAPI(fail_with=[400])
    monkeypatch.setattr(cr, "_gemini_post", api)

    with pytest.raises(cr.GeminiHTTPError) as exc:
        cr._post_with_retry({"requests": []}, sleep=lambda _: None)

    assert exc.value.status == 400
    assert len(api.bodies) == 1


def test_short_response_is_an_error(monkeypatch):
    """Fewer vectors than inputs would misalign every id in the batch."""

    def short(body):
        return {"embeddings": [{"values": [0.0] * 1024}]}

    monkeypatch.setattr(cr, "_gemini_post", short)

    with pytest.raises(RuntimeError, match="2 textos"):
        cr.encode_gemini(["a", "b"], dim=1024)


def test_collection_name_carries_the_dimension():
    assert cr.gemini_collection(1024) == "kardec_docs_gemini_1024"
    assert cr.gemini_collection(3072) == "kardec_docs_gemini_3072"
