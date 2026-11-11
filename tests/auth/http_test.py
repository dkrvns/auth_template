from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid7

import jwt
import pytest
from httpx import AsyncClient
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from auth_template.config import Config
from auth_template.infrastructure.db.models import (
    AuthSessionModel,
    RefreshTokenModel,
    UserModel,
)


async def test_sign_up_user(
    http_client: AsyncClient, credentials: dict[str, str], session: AsyncSession
) -> None:
    response = await http_client.post('/auth/signup', json=credentials)

    assert response.status_code == 201
    user = await session.get(UserModel, UUID(response.json()['id']))
    assert user is not None
    assert user.password_hash.startswith('$argon2id$')
    assert credentials['password'] not in response.text
    assert user.email == credentials['email']


async def test_sign_up_user_duplicate(
    http_client: AsyncClient, credentials: dict[str, str]
) -> None:
    assert (await http_client.post('/auth/signup', json=credentials)).status_code == 201
    credentials['email'] = credentials['email'].upper()

    response = await http_client.post('/auth/signup', json=credentials)

    assert response.status_code == 409
    assert response.json() == {'detail': 'User already exists'}


@pytest.mark.parametrize(
    ('field', 'value'),
    [
        ('email', 'not-an-email'),
        ('password', 'short'),
        ('password', 'x' * 129),
        ('is_active', True),
    ],
    ids=['invalid-email', 'short-password', 'long-password', 'extra-field'],
)
async def test_sign_up_user_invalid_request(
    http_client: AsyncClient,
    credentials: dict[str, str],
    field: str,
    value: str | bool,
) -> None:
    payload = {**credentials, field: value}

    response = await http_client.post('/auth/signup', json=payload)

    assert response.status_code == 422
    assert response.json() == {'detail': 'Invalid request'}
    assert credentials['password'] not in response.text


async def test_log_in_user_returns_stored_identity(
    http_client: AsyncClient, credentials: dict[str, str], token_pair: dict[str, str]
) -> None:
    headers = {'Authorization': f'Bearer {token_pair["access_token"]}'}

    response = await http_client.get('/users/me', headers=headers)

    assert response.status_code == 200
    assert response.json()['email'] == credentials['email']
    assert set(response.json()) == {'id', 'email'}
    assert response.headers['cache-control'] == 'no-store'
    assert response.headers['x-request-id']


@pytest.mark.parametrize(
    'existing_user', [False, True], ids=['unknown', 'wrong-password']
)
async def test_log_in_user_invalid_credentials(
    http_client: AsyncClient, credentials: dict[str, str], existing_user: bool
) -> None:
    if existing_user:
        assert (
            await http_client.post('/auth/signup', json=credentials)
        ).status_code == 201
    response = await http_client.post(
        '/auth/login', json={**credentials, 'password': 'Wrong password 42!'}
    )

    assert response.status_code == 401
    assert response.json() == {'detail': 'Invalid credentials'}
    assert response.headers['www-authenticate'] == 'Bearer'


@pytest.mark.parametrize('raw', ['', 'Bearer broken', 'Basic abc'])
async def test_get_user_missing_or_invalid_token(
    http_client: AsyncClient, raw: str
) -> None:
    response = await http_client.get('/users/me', headers={'Authorization': raw})

    assert response.status_code == 401
    assert response.json() == {'detail': 'Invalid or expired token'}


@pytest.mark.parametrize(
    'claim',
    [
        'exp',
        'aud',
        'iss',
        'sid',
        'type',
        'sub',
        'signature',
        'other-user',
        'missing-exp',
    ],
)
async def test_get_user_rejects_invalid_claims(
    http_client: AsyncClient,
    token_pair: dict[str, str],
    test_config: Config,
    claim: str,
) -> None:
    payload = jwt.decode(
        token_pair['access_token'], options={'verify_signature': False}
    )
    replacements = {
        'exp': int((datetime.now(UTC) - timedelta(seconds=10)).timestamp()),
        'aud': 'other-api',
        'iss': 'other-issuer',
        'sid': str(uuid7()),
        'type': 'refresh',
        'sub': None,
    }
    if claim == 'other-user':
        payload['sub'] = str(uuid7())
    elif claim == 'missing-exp':
        del payload['exp']
    elif claim != 'signature':
        payload[claim] = replacements[claim]
    secret = test_config.auth.secret.get_secret_value()
    token = jwt.encode(
        payload, secret if claim != 'signature' else 'x' * 48, algorithm='HS256'
    )

    response = await http_client.get(
        '/users/me', headers={'Authorization': f'Bearer {token}'}
    )

    assert response.status_code == 401


async def test_refresh_rotates_and_revokes_replayed_session(
    http_client: AsyncClient, token_pair: dict[str, str], session: AsyncSession
) -> None:
    response = await http_client.post(
        '/auth/refresh', json={'refresh_token': token_pair['refresh_token']}
    )
    assert response.status_code == 200
    replacement = response.json()
    assert replacement['refresh_token'] != token_pair['refresh_token']
    assert replacement['refresh_token'] not in str(
        (await session.scalars(select(RefreshTokenModel.digest))).all()
    )

    replay = await http_client.post(
        '/auth/refresh', json={'refresh_token': token_pair['refresh_token']}
    )
    assert replay.status_code == 401
    denied = await http_client.get(
        '/users/me', headers={'Authorization': f'Bearer {replacement["access_token"]}'}
    )
    assert denied.status_code == 401
    denied_refresh = await http_client.post(
        '/auth/refresh', json={'refresh_token': replacement['refresh_token']}
    )
    assert denied_refresh.status_code == 401


