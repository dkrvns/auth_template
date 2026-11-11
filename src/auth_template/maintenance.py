"""Delete expired sessions and their refresh history; schedule this command daily."""

import asyncio

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import create_async_engine

from auth_template.config import Config
from auth_template.infrastructure.clock import utc_now
from auth_template.infrastructure.db.models import AuthSessionModel


async def purge_expired_sessions() -> None:
    config = Config()
    engine = create_async_engine(config.database.dsn.get_secret_value())
    try:
        async with engine.begin() as connection:
            await connection.execute(
                delete(AuthSessionModel).where(AuthSessionModel.expires_at <= utc_now())
            )
    finally:
        await engine.dispose()


if __name__ == '__main__':
    asyncio.run(purge_expired_sessions())
