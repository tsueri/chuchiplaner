from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "Chuchiplaner"
    app_version: str = "0.1.0"
    database_url: str = "sqlite+aiosqlite:///./chuchiplaner.db"
    cors_origins: list[str] = ["http://localhost:5173"]
    signup_enabled: bool = True
    admin_signup_code: str = ""

    model_config = {"env_prefix": "CHUCHI_"}


settings = Settings()
