from auth_template.application.dto.principal import Principal
from auth_template.application.dto.user.user import User
from auth_template.application.errors import InvalidTokenError
from auth_template.application.ports.clock import Clock
from auth_template.application.ports.security.access_token_codec import AccessTokenCodec
from auth_template.application.ports.session.reader import SessionReader
from auth_template.application.ports.user.reader import UserReader


class GetCurrentUserInteractor:
    def __init__(
        self,
        codec: AccessTokenCodec,
        sessions: SessionReader,
        reader: UserReader,
        clock: Clock,
    ) -> None:
        self._codec = codec
        self._sessions = sessions
        self._reader = reader
        self._clock = clock

    async def __call__(self, access_token: str) -> tuple[User, Principal]:
        principal = self._codec.decode(access_token)
        session = await self._sessions.get(principal.session_id)
        if (
            session.id is None
            or session.user_id != principal.user_id
            or session.is_revoked
            or session.expires_at is None
            or session.expires_at <= self._clock()
        ):
            raise InvalidTokenError
        user = await self._reader.get_by_id(principal.user_id)
        if user.id is None or not user.is_active:
            raise InvalidTokenError
        return user, principal
