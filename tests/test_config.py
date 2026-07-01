import pytest


def test_settings_has_correct_defaults(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "test-key")
    from src.core.config import Settings
    s = Settings()
    assert s.top_k == 5
    assert s.max_distance == 1.2
    assert s.max_history_turns == 10
    assert s.chroma_collection == "kardec_docs"
    assert s.chat_model == "llama-3.3-70b-versatile"
    assert s.condenser_model == "llama-3.1-8b-instant"
    assert s.paths_dir == "data/paths"
    assert s.embedding_model == "BAAI/bge-m3"


def test_settings_requires_api_key(monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    from pydantic import ValidationError
    from src.core.config import Settings
    with pytest.raises(ValidationError):
        Settings(_env_file=None)
