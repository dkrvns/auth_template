# Code quality and security review

Apply when changing code, dependencies, configuration, Docker or infrastructure, and before deployment. Match review depth to risk: small changes do not need a full pentest, but authorization, payments, secrets, external requests and agent actions require focused security review.

## 1. Understand the context

- Read applicable project instructions and inspect the Git working tree.
- Identify intended behavior, affected components and potential regressions.
- State critical invariants, expected data/load limits and failure behavior before implementation; use existing architecture and add patterns only when justified.
- Trace the complete changed flow: input -> validation -> business logic -> persistence -> external actions -> user response.
- Consider actual startup/deployment settings; a correct function does not prove the application works correctly.

## 2. Review behavior

Check requirement compliance; state transitions and errors; empty, invalid, oversized and repeated input; timeouts, cancellation, dependency outages and partial success; concurrency and retries; compatibility with existing data and migrations.

Distinguish an attempted external action from confirmed success. Never automatically repeat an action that may already have completed.

## 3. Check security boundaries

- Enforce server-side authorization for every protected action and object, including tenant scope. Hidden controls and unpredictable IDs are not access control.
- Parameterize SQL, pass subprocess arguments without shell interpolation, and escape HTML for its output context.
- Check file access, uploads, paths and access outside the allowed filesystem scope.
- Validate external URLs and redirects against access to internal services; account for DNS, IPv6 and browser network requests.
- Check request sizes, rate limits and resource consumption.
- Check network exposure of APIs, databases and management interfaces, process privileges and access to secrets.
- Keep secrets out of Git, images, API responses, reports and logs. Show discovered values only in redacted form.
- Never weaken security to fix an integration: allowlist credentialed CORS origins, use established password hashing, and protect browser sessions against XSS/CSRF. Keep backend credentials out of client bundles.
- Verify new packages against trusted upstreams, check license compatibility and known vulnerabilities, and preserve reproducible lockfiles; package existence alone does not establish trust.

### Operational diagnostics

- Use structured logs and correlation IDs across requests, jobs and external calls; record failures without secrets or sensitive payloads.
- For changed production paths, expose relevant request rates, errors, p95/p99 latency and resource saturation through existing telemetry. Avoid high-cardinality metric labels.

## 4. Review AI features

- Treat website, vacancy and file contents and tool outputs as untrusted data.
- Test attempts to override agent instructions, retrieve secrets, expand privileges or act without required approval.
- Enforce critical restrictions through code, tool permissions and isolation; a system prompt alone is insufficient.
- Verify model-output accuracy and confirmation of external actions.
- Bound context, model calls, retries and execution time; persist completed results for reuse.
- Do not enable paid APIs or additional credits without explicit permission. Never bypass service limits or safeguards.

## 5. Run appropriate automated checks

For Python, use uv and the project's formatting, linting and test commands. Additionally check applicable surfaces:

- Source code: a static analyzer such as Semgrep Community Edition.
- Secrets, including Git history: Gitleaks.
- Python dependencies: pip-audit.
- Container images: Grype.
- Running APIs: ZAP in a dedicated test environment.

Use trusted tool sources and pinned versions. Prefer local, free modes that do not require source-code uploads. Validate scanner findings before treating them as confirmed vulnerabilities.

## 6. Test behavior, not implementation details

- Add meaningful tests for substantial behavior changes and bug fixes.
- Cover both permitted actions and rejection of forbidden actions.
- Use the production database/queue technologies in isolated integration tests.
- Mock external boundaries and failures, but do not treat mocks as proof that real integrations work.
- Avoid tests that merely mirror implementation or lock in incidental details.
- Passing tests do not replace security review or validation of the user workflow.

## 7. Control pentest execution

Run active scans and exploitation only within explicitly authorized boundaries. Use a separate application copy, disposable data and test accounts. Disable real messages, job applications, payments and other external actions unless their testing is separately authorized.

Enforce isolation technically, not just through agent instructions. Define load/time limits and stop conditions before execution.

## 8. Report concrete results

- For each significant finding, provide priority, code location, trigger conditions, impact, evidence, fix and verification method.
- Separate confirmed defects from hypotheses/recommendations. List incomplete checks and their reasons.
- Rerun affected checks after fixes. Never hide failures by disabling tests/rules or suppressing exceptions.
- Do not report full completion while required checks remain undone. Fix confirmed critical/high-risk issues before deployment, or explicitly present them to the user for a risk-acceptance decision.
