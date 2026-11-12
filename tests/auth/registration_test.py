import os
import secrets
from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient
from pydantic import SecretStr
from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from tests.auth.registration_helpers import RegistrationMailbox, registration_payload

from auth_template.application.errors import MailDeliveryError
from auth_template.config import Config, MailConfig
from auth_template.infrastructure.db.models import RegistrationCodeModel, UserModel
from auth_template.infrastructure.gateways.registration_code import (
    RegistrationCodeGateway,
)
from auth_template.infrastructure.mail.smtp import SmtpRegistrationCodeSender
from auth_template.infrastructure.security.registration_code_codec import (
    HmacRegistrationCodeCodec,
)


async def test_signup_requires_code(
    http_client: AsyncClient, credentials: dict[str, str]
) -> None:
    response = await http_client.post('/auth/signup', json=credentials)

    assert response.status_code == 422
    assert response.json() == {'detail': 'Invalid request'}
    assert (await http_client.post('/auth/login', json=credentials)).status_code == 401


@pytest.mark.parametrize(
    'condition', ['missing', 'expired', 'exhausted', 'wrong-email']
)
async def test_signup_rejects_unusable_code(
    http_client: AsyncClient,
    credentials: dict[str, str],
    registration_mailbox: RegistrationMailbox,
    session: AsyncSession,
    condition: str,
) -> None:
    payload = await registration_payload(http_client, registration_mailbox, credentials)
    if condition == 'missing':
        await session.execute(delete(RegistrationCodeModel))
    elif condition == 'expired':
        await session.execute(
            update(RegistrationCodeModel).values(expires_at=datetime.now(UTC))
        )
    elif condition == 'exhausted':
        await session.execute(update(RegistrationCodeModel).values(attempts_left=0))
    else:
        payload['email'] = f'other-{secrets.token_hex(8)}@example.com'
    await session.commit()

    response = await http_client.post('/auth/signup', json=payload)

    assert response.status_code == 400
    assert response.json() == {'detail': 'Invalid or expired registration code'}
    assert await session.scalar(select(UserModel.id)) is None


async def test_wrong_codes_persist_attempt_limit(
    http_client: AsyncClient,
    credentials: dict[str, str],
    registration_mailbox: RegistrationMailbox,
    session: AsyncSession,
) -> None:
    payload = await registration_payload(http_client, registration_mailbox, credentials)
    wrong = '000000' if payload['code'] != '000000' else '000001'
    for remaining in range(4, -1, -1):
        response = await http_client.post(
            '/auth/signup', json={**payload, 'code': wrong}
        )
        assert response.status_code == 400
        assert (
            await session.scalar(select(RegistrationCodeModel.attempts_left))
            == remaining
        )

    response = await http_client.post('/auth/signup', json=payload)

    assert response.status_code == 400
    assert await session.scalar(select(UserModel.id)) is None


async def test_successful_code_is_consumed_atomically(
    http_client: AsyncClient,
    credentials: dict[str, str],
    registration_mailbox: RegistrationMailbox,
    session: AsyncSession,
) -> None:
    payload = await registration_payload(http_client, registration_mailbox, credentials)
    assert (await http_client.post('/auth/signup', json=payload)).status_code == 201
    assert await session.scalar(select(RegistrationCodeModel.attempts_left)) == 0
    await session.execute(delete(UserModel))
    await session.commit()

    replay = await http_client.post('/auth/signup', json=payload)

    assert replay.status_code == 400
    assert await session.scalar(select(UserModel.id)) is None


