from uuid import UUID

from sqlalchemy import insert, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from auth_template.application.dto.security.refresh_token import RefreshToken
from auth_template.application.dto.session.auth_session import AuthSession
from auth_template.infrastructure.models import AuthSessionModel, RefreshTokenModel


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
