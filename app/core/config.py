"""Application settings loaded from environment variables."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration for the FastAPI service."""

    app_name: str = "Tu Comité API"
    api_v1_prefix: str = "/api/v1"
    cors_origins: list[str] = [
        "http://127.0.0.1:5173",
        "http://localhost:5173",
        "http://127.0.0.1:5174",
        "http://localhost:5174",
        "https://tucomite-admin.web.app",
        "https://tucomite-admin.firebaseapp.com",
        "https://tucomite-frontend.web.app",
        "https://tucomite-frontend.firebaseapp.com",
    ]
    database_url: str = "mysql+pymysql://root:@127.0.0.1:3306/tu_comite?charset=utf8mb4"
    session_secret: str = "tu-comite-dev-session-secret-change-me"
    session_https_only: bool = False
    session_same_site: str = "lax"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


settings = Settings()
