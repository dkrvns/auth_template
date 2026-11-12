FROM python:3.14-slim AS base
COPY --from=ghcr.io/astral-sh/uv:0.9.5 /uv /uvx /bin/
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never
WORKDIR /app
COPY pyproject.toml uv.lock ./

FROM base AS development
RUN uv sync --locked --no-install-project
COPY . .
RUN uv sync --locked
CMD ["uv", "run", "pytest"]

FROM base AS runtime
RUN uv sync --locked --no-dev --no-install-project
COPY src ./src
COPY migrations ./migrations
COPY alembic.ini README.md ./
RUN uv sync --locked --no-dev && useradd --uid 10001 --create-home app
USER 10001
CMD ["uv", "run", "--no-dev", "python", "-m", "auth_template"]
