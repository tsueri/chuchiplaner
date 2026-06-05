from typing import Any, Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings


class CookieConfig(BaseSettings):
    secure: bool = False
    samesite: Literal["strict", "lax", "none"] = "strict"
    max_age_seconds: int = 604800
    httponly: bool = True
    name: str = "session_token"

    model_config = {"env_prefix": "CHUCHI_COOKIE_"}


class Settings(BaseSettings):
    app_name: str = "Chuchiplaner"
    app_version: str = "0.1.0"
    database_url: str = "sqlite+aiosqlite:///./chuchiplaner.db"
    cors_origins: list[str] = []
    signup_enabled: bool = False
    admin_signup_code: str = ""
    csp: str = (
        "default-src 'self'; "
        "img-src 'self' https:; "
        "style-src 'self' 'unsafe-inline'; "
        "script-src 'self' 'sha256-VH1OnQOgBQ3EbKOSckBIAquRRMcgooysHqbNPCrDcC4='; "
        "connect-src 'self'; "
        "frame-ancestors 'none'; "
        "base-uri 'self'; "
        "form-action 'self'"
    )
    cookie: CookieConfig = Field(default_factory=CookieConfig)
    trust_proxy_headers: bool = False

    rate_limit_enabled: bool = True
    rate_limit_login_per_minute: int = 5
    rate_limit_register_per_hour: int = 3
    rate_limit_password_per_hour: int = 3

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
