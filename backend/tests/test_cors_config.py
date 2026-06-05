import logging
from unittest.mock import patch

from _pytest.logging import LogCaptureFixture

from app.core.config import Settings


class TestCorsSettings:
    def test_default_empty_list(self) -> None:
        """Fresh deployment (no env) starts with cors_origins=[]."""
        s = Settings()
        assert s.cors_origins == []

    def test_comma_separated_parsing(self) -> None:
        s = Settings(
            cors_origins="https://app.example.com,https://admin.example.com"  # type: ignore[arg-type]
        )
        assert s.cors_origins == [
            "https://app.example.com",
            "https://admin.example.com",
        ]

    def test_single_origin(self) -> None:
        s = Settings(cors_origins="https://app.example.com")  # type: ignore[arg-type]
        assert s.cors_origins == ["https://app.example.com"]

    def test_whitespace_stripping(self) -> None:
        s = Settings(
            cors_origins=" https://app.example.com , https://admin.example.com "  # type: ignore[arg-type]
        )
        assert s.cors_origins == [
            "https://app.example.com",
            "https://admin.example.com",
        ]

    def test_empty_string_yields_empty_list(self) -> None:
        s = Settings(cors_origins="")  # type: ignore[arg-type]
        assert s.cors_origins == []

    def test_whitespace_only_yields_empty_list(self) -> None:
        s = Settings(cors_origins="   ")  # type: ignore[arg-type]
        assert s.cors_origins == []


class TestStartupWarning:
    def test_warns_when_cors_empty_and_signup_enabled(
        self,
        caplog: LogCaptureFixture,
    ) -> None:
        """Startup log warns when cors_origins=[] AND signup_enabled=True."""
        with caplog.at_level(logging.WARNING):
            from app.main import create_app

            with patch("app.main.settings.cors_origins", []):
                with patch("app.main.settings.signup_enabled", True):
                    create_app()
        assert any(
            "cors_origins" in r.message.lower() for r in caplog.records
        )

    def test_no_warning_when_signup_disabled(
        self,
        caplog: LogCaptureFixture,
    ) -> None:
        """No warning when signup_enabled=False, even with empty cors_origins."""
        with caplog.at_level(logging.WARNING):
            from app.main import create_app

            with patch("app.main.settings.cors_origins", []):
                with patch("app.main.settings.signup_enabled", False):
                    create_app()
        assert not any(
            "cors_origins" in r.message.lower() for r in caplog.records
        )

    def test_no_warning_when_cors_non_empty(
        self,
        caplog: LogCaptureFixture,
    ) -> None:
        """No warning when cors_origins is non-empty."""
        with caplog.at_level(logging.WARNING):
            from app.main import create_app

            with patch("app.main.settings.cors_origins", ["https://example.com"]):
                with patch("app.main.settings.signup_enabled", True):
                    create_app()
        assert not any(
            "cors_origins" in r.message.lower() for r in caplog.records
        )
