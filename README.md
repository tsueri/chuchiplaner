# Chuchiplaner

[![CI](https://github.com/tsueri/chuchiplaner/actions/workflows/ci.yml/badge.svg)](https://github.com/tsueri/chuchiplaner/actions/workflows/ci.yml)

Familien-Menuplaner zur Reduktion von Food Waste. Plane deine Wochenmenus basierend auf verfügbaren Zutaten im Kühlschrank.

## Stack

- **Backend**: Python 3.12+ / FastAPI / SQLAlchemy 2.0 / SQLite
- **Frontend**: React 19 / TypeScript / shadcn/ui / Tailwind CSS 4 / Vite
- **Deployment**: Docker Compose (multi-stage build, backup sidecar)

## Prerequisites

- Python 3.12+
- Node.js 24+
- [uv](https://docs.astral.sh/uv/) (Python package manager)
- npm

## Development Setup

### Backend

```bash
cd backend
uv sync                         # install dependencies
uv run alembic upgrade head     # run database migrations
uv run uvicorn app.main:app --reload   # start API on http://localhost:8000
```

### Frontend

In a separate terminal:

```bash
cd frontend
npm install                     # install dependencies
npm run dev                     # start Vite dev server on http://localhost:5173
```

Open `http://localhost:5173` — the Vite dev server proxies `/api` requests to the backend on port 8000.

### Docker Compose (development)

```bash
docker compose -f docker-compose.dev.yml up
```

Runs backend and frontend as separate containers with live-reload and hot module replacement.

## Production Setup

```bash
docker compose up --build
```

Builds a single Python container (multi-stage Dockerfile: builds the React frontend, copies the static bundle into the FastAPI app), then runs database migrations on startup and serves everything on `http://localhost:8000`. The SQLite database is persisted in `./data/` and daily backups are kept in `./backups/` (7-day retention).

To run without the backup sidecar:

```bash
docker compose up app --build
```

## Environment Variables

All settings use the `CHUCHI_` prefix. Copy `.env.example` to `.env` and adjust as needed (`.env` is gitignored).

### App

| Variable | Default | Description |
|---|---|---|
| `CHUCHI_APP_NAME` | `Chuchiplaner` | Application name |
| `CHUCHI_APP_VERSION` | `0.1.0` | Application version |
| `CHUCHI_DATABASE_URL` | `sqlite+aiosqlite:///./chuchiplaner.db` | SQLite database path (SQLAlchemy URL) |
| `CHUCHI_CORS_ORIGINS` | `""` (empty) | Allowed CORS origins (comma-separated). Set to your frontend origin(s) in production, e.g. `https://app.example.com`. For local dev: `http://localhost:5173`. |
| `CHUCHI_SIGNUP_ENABLED` | `true` | Whether new users can register |
| `CHUCHI_ADMIN_SIGNUP_CODE` | `""` | If non-empty, registration requires a valid household invite code |

### Session cookie

| Variable | Default | Description |
|---|---|---|
| `CHUCHI_COOKIE_SECURE` | `false` | Set to `true` behind HTTPS so cookies get the `Secure` flag |
| `CHUCHI_COOKIE_SAMESITE` | `strict` | SameSite cookie attribute (`strict`, `lax`, or `none`) |
| `CHUCHI_COOKIE_MAX_AGE_SECONDS` | `604800` | Session duration in seconds (default: 7 days) |
| `CHUCHI_COOKIE_HTTPONLY` | `true` | HttpOnly flag (inaccessible to JavaScript) |
| `CHUCHI_COOKIE_NAME` | `session_token` | Cookie name |

### Reverse proxy / HTTPS

| Variable | Default | Description |
|---|---|---|
| `CHUCHI_TRUST_PROXY_HEADERS` | `false` | Set to `true` to read the real client IP from `X-Forwarded-For` for rate limiting |
| `FORWARDED_ALLOW_IPS` | `127.0.0.1` | (uvicorn) IPs trusted to set `X-Forwarded-*` headers. Use `172.16.0.0/12` for Docker networks, or `*` if the proxy is on the same host |

When deploying behind a reverse proxy (nginx, Caddy, Traefik) with HTTPS, set these three variables as a minimum:

```bash
CHUCHI_COOKIE_SECURE=true
CHUCHI_TRUST_PROXY_HEADERS=true
FORWARDED_ALLOW_IPS=172.16.0.0/12   # or * for same-host proxy
```

### Backup sidecar (Docker Compose only)

| Variable | Default | Description |
|---|---|---|
| `CHUCHI_DB_PATH` | `/data/chuchiplaner.db` | Path to the SQLite database |
| `CHUCHI_BACKUP_DIR` | `/backups` | Backup output directory |
| `CHUCHI_BACKUP_RETENTION` | `7` | Days to retain backups |
| `CHUCHI_BACKUP_INTERVAL` | `86400` | Seconds between backups (default: daily) |

## Testing, Linting & Type Checking

### Backend

```bash
cd backend
uv run pytest -v          # run tests
uv run ruff check .       # lint
uv run mypy app           # type check
```

### Frontend

```bash
cd frontend
npm run lint              # ESLint
npm run typecheck         # TypeScript type check
```
