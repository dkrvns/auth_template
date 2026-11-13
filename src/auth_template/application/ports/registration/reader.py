from typing import Protocol

from auth_template.application.dto.registration.code import RegistrationCode


class RegistrationCodeReader(Protocol):
    async def get_by_email(self, email: str) -> RegistrationCode: ...
