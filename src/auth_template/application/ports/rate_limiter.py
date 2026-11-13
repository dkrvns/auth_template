from typing import Protocol


class RateLimiter(Protocol):
    async def allow(self, client: str) -> bool: ...
