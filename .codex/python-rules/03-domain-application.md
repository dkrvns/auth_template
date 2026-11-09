# Domain and application

Applies to domain/, application/ and ioc.py responsibilities, regardless of directory names.

## Entities and DTOs

```python
from dataclasses import dataclass
from uuid import UUID


@dataclass(slots=True)
class User:
    id: UUID
    team_id: UUID
    email: str
    name: str
```

- The example is a supporting-subdomain active record. Core domains use behavioral aggregates, value objects and events as described in rule 02.
- Keep entities framework-independent. Put id first, references to other aggregates by `<parent>_id` next, then other fields.
- Include persistence fields such as is_deleted/created_at in the entity only when business behavior needs them.
- Enforce domain invariants in entities/aggregates, not use cases or presentation code.
- DTOs are flat, serializable dataclasses with slots=True and no behavior. NewEntityDTO has no ID; UpdatedEntityDTO starts with entity_id.
- Use Decimal or integer minor units for money, with explicit currency and rounding; never derive Decimal from float. Distinguish UTC-aware instants from calendar dates and local schedules with named time zones.

## Ports

```python
class UserReader(Protocol):
    async def get_by_id(self, user_id: UUID) -> User | None: ...

    async def get_by_team_id(self, team_id: UUID) -> Sequence[User]: ...
```

- Define one repository per aggregate root, never for nested entities. Split ports into Reader/Saver/Updater/Deleter roles so each use case depends only on what it needs.
- Protocol methods are async with `...` bodies, accepting/returning entities and primitives.
- Put all nondeterminism and external behavior behind ports: IDs, time, transactions, external APIs.

```python
class IdGenerator(Protocol):
    def __call__(self) -> UUID: ...
```

## Commands and queries

```python
class CreateUserCommand:
    def __init__(
        self,
        user_saver: UserSaver,
        team_reader: TeamReader,
        id_generator: IdGenerator,
    ) -> None:
        self._user_saver = user_saver
        self._team_reader = team_reader
        self._id_generator = id_generator

    async def __call__(self, dto: NewUserDTO) -> UUID:
        if await self._team_reader.get_by_id(dto.team_id) is None:
            raise EntityNotFoundError('Team does not exist')

        user = User(
            id=self._id_generator(),
            team_id=dto.team_id,
            email=dto.email,
            name=dto.name,
        )
        await self._user_saver.save(user)

        return user.id
```

- The example is a transaction script for simple logic. For aggregates, orchestrate load -> domain method -> save + integration-event outbox -> UnitOfWork commit; publish externally through the outbox worker (rule 02).
- A command changes one aggregate; coordinate other aggregates through domain events.
- One class represents one use case, with a single public `async def __call__`.
- Inject the narrowest required Protocols through __init__ into self._<name>.
- Order command steps: checks -> generate IDs -> construct entity -> call port -> return ID.
- Generate IDs only through the injected IdGenerator (uuid.uuid7 in production), never uuid4()/uuid7() directly inside use cases.
- Queries return None/empty collections rather than raising not-found errors; presentation decides whether to return 404.
- Use distinct messages for distinct errors even when their exception type matches, e.g. 'Team does not exist' versus 'User does not exist'.

## Exceptions

```python
class ApplicationError(Exception):
    message = 'Application error'

    def __init__(self, message: str | None = None) -> None:
        self.message = message or self.message
        super().__init__(self.message)


class EntityNotFoundError(ApplicationError):
    message = 'Entity not found'


class EntityAlreadyExistsError(ApplicationError):
    message = 'Entity already exists'
```

- Domain errors represent invariant violations, live in domain/errors.py under DomainError, use domain language, and are raised by aggregates/value objects.
- Application errors represent use-case failures such as not found, already exists or denied access; keep them in application/errors.py under ApplicationError.
- Both base classes expose message. Map errors centrally in presentation: DomainError -> 409/422 or FAILED_PRECONDITION; EntityNotFoundError -> 404/NOT_FOUND; EntityAlreadyExistsError -> 409/ALREADY_EXISTS; validation -> 422/INVALID_ARGUMENT.

## Dependency injection

- Use one composition root, ioc.py, with providers grouped by entity.
- Use Scope.APP for settings, pools/engines, clients and ID generators; Scope.REQUEST for database sessions and dependents.
- Register implementations serving multiple ports once with provides=AnyOf[...].
- Resolve services through the container; do not construct them manually inside business logic.
