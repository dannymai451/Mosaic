# Mosaic

Showcase your taste through Mosaic!

## Repository layout

| Folder | Purpose |
| --- | --- |
| `frontend/` | Next.js App Router app with TypeScript and Tailwind CSS. |
| `backend/` | FastAPI app with a health endpoint and pytest tests. |
| `infrastructure/` | Reserved for deployment and service configuration. |
| `docs/` | Reserved for project documentation. |

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
docker compose exec db pg_isready -U album_mosaic -d album_mosaic
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

Open http://localhost:3000.

In a second terminal, from the repository root:

```bash
cd backend
uv sync --locked
uv run fastapi dev
```

The API runs at http://localhost:8000. Interactive API documentation is at
http://localhost:8000/docs, and the health endpoint is `/api/health`.

## Run checks

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
Copy the checked-in example to create it. For future app configuration, copy the
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
