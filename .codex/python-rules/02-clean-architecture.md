# Domain-driven design and clean architecture

Applies when designing or changing backend services with business logic.

Sources: Eric Evans, Domain-Driven Design (2003) and Domain-Driven Design Reference (2015); Vlad Khononov, Learning Domain-Driven Design (2021) and Balancing Coupling in Software Design (2024).

Match code complexity to business complexity. Start with strategic analysis, then choose tactical patterns; not every component needs a rich domain model.

## 1. Ubiquitous language

- Name modules, classes, methods, events and errors using domain-expert terms: Order.place(), Invoice.issue(), OrderPlaced, CreditLimitExceededError, not OrderManager, process_data() or update_status(2).
- Give each term one meaning within a context. Different meanings across business areas suggest a context boundary, not a type field.
- Use CRUD verbs only when the business uses them; otherwise name the intent: cancel, approve, reschedule.
- New code terms must be understandable to domain experts; update code names when business terminology changes.
- Keep a glossary in docs/ or the context README when the vocabulary exceeds a dozen terms.

## 2. Subdomains

Identify the subdomain type before choosing the design:

- Core: competitive advantage, complex/frequently changing logic. Build internally, prioritize expertise, rich models and domain tests.
- Supporting: necessary but not differentiating, simple logic. Build simply with transaction scripts or active records.
- Generic: established solutions such as authentication, payments, messaging or search. Reuse libraries/SaaS behind an anticorruption layer (ACL).

Document the type in the context README or package docstring, e.g. `Core subdomain: pricing.` Do not force core-domain patterns onto supporting/generic code.

## 3. Choose logic, architecture and tests together

- Simple operations, ETL and integrations: Transaction Script in application, without a domain model; layered presentation -> application -> infrastructure; emphasize end-to-end tests (inverted pyramid).
- Simple CRUD plus validation: Active Record (data entity plus use case); layered architecture with an application layer; emphasize integration tests (diamond).
- Complex rules, invariants, financial calculations or processes: Domain Model with aggregates, value objects and events; ports/adapters (hexagonal/clean); emphasize domain unit tests (pyramid).
- Required auditability, history and reconstruction of past state: Event-Sourced Domain Model; ports/adapters plus CQRS; pyramid tests.

Record the decision in docs/adr/ or the context README. Different contexts in one service may use different patterns.

## 4. Bounded contexts and context maps

- A bounded context owns a consistent model and language. Use one Python package or service per context, with its own model and database tables/schema.
- Contexts must not import each other's domain types or directly read each other's tables. Communicate through published DTO/event/API contracts.
- Choose context-map relationships deliberately:
  - Partnership: teams coordinate changes closely.
  - Shared Kernel: a small, explicitly agreed shared model, usually value objects/IDs, changed jointly.
  - Customer-Supplier: downstream depends on upstream with agreed priorities.
  - Conformist: downstream adopts the upstream model.
  - ACL: infrastructure/acl/ adapters translate external, legacy or foreign models into local types.
  - Open Host Service + Published Language: stable versioned public API/event schemas separated from internal models.
  - Separate Ways: duplicate when integration costs more than duplication.
- Connect generic subdomains and external APIs only through ACLs; never expose external SDK types in the domain.
- Maintain docs/context-map.md when there is more than one context.

## 5. Tactical patterns

### Value objects

```python
@dataclass(frozen=True, slots=True)
class Money:
    amount: Decimal
    currency: Currency

    def __post_init__(self) -> None:
        if self.amount < 0:
            raise NegativeMoneyError(self.amount)

    def add(self, other: Money) -> Money:
        if other.currency != self.currency:
            raise CurrencyMismatchError(self.currency, other.currency)
        return Money(self.amount + other.amount, self.currency)
```

- Value objects are immutable (frozen=True), compare by value and validate themselves at construction so invalid instances cannot exist. Operations return new objects without side effects.
- Prefer Email, Money, Quantity and OrderId to primitive obsession. Typed IDs may use `type OrderId = UUID` or NewType.
- Put most domain logic in value objects when appropriate; they are the simplest to test.

### Entities and aggregates

```python
class Order:
    def __init__(self, order_id: OrderId, customer_id: CustomerId) -> None:
        self.id = order_id
        self.customer_id = customer_id
        self._lines: list[OrderLine] = []
        self._status = OrderStatus.DRAFT
        self._events: list[DomainEvent] = []

    @property
    def lines(self) -> Sequence[OrderLine]:
        return tuple(self._lines)

    def add_line(self, product_id: ProductId, quantity: Quantity, price: Money) -> None:
        if self._status is not OrderStatus.DRAFT:
            raise OrderAlreadyPlacedError(self.id)
        self._lines.append(
            OrderLine(product_id=product_id, quantity=quantity, price=price)
        )

    def place(self) -> None:
        if not self._lines:
            raise EmptyOrderError(self.id)
        self._status = OrderStatus.PLACED
        self._events.append(OrderPlaced(order_id=self.id, total=self.total()))

    def pull_events(self) -> list[DomainEvent]:
        events, self._events = self._events, []
        return events
```

- An entity has identity and a lifecycle; equality follows its ID.
- An aggregate groups entities/value objects under one root responsible for every invariant within the boundary.
- Change aggregates only through root methods named in the ubiquitous language. Expose internal collections read-only.
- Preserve aggregate invariants after every method. Coordinate aggregates through events and eventual consistency.
- One transaction changes one aggregate. If two aggregates appear to need one transaction, reconsider the boundaries or use an event.
- Reference other aggregates by ID, not object references. Keep aggregates small: include only what invariant enforcement requires.
- Field-only core-domain entities are anemic; move behavior out of use cases into the domain.
- Constructors/factories must enforce invariants and make invalid states unrepresentable.

