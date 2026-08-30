from unittest.mock import MagicMock, patch

from src.rag.reflection_cache import cache_key, get, put

_PASSAGEM = {
    "date": "2026-08-29",
    "content": "texto original da passagem",
    "source": {
        "book": "O Evangelho Segundo o Espiritismo",
        "chapter": "CAPÍTULO VIII",
        "item_number": "2",
        "part": None,
    },
}
_RESPOSTA = {"contexto": "uma explicação", "sources": []}


def test_a_chave_muda_quando_a_passagem_muda():
    # The hard rule: keyed by the passage's IDENTITY, not just by the date.
    # A correction in trecho_diario.md must miss, not serve stale text.
    outra = {**_PASSAGEM, "source": {**_PASSAGEM["source"], "item_number": "3"}}
    assert cache_key(_PASSAGEM) != cache_key(outra)


def test_a_chave_muda_quando_o_dia_muda():
    assert cache_key(_PASSAGEM) != cache_key({**_PASSAGEM, "date": "2026-08-30"})


def test_a_chave_e_estavel_para_a_mesma_passagem():
    assert cache_key(_PASSAGEM) == cache_key(dict(_PASSAGEM))


def test_a_chave_muda_quando_so_o_texto_muda():
    # Identity (date, book, chapter, part, item_number) is unchanged here —
    # only the prose is corrected, same as a hand edit to trecho_diario.md
    # that fixes wording without touching which item it is. The key must
    # still change, or the stale explanation is served for the rest of the day.
    corrigida = {**_PASSAGEM, "content": "texto corrigido da passagem"}
    assert cache_key(_PASSAGEM) != cache_key(corrigida)


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
    # Firestore down cannot ever cost anyone's explanation: get returns
    # None and put swallows, exactly like the turn log does.
    with patch("src.rag.reflection_cache._colecao", side_effect=RuntimeError("fora")):
        assert get(_PASSAGEM) is None
        put(_PASSAGEM, _RESPOSTA)  # does not raise
