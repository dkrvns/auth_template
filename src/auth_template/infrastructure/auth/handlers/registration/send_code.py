from datetime import timedelta

from auth_template.application.dto.registration.code import RegistrationCode
from auth_template.application.errors import (
    MailDeliveryError,
    RegistrationCodeRateLimitError,
)
from auth_template.application.ports.clock import Clock
from auth_template.application.ports.committer import Committer
from auth_template.application.ports.registration.saver import RegistrationCodeSaver
from auth_template.application.ports.registration.sender import RegistrationCodeSender
from auth_template.application.ports.registration.updater import RegistrationCodeUpdater
from auth_template.application.ports.security.registration_code_codec import (
    RegistrationCodeCodec,
)


class SendRegistrationCodeHandler:
    def __init__(
        self,
        saver: RegistrationCodeSaver,
        updater: RegistrationCodeUpdater,
        sender: RegistrationCodeSender,
        codec: RegistrationCodeCodec,
        clock: Clock,
        committer: Committer,
    ) -> None:
        self._saver = saver
        self._updater = updater
        self._sender = sender
        self._codec = codec
        self._clock = clock
        self._committer = committer

    async def __call__(self, email: str) -> None:
        email = email.strip().casefold()
        raw = self._codec.generate()
        now = self._clock()
        code = RegistrationCode(
            email=email,
            digest=self._codec.digest(email, raw),
            sent_at=now,
            expires_at=now + timedelta(minutes=10),
            attempts_left=5,
        )
        if not await self._saver.save(code):
            raise RegistrationCodeRateLimitError
        # Commit before SMTP: no open DB transaction during an external request.
        await self._committer.commit()
        try:
            await self._sender.send(email, raw)
        except MailDeliveryError:
            await self._updater.invalidate(email, code.digest)
            await self._committer.commit()
            raise
