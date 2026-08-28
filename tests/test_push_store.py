from datetime import date
from unittest.mock import MagicMock, patch

from src.push.store import Subscription, delete_stale, from_document, to_document, touch


def _sub(**over):
    base = dict(
        endpoint="https://push.example/abc",
        keys={"p256dh": "chave-publica", "auth": "segredo"},
        hour="08:00",
        timezone="America/Sao_Paulo",
        last_seen=date(2026, 8, 27),
    )
    base.update(over)
    return Subscription(**base)


def test_o_documento_tem_exatamente_os_cinco_campos():
    # A regra dura da spec: um sexto campo exige reabrir a decisão. Este
    # teste é onde essa regra vira código.
    doc = to_document(_sub())
    assert set(doc) == {"endpoint", "keys", "hour", "timezone", "last_seen"}
    # E esta asserção é o que dá dentes à de cima: asdict() devolveria o mesmo
    # conjunto de chaves e deixaria last_seen como um objeto date. Serializar
    # explicitamente é o que separa os dois, então é isso que se confere.
    assert doc["last_seen"] == "2026-08-27"
    assert isinstance(doc["last_seen"], str)


def test_ida_e_volta_preserva_o_registro():
    sub = _sub()
    assert from_document(to_document(sub)) == sub


def test_delete_stale_apaga_quem_passou_do_prazo():
    velho = _sub(endpoint="https://push.example/velho", last_seen=date(2026, 5, 1))
    novo = _sub(endpoint="https://push.example/novo", last_seen=date(2026, 8, 20))
    apagados = []

    with (
        patch("src.push.store.all_subscriptions", return_value=[velho, novo]),
        patch("src.push.store.delete", side_effect=apagados.append),
    ):
        n = delete_stale(today=date(2026, 8, 27), max_age_days=90)

    assert n == 1
    assert apagados == ["https://push.example/velho"]


def test_delete_stale_nao_apaga_exatamente_no_limite():
    # 90 dias exatos ainda está dentro; só o 91º sai.
    no_limite = _sub(last_seen=date(2026, 5, 29))
    with (
        patch("src.push.store.all_subscriptions", return_value=[no_limite]),
        patch("src.push.store.delete") as apagar,
    ):
        n = delete_stale(today=date(2026, 8, 27), max_age_days=90)

    assert n == 0
    apagar.assert_not_called()


def test_carimbar_um_registro_que_nao_existe_nao_levanta():
    # Corrida normal: o clique na notificação chega depois de a inscrição ter
    # sido desligada ou varrida. Não é erro, e não pode virar 500.
    from google.api_core.exceptions import NotFound

    doc = MagicMock()
    doc.update.side_effect = NotFound("sumiu")
    with patch("src.push.store._colecao") as colecao:
        colecao.return_value.document.return_value = doc
        touch("https://push.example/sumido", date(2026, 8, 27))
