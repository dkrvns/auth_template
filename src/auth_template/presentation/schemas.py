from typing import Annotated, Literal, Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, SecretStr, model_validator

from auth_template.application.dto.security.token_pair import TokenPairDTO
from auth_template.application.dto.user.user import User

type Password = Annotated[
    SecretStr,
    Field(
        min_length=12,
        max_length=128,
        description='Password must contain 12 to 128 characters.',
    ),
]
type RawToken = Annotated[SecretStr, Field(min_length=32, max_length=256)]


class CredentialsRequest(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
        json_schema_extra={
            'examples': [
                {
                    'email': 'learner@example.com',
                    'password': 'Example-password-123!',
                }
            ]
        },
    )
    email: Annotated[EmailStr, Field(max_length=254)]
    password: Password


class RefreshRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    refresh_token: RawToken | None = None


class RegistrationCodeRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    email: Annotated[EmailStr, Field(max_length=254)]


class SignUpRequest(CredentialsRequest):
    model_config = ConfigDict(
        extra='forbid',
        json_schema_extra={
            'examples': [
                {
                    'email': 'learner@example.com',
                    'password': 'Example-password-123!',
                    'code': '123456',
                }
            ]
        },
    )
    code: Annotated[SecretStr, Field(min_length=6, max_length=6)]

    @model_validator(mode='after')
    def validate_code(self) -> Self:
        raw = self.code.get_secret_value()
        if not raw.isascii() or not raw.isdigit():
            raise ValueError('Code must contain six digits')
        return self


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
