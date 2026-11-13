from datetime import timedelta

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from auth_template.application.dto.registration.code import RegistrationCode
from auth_template.application.ports.registration.reader import RegistrationCodeReader
from auth_template.application.ports.registration.saver import RegistrationCodeSaver
from auth_template.application.ports.registration.updater import RegistrationCodeUpdater
from auth_template.infrastructure.db.models import RegistrationCodeModel


class RegistrationCodeGateway(
    RegistrationCodeReader, RegistrationCodeSaver, RegistrationCodeUpdater
):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_email(self, email: str) -> RegistrationCode:
        row = await self._session.scalar(
            select(RegistrationCodeModel)
            .where(RegistrationCodeModel.email == email)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        return (
            RegistrationCode(
                email=row.email,
                digest=row.digest,
                sent_at=row.sent_at,
                expires_at=row.expires_at,
                attempts_left=row.attempts_left,
            )
            if row
            else RegistrationCode()
        )

    async def save(self, code: RegistrationCode) -> bool:
        if code.sent_at is None:
            raise ValueError('Registration code requires sent_at')
        query = (
            pg_insert(RegistrationCodeModel)
            .values(
                email=code.email,
                digest=code.digest,
                sent_at=code.sent_at,
                expires_at=code.expires_at,
                attempts_left=code.attempts_left,
            )
            .on_conflict_do_update(
                index_elements=[RegistrationCodeModel.email],
                set_={
                    'digest': code.digest,
                    'sent_at': code.sent_at,
                    'expires_at': code.expires_at,
                    'attempts_left': code.attempts_left,
                },
                where=RegistrationCodeModel.sent_at
                <= code.sent_at - timedelta(seconds=45),
            )
            .returning(RegistrationCodeModel.email)
        )
        return await self._session.scalar(query) is not None

    async def use_attempt(self, email: str) -> None:
        await self._session.execute(
            update(RegistrationCodeModel)
            .where(
                RegistrationCodeModel.email == email,
                RegistrationCodeModel.attempts_left > 0,
            )
            .values(attempts_left=RegistrationCodeModel.attempts_left - 1)
        )

    async def invalidate(self, email: str, digest: str) -> None:
        await self._session.execute(
            update(RegistrationCodeModel)
            .where(
                RegistrationCodeModel.email == email,
                RegistrationCodeModel.digest == digest,
            )
            .values(attempts_left=0)
        )
