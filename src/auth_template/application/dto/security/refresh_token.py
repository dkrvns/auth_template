from dataclasses import dataclass, field
from uuid import UUID


@dataclass(frozen=True, slots=True, kw_only=True)
class RefreshToken:
    session_id: UUID
    digest: str = field(repr=False)
    is_used: bool = False
