"""The Gemini lane of the retrieval comparison harness.

The lane is an instrument, and the deployment decision rests on it, so the
parts that can silently corrupt a measurement get tests: batch splitting (the
API caps at 100 and rejects more), the document/query asymmetry (embedding a
query as a document degrades the model for reasons unrelated to the model),
and retry (a 429 mid-corpus must not leave half an index behind).
"""

import json
import os

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


CORPUS_DIR = "data/json_files"
needs_corpus = pytest.mark.skipif(
    not os.path.isdir(CORPUS_DIR), reason="data/json_files é gitignored e regenerável"
)


def corpus_chapter_titles() -> set[str]:
    titles = set()
    for filename in os.listdir(CORPUS_DIR):
        if filename.endswith(".json"):
            with open(os.path.join(CORPUS_DIR, filename), encoding="utf-8") as f:
                for chunk in json.load(f):
                    if chunk.get("chapter_title"):
                        titles.add(chunk["chapter_title"])
    return titles


@needs_corpus
def test_every_label_matches_a_real_chapter_title():
    """A mistyped label never matches and scores as "found nothing" — the
    harness would report a retrieval failure that is really a typo.

    This is not hypothetical: O Evangelho's misericordiosos chapter spells its
    hyphen U+2011 (NON-BREAKING HYPHEN) while every other BEM-AVENTURADOS uses
    U+002D. Typing that label by hand produces a label that can never hit.
    """
    titles = corpus_chapter_titles()
    unknown = [
        (case_set["name"], case["id"], label)
        for case_set in cr.CASE_SETS
        for case in case_set["cases"]
        for label in case["expect"] + case["avoid"]
        if label not in titles
    ]
    assert unknown == []


def test_expect_and_avoid_never_overlap():
    """A chapter counted as both apt and known-wrong makes the case unscoreable."""
    for case_set in cr.CASE_SETS:
        for case in case_set["cases"]:
            assert not set(case["expect"]) & set(case["avoid"]), case["id"]


def test_case_ids_are_unique_within_a_set():
    for case_set in cr.CASE_SETS:
        ids = [case["id"] for case in case_set["cases"]]
        assert len(ids) == len(set(ids)), case_set["name"]


def test_case_sets_cover_both_query_regimes():
    names = [case_set["name"] for case_set in cr.CASE_SETS]
    assert names == ["reflexivo", "chat"]
    assert len(cr.REFLECT_CASES) == 9  # 8 originais + ansiedade-nua
    assert len(cr.CHAT_CASES) == 8
    # /chat questions span all five works, so the lane must not be book-filtered
    assert dict(zip(names, [cs["where"] for cs in cr.CASE_SETS]))["chat"] is None
    # /reflect is restricted in production to these two works; the case set's
    # filter must measure the same universe /reflect actually searches.
    assert cr.CASE_SETS[0]["where"] == {"book": {"$in": list(cr.REFLECT_BOOKS)}}


def test_the_bug_that_started_this_is_a_case():
    """The bare phrasing, not only the long one: a longer query has more
    vocabulary to anchor the ranking and can pass while the short one fails."""
    by_id = {case["id"]: case for case in cr.REFLECT_CASES}
    assert by_id["ansiedade-nua"]["query"] == "estou me sentindo ansioso"
    assert "DA VOLTA DO ESPÍRITO À VIDA CORPORAL" in by_id["ansiedade-nua"]["avoid"]


def test_lane_names_are_stable_and_cover_every_lane():
    """The report's lane labels end up in the log that the decision cites."""
    assert list(cr.LANES) == [
        "bge-m3 (atual)",
        "e5-instruct (Together)",
        "gemini-2 @1024",
        "gemini-2 @3072",
        "qwen3-8b @1024",
        "qwen3-8b @4096",
    ]


def test_every_lane_declares_the_collection_it_reads():
    """`report()` skips un-indexed lanes by looking them up here. A lane missing
    from the map would count as never indexed and vanish from the comparison
    without ever being queried."""
    assert set(cr.LANE_COLLECTIONS) == set(cr.LANES)


def test_gemini_lanes_query_their_own_collection(monkeypatch):
    seen: list[tuple[str, int]] = []

    class FakeStore:
        def __init__(self, path, collection):
            seen.append(collection)

        def query(self, vector, n_results, where):
            seen.append(len(vector))
            return []

    monkeypatch.setattr(cr, "VectorStore", FakeStore)
    monkeypatch.setattr(
        cr, "_gemini_post", lambda body: {"embeddings": [{"values": [0.0] * 3072}]}
    )

    cr.LANES["gemini-2 @3072"]("uma consulta", None)

    assert seen[0] == "kardec_docs_gemini_3072"
    assert seen[1] == 3072


def test_index_choices_are_the_three_lanes():
    parser = cr.build_parser()
    args = parser.parse_args(["--index", "gemini-1024"])
    assert args.index == "gemini-1024"
    with pytest.raises(SystemExit):
        parser.parse_args(["--index", "gemini-2048"])


