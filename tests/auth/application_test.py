from datetime import UTC, datetime, timedelta
from unittest.mock import create_autospec
from uuid import uuid7

import pytest

from auth_template.application.dto.registration.code import RegistrationCode
from auth_template.application.dto.user.sign_up import SignUpDTO
from auth_template.application.dto.user.user import User
from auth_template.application.errors import UserAlreadyExistsError
from auth_template.application.ports.clock import Clock
from auth_template.application.ports.committer import Committer
from auth_template.application.ports.id_generator import IdGenerator
from auth_template.application.ports.registration.reader import RegistrationCodeReader
from auth_template.application.ports.registration.updater import RegistrationCodeUpdater
from auth_template.application.ports.security.password_hasher import PasswordHasher
from auth_template.application.ports.security.registration_code_codec import (
    RegistrationCodeCodec,
)
from auth_template.application.ports.user.reader import UserReader
from auth_template.application.ports.user.saver import UserSaver
from auth_template.infrastructure.auth.handlers.registration.sign_up import (
    SignUpHandler as SignUpCommand,
)


@pytest.fixture
def sign_up() -> SignUpCommand:
    return SignUpCommand(
        reader=create_autospec(UserReader, instance=True),
        saver=create_autospec(UserSaver, instance=True),
        hasher=create_autospec(PasswordHasher, instance=True),
        ids=create_autospec(IdGenerator, instance=True),
        committer=create_autospec(Committer, instance=True),
        codes=create_autospec(RegistrationCodeReader, instance=True),
        code_updater=create_autospec(RegistrationCodeUpdater, instance=True),
        codec=create_autospec(RegistrationCodeCodec, instance=True),
        clock=create_autospec(Clock, instance=True),
    )


async def test_sign_up_saves_normalized_user(sign_up: SignUpCommand) -> None:
    user_id = uuid7()
    sign_up._reader.get_by_email.return_value = User()
    sign_up._hasher.hash.return_value = 'encoded-password'
    sign_up._ids.return_value = user_id
    now = datetime.now(UTC)
    sign_up._clock.return_value = now
    sign_up._codes.get_by_email.return_value = RegistrationCode(
        email='user@example.com',
        digest='encoded-code',
        attempts_left=5,
        expires_at=now + timedelta(minutes=10),
    )
    sign_up._codec.verify.return_value = True
    dto = SignUpDTO(
        email=' User@Example.com ', password='Long password 42!', code='123456'
    )

    result = await sign_up(dto)

    assert result == user_id
    sign_up._saver.save.assert_awaited_once_with(
        User(id=user_id, email='user@example.com', password_hash='encoded-password')
    )
    sign_up._committer.commit.assert_awaited_once_with()


async def test_sign_up_duplicate_does_not_write(sign_up: SignUpCommand) -> None:
    sign_up._reader.get_by_email.return_value = User(
        id=uuid7(), email='user@example.com', password_hash='encoded-password'
    )

    with pytest.raises(UserAlreadyExistsError, match='User already exists'):
        await sign_up(
            SignUpDTO(email='user@example.com', password='unused', code='123456')
        )

    sign_up._saver.save.assert_not_awaited()
    sign_up._hasher.hash.assert_not_awaited()
    sign_up._ids.assert_not_called()
