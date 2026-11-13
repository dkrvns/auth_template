from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True, kw_only=True)
class CredentialsDTO:
    email: str
    password: str = field(repr=False)
