from typing import Protocol


class RefreshTokenGenerator(Protocol):
    def generate(self) -> str: ...

    def digest(self, token: str) -> str: ...
