from typing import Protocol


class RegistrationCodeUpdater(Protocol):
    async def use_attempt(self, email: str) -> None: ...

    async def invalidate(self, email: str, digest: str) -> None: ...
