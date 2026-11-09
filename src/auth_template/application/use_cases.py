from datetime import datetime
from uuid import UUID

from auth_template.application.dto.auth_policy import AuthPolicy
from auth_template.application.dto.principal import Principal
from auth_template.application.dto.security.refresh_token import RefreshToken
from auth_template.application.dto.security.token_pair import TokenPairDTO
from auth_template.application.dto.session.auth_session import AuthSession
from auth_template.application.dto.user.change_password import ChangePasswordDTO
from auth_template.application.dto.user.credentials import CredentialsDTO
from auth_template.application.dto.user.user import User
from auth_template.application.errors import (
    InvalidCredentialsError,
    InvalidTokenError,
    PasswordChangeError,
    UserAlreadyExistsError,
)
from auth_template.application.ports.clock import Clock
from auth_template.application.ports.committer import Committer
from auth_template.application.ports.id_generator import IdGenerator
from auth_template.application.ports.security.access_token_codec import AccessTokenCodec
from auth_template.application.ports.security.password_hasher import PasswordHasher
from auth_template.application.ports.security.refresh_token_generator import (
    RefreshTokenGenerator,
)
from auth_template.application.ports.session.repository import SessionRepository
from auth_template.application.ports.user.reader import UserReader
from auth_template.application.ports.user.saver import UserSaver
from auth_template.application.ports.user.updater import UserUpdater


class SignUpCommand:
    def __init__(
        self,
        reader: UserReader,
        saver: UserSaver,
        hasher: PasswordHasher,
        ids: IdGenerator,
        committer: Committer,
    ) -> None:
        self._reader = reader
        self._saver = saver
        self._hasher = hasher
        self._ids = ids
        self._committer = committer

    async def __call__(self, dto: CredentialsDTO) -> UUID:
        email = dto.email.strip().casefold()
        if await self._reader.get_by_email(email) is not None:
            raise UserAlreadyExistsError
        password_hash = await self._hasher.hash(dto.password)
        user = User(id=self._ids(), email=email, password_hash=password_hash)
        await self._saver.save(user)
        await self._committer.commit()
        return user.id


class TokenIssuer:
    def __init__(
        self,
        codec: AccessTokenCodec,
        generator: RefreshTokenGenerator,
        policy: AuthPolicy,
    ) -> None:
        self._codec = codec
        self._generator = generator
        self._policy = policy

    def issue(
        self, session: AuthSession, now: datetime
    ) -> tuple[TokenPairDTO, RefreshToken]:
        raw = self._generator.generate()
        access_expires_at = min(now + self._policy.access_ttl, session.expires_at)
        pair = TokenPairDTO(
            access_token=self._codec.encode(
                Principal(user_id=session.user_id, session_id=session.id),
                now,
                access_expires_at,
            ),
            refresh_token=raw,
            expires_in=int((access_expires_at - now).total_seconds()),
            refresh_expires_in=int((session.expires_at - now).total_seconds()),
        )
        return pair, RefreshToken(
            session_id=session.id, digest=self._generator.digest(raw)
        )


class LogInCommand:
    def __init__(
        self,
        reader: UserReader,
        hasher: PasswordHasher,
        sessions: SessionRepository,
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
        valid = await self._hasher.verify(
            dto.password, user.password_hash if user else None
        )
        if not valid or user is None or not user.is_active:
            raise InvalidCredentialsError

        # Lock ordering is user -> session throughout login/refresh/password changes.
        locked = await self._reader.get_by_id(user.id, lock=True)
        if (
            locked is None
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


class RefreshCommand:
    def __init__(
        self,
        sessions: SessionRepository,
        reader: UserReader,
        generator: RefreshTokenGenerator,
        issuer: TokenIssuer,
        clock: Clock,
        committer: Committer,
    ) -> None:
        self._sessions = sessions
        self._reader = reader
        self._generator = generator
        self._issuer = issuer
        self._clock = clock
        self._committer = committer

    async def __call__(self, raw_token: str) -> TokenPairDTO:
        digest = self._generator.digest(raw_token)
        token = await self._sessions.find_token(digest)
        if token is None:
            raise InvalidTokenError
        session = await self._sessions.get(token.session_id)
        if session is None:
            raise InvalidTokenError
        user = await self._reader.get_by_id(session.user_id, lock=True)
        session = await self._sessions.get(session.id, lock=True)
        token = await self._sessions.find_token(digest)
        now = self._clock()
        if (
            user is None
            or not user.is_active
            or session is None
            or session.is_revoked
            or session.expires_at <= now
            or token is None
        ):
            raise InvalidTokenError
        if token.is_used:
            await self._sessions.revoke(session.id)
            # Persist replay revocation even though this request returns 401.
            await self._committer.commit()
            raise InvalidTokenError
        pair, replacement = self._issuer.issue(session, now)
        await self._sessions.rotate(digest, replacement)
        await self._committer.commit()
        return pair


class GetCurrentUserInteractor:
    def __init__(
        self,
        codec: AccessTokenCodec,
        sessions: SessionRepository,
        reader: UserReader,
        clock: Clock,
    ) -> None:
        self._codec = codec
        self._sessions = sessions
        self._reader = reader
        self._clock = clock

    async def __call__(self, access_token: str) -> tuple[User, Principal]:
        principal = self._codec.decode(access_token)
        session = await self._sessions.get(principal.session_id)
        if (
            session is None
            or session.user_id != principal.user_id
            or session.is_revoked
            or session.expires_at <= self._clock()
        ):
            raise InvalidTokenError
        user = await self._reader.get_by_id(principal.user_id)
        if user is None or not user.is_active:
            raise InvalidTokenError
        return user, principal


class LogOutCommand:
    def __init__(self, sessions: SessionRepository, committer: Committer) -> None:
        self._sessions = sessions
        self._committer = committer

    async def __call__(self, principal: Principal) -> None:
        await self._sessions.revoke(principal.session_id)
        await self._committer.commit()


class ChangePasswordCommand:
    def __init__(
        self,
        reader: UserReader,
        updater: UserUpdater,
        hasher: PasswordHasher,
        sessions: SessionRepository,
        committer: Committer,
    ) -> None:
        self._reader = reader
        self._updater = updater
        self._hasher = hasher
        self._sessions = sessions
        self._committer = committer

    async def __call__(self, dto: ChangePasswordDTO) -> None:
        user = await self._reader.get_by_id(dto.user_id, lock=True)
        if user is None or not user.is_active:
            raise InvalidCredentialsError
        if not await self._hasher.verify(dto.current_password, user.password_hash):
            raise InvalidCredentialsError
        if dto.current_password == dto.new_password:
            raise PasswordChangeError
        password_hash = await self._hasher.hash(dto.new_password)
        await self._updater.set_password(user.id, password_hash)
        await self._sessions.revoke_for_user(user.id)
        await self._committer.commit()
