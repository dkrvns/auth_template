import os
import secrets
from collections.abc import AsyncIterator

import pytest
from dishka import Provider, Scope, provide
from httpx import ASGITransport, AsyncClient
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine

from auth_template.config import Config
from auth_template.infrastructure.models import Base
from auth_template.ioc import create_container
from auth_template.main import create_app


@pytest.fixture(scope='session')
def test_config() -> Config:
    dsn = os.environ.get('TEST_DATABASE_DSN')
    if not dsn or not (make_url(dsn).database or '').endswith('_test'):
        raise pytest.UsageError(
            'Set TEST_DATABASE_DSN to a dedicated PostgreSQL database ending in _test'
        )
    return Config.model_validate(
        {
            'database': {'dsn': dsn},
            'auth': {
                'secret': secrets.token_urlsafe(48),
                'issuer': 'auth-tests',
                'audience': 'auth-tests-api',
                'requests_per_minute': 1000,
            },
            'http': {'host': '127.0.0.1', 'port': 8000},
        }
    )


@pytest.fixture(scope='session')
async def engine(test_config: Config) -> AsyncIterator[AsyncEngine]:
    engine = create_async_engine(test_config.database.dsn.get_secret_value())
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.drop_all)
        await connection.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest.fixture
async def session(engine: AsyncEngine) -> AsyncIterator[AsyncSession]:
    async with engine.connect() as connection:
        transaction = await connection.begin()
        session = AsyncSession(
            bind=connection,
            join_transaction_mode='create_savepoint',
            expire_on_commit=False,
            autoflush=False,
        )
        try:
            yield session
        finally:
            await session.close()
            await transaction.rollback()


class DatabaseOverrideProvider(Provider):
    def __init__(self, session: AsyncSession, engine: AsyncEngine) -> None:
        super().__init__()
        self._session = session
        self._engine = engine

    @provide(scope=Scope.APP, override=True)
    def engine(self) -> AsyncEngine:
        return self._engine

    @provide(scope=Scope.REQUEST, override=True)
    def session(self) -> AsyncSession:
        return self._session


@pytest.fixture
async def http_client(
    test_config: Config, session: AsyncSession, engine: AsyncEngine
) -> AsyncIterator[AsyncClient]:
    container = create_container(test_config, DatabaseOverrideProvider(session, engine))
    app = create_app(test_config, container)
    async with (
        app.router.lifespan_context(app),
        AsyncClient(
            transport=ASGITransport(app=app), base_url='https://test'
        ) as client,
    ):
        yield client


@pytest.fixture
def credentials() -> dict[str, str]:
    return {
        'email': f'{secrets.token_hex(8)}@example.com',
        'password': 'Long password 42!',
    }


@pytest.fixture
async def token_pair(
    http_client: AsyncClient, credentials: dict[str, str]
) -> dict[str, str]:
    response = await http_client.post('/auth/signup', json=credentials)
    assert response.status_code == 201
    response = await http_client.post('/auth/login', json=credentials)
    assert response.status_code == 200
    return response.json()