### Domain services

Use stateless functions/classes in domain/services.py for domain policies or calculations that do not naturally belong to one entity/value object. Domain services know nothing about transactions, databases or external systems.

### Domain events

```python
@dataclass(frozen=True, slots=True, kw_only=True)
class OrderPlaced(DomainEvent):
    order_id: OrderId
    total: Money
```

- Use past-tense domain facts such as OrderPlaced or PaymentFailed.
- Events are immutable and carry aggregate ID, time and subscriber data.
- Aggregates collect events; application code pulls them with pull_events() and publishes after successful persistence.
- Publish separate, stable integration-event schemas (Published Language) outside a context, not domain classes.

### Repositories and factories

- One repository per aggregate root operates on the whole aggregate: get_by_id, add/save and domain-specific selections. Do not create repositories for nested entities.
- Define ports in application or domain and adapters in infrastructure. Split ports into roles such as OrderReader/OrderSaver where useful.
- For complex construction involving many invariants or multiple sources, use a root classmethod such as Order.create(...) or a domain factory.

## 6. Layers and dependency direction

```
presentation   -> application -> domain
infrastructure -> application -> domain
ioc / main      -> all layers
```

- Domain: aggregates, value objects, events, services and errors; stdlib only, no ORM/pydantic/frameworks or I/O.
- Application: commands/queries orchestrating load -> domain method -> save -> publish; owns orchestration, transactions and authorization, not domain rules in a domain-model design.
- Infrastructure: repositories, ORM mappings, ACLs, outbox and broker adapters.
- Presentation: HTTP/gRPC/CLI/consumer adapters translating transport input/output into application commands/queries.
- Wire ports to adapters only in ioc.py.
- Keep ORM and domain types separate. Map in repositories, or use explicitly chosen SQLAlchemy imperative mapping; the domain must not know its storage format.

## 7. CQRS and reads

- Commands mutate through aggregates and return at most an ID.
- Queries need not load aggregates: core contexts may use dedicated read models/direct database queries returning client-specific DTOs.
- Use event sourcing and projections only when requirements justify them.

## 8. Context integration and reliability

- Transactional Outbox: persist events with the aggregate in the same transaction; a separate process publishes to the broker. Do not publish directly from the use case before/after commit.
- Saga: a long-running cross-aggregate/context workflow with compensating actions. Process Manager: explicit persisted state and step routing for such a workflow.
- Make consumers idempotent using event-ID deduplication.
- Use ACL clients with timeouts for synchronous context calls; translate foreign errors into local ones.

## 9. Balance coupling

Evaluate each dependency by integration strength, distance and volatility:

- Strength, strongest to weakest: intrusive (private internals/shared tables), functional (shared business logic), model (shared domain model), contract (published contract only).
- Distance: function -> class -> module -> package/context -> service -> another team.
- Volatility: core subdomains change often; generic subdomains change less frequently.

Strong coupling belongs at short distances inside aggregates/modules (high cohesion). Across contexts/services, use contract coupling: DTOs, integration events and versioned APIs. Strong long-distance coupling is tolerable only to nearly stable generic components, still behind an ACL. Shared tables/databases between contexts are forbidden intrusive coupling.

## 10. Layout

```
src/<package>/
  <context>/                    # bounded context: ordering, billing, catalog...
    domain/
      <aggregate>.py            # aggregate root and its entities
      value_objects.py
      events.py
      services.py               # domain services
      errors.py                 # invariant violations
    application/
      commands/                 # write use cases
      queries/                  # read use cases
      ports.py                  # repositories, UnitOfWork, Clock, IdGenerator, external services
      dto.py
      errors.py
    infrastructure/
      orm.py                    # context tables/ORM models
      repositories/
      acl/                      # external system/context adapters
      outbox.py
    presentation/
      http/  grpc/  consumers/
  shared_kernel/                # explicitly agreed shared kernel only
  ioc.py
  main.py
tests/<context>/{domain,application,infrastructure,presentation}/
```

Omit the context/ level for a single-context project. Supporting transaction-script contexts may omit domain/. Domain modules must not import other contexts except the explicitly agreed shared_kernel.

## 11. Avoid

- Anemic core models with all behavior in use cases, or full tactical DDD in simple supporting/generic contexts merely for uniformity.
- One oversized aggregate per context; direct references to other aggregate objects; cross-aggregate transaction mutations.
- Domain classes in public APIs or external message schemas; shared tables/ORM models across contexts.
- External SDK, ORM or pydantic types in domain/.
- Generic names outside ubiquitous language: Manager, Helper, Processor, Data, Info, handle().

## 12. New-feature checklist

1. Identify the business operation and its name in the context language.
2. Identify the context/subdomain and choose the logic pattern using section 3.
3. Identify the aggregate owning each invariant; decide whether a new aggregate, value object or event is needed.
4. Implement behavior in aggregate/value-object methods or domain services, with domain errors for invariant violations.
5. Orchestrate in application: load -> domain method -> save -> publish; use outbox for external events.
6. Add repository/ACL ports and adapters; wire them in ioc.py.
7. Add the presentation adapter and map domain/application errors to transport status codes.
8. Integrate other contexts through contracts/events, never domain-model imports.
9. Match tests to the selected pattern; for domain models, start with aggregate/value-object unit tests without mocks or databases.
10. Add a schema migration when persistence changes.
