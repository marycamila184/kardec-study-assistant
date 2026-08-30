from datetime import date, datetime, timezone
from unittest.mock import patch

from src.push.dispatch import run
from src.push.sender import Gone
from src.push.store import Subscription

_AGORA = datetime(2026, 8, 27, 11, 0, tzinfo=timezone.utc)  # 08:00 em SP


def _sub(endpoint, hour="08:00"):
    return Subscription(
        endpoint=endpoint,
        keys={"p256dh": "c", "auth": "s"},
        hour=hour,
        timezone="America/Sao_Paulo",
        last_seen=date(2026, 8, 27),
    )


def test_envia_so_para_quem_esta_na_janela():
    na_hora = _sub("https://push.example/agora", "08:00")
    mais_tarde = _sub("https://push.example/depois", "20:00")
    enviados = []

    with (
        patch(
            "src.push.dispatch.store.all_subscriptions",
            return_value=[na_hora, mais_tarde],
        ),
        patch("src.push.dispatch.store.delete_stale", return_value=0),
        patch(
            "src.push.dispatch.sender.send",
            side_effect=lambda s, chapter_title=None: enviados.append(s.endpoint),
        ),
    ):
        resultado = run(now_utc=_AGORA)

    assert enviados == ["https://push.example/agora"]
    assert resultado["sent"] == 1


def test_Gone_apaga_o_registro():
    sub = _sub("https://push.example/morto")
    apagados = []

    with (
        patch("src.push.dispatch.store.all_subscriptions", return_value=[sub]),
        patch("src.push.dispatch.store.delete_stale", return_value=0),
        patch("src.push.dispatch.store.delete", side_effect=apagados.append),
        patch("src.push.dispatch.sender.send", side_effect=Gone("x")),
    ):
        resultado = run(now_utc=_AGORA)

    assert apagados == ["https://push.example/morto"]
    assert resultado["gone"] == 1
    assert resultado["sent"] == 0


def test_uma_falha_nao_impede_os_outros():
    # Um endpoint com problema não pode custar o lembrete de todo mundo.
    ruim = _sub("https://push.example/ruim")
    bom = _sub("https://push.example/bom")
    enviados = []

    def enviar(sub, chapter_title=None):
        if sub.endpoint.endswith("ruim"):
            raise RuntimeError("timeout")
        enviados.append(sub.endpoint)

    with (
        patch("src.push.dispatch.store.all_subscriptions", return_value=[ruim, bom]),
        patch("src.push.dispatch.store.delete_stale", return_value=0),
        patch("src.push.dispatch.sender.send", side_effect=enviar),
    ):
        resultado = run(now_utc=_AGORA)

    assert enviados == ["https://push.example/bom"]
    assert resultado["failed"] == 1
    assert resultado["sent"] == 1


def test_a_varredura_dos_90_dias_roda_junto():
    with (
        patch("src.push.dispatch.store.all_subscriptions", return_value=[]),
        patch("src.push.dispatch.store.delete_stale", return_value=3) as varrer,
    ):
        resultado = run(now_utc=_AGORA)

    assert resultado["expired"] == 3
    assert varrer.call_args.kwargs["max_age_days"] == 90


def test_falha_transitoria_nunca_apaga_a_inscricao():
    # A propriedade mais importante deste arquivo. Apagar por engano tira o
    # lembrete de alguém que ainda usa, e o teste ao lado só provava isso por
    # acidente — o cliente real do Firestore explodiria sem credencial, o que
    # não é prova de nada.
    sub = _sub("https://push.example/instavel")

    with (
        patch("src.push.dispatch.store.all_subscriptions", return_value=[sub]),
        patch("src.push.dispatch.store.delete_stale", return_value=0),
        patch("src.push.dispatch.store.delete") as apagar,
        patch("src.push.dispatch.sender.send", side_effect=RuntimeError("timeout")),
    ):
        resultado = run(now_utc=_AGORA)

    apagar.assert_not_called()
    assert resultado["failed"] == 1


def test_all_subscriptions_e_chamado_uma_vez_so_por_execucao():
    # 192 varreduras completas por dia (uma para despachar, outra para os 90
    # dias) cruza o nível grátis do Firestore com poucas centenas de
    # aparelhos. dispatch.run precisa ler a coleção uma vez e reaproveitar a
    # lista na varredura dos expirados.
    with (
        patch("src.push.dispatch.store.all_subscriptions", return_value=[]) as buscar,
        patch("src.push.dispatch.store.delete_stale", return_value=0) as varrer,
    ):
        run(now_utc=_AGORA)

    buscar.assert_called_once()
    assert varrer.call_args.kwargs["subscriptions"] == []


def test_apagar_um_morto_falhando_nao_derruba_o_resto():
    # O aparelho morto é o primeiro da lista de propósito: se a falha do
    # delete subisse, o segundo nunca receberia.
    morto = _sub("https://push.example/morto")
    vivo = _sub("https://push.example/vivo")
    enviados = []

    def enviar(sub, chapter_title=None):
        if sub.endpoint.endswith("morto"):
            raise Gone("x")
        enviados.append(sub.endpoint)

    with (
        patch("src.push.dispatch.store.all_subscriptions", return_value=[morto, vivo]),
        patch("src.push.dispatch.store.delete_stale", return_value=0),
        patch(
            "src.push.dispatch.store.delete",
            side_effect=RuntimeError("firestore fora"),
        ),
        patch("src.push.dispatch.sender.send", side_effect=enviar),
    ):
        resultado = run(now_utc=_AGORA)

    assert enviados == ["https://push.example/vivo"]
    assert resultado["failed"] == 1


def test_o_capitulo_do_dia_chega_ao_envio():
    sub = _sub("https://push.example/a")
    recebidos = []

    with (
        patch("src.push.dispatch.store.all_subscriptions", return_value=[sub]),
        patch("src.push.dispatch.store.delete_stale", return_value=0),
        patch(
            "src.push.dispatch.get_daily_passage",
            return_value={"source": {"chapter_title": "OS AFLITOS"}},
        ),
        patch(
            "src.push.dispatch.sender.send",
            side_effect=lambda s, chapter_title=None: recebidos.append(chapter_title),
        ),
    ):
        run(now_utc=_AGORA)

    assert recebidos == ["OS AFLITOS"]


def test_o_lembrete_sai_mesmo_se_o_trecho_do_dia_falhar():
    # Falha ao ler o trecho não pode virar lembrete não enviado.
    sub = _sub("https://push.example/a")
    enviados = []

    with (
        patch("src.push.dispatch.store.all_subscriptions", return_value=[sub]),
        patch("src.push.dispatch.store.delete_stale", return_value=0),
        patch(
            "src.push.dispatch.get_daily_passage", side_effect=OSError("sem arquivo")
        ),
        patch(
            "src.push.dispatch.sender.send",
            side_effect=lambda s, chapter_title=None: enviados.append(chapter_title),
        ),
    ):
        resultado = run(now_utc=_AGORA)

    assert enviados == [None]
    assert resultado["sent"] == 1
