import asyncio
from uuid import uuid7

import pytest
from alembic import command
from alembic.config import Config as AlembicConfig
from sqlalchemy import inspect, text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from auth_template.config import Config


async def test_migration_upgrade_downgrade_and_model_consistency(
    test_config: Config, engine: AsyncEngine, monkeypatch: pytest.MonkeyPatch
) -> None:
    schema = f'migration_{uuid7().hex}'
    async with engine.begin() as connection:
        await connection.execute(text(f'CREATE SCHEMA {schema}'))
    dsn = make_url(test_config.database.dsn.get_secret_value()).update_query_dict(
        {'options': f'-csearch_path={schema}'}
    )
    monkeypatch.setenv('DATABASE__DSN', dsn.render_as_string(hide_password=False))
    monkeypatch.setenv('AUTH__SECRET', test_config.auth.secret.get_secret_value())
    monkeypatch.setenv('AUTH__ISSUER', test_config.auth.issuer)
    monkeypatch.setenv('AUTH__AUDIENCE', test_config.auth.audience)
    monkeypatch.setenv('HTTP__HOST', test_config.http.host)
    monkeypatch.setenv('HTTP__PORT', str(test_config.http.port))
    migration_config = AlembicConfig('alembic.ini')
    migration_engine = create_async_engine(dsn)
    try:
        await asyncio.to_thread(command.upgrade, migration_config, 'head')
        await asyncio.to_thread(command.check, migration_config)
        async with migration_engine.connect() as connection:
            names = await connection.run_sync(
                lambda sync: inspect(sync).get_table_names(schema=schema)
            )
        assert set(names) == {
            'alembic_version',
            'users',
            'auth_sessions',
            'refresh_tokens',
            'auth_rate_limits',
        }
        await asyncio.to_thread(command.downgrade, migration_config, 'base')
        async with migration_engine.connect() as connection:
            names = await connection.run_sync(
                lambda sync: inspect(sync).get_table_names(schema=schema)
            )
        assert names == ['alembic_version']
        await asyncio.to_thread(command.upgrade, migration_config, 'head')
    finally:
        await migration_engine.dispose()
        async with engine.begin() as connection:
            await connection.execute(text(f'DROP SCHEMA {schema} CASCADE'))
