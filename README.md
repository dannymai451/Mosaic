# Mosaic

Showcase your taste through Mosaic!

## Repository layout

| Folder | Purpose |
| --- | --- |
| `frontend/` | Next.js App Router app with TypeScript and Tailwind CSS. |
| `backend/` | FastAPI API, PostgreSQL persistence, migrations, and pytest tests. |
| `scripts/` | Repository verification and static architecture checks. |
| `docs/` | Architecture, feature map, conventions, and acceptance instructions. |

AI coding agents start with [AGENTS.md](AGENTS.md). See
[current architecture](docs/ARCHITECTURE.md), [feature map](docs/FEATURE_MAP.md),
and [conventions](docs/CONVENTIONS.md) for durable project context.

## Requirements

- Node.js 20.9 or newer and npm.
- Python 3.14 or newer and [uv](https://docs.astral.sh/uv/getting-started/installation/).
- [Docker Desktop](https://docs.docker.com/desktop/) or Docker Engine with Compose.

## Start the local database

From the repository root, create your local environment file if you haven't already:

```bash
cp -n .env.example .env
```

Docker Compose reads `.env` to configure PostgreSQL. The checked-in example uses
development-only credentials. Keep your actual `.env` file private.

Start the database in the background:

```bash
docker compose up -d db
```

Check whether it is ready:

```bash
docker compose ps
docker compose exec db pg_isready -U mosaic -d mosaic
```

The database listens on port `5432` by default. Its data is kept in the named
`postgres_data` volume when the container is stopped or recreated. To stop the
database while keeping its data, run:

```bash
docker compose stop db
```

Start it again with `docker compose up -d db`. To remove the container and
network, run `docker compose down`; the named database volume remains. Removing
the volume with `docker compose down -v` permanently deletes the local database.

## Run locally

In a terminal, from the repository root:

```bash
cd frontend
npm ci
npm run dev
```

Open http://127.0.0.1:3000. Use `127.0.0.1` consistently for the frontend,
API, and Spotify callback: current CORS allows that frontend origin only.

In a second terminal, from the repository root:

```bash
cd backend
uv sync --locked
uv run fastapi dev
```

The API runs at http://127.0.0.1:8000. Interactive API documentation is at
http://127.0.0.1:8000/docs, and the health endpoint is `/api/health`.
Copy `backend/.env.example` to `backend/.env` and configure its settings first;
the API loads them at import. Apply migrations before using authenticated routes.

## Run checks

After installing both dependency sets, from the repository root with Docker running:

```bash
uv run --project backend --locked python scripts/verify.py
```

This is the standard completion check: architecture guardrails, backend Ruff,
frontend lint/type checking/build, and the entire backend suite with disposable
PostgreSQL 18. It stops on failures and rejects skipped backend tests. It does not
use your development database. See [verification details](docs/CONVENTIONS.md#verification).

For targeted checks while developing:

From `frontend/`:

```bash
npm run lint
npm run typecheck
npm run build
```

From `backend/`:

```bash
uv run pytest
uv run ruff check .
```

## Database migrations

Alembic manages the PostgreSQL schema for `users`, `spotify_connections`,
`sessions`, and `profiles`. Start the local database, then from `backend/`:

```bash
cp -n .env.example .env
uv sync --locked
uv run alembic upgrade head
```

Set `DATABASE_URL` in `backend/.env` to a `postgresql+asyncpg://` URL matching
your database credentials and port. An exported `DATABASE_URL` takes precedence.
Alembic loads this file automatically and does not require Spotify credentials.

After changing models, generate and review a migration before applying it:

```bash
uv run alembic revision --autogenerate -m "describe schema change"
uv run alembic upgrade head
uv run alembic check
```

`alembic check` verifies that the database schema matches the models. To preview
upgrade SQL without connecting, run `uv run alembic upgrade head --sql`.
To roll back the most recent migration, run `uv run alembic downgrade -1`;
rolling back the initial migration drops all four tables and their data.

## Phase 2 persistence and local fixture

The database enforces unique `users.spotify_account_id` and `profiles.username`
values with named constraints. Usernames use PostgreSQL's case-sensitive string
comparison. The new migration names the constraints already created by the
initial migration; it preserves existing data.

Repository functions in `backend/app/repositories/` accept an `AsyncSession`.
They flush writes without committing. Callers wrap related changes in
`async with db.begin()` so failures roll back the entire operation.
`create_user_with_profile` in `app.services.accounts` owns that transaction and
requires a fresh session with no active transaction. Session repositories store
SHA-256 token digests and reject expired sessions; Spotify connection repositories
accept already-encrypted refresh tokens.

After migrating, seed the local development fixture from `backend/`:

```bash
uv run python -m app.db.seed --local
```

This creates the private profile `mosaic_local_test` (`Local Test User`) linked to
Spotify account ID `mosaic-local-test-user`. Repeating the command preserves
profile edits and creates no duplicate rows. It targets your configured
`DATABASE_URL`; use your local development database. It does not create a Spotify
connection or a login session. OAuth callbacks atomically upsert the user and Spotify connection, create a
profile on first login, and persist a hashed session. Refresh tokens are encrypted
with `TOKEN_ENCRYPTION_KEY`; `/api/me` and logout use PostgreSQL. Sessions survive
backend restarts until their one-hour expiry. Repeat login preserves profile edits.

Validate the migration and run the tests from `backend/`:

```bash
uv run alembic upgrade head
uv run alembic check
uv run python scripts/verify_phase2.py
```

The verification script starts a disposable PostgreSQL 18 container, creates a
blank test database, applies Alembic migrations, runs all tests, and cleans up.
It requires Docker and does not use your development database. Direct `pytest`
runs require `TEST_DATABASE_URL` with a role allowed to create databases; otherwise
database-dependent tests are skipped. They verify identity uniqueness,
atomic rollback, profile updates, connection upserts, session hashing/expiry/logout,
and seed idempotency. The existing health and OAuth tests also run. See
[Phase 2 acceptance verification](docs/phase-2-verification.md) for setup and the
manual browser checklist.

## Phase 3 profile editing and sharing

Open `/settings/profile` while signed in to preview and save username, display
name, bio, visibility, and theme. Save as public to enable View public profile,
Share profile, and Copy link. Shared URLs use `/@username` and work signed out.
Private or missing profiles return the same unavailable page; switching back to
private prevents subsequent public reads. Renaming changes the shared URL.

GET `/api/profiles/{username}/public` returns only public profile fields; the
existing PATCH `/api/me/profile` remains owner-only. Album/mosaic editing belongs
to later phases. See [Phase 3 acceptance verification](docs/phase-3-verification.md)
for the criteria, coverage, and browser checklist.

## Shared setup files

- `.editorconfig` gives supporting editors consistent whitespace settings:
  two spaces by default, four for Python, UTF-8, and a final newline.
  Editors without built-in support may need an EditorConfig extension.
- `.gitignore` keeps dependencies, generated files, caches, and local environment
  values out of Git. It does not remove files already tracked by Git.
- `.env.example` files document configuration names and safe example values.
  Commit examples; keep actual `.env` and `.env.local` files local.
- This README explains how to install dependencies, run the apps, and run checks.

## Environment variables

Compose reads the root `.env` file to configure the local PostgreSQL container.
Copy the checked-in example to create it. For application configuration, copy the
appropriate example:

```bash
cp -n .env.example .env
cp -n frontend/.env.example frontend/.env.local
cp -n backend/.env.example backend/.env
```

Next.js loads `frontend/.env.local` automatically. Values prefixed with
`NEXT_PUBLIC_` are exposed to the browser, so use them only for public settings.
For backend commands that need local values, use:

```bash
cd backend
uv run --env-file .env fastapi dev
```

The backend reads its settings from environment variables or `backend/.env`.
Its database engine and Alembic use `DATABASE_URL`; Spotify authentication also
requires the Spotify and frontend settings in the backend example.

## Commit hooks

No commit hooks are enabled. Hooks are scripts Git runs automatically, such as
running lint before allowing a commit. For now, run the checks above manually
before committing. Hooks can be added later when the checks and workflow are settled.
