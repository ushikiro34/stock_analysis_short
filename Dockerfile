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

# System deps: gcc(pykrx/pandas 컴파일), libxml2(lxml)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc g++ libffi-dev libssl-dev curl \
    libxml2-dev libxslt1-dev \
    && rm -rf /var/lib/apt/lists/*

# matplotlib headless 설정 (pykrx 의존성 — 화면 없이 동작)
ENV MPLBACKEND=Agg

COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ ./backend/
COPY --from=frontend /frontend/dist ./frontend/dist

ENV PORT=8000
CMD ["sh", "-c", "uvicorn backend.api.main:app --host 0.0.0.0 --port ${PORT}"]
