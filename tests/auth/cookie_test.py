from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession
from tests.conftest import DatabaseOverrideProvider

from auth_template.config import Config
from auth_template.ioc import create_container
from auth_template.main import create_app


@pytest.fixture
async def cookie_client(
    test_config: Config, session: AsyncSession, engine: AsyncEngine
) -> AsyncIterator[AsyncClient]:
    config = test_config.model_copy(deep=True)
    config.auth.transport = 'cookie'
    config.auth.allowed_origins = ['https://test']
    container = create_container(config, DatabaseOverrideProvider(session, engine))
    app = create_app(config, container)
    async with (
        app.router.lifespan_context(app),
        AsyncClient(
            transport=ASGITransport(app=app),
            base_url='https://test',
            headers={'Origin': 'https://test', 'X-CSRF-Token': '1'},
        ) as client,
    ):
        yield client


async def test_cookie_authentication_lifecycle(
    cookie_client: AsyncClient, credentials: dict[str, str]
) -> None:
    assert (
        await cookie_client.post('/auth/signup', json=credentials)
    ).status_code == 201
    login = await cookie_client.post('/auth/login', json=credentials)

    assert login.status_code == 200
    assert login.json()['access_token'] is None
    assert login.json()['refresh_token'] is None
    for header in login.headers.get_list('set-cookie'):
        assert 'HttpOnly' in header
        assert 'Secure' in header
        assert 'SameSite=strict' in header
    assert (await cookie_client.get('/users/me')).status_code == 200
    old_refresh = cookie_client.cookies.get('refresh_token')
    refreshed = await cookie_client.post('/auth/refresh')
    assert refreshed.status_code == 200
    assert cookie_client.cookies.get('refresh_token') != old_refresh
    logout = await cookie_client.post('/auth/logout')
    assert logout.status_code == 204
    assert cookie_client.cookies.get('access_token') is None
    assert cookie_client.cookies.get('refresh_token') is None
    assert (await cookie_client.get('/users/me')).status_code == 401


@pytest.mark.parametrize(
    'headers',
    [
        {'Origin': 'https://attacker.example', 'X-CSRF-Token': '1'},
        {'Origin': 'https://test'},
        {'X-CSRF-Token': '1'},
        {'Origin': 'null', 'X-CSRF-Token': '1'},
    ],
    ids=['foreign-origin', 'missing-header', 'missing-origin', 'null-origin'],
)
async def test_cookie_rejects_csrf(
    cookie_client: AsyncClient,
    credentials: dict[str, str],
    headers: dict[str, str],
) -> None:
    cookie_client.headers.clear()
    response = await cookie_client.post(
        '/auth/signup', json=credentials, headers=headers
    )

    assert response.status_code == 403
    assert response.json() == {'detail': 'CSRF validation failed'}


async def test_http_rate_limit_returns_retry_after(
    test_config: Config,
    session: AsyncSession,
    engine: AsyncEngine,
    credentials: dict[str, str],
) -> None:
    config = test_config.model_copy(deep=True)
    config.auth.requests_per_minute = 1
    container = create_container(config, DatabaseOverrideProvider(session, engine))
    app = create_app(config, container)
    async with (
        app.router.lifespan_context(app),
        AsyncClient(
            transport=ASGITransport(app=app, client=(credentials['email'], 123)),
            base_url='https://test',
        ) as client,
    ):
        first = await client.post('/auth/signup', json=credentials)
        assert first.status_code == 201

        response = await client.post('/auth/login', json=credentials)

    assert response.status_code == 429
    assert response.json() == {'detail': 'Too many requests'}
    assert response.headers['retry-after'] == '60'
