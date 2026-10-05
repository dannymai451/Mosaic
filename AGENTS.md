# Working in Mosaic

## Before changing code

- Read [README.md](README.md) for setup and commands.
- Read [architecture](docs/ARCHITECTURE.md) for layer/data changes and the relevant
  [feature map](docs/FEATURE_MAP.md) section for product behavior.
- Consult [conventions](docs/CONVENTIONS.md) and search for a similar implementation.
  Extend an established pattern before inventing one.
- Frontend work also follows [frontend/AGENTS.md](frontend/AGENTS.md), including
  the installed Next.js documentation requirement.

## Scope and architecture

Make the smallest coherent change. Avoid unrelated refactors, moves, renames,
library replacements, speculative abstractions, and unnecessary dependencies.
Search for existing infrastructure first. Follow the documented boundaries;
repositories flush writes and callers own transactions. Never expose Spotify
tokens through browser responses. Keep real environment files and generated
output out of Git. Report unrelated debt instead of fixing it automatically.

## Workflow

- **Feature:** read relevant context, find an example, implement a small slice,
  verify, fix relevant failures, report.
- **Bug:** establish evidence/reproduction, trace the execution path, form a
  code-backed hypothesis, apply the smallest fix, add regression coverage when
  useful, verify. Do not guess at root causes.
- **Large feature:** use independently verifiable vertical slices.
- **Broad architectural change:** first describe current state, problem,
  constraints, proposal, alternatives, migration, and risks; stop for human
  review before migration unless implementation was explicitly authorized.

## Verification

From the repository root, after installing dependencies as described in README:

```sh
uv run --project backend --locked python scripts/verify.py
```

This runs static guardrails, Ruff, frontend lint/type checking/build, and the
backend suite against disposable PostgreSQL. Docker must be running. It fails
on errors or skipped backend tests; plain pytest with skipped database tests
is not full verification. See [verification details](docs/CONVENTIONS.md#verification).
Investigate failures, distinguish baseline problems from your change, and fix
relevant causes. Do not hide failures or disable checks to obtain a pass.

## Improve the system after a failure

Fix the immediate mistake first. Missing context calls for improving the relevant
architecture/feature/conventions document; missing verification calls for a test
or reproducible check; repeated boundary violations may justify a cheap static
constraint. A one-off implementation mistake usually needs only its fix. Do not
turn isolated incidents into global rules.

## Completion report

Report what changed and why, important files, verification command/result,
remaining uncertainty, and relevant debt intentionally left unchanged.
