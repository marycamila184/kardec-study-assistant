from unittest.mock import patch

from fastapi.testclient import TestClient

from src.api.main import app

client = TestClient(app)

_ANSWER_RESULT = {
    "answer": "A reencarnação permite a evolução do espírito.",
    "sources": [{"book": "O Livro dos Espíritos", "chapter": "Da Encarnação", "item_number": "132"}],
    "not_found": False,
}

_NOT_FOUND_RESULT = {
    "answer": "Não encontrei nas obras de Kardec informações suficientes…",
    "sources": [],
    "not_found": True,
}


def test_chat_returns_200():
    with patch("src.api.routes.generate", return_value=_ANSWER_RESULT):
        response = client.post("/chat", json={"question": "O que é reencarnação?", "history": []})
    assert response.status_code == 200


def test_chat_response_has_expected_fields():
    with patch("src.api.routes.generate", return_value=_ANSWER_RESULT):
        data = client.post("/chat", json={"question": "O que é reencarnação?", "history": []}).json()
    assert "answer" in data
    assert "sources" in data
    assert "not_found" in data
    assert data["not_found"] is False


def test_chat_not_found_flag_is_true_when_out_of_doctrine():
    with patch("src.api.routes.generate", return_value=_NOT_FOUND_RESULT):
        data = client.post("/chat", json={"question": "Fale sobre budismo", "history": []}).json()
    assert data["not_found"] is True
    assert data["sources"] == []


def test_chat_passes_history_to_generator():
    history = [{"role": "user", "content": "Olá"}, {"role": "assistant", "content": "Olá!"}]
    with patch("src.api.routes.generate", return_value=_ANSWER_RESULT) as mock_gen:
        client.post("/chat", json={"question": "Continua?", "history": history})
    _, called_history = mock_gen.call_args[0]
    assert len(called_history) == 2


def test_health_returns_ok():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
