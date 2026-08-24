FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    NAKUPY_DATA_DIR=/data \
    NAKUPY_PORT=8000

WORKDIR /app

# curl je tu kvuli HEALTHCHECK nize
RUN apt-get update \
 && apt-get install -y --no-install-recommends curl \
 && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app

RUN useradd --system --create-home --uid 10001 nakupy \
 && mkdir -p /data \
 && chown -R nakupy:nakupy /data /app
USER nakupy

VOLUME ["/data"]
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD curl -fsS "http://127.0.0.1:${NAKUPY_PORT}/zdravi" || exit 1

CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port ${NAKUPY_PORT} --proxy-headers --forwarded-allow-ips='*'"]
