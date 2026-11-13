import asyncio

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import create_async_engine

from auth_template.config import Config
from auth_template.infrastructure.db.models import Base


def configure(connection: Connection | None = None) -> None:
    context.configure(
        connection=connection,
        url=Config().database.dsn.get_secret_value() if connection is None else None,
        target_metadata=Base.metadata,
        compare_type=True,
        literal_binds=connection is None,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_online() -> None:
    engine = create_async_engine(
        Config().database.dsn.get_secret_value(), poolclass=pool.NullPool
    )
    try:
        async with engine.connect() as connection:
            await connection.run_sync(configure)
    finally:
        await engine.dispose()


if context.is_offline_mode():
    configure()
else:
    asyncio.run(run_online())
