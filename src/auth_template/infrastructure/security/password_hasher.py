import secrets

import anyio
from pwdlib import PasswordHash


class ArgonPasswordHasher:
    def __init__(self) -> None:
        self._hasher = PasswordHash.recommended()
        self._limiter = anyio.CapacityLimiter(4)
        self._dummy_hash: str | None = None

    async def initialize(self) -> None:
        self._dummy_hash = await self.hash(secrets.token_urlsafe(32))

    async def hash(self, password: str) -> str:
        return await anyio.to_thread.run_sync(
            self._hasher.hash, password, limiter=self._limiter
        )

    async def verify(self, password: str, password_hash: str | None) -> bool:
        candidate = password_hash or self._dummy_hash
        if candidate is None:
            raise RuntimeError('Password hasher is not initialized')
        valid = await anyio.to_thread.run_sync(
            self._hasher.verify, password, candidate, limiter=self._limiter
        )
        return valid and password_hash is not None
