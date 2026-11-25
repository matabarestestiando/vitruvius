FROM node:22-slim AS portal
WORKDIR /ui
COPY frontend/package*.json ./
RUN npm ci
COPY frontend ./
RUN npm run build
FROM python:3.12-slim
COPY --from=ghcr.io/astral-sh/uv:0.7.5 /uv /usr/local/bin/uv
WORKDIR /srv
COPY pyproject.toml uv.lock ./
ARG DOCUMENTS=0
RUN if [ "$DOCUMENTS" = "1" ]; then uv sync --frozen --no-dev --extra documents; else uv sync --frozen --no-dev; fi
COPY app ./app
COPY --from=portal /ui/dist ./app/static
RUN useradd -u 10001 -M worker && mkdir -p /tmp/huggingface && chown worker:worker /tmp/huggingface
USER worker
ENV PATH="/srv/.venv/bin:$PATH" PYTHONUNBUFFERED=1
CMD ["uvicorn","app.main:app","--host","0.0.0.0","--port","8000","--no-access-log"]
