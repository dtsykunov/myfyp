# AGENTS.md

This file defines working rules for AI agents and human contributors in this repository.

## Project Context (from README)

- Project: `For Us Page`
- Purpose: Share a snapshot of a user's YouTube recommendations via a temporary link.
- User flow:
  1. User opens YouTube and triggers `Share Recommendation Page` in the extension.
  2. Extension generates a URL in the format `https://<domain>/<hash>`.
  3. Recipient opens the link and sees the captured recommendations.
- System flow:
  1. Extension parses YouTube homepage recommendations and creates a JSON payload.
  2. API stores payload in SQLite and returns a unique `hash`.
  3. Frontend route `/<hash>` fetches payload and renders plain HTML.
- Data retention rule: recommendation snapshots expire after 7 days and must be deleted.
- Current stack: browser extension + Python/FastAPI API + SQLite + plain HTML frontend.
- Architectural intent: minimal pipeline (`extension -> API -> SQLite -> HTML render`).

## Engineering Rules

1. Use idiomatic patterns for each language/framework in this repository.
2. Apply strong design principles, but do not overengineer. Prefer simple, maintainable solutions.
3. Keep everything testable:
   - Design code with clear seams for unit/integration testing.
   - Add or update tests for behavioral changes.
4. Keep coupling low:
   - Minimize cross-module dependencies.
   - Prefer explicit interfaces/contracts over implicit coupling.
5. Keep extension, API, and frontend isolated from each other:
   - No leaking internal implementation details across boundaries.
   - Communicate only through stable contracts (e.g., payload schemas, HTTP API).
6. Use current stable software versions (baseline year: 2026):
   - Prefer modern, actively maintained dependencies.
   - Avoid introducing deprecated libraries/patterns.
7. AI agents may commit code only when all quality gates pass:
   - Configure commit identity with agent name and email.
   - Sign commits with name/email (`git commit -s`).
   - Use clear, comprehensible commit messages describing the change.
   - Ensure linting and tests pass before committing.

## Task Execution Protocol (Required)

For each non-trivial task, the agent must follow this sequence:

1. Understand user intention:
   - Confirm what the user wants to achieve.
   - Ask clarifying questions when requirements are ambiguous.
2. Analyze:
   - Inspect the current codebase and existing changes.
   - Determine feasible implementation options and constraints.
3. Research:
   - Use reliable sources (including web research when needed) to verify current best practices and latest solutions.
4. Analyze and plan:
   - Synthesize findings into a concrete implementation plan.
   - Create explicit TODOs for execution.
5. Ask for plan approval:
   - Present the proposed plan to the user and confirm it is acceptable before implementation.
6. Implement:
   - Execute the approved TODOs.
   - Run required checks (tests, lint, formatting, type checks where applicable).
   - Do not mark tasks done until all TODOs are completed and checks pass.
7. Commit:
   - Commit only after successful checks.
   - Follow commit rules in this file (identity, signing, clear message).

## Definition of Done for Agent Changes

- Behavior matches requirements.
- Tests added/updated and passing.
- Lints/format checks passing.
- Boundaries between extension/API/frontend remain clean.
- No unnecessary complexity added.
