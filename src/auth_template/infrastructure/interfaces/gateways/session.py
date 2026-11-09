from typing import Protocol

from auth_template.application.ports.session.reader import SessionReader
from auth_template.application.ports.session.saver import SessionSaver
from auth_template.application.ports.session.updater import SessionUpdater


class SessionGatewayInterface(SessionReader, SessionSaver, SessionUpdater, Protocol):
    """Combined contract implemented by a session database gateway."""
