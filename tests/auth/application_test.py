from unittest.mock import create_autospec
from uuid import uuid7

import pytest

from auth_template.application.dto import CredentialsDTO, User
from auth_template.application.errors import UserAlreadyExistsError
from auth_template.application.ports import (
    Committer,
    IdGenerator,
    PasswordHasher,
    UserReader,
    UserSaver,
)
from auth_template.application.use_cases import SignUpCommand


@pytest.fixture
def sign_up() -> SignUpCommand:
    return SignUpCommand(
        reader=create_autospec(UserReader, instance=True),
        saver=create_autospec(UserSaver, instance=True),
        hasher=create_autospec(PasswordHasher, instance=True),
        ids=create_autospec(IdGenerator, instance=True),
        committer=create_autospec(Committer, instance=True),
    )


async def test_sign_up_saves_normalized_user(sign_up: SignUpCommand) -> None:
    user_id = uuid7()
    sign_up._reader.get_by_email.return_value = None
    sign_up._hasher.hash.return_value = 'encoded-password'
    sign_up._ids.return_value = user_id
    dto = CredentialsDTO(email=' User@Example.com ', password='Long password 42!')

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
        await sign_up(CredentialsDTO(email='user@example.com', password='unused'))

    sign_up._saver.save.assert_not_awaited()
    sign_up._hasher.hash.assert_not_awaited()
    sign_up._ids.assert_not_called()
