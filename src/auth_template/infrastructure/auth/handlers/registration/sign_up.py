from uuid import UUID

from auth_template.application.dto.user.credentials import CredentialsDTO
from auth_template.application.dto.user.user import User
from auth_template.application.errors import UserAlreadyExistsError
from auth_template.application.ports.committer import Committer
from auth_template.application.ports.id_generator import IdGenerator
from auth_template.application.ports.security.password_hasher import PasswordHasher
from auth_template.application.ports.user.reader import UserReader
from auth_template.application.ports.user.saver import UserSaver


class SignUpHandler:
    def __init__(
        self,
        reader: UserReader,
        saver: UserSaver,
        hasher: PasswordHasher,
        ids: IdGenerator,
        committer: Committer,
    ) -> None:
        self._reader = reader
        self._saver = saver
        self._hasher = hasher
        self._ids = ids
        self._committer = committer

    async def __call__(self, dto: CredentialsDTO) -> UUID:
        email = dto.email.strip().casefold()
        existing_user = await self._reader.get_by_email(email)
        if existing_user.id is not None:
            raise UserAlreadyExistsError
        password_hash = await self._hasher.hash(dto.password)
        user_id = self._ids()
        user = User(id=user_id, email=email, password_hash=password_hash)
        await self._saver.save(user)
        await self._committer.commit()
        return user_id
