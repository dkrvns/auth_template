import secrets
from uuid import uuid7

from sqlalchemy.ext.asyncio import AsyncSession

from auth_template.application.dto.security.refresh_token import RefreshToken
from auth_template.application.dto.session.auth_session import AuthSession
from auth_template.application.dto.user.user import User
from auth_template.infrastructure.gateways.session import SessionGateway
from auth_template.infrastructure.gateways.user import UserGateway


async def test_get_user_by_id_missing_returns_empty_user(session: AsyncSession) -> None:
    gateway = UserGateway(session)

    user = await gateway.get_by_id(uuid7())

    assert user == User()
    assert user.id is None
    assert user.email == ''
    assert user.password_hash == ''


async def test_get_user_by_email_missing_returns_empty_user(
    session: AsyncSession,
) -> None:
    gateway = UserGateway(session)

    user = await gateway.get_by_email(f'{uuid7().hex}@example.com')

    assert user == User()
    assert user.id is None


async def test_get_session_missing_returns_empty_session(session: AsyncSession) -> None:
    gateway = SessionGateway(session)

    auth_session = await gateway.get(uuid7())

    assert auth_session == AuthSession()
    assert auth_session.id is None
    assert auth_session.user_id is None
    assert auth_session.expires_at is None


async def test_find_token_missing_returns_empty_token(session: AsyncSession) -> None:
    gateway = SessionGateway(session)

    token = await gateway.find_token(secrets.token_hex(32))

    assert token == RefreshToken()
    assert token.session_id is None
    assert token.digest == ''
