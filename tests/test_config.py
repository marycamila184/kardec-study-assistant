import pytest


def _settings(monkeypatch, **env):
    for var in (
        # Not a Settings field anymore: an exported shell value would make
        # Settings() raise on the unknown key, so it has to be cleared here.
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
        "GOOGLE_API_KEY",
    ):
        monkeypatch.delenv(var, raising=False)
    for k, v in env.items():
        monkeypatch.setenv(k, v)
    from src.core.config import Settings

    return Settings(_env_file=None)


def test_settings_has_correct_defaults(monkeypatch):
    monkeypatch.setenv("TOGETHER_API_KEY", "test-key")
    from src.core.config import Settings

    s = Settings()
    assert s.top_k == 5
    assert s.max_distance == 0.45
    assert s.max_history_turns == 10
    assert s.chroma_collection == "kardec_docs"
    assert s.paths_dir == "data/paths"
    assert s.embedding_model == "BAAI/bge-m3"


def test_max_distance_sits_in_the_measured_gap(monkeypatch):
    """0.45 não é palpite: medido em 2026-07-29 sobre o índice bge-m3.

    As oito perguntas do arnês de /chat encontram seu capítulo apto entre 0.319
    e 0.379. Seis perguntas que as obras não cobrem — fofoca, chakras, signo,
    cristal, amuleto — têm sua MELHOR passagem entre 0.474 e 0.546. Os dois
    grupos não se tocam, e 0.45 fica no meio do vão: preserva 8/8 das cobertas
    e cala 6/6 das não cobertas.

    O limiar existe para isto: sem ele, uma pergunta que Kardec não trata ainda
    entrega cinco passagens fracas ao modelo, e foi sobre passagem fraca que ele
    inventou uma frase sobre demônios e a atribuiu a um trecho que fala de outra
    coisa. A guarda de citação não pegou porque a invenção veio parafraseada.

    Este projeto apertou guarda por raciocínio duas vezes e nas duas negou
    resposta correta. Se este número mudar, meça de novo — o vão é do bge-m3 e
    de mais nada.
    """
    monkeypatch.setenv("TOGETHER_API_KEY", "test-key")
    from src.core.config import Settings

    s = Settings()
    assert 0.379 < s.max_distance < 0.474


def test_defaults_to_together_provider(monkeypatch):
    """The tripwire that says which lane production is actually on."""
    s = _settings(monkeypatch, TOGETHER_API_KEY="k")
    assert s.llm_provider == "together"
    assert s.active_provider.base_url == "https://api.together.xyz/v1"
    assert s.active_api_key == "k"
    assert s.resolved_chat_model == "meta-llama/Llama-3.3-70B-Instruct-Turbo"
    assert s.resolved_condenser_model == "Qwen/Qwen2.5-7B-Instruct-Turbo"


def test_openrouter_provider_defaults(monkeypatch):
    s = _settings(monkeypatch, LLM_PROVIDER="openrouter", OPENROUTER_API_KEY="or-k")
    assert s.active_provider.base_url == "https://openrouter.ai/api/v1"
    assert s.active_api_key == "or-k"
    assert s.resolved_chat_model == "deepseek/deepseek-chat"


def test_together_provider_defaults(monkeypatch):
    s = _settings(monkeypatch, LLM_PROVIDER="together", TOGETHER_API_KEY="tg-k")
    assert s.active_provider.base_url == "https://api.together.xyz/v1"
    assert s.resolved_chat_model == "meta-llama/Llama-3.3-70B-Instruct-Turbo"


def test_explicit_model_overrides_provider_default(monkeypatch):
    s = _settings(
        monkeypatch,
        LLM_PROVIDER="together",
        TOGETHER_API_KEY="tg-k",
        CHAT_MODEL="my/custom-model",
    )
    assert s.resolved_chat_model == "my/custom-model"


def test_unknown_provider_raises(monkeypatch):
    s = _settings(monkeypatch, LLM_PROVIDER="bogus", TOGETHER_API_KEY="k")
    with pytest.raises(ValueError, match="Unknown provider"):
        _ = s.active_provider


def test_missing_key_for_selected_provider_raises(monkeypatch):
    s = _settings(monkeypatch, LLM_PROVIDER="openrouter")  # no OPENROUTER_API_KEY
    with pytest.raises(ValueError, match="OPENROUTER_API_KEY"):
        _ = s.active_api_key


