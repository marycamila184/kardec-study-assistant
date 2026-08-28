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
        r = client.post("/push/unsubscribe", json={"endpoint": _CORPO["endpoint"]})
    assert r.status_code == 204
    apagar.assert_called_once_with(_CORPO["endpoint"])


def test_seen_carimba_a_data():
    with patch("src.api.routes.push_store.touch") as carimbar:
        r = client.post("/push/seen", json={"endpoint": _CORPO["endpoint"]})
    assert r.status_code == 204
    carimbar.assert_called_once()


def test_subscribe_e_limitado_por_taxa():
    """O único caminho que CRIA registro, e por isso o único com teto: sem
    isto, qualquer um poderia crescer a coleção que o job de despacho lê
    inteira a cada 15 minutos."""
    with patch("src.api.routes.check_rate_limit", return_value=42):
        r = client.post("/push/subscribe", json=_CORPO)
    assert r.status_code == 429
    assert r.headers["Retry-After"] == "42"


def test_subscribe_rejeita_hora_malformada():
    # Sem isto, uma hora que não bate com HH:MM não dá erro nenhum: is_due
    # devolve False para sempre e o lembrete nunca chega, em silêncio.
    corpo = {**_CORPO, "hour": "25:99"}
    r = client.post("/push/subscribe", json=corpo)
    assert r.status_code == 422


def test_subscribe_rejeita_fuso_desconhecido():
    corpo = {**_CORPO, "timezone": "Nao/Existe"}
    r = client.post("/push/subscribe", json=corpo)
    assert r.status_code == 422


def test_o_push_nao_acrescenta_campo_nenhum_ao_log_de_turnos():
    # A salvaguarda inteira desta funcionalidade é o store não cruzar com
    # nada. Se alguém um dia acrescentar `endpoint` ou `subscription` ao log,
    # este teste cai — que é o único aviso que existiria.
    #
    # É um arame de tropeço, não uma prova: alguém que ligasse os dois com um
    # campo de outro nome passaria por aqui. O sentido inverso — pôr um
    # session_id na Subscription — já cai no teste dos cinco campos em
    # test_push_store.py.
    import inspect

    from src.rag import conversation_log

    fonte = inspect.getsource(conversation_log)
    for proibido in ("endpoint", "subscription", "push_"):
        assert proibido not in fonte, f"{proibido} apareceu no log de turnos"
