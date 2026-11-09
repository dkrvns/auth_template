import hashlib
from uuid import UUID

from sqlalchemy import delete, insert, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from auth_template.application.dto import AuthSession, RefreshToken, User
from auth_template.application.errors import UserAlreadyExistsError
from auth_template.application.ports import Clock
from auth_template.config import AuthConfig
from auth_template.infrastructure.models import (
    AuthSessionModel,
    RateLimitModel,
    RefreshTokenModel,
    UserModel,
)


class UserGateway:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_email(self, email: str) -> User | None:
        row = await self._session.scalar(
            select(UserModel).where(UserModel.email == email)
        )
        return self._to_entity(row) if row else None

    async def get_by_id(self, user_id: UUID, *, lock: bool = False) -> User | None:
        query = select(UserModel).where(UserModel.id == user_id)
        if lock:
            query = query.with_for_update().execution_options(populate_existing=True)
        row = await self._session.scalar(query)
        return self._to_entity(row) if row else None

    async def save(self, user: User) -> None:
        query = (
            pg_insert(UserModel)
            .values(
                id=user.id,
                email=user.email,
                password_hash=user.password_hash,
                is_active=user.is_active,
            )
            .on_conflict_do_nothing(index_elements=[UserModel.email])
            .returning(UserModel.id)
        )
        if await self._session.scalar(query) is None:
            raise UserAlreadyExistsError

    async def set_password(self, user_id: UUID, password_hash: str) -> None:
        await self._session.execute(
            update(UserModel)
            .where(UserModel.id == user_id)
            .values(password_hash=password_hash)
        )

    @staticmethod
    def _to_entity(row: UserModel) -> User:
        return User(
            id=row.id,
            email=row.email,
            password_hash=row.password_hash,
            is_active=row.is_active,
        )


class SessionGateway:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save(self, session: AuthSession, token: RefreshToken) -> None:
        await self._session.execute(
            insert(AuthSessionModel).values(
                id=session.id,
                user_id=session.user_id,
                expires_at=session.expires_at,
                is_revoked=session.is_revoked,
            )
        )
        await self._save_token(token)

    async def _save_token(self, token: RefreshToken) -> None:
        await self._session.execute(
            insert(RefreshTokenModel).values(
                session_id=token.session_id, digest=token.digest, is_used=token.is_used
            )
        )

    async def get(self, session_id: UUID, *, lock: bool = False) -> AuthSession | None:
        query = select(AuthSessionModel).where(AuthSessionModel.id == session_id)
        if lock:
            query = query.with_for_update().execution_options(populate_existing=True)
        row = await self._session.scalar(query)
        return (
            AuthSession(
                id=row.id,
                user_id=row.user_id,
                expires_at=row.expires_at,
                is_revoked=row.is_revoked,
            )
            if row
            else None
        )

    async def find_token(self, digest: str) -> RefreshToken | None:
        row = await self._session.scalar(
            select(RefreshTokenModel)
            .where(RefreshTokenModel.digest == digest)
            .execution_options(populate_existing=True)
        )
        return (
            RefreshToken(
                session_id=row.session_id, digest=row.digest, is_used=row.is_used
            )
            if row
            else None
        )

    async def rotate(self, old_digest: str, token: RefreshToken) -> None:
        await self._session.execute(
            update(RefreshTokenModel)
            .where(RefreshTokenModel.digest == old_digest)
            .values(is_used=True)
        )
        await self._save_token(token)

    async def revoke(self, session_id: UUID) -> None:
        await self._session.execute(
            update(AuthSessionModel)
            .where(AuthSessionModel.id == session_id)
            .values(is_revoked=True)
        )

    async def revoke_for_user(self, user_id: UUID) -> None:
        await self._session.execute(
            update(AuthSessionModel)
            .where(AuthSessionModel.user_id == user_id)
            .values(is_revoked=True)
        )


class SqlCommitter:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def commit(self) -> None:
        await self._session.commit()


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
