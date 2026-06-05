from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "Chuchiplaner"
    app_version: str = "0.1.0"
    database_url: str = "sqlite+aiosqlite:///./chuchiplaner.db"
    cors_origins: list[str] = ["http://localhost:5173"]
    signup_enabled: bool = True
    admin_signup_code: str = ""
    csp: str = (
        "default-src 'self'; "
        "img-src 'self' https:; "
        "style-src 'self' 'unsafe-inline'; "
        "script-src 'self'; "
        "connect-src 'self'; "
        "frame-ancestors 'none'; "
        "base-uri 'self'; "
        "form-action 'self'"
    )

    model_config = {"env_prefix": "CHUCHI_"}


settings = Settings()
