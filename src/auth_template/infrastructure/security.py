import hashlib
import secrets
from datetime import UTC, datetime
from uuid import UUID

import anyio
import jwt
from pwdlib import PasswordHash

from auth_template.application.dto.principal import Principal
from auth_template.application.errors import InvalidTokenError
from auth_template.config import AuthConfig


def utc_now() -> datetime:
    return datetime.now(UTC)


class ArgonPasswordHasher:
    def __init__(self) -> None:
        self._hasher = PasswordHash.recommended()
        self._limiter = anyio.CapacityLimiter(4)
        self._dummy_hash: str | None = None

    async def initialize(self) -> None:
        self._dummy_hash = await self.hash(secrets.token_urlsafe(32))

    async def hash(self, password: str) -> str:
        return await anyio.to_thread.run_sync(
            self._hasher.hash, password, limiter=self._limiter
        )

    async def verify(self, password: str, password_hash: str | None) -> bool:
        candidate = password_hash or self._dummy_hash
        if candidate is None:
            raise RuntimeError('Password hasher is not initialized')
        valid = await anyio.to_thread.run_sync(
            self._hasher.verify, password, candidate, limiter=self._limiter
        )
        return valid and password_hash is not None


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


class OpaqueRefreshTokenGenerator:
    def generate(self) -> str:
        return secrets.token_urlsafe(48)

    def digest(self, token: str) -> str:
        return hashlib.sha256(token.encode()).hexdigest()
