from dataclasses import dataclass, field
from datetime import datetime, timedelta
from uuid import UUID


@dataclass(frozen=True, slots=True, kw_only=True)
class User:
    id: UUID
    email: str
    password_hash: str = field(repr=False)
    is_active: bool = True


@dataclass(frozen=True, slots=True, kw_only=True)
class AuthSession:
    id: UUID
    user_id: UUID
    expires_at: datetime
    is_revoked: bool = False


@dataclass(frozen=True, slots=True, kw_only=True)
class RefreshToken:
    session_id: UUID
    digest: str = field(repr=False)
    is_used: bool = False


@dataclass(frozen=True, slots=True, kw_only=True)
class CredentialsDTO:
    email: str
    password: str = field(repr=False)


@dataclass(frozen=True, slots=True, kw_only=True)
class ChangePasswordDTO:
    user_id: UUID
    current_password: str = field(repr=False)
    new_password: str = field(repr=False)


@dataclass(frozen=True, slots=True, kw_only=True)
class Principal:
    user_id: UUID
    session_id: UUID


@dataclass(frozen=True, slots=True, kw_only=True)
class TokenPairDTO:
    access_token: str = field(repr=False)
    refresh_token: str = field(repr=False)
    expires_in: int
    refresh_expires_in: int


@dataclass(frozen=True, slots=True, kw_only=True)
class AuthPolicy:
    access_ttl: timedelta
    session_ttl: timedelta
