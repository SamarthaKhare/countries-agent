# ── Build stage ────────────────────────────────────────────────────────────
FROM python:3.12-slim AS builder

WORKDIR /build
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt


# ── Runtime stage ──────────────────────────────────────────────────────────
FROM python:3.12-slim

# Non-root user for security
RUN addgroup --system app && adduser --system --group app

WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /install /usr/local

# Copy application source
COPY --chown=app:app agent/    ./agent/
COPY --chown=app:app api/      ./api/
COPY --chown=app:app static/   ./static/
COPY --chown=app:app main.py   .

USER app

EXPOSE 8000

ENV HOST=0.0.0.0
ENV PORT=8000
ENV LOG_LEVEL=info

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/health')"

CMD ["python", "main.py"]
