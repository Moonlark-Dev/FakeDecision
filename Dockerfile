# syntax=docker/dockerfile:1.7
FROM node:22-slim AS web
WORKDIR /app
RUN npm install --global pnpm@9
COPY frontend/package.json frontend/pnpm-lock.yaml ./frontend/
RUN cd frontend && pnpm install --frozen-lockfile
COPY backend/fake_decision ./backend/fake_decision
COPY frontend ./frontend
RUN cd frontend && pnpm build

FROM python:3.12-slim AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/backend \
    FAKE_DECISION_HOST=0.0.0.0 \
    FAKE_DECISION_PORT=8790 \
    FAKE_DECISION_DATA_DIR=/data
WORKDIR /app
COPY backend/requirements.txt /app/backend/requirements.txt
RUN pip install --no-cache-dir -r /app/backend/requirements.txt
COPY backend/fake_decision /app/backend/fake_decision
COPY --from=web /app/backend/fake_decision/web/dist /app/backend/fake_decision/web/dist
RUN useradd --create-home --uid 10001 fakedecision \
    && mkdir -p /data \
    && chown -R fakedecision:fakedecision /data /app
USER fakedecision
EXPOSE 8790
VOLUME ["/data"]
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8790/healthz', timeout=3)"
CMD ["python", "-m", "fake_decision", "--host", "0.0.0.0", "--port", "8790", "--data-dir", "/data"]
