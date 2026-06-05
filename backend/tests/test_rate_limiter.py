"""Tests for the in-memory rate limiter and auth-route integration."""

import pytest
from httpx import AsyncClient

from app.core.rate_limiter import RateLimiter, _limiter


class FakeClock:
    """A monotonic-clock seam for testing the rate limiter without time.sleep."""

    def __init__(self, start: float = 0.0):
        self._now = start

    def __call__(self) -> float:
        return self._now

    def advance(self, seconds: float) -> None:
        self._now += seconds


# ---------------------------------------------------------------------------
# Helper – reset the global singleton between integration tests
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _reset_rate_limiter() -> None:
    """Reset the global rate-limiter singleton before every test."""
    _limiter.reset()


# ---------------------------------------------------------------------------
# Unit tests – RateLimiter.check()
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_first_request_allowed() -> None:
    """A single request with a fresh key is always allowed."""
    clock = FakeClock(1000.0)
    limiter = RateLimiter(clock=clock)
    result = await limiter.check("test_key", limit=5, window_seconds=60)
    assert result is None


@pytest.mark.asyncio
async def test_multiple_requests_within_limit() -> None:
    """All requests up to the limit are allowed."""
    clock = FakeClock(1000.0)
    limiter = RateLimiter(clock=clock)
    for _ in range(5):
        result = await limiter.check("test_key", limit=5, window_seconds=60)
        assert result is None


@pytest.mark.asyncio
async def test_over_limit_returns_retry_after() -> None:
    """The 6th request within 60 seconds is blocked with a retry-after value."""
    clock = FakeClock(1000.0)
    limiter = RateLimiter(clock=clock)
    for _ in range(5):
        result = await limiter.check("test_key", limit=5, window_seconds=60)
        assert result is None

    result = await limiter.check("test_key", limit=5, window_seconds=60)
    assert result is not None
    assert result > 0


@pytest.mark.asyncio
async def test_token_refill_after_time_passes() -> None:
    """After enough time passes, tokens refill and requests are allowed again."""
    clock = FakeClock(1000.0)
    limiter = RateLimiter(clock=clock)

    # Exhaust the bucket
    for _ in range(5):
        await limiter.check("test_key", limit=5, window_seconds=60)

    # Next request blocked
    result = await limiter.check("test_key", limit=5, window_seconds=60)
    assert result is not None

    # Advance past the refill window
    clock.advance(61)
    result = await limiter.check("test_key", limit=5, window_seconds=60)
    assert result is None


@pytest.mark.asyncio
async def test_independent_keys_have_separate_buckets() -> None:
    """Different keys have independent token buckets."""
    clock = FakeClock(1000.0)
    limiter = RateLimiter(clock=clock)

    # Exhaust key A
    for _ in range(5):
        assert await limiter.check("key_a", limit=5, window_seconds=60) is None
    assert await limiter.check("key_a", limit=5, window_seconds=60) is not None

    # Key B is still fresh
    assert await limiter.check("key_b", limit=5, window_seconds=60) is None


@pytest.mark.asyncio
async def test_composed_identifier_keys_are_independent() -> None:
    """A key that composes IP+username is distinct from IP-only."""
    clock = FakeClock(1000.0)
    limiter = RateLimiter(clock=clock)

    # Exhaust login:user:alice
    for _ in range(5):
        assert (
            await limiter.check("login:user:alice", limit=5, window_seconds=60)
            is None
        )
    assert (
        await limiter.check("login:user:alice", limit=5, window_seconds=60)
        is not None
    )

    # login:ip:10.0.0.1 is still fresh (separate bucket)
    assert await limiter.check("login:ip:10.0.0.1", limit=5, window_seconds=60) is None


@pytest.mark.asyncio
async def test_lazy_eviction_sweeps_stale_entries() -> None:
    """Stale entries (no access in 5 minutes) are evicted during the lazy sweep."""
    clock = FakeClock(1000.0)
    limiter = RateLimiter(clock=clock, sweep_every=3, stale_seconds=300)

    # Create a bucket entry
    await limiter.check("ephemeral", limit=5, window_seconds=60)

    # Advance time past the stale threshold
    clock.advance(301)

    # Trigger enough checks to hit the sweep threshold
    for i in range(3):
        await limiter.check(f"filler:{i}", limit=5, window_seconds=60)

    # The ephemeral key should be gone — fresh bucket on next access
    result = await limiter.check("ephemeral", limit=5, window_seconds=60)
    assert result is None  # treated as new bucket, allowed


