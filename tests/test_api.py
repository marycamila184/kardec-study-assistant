from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from src.api.main import app
from src.api.schemas import ChatResponse, ReflectResponse

client = TestClient(app)

# Refletir is switched off in production; these tests exercise the now-gone
# /reflect route and are skipped along with it, not deleted (ReflectResponse
# stays a live schema, so test_reflect_response_safety_level_defaults_none
# below still runs unskipped).
# See docs/superpowers/specs/2026-07-26-desligar-reflexivo-design.md
_reflect_route_skip = pytest.mark.skip(
    reason="Refletir switched off — see docs/superpowers/specs/2026-07-26-desligar-reflexivo-design.md"
)

_ANSWER_RESULT = {
    "answer": "A reencarnação permite a evolução do espírito.",
    "sources": [
        {
            "book": "O Livro dos Espíritos",
            "chapter": "Da Encarnação",
            "item_number": "132",
        }
    ],
    "not_found": False,
}

_NOT_FOUND_RESULT = {
    "answer": "Não encontrei nas obras de Kardec informações suficientes…",
    "sources": [],
    "not_found": True,
}


def test_chat_returns_200():
    with patch("src.api.routes.generate", return_value=_ANSWER_RESULT):
        response = client.post(
            "/chat", json={"question": "O que é reencarnação?", "history": []}
        )
    assert response.status_code == 200


def test_chat_response_has_expected_fields():
    with patch("src.api.routes.generate", return_value=_ANSWER_RESULT):
        data = client.post(
            "/chat", json={"question": "O que é reencarnação?", "history": []}
        ).json()
    assert "answer" in data
    assert "sources" in data
    assert "not_found" in data
    assert data["not_found"] is False


def test_chat_not_found_flag_is_true_when_out_of_doctrine():
    with patch("src.api.routes.generate", return_value=_NOT_FOUND_RESULT):
        data = client.post(
            "/chat", json={"question": "Fale sobre budismo", "history": []}
        ).json()
    assert data["not_found"] is True
    assert data["sources"] == []


def test_chat_passes_history_to_generator():
    history = [
        {"role": "user", "content": "Olá"},
        {"role": "assistant", "content": "Olá!"},
    ]
    with patch("src.api.routes.generate", return_value=_ANSWER_RESULT) as mock_gen:
        client.post("/chat", json={"question": "Continua?", "history": history})
    _, called_history = mock_gen.call_args[0]
    assert len(called_history) == 2


def test_chat_surfaces_orchestrator_nudge():
    with (
        patch("src.api.routes.generate", return_value=_ANSWER_RESULT),
        patch(
            "src.api.routes.classify_intent",
            return_value={"mode": "refletir", "confidence": "high"},
        ),
    ):
        data = client.post(
            "/chat",
            json={"question": "estou muito mal", "current_mode": "tirar_duvida"},
        ).json()
    assert data["suggested_mode"] == "refletir"


def test_health_returns_ok():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


