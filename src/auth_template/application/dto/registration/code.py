from dataclasses import dataclass, field
from datetime import datetime


@dataclass(frozen=True, slots=True, kw_only=True)
class RegistrationCode:
    email: str = ''
    digest: str = field(default='', repr=False)
    sent_at: datetime | None = None
    expires_at: datetime | None = None
    attempts_left: int = 0
