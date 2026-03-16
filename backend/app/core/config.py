from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "postgresql+psycopg://threat:threat@db:5432/threatintel"
    db_startup_timeout_seconds: int = 60
    db_startup_retry_interval_seconds: float = 2.0
    redis_url: str = "redis://redis:6379/0"
    model_path: str = "/app/models/model.joblib"
    secret_key: str = "supersecret-dev-key"
    classifier_mode: str = "sklearn"
    llm_api_base: str = "http://llm:8000/v1"
    llm_api_key: str = "EMPTY"
    llm_model_name: str = "Qwen/Qwen2.5-14B-Instruct-AWQ"
    llm_timeout_seconds: int = 45
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 480
    api_key_pepper: str = "ps13-pepper"
    allow_plain_api_keys: bool = True
    dedup_similarity_threshold: float = 0.95
    dedup_scan_limit: int = 80
    embedding_mode: str = "semantic"  # semantic|hash
    embedding_model_name: str = "sentence-transformers/all-MiniLM-L6-v2"
    anchor_interval: int = 50
    source_reliability_default: float = 60.0
    live_poll_scheduler_seconds: int = 60
    federation_scheduler_seconds: int = 300
    live_feed_request_timeout_seconds: int = 60

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
        case_sensitive=False,
    )


settings = Settings()
