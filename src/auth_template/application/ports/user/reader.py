from typing import Protocol
from uuid import UUID

from auth_template.application.dto import User


class UserReader(Protocol):
    async def get_by_email(self, email: str) -> User | None: ...

    async def get_by_id(self, user_id: UUID, *, lock: bool = False) -> User | None: ...