_STUDY_RESULT = {
    "original_text": "A alma é imortal.",
    "contexto": "A alma continua existindo após a morte do corpo físico.",
    "conceitos_chave": ["alma: princípio inteligente do ser"],
    "perguntas": ["O que isso significa para a nossa existência?"],
    "related_items": [],
    "sources": [
        {
            "book": "O Livro dos Espíritos",
            "chapter_title": "Da Alma",
            "item_number": "150",
        }
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
        patch(
            "src.api.routes.classify_intent",
            return_value={"mode": "estudar_obra", "confidence": "high"},
        ),
    ):
        data = client.post(
            "/chat", json={"question": "explique a questão 132", "history": []}
        ).json()
    assert data["suggested_mode"] == "estudar_obra"


def test_chat_suggested_mode_is_none_for_generic_question():
    with (
        patch("src.api.routes.generate", return_value=_ANSWER_RESULT),
        patch(
            "src.api.routes.classify_intent",
            return_value={"mode": None, "confidence": "low"},
        ),
    ):
        data = client.post(
            "/chat", json={"question": "o que é amor?", "history": []}
        ).json()
    assert data["suggested_mode"] is None
    assert data["suggested_item_number"] is None
    assert data["suggested_book"] is None


def test_chat_includes_study_reference_for_item_lookup():
    with (
        patch("src.api.routes.generate", return_value=_ANSWER_RESULT),
        patch(
            "src.api.routes.classify_intent",
            return_value={"mode": "estudar_obra", "confidence": "high"},
        ),
    ):
        data = client.post(
            "/chat",
            json={
                "question": "explique a questão 132 do Livro dos Espíritos",
                "history": [],
            },
        ).json()
    assert data["suggested_mode"] == "estudar_obra"
    assert data["suggested_item_number"] == "132"
    assert data["suggested_book"] == "O Livro dos Espíritos"


def test_chat_study_reference_questao_defaults_book_to_livro_espiritos():
    with (
        patch("src.api.routes.generate", return_value=_ANSWER_RESULT),
        patch(
            "src.api.routes.classify_intent",
            return_value={"mode": "estudar_obra", "confidence": "high"},
        ),
    ):
        data = client.post(
            "/chat", json={"question": "explique a questão 132", "history": []}
        ).json()
    assert data["suggested_item_number"] == "132"
    assert data["suggested_book"] == "O Livro dos Espíritos"


def test_chat_study_reference_book_is_none_for_generic_item():
    with (
        patch("src.api.routes.generate", return_value=_ANSWER_RESULT),
        patch(
            "src.api.routes.classify_intent",
            return_value={"mode": "estudar_obra", "confidence": "high"},
        ),
    ):
        data = client.post(
            "/chat", json={"question": "explique o item 45", "history": []}
        ).json()
    assert data["suggested_item_number"] == "45"
    assert data["suggested_book"] is None


def test_chat_no_study_reference_for_refletir_suggestion():
    with (
        patch("src.api.routes.generate", return_value=_ANSWER_RESULT),
        patch(
            "src.api.routes.classify_intent",
            return_value={"mode": "refletir", "confidence": "high"},
        ),
    ):
        data = client.post(
            "/chat",
            json={"question": "tenho medo de morrer no ano 2050", "history": []},
        ).json()
    assert data["suggested_mode"] == "refletir"
    assert data["suggested_item_number"] is None
    assert data["suggested_book"] is None


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
        {
            "book": "O Livro dos Espíritos",
            "chapter_title": "Da Alma",
            "item_number": "150",
        }
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


def test_reflect_route_is_gone():
    """Refletir is off (see the 2026-07-26 shutdown spec): the route does not
    exist in this version, so the honest answer is 404 — not a 503 that invites
    the frontend to retry."""
    response = client.post("/reflect", json={"situation": "estou triste"})
    assert response.status_code == 404


def test_chat_still_exits_on_first_person_ideation():
    """The floor that must survive the shutdown: /chat's crisis exit is not
    part of the Refletir feature and cannot go away with it."""
    from src.rag.crisis import CRISIS_EXIT_MESSAGE

    crisis_result = {
        "answer": CRISIS_EXIT_MESSAGE,
        "sources": [],
        "suggested_questions": [],
        "not_found": False,
        "safety_level": "crise",
    }
    with patch("src.api.routes.generate", return_value=crisis_result):
        response = client.post("/chat", json={"question": "eu quero morrer"})
    assert response.status_code == 200
    body = response.json()
    assert body["safety_level"] == "crise"
    assert "188" in body["answer"]
    assert body["sources"] == []
    assert body["suggested_questions"] == []


@_reflect_route_skip
def test_reflect_returns_200():
    with patch("src.api.routes.reflect_fn", return_value=_REFLECT_RESULT):
        response = client.post("/reflect", json={"situation": "meu pai faleceu"})
    assert response.status_code == 200
    data = response.json()
    assert data["opening"] == "Compreendemos profundamente sua dor."
    assert len(data["reflection_questions"]) == 3
    assert data["not_found"] is False


@_reflect_route_skip
def test_reflect_returns_200_with_not_found_flag_when_no_doctrine():
    with patch("src.api.routes.reflect_fn", return_value=_REFLECT_NOT_FOUND):
        response = client.post("/reflect", json={"situation": "assunto sem doutrina"})
    assert response.status_code == 200
    assert response.json()["not_found"] is True


@_reflect_route_skip
def test_reflect_response_has_all_required_fields():
    with patch("src.api.routes.reflect_fn", return_value=_REFLECT_RESULT):
        data = client.post(
            "/reflect", json={"situation": "meu casamento está difícil"}
        ).json()
    for field in (
        "opening",
        "doctrine_connection",
        "reflection_questions",
        "complementary_items",
        "sources",
        "not_found",
        "generation_failed",
        "is_closing",
    ):
        assert field in data


@_reflect_route_skip
def test_reflect_passes_situation_to_reflect_fn():
    with patch("src.api.routes.reflect_fn", return_value=_REFLECT_RESULT) as mock_fn:
        client.post("/reflect", json={"situation": "me sinto vazio"})
    mock_fn.assert_called_once_with("me sinto vazio", [], anchor_text=None)


@_reflect_route_skip
def test_reflect_passes_conversation_history_to_reflect_fn():
    history_payload = [
        {"role": "user", "content": "pergunta anterior"},
        {"role": "assistant", "content": "resposta anterior"},
    ]
    with patch("src.api.routes.reflect_fn", return_value=_REFLECT_RESULT) as mock_fn:
        client.post(
            "/reflect",
            json={
                "situation": "nova pergunta",
                "conversation_history": history_payload,
            },
        )
    mock_fn.assert_called_once_with("nova pergunta", history_payload, anchor_text=None)


@_reflect_route_skip
def test_reflect_response_includes_is_closing_field():
    result_with_closing = dict(_REFLECT_RESULT, is_closing=True)
    with patch("src.api.routes.reflect_fn", return_value=result_with_closing):
        data = client.post("/reflect", json={"situation": "situação"}).json()
    assert data["is_closing"] is True


@_reflect_route_skip
def test_reflect_surfaces_orchestrator_nudge():
    reflect_result = {
        "opening": "",
        "doctrine_connection": "texto",
        "reflection_questions": [],
        "complementary_items": [],
        "sources": [],
        "not_found": False,
        "generation_failed": False,
    }
    with (
        patch("src.api.routes.reflect_fn", return_value=reflect_result),
        patch(
            "src.api.routes.classify_intent",
            return_value={"mode": "estudar_obra", "confidence": "high"},
        ),
    ):
        data = client.post(
            "/reflect",
            json={"situation": "explique a questão 132", "current_mode": "refletir"},
        ).json()
    assert data["suggested_mode"] == "estudar_obra"
    assert data["suggested_item_number"] == "132"


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


def test_study_with_chapter_passes_chapter_to_study_fn():
    with patch("src.api.routes.study_item_fn", return_value=_STUDY_RESULT) as mock_fn:
        client.post(
            "/study",
            json={
                "book": "O Evangelho Segundo o Espiritismo",
                "item_number": "1",
                "chapter": "CAPÍTULO IV",
            },
        )
    mock_fn.assert_called_once_with(
        "O Evangelho Segundo o Espiritismo", "1", "CAPÍTULO IV"
    )


def test_evangelho_response_includes_chapter_summary():
    passage = dict(_EVANGELHO_PASSAGE, chapter_summary="Resumo do capítulo.")
    with patch("src.api.routes.get_daily_passage", return_value=passage):
        data = client.get("/evangelho").json()
    assert data["chapter_summary"] == "Resumo do capítulo."


def test_evangelho_response_chapter_summary_defaults_to_none():
    passage = dict(_EVANGELHO_PASSAGE, chapter_summary=None)
    with patch("src.api.routes.get_daily_passage", return_value=passage):
        data = client.get("/evangelho").json()
    assert data["chapter_summary"] is None


def test_chat_passes_suggested_questions_through():
    result = dict(_ANSWER_RESULT, suggested_questions=["Pergunta A?", "Pergunta B?"])
    with patch("src.api.routes.generate", return_value=result):
        data = client.post(
            "/chat", json={"question": "O que é a alma?", "history": []}
        ).json()
    assert data["suggested_questions"] == ["Pergunta A?", "Pergunta B?"]


def test_chat_forwards_anchor_text_to_generator():
    with patch("src.api.routes.generate", return_value=_ANSWER_RESULT) as mock_gen:
        client.post(
            "/chat",
            json={"question": "preciso ser criança?", "anchor_text": "humildade"},
        )
    assert mock_gen.call_args.kwargs["anchor_text"] == "humildade"


@_reflect_route_skip
def test_reflect_forwards_anchor_text_to_reflect_fn():
    with patch("src.api.routes.reflect_fn", return_value=_REFLECT_RESULT) as mock_ref:
        client.post(
            "/reflect",
            json={"situation": "estou pensando nisso", "anchor_text": "humildade"},
        )
    assert mock_ref.call_args.kwargs["anchor_text"] == "humildade"


@_reflect_route_skip
def test_reflect_never_self_nudges_even_if_classifier_says_refletir():
    def classify_with_guard(message, current_mode, history):
        # Simulate the real guard logic from orchestrator.classify_intent
        suggested = {"mode": "refletir", "confidence": "high"}
        if suggested["mode"] == current_mode:
            return {"mode": None, "confidence": suggested["confidence"]}
        return suggested

    with (
        patch("src.api.routes.reflect_fn", return_value=_REFLECT_RESULT),
        patch(
            "src.api.routes.classify_intent",
            side_effect=classify_with_guard,
        ),
    ):
        data = client.post(
            "/reflect", json={"situation": "ser criança novamente"}
        ).json()
    assert data["suggested_mode"] != "refletir"


@_reflect_route_skip
def test_reflect_passes_refletir_as_current_mode_to_classifier():
    with (
        patch("src.api.routes.reflect_fn", return_value=_REFLECT_RESULT),
        patch(
            "src.api.routes.classify_intent", return_value={"mode": None}
        ) as mock_cls,
    ):
        client.post(
            "/reflect", json={"situation": "algo", "current_mode": "tirar_duvida"}
        )
    # current_mode is the 2nd positional arg to classify_intent
    assert mock_cls.call_args.args[1] == "refletir"


def test_chat_passes_tirar_duvida_as_current_mode_to_classifier():
    with (
        patch("src.api.routes.generate", return_value=_ANSWER_RESULT),
        patch(
            "src.api.routes.classify_intent", return_value={"mode": None}
        ) as mock_cls,
    ):
        client.post("/chat", json={"question": "algo", "current_mode": "refletir"})
    assert mock_cls.call_args.args[1] == "tirar_duvida"


def test_chat_response_accepts_safety_level():
    resp = ChatResponse(answer="x", sources=[], safety_level="crise")
    assert resp.safety_level == "crise"


def test_reflect_response_safety_level_defaults_none():
    resp = ReflectResponse(
        opening="",
        doctrine_connection="x",
        reflection_questions=[],
        complementary_items=[],
        sources=[],
    )
    assert resp.safety_level is None


_CRISIS_ANSWER_RESULT = {
    "answer": "Sinto muito... 188 ... 192",
    "sources": [],
    "suggested_questions": [],
    "not_found": False,
    "generation_failed": False,
    "safety_level": "crise",
}


def test_chat_exposes_safety_level():
    with patch("src.api.routes.generate", return_value=_CRISIS_ANSWER_RESULT):
        data = client.post("/chat", json={"question": "não aguento mais viver"}).json()
    assert data["safety_level"] == "crise"


def test_chat_suppresses_nudge_on_crise():
    with (
        patch("src.api.routes.generate", return_value=_CRISIS_ANSWER_RESULT),
        patch(
            "src.api.routes.classify_intent",
            return_value={"mode": "refletir", "confidence": "high"},
        ),
    ):
        data = client.post("/chat", json={"question": "não aguento mais viver"}).json()
    assert data["suggested_mode"] is None


@_reflect_route_skip
def test_reflect_exposes_safety_level():
    crise_reflect = {
        "opening": "",
        "doctrine_connection": "Sinto muito... 188 ... 192",
        "reflection_questions": [],
        "is_closing": False,
        "complementary_items": [],
        "sources": [],
        "not_found": False,
        "generation_failed": False,
        "safety_level": "crise",
    }
    with (
        patch("src.api.routes.reflect_fn", return_value=crise_reflect),
        patch(
            "src.api.routes.classify_intent",
            return_value={"mode": "estudar_obra", "confidence": "high"},
        ),
    ):
        data = client.post(
            "/reflect", json={"situation": "não quero mais viver"}
        ).json()
    assert data["safety_level"] == "crise"
    assert data["suggested_mode"] is None


# --- abuse guards -------------------------------------------------------------


def test_long_message_never_reaches_the_model():
    """The guard has to run BEFORE generation, or it saves nothing."""
    from unittest.mock import patch

    with patch("src.api.routes.generate") as generate:
        response = client.post("/chat", json={"question": "palavra " * 2001})

    assert response.status_code == 200
    assert "duas mil palavras" in response.json()["answer"]
    assert response.json()["sources"] == []
    generate.assert_not_called()


def test_message_just_under_the_ceiling_flows_normally():
    from unittest.mock import patch

    with patch("src.api.routes.generate", return_value=_ANSWER_RESULT) as generate:
        response = client.post("/chat", json={"question": "palavra " * 1999})

    assert response.status_code == 200
    generate.assert_called_once()


def test_a_long_conversation_is_trimmed_not_refused():
    """Found in production 2026-07-28: history counted toward the ceiling, so a
    long conversation refused an eight-word question — and every question after
    it, since history only grows. The refusal was permanent."""
    from unittest.mock import patch

    # Over 2000 words of the reader's own text, which is what the ceiling counts.
    history = [{"role": "user", "content": "palavra " * 800} for _ in range(4)]
    with patch("src.api.routes.generate") as generate:
        generate.return_value = {
            "answer": "resposta",
            "sources": [],
            "suggested_questions": [],
            "not_found": False,
            "generation_failed": False,
            "safety_level": "normal",
        }
        response = client.post(
            "/chat", json={"question": "e sobre isso?", "history": history}
        )

    assert response.status_code == 200
    assert "duas mil palavras" not in response.json()["answer"]
    generate.assert_called_once()

    # The oldest turns were dropped to fit the budget, not the newest.
    passed_history = generate.call_args[0][1]
    assert len(passed_history) < len(history)


def test_a_single_over_long_message_is_still_refused():
    """The cost guard the ceiling exists for is unchanged."""
    from unittest.mock import patch

    with patch("src.api.routes.generate") as generate:
        response = client.post(
            "/chat", json={"question": "palavra " * 2500, "history": []}
        )

    assert "duas mil palavras" in response.json()["answer"]
    generate.assert_not_called()


def test_crisis_outranks_the_size_cap():
    """The guard that saves money can never be the one that answers ideation.

    A long message containing first-person ideation must reach the crisis exit
    with CVV 188, not the "your message is too long" reply.
    """
    from unittest.mock import patch

    question = "palavra " * 2500 + " eu quero morrer"
    with patch("src.api.routes.generate", return_value=_CRISIS_ANSWER_RESULT) as gen:
        response = client.post("/chat", json={"question": question})

    assert response.status_code == 200
    assert "duas mil palavras" not in response.json()["answer"]
    assert "188" in response.json()["answer"]
    gen.assert_called_once()


def test_rate_limit_returns_429_with_retry_after():
    from unittest.mock import patch

    from src.api import limits

    with patch("src.api.routes.generate", return_value=_ANSWER_RESULT):
        for _ in range(limits.RATE_LIMIT_REQUESTS):
            assert client.post("/chat", json={"question": "oi"}).status_code == 200
        blocked = client.post("/chat", json={"question": "oi"})

    assert blocked.status_code == 429
    assert int(blocked.headers["Retry-After"]) > 0
    assert "pausa" in blocked.json()["detail"]["message"]


def test_cheap_routes_are_not_rate_limited():
    from src.api import limits

    for _ in range(limits.RATE_LIMIT_REQUESTS + 5):
        assert client.get("/health").status_code == 200
    assert client.get("/paths").status_code == 200


def test_only_the_readers_own_words_count_toward_the_ceiling():
    """The assistant's turns are generated here and already bounded by
    max_tokens; counting them against the reader's budget is what made a long
    conversation refuse an eight-word question."""
    from unittest.mock import patch

    from src.api.limits import trim_history

    history = []
    for i in range(4):
        history.append({"role": "user", "content": f"u{i} " + "palavra " * 400})
        history.append({"role": "assistant", "content": f"a{i} " + "resposta " * 900})

    kept = trim_history("e sobre isso?", history)

    user_words = sum(len(m["content"].split()) for m in kept if m["role"] == "user")
    assert user_words <= 2000
    # Long assistant turns did not push the reader's turns out.
    assert len([m for m in kept if m["role"] == "user"]) == 4


def test_trimming_never_leaves_a_reply_without_its_question():
    from src.api.limits import trim_history

    history = []
    for i in range(5):
        history.append({"role": "user", "content": f"u{i} " + "palavra " * 700})
        history.append({"role": "assistant", "content": f"a{i} " + "resposta " * 50})

    kept = trim_history("pergunta", history)

    assert kept, "some history should survive"
    assert kept[0]["role"] == "user"
