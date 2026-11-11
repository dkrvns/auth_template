from datetime import datetime
from uuid import UUID

import jwt

from auth_template.application.dto.principal import Principal
from auth_template.application.errors import InvalidTokenError
from auth_template.config import AuthConfig


class JwtAccessTokenCodec:
    def __init__(self, config: AuthConfig) -> None:
        self._config = config

    def encode(self, principal: Principal, now: datetime, expires_at: datetime) -> str:
        return jwt.encode(
            {
                'sub': str(principal.user_id),
                'sid': str(principal.session_id),
                'iat': now,
                'nbf': now,
                'exp': expires_at,
                'iss': self._config.issuer,
                'aud': self._config.audience,
                'type': 'access',
            },
            self._config.secret.get_secret_value(),
            algorithm='HS256',
        )

    def decode(self, token: str) -> Principal:
        try:
            payload = jwt.decode(
                token,
                self._config.secret.get_secret_value(),
                algorithms=['HS256'],
                issuer=self._config.issuer,
                audience=self._config.audience,
                options={
                    'require': ['sub', 'sid', 'iat', 'nbf', 'exp', 'iss', 'aud', 'type']
                },
            )
            if payload['type'] != 'access':
                raise InvalidTokenError
            return Principal(
                user_id=UUID(payload['sub']), session_id=UUID(payload['sid'])
            )
        except (jwt.InvalidTokenError, ValueError, TypeError, AttributeError) as exc:
            raise InvalidTokenError from exc
