from typing import Protocol

from auth_template.application.dto.security.refresh_token import RefreshToken
from auth_template.application.dto.session.auth_session import AuthSession


class SessionSaver(Protocol):
    async def save(self, session: AuthSession, token: RefreshToken) -> None: ...
