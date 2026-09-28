# syntax=docker/dockerfile:1.6

# ─── Base stage ───────────────────────────────────────────
FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# System deps: ffmpeg cho MoviePy, libpq cho psycopg, fonts cho text rendering, libs cho Playwright
RUN apt-get update && apt-get install -y --no-install-recommends \
        gcc \
        libpq-dev \
        curl \
        ffmpeg \
        imagemagick \
        fonts-dejavu-core \
        fontconfig \
        libnss3 libnspr4 \
        libatk1.0-0 libatk-bridge2.0-0 \
        libcups2 libdrm2 libxkbcommon0 \
        libxcomposite1 libxdamage1 libxfixes3 libxrandr2 \
        libgbm1 libpango-1.0-0 libcairo2 libasound2 \
    && rm -rf /var/lib/apt/lists/*

# ImageMagick policy: cho phép MoviePy ghi file (mặc định bị block từ v6.9.10)
RUN sed -i 's|<policy domain="path" rights="none" pattern="@\*"/>|<!-- relaxed -->|g' \
    /etc/ImageMagick-6/policy.xml || true

COPY requirements.txt ./
RUN pip install --upgrade pip setuptools wheel \
    && pip install --no-cache-dir -r requirements.txt

# ─── Development stage (API) ──────────────────────────────
FROM base AS development

RUN pip install --no-cache-dir watchfiles

COPY . .

EXPOSE 8000
CMD ["uvicorn", "src.main:app", \
     "--host", "0.0.0.0", \
     "--port", "8000", \
     "--reload", \
     "--reload-dir", "/app/src"]

# ─── Worker stage ─────────────────────────────────────────
FROM base AS worker

COPY . .

RUN mkdir -p /app/jobs /app/logs /app/models

CMD ["python", "-m", "src.worker.main"]

# ─── Production stage (API) ───────────────────────────────
FROM base AS production

COPY . .

RUN mkdir -p /app/jobs /app/logs /app/models

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD curl -fsS http://localhost:8000/health || exit 1

CMD ["gunicorn", "src.main:app", \
     "-k", "uvicorn.workers.UvicornWorker", \
     "--bind", "0.0.0.0:8000", \
     "--workers", "4", \
     "--timeout", "120", \
     "--graceful-timeout", "30", \
     "--access-logfile", "-", \
     "--error-logfile", "-"]