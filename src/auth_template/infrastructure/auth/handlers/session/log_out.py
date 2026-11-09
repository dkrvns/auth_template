from auth_template.application.dto.principal import Principal
from auth_template.application.ports.committer import Committer
from auth_template.application.ports.session.repository import SessionRepository


class LogOutHandler:
    def __init__(self, sessions: SessionRepository, committer: Committer) -> None:
        self._sessions = sessions
        self._committer = committer

    async def __call__(self, principal: Principal) -> None:
        await self._sessions.revoke(principal.session_id)
        await self._committer.commit()
