# Testing

Applies to tests/**/*.py and conftest.py.

Use pytest, pytest-asyncio (asyncio_mode="auto" in [tool.pytest]), faker, unittest.mock, and httpx.AsyncClient with ASGITransport. Run tests only through `uv run pytest`, e.g. `uv run pytest tests/user/application_test.py -k create`.

## Structure

```
tests/
  conftest.py                # shared config, engine, session and DI fixtures
  <entity>/
    __init__.py
    application_test.py      # use cases with mocked dependencies
    infrastructure_test.py   # gateways with a real test database
    http_test.py             # end-to-end endpoints through ASGI
```

- Group directories by entity and files by layer. Use one naming convention: *_test.py or test_*.py.
- Write module-level `async def test_...() -> None` functions, not classes. Do not add @pytest.mark.asyncio or pytestmark in auto mode.
- Put shared fixtures in tests/conftest.py; keep use-case-specific fixtures immediately above their tests.

## Real database isolation

```python
@pytest.fixture(scope='session')
async def engine(test_config: Config) -> AsyncIterator[AsyncEngine]:
    engine = create_async_engine(test_config.db.dsn)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest.fixture
async def session(engine: AsyncEngine) -> AsyncIterator[AsyncSession]:
    async with engine.connect() as conn:
        transaction = await conn.begin()
        session = AsyncSession(
            bind=conn, join_transaction_mode='create_savepoint', expire_on_commit=False
        )
        yield session
        await session.close()
        await transaction.rollback()
```

- Use a separate test database/service with separate environment settings, never production data.
- Create the schema once per session. Roll back an outer transaction after each test; internal commits must become savepoints, not leak between tests. Do not create engines/sessions inside individual tests.
- Session-scoped asynchronous fixtures require asyncio_default_fixture_loop_scope="session" and asyncio_default_test_loop_scope="session" in [tool.pytest].
- Use the production database engine (e.g. PostgreSQL), not SQLite substitutes; pysqlite savepoint behavior can break isolation.
- Reuse the application DI provider, overriding its database/session with test resources.

## Application unit tests

```python
@pytest.fixture
def create_user() -> CreateUserCommand:
    return CreateUserCommand(
        user_saver=create_autospec(UserSaver, instance=True),
        team_reader=create_autospec(TeamReader, instance=True),
        id_generator=MagicMock(),
    )


async def test_create_user_team_not_exists(
    create_user: CreateUserCommand, faker: Faker
) -> None:
    dto = NewUserDTO(team_id=uuid.uuid7(), email=faker.email(), name=faker.name())
    create_user._team_reader.get_by_id.return_value = None

    with pytest.raises(EntityNotFoundError, match='Team does not exist'):
        await create_user(dto)

    create_user._user_saver.save.assert_not_awaited()
    create_user._id_generator.assert_not_called()
```

- Create one snake_case fixture per use case, e.g. create_user or get_users_interactor.
- Mock ports using create_autospec(Protocol, instance=True) to check signatures; mock ID generators using MagicMock(return_value=...).
- Set dependency return_value/side_effect explicitly for each test. Access mocks through use-case attributes or dedicated fixtures; keep one project convention.
- On success, construct the expected entity, assert save.assert_awaited_once_with(expected), verify arguments and the returned generated ID.
- On failure, use pytest.raises(..., match=...) and assert writing methods were not awaited.
- For pass-through reads, assert the awaited call and equality with the dependency result.
- Test each meaningful branch separately: success, missing parent, already exists, etc. Parametrize equivalent inputs with descriptive ids.

## Infrastructure tests

- Construct gateways over real test database fixtures; do not mock SQLAlchemy.
- Seed read tests directly with insert(Model).values(...), not the gateway under test. For writes, call the gateway and inspect persisted state.
- Verify both results and actual database state, especially deletion/updates.
- Test races with independent sessions/connections, concurrent duplicates, and failures between persistence and delivery; a shared rollback fixture cannot prove concurrency safety.
- For lists, assert length and IDs; compare sets when ordering is not guaranteed.

## HTTP tests

```python
@pytest.fixture
async def http_client(container: AsyncContainer) -> AsyncIterator[AsyncClient]:
    app = create_app(container)
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url='http://test'
    ) as client:
        yield client
```

- Use the real application factory with the test DI container and ASGITransport; do not start a network server.
- Prepare related data through the test session in parent-before-child order.
- Assert status_code before response fields; compare exact detail messages for errors.
- Verify create/update/delete effects with a subsequent GET.
- Cover each endpoint with at least one success and one negative case such as 404, 409 or 422.
- For protected resources, test another user's/tenant's access as well as permitted access.

## Names and data

- Use test_<action>_<entity> for success and test_<action>_<entity>_<condition> for branches. Describe behavior, not implementation.
- Generate values with faker and IDs with uuid.uuid7(); hardcode only inputs relevant to the behavior being checked.
- Store asserted values in local variables; use old_<field>/new_<field> for updates.
- Separate arrange, act and assert with blank lines. Keep one behavioral idea per test; tests must not depend on each other or execution order.
- Cover relevant boundaries, cancellation and dependency failures; use property-based tests for nontrivial invariants and load checks for resource-sensitive changes.
