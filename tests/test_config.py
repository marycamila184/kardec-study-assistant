import pytest


def _settings(monkeypatch, **env):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.delenv("TOGETHER_API_KEY", raising=False)
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    monkeypatch.delenv("CHAT_MODEL", raising=False)
    monkeypatch.delenv("CONDENSER_MODEL", raising=False)
    for k, v in env.items():
        monkeypatch.setenv(k, v)
    from src.core.config import Settings

    return Settings(_env_file=None)


def test_settings_has_correct_defaults(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "test-key")
    from src.core.config import Settings

    s = Settings()
    assert s.top_k == 5
    assert s.max_distance == 0.55
    assert s.max_history_turns == 10
    assert s.chroma_collection == "kardec_docs"
    assert s.paths_dir == "data/paths"
    assert s.embedding_model == "BAAI/bge-m3"


def test_defaults_to_groq_provider(monkeypatch):
    s = _settings(monkeypatch, GROQ_API_KEY="k")
    assert s.llm_provider == "groq"
    assert s.active_provider.base_url == "https://api.groq.com/openai/v1"
    assert s.active_api_key == "k"
    assert s.resolved_chat_model == "llama-3.3-70b-versatile"
    assert s.resolved_condenser_model == "llama-3.1-8b-instant"


def test_openrouter_provider_defaults(monkeypatch):
    s = _settings(monkeypatch, LLM_PROVIDER="openrouter", OPENROUTER_API_KEY="or-k")
    assert s.active_provider.base_url == "https://openrouter.ai/api/v1"
    assert s.active_api_key == "or-k"
    assert s.resolved_chat_model == "deepseek/deepseek-chat"


def test_together_provider_defaults(monkeypatch):
    s = _settings(monkeypatch, LLM_PROVIDER="together", TOGETHER_API_KEY="tg-k")
    assert s.active_provider.base_url == "https://api.together.xyz/v1"
    assert s.resolved_chat_model == "deepseek-ai/DeepSeek-V3"


def test_explicit_model_overrides_provider_default(monkeypatch):
    s = _settings(
        monkeypatch,
        LLM_PROVIDER="together",
        TOGETHER_API_KEY="tg-k",
        CHAT_MODEL="my/custom-model",
    )
    assert s.resolved_chat_model == "my/custom-model"


def test_unknown_provider_raises(monkeypatch):
    s = _settings(monkeypatch, LLM_PROVIDER="bogus", GROQ_API_KEY="k")
    with pytest.raises(ValueError, match="Unknown LLM_PROVIDER"):
        _ = s.active_provider


def test_missing_key_for_selected_provider_raises(monkeypatch):
    s = _settings(monkeypatch, LLM_PROVIDER="openrouter")  # no OPENROUTER_API_KEY
    with pytest.raises(ValueError, match="OPENROUTER_API_KEY"):
        _ = s.active_api_key
