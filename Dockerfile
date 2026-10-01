# syntax=docker/dockerfile:1.7

FROM node:22.23.1-alpine AS frontend-build
WORKDIR /workspace/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.13-slim AS backend-base
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH=/opt/venv/bin:$PATH
RUN python -m venv /opt/venv
WORKDIR /workspace/backend
COPY backend/requirements.lock backend/requirements-dev.lock ./

FROM backend-base AS development
RUN pip install --no-cache-dir --require-hashes -r requirements-dev.lock
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload", "--no-proxy-headers"]

FROM backend-base AS backend-production
RUN pip install --no-cache-dir --require-hashes -r requirements.lock

FROM python:3.13-slim AS production
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH=/opt/venv/bin:$PATH \
    HERMES_STATIC_DIR=/app/static
RUN groupadd --system hermes && useradd --system --gid hermes --home /app hermes
COPY --from=backend-production /opt/venv /opt/venv
WORKDIR /app
COPY --chown=hermes:hermes backend/ ./
COPY --from=frontend-build --chown=hermes:hermes /workspace/frontend/dist/frontend/browser ./static
USER hermes
EXPOSE 8000
CMD ["sh", "-c", "alembic upgrade head && exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --no-proxy-headers"]
