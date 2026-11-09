from datetime import datetime

from auth_template.application.dto.auth_policy import AuthPolicy
from auth_template.application.dto.principal import Principal
from auth_template.application.dto.security.refresh_token import RefreshToken
from auth_template.application.dto.security.token_pair import TokenPairDTO
from auth_template.application.dto.session.auth_session import AuthSession
from auth_template.application.errors import InvalidTokenError
from auth_template.application.ports.security.access_token_codec import AccessTokenCodec
from auth_template.application.ports.security.refresh_token_generator import (
    RefreshTokenGenerator,
)


class TokenIssuer:
    def __init__(
        self,
        codec: AccessTokenCodec,
        generator: RefreshTokenGenerator,
        policy: AuthPolicy,
    ) -> None:
        self._codec = codec
        self._generator = generator
        self._policy = policy

    def issue(
        self, session: AuthSession, now: datetime
    ) -> tuple[TokenPairDTO, RefreshToken]:
        if session.id is None or session.user_id is None or session.expires_at is None:
            raise InvalidTokenError
        raw = self._generator.generate()
        access_expires_at = min(now + self._policy.access_ttl, session.expires_at)
        pair = TokenPairDTO(
            access_token=self._codec.encode(
                Principal(user_id=session.user_id, session_id=session.id),
                now,
                access_expires_at,
            ),
            refresh_token=raw,
            expires_in=int((access_expires_at - now).total_seconds()),
            refresh_expires_in=int((session.expires_at - now).total_seconds()),
        )
        return pair, RefreshToken(
            session_id=session.id, digest=self._generator.digest(raw)
        )
