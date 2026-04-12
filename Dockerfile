FROM python:3.14-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

COPY pyproject.toml .
COPY .python-version .
COPY src/ src/
# uv needs this
RUN touch README.md

RUN uv sync --no-dev --no-cache

ENV PATH="/app/.venv/bin:$PATH"
# for caching
RUN aiolocust --help

ENTRYPOINT ["aiolocust"]
