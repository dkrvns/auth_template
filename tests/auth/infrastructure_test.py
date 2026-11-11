import asyncio
import secrets
from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker

from auth_template.config import Config
from auth_template.infrastructure.db.models import UserModel
from auth_template.main import create_app


@pytest.fixture
async def independent_client(
    engine: AsyncEngine, test_config: Config, credentials: dict[str, str]
) -> AsyncIterator[AsyncClient]:
    app = create_app(test_config)
    async with (
        app.router.lifespan_context(app),
        AsyncClient(
            transport=ASGITransport(app=app), base_url='https://test'
        ) as client,
    ):
        try:
            yield client
        finally:
            async with async_sessionmaker(engine).begin() as session:
                await session.execute(
                    delete(UserModel).where(UserModel.email == credentials['email'])
                )


async def test_concurrent_sign_up_creates_one_user(
    independent_client: AsyncClient,
    credentials: dict[str, str],
    engine: AsyncEngine,
) -> None:
    responses = await asyncio.gather(
        independent_client.post('/auth/signup', json=credentials),
        independent_client.post('/auth/signup', json=credentials),
    )

    assert sorted(response.status_code for response in responses) == [201, 409]
    async with async_sessionmaker(engine)() as session:
        count = await session.scalar(
            select(func.count())
            .select_from(UserModel)
            .where(UserModel.email == credentials['email'])
        )
        assert count == 1


async def test_concurrent_refresh_revokes_replayed_session(
    independent_client: AsyncClient, credentials: dict[str, str]
) -> None:
    signup = await independent_client.post('/auth/signup', json=credentials)
    assert signup.status_code == 201
    login = await independent_client.post('/auth/login', json=credentials)
    assert login.status_code == 200
    pair = login.json()

    responses = await asyncio.gather(
        independent_client.post(
            '/auth/refresh', json={'refresh_token': pair['refresh_token']}
        ),
        independent_client.post(
            '/auth/refresh', json={'refresh_token': pair['refresh_token']}
        ),
    )

    assert sorted(response.status_code for response in responses) == [200, 401]
    winner = next(
        response.json() for response in responses if response.status_code == 200
    )
    denied = await independent_client.get(
        '/users/me', headers={'Authorization': f'Bearer {winner["access_token"]}'}
    )
    assert denied.status_code == 401


async def test_concurrent_password_change_and_login(
    independent_client: AsyncClient, credentials: dict[str, str]
) -> None:
    assert (
        await independent_client.post('/auth/signup', json=credentials)
    ).status_code == 201
    login = await independent_client.post('/auth/login', json=credentials)
    assert login.status_code == 200
    pair = login.json()

    changed, logged_in = await asyncio.gather(
        independent_client.post(
            '/auth/change-password',
            headers={'Authorization': f'Bearer {pair["access_token"]}'},
            json={
                'current_password': credentials['password'],
                'new_password': 'Different password 56!',
            },
        ),
        independent_client.post('/auth/login', json=credentials),
    )

    assert changed.status_code == 204
    assert logged_in.status_code in (200, 401)
    if logged_in.status_code == 200:
        denied = await independent_client.get(
            '/users/me',
            headers={'Authorization': f'Bearer {logged_in.json()["access_token"]}'},
        )
        assert denied.status_code == 401


async def test_rate_limiter_shares_state_between_instances(
    test_config: Config, engine: AsyncEngine
) -> None:
    from auth_template.infrastructure.clock import utc_now
    from auth_template.infrastructure.db.rate_limiter import PostgresRateLimiter

    config = test_config.auth.model_copy(update={'requests_per_minute': 2})
    sessions = async_sessionmaker(engine)
    first = PostgresRateLimiter(sessions, utc_now, config)
    second = PostgresRateLimiter(sessions, utc_now, config)
    client = secrets.token_hex(16)

    allowed = await asyncio.gather(
        first.allow(client), second.allow(client), first.allow(client)
    )

    assert sorted(allowed) == [False, True, True]
