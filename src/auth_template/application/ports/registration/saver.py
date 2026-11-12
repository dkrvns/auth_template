from typing import Protocol

from auth_template.application.dto.registration.code import RegistrationCode


class RegistrationCodeSaver(Protocol):
    async def save(self, code: RegistrationCode) -> bool: ...
