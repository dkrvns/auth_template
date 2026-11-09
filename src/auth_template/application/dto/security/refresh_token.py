from dataclasses import dataclass, field
from uuid import UUID


@dataclass(frozen=True, slots=True, kw_only=True)
class RefreshToken:
    session_id: UUID | None = None
    digest: str = field(default='', repr=False)
    is_used: bool = False
