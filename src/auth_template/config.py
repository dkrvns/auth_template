from typing import Literal, Self
from urllib.parse import urlsplit

from pydantic import BaseModel, Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class DatabaseConfig(BaseModel):
    dsn: SecretStr
    pool_size: int = Field(default=5, ge=1, le=50)

    @model_validator(mode='after')
    def validate_driver(self) -> Self:
        if not self.dsn.get_secret_value().startswith('postgresql+psycopg://'):
            raise ValueError('Use a postgresql+psycopg DSN')
        return self


class AuthConfig(BaseModel):
    secret: SecretStr
    issuer: str = Field(min_length=1)
    audience: str = Field(min_length=1)
    access_ttl_seconds: int = Field(default=900, ge=30, le=3600)
    session_ttl_seconds: int = Field(default=2592000, ge=3600, le=7776000)
    transport: Literal['bearer', 'cookie'] = 'bearer'
    cookie_secure: bool = True
    allowed_origins: list[str] = Field(default_factory=list)
    requests_per_minute: int = Field(default=20, ge=1, le=1000)

    @model_validator(mode='after')
    def validate_security(self) -> Self:
        secret = self.secret.get_secret_value()
        if len(secret.encode()) < 32 or secret.startswith('CHANGE_ME'):
            raise ValueError('Set a random auth secret of at least 32 bytes')
        if self.transport == 'cookie' and not self.allowed_origins:
            raise ValueError('Cookie transport requires explicit allowed origins')
        for origin in self.allowed_origins:
            parsed = urlsplit(origin)
            if (
                parsed.scheme not in {'http', 'https'}
                or not parsed.hostname
                or parsed.username
                or parsed.password
                or parsed.path
                or parsed.query
                or parsed.fragment
                or '*' in origin
            ):
                raise ValueError('Use explicit origins without trailing slash')
        return self


class HttpConfig(BaseModel):
    host: str
    port: int = Field(ge=1, le=65535)
    concurrency: int = Field(default=100, ge=1, le=1000)


class Config(BaseSettings):
    model_config = SettingsConfigDict(
        env_file='.env', env_nested_delimiter='__', extra='ignore'
    )
    database: DatabaseConfig
    auth: AuthConfig
    http: HttpConfig
