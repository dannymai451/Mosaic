# Current architecture

## System overview

Mosaic is an early music-profile application. Implemented product behavior is
Spotify sign-in, persistent owner sessions, an owner dashboard, profile previews,
profile saving, read-only public profile sharing, saved Spotify album browsing,
and persistent owner Featured Album selection, a mosaic editor with four coordinate
presets, atomic layout saves, and public active mosaics. `services/spotify.py`
implements token refresh/library/catalog reads; `services/mosaic.py` implements
preset expansion and album placement validation. The project-plan PDF describes
the roadmap; this MVP supports one saved mosaic per profile.

- `frontend/`: Next.js 16.3.8 App Router, React 19.2.8, TypeScript with strict
  checking, Tailwind CSS 4. npm and `package-lock.json` pin the installed graph.
- `backend/`: Python >=3.14, FastAPI, SQLAlchemy async sessions with asyncpg,
  Alembic, Pydantic settings/validation, httpx for Spotify HTTP, Fernet encryption.
  uv and `uv.lock` manage dependencies. Locked versions are the source of truth.
- `compose.yaml`: PostgreSQL 18 only. Application servers run on the host.

## Directory responsibilities

| Location | Responsibility |
| --- | --- |
| `frontend/src/app/` | Route pages, root layout, global CSS; components/types are mostly colocated in pages. |
| `frontend/src/styles/tokens.css` | Tailwind theme tokens; pages currently also use hardcoded utility colors. |
| `backend/app/main.py` | FastAPI creation, router registration, CORS, active health endpoint. |
| `backend/app/api/routes/` | HTTP/authentication orchestration, owner updates, and public profile reads. |
| `backend/app/services/` | Account/login transactions, Spotify refresh/library integration, mosaic preset expansion and validation. |
| `backend/app/repositories/` | Async persistence functions accepting a caller-provided session. |
| `backend/app/models/` | Five SQLAlchemy models; `__init__.py` registers them together. |
| `backend/app/schemas/` | Profile PATCH validation and normalized album/selection contracts. |
| `backend/app/db/` | Declarative base, engine/session dependency, local seed and connectivity commands. |
| `backend/app/core/config.py` | Application environment settings instantiated at import. |
| `backend/migrations/` | Alembic environment and versioned schema. |
| `backend/tests/` | pytest HTTP, migration, persistence, and guardrail checks. |
| `backend/scripts/verify_phase2.py` | Disposable PostgreSQL suite runner. |
| `scripts/` | Repository verification entry point and small static boundary checker. |
| `docs/` | Architecture, product map, conventions, persistence acceptance checklist. |

There is no shared frontend API client, generic component library, shared
cross-language types, or implemented `infrastructure/` directory.

## Dependency direction and boundaries

Browser pages use HTTP endpoints with `credentials: "include"` for owner requests.
They do not access PostgreSQL or backend Python directly. The landing page is a
server-rendered page; connect/dashboard/settings are client components.

The observed backend path is:

```text
main -> API routes -> services and/or repositories -> models -> db.base
                   -> request schemas
db.session -> core.config
migrations -> models + db.base
```

Routes may call repositories directly: `api/routes/profiles.py` owns its update
transaction, and `api/routes/auth.py` owns logout. Do not impose a service-only
route rule. Spotify HTTP exchange currently lives in the auth route.

