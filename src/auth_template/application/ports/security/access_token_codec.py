from datetime import datetime
from typing import Protocol

from auth_template.application.dto import Principal


class AccessTokenCodec(Protocol):
    def encode(
        self, principal: Principal, now: datetime, expires_at: datetime
    ) -> str: ...

    def decode(self, token: str) -> Principal: ...
