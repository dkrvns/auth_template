from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True, slots=True, kw_only=True)
class AuthSession:
    id: UUID | None = None
    user_id: UUID | None = None
    expires_at: datetime | None = None
    is_revoked: bool = False
