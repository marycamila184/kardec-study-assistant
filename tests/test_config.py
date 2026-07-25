import pytest


def _settings(monkeypatch, **env):
    for var in (
        "GROQ_API_KEY",
        "OPENROUTER_API_KEY",
        "TOGETHER_API_KEY",
        "LLM_PROVIDER",
        "CHAT_MODEL",
        "CONDENSER_MODEL",
        "PROSE_PROVIDER",
        "PROSE_MODEL",
        "OLLAMA_BASE_URL",
        "HF_ENDPOINT_URL",
        "HF_TOKEN",
    ):
        monkeypatch.delenv(var, raising=False)
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
    with pytest.raises(ValueError, match="Unknown provider"):
        _ = s.active_provider


def test_missing_key_for_selected_provider_raises(monkeypatch):
    s = _settings(monkeypatch, LLM_PROVIDER="openrouter")  # no OPENROUTER_API_KEY
    with pytest.raises(ValueError, match="OPENROUTER_API_KEY"):
        _ = s.active_api_key


def test_prose_lane_defaults_to_the_json_lane(monkeypatch):
    """PROSE_PROVIDER unset => prose is identical to chat. The rollback switch."""
    s = _settings(monkeypatch, GROQ_API_KEY="k")
    assert s.prose_provider is None
    assert s.prose_provider_name == "groq"
    assert s.resolved_prose_model == s.resolved_chat_model


def test_prose_lane_honors_chat_model_override_when_unset(monkeypatch):
    """An explicit CHAT_MODEL must still drive prose while PROSE_PROVIDER is unset."""
    s = _settings(monkeypatch, GROQ_API_KEY="k", CHAT_MODEL="my/custom-model")
    assert s.resolved_prose_model == "my/custom-model"


def test_ollama_prose_provider(monkeypatch):
    s = _settings(monkeypatch, GROQ_API_KEY="k", PROSE_PROVIDER="ollama")
    assert s.prose_provider_name == "ollama"
    assert s.provider("ollama").base_url == "http://localhost:11434/v1"
    assert s.resolved_prose_model == "hf.co/ia-espirita/riv-ai-v2-Q4_K_M-GGUF"
    assert s.api_key_for("ollama") == "ollama"  # dummy; SDK rejects empty


def test_prose_model_override(monkeypatch):
    s = _settings(
        monkeypatch,
        GROQ_API_KEY="k",
        PROSE_PROVIDER="ollama",
        PROSE_MODEL="some/other-gguf",
    )
    assert s.resolved_prose_model == "some/other-gguf"


def test_ollama_base_url_override(monkeypatch):
    s = _settings(
        monkeypatch,
        GROQ_API_KEY="k",
        PROSE_PROVIDER="ollama",
        OLLAMA_BASE_URL="http://192.168.0.9:11434/v1",
    )
    assert s.provider("ollama").base_url == "http://192.168.0.9:11434/v1"


def test_hf_endpoint_requires_a_url(monkeypatch):
    s = _settings(
        monkeypatch, GROQ_API_KEY="k", HF_TOKEN="hf-k", PROSE_PROVIDER="hf-endpoint"
    )
    with pytest.raises(ValueError, match="HF_ENDPOINT_URL"):
        _ = s.provider("hf-endpoint")


def test_hf_endpoint_with_url(monkeypatch):
    s = _settings(
        monkeypatch,
        GROQ_API_KEY="k",
        HF_TOKEN="hf-k",
        PROSE_PROVIDER="hf-endpoint",
        HF_ENDPOINT_URL="https://abc.endpoints.huggingface.cloud/v1",
    )
    assert (
        s.provider("hf-endpoint").base_url
        == "https://abc.endpoints.huggingface.cloud/v1"
    )
    assert s.api_key_for("hf-endpoint") == "hf-k"


def test_unknown_prose_provider_raises(monkeypatch):
    s = _settings(monkeypatch, GROQ_API_KEY="k", PROSE_PROVIDER="bogus")
    with pytest.raises(ValueError, match="Unknown provider"):
        _ = s.provider("bogus")
