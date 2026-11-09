from typing import Annotated, Literal, Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, SecretStr

from auth_template.application.dto import TokenPairDTO, User

type Password = Annotated[SecretStr, Field(min_length=12, max_length=128)]
type RawToken = Annotated[SecretStr, Field(min_length=32, max_length=256)]


class CredentialsRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    email: Annotated[EmailStr, Field(max_length=254)]
    password: Password


class RefreshRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    refresh_token: RawToken | None = None


class ChangePasswordRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    current_password: Password
    new_password: Password


class CreatedUserResponse(BaseModel):
    id: UUID


class UserResponse(BaseModel):
    id: UUID
    email: str

    @classmethod
    def from_entity(cls, user: User) -> Self:
        return cls(id=user.id, email=user.email)


class TokenResponse(BaseModel):
    access_token: str | None
    refresh_token: str | None
    token_type: Literal['bearer'] = 'bearer'
    expires_in: int

    @classmethod
    def from_entity(cls, pair: TokenPairDTO, *, cookie: bool) -> Self:
        return cls(
            access_token=None if cookie else pair.access_token,
            refresh_token=None if cookie else pair.refresh_token,
            expires_in=pair.expires_in,
        )
