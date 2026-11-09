from auth_template.application.dto.security.token_pair import TokenPairDTO
from auth_template.application.errors import InvalidTokenError
from auth_template.application.ports.clock import Clock
from auth_template.application.ports.committer import Committer
from auth_template.application.ports.security.refresh_token_generator import (
    RefreshTokenGenerator,
)
from auth_template.application.ports.session.reader import SessionReader
from auth_template.application.ports.session.updater import SessionUpdater
from auth_template.application.ports.user.reader import UserReader
from auth_template.infrastructure.auth.tokens.issuer import TokenIssuer


class RefreshHandler:
    def __init__(
        self,
        session_reader: SessionReader,
        session_updater: SessionUpdater,
        reader: UserReader,
        generator: RefreshTokenGenerator,
        issuer: TokenIssuer,
        clock: Clock,
        committer: Committer,
    ) -> None:
        self._session_reader = session_reader
        self._session_updater = session_updater
        self._reader = reader
        self._generator = generator
        self._issuer = issuer
        self._clock = clock
        self._committer = committer

    async def __call__(self, raw_token: str) -> TokenPairDTO:
        digest = self._generator.digest(raw_token)
        token = await self._session_reader.find_token(digest)
        if token.session_id is None:
            raise InvalidTokenError
        session = await self._session_reader.get(token.session_id)
        if session.id is None or session.user_id is None:
            raise InvalidTokenError
        user = await self._reader.get_by_id(session.user_id, lock=True)
        session = await self._session_reader.get(session.id, lock=True)
        token = await self._session_reader.find_token(digest)
        now = self._clock()
        if (
            user.id is None
            or not user.is_active
            or session.id is None
            or session.user_id is None
            or session.is_revoked
            or session.expires_at is None
            or session.expires_at <= now
            or token.session_id is None
        ):
            raise InvalidTokenError
        if token.is_used:
            await self._session_updater.revoke(session.id)
            # Persist replay revocation even though this request returns 401.
            await self._committer.commit()
            raise InvalidTokenError
        pair, replacement = self._issuer.issue(session, now)
        await self._session_updater.rotate(digest, replacement)
        await self._committer.commit()
        return pair
