from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True, slots=True, kw_only=True)
class Principal:
    user_id: UUID
    session_id: UUID
