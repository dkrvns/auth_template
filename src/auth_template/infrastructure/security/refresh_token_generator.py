import hashlib
import secrets


class OpaqueRefreshTokenGenerator:
    def generate(self) -> str:
        return secrets.token_urlsafe(48)

    def digest(self, token: str) -> str:
        return hashlib.sha256(token.encode()).hexdigest()
