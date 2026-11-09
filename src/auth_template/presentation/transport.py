from fastapi import Response

from auth_template.application.dto.security.token_pair import TokenPairDTO
from auth_template.config import AuthConfig


def deliver_tokens(response: Response, pair: TokenPairDTO, config: AuthConfig) -> None:
    response.headers['Cache-Control'] = 'no-store'
    if config.transport != 'cookie':
        return
    response.set_cookie(
        'access_token',
        pair.access_token,
        max_age=pair.expires_in,
        httponly=True,
        secure=config.cookie_secure,
        samesite='strict',
        path='/',
    )
    response.set_cookie(
        'refresh_token',
        pair.refresh_token,
        max_age=pair.refresh_expires_in,
        httponly=True,
        secure=config.cookie_secure,
        samesite='strict',
        path='/auth/refresh',
    )


def clear_tokens(response: Response, config: AuthConfig) -> None:
    for name, path in [('access_token', '/'), ('refresh_token', '/auth/refresh')]:
        response.delete_cookie(
            name,
            path=path,
            httponly=True,
            secure=config.cookie_secure,
            samesite='strict',
        )
