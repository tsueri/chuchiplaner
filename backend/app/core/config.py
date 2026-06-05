from typing import Any

from pydantic import field_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "Chuchiplaner"
    app_version: str = "0.1.0"
    database_url: str = "sqlite+aiosqlite:///./chuchiplaner.db"
    cors_origins: list[str] = []
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

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, v: Any) -> object:
        if isinstance(v, str):
            if not v.strip():
                return []
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        return v


settings = Settings()
