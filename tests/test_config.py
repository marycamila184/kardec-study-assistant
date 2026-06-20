import pytest


def test_settings_has_correct_defaults(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    from src.core.config import Settings
    s = Settings()
    assert s.top_k == 5
    assert s.max_distance == 1.2
    assert s.max_history_turns == 10
    assert s.chroma_collection == "kardec_docs"
    assert s.chat_model == "claude-haiku-4-5"
    assert s.condenser_model == "claude-haiku-4-5"


def test_settings_requires_api_key(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    from pydantic import ValidationError
    from src.core.config import Settings
    with pytest.raises(ValidationError):
        Settings(_env_file=None)
