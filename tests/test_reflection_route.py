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
# All fields StudyResponse requires with no default — the pydantic model
# behind _study_response, unaffected by this fixture's brevity in the brief.
_RESULTADO = {
    "original_text": "texto original",
    "contexto": "explicação",
    "conceitos_chave": [],
    "perguntas": [],
    "sources": [],
    "related_items": [],
}


def test_a_passagem_do_dia_vem_do_cache_sem_chamar_o_modelo():
    with (
        patch("src.api.routes.get_daily_passage", return_value=_HOJE),
        patch("src.api.routes.reflection_cache.get", return_value=_RESULTADO),
        patch("src.api.routes.study_item_fn") as modelo,
    ):
        r = client.post("/study", json=_PEDIDO)

    assert r.status_code == 200
    modelo.assert_not_called()


def test_um_miss_gera_e_guarda():
    with (
        patch("src.api.routes.get_daily_passage", return_value=_HOJE),
        patch("src.api.routes.reflection_cache.get", return_value=None),
        patch("src.api.routes.reflection_cache.put") as guardar,
        patch("src.api.routes.study_item_fn", return_value=_RESULTADO),
    ):
        r = client.post("/study", json=_PEDIDO)

    assert r.status_code == 200
    guardar.assert_called_once()


def test_uma_falha_nunca_e_guardada():
    # The hard rule: a stored generation_failed would be served all day.
    falha = {
        "original_text": "texto original",
        "contexto": "",
        "conceitos_chave": [],
        "perguntas": [],
        "sources": [],
        "related_items": [],
        "generation_failed": True,
    }
    with (
        patch("src.api.routes.get_daily_passage", return_value=_HOJE),
        patch("src.api.routes.reflection_cache.get", return_value=None),
        patch("src.api.routes.reflection_cache.put") as guardar,
        patch("src.api.routes.study_item_fn", return_value=falha),
    ):
        client.post("/study", json=_PEDIDO)

    guardar.assert_not_called()


def test_outra_passagem_nao_toca_o_cache():
    # /study serves any item; only the day's own passage goes through the cache.
    outro = {**_PEDIDO, "item_number": "9"}
    with (
        patch("src.api.routes.get_daily_passage", return_value=_HOJE),
        patch("src.api.routes.reflection_cache.get") as ler,
        patch("src.api.routes.reflection_cache.put") as guardar,
        patch("src.api.routes.study_item_fn", return_value=_RESULTADO),
    ):
        client.post("/study", json=outro)

    ler.assert_not_called()
    guardar.assert_not_called()


def test_o_stream_do_dia_em_cache_manda_source_e_done_sem_token():
    with (
        patch("src.api.routes.get_daily_passage", return_value=_HOJE),
        patch("src.api.routes.reflection_cache.get", return_value=_RESULTADO),
        patch(
            "src.api.routes.prepare_study",
            return_value={"original_text": "t", "chunks": []},
        ),
        patch("src.api.routes.build_sources", return_value=[]),
        patch("src.api.routes.explicar_stream") as stream,
    ):
        r = client.post("/study/stream", json=_PEDIDO)

    corpo = r.text
    assert "event: source" in corpo
    assert "event: done" in corpo
    assert "event: token" not in corpo
    stream.assert_not_called()


def test_a_resposta_em_cache_e_identica_a_resposta_viva():
    # The guarantee the cache exists to give: same passage, same answer.
    # If /study ever starts carrying profile or history, this premise falls —
    # and this test is what warns, instead of the cache serving someone
    # else's answer.
    with (
        patch("src.api.routes.get_daily_passage", return_value=_HOJE),
        patch("src.api.routes.reflection_cache.get", return_value=None),
        patch("src.api.routes.reflection_cache.put"),
        patch("src.api.routes.study_item_fn", return_value=_RESULTADO),
    ):
        viva = client.post("/study", json=_PEDIDO).json()

    with (
        patch("src.api.routes.get_daily_passage", return_value=_HOJE),
        patch("src.api.routes.reflection_cache.get", return_value=_RESULTADO),
        patch("src.api.routes.study_item_fn") as modelo,
    ):
        do_cache = client.post("/study", json=_PEDIDO).json()

    modelo.assert_not_called()
    # `turn_id` is generated per request and legitimately differs.
    viva.pop("turn_id", None)
    do_cache.pop("turn_id", None)
    assert viva == do_cache
