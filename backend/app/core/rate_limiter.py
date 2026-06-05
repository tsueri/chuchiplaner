"""In-memory token-bucket rate limiter for auth endpoints.

Single uvicorn-worker assumption: the in-memory store is not shared across
workers, which is acceptable for the production deploy topology.
"""

import asyncio
import time
from collections.abc import Callable

from fastapi import HTTPException, Request, status

from app.core.config import settings


class RateLimiter:
    """Token-bucket rate limiter with lazy eviction of stale entries.

    Parameters
    ----------
    clock : callable
        Monotonic-clock callable (injectable for tests; defaults to time.monotonic).
    sweep_every : int
        Run the lazy eviction sweep after this many .check() calls.
    stale_seconds : int
        Entries untouched for longer than this are candidate for eviction.
    """

    def __init__(
        self,
        clock: Callable[[], float] | None = None,
        sweep_every: int = 1000,
        stale_seconds: int = 300,
    ) -> None:
        self._buckets: dict[str, tuple[float, float]] = {}
        self._lock = asyncio.Lock()
        self._clock = clock or time.monotonic
        self._check_count = 0
        self._sweep_every = sweep_every
        self._stale_seconds = stale_seconds

    async def check(
        self, key: str, *, limit: int, window_seconds: int
    ) -> float | None:
        """Check whether *key* is allowed another request.

        Returns ``None`` if the request is allowed, or the number of
        seconds the caller should wait before retrying (``Retry-After``).
        """
        async with self._lock:
            self._check_count += 1
            if self._check_count % self._sweep_every == 0:
                self._sweep()

            now = self._clock()
            tokens, last_refill = self._buckets.get(key, (float(limit), now))

            # Refill tokens proportionally to elapsed time.
            elapsed = now - last_refill
            refill_rate = limit / window_seconds
            tokens = min(float(limit), tokens + elapsed * refill_rate)

            if tokens >= 1.0:
                self._buckets[key] = (tokens - 1.0, now)
                return None

            # Not enough tokens — compute a rough retry-after hint.
            deficit = 1.0 - tokens
            retry_after = deficit / refill_rate
            return max(0.0, retry_after)

    def _sweep(self) -> None:
        now = self._clock()
        stale = [
            k
            for k, (_, last_refill) in self._buckets.items()
            if now - last_refill > self._stale_seconds
        ]
        for k in stale:
            del self._buckets[k]

    def reset(self) -> None:
        """Clear all bucket state (for test isolation)."""
        self._buckets.clear()
        self._check_count = 0


# ---------------------------------------------------------------------------
# Singleton instance used by the dependencies below.
# ---------------------------------------------------------------------------

_limiter = RateLimiter()


# ---------------------------------------------------------------------------
# Rate-limit configuration (overridable via env vars).
# ---------------------------------------------------------------------------

LOGIN_LIMIT = settings.rate_limit_login_per_minute
LOGIN_WINDOW = 60  # seconds

REGISTER_LIMIT = settings.rate_limit_register_per_hour
REGISTER_WINDOW = 3600  # seconds (1 hour)

PASSWORD_LIMIT = settings.rate_limit_password_per_hour
PASSWORD_WINDOW = 3600  # seconds (1 hour)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_client_ip(request: Request) -> str:
    """Return the effective client IP, respecting X-Forwarded-For when configured."""
    if settings.trust_proxy_headers:
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0].strip()
    if request.client:
        return request.client.host
    return "unknown"


async def _check_rate_limit(
    key: str, *, limit: int, window_seconds: int
) -> None:
    """Check the global limiter and raise HTTP 429 on over-limit."""
    if not settings.rate_limit_enabled:
        return

    retry_after = await _limiter.check(key, limit=limit, window_seconds=window_seconds)
    if retry_after is not None:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many requests",
            headers={"Retry-After": str(int(retry_after + 1))},
        )


# ---------------------------------------------------------------------------
# FastAPI Depends() callables — one per auth route.
# ---------------------------------------------------------------------------


async def rate_limit_login(request: Request) -> None:
    """Rate-limit login by IP."""
    ip = _get_client_ip(request)
    await _check_rate_limit(
        f"login:ip:{ip}", limit=LOGIN_LIMIT, window_seconds=LOGIN_WINDOW
    )


async def rate_limit_register(request: Request) -> None:
    """Rate-limit registration by IP."""
    ip = _get_client_ip(request)
    await _check_rate_limit(
        f"register:ip:{ip}", limit=REGISTER_LIMIT, window_seconds=REGISTER_WINDOW
    )


async def rate_limit_password(request: Request) -> None:
    """Rate-limit password changes by IP."""
    ip = _get_client_ip(request)
    await _check_rate_limit(
        f"password:ip:{ip}", limit=PASSWORD_LIMIT, window_seconds=PASSWORD_WINDOW
    )
