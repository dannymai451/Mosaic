# Conventions supported by the current code

## Files and examples

- Next.js route files use `src/app/<route>/page.tsx`; layout and global CSS live
  at the app root. Types and small components currently live in page files.
  Read the relevant installed Next.js guide before frontend framework changes.
- Shared handles use `src/app/[handle]/page.tsx` for `/@username`. In the installed
  Next.js version, browser checks observed `%40username` in the route parameter.
  Decode safely before validating; verify both literal `@` and `%40` URLs in a
  running app. A successful build alone does not verify route behavior.
- Python module/function names use snake_case, models/schema classes PascalCase.
  `.editorconfig` specifies UTF-8/LF, two spaces generally and four for Python.
- Backend modules import `app.*` and commands run from `backend/`. Alembic's
  active directory is `migrations/` as configured by `alembic.ini`.
- Frontend alias `@/*` maps to `src/*`; no feature-folder convention exists yet.

## Persistence and HTTP

Preferred transaction example: `backend/app/services/accounts.py`. Accept a
fresh AsyncSession, begin the operation transaction at the caller, and use
repository functions. Repositories flush or execute, never control transactions.
Preferred repository examples: `backend/app/repositories/profiles.py` and
`spotify_connections.py`. PostgreSQL conflict clauses are already used for upserts.

Register new models through `backend/app/models/__init__.py` so Alembic sees their
metadata. Add a migration for schema changes and review generated SQL. Do not
replace migrations with runtime `create_all`; its current use is test scaffolding.

Preferred owner-update example: `backend/app/api/routes/profiles.py` and
`schemas/profile.py`. Use Cookie/Depends for owner identity, reject unknown
request fields, validate partial patches, and handle database uniqueness races.
PATCH request keys use snake_case; existing owner responses use `displayName`.
Copy the current API contract until a task explicitly changes it.

Session digests belong in `repositories/sessions.py`; encrypt refresh tokens in
the service before persistence. Owner responses must not contain Spotify tokens.
Use explicit HTTP status errors, OAuth error redirects, and frontend status-aware
fetch handling. The settings loading effect is the preferred abort/retry example.
For Spotify integration, copy `api/routes/albums.py`, the shared owner/Spotify
dependencies in `api/dependencies.py`, and `services/spotify.py`: normalize provider payloads, keep access tokens server-side,
commit encrypted refresh-token rotation before subsequent reads, and return safe
error codes. `/me/library/contains` replaces the deprecated album-specific
membership endpoint. Mosaic presets are coordinate maps in `services/mosaic.py`;
owner writes in `api/routes/mosaics.py` lock the profile before the mosaic and
replace the validated complete tile list in one transaction. Copy that lock order
for changes that touch both the selection and layout. Avoid copying the inactive
health router as implemented infrastructure; see ARCHITECTURE's debt section.

## Configuration and generated files

Application settings live in `backend/app/core/config.py`. Migration settings are
intentionally separate, requiring only DATABASE_URL. Frontend API URL is currently
repeated in pages via `NEXT_PUBLIC_API_BASE_URL`; there is no shared config module.
Only public settings belong under `NEXT_PUBLIC_`. Commit `.env.example` files,
never real `.env` files. Use `127.0.0.1` consistently in the local browser flow.
Next's development origin allowlist in `frontend/next.config.ts` explicitly includes
`127.0.0.1`, since `npm run dev` starts with `localhost` by default. Without this,
Next blocks the dev HMR endpoint and client pages can remain on their initial
loading screen. Verify local sign-in using the documented host after config changes.

Do not hand-edit `.next/`, `next-env.d.ts`, `*.tsbuildinfo`, virtual environments,
or dependency directories. Regenerate lockfiles with npm/uv only when dependencies
change. `frontend/AGENTS.md` has a Next-managed block; preserve it and keep project
instructions above it. Ruff explicitly treats `alembic` as third-party so a local
directory of that name cannot change import classification.

## Tests

Use existing pytest/TestClient/respx patterns rather than introducing a framework.
`backend/tests/test_profile_update_api.py` demonstrates API regression scenarios;
`test_persistent_auth.py` demonstrates persistence and HTTP mocks. Prefer tests of
observable behavior/failure modes over coverage-only or implementation-mirroring
tests. Live Spotify login and preview UI still need manual checks in FEATURE_MAP.

For native album-detail dialogs, also check the development server: React Strict
Mode repeats effect setup/cleanup. A queued close event from cleanup must not
discard a dialog that has already reopened. The reproducible check is in
[Phase 4 verification](phase-4-verification.md#browser-golden-path).

## Verification

Install once (or after changing lockfiles): `npm ci` from frontend and
`uv sync --locked` from backend. Start Docker; PostgreSQL 18 may be pulled on first
run. Then from the repository root, in PowerShell or a POSIX shell:

```sh
uv run --project backend --locked python scripts/verify.py
```

The Python wrapper resolves paths from itself and uses `npm.cmd` on Windows.
It runs, in order: static boundary checks; Ruff on backend/root scripts; frontend
ESLint; TypeScript including Next route type generation; Next production build;
the backend suite in a disposable PostgreSQL 18 container. It stops on failure,
returns nonzero, and has no interactive prompts. A failed Docker startup is a
failure, not permission to silently skip integration coverage. It never migrates
the development database. Container/database cleanup runs on test failures too.
The DB runner uses a temporary JUnit report to reject skipped/empty suites and
disables pytest's disk cache (some existing Windows caches are inaccessible).

Targeted development checks remain `npm run lint`, `npm run typecheck`,
`npm run build` from frontend, and `uv run --locked ruff check .` /
`uv run --locked pytest -ra` from backend. Direct pytest without TEST_DATABASE_URL
skips integration tests; it is not the full completion check. There is no backend
type checker, global formatting gate, or frontend behavior test suite. The full
command is currently small enough to avoid a separate fast/full system.

## Hard guardrails

`scripts/check_boundaries.py` uses Python's AST, runs in the standard verifier,
and has negative/positive fixture tests in `backend/tests/test_agent_guardrails.py`.

1. **No upward imports:** files under `backend/app/models`, `repositories`, and
   `schemas` cannot statically import `app.api` or `app.services`. Checks include
   absolute imports, aliases, `from app import ...`, and relative imports. This
   keeps data/schema layers reusable without coupling them to HTTP orchestration.
2. **Caller-owned transactions:** repository calls to `.commit()`, `.rollback()`,
   `.begin()`, or `.begin_nested()` are rejected. Repositories have no other
   objects needing those operations today. This protects atomic multi-row
   operations already tested in `test_repositories.py`.

This is a small syntax check, not a dependency-analysis framework: dynamic imports,
indirect calls, and transaction aliases are not traced. Tests and code review still
matter. Services, routes, seed scripts, and tests can own transactions. No blanket
ban on route-to-repository calls or arbitrary new feature boundaries is imposed.
