from typing import Protocol

from auth_template.application.dto import User


class UserSaver(Protocol):
    async def save(self, user: User) -> None: ...
