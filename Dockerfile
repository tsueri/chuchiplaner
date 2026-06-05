FROM node:24-alpine AS frontend-builder
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build


FROM python:3.12-slim AS backend
WORKDIR /app

COPY backend/pyproject.toml backend/uv.lock* ./
RUN pip install --no-cache-dir uv && uv sync --frozen --no-dev

COPY backend/ ./
COPY --from=frontend-builder /app/frontend/dist ./static

RUN uv run alembic upgrade head

EXPOSE 8000
CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]
