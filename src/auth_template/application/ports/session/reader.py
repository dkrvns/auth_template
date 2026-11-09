from typing import Protocol
from uuid import UUID

from auth_template.application.dto.security.refresh_token import RefreshToken
from auth_template.application.dto.session.auth_session import AuthSession


class SessionReader(Protocol):
    async def get(
        self, session_id: UUID, *, lock: bool = False
    ) -> AuthSession | None: ...

    async def find_token(self, digest: str) -> RefreshToken | None: ...
