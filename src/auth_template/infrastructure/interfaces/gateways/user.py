from typing import Protocol

from auth_template.application.ports.user.reader import UserReader
from auth_template.application.ports.user.saver import UserSaver
from auth_template.application.ports.user.updater import UserUpdater


class UserGatewayInterface(UserReader, UserSaver, UserUpdater, Protocol):
    """Combined contract implemented by a user database gateway."""
