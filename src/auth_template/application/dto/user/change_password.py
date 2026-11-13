from dataclasses import dataclass, field
from uuid import UUID


@dataclass(frozen=True, slots=True, kw_only=True)
class ChangePasswordDTO:
    user_id: UUID
    current_password: str = field(repr=False)
    new_password: str = field(repr=False)
