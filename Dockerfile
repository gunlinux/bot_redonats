FROM python:3.12-slim

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PYTHONUNBUFFERED=1

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

COPY pyproject.toml uv.lock ./
COPY donats/ donats/
COPY donats_getter.py donats_worker.py ./

RUN uv sync --frozen --no-dev

CMD ["uv", "run", "--no-sync", "donats_getter.py"]
