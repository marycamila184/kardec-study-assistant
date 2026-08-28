from datetime import datetime, timezone

from src.push.schedule import is_due

# 2026-08-27 11:00 UTC é 08:00 em São Paulo (UTC-3).
_ONZE_UTC = datetime(2026, 8, 27, 11, 0, tzinfo=timezone.utc)


def test_esta_na_janela_quando_a_hora_local_bate():
    assert is_due("08:00", "America/Sao_Paulo", _ONZE_UTC, 15)


def test_fora_da_janela_uma_hora_antes():
    assert not is_due(
        "08:00",
        "America/Sao_Paulo",
        datetime(2026, 8, 27, 10, 0, tzinfo=timezone.utc),
        15,
    )


def test_quem_escolheu_um_minuto_quebrado_e_pego_pela_execucao_seguinte():
    # O Scheduler roda em :00, :15, :30 e :45. Quem escolheu 08:10 NÃO é pego
    # às 08:00 — só na execução das 08:15, cinco minutos atrasado. É esse o
    # custo aceito da janela de 15 minutos: o lembrete pode chegar até uns 14
    # minutos depois da hora pedida. Um lembrete de estudo não é despertador.
    às_8h00 = datetime(2026, 8, 27, 11, 0, tzinfo=timezone.utc)
    às_8h15 = datetime(2026, 8, 27, 11, 15, tzinfo=timezone.utc)
    assert not is_due("08:10", "America/Sao_Paulo", às_8h00, 15)
    assert is_due("08:10", "America/Sao_Paulo", às_8h15, 15)


def test_nao_dispara_duas_vezes_na_mesma_janela():
    # 08:00 está na janela que começa às 08:00, e não na seguinte.
    assert is_due("08:00", "America/Sao_Paulo", _ONZE_UTC, 15)
    assert not is_due(
        "08:00",
        "America/Sao_Paulo",
        datetime(2026, 8, 27, 11, 15, tzinfo=timezone.utc),
        15,
    )


def test_fuso_de_meia_hora():
    # Índia é UTC+5:30. 02:30 UTC é 08:00 lá.
    assert is_due(
        "08:00", "Asia/Kolkata", datetime(2026, 8, 27, 2, 30, tzinfo=timezone.utc), 15
    )


def test_fuso_desconhecido_nao_explode_e_nao_dispara():
    # Um fuso inválido vindo do cliente não pode derrubar o Job inteiro:
    # aquele registro simplesmente não é elegível.
    assert not is_due("08:00", "Nao/Existe", _ONZE_UTC, 15)


def test_hora_malformada_nao_dispara():
    assert not is_due("banana", "America/Sao_Paulo", _ONZE_UTC, 15)
