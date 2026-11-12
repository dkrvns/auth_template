from dishka import Provider, Scope, provide
from httpx import AsyncClient

from auth_template.application.ports.registration.sender import RegistrationCodeSender


class RegistrationMailbox:
    def __init__(self) -> None:
        self.codes: dict[str, str] = {}

    async def send(self, email: str, code: str) -> None:
        self.codes[email] = code


class MailOverrideProvider(Provider):
    def __init__(self, mailbox: RegistrationMailbox) -> None:
        super().__init__()
        self._mailbox = mailbox

    @provide(scope=Scope.APP, override=True)
    def sender(self) -> RegistrationCodeSender:
        return self._mailbox


async def registration_payload(
    client: AsyncClient,
    mailbox: RegistrationMailbox,
    credentials: dict[str, str],
) -> dict[str, str]:
    response = await client.post(
        '/auth/signup/code', json={'email': credentials['email']}
    )
    assert response.status_code == 204
    return {
        **credentials,
        'code': mailbox.codes[credentials['email'].casefold()],
    }
