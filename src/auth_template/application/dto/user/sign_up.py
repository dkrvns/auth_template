from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True, kw_only=True)
class SignUpDTO:
    email: str
    password: str = field(repr=False)
    code: str = field(repr=False)