async def test_resend_is_throttled_and_replaces_old_code(
    http_client: AsyncClient,
    credentials: dict[str, str],
    registration_mailbox: RegistrationMailbox,
    session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    values = iter([123456, 234567, 345678])
    monkeypatch.setattr(
        'auth_template.infrastructure.security.registration_code_codec.secrets.randbelow',
        lambda _: next(values),
    )
    payload = await registration_payload(http_client, registration_mailbox, credentials)
    response = await http_client.post(
        '/auth/signup/code', json={'email': credentials['email'].upper()}
    )
    assert response.status_code == 429
    assert response.headers['retry-after'] == '60'
    assert registration_mailbox.codes[credentials['email']] == payload['code']
    await session.execute(
        update(RegistrationCodeModel).values(
            sent_at=datetime.now(UTC) - timedelta(seconds=61)
        )
    )
    await session.commit()
    replacement = await registration_payload(
        http_client, registration_mailbox, credentials
    )
    assert replacement['code'] != payload['code']

    assert (await http_client.post('/auth/signup', json=payload)).status_code == 400
    assert (await http_client.post('/auth/signup', json=replacement)).status_code == 201


async def test_delivery_failure_invalidates_code(
    http_client: AsyncClient,
    credentials: dict[str, str],
    registration_mailbox: RegistrationMailbox,
    session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fail(email: str, code: str) -> None:
        raise MailDeliveryError

    monkeypatch.setattr(registration_mailbox, 'send', fail)

    response = await http_client.post(
        '/auth/signup/code', json={'email': credentials['email']}
    )

    assert response.status_code == 503
    assert response.json() == {'detail': 'Unable to send registration email'}
    assert await session.scalar(select(RegistrationCodeModel.attempts_left)) == 0
    assert await session.scalar(select(UserModel.id)) is None


async def test_code_digest_is_keyed_and_bound_to_email(test_config: Config) -> None:
    codec = HmacRegistrationCodeCodec(test_config.auth)
    code = codec.generate()
    digest = codec.digest('owner@example.com', code)

    assert len(code) == 6
    assert code.isascii()
    assert code.isdigit()
    assert len(digest) == 64
    assert digest != code
    assert codec.verify('owner@example.com', code, digest)
    assert not codec.verify('other@example.com', code, digest)
    other = test_config.auth.model_copy(
        update={'secret': SecretStr(secrets.token_urlsafe(48))}
    )
    assert not HmacRegistrationCodeCodec(other).verify(
        'owner@example.com', code, digest
    )


async def test_missing_gateway_code_returns_empty_dto(session: AsyncSession) -> None:
    code = await RegistrationCodeGateway(session).get_by_email('missing@example.com')

    assert code.email == ''
    assert code.expires_at is None
    assert code.attempts_left == 0


async def test_smtp_delivers_code_to_isolated_mailpit(test_config: Config) -> None:
    host = os.environ['TEST_SMTP_HOST']
    mailbox_url = os.environ['TEST_MAILPIT_URL']
    email = f'smtp-{secrets.token_hex(12)}@example.com'
    code = '123456'
    config = test_config.model_copy(deep=True)
    config.mail = MailConfig(
        host=host, port=1025, sender='no-reply@example.com', security='plain'
    )

    await SmtpRegistrationCodeSender(config).send(email, code)

    async with AsyncClient(base_url=mailbox_url, timeout=5) as client:
        response = await client.get('/api/v1/search', params={'query': f'to:{email}'})
        assert response.status_code == 200
        messages = response.json()['messages']
        assert len(messages) == 1
        message = await client.get(f'/api/v1/message/{messages[0]["ID"]}')
        assert message.status_code == 200
        assert code in message.json()['Text']
        assert message.json()['To'][0]['Address'] == email


async def test_smtp_missing_configuration_fails_closed(test_config: Config) -> None:
    config = test_config.model_copy(update={'mail': None})

    with pytest.raises(MailDeliveryError, match='Unable to send registration email'):
        await SmtpRegistrationCodeSender(config).send('test@example.com', '123456')


async def test_smtp_plaintext_authentication_is_rejected() -> None:
    with pytest.raises(ValueError, match='SMTP authentication requires TLS'):
        MailConfig(
            host='smtp.example.com',
            port=1025,
            sender='test@example.com',
            security='plain',
            username='user',
            password='test-password',
        )


@pytest.mark.parametrize(
    'code', ['', '12345', '1234567', 'abcdef', '\uff11\uff12\uff13\uff14\uff15\uff16']
)
async def test_signup_validates_code_without_echoing_it(
    http_client: AsyncClient, credentials: dict[str, str], code: str
) -> None:
    response = await http_client.post(
        '/auth/signup', json={**credentials, 'code': code}
    )

    assert response.status_code == 422
    assert response.json() == {'detail': 'Invalid request'}


async def test_smtp_errors_do_not_log_email_or_code(
    test_config: Config,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    config = test_config.model_copy(deep=True)
    config.mail = MailConfig(
        host='smtp.example.com', port=587, sender='no-reply@example.com'
    )
    email = 'private-recipient@example.com'
    code = '654321'

    def fail(*args: object, **kwargs: object) -> None:
        raise OSError(f'upstream rejected {email}: {code}')

    monkeypatch.setattr('auth_template.infrastructure.mail.smtp.smtplib.SMTP', fail)

    with pytest.raises(MailDeliveryError, match='Unable to send registration email'):
        await SmtpRegistrationCodeSender(config).send(email, code)
    assert 'registration_mail_delivery_failed' in caplog.text
    assert email not in caplog.text
    assert code not in caplog.text
