# Project instructions

Read [.codex/AGENTS.md](.codex/AGENTS.md) and the applicable complete rule files.

Do not modify existing tests or test fixtures without the user's explicit permission.
This includes automatic formatting and lint fixes in test files.

Group state-changing business operations in application/commands/<area>/ and
atomic application actions in application/interactors/<area>/; avoid generic
use_cases modules. Authentication and registration belong to infrastructure/auth:
group handlers by responsibility and keep token issuance there. The existing
application/use_cases.py is a compatibility shim for frozen test imports only.
