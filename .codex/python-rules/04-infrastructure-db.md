# Infrastructure

Applies to infrastructure/, migrations/ and config.py responsibilities.

## SQLAlchemy 2 ORM models

```python
class UserModel(Base):
    __tablename__ = 'users'

    id: Mapped[UUID] = mapped_column(primary_key=True)
    team_id: Mapped[UUID] = mapped_column(ForeignKey('teams.id'), index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True)
    name: Mapped[str] = mapped_column(String(100))
```

- Use Mapped[...] and mapped_column(...). Follow an existing Column(...) style where already established; do not mix styles within a module.
- Use a shared Base(DeclarativeBase) with MetaData(naming_convention=...) for stable migration constraint names.
- Specify string lengths, indexed ForeignKey fields and explicit nullable `T | None` annotations.
- Import all models in models/__init__.py with __all__ so Alembic discovers them.

## Gateways/repositories

```python
class UserGateway(UserReader, UserSaver):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, user_id: UUID) -> User | None:
        query = select(UserModel).where(UserModel.id == user_id)
        row = await self._session.scalar(query)

        return self._to_entity(row) if row else None

    async def save(self, user: User) -> None:
        await self._session.execute(insert(UserModel).values(...))

    @staticmethod
    def _to_entity(row: UserModel) -> User:
        return User(id=row.id, team_id=row.team_id, email=row.email, name=row.name)
```

- Implement the relevant Protocols; depend only on AsyncSession or the external client.
- Use SQLAlchemy 2 select/insert/update/delete and session.scalar(s)/execute, never legacy session.query.
- Return mapped domain entities through an explicit _to_entity mapper, never ORM instances. Map lists likewise.
- Use Model.flag.is_(False), not `== False`.
- Choose one commit policy consistently: preferably commands commit through UnitOfWork/Committer; simple CRUD may commit inside gateway writes.
- Add soft deletion only when required; all reads must then exclude deleted records and deletions update is_deleted=True.
- Prevent lost updates with atomic conditional writes, row locks or version checks; choose isolation deliberately. Enforce persistent invariants with database constraints, not read-before-write checks alone.
- Avoid N+1 with eager loading/batching; paginate lists and justify indexes using actual query patterns and plans.

## Connections and sessions

- Create create_async_engine and async_sessionmaker(expire_on_commit=False, autoflush=False) once at Scope.APP; use async context-managed per-request sessions at Scope.REQUEST.
- Build DSNs from configuration using sqlalchemy.URL.create(...) or configured fields; do not hardcode them.
- Use one PostgreSQL driver per project: psycopg 3 or asyncpg.

## Alembic migrations

- Model changes require a new revision: `uv run alembic revision --autogenerate -m "<what changed>"`; inspect and edit generated migrations.
- Apply with `uv run alembic upgrade head`; every migration needs a working downgrade.
- Separate data migrations from schema migrations. Exclude the migrations directory from ruff.

## External clients and configuration

- Use one httpx.AsyncClient per application (Scope.APP), with timeouts.
- Bound connection pools and total operation deadlines; retry only transient failures within a capped budget using backoff and jitter. Respect cancellation; add circuit breakers when dependency failures can cascade.
- For repeatable mutations, persist an operation key, payload fingerprint and outcome; atomically claim concurrent duplicates. Reuse the key with external providers; reconcile unknown outcomes before retrying.
- Wrap clients in gateways implementing application ports; translate external errors into application exceptions.
- Do not edit generated protobuf/client code; exclude it from linting.
- Use pydantic models/pydantic-settings, grouped into subsystem models such as DatabaseConfig and HttpConfig under one Config.
- Load values from the environment and pass Config through DI context, never global imports.