@pytest.mark.asyncio
async def test_retry_after_is_roughly_time_until_refill() -> None:
    """blocked requests return a retry-after close to 1 token's refill time."""
    clock = FakeClock(1000.0)
    limiter = RateLimiter(clock=clock)

    # 5 req/min = one token every 12 seconds
    for _ in range(5):
        await limiter.check("key", limit=5, window_seconds=60)

    result = await limiter.check("key", limit=5, window_seconds=60)
    assert result is not None
    # retry-after should be ~12 seconds (time for 1 token to refill)
    assert 10 <= result <= 14


# ---------------------------------------------------------------------------
# Integration tests – HTTP-level rate limiting on auth routes
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_login_rate_limited_by_ip(client: AsyncClient) -> None:
    """6 login attempts from the same IP within 60s → 429 on the 6th."""
    # Register a user first so the requests are valid
    await client.post(
        "/api/auth/register",
        json={"username": "rltest1", "password": "secret123"},
    )

    for i in range(5):
        resp = await client.post(
            "/api/auth/login",
            json={"username": "rltest1", "password": "secret123"},
        )
        assert resp.status_code == 200, f"Request {i} should succeed"

    # 6th request should be rate-limited
    resp = await client.post(
        "/api/auth/login",
        json={"username": "rltest1", "password": "secret123"},
    )
    assert resp.status_code == 429
    assert "Retry-After" in resp.headers


@pytest.mark.asyncio
async def test_login_rate_limited_by_username(client: AsyncClient) -> None:
    """6 login attempts for the same username → 429 (username bucket exhausts)."""
    await client.post(
        "/api/auth/register",
        json={"username": "rltest2", "password": "secret123"},
    )

    for i in range(5):
        resp = await client.post(
            "/api/auth/login",
            json={"username": "rltest2", "password": "secret123"},
        )
        assert resp.status_code == 200, f"Request {i} should succeed"

    resp = await client.post(
        "/api/auth/login",
        json={"username": "rltest2", "password": "secret123"},
    )
    assert resp.status_code == 429


@pytest.mark.asyncio
async def test_register_rate_limited_by_ip(client: AsyncClient) -> None:
    """4 registration attempts from the same IP within 1 hour → 429 on the 4th."""
    # 3 registrations succeed (3/hr limit)
    for i in range(3):
        resp = await client.post(
            "/api/auth/register",
            json={"username": f"rlreg{i}", "password": "secret123"},
        )
        assert resp.status_code == 200, f"Registration {i} should succeed"

    # 4th should be rate-limited
    resp = await client.post(
        "/api/auth/register",
        json={"username": "rlreg99", "password": "secret123"},
    )
    assert resp.status_code == 429


@pytest.mark.asyncio
async def test_password_change_rate_limited_by_ip(client: AsyncClient) -> None:
    """4 password-change attempts from the same IP within 1 hour → 429 on the 4th."""
    # Register and get cookies
    reg_resp = await client.post(
        "/api/auth/register",
        json={"username": "rlpwuser", "password": "secret123"},
    )
    cookies = reg_resp.cookies

    for i in range(3):
        resp = await client.put(
            "/api/auth/password",
            json={"current_password": "secret123", "new_password": f"newpass{i:03}"},
            cookies=cookies,
        )
        # After first change, current_password is no longer "secret123"
        # but rate-limiting checks happen BEFORE the handler, so 3 requests
        # reach the check. We care about the 4th getting 429.
        pass

    # 4th should be rate-limited
    resp = await client.put(
        "/api/auth/password",
        json={"current_password": "secret123", "new_password": "newpass999"},
        cookies=cookies,
    )
    assert resp.status_code == 429


@pytest.mark.asyncio
async def test_x_forwarded_for_not_trusted_by_default(client: AsyncClient) -> None:
    """When trust_proxy_headers is False (default), X-Forwarded-For is ignored."""
    await client.post(
        "/api/auth/register",
        json={"username": "rlfwd1", "password": "secret123"},
    )

    # All requests come from test client IP; X-Forwarded-For is ignored
    for i in range(5):
        resp = await client.post(
            "/api/auth/login",
            json={"username": "rlfwd1", "password": "secret123"},
            headers={"X-Forwarded-For": f"192.168.1.{i}"},
        )
        assert resp.status_code == 200, f"Request {i} should succeed"

    # 6th — blocked because all IPs resolved to the same client IP
    resp = await client.post(
        "/api/auth/login",
        json={"username": "rlfwd1", "password": "secret123"},
        headers={"X-Forwarded-For": "192.168.1.99"},
    )
    assert resp.status_code == 429
