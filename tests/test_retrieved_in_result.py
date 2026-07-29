"""O conjunto recuperado sai do pipeline para o log — e não para a resposta.

`sources` é o subconjunto que a resposta citou; `retrieved` é tudo que chegou ao
prompt. A diferença entre os dois é o diagnóstico que faltava: mostra se o
trecho certo nem foi recuperado, ou foi e o modelo ignorou.

Ver docs/superpowers/specs/2026-07-28-log-de-sessao-e-feedback-design.md
"""

from src.rag.retriever import retrieved_summary


def test_summary_keeps_distance_raw_and_names_the_chapter():
    chunks = [
        {
            "content": "…",
            "distance": 0.31,
            "metadata": {
                "book": "A Gênese",
                "chapter_title": "OS FLUIDOS",
                "item_number": "22",
            },
        }
    ]
    assert retrieved_summary(chunks) == [
        {"book": "A Gênese", "chapter": "OS FLUIDOS", "item": "22", "distance": 0.31}
    ]


def test_summary_survives_missing_metadata():
    # Um chunk sem capítulo nem item não pode derrubar o log de um turno bom.
    chunks = [{"content": "…", "distance": 0.4, "metadata": {"book": "A Gênese"}}]
    assert retrieved_summary(chunks) == [
        {"book": "A Gênese", "chapter": None, "item": None, "distance": 0.4}
    ]


def test_summary_of_nothing_is_empty():
    assert retrieved_summary([]) == []


def test_summary_survives_a_chunk_with_no_book():
    """Chapter commentary reaches the prompt without full metadata.

    Caught by the existing suite on 2026-07-28: assuming `book` was always
    there raised a KeyError and turned a working /study into a 500. Logging may
    never break an answer that already worked.
    """
    assert retrieved_summary([{"content": "…", "metadata": {}}]) == [
        {"book": None, "chapter": None, "item": None, "distance": None}
    ]


def test_retrieved_is_not_a_copy_of_sources():
    """O ponto inteiro do campo: ele carrega o que NÃO foi citado.

    Um turno em que cinco trechos foram recuperados e um foi citado é
    exatamente o caso que `sources` sozinho torna invisível.
    """
    chunks = [
        {
            "content": f"trecho {i}",
            "distance": 0.3 + i / 100,
            "metadata": {
                "book": "A Gênese",
                "chapter_title": "OS FLUIDOS",
                "item_number": str(20 + i),
            },
        }
        for i in range(5)
    ]
    summary = retrieved_summary(chunks)
    assert len(summary) == 5
    assert [s["item"] for s in summary] == ["20", "21", "22", "23", "24"]
