from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import insert, select
from sqlalchemy.ext.asyncio import AsyncSession

from auth_template.application.dto.registration.code import RegistrationCode
from auth_template.infrastructure.db.models import RegistrationCodeModel
from auth_template.infrastructure.gateways.registration_code import (
    RegistrationCodeGateway,
)


@pytest.mark.parametrize(('elapsed', 'allowed'), [(44, False), (45, True)])
async def test_registration_resend_enforces_45_second_boundary(
    session: AsyncSession, elapsed: int, allowed: bool
) -> None:
    now = datetime.now(UTC)
    email = 'cooldown@example.com'
    await session.execute(
        insert(RegistrationCodeModel).values(
            email=email,
            digest='old-digest',
            sent_at=now,
            expires_at=now + timedelta(minutes=10),
            attempts_left=5,
        )
    )
    replacement = RegistrationCode(
        email=email,
        digest='new-digest',
        sent_at=now + timedelta(seconds=elapsed),
        expires_at=now + timedelta(minutes=11),
        attempts_left=5,
    )

    result = await RegistrationCodeGateway(session).save(replacement)

    assert result is allowed
    stored = await session.scalar(
        select(RegistrationCodeModel.digest).where(RegistrationCodeModel.email == email)
    )
    assert stored == ('new-digest' if allowed else 'old-digest')