class FakeEmbeddings:
    """Stands in for the OpenAI-compatible embeddings endpoint."""

    def __init__(self, shuffle: bool = False):
        self.calls: list[dict] = []
        self.shuffle = shuffle

    def create(self, model, input, dimensions):
        self.calls.append({"model": model, "input": list(input), "dims": dimensions})
        items = [
            type("D", (), {"index": i, "embedding": [float(i)] * dimensions})()
            for i in range(len(input))
        ]
        return type(
            "R", (), {"data": list(reversed(items)) if self.shuffle else items}
        )()


class FakeClient:
    def __init__(self, embeddings):
        self.embeddings = embeddings


def test_qwen_instructs_queries_and_leaves_documents_bare(monkeypatch):
    """The asymmetry trap: Qwen3-Embedding expects the task instruction on the
    query only. Prefixing documents, or omitting it on queries, degrades the
    lane for a reason that is not the model."""
    api = FakeEmbeddings()
    monkeypatch.setattr(cr, "_openrouter_client", lambda: FakeClient(api))

    cr.encode_qwen(["um documento"], dim=1024)
    cr.encode_qwen(["uma consulta"], dim=1024, is_query=True)

    assert api.calls[0]["input"] == ["um documento"]
    assert api.calls[1]["input"] == [
        "Instruct: " + cr.QWEN_TASK + "\nQuery: uma consulta"
    ]


def test_qwen_reorders_vectors_by_returned_index(monkeypatch):
    """A batch returned out of order would store every document against another
    document's vector. Chroma accepts that silently; the only symptom is worse
    retrieval, which is exactly what this harness claims to measure."""
    api = FakeEmbeddings(shuffle=True)
    monkeypatch.setattr(cr, "_openrouter_client", lambda: FakeClient(api))

    vectors = cr.encode_qwen(["a", "b", "c"], dim=8)

    assert [v[0] for v in vectors] == [0.0, 1.0, 2.0]


def test_qwen_batches_at_the_pipeline_batch_size(monkeypatch):
    api = FakeEmbeddings()
    monkeypatch.setattr(cr, "_openrouter_client", lambda: FakeClient(api))

    vectors = cr.encode_qwen([f"t{i}" for i in range(150)], dim=1024)

    assert len(vectors) == 150
    assert [len(c["input"]) for c in api.calls] == [64, 64, 22]


def test_qwen_rejects_a_vector_of_the_wrong_width(monkeypatch):
    """MRL truncation is requested per call; a provider ignoring `dimensions`
    would fill the collection with vectors Chroma cannot match against."""

    class WrongWidth(FakeEmbeddings):
        def create(self, model, input, dimensions):
            return type(
                "R",
                (),
                {"data": [type("D", (), {"index": 0, "embedding": [0.0] * 4096})()]},
            )()

    monkeypatch.setattr(cr, "_openrouter_client", lambda: FakeClient(WrongWidth()))

    with pytest.raises(RuntimeError, match="4096"):
        cr.encode_qwen(["t"], dim=1024)


def test_report_skips_lanes_that_were_never_indexed(monkeypatch, capsys):
    """`VectorStore` opens with get_or_create_collection, so an un-indexed lane
    returns no hits instead of raising — and `summarize()` would print that as a
    genuine `hit_rate@5: 0.0`. Absent must read as absent, never as a score."""
    called: list[str] = []

    def fake_counts():
        return {name: (7347 if "bge" in name else None) for name in cr.LANES}

    monkeypatch.setattr(cr, "_collection_counts", fake_counts)
    for name in cr.LANES:
        monkeypatch.setitem(
            cr.LANES, name, lambda q, w, _n=name: called.append(_n) or []
        )

    cr.report()

    assert set(called) == {"bge-m3 (atual)"}
    out = capsys.readouterr().out
    assert "Vias não indexadas" in out
    assert "qwen3-8b @1024" in out


def test_summarize_reports_case_count_and_distance_to_cutoff():
    """`summarize()` must expose `n` (so lanes that raised on some cases are
    not silently compared over a smaller denominator), `dist@1` (mean rank-1
    distance) and `over_cutoff` (how many rank-1 hits exceed production's
    `settings.max_distance`) — built by hand, no network involved."""
    from src.core.config import settings

    rows = [
        {"best_rank": 1, "hit": True, "avoid_hit": False, "top_distance": 0.2},
        {
            "best_rank": None,
            "hit": False,
            "avoid_hit": False,
            "top_distance": settings.max_distance + 0.1,
        },
    ]

    summary = cr.summarize(rows)

    assert summary["n"] == 2
    assert summary["dist@1"] == round((0.2 + settings.max_distance + 0.1) / 2, 3)
    assert summary["over_cutoff"] == 1
