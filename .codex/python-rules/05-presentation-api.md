# Presentation

Applies to presentation/, api/ and main.py responsibilities.

## FastAPI

```python
router = APIRouter(prefix='/users', tags=['users'])


@router.get('/{user_id}')
@inject
async def get_user(
    user_id: UUID,
    interactor: FromDishka[GetUserByIdInteractor],
) -> UserResponse:
    user = await interactor(user_id)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, 'User not found')

    return UserResponse.from_entity(user)
```

- Use one router per entity with prefix and tags; register it in create_app().
- Order decorators as @router.<method>(...) followed by @inject.
- Keep handlers thin: unpack input -> invoke command/query -> map result; no business logic or database access.
- Follow the project's URL style consistently. For new projects use resource REST: GET /users, GET /users/{user_id}, POST /users, PUT/PATCH /users/{user_id}, DELETE /users/{user_id}.
- Use status.HTTP_* constants rather than numeric status codes; creation returns 201 and bodyless deletion 204.
- Annotate handler return types; these define response_model.
- Map application exceptions centrally with app.add_exception_handler(ApplicationError, ...), rather than catching them in each handler. Use local catches only for endpoint-specific responses.
- Keep detail messages short, stable and in English; they are part of the tested contract.

## Schemas

- Use pydantic schemas only in presentation: EntityRequest for input and EntityResponse for output.
- Map entities explicitly with @classmethod from_entity(...) or model_validate(..., from_attributes=True); choose one project convention.
- Validate shape, lengths and formats such as EmailStr in schemas; enforce uniqueness/existence and other business rules in commands.
- Validate all external boundaries, including broker messages and upstream responses; static annotations do not validate runtime data. Limit request/upload sizes before buffering.

## gRPC, when present

- EntityGRPCService inherits the generated EntityServiceServicer; use PascalCase methods matching .proto.
- Signature: self, request, context, interactor: FromDishka[...]. Parse incoming IDs with UUID(request.<field>) and serialize with str(...).
- Abort with `await context.abort(grpc.StatusCode.<CODE>, '<message>')`, using the same messages as HTTP.
- Use proto3 syntax, package <entity>, string UUIDs and google.protobuf.Empty for empty messages.

## Startup

- create_app() constructs the application, registers routers, exception handlers and DI; tests use the same factory.
- Load host/port from configuration. Start with `uv run python -m <package>` or `uv run uvicorn <package>.main:create_app --factory`.
