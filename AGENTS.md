# Project instructions

Read [.codex/AGENTS.md](.codex/AGENTS.md) and the applicable complete rule files.

Imports in existing tests and test fixtures may be updated without additional
permission. Do not change test or fixture logic without the user's explicit
permission, including assertions, test data, mock behavior and test coverage.
Keep formatting and lint fixes in test files limited to import changes.

Group state-changing business operations in application/commands/<area>/ and
atomic application actions in application/interactors/<area>/; avoid generic
use_cases modules. Authentication and registration belong to infrastructure/auth:
group handlers by responsibility and keep token issuance there.
Application must never import infrastructure, including through compatibility shims.
Import from the defining modules directly; do not add import-only compatibility
modules or re-export aggregators to preserve obsolete import paths.
Use gateway terminology for database access in this project; keep each gateway
implementation in its own infrastructure/gateways module. Transaction committers
and rate limiters belong in separate modules rather than gateway aggregators.
User and session gateway implementations must explicitly implement their contracts
from infrastructure/interfaces/gateways. Preserve narrow application ports where
consumers only need a subset of the gateway operations.
Do not add @override decorators to gateway implementations.
