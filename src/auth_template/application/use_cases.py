"""Legacy imports for existing consumers; auth is implemented in infrastructure."""

from auth_template.infrastructure.auth.handlers.registration.sign_up import (
    SignUpHandler as SignUpCommand,
)
from auth_template.infrastructure.auth.handlers.session.log_in import (
    LogInHandler as LogInCommand,
)
from auth_template.infrastructure.auth.handlers.session.log_out import (
    LogOutHandler as LogOutCommand,
)
from auth_template.infrastructure.auth.handlers.session.refresh import (
    RefreshHandler as RefreshCommand,
)
from auth_template.infrastructure.auth.handlers.user.change_password import (
    ChangePasswordHandler as ChangePasswordCommand,
)
from auth_template.infrastructure.auth.interactors.user.get_current_user import (
    GetCurrentUserInteractor,
)
from auth_template.infrastructure.auth.tokens.issuer import TokenIssuer

__all__ = [
    'ChangePasswordCommand',
    'GetCurrentUserInteractor',
    'LogInCommand',
    'LogOutCommand',
    'RefreshCommand',
    'SignUpCommand',
    'TokenIssuer',
]
