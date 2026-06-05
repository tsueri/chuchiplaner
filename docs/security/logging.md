# Logging policy

## Forbidden log data

The following categories must **never** appear in application log output:

1. **Cookie values** — cookie dicts, individual cookie names/values (e.g. `session_token=...`). The cookie *name* is configurable via `CHUCHI_COOKIE_NAME` and must not be treated as a safe literal.
2. **`set-cookie` headers** — response headers that set authentication cookies. These carry the same tokens as item 1.
3. **Auth-route request bodies** — any field of `/api/auth/register`, `/api/auth/login`, `/api/auth/password`, or similar auth endpoints. This includes `password` (plaintext or otherwise), `invite_code`, and `username`.
4. **Password field at any level** — anywhere a `password` field could appear in a nested or flattened request body.

## Session middleware log shape

The session middleware (`SessionMiddleware` in `backend/app/core/middleware.py`) emits exactly **one log line per request**:

```
<METHOD> <path> <status_code> <duration_ms>ms
```

Example: `GET /api/auth/me 200 1ms`

No request cookies, no response headers, and no request body are included.

## Self-check for contributors

When adding logging to any route or middleware:

- Does the log message contain a cookie name or value?
- Does it echo a `set-cookie` header?
- Does it print fields from an auth endpoint's request body?
- Does a `password` field appear anywhere in the logged data?

If any answer is yes, the log call must be revised before merge.
