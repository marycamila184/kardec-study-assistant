from typing import NamedTuple

from pydantic_settings import BaseSettings, SettingsConfigDict


class ProviderConfig(NamedTuple):
    base_url: str
    api_key_field: str
    default_chat_model: str
    default_condenser_model: str
    # Name of a Settings field that overrides base_url when set. Used by
    # providers whose URL is per-machine (ollama) or per-deployment (hf-endpoint).
    base_url_field: str | None = None


_RIV_AI = "hf.co/ia-espirita/riv-ai-v2-Q4_K_M-GGUF"

PROVIDERS: dict[str, ProviderConfig] = {
    "groq": ProviderConfig(
        "https://api.groq.com/openai/v1",
        "groq_api_key",
        "llama-3.3-70b-versatile",
        "llama-3.1-8b-instant",
    ),
    "openrouter": ProviderConfig(
        "https://openrouter.ai/api/v1",
        "openrouter_api_key",
        "deepseek/deepseek-chat",
        "meta-llama/llama-3.1-8b-instruct",
    ),
    "together": ProviderConfig(
        "https://api.together.xyz/v1",
        "together_api_key",
        "deepseek-ai/DeepSeek-V3",
        # Not a Llama 3.1 8B: Together serves no small Llama serverless. Every
        # variant (with or without the "Meta-" prefix, Lite, 3.2-3B) returns
        # "Unable to access non-serverless model" and needs a dedicated
        # endpoint. Verified serverless 2026-07-25; the failure surfaces as
        # every small-LLM agent breaking while chat works fine.
        "Qwen/Qwen2.5-7B-Instruct-Turbo",
    ),
    # Prose-lane providers. Both serve riv-ai-v2 over an OpenAI-compatible /v1;
    # they differ only in where that endpoint lives.
    "ollama": ProviderConfig(
        "http://localhost:11434/v1",
        "ollama_api_key",
        _RIV_AI,
        _RIV_AI,
        "ollama_base_url",
    ),
    "hf-endpoint": ProviderConfig(
        "",  # no default; HF_ENDPOINT_URL is required
        "hf_token",
        _RIV_AI,
        _RIV_AI,
        "hf_endpoint_url",
    ),
}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    llm_provider: str = "groq"
    groq_api_key: str | None = None
    openrouter_api_key: str | None = None
    together_api_key: str | None = None
    hf_token: str | None = None

    # Embedding lane, not a text-generation provider: the Gemini embedding API
    # is not OpenAI-compatible and does not belong in PROVIDERS.
    google_api_key: str | None = None

    # Optional per-model overrides; unset → the active provider's default.
    chat_model: str | None = None
    condenser_model: str | None = None
    structured_output: bool = True

    # Prose lane. Unset => prose uses the same provider and model as everything
    # else, i.e. exactly today's behavior.
    prose_provider: str | None = None
    prose_model: str | None = None

    ollama_api_key: str = "ollama"  # dummy: the OpenAI SDK rejects an empty key
    ollama_base_url: str = "http://localhost:11434/v1"
    hf_endpoint_url: str | None = None

    # Which retrieved chunks become source chips on the prose lane.
    #
    # The cut is RELATIVE: keep chunks within `source_relative_margin` of the
    # best chunk for that answer. Measured 2026-07-25 over 15 questions on both
    # lanes — an absolute cut cannot work, because the similarity level tracks
    # the question's vocabulary rather than passage relevance (the worst chunk
    # for "o que é o perispírito?" scored 0.744, the best for "o que a doutrina
    # diz sobre o perdão?" scored 0.740). At 0.35 all 75 chunks survived on both
    # lanes, i.e. the filter was inert. Within one question the elbow is sharp
    # (mean step 0.092), and 0.10 yields ~2.7 chips per answer.
    source_relative_margin: float = 0.10
    source_max_count: int = 3
    # Absolute floor, not the primary cut: the margin only compares chunks to
    # each other, so a uniformly bad retrieval would keep all of them.
    source_min_similarity: float = 0.35

    embedding_model: str = "BAAI/bge-m3"
    top_k: int = 5
    max_distance: float = 0.55
    max_history_turns: int = 10
    chroma_path: str = "data/embeddings/"
    chroma_collection: str = "kardec_docs"
    json_dir: str = "data/json_files"
    paths_dir: str = "data/paths"
    cors_allowed_origins: str = "http://localhost:5173"

    @property
    def cors_allowed_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_allowed_origins.split(",") if o.strip()]

    def provider(self, name: str | None = None) -> ProviderConfig:
        """Resolves a provider by name, applying its env base-URL override.
        `name=None` means the active JSON-lane provider."""
        name = name or self.llm_provider
        try:
            cfg = PROVIDERS[name]
        except KeyError:
            raise ValueError(
                f"Unknown provider {name!r}; valid options: {', '.join(PROVIDERS)}"
            )
        if cfg.base_url_field:
            override = getattr(self, cfg.base_url_field)
            if override:
                cfg = cfg._replace(base_url=override)
            elif not cfg.base_url:
                raise ValueError(
                    f"provider {name!r} requires "
                    f"{cfg.base_url_field.upper()} to be set in the environment/.env"
                )
        return cfg

    def api_key_for(self, name: str) -> str:
        field = self.provider(name).api_key_field
        key = getattr(self, field)
        if not key:
            raise ValueError(
                f"provider {name!r} requires "
                f"{field.upper()} to be set in the environment/.env"
            )
        return key

    @property
    def active_provider(self) -> ProviderConfig:
        return self.provider()

    @property
    def active_api_key(self) -> str:
        return self.api_key_for(self.llm_provider)

    @property
    def prose_provider_name(self) -> str:
        return self.prose_provider or self.llm_provider

    @property
    def resolved_chat_model(self) -> str:
        return self.chat_model or self.active_provider.default_chat_model

    @property
    def resolved_condenser_model(self) -> str:
        return self.condenser_model or self.active_provider.default_condenser_model

    @property
    def resolved_prose_model(self) -> str:
        # While the prose lane is off, prose must resolve exactly as chat does —
        # including an explicit CHAT_MODEL override.
        if self.prose_provider is None:
            return self.resolved_chat_model
        return self.prose_model or self.provider(self.prose_provider).default_chat_model


settings = Settings()
