# Python code style

Applies to `**/*.py`.

## Formatting and imports

- Use ruff configured in pyproject.toml; `uv run ruff format .` and `uv run ruff check .` must pass.
- Limit lines to 88 characters. Wrap long calls, signatures and collections one item per line with trailing commas.
- Use single quotes, except when the string contains an apostrophe. Separate top-level definitions by two blank lines and methods by one; separate logical steps within functions.
- Use f-strings, not `%` formatting or `.format()`.
- Order imports as stdlib, third-party, first-party, separated by blank lines (ruff I).
- Use absolute imports from the package root. Relative imports are allowed only for __init__.py re-exports with __all__. Never use wildcard imports.
- Parenthesize long import lists, one name per line. Import Sequence, Mapping, Iterable, AsyncIterator, AsyncGenerator, Callable and other abstract collections from collections.abc, not typing or third-party libraries.

## Python 3.14 typing and syntax

- Annotate every parameter and return value, including `-> None` and tests.
- Use built-in generics and unions: `list[int]`, `dict[str, Any]`, `X | None`; avoid Optional, Union, List and Dict.
- Annotations are lazy (PEP 649/749): do not add `from __future__ import annotations` or quoted forward references; `def child(self) -> Node:` works directly.
- Use PEP 695 generics and aliases: `class Repo[T]: ...`, `def first[T](items: Sequence[T]) -> T: ...`, `type UserId = UUID`. Do not introduce TypeVar, Generic or TypeAlias.
- Use typing.Self for methods returning the same class and @override for overridden base-class methods.
- Represent absence with `T | None`, business-rule violations with exceptions. Use Any only at untyped external boundaries.
- Prefer `except ValueError, TypeError:` without parentheses when there is no `as` (PEP 758); retain parentheses with `as`.
- Use sortable uuid.uuid7() IDs rather than uuid4() for primary keys.
- Use t-strings (PEP 750) for safe SQL/HTML/template interpolation when supported by the library; use f-strings for ordinary text.
- Use match for structured data or type/shape branches, not as a replacement for simple if/elif.

## Naming

- Modules, functions and variables: snake_case; classes: PascalCase; constants: UPPER_SNAKE_CASE; private attributes/methods: one leading underscore.
- Use consistent role names: Entity or EntityDM; NewEntityDTO/UpdatedEntityDTO; EntityReader/Saver/Updater/Deleter ports; GetEntityInteractor/DeleteEntityInteractor queries/deletions; CreateEntityCommand/UpdateEntityCommand mutations; EntityGateway or EntityRepository implementations; Entity/EntityModel ORM types; EntityRequest/EntityResponse presentation schemas.
- ID parameters: `<entity>_id`, not id/uuid/pk. Collections are plural; individual objects singular. Booleans use is_/has_/can_; existence checks use exists_with_<field>.
- Do not shadow built-ins or module names such as id, type, list or uuid.

## Data and behavior

- Pass data between layers as `@dataclass(slots=True)` instances, using frozen=True for immutable data; do not pass dictionaries or ORM objects.
- Construct objects with keyword arguments and use field(default_factory=...) for mutable defaults.
- Give each function/class one responsibility; prefer early return/raise over deep nesting.
- Inject dependencies through __init__, not globals or constructors inside business methods.
- Keep async code nonblocking; offload heavy CPU work to bounded workers. Bound input sizes, concurrency, queues and caches; close resources on errors and cancellation.
- Check complexity on realistic data sizes; avoid repeated linear searches where a set/map suffices.

## Errors and documentation

- Keep application exceptions in application/errors.py under ApplicationError; domain exceptions follow the domain rules.
- Catch specific exceptions; never use bare except or `except Exception: pass`. Preserve causes with `raise NewError(...) from exc`.
- Keep exception and API error messages short, stable and in English because tests depend on them.
- Comment only non-obvious constraints/workarounds. Do not narrate obvious code or leave commented-out code.
- Use docstrings for public library APIs and non-obvious functions, not every method.
