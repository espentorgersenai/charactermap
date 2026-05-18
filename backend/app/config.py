from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+asyncpg://charactermap:charactermap@localhost:5432/charactermap"
    redis_url: str = "redis://localhost:6379/0"

    anthropic_api_key: str = ""
    openai_api_key: str = ""
    google_api_key: str = ""
    # Gemini via Vertex AI uses ADC instead of an API key (some orgs disallow
    # API keys). If google_cloud_project is set, GeminiClient routes through
    # Vertex AI; otherwise falls back to AI Studio + api key.
    google_cloud_project: str = ""
    google_cloud_location: str = "us-central1"
    tmdb_api_key: str = ""

    resend_api_key: str = ""
    email_from: str = "charactermap@torgersen.ai"

    turnstile_site_key: str = ""
    turnstile_secret_key: str = ""

    daily_cost_limit_usd: float = 5.00
    artifact_storage_path: str = "/var/lib/charactermap/artifacts"
    artifact_signing_key: str = "change-me-in-production"
    artifact_retention_days: int = 30
    image_cache_path: str = "/var/lib/charactermap/image_cache"

    environment: str = "development"
    base_url: str = "http://localhost:8201"


settings = Settings()
