import hmac
import secrets

from auth_template.config import AuthConfig


class HmacRegistrationCodeCodec:
    def __init__(self, config: AuthConfig) -> None:
        self._key = config.secret.get_secret_value().encode()

    def generate(self) -> str:
        return f'{secrets.randbelow(1_000_000):06d}'

    def digest(self, email: str, code: str) -> str:
        payload = f'registration\0{email}\0{code}'.encode()
        return hmac.digest(self._key, payload, 'sha256').hex()

    def verify(self, email: str, code: str, digest: str) -> bool:
        return hmac.compare_digest(self.digest(email, code), digest)
