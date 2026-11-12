class ApplicationError(Exception):
    message = 'Application error'

    def __init__(self, message: str | None = None) -> None:
        self.message = message or self.message
        super().__init__(self.message)


class InvalidCredentialsError(ApplicationError):
    message = 'Invalid credentials'


class InvalidTokenError(ApplicationError):
    message = 'Invalid or expired token'


class UserAlreadyExistsError(ApplicationError):
    message = 'User already exists'


class PasswordChangeError(ApplicationError):
    message = 'New password must differ from current password'


class InvalidRegistrationCodeError(ApplicationError):
    message = 'Invalid or expired registration code'


class RegistrationCodeRateLimitError(ApplicationError):
    message = 'Registration code requested too recently'


class MailDeliveryError(ApplicationError):
    message = 'Unable to send registration email'
