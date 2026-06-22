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


_STUDY_RESULT = {
    "original_text": "A alma é imortal.",
    "explanation": "A alma continua existindo após a morte do corpo físico.",
    "practical_example": "Como quando acordamos de um sonho muito vívido.",
    "related_items": [],
    "sources": [
        {"book": "O Livro dos Espíritos", "chapter_title": "Da Alma", "item_number": "150"}
    ],
    "generation_failed": False,
}

_PATH_SUMMARY = {
    "id": "fundamentos",
    "title": "Fundamentos",
    "description": "Para iniciantes.",
    "level": "iniciante",
    "step_count": 2,
}

_PATH_DETAIL = {
    "id": "fundamentos",
    "title": "Fundamentos",
    "description": "Para iniciantes.",
    "level": "iniciante",
    "steps": [
        {"book": "O Livro dos Espíritos", "item_number": "1", "label": "O que é Deus?"}
    ],
}


def test_study_returns_200():
    with patch("src.api.routes.study_item_fn", return_value=_STUDY_RESULT):
        response = client.post(
            "/study", json={"book": "O Livro dos Espíritos", "item_number": "150"}
        )
    assert response.status_code == 200
    data = response.json()
    assert data["original_text"] == "A alma é imortal."
    assert data["generation_failed"] is False


def test_study_returns_404_when_item_not_found():
    with patch("src.api.routes.study_item_fn", return_value=None):
        response = client.post(
            "/study", json={"book": "O Livro dos Espíritos", "item_number": "999"}
        )
    assert response.status_code == 404
    assert response.json()["detail"]["error"] == "item_not_found"


def test_list_paths_returns_200_with_summaries():
    with patch("src.api.routes.load_all_paths", return_value=[_PATH_SUMMARY]):
        response = client.get("/paths")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["id"] == "fundamentos"
    assert "steps" not in data[0]


def test_get_path_returns_full_detail():
    with patch("src.api.routes.load_path", return_value=_PATH_DETAIL):
        response = client.get("/paths/fundamentos")
    assert response.status_code == 200
    data = response.json()
    assert len(data["steps"]) == 1


def test_get_path_returns_404_when_not_found():
    with patch("src.api.routes.load_path", return_value=None):
        response = client.get("/paths/nonexistent")
    assert response.status_code == 404
    assert response.json()["detail"]["error"] == "path_not_found"


def test_chat_includes_suggested_mode_when_detected():
    with (
        patch("src.api.routes.generate", return_value=_ANSWER_RESULT),
        patch("src.api.routes.detect_suggested_mode", return_value="estudar_obra"),
    ):
        data = client.post(
            "/chat", json={"question": "explique a questão 132", "history": []}
        ).json()
    assert data["suggested_mode"] == "estudar_obra"


def test_chat_suggested_mode_is_none_for_generic_question():
    with (
        patch("src.api.routes.generate", return_value=_ANSWER_RESULT),
        patch("src.api.routes.detect_suggested_mode", return_value=None),
    ):
        data = client.post(
            "/chat", json={"question": "o que é amor?", "history": []}
        ).json()
    assert data["suggested_mode"] is None


_REFLECT_RESULT = {
    "opening": "Compreendemos profundamente sua dor.",
    "doctrine_connection": "A doutrina espírita ensina que a morte não é o fim.",
    "reflection_questions": [
        "O que essa situação revela sobre minha jornada espiritual?",
        "Como a perspectiva da continuidade da vida muda meu sentimento?",
        "Que mensagem meu pai poderia me transmitir agora?",
    ],
    "complementary_items": [],
    "sources": [
        {"book": "O Livro dos Espíritos", "chapter_title": "Da Alma", "item_number": "150"}
    ],
    "not_found": False,
    "generation_failed": False,
}

_REFLECT_NOT_FOUND = {
    "opening": "",
    "doctrine_connection": "Não encontrei passagens relacionadas.",
    "reflection_questions": [],
    "complementary_items": [],
    "sources": [],
    "not_found": True,
    "generation_failed": False,
}


def test_reflect_returns_200():
    with patch("src.api.routes.reflect_fn", return_value=_REFLECT_RESULT):
        response = client.post("/reflect", json={"situation": "meu pai faleceu"})
    assert response.status_code == 200
    data = response.json()
    assert data["opening"] == "Compreendemos profundamente sua dor."
    assert len(data["reflection_questions"]) == 3
    assert data["not_found"] is False


def test_reflect_returns_200_with_not_found_flag_when_no_doctrine():
    with patch("src.api.routes.reflect_fn", return_value=_REFLECT_NOT_FOUND):
        response = client.post("/reflect", json={"situation": "assunto sem doutrina"})
    assert response.status_code == 200
    assert response.json()["not_found"] is True


def test_reflect_response_has_all_required_fields():
    with patch("src.api.routes.reflect_fn", return_value=_REFLECT_RESULT):
        data = client.post("/reflect", json={"situation": "meu casamento está difícil"}).json()
    for field in ("opening", "doctrine_connection", "reflection_questions", "complementary_items", "sources", "not_found", "generation_failed"):
        assert field in data


def test_reflect_passes_situation_to_reflect_fn():
    with patch("src.api.routes.reflect_fn", return_value=_REFLECT_RESULT) as mock_fn:
        client.post("/reflect", json={"situation": "me sinto vazio"})
    mock_fn.assert_called_once_with("me sinto vazio")


_EVANGELHO_PASSAGE = {
    "date": "2026-06-22",
    "content": "Bem-aventurados os que têm puro o coração.",
    "source": {
        "book": "O Evangelho segundo o Espiritismo",
        "chapter_title": "Bem-aventuranças",
        "item_number": "section-4",
        "subchunk_index": 1,
        "total_subchunks": 1,
    },
}


def test_evangelho_returns_200():
    with patch("src.api.routes.get_daily_passage", return_value=_EVANGELHO_PASSAGE):
        response = client.get("/evangelho")
    assert response.status_code == 200
    data = response.json()
    assert data["date"] == "2026-06-22"
    assert data["content"] == "Bem-aventurados os que têm puro o coração."


def test_evangelho_response_has_source_fields():
    with patch("src.api.routes.get_daily_passage", return_value=_EVANGELHO_PASSAGE):
        data = client.get("/evangelho").json()
    assert data["source"]["book"] == "O Evangelho segundo o Espiritismo"
    assert data["source"]["chapter_title"] == "Bem-aventuranças"
    assert data["source"]["item_number"] == "section-4"
    assert data["source"]["subchunk_index"] == 1
    assert data["source"]["total_subchunks"] == 1


def test_evangelho_returns_503_when_not_indexed():
    with patch("src.api.routes.get_daily_passage", return_value=None):
        response = client.get("/evangelho")
    assert response.status_code == 503
    assert response.json()["detail"]["error"] == "evangelho_not_indexed"
