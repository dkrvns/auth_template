from dataclasses import dataclass, field
from uuid import UUID


@dataclass(frozen=True, slots=True, kw_only=True)
class User:
    id: UUID | None = None
    email: str = ''
    password_hash: str = field(default='', repr=False)
    is_active: bool = True
