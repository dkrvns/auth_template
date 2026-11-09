from dishka.integrations.fastapi import FromDishka, inject
from fastapi import APIRouter, Depends, Request, Response, status

from auth_template.application.dto.user.change_password import ChangePasswordDTO
from auth_template.application.dto.user.credentials import CredentialsDTO
from auth_template.application.errors import InvalidTokenError
from auth_template.config import AuthConfig
from auth_template.infrastructure.auth.handlers.registration.sign_up import (
    SignUpHandler,
)
from auth_template.infrastructure.auth.handlers.session.log_in import LogInHandler
from auth_template.infrastructure.auth.handlers.session.log_out import LogOutHandler
from auth_template.infrastructure.auth.handlers.session.refresh import RefreshHandler
from auth_template.infrastructure.auth.handlers.user.change_password import (
    ChangePasswordHandler,
)
from auth_template.presentation.dependencies import CurrentUser, guard_auth_request
from auth_template.presentation.schemas import (
    ChangePasswordRequest,
    CreatedUserResponse,
    CredentialsRequest,
    RefreshRequest,
    TokenResponse,
    UserResponse,
)
from auth_template.presentation.transport import clear_tokens, deliver_tokens

auth_router = APIRouter(
    prefix='/auth', tags=['auth'], dependencies=[Depends(guard_auth_request)]
)
users_router = APIRouter(prefix='/users', tags=['users'])


@auth_router.post('/signup', status_code=status.HTTP_201_CREATED)
@inject
async def sign_up(
    body: CredentialsRequest, handler: FromDishka[SignUpHandler]
) -> CreatedUserResponse:
    user_id = await handler(
        CredentialsDTO(email=str(body.email), password=body.password.get_secret_value())
    )
    return CreatedUserResponse(id=user_id)


@auth_router.post('/login')
@inject
async def log_in(
    body: CredentialsRequest,
    response: Response,
    handler: FromDishka[LogInHandler],
    config: FromDishka[AuthConfig],
) -> TokenResponse:
    pair = await handler(
        CredentialsDTO(email=str(body.email), password=body.password.get_secret_value())
    )
    deliver_tokens(response, pair, config)
    return TokenResponse.from_entity(pair, cookie=config.transport == 'cookie')


@auth_router.post('/refresh')
@inject
async def refresh(
    request: Request,
    response: Response,
    handler: FromDishka[RefreshHandler],
    config: FromDishka[AuthConfig],
    body: RefreshRequest | None = None,
) -> TokenResponse:
    raw = (
        request.cookies.get('refresh_token')
        if config.transport == 'cookie'
        else body.refresh_token.get_secret_value()
        if body and body.refresh_token
        else None
    )
    if raw is None or not 32 <= len(raw) <= 256:
        raise InvalidTokenError
    pair = await handler(raw)
    deliver_tokens(response, pair, config)
    return TokenResponse.from_entity(pair, cookie=config.transport == 'cookie')


@auth_router.post('/logout', status_code=status.HTTP_204_NO_CONTENT)
@inject
async def log_out(
    identity: CurrentUser,
    response: Response,
    handler: FromDishka[LogOutHandler],
    config: FromDishka[AuthConfig],
) -> None:
    await handler(identity[1])
    clear_tokens(response, config)


@auth_router.post('/change-password', status_code=status.HTTP_204_NO_CONTENT)
@inject
async def change_password(
    body: ChangePasswordRequest,
    identity: CurrentUser,
    response: Response,
    handler: FromDishka[ChangePasswordHandler],
    config: FromDishka[AuthConfig],
) -> None:
    await handler(
        ChangePasswordDTO(
            user_id=identity[1].user_id,
            current_password=body.current_password.get_secret_value(),
            new_password=body.new_password.get_secret_value(),
        )
    )
    clear_tokens(response, config)


@users_router.get('/me')
async def get_me(identity: CurrentUser) -> UserResponse:
    return UserResponse.from_entity(identity[0])
