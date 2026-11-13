import asyncio
import secrets
from contextvars import ContextVar
from uuid import UUID

import pytest
from httpx import AsyncClient, Response
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker
from tests.auth.registration_helpers import (
    RegistrationMailbox,
    registration_payload,
)

from auth_template.application.dto.user.user import User
from auth_template.config import Config
from auth_template.infrastructure.db.models import RegistrationCodeModel, UserModel
from auth_template.infrastructure.gateways.user import UserGateway


async def test_concurrent_sign_up_creates_one_user(
    independent_client: AsyncClient,
    credentials: dict[str, str],
    engine: AsyncEngine,
    registration_mailbox: RegistrationMailbox,
) -> None:
    payload = await registration_payload(
        independent_client, registration_mailbox, credentials
    )
    responses = await asyncio.gather(
        independent_client.post('/auth/signup', json=payload),
        independent_client.post('/auth/signup', json=payload),
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
    independent_client: AsyncClient,
    credentials: dict[str, str],
    registration_mailbox: RegistrationMailbox,
) -> None:
    payload = await registration_payload(
        independent_client, registration_mailbox, credentials
    )
    signup = await independent_client.post('/auth/signup', json=payload)
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


@pytest.mark.parametrize(
    ('first', 'login_status'), [('login', 200), ('change-password', 401)]
)
async def test_concurrent_password_change_and_login(
    independent_client: AsyncClient,
    credentials: dict[str, str],
    registration_mailbox: RegistrationMailbox,
    engine: AsyncEngine,
    monkeypatch: pytest.MonkeyPatch,
    first: str,
    login_status: int,
) -> None:
    payload = await registration_payload(
        independent_client, registration_mailbox, credentials
    )
    signup = await independent_client.post('/auth/signup', json=payload)
    assert signup.status_code == 201
    user_id = UUID(signup.json()['id'])
    login = await independent_client.post('/auth/login', json=credentials)
    assert login.status_code == 200
    pair = login.json()
    new_password = 'Different password 56!'
    operation: ContextVar[str] = ContextVar('password_race_operation', default='')
    holder_locked = asyncio.Event()
    contender_started = asyncio.Event()
    release_holder = asyncio.Event()
    backend_pids: dict[str, int] = {}
    original_get = UserGateway.get_by_id

    async def controlled_get(
        gateway: UserGateway, requested_id: UUID, *, lock: bool = False
    ) -> User:
        role = operation.get()
        if requested_id != user_id or not lock or not role:
            return await original_get(gateway, requested_id, lock=lock)
        backend_pids[role] = await gateway._session.scalar(
            select(func.pg_backend_pid())
        )
        if role == first:
            result = await original_get(gateway, requested_id, lock=True)
            holder_locked.set()
            await release_holder.wait()
            return result
        contender_started.set()
        return await original_get(gateway, requested_id, lock=True)

    async def send(role: str) -> Response:
        marker = operation.set(role)
        try:
            if role == 'login':
                return await independent_client.post('/auth/login', json=credentials)
            return await independent_client.post(
                '/auth/change-password',
                headers={'Authorization': f'Bearer {pair["access_token"]}'},
                json={
                    'current_password': credentials['password'],
                    'new_password': new_password,
                },
            )
        finally:
            operation.reset(marker)

    monkeypatch.setattr(UserGateway, 'get_by_id', controlled_get)
    second = 'change-password' if first == 'login' else 'login'
    tasks: dict[str, asyncio.Task[Response]] = {}
    try:
        async with asyncio.timeout(15):
            tasks[first] = asyncio.create_task(send(first))
            await holder_locked.wait()
            tasks[second] = asyncio.create_task(send(second))
            await contender_started.wait()
            async with engine.connect() as connection:
                while True:
                    blockers = await connection.scalar(
                        select(func.pg_blocking_pids(backend_pids[second]))
                    )
                    if backend_pids[first] in blockers:
                        break
                    await asyncio.sleep(0.01)
            # The second transaction is demonstrably blocked by the first in PostgreSQL.
            assert not tasks[second].done()
            release_holder.set()
            await asyncio.gather(*tasks.values())
    finally:
        release_holder.set()
        for task in tasks.values():
            if not task.done():
                task.cancel()
        await asyncio.gather(*tasks.values(), return_exceptions=True)

    changed = tasks['change-password'].result()
    logged_in = tasks['login'].result()

    assert changed.status_code == 204
    assert logged_in.status_code == login_status
    if logged_in.status_code == 200:
        denied = await independent_client.get(
            '/users/me',
            headers={'Authorization': f'Bearer {logged_in.json()["access_token"]}'},
        )
        assert denied.status_code == 401
        refresh = await independent_client.post(
            '/auth/refresh', json={'refresh_token': logged_in.json()['refresh_token']}
        )
        assert refresh.status_code == 401
    assert (
        await independent_client.get(
            '/users/me', headers={'Authorization': f'Bearer {pair["access_token"]}'}
        )
    ).status_code == 401
    assert (
        await independent_client.post('/auth/login', json=credentials)
    ).status_code == 401
    new_login = await independent_client.post(
        '/auth/login', json={**credentials, 'password': new_password}
    )
    assert new_login.status_code == 200
    assert (
        await independent_client.get(
            '/users/me',
            headers={'Authorization': f'Bearer {new_login.json()["access_token"]}'},
        )
    ).status_code == 200


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


async def test_concurrent_code_requests_send_one_email(
    independent_client: AsyncClient,
    credentials: dict[str, str],
    registration_mailbox: RegistrationMailbox,
) -> None:
    responses = await asyncio.gather(
        independent_client.post(
            '/auth/signup/code', json={'email': credentials['email']}
        ),
        independent_client.post(
            '/auth/signup/code', json={'email': credentials['email']}
        ),
    )

    assert sorted(response.status_code for response in responses) == [204, 429]
    assert registration_mailbox.deliveries == [
        (credentials['email'], registration_mailbox.codes[credentials['email']])
    ]


async def test_concurrent_wrong_codes_do_not_lose_attempts(
    independent_client: AsyncClient,
    credentials: dict[str, str],
    registration_mailbox: RegistrationMailbox,
    engine: AsyncEngine,
) -> None:
    payload = await registration_payload(
        independent_client, registration_mailbox, credentials
    )
    wrong = '000000' if payload['code'] != '000000' else '000001'

    responses = await asyncio.gather(
        *(
            independent_client.post('/auth/signup', json={**payload, 'code': wrong})
            for _ in range(7)
        )
    )

    assert all(response.status_code == 400 for response in responses)
    async with async_sessionmaker(engine)() as session:
        remaining = await session.scalar(
            select(RegistrationCodeModel.attempts_left).where(
                RegistrationCodeModel.email == credentials['email']
            )
        )
        assert remaining == 0
    assert (
        await independent_client.post('/auth/signup', json=payload)
    ).status_code == 400
