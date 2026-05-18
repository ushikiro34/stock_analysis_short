# ── Stage 1: Frontend build ──────────────────────────────────
FROM node:20-alpine AS frontend
WORKDIR /frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# ── Stage 2: Backend + static ────────────────────────────────
FROM python:3.12-slim
WORKDIR /app

# System deps (pykrx, lxml 등)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc g++ libffi-dev libssl-dev curl \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ ./backend/
COPY --from=frontend /frontend/dist ./frontend/dist

ENV PORT=8000
CMD uvicorn backend.api.main:app --host 0.0.0.0 --port ${PORT}
