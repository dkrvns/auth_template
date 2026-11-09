from auth_template.application.dto.user.change_password import ChangePasswordDTO
from auth_template.application.errors import (
    InvalidCredentialsError,
    PasswordChangeError,
)
from auth_template.application.ports.committer import Committer
from auth_template.application.ports.security.password_hasher import PasswordHasher
from auth_template.application.ports.session.updater import SessionUpdater
from auth_template.application.ports.user.reader import UserReader
from auth_template.application.ports.user.updater import UserUpdater


class ChangePasswordHandler:
    def __init__(
        self,
        reader: UserReader,
        updater: UserUpdater,
        hasher: PasswordHasher,
        sessions: SessionUpdater,
        committer: Committer,
    ) -> None:
        self._reader = reader
        self._updater = updater
        self._hasher = hasher
        self._sessions = sessions
        self._committer = committer

    async def __call__(self, dto: ChangePasswordDTO) -> None:
        user = await self._reader.get_by_id(dto.user_id, lock=True)
        if user is None or not user.is_active:
            raise InvalidCredentialsError
        if not await self._hasher.verify(dto.current_password, user.password_hash):
            raise InvalidCredentialsError
        if dto.current_password == dto.new_password:
            raise PasswordChangeError
        password_hash = await self._hasher.hash(dto.new_password)
        await self._updater.set_password(user.id, password_hash)
        await self._sessions.revoke_for_user(user.id)
        await self._committer.commit()