async def test_refresh_unknown_token(http_client: AsyncClient) -> None:
    response = await http_client.post('/auth/refresh', json={'refresh_token': 'a' * 64})

    assert response.status_code == 401


async def test_refresh_missing_token(http_client: AsyncClient) -> None:
    response = await http_client.post('/auth/refresh')

    assert response.status_code == 401


async def test_log_out_revokes_access_and_refresh(
    http_client: AsyncClient, token_pair: dict[str, str]
) -> None:
    headers = {'Authorization': f'Bearer {token_pair["access_token"]}'}

    response = await http_client.post('/auth/logout', headers=headers)

    assert response.status_code == 204
    assert response.content == b''
    assert (await http_client.get('/users/me', headers=headers)).status_code == 401
    assert (await http_client.post('/auth/logout', headers=headers)).status_code == 401
    refresh = await http_client.post(
        '/auth/refresh', json={'refresh_token': token_pair['refresh_token']}
    )
    assert refresh.status_code == 401


async def test_log_out_requires_authentication(http_client: AsyncClient) -> None:
    response = await http_client.post('/auth/logout')

    assert response.status_code == 401


async def test_change_password_revokes_all_sessions(
    http_client: AsyncClient, credentials: dict[str, str], token_pair: dict[str, str]
) -> None:
    second = await http_client.post('/auth/login', json=credentials)
    assert second.status_code == 200
    new_password = 'New password 43!'

    response = await http_client.post(
        '/auth/change-password',
        headers={'Authorization': f'Bearer {token_pair["access_token"]}'},
        json={
            'current_password': credentials['password'],
            'new_password': new_password,
        },
    )

    assert response.status_code == 204
    for pair in (token_pair, second.json()):
        denied = await http_client.get(
            '/users/me', headers={'Authorization': f'Bearer {pair["access_token"]}'}
        )
        assert denied.status_code == 401
    assert (await http_client.post('/auth/login', json=credentials)).status_code == 401
    logged_in = await http_client.post(
        '/auth/login', json={**credentials, 'password': new_password}
    )
    assert logged_in.status_code == 200


@pytest.mark.parametrize(
    ('current', 'new', 'status'),
    [
        ('Wrong password 42!', 'New password 43!', 401),
        ('Long password 42!', 'Long password 42!', 422),
    ],
    ids=['wrong-current', 'unchanged'],
)
async def test_change_password_rejects_invalid_credentials(
    http_client: AsyncClient,
    token_pair: dict[str, str],
    current: str,
    new: str,
    status: int,
) -> None:
    response = await http_client.post(
        '/auth/change-password',
        headers={'Authorization': f'Bearer {token_pair["access_token"]}'},
        json={'current_password': current, 'new_password': new},
    )

    assert response.status_code == status


async def test_change_password_requires_authentication(
    http_client: AsyncClient,
) -> None:
    response = await http_client.post(
        '/auth/change-password',
        json={
            'current_password': 'Long password 42!',
            'new_password': 'New password 43!',
        },
    )

    assert response.status_code == 401


@pytest.mark.parametrize('condition', ['inactive', 'session-expired'])
async def test_get_user_rejects_disabled_user_or_expired_session(
    http_client: AsyncClient,
    token_pair: dict[str, str],
    session: AsyncSession,
    condition: str,
) -> None:
    if condition == 'inactive':
        await session.execute(update(UserModel).values(is_active=False))
    else:
        await session.execute(
            update(AuthSessionModel).values(
                expires_at=datetime.now(UTC) - timedelta(seconds=10)
            )
        )
    await session.commit()

    response = await http_client.get(
        '/users/me', headers={'Authorization': f'Bearer {token_pair["access_token"]}'}
    )

    assert response.status_code == 401


async def test_request_body_is_bounded(http_client: AsyncClient) -> None:
    response = await http_client.post('/auth/signup', content=b'x' * 16385)

    assert response.status_code == 413


async def test_openapi_schema_describes_authentication(
    http_client: AsyncClient,
) -> None:
    response = await http_client.get('/openapi.json')

    assert response.status_code == 200
    assert set(response.json()['paths']) == {
        '/auth/signup',
        '/auth/login',
        '/auth/refresh',
        '/auth/logout',
        '/auth/change-password',
        '/users/me',
    }
    assert response.json()['components']['securitySchemes']['HTTPBearer']['scheme'] == (
        'bearer'
    )


@pytest.mark.parametrize('condition', ['inactive', 'expired'])
async def test_refresh_rejects_inactive_user_or_expired_session(
    http_client: AsyncClient,
    token_pair: dict[str, str],
    session: AsyncSession,
    condition: str,
) -> None:
    if condition == 'inactive':
        await session.execute(update(UserModel).values(is_active=False))
    else:
        await session.execute(
            update(AuthSessionModel).values(
                expires_at=datetime.now(UTC) - timedelta(seconds=10)
            )
        )
    await session.commit()

    response = await http_client.post(
        '/auth/refresh', json={'refresh_token': token_pair['refresh_token']}
    )

    assert response.status_code == 401
