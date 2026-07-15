from unittest.mock import MagicMock

from src.rag.sensitivity import classify_sensitivity


def _mock_client(monkeypatch, content):
    response = MagicMock()
    response.choices = [MagicMock(message=MagicMock(content=content))]
    client = MagicMock()
    client.chat.completions.create.return_value = response
    monkeypatch.setattr("src.rag.sensitivity.get_client", lambda: client)


def test_classify_returns_crise(monkeypatch):
    _mock_client(monkeypatch, '{"nivel": "crise"}')
    assert classify_sensitivity("não quero mais existir") == "crise"


def test_classify_returns_abalo(monkeypatch):
    _mock_client(monkeypatch, '{"nivel": "abalo"}')
    assert classify_sensitivity("estou cansada e não aguento mais") == "abalo"


def test_classify_returns_normal(monkeypatch):
    _mock_client(monkeypatch, '{"nivel": "normal"}')
    assert classify_sensitivity("o que é o perispírito?") == "normal"


def test_classify_invalid_level_defaults_normal(monkeypatch):
    _mock_client(monkeypatch, '{"nivel": "banana"}')
    assert classify_sensitivity("qualquer coisa") == "normal"


def test_classify_malformed_json_defaults_normal(monkeypatch):
    _mock_client(monkeypatch, "desculpe, não sei responder")
    assert classify_sensitivity("qualquer coisa") == "normal"


def test_classify_empty_text_defaults_normal():
    assert classify_sensitivity("") == "normal"


def test_classify_llm_failure_defaults_normal(monkeypatch):
    def _boom():
        raise RuntimeError("groq down")

    monkeypatch.setattr("src.rag.sensitivity.get_client", _boom)
    assert classify_sensitivity("texto") == "normal"
