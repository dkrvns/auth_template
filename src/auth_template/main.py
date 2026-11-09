from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import cast

from dishka import AsyncContainer
from dishka.integrations.fastapi import setup_dishka
from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import OperationalError, TimeoutError

from auth_template.application.errors import (
    ApplicationError,
    InvalidCredentialsError,
    InvalidTokenError,
    PasswordChangeError,
    UserAlreadyExistsError,
)
from auth_template.config import Config
from auth_template.ioc import create_container
from auth_template.presentation.middleware import RequestBoundaryMiddleware
from auth_template.presentation.routes import auth_router, users_router
from auth_template.presentation.transport import clear_tokens


def create_app(
    config: Config | None = None, container: AsyncContainer | None = None
) -> FastAPI:
    settings = config or Config()
    dependencies = container or create_container(settings)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        try:
            yield
        finally:
            await dependencies.close()

    app = FastAPI(title='Auth template', lifespan=lifespan)
    app.include_router(auth_router)
    app.include_router(users_router)
    setup_dishka(dependencies, app)

    async def application_error(request: Request, exc: Exception) -> JSONResponse:
        error = cast(ApplicationError, exc)
        code = status.HTTP_400_BAD_REQUEST
        headers: dict[str, str] = {}
        if isinstance(exc, InvalidCredentialsError | InvalidTokenError):
            code = status.HTTP_401_UNAUTHORIZED
            headers['WWW-Authenticate'] = 'Bearer'
        elif isinstance(exc, UserAlreadyExistsError):
            code = status.HTTP_409_CONFLICT
        elif isinstance(exc, PasswordChangeError):
            code = status.HTTP_422_UNPROCESSABLE_CONTENT
        response = JSONResponse({'detail': error.message}, code, headers=headers)
        if isinstance(exc, InvalidTokenError) and settings.auth.transport == 'cookie':
            clear_tokens(response, settings.auth)
        return response

    async def validation_error(request: Request, exc: Exception) -> JSONResponse:
        # FastAPI's default validation response can echo raw passwords and tokens.
        return JSONResponse(
            {'detail': 'Invalid request'}, status.HTTP_422_UNPROCESSABLE_CONTENT
        )

    async def database_error(request: Request, exc: Exception) -> JSONResponse:
        return JSONResponse(
            {'detail': 'Service unavailable'}, status.HTTP_503_SERVICE_UNAVAILABLE
        )

    app.add_exception_handler(ApplicationError, application_error)
    app.add_exception_handler(RequestValidationError, validation_error)
    app.add_exception_handler(OperationalError, database_error)
    app.add_exception_handler(TimeoutError, database_error)
    if settings.auth.allowed_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.auth.allowed_origins,
            allow_credentials=settings.auth.transport == 'cookie',
            allow_methods=['GET', 'POST'],
            allow_headers=['Authorization', 'Content-Type', 'X-CSRF-Token'],
        )
    app.add_middleware(RequestBoundaryMiddleware)
    return app
