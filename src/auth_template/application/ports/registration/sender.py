from typing import Protocol


class RegistrationCodeSender(Protocol):
    async def send(self, email: str, code: str) -> None: ...
