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

Both apps currently run without environment variables. The examples reserve
settings for future backend and database integration; they do not connect a
database or configure API requests by themselves.

When configuration is needed, copy the appropriate example from the repository root:

```bash
cp .env.example .env
cp frontend/.env.example frontend/.env.local
cp backend/.env.example backend/.env
```

Next.js loads `frontend/.env.local` automatically. Values prefixed with
`NEXT_PUBLIC_` are exposed to the browser, so use them only for public settings.
For backend commands that need local values, use:

```bash
cd backend
uv run --env-file .env fastapi dev
```

The root PostgreSQL values are development examples for future infrastructure.
There is no database service configured yet.

## Commit hooks

No commit hooks are enabled. Hooks are scripts Git runs automatically, such as
running lint before allowing a commit. For now, run the checks above manually
before committing. Hooks can be added later when the checks and workflow are settled.
