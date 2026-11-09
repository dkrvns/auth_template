from auth_template.application.dto.auth_policy import AuthPolicy
from auth_template.application.dto.security.token_pair import TokenPairDTO
from auth_template.application.dto.session.auth_session import AuthSession
from auth_template.application.dto.user.credentials import CredentialsDTO
from auth_template.application.errors import InvalidCredentialsError
from auth_template.application.ports.clock import Clock
from auth_template.application.ports.committer import Committer
from auth_template.application.ports.id_generator import IdGenerator
from auth_template.application.ports.security.password_hasher import PasswordHasher
from auth_template.application.ports.session.saver import SessionSaver
from auth_template.application.ports.user.reader import UserReader
from auth_template.infrastructure.auth.tokens.issuer import TokenIssuer


class LogInHandler:
    def __init__(
        self,
        reader: UserReader,
        hasher: PasswordHasher,
        sessions: SessionSaver,
        issuer: TokenIssuer,
        ids: IdGenerator,
        clock: Clock,
        policy: AuthPolicy,
        committer: Committer,
    ) -> None:
        self._reader = reader
        self._hasher = hasher
        self._sessions = sessions
        self._issuer = issuer
        self._ids = ids
        self._clock = clock
        self._policy = policy
        self._committer = committer

    async def __call__(self, dto: CredentialsDTO) -> TokenPairDTO:
        user = await self._reader.get_by_email(dto.email.strip().casefold())
        valid = await self._hasher.verify(dto.password, user.password_hash or None)
        if not valid or user.id is None or not user.is_active:
            raise InvalidCredentialsError

        # Lock ordering is user -> session throughout login/refresh/password changes.
        locked = await self._reader.get_by_id(user.id, lock=True)
        if (
            locked.id is None
            or not locked.is_active
            or locked.password_hash != user.password_hash
        ):
            raise InvalidCredentialsError
        now = self._clock()
        session = AuthSession(
            id=self._ids(),
            user_id=user.id,
            expires_at=now + self._policy.session_ttl,
        )
        pair, token = self._issuer.issue(session, now)
        await self._sessions.save(session, token)
        await self._committer.commit()
        return pair
