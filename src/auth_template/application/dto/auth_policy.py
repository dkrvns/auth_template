from dataclasses import dataclass
from datetime import timedelta


@dataclass(frozen=True, slots=True, kw_only=True)
class AuthPolicy:
    access_ttl: timedelta
    session_ttl: timedelta
