from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    anthropic_api_key: str
    embedding_model: str = "paraphrase-multilingual-mpnet-base-v2"
    chat_model: str = "claude-haiku-4-5"
    condenser_model: str = "claude-haiku-4-5"
    top_k: int = 5
    max_distance: float = 1.2
    max_history_turns: int = 10
    chroma_path: str = "data/embeddings/"
    chroma_collection: str = "kardec_docs"
    json_dir: str = "data/json_files"


settings = Settings()
