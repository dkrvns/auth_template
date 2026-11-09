from typing import Annotated

from dishka.integrations.fastapi import FromDishka, inject
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from auth_template.application.dto import Principal, User
from auth_template.application.errors import InvalidTokenError
from auth_template.application.ports.rate_limiter import RateLimiter
from auth_template.application.use_cases import GetCurrentUserInteractor
from auth_template.config import AuthConfig

bearer = HTTPBearer(auto_error=False)


@inject
async def current_user(
    request: Request,
    interactor: FromDishka[GetCurrentUserInteractor],
    config: FromDishka[AuthConfig],
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
) -> tuple[User, Principal]:
    raw = (
        request.cookies.get('access_token')
        if config.transport == 'cookie'
        else credentials.credentials
        if credentials
        else None
    )
    if not raw or len(raw) > 4096:
        raise InvalidTokenError
    return await interactor(raw)


type CurrentUser = Annotated[tuple[User, Principal], Depends(current_user)]


@inject
async def guard_auth_request(
    request: Request,
    config: FromDishka[AuthConfig],
    limiter: FromDishka[RateLimiter],
) -> None:
    if config.transport == 'cookie' and (
        request.headers.get('origin') not in config.allowed_origins
        or request.headers.get('x-csrf-token') != '1'
    ):
        raise HTTPException(status.HTTP_403_FORBIDDEN, 'CSRF validation failed')
    # Forwarded headers are accepted only by an explicitly configured trusted proxy.
    client = request.client.host if request.client else 'unknown'
    if not await limiter.allow(client):
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            'Too many requests',
            headers={'Retry-After': '60'},
        )
