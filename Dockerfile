FROM ghcr.io/astral-sh/uv:0.11.30 AS uv

FROM python:3.11-slim AS runtime
COPY --from=uv /uv /uvx /bin/

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PATH="/app/.venv/bin:$PATH" \
    RELAY_DATABASE_URL="sqlite:////data/agent-relay.db"

WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-dev --no-install-project

RUN useradd --create-home --uid 10001 relay \
    && mkdir /data \
    && chown relay:relay /data
COPY --chown=relay:relay *.py dashboard.html SPEC.md README.md ./

USER 10001:10001
EXPOSE 8000
HEALTHCHECK --interval=10s --timeout=3s --start-period=10s --retries=5 \
  CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/ready', timeout=2)"]
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
