import pytest

from app.core.config import CookieConfig, Settings


def test_cookie_config_defaults() -> None:
    cfg = CookieConfig()
    assert cfg.secure is False
    assert cfg.samesite == "strict"
    assert cfg.max_age_seconds == 604800
    assert cfg.httponly is True
    assert cfg.name == "session_token"


def test_cookie_config_override() -> None:
    cfg = CookieConfig(
        secure=True,
        samesite="lax",
        max_age_seconds=3600,
        httponly=False,
        name="my_token",
    )
    assert cfg.secure is True
    assert cfg.samesite == "lax"
    assert cfg.max_age_seconds == 3600
    assert cfg.httponly is False
    assert cfg.name == "my_token"


def test_settings_cookie_defaults() -> None:
    s = Settings()
    assert s.cookie.secure is False
    assert s.cookie.samesite == "strict"
    assert s.cookie.max_age_seconds == 604800
    assert s.cookie.httponly is True
    assert s.cookie.name == "session_token"


def test_settings_cookie_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CHUCHI_COOKIE_SECURE", "true")
    monkeypatch.setenv("CHUCHI_COOKIE_SAMESITE", "lax")
    monkeypatch.setenv("CHUCHI_COOKIE_MAX_AGE_SECONDS", "3600")
    monkeypatch.setenv("CHUCHI_COOKIE_HTTPONLY", "false")
    monkeypatch.setenv("CHUCHI_COOKIE_NAME", "my_session")

    s = Settings()
    assert s.cookie.secure is True
    assert s.cookie.samesite == "lax"
    assert s.cookie.max_age_seconds == 3600
    assert s.cookie.httponly is False
    assert s.cookie.name == "my_session"


def test_cookie_config_samesite_validation() -> None:
    with pytest.raises(Exception):
        CookieConfig(samesite="invalid")  # type: ignore[arg-type]
