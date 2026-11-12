from uuid import UUID

from auth_template.application.dto.user.sign_up import SignUpDTO
from auth_template.application.dto.user.user import User
from auth_template.application.errors import (
    InvalidRegistrationCodeError,
    UserAlreadyExistsError,
)
from auth_template.application.ports.clock import Clock
from auth_template.application.ports.committer import Committer
from auth_template.application.ports.id_generator import IdGenerator
from auth_template.application.ports.registration.reader import RegistrationCodeReader
from auth_template.application.ports.registration.updater import RegistrationCodeUpdater
from auth_template.application.ports.security.password_hasher import PasswordHasher
from auth_template.application.ports.security.registration_code_codec import (
    RegistrationCodeCodec,
)
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
        codes: RegistrationCodeReader,
        code_updater: RegistrationCodeUpdater,
        codec: RegistrationCodeCodec,
        clock: Clock,
    ) -> None:
        self._reader = reader
        self._saver = saver
        self._hasher = hasher
        self._ids = ids
        self._committer = committer
        self._codes = codes
        self._code_updater = code_updater
        self._codec = codec
        self._clock = clock

    async def __call__(self, dto: SignUpDTO) -> UUID:
        email = dto.email.strip().casefold()
        # The row lock covers validation, consumption and creation in one transaction.
        code = await self._codes.get_by_email(email)
        existing_user = await self._reader.get_by_email(email)
        if existing_user.id is not None:
            raise UserAlreadyExistsError
        if (
            not code.email
            or code.expires_at is None
            or code.expires_at <= self._clock()
            or code.attempts_left <= 0
        ):
            raise InvalidRegistrationCodeError
        if not self._codec.verify(email, dto.code, code.digest):
            await self._code_updater.use_attempt(email)
            # Persist the failed attempt even though the request returns an error.
            await self._committer.commit()
            raise InvalidRegistrationCodeError
        await self._code_updater.invalidate(email, code.digest)
        password_hash = await self._hasher.hash(dto.password)
        user_id = self._ids()
        user = User(id=user_id, email=email, password_hash=password_hash)
        await self._saver.save(user)
        await self._committer.commit()
        return user_id
