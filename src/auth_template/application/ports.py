from datetime import datetime
from typing import Protocol
from uuid import UUID

from auth_template.application.dto import AuthSession, Principal, RefreshToken, User


class UserReader(Protocol):
    async def get_by_email(self, email: str) -> User | None: ...

    async def get_by_id(self, user_id: UUID, *, lock: bool = False) -> User | None: ...


class UserSaver(Protocol):
    async def save(self, user: User) -> None: ...


class UserUpdater(Protocol):
    async def set_password(self, user_id: UUID, password_hash: str) -> None: ...


class SessionRepository(Protocol):
    async def save(self, session: AuthSession, token: RefreshToken) -> None: ...

    async def get(
        self, session_id: UUID, *, lock: bool = False
    ) -> AuthSession | None: ...

    async def find_token(self, digest: str) -> RefreshToken | None: ...

    async def rotate(self, old_digest: str, token: RefreshToken) -> None: ...

    async def revoke(self, session_id: UUID) -> None: ...

    async def revoke_for_user(self, user_id: UUID) -> None: ...


class Committer(Protocol):
    async def commit(self) -> None: ...


class PasswordHasher(Protocol):
    async def hash(self, password: str) -> str: ...

    async def verify(self, password: str, password_hash: str | None) -> bool: ...


class AccessTokenCodec(Protocol):
    def encode(
        self, principal: Principal, now: datetime, expires_at: datetime
    ) -> str: ...

    def decode(self, token: str) -> Principal: ...


class RefreshTokenGenerator(Protocol):
    def generate(self) -> str: ...

    def digest(self, token: str) -> str: ...


class Clock(Protocol):
    def __call__(self) -> datetime: ...


class IdGenerator(Protocol):
    def __call__(self) -> UUID: ...


class RateLimiter(Protocol):
    async def allow(self, client: str) -> bool: ...
