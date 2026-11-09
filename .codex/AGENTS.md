# Project rule index

Rule files live in [python-rules/](python-rules/), relative to this index. Read the complete applicable files before work. User instructions and project-specific requirements take precedence over general guidance.

- Every Python task: [00 - Setup and tooling](python-rules/00-python-project-setup.md) and [07 - Git workflow](python-rules/07-git-workflow.mdc).
- Reading or editing Python: [01 - Code style](python-rules/01-python-code-style.md).
- Backend/business-logic design or changes: [02 - DDD and architecture](python-rules/02-clean-architecture.md).
- Domain, application and DI responsibilities, regardless of paths: [03 - Domain and application](python-rules/03-domain-application.md).
- Infrastructure, migrations, database clients and configuration: [04 - Infrastructure](python-rules/04-infrastructure-db.md).
- Presentation, API, startup and transports: [05 - Presentation](python-rules/05-presentation-api.md).
- Changing behavior or writing/modifying tests and fixtures: [06 - Testing](python-rules/06-testing.md).
- Code, dependency, configuration, Docker/infrastructure changes and deployment: [08 - Quality and security review](python-rules/08-code-review-security.md).

Read multiple rules for cross-cutting tasks. Apply Python-specific rules only to Python projects, including Python components of mixed repositories. Run example commands only when relevant to the task. If a referenced file is unavailable, report it; never claim unread instructions were loaded.
