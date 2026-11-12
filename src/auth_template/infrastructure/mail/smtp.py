import logging
import smtplib
import ssl
from email.message import EmailMessage

import anyio

from auth_template.application.errors import MailDeliveryError
from auth_template.config import Config

logger = logging.getLogger('auth_template.mail')


class SmtpRegistrationCodeSender:
    def __init__(self, config: Config) -> None:
        self._config = config.mail
        self._limiter = anyio.CapacityLimiter(4)

    async def send(self, email: str, code: str) -> None:
        try:
            await anyio.to_thread.run_sync(
                self._send, email, code, limiter=self._limiter
            )
        except OSError, ValueError:
            logger.warning('registration_mail_delivery_failed')
            raise MailDeliveryError from None

    def _send(self, email: str, code: str) -> None:
        config = self._config
        if config is None:
            raise MailDeliveryError
        message = EmailMessage()
        message['From'] = config.sender
        message['To'] = email
        message['Subject'] = 'Код подтверждения регистрации'
        message.set_content(
            f'Ваш код подтверждения: {code}\n\n'
            'Код действует 10 минут и может быть использован один раз.\n'
            'Если вы не запрашивали регистрацию, проигнорируйте это письмо.\n'
        )
        client = (
            smtplib.SMTP_SSL(
                config.host,
                config.port,
                timeout=config.timeout_seconds,
                context=ssl.create_default_context(),
            )
            if config.security == 'ssl'
            else smtplib.SMTP(config.host, config.port, timeout=config.timeout_seconds)
        )
        try:
            if config.security == 'starttls':
                client.starttls(context=ssl.create_default_context())
            if config.username:
                client.login(config.username, config.password.get_secret_value())
            if client.send_message(message):
                raise MailDeliveryError
        finally:
            # DATA acceptance is success; a failed QUIT must not trigger a resend.
            client.close()