Models, repositories, and request schemas must not import API or services.
Repositories leave transaction control to callers so multi-row operations remain
atomic. The static checker enforces these two rules; its exact scope and limits
are in [conventions](CONVENTIONS.md#hard-guardrails).

## Patterns to copy

- Transaction ownership: `services/accounts.py::create_user_with_profile` uses
  `async with db.begin()` on a fresh session. Repository writes flush/execute
  without committing (`repositories/profiles.py`, `repositories/users.py`).
- Idempotent identity linking: `services/auth.py::persist_login` calls PostgreSQL
  upserts, retains profile edits on repeat login, encrypts refresh tokens, and
  creates a new opaque session token. `repositories/sessions.py` stores/queries
  only its SHA-256 digest and checks expiry.
- Owner identity comes from the session cookie, never a request-body user ID.
  See `api/routes/profiles.py` and `schemas/profile.py`; the schema rejects extra
  fields and explicit nulls and supports partial updates.
- Async DB injection: `db/session.py::get_db`, with `Depends(get_db)` in routes.
  Startup creates an engine but does not apply migrations automatically.
- Frontend request cancellation/retry: the loading effect in
  `frontend/src/app/settings/profile/page.tsx` aborts on unmount and times out.

## State management

Frontend state uses React `useState`/`useEffect`, with no global store or query
library. Settings keeps separate saved, draft, and preview states; refresh/navigation
loses unsaved changes. Saves send changed fields only and retain drafts on failure.
Public reads use a server page and uncached API fetch, with a small client sharing
component. The shared card/theme presets also supply the settings preview.
The builder uses the same saved/draft pattern, with up to 50 local undo snapshots,
click/keyboard placement, and server-supplied preset coordinates. One shared CSS
Grid canvas renders both editable and public layouts from device-independent
coordinates. Public canvases expose only album detail/Spotify links. Album metadata
loads sequentially per unique ID and remains ephemeral; failure stops further reads
and exposes retry while preserving the saved layout.
Connect reads the `error` URL query with Next's
`useSearchParams` behind a Suspense boundary. Dashboard
loads `/api/me`, displays errors, and POSTs logout before returning home.

Authentication state resides in PostgreSQL plus the HttpOnly `mosaic_session`
cookie (one-hour lifetime). OAuth uses a ten-minute state cookie, validates it
with constant-time comparison, then deletes it. Tokens are not put in browser
storage or owner DTOs. Local cookies currently have `secure=False`. Public profile
reads require no cookie and return an allowlisted DTO only when saved visibility
is public.

## Data access and configuration

The album picker at `/settings/albums` keeps separate saved/draft ID lists and
ephemeral normalized metadata. It loads 20 albums at a time, deduplicates appended
pages, retains drafts when saves or library reads fail, and resolves off-page
selected album details on demand. Native dialog semantics provide focus trapping
and Escape dismissal. Retrying library reads does not replace a pending selection.

Album/mosaic routes share session-derived owner identity in `api/dependencies.py`.
The shared Spotify context owns a short
transaction to lock the connection, refresh access, and persist encrypted rotated
refresh tokens before making library requests. A Spotify 401 gets one refresh/retry;
429 returns immediately with a sanitized Retry-After header exposed through CORS.
Access tokens live only in the request's service object. This initial implementation
refreshes per Spotify-backed request rather than adding a shared token cache.

Tables are `users` (unique Spotify account ID), `profiles` (one per user, unique
case-sensitive username), `spotify_connections` (one encrypted refresh token per
user), and `sessions` (digest, user ID, expiry). Profiles include avatar, bio,
private/public visibility, mutable JSONB theme, and an ordered JSONB
`featured_album_ids` list (default empty). Only selected Spotify IDs are persisted,
with up to 100 unique IDs allowed by the owner API; catalog metadata is not stored.
Newly added IDs are checked against Spotify's `/me/library/contains` in batches of
40 URIs; existing selections can be retained/removed after being unsaved in Spotify.
`mosaics` has a UUID, unique profile FK, preset key, bounded width/height, a complete
JSONB tile list, and an activation flag. Each tile stores only a Spotify album ID
and integer x/y. One JSONB replacement saves the complete layout in a caller-owned
transaction; separate tile rows and multiple designs are unnecessary for this MVP.
Profile row locks serialize creation, layout saves, and selection updates; saves
also lock the mosaic and verify every tile against the current Featured Album IDs.
Featured Album removal prunes affected tiles within the selection transaction.
Set Active only changes the mosaic flag; profile visibility still gates public
reads. Later owner saves update the active design. Public DTOs omit mosaic/internal
IDs; a separate public album endpoint checks public visibility, activation, and
tile membership before using the owner's server-side Spotify connection. This keeps
the public profile/layout readable during Spotify outages. Foreign keys cascade deletes.
Alembic is the schema authority; changing a model requires a reviewed migration.

Root `.env` configures Compose. Backend commands run from `backend/` so application
settings find `.env`; exported variables override it. Application import requires
database, Spotify, and frontend settings. Migrations independently load only
`DATABASE_URL` from the backend file. Frontend reads `NEXT_PUBLIC_API_BASE_URL`
(default `http://127.0.0.1:8000`) and Next.js loads `.env.local`.

Current CORS allows only `http://127.0.0.1:3000` with credentials. Use that host
consistently for browser/API/callback URLs; `localhost` is a different origin.
README covers setup and migration commands; examples contain no real credentials.

## Error handling

OAuth redirects to `/connect?error=...` for validation, upstream status/network,
and selected persistence failures. The connect page maps many codes to friendly
messages and uses a generic fallback for others. Owner reads return empty 401
responses for invalid sessions. Profile PATCH raises HTTPException (401/404/409/
422), with a username preflight plus an IntegrityError retry lookup for races.
Frontend fetches check HTTP status and show explicit loading/error/retry states.
There is no common application error middleware or response schema layer.

## Testing architecture

pytest uses FastAPI TestClient and respx mocks for Spotify; tests use test settings
without requiring real login. `tests/conftest.py` creates a randomly named database,
applies all migrations, and drops it on teardown when `TEST_DATABASE_URL` exists.
Repository scenarios additionally use isolated schemas populated from metadata;
HTTP tests use the migrated database. `test_migrations.py` checks schema/model
agreement. `test_persistent_auth.py` also verifies a fresh interpreter can read a
session. See FEATURE_MAP for scenario coverage.

The full verifier creates its own temporary PostgreSQL container on a random
loopback port and rejects skips. Direct pytest skips DB coverage without the test
URL. Frontend coverage currently consists of ESLint, TypeScript, production build,
and manual browser checks; no frontend unit/browser test framework exists.
There is no checked-in CI or enabled commit hook. Backend has Ruff but no separate
static type checker. No global formatting gate is installed.

## Known architectural debt

- First login now generates a 30-character username. Existing 37-character
  generated names remain readable and can be kept when saving other fields;
  changing a username still requires the current 3-30 character format.
- `persist_login` uses Spotify's `account_id`, as required by the current
  [provider reference](https://developer.spotify.com/documentation/web-api/reference/get-current-users-profile).
  There is no real-response fixture or live OAuth acceptance run; mocked OAuth
  passes do not establish live Spotify compatibility.
- OAuth exchange is inline in `api/routes/auth.py`; album reads/refresh are in the
  Spotify service. `api/routes/health.py` is also unregistered: the active
  health endpoint is in `main.py`.
- Owner JSON responses are duplicated across routes. Request `display_name` becomes
  response `displayName`; frontend types are manually duplicated and partial.
- CORS is hardcoded to a local origin and cookies are not production-secure. Keep
  deployment work explicit rather than assuming environment URLs configure CORS.
- Global tokens and page utility colors diverge. Dashboard uses a raw image tag;
  settings uses an unoptimized Next Image. Follow task scope before unifying them.
- Older phase acceptance records describe past runs. Current verification and
  feature behavior are documented here and in FEATURE_MAP.
