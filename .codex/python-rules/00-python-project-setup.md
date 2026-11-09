# Environment and tooling

Applies to every Python project.

## Python and dependencies

- Target Python 3.14: set `requires-python = ">=3.14"` in `pyproject.toml` and `3.14` in `.python-version`. Do not add compatibility with older versions.
- Use uv exclusively. Do not introduce Poetry, pip, pip-tools, pipenv, requirements.txt, setup.py or poetry.lock; propose migration if they already exist.
- Create applications with `uv init --app --python 3.14 <name>` and packages with `uv init --package --python 3.14 <name>`.
- Install Python with `uv python install 3.14`; manage packages with `uv add/remove`, development tools with `uv add --dev`, and lockfiles with `uv lock` or `uv lock --upgrade-package <pkg>`.
- Never edit dependency lists manually; keep pyproject.toml and uv.lock synchronized. Commit uv.lock and .python-version; ignore .venv/.
- Use `uv sync` locally and `uv sync --locked` in CI/Docker. Run commands through `uv run <command>` and one-off tools through `uvx <tool>`; do not manually activate virtual environments.
- Keep ruff, pytest, pytest-asyncio, faker, mypy and other development tools in `[dependency-groups] dev`, not runtime dependencies.
- Specify extras explicitly, e.g. `uv add "sqlalchemy[asyncio]"`, `uv add "psycopg[binary]"`, `uv add "fastapi[standard]"`. Async SQLAlchemy on Python 3.14 needs greenlet from its asyncio extra.

## Configuration

Keep all tool configuration in pyproject.toml; do not introduce .ruff.toml, setup.cfg, pytest.ini or tox.ini. Baseline:

```toml
[project]
name = "<project-name>"
version = "0.1.0"
requires-python = ">=3.14"
dependencies = []

[dependency-groups]
dev = ["ruff", "pytest", "pytest-asyncio", "faker"]

[tool.ruff]
target-version = "py314"
line-length = 88
src = ["src", "tests"]

[tool.ruff.lint]
select = ["E", "W", "F", "I", "B", "C4", "UP", "SIM", "RUF", "ASYNC", "PT"]

[tool.ruff.lint.isort]
known-first-party = ["<package>"]

[tool.ruff.format]
quote-style = "single"
line-ending = "lf"

[tool.pytest]
testpaths = ["tests"]
asyncio_mode = "auto"
asyncio_default_fixture_loop_scope = "session"
asyncio_default_test_loop_scope = "session"
```

- Use pytest 9+ native `[tool.pytest]`, not `[tool.pytest.ini_options]`.
- Use one session event loop for session-scoped asynchronous resources.
- Explain global ruff ignores in a comment; use `# noqa: <code>` for individual lines. Exclude generated protobuf code and migrations through `extend-exclude`.
- Read settings from environment variables through pydantic-settings/models or os.environ; use .env for local development. Commit a complete secret-free .env.example, never .env.
- Do not hardcode hosts, ports, passwords or DSNs in application code.

## Required completion checks

```bash
uv run ruff format .
uv run ruff check --fix .
uv run pytest
```

The task is not complete until all three checks pass.

## Docker

```dockerfile
FROM python:3.14-slim
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never
WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-dev --no-install-project

COPY . .
RUN uv sync --locked --no-dev

CMD ["uv", "run", "--no-dev", "python", "-m", "<package>"]
```

- Cache dependencies with `--no-install-project` before copying source code.
- Run local infrastructure through Docker Compose; use separate services/databases for tests.
- README must explain the project, `uv sync`, infrastructure startup, migrations, application startup and tests, using `uv run` for project commands.
