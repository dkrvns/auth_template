from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from auth_template.application.dto.user.user import User
from auth_template.application.errors import UserAlreadyExistsError
from auth_template.application.ports.user.reader import UserReader
from auth_template.application.ports.user.saver import UserSaver
from auth_template.application.ports.user.updater import UserUpdater
from auth_template.infrastructure.models import UserModel


class UserGateway(UserReader, UserSaver, UserUpdater):
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
