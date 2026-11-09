from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True, kw_only=True)
class TokenPairDTO:
    access_token: str = field(repr=False)
    refresh_token: str = field(repr=False)
    expires_in: int
    refresh_expires_in: int