def test_prose_lane_defaults_to_the_json_lane(monkeypatch):
    """PROSE_PROVIDER unset => prose is identical to chat. The rollback switch."""
    s = _settings(monkeypatch, TOGETHER_API_KEY="k")
    assert s.prose_provider is None
    assert s.prose_provider_name == "together"
    assert s.resolved_prose_model == s.resolved_chat_model


def test_prose_lane_honors_chat_model_override_when_unset(monkeypatch):
    """An explicit CHAT_MODEL must still drive prose while PROSE_PROVIDER is unset."""
    s = _settings(monkeypatch, TOGETHER_API_KEY="k", CHAT_MODEL="my/custom-model")
    assert s.resolved_prose_model == "my/custom-model"


def test_ollama_prose_provider(monkeypatch):
    s = _settings(monkeypatch, TOGETHER_API_KEY="k", PROSE_PROVIDER="ollama")
    assert s.prose_provider_name == "ollama"
    assert s.provider("ollama").base_url == "http://localhost:11434/v1"
    assert s.resolved_prose_model == "hf.co/ia-espirita/riv-ai-v2-Q4_K_M-GGUF"
    assert s.api_key_for("ollama") == "ollama"  # dummy; SDK rejects empty


def test_prose_model_override(monkeypatch):
    s = _settings(
        monkeypatch,
        TOGETHER_API_KEY="k",
        PROSE_PROVIDER="ollama",
        PROSE_MODEL="some/other-gguf",
    )
    assert s.resolved_prose_model == "some/other-gguf"


def test_ollama_base_url_override(monkeypatch):
    s = _settings(
        monkeypatch,
        TOGETHER_API_KEY="k",
        PROSE_PROVIDER="ollama",
        OLLAMA_BASE_URL="http://192.168.0.9:11434/v1",
    )
    assert s.provider("ollama").base_url == "http://192.168.0.9:11434/v1"


def test_hf_endpoint_requires_a_url(monkeypatch):
    s = _settings(
        monkeypatch, TOGETHER_API_KEY="k", HF_TOKEN="hf-k", PROSE_PROVIDER="hf-endpoint"
    )
    with pytest.raises(ValueError, match="HF_ENDPOINT_URL"):
        _ = s.provider("hf-endpoint")


def test_hf_endpoint_with_url(monkeypatch):
    s = _settings(
        monkeypatch,
        TOGETHER_API_KEY="k",
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
    s = _settings(monkeypatch, TOGETHER_API_KEY="k", PROSE_PROVIDER="bogus")
    with pytest.raises(ValueError, match="Unknown provider"):
        _ = s.provider("bogus")


def test_google_api_key_defaults_to_none_and_reads_env(monkeypatch):
    """`google_api_key` is a single field serving two axes: the Gemini
    embedding API (compare_retrieval.py) and, via the "google" PROVIDERS
    entry, /chat text generation over Gemini's OpenAI-compatible endpoint.
    Reading it must not depend on which axis is active.
    """
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    from src.core.config import Settings

    assert Settings(_env_file=None).google_api_key is None

    monkeypatch.setenv("GOOGLE_API_KEY", "test-google-key")
    assert Settings(_env_file=None).google_api_key == "test-google-key"


def test_google_provider_defaults(monkeypatch):
    s = _settings(monkeypatch, LLM_PROVIDER="google", GOOGLE_API_KEY="g-k")
    assert (
        s.active_provider.base_url
        == "https://generativelanguage.googleapis.com/v1beta/openai/"
    )
    assert s.active_api_key == "g-k"
    assert s.resolved_chat_model == "gemini-3.6-flash"
    assert s.resolved_condenser_model == "gemini-3.1-flash-lite"


def test_google_provider_requires_key(monkeypatch):
    s = _settings(monkeypatch, LLM_PROVIDER="google")  # no GOOGLE_API_KEY
    with pytest.raises(ValueError, match="GOOGLE_API_KEY"):
        _ = s.active_api_key


def test_push_settings_have_safe_defaults():
    from src.core.config import Settings

    s = Settings(_env_file=None)
    # Sem chave configurada o push simplesmente não existe — o dispatch
    # verifica isto e sai, em vez de tentar enviar sem assinar.
    assert s.vapid_public_key == ""
    assert s.vapid_private_key == ""
    assert s.vapid_subject == "mailto:contato@dialogandodoutrina.com.br"
    assert s.push_collection == "push_subscriptions"
    assert s.push_expiry_days == 90
    assert s.push_window_minutes == 15
