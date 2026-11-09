from collections.abc import AsyncIterator
from datetime import timedelta
from uuid import uuid7

from dishka import (
    AnyOf,
    AsyncContainer,
    Provider,
    Scope,
    from_context,
    make_async_container,
    provide,
)
from dishka.integrations.fastapi import FastapiProvider
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from auth_template.application.dto import AuthPolicy
from auth_template.application.ports import (
    AccessTokenCodec,
    Clock,
    Committer,
    IdGenerator,
    PasswordHasher,
    RateLimiter,
    RefreshTokenGenerator,
    SessionRepository,
    UserReader,
    UserSaver,
    UserUpdater,
)
from auth_template.application.use_cases import (
    ChangePasswordCommand,
    GetCurrentUserInteractor,
    LogInCommand,
    LogOutCommand,
    RefreshCommand,
    SignUpCommand,
    TokenIssuer,
)
from auth_template.config import AuthConfig, Config
from auth_template.infrastructure.repositories import (
    PostgresRateLimiter,
    SessionGateway,
    SqlCommitter,
    UserGateway,
)
from auth_template.infrastructure.security import (
    ArgonPasswordHasher,
    JwtAccessTokenCodec,
    OpaqueRefreshTokenGenerator,
    utc_now,
)


class InfrastructureProvider(Provider):
    config = from_context(provides=Config, scope=Scope.APP)

    @provide(scope=Scope.APP)
    def auth_config(self, config: Config) -> AuthConfig:
        return config.auth

    @provide(scope=Scope.APP)
    async def engine(self, config: Config) -> AsyncIterator[AsyncEngine]:
        engine = create_async_engine(
            config.database.dsn.get_secret_value(),
            pool_size=config.database.pool_size,
            max_overflow=0,
            pool_timeout=10,
            pool_pre_ping=True,
            connect_args={
                'connect_timeout': 5,
                'options': '-c statement_timeout=10000',
            },
        )
        try:
            yield engine
        finally:
            await engine.dispose()

    @provide(scope=Scope.APP)
    def sessions(self, engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
        return async_sessionmaker(engine, expire_on_commit=False, autoflush=False)

    @provide(scope=Scope.REQUEST)
    async def session(
        self, sessions: async_sessionmaker[AsyncSession]
    ) -> AsyncIterator[AsyncSession]:
        async with sessions() as session:
            yield session

    @provide(scope=Scope.APP)
    def clock(self) -> Clock:
        return utc_now

    @provide(scope=Scope.APP)
    def ids(self) -> IdGenerator:
        return uuid7

    @provide(scope=Scope.APP)
    def policy(self, config: AuthConfig) -> AuthPolicy:
        return AuthPolicy(
            access_ttl=timedelta(seconds=config.access_ttl_seconds),
            session_ttl=timedelta(seconds=config.session_ttl_seconds),
        )

    @provide(scope=Scope.APP)
    async def hasher(self) -> PasswordHasher:
        hasher = ArgonPasswordHasher()
        await hasher.initialize()
        return hasher

    codec = provide(JwtAccessTokenCodec, scope=Scope.APP, provides=AccessTokenCodec)
    generator = provide(
        OpaqueRefreshTokenGenerator, scope=Scope.APP, provides=RefreshTokenGenerator
    )
    limiter = provide(PostgresRateLimiter, scope=Scope.APP, provides=RateLimiter)
    users = provide(
        UserGateway,
        scope=Scope.REQUEST,
        provides=AnyOf[UserReader, UserSaver, UserUpdater],
    )
    auth_sessions = provide(
        SessionGateway, scope=Scope.REQUEST, provides=SessionRepository
    )
    committer = provide(SqlCommitter, scope=Scope.REQUEST, provides=Committer)


class AuthProvider(Provider):
    issuer = provide(TokenIssuer, scope=Scope.REQUEST)
    sign_up = provide(SignUpCommand, scope=Scope.REQUEST)
    log_in = provide(LogInCommand, scope=Scope.REQUEST)
    refresh = provide(RefreshCommand, scope=Scope.REQUEST)
    current_user = provide(GetCurrentUserInteractor, scope=Scope.REQUEST)
    log_out = provide(LogOutCommand, scope=Scope.REQUEST)
    change_password = provide(ChangePasswordCommand, scope=Scope.REQUEST)


def create_container(config: Config, *overrides: Provider) -> AsyncContainer:
    return make_async_container(
        InfrastructureProvider(),
        AuthProvider(),
        FastapiProvider(),
        *overrides,
        context={Config: config},
    )
