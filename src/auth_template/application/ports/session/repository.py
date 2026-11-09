from typing import Protocol
from uuid import UUID

from auth_template.application.dto import AuthSession, RefreshToken


class SessionRepository(Protocol):
    async def save(self, session: AuthSession, token: RefreshToken) -> None: ...

    async def get(
        self, session_id: UUID, *, lock: bool = False
    ) -> AuthSession | None: ...

    async def find_token(self, digest: str) -> RefreshToken | None: ...

    async def rotate(self, old_digest: str, token: RefreshToken) -> None: ...

    async def revoke(self, session_id: UUID) -> None: ...

    async def revoke_for_user(self, user_id: UUID) -> None: ...
