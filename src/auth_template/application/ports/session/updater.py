from typing import Protocol
from uuid import UUID

from auth_template.application.dto.security.refresh_token import RefreshToken


class SessionUpdater(Protocol):
    async def rotate(self, old_digest: str, token: RefreshToken) -> None: ...

    async def revoke(self, session_id: UUID) -> None: ...

    async def revoke_for_user(self, user_id: UUID) -> None: ...
