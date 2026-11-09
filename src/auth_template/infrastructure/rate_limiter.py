import hashlib

from sqlalchemy import delete
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from auth_template.application.ports.clock import Clock
from auth_template.config import AuthConfig
from auth_template.infrastructure.models import RateLimitModel


class PostgresRateLimiter:
    def __init__(
        self,
        sessions: async_sessionmaker[AsyncSession],
        clock: Clock,
        config: AuthConfig,
    ) -> None:
        self._sessions = sessions
        self._clock = clock
        self._limit = config.requests_per_minute

    async def allow(self, client: str) -> bool:
        window = int(self._clock().timestamp()) // 60
        digest = hashlib.sha256(client.encode()).hexdigest()
        query = (
            pg_insert(RateLimitModel)
            .values(client_digest=digest, window=window, requests=1)
            .on_conflict_do_update(
                index_elements=[RateLimitModel.client_digest, RateLimitModel.window],
                set_={'requests': RateLimitModel.requests + 1},
                where=RateLimitModel.requests < self._limit,
            )
            .returning(RateLimitModel.requests)
        )
        async with self._sessions.begin() as session:
            await session.execute(
                delete(RateLimitModel).where(RateLimitModel.window < window - 1)
            )
            count = await session.scalar(query)
        return count is not None
