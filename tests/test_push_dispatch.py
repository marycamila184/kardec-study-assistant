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
            side_effect=lambda s: enviados.append(s.endpoint),
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

    def enviar(sub):
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
