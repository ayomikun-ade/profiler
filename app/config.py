from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "sqlite+aiosqlite:///./profiler.db"
    genderize_url: str = "https://api.genderize.io"
    agify_url: str = "https://api.agify.io"
    nationalize_url: str = "https://api.nationalize.io"
    upstream_timeout_seconds: float = 10.0


settings = Settings()
