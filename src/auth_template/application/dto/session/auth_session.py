from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True, slots=True, kw_only=True)
class AuthSession:
    id: UUID
    user_id: UUID
    expires_at: datetime
    is_revoked: bool = False
