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

Builds a single Python container (multi-stage Dockerfile: builds the React frontend, copies the static bundle into the FastAPI app, runs migrations), then serves everything on `http://localhost:8000`. The SQLite database is persisted in `./data/` and daily backups are kept in `./backups/` (7-day retention).

To run without the backup sidecar:

```bash
docker compose up app --build
```

## Environment Variables

All backend settings use the `CHUCHI_` prefix. The `.env` file is gitignored.

| Variable | Default | Description |
|---|---|---|
| `CHUCHI_DATABASE_URL` | `sqlite+aiosqlite:///./chuchiplaner.db` | SQLite database path |
| `CHUCHI_CORS_ORIGINS` | `["http://localhost:5173"]` | Allowed CORS origins (JSON list) |

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
