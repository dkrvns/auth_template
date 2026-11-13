from typing import Protocol
from uuid import UUID


class UserUpdater(Protocol):
    async def set_password(self, user_id: UUID, password_hash: str) -> None: ...
