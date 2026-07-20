from typing import NamedTuple

from pydantic_settings import BaseSettings, SettingsConfigDict


class ProviderConfig(NamedTuple):
    base_url: str
    api_key_field: str
    default_chat_model: str
    default_condenser_model: str


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
        "meta-llama/Llama-3.1-8B-Instruct-Turbo",
    ),
}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    llm_provider: str = "groq"
    groq_api_key: str | None = None
    openrouter_api_key: str | None = None
    together_api_key: str | None = None
    hf_token: str | None = None

    # Optional per-model overrides; unset → the active provider's default.
    chat_model: str | None = None
    condenser_model: str | None = None
    structured_output: bool = True

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

    @property
    def active_provider(self) -> ProviderConfig:
        try:
            return PROVIDERS[self.llm_provider]
        except KeyError:
            raise ValueError(
                f"Unknown LLM_PROVIDER {self.llm_provider!r}; "
                f"valid options: {', '.join(PROVIDERS)}"
            )

    @property
    def active_api_key(self) -> str:
        field = self.active_provider.api_key_field
        key = getattr(self, field)
        if not key:
            raise ValueError(
                f"LLM_PROVIDER={self.llm_provider!r} requires "
                f"{field.upper()} to be set in the environment/.env"
            )
        return key

    @property
    def resolved_chat_model(self) -> str:
        return self.chat_model or self.active_provider.default_chat_model

    @property
    def resolved_condenser_model(self) -> str:
        return self.condenser_model or self.active_provider.default_condenser_model


settings = Settings()
