# Feature map

This map describes implemented behavior, not the project-plan PDF's roadmap.
Use [README](../README.md) to start PostgreSQL, migrate, and run both servers.
Use `http://127.0.0.1:3000` for browser checks. The standard automated command is
`uv run --project backend --locked python scripts/verify.py` from the repo root.
Automated Spotify calls are mocked; a live sign-in requires developer-app settings,
an encryption key, and an allowlisted Spotify account.

## Spotify connection and sign-in recovery

**User purpose:** connect a Spotify account and recover from failed/cancelled login.

**Entry points:** `/`, `/connect`, GET `/api/auth/spotify/start`, GET
`/api/auth/spotify/callback`. Successful login redirects to `/dashboard`;
failures redirect to `/connect?error=...`.

**Implementation:** `frontend/src/app/page.tsx`, `frontend/src/app/connect/page.tsx`,
`backend/app/api/routes/auth.py`, `backend/app/services/auth.py`.

**Backend/data:** Spotify authorize/token/current-user HTTP endpoints, backend
settings, OAuth state cookie; atomically upserts users/connections, creates a
profile on first login, encrypts refresh tokens, and creates a hashed session.

**Tests:** `backend/tests/test_spotify_auth.py` (invalid state and success),
`backend/tests/test_persistent_auth.py` (repeat login preserves edits and IDs,
encrypted refresh token, missing-refresh rollback, fresh-process session read).

**Verification:** run full verification for mocked flows. For live acceptance,
open `/connect`, click Connect Spotify, approve, and confirm the dashboard loads
your name/avatar. Reconnect and confirm the same owner profile is retained.
Open `/connect?error=state_mismatch` to check the error/retry UI without login.
Live identity compatibility remains unverified; see architectural debt.

## Owner dashboard, durable session, and logout

**User purpose:** see the connected owner's name/avatar and end the current session.

**Entry points:** `/dashboard`, GET `/api/me`, POST `/api/auth/logout`.

**Implementation:** `frontend/src/app/dashboard/page.tsx`,
`backend/app/api/routes/auth.py`, `backend/app/repositories/sessions.py`,
`backend/app/repositories/profiles.py`.

**Backend/data:** HttpOnly `mosaic_session`, sessions/profiles tables; owner JSON
contains `username`, `displayName`, `images`, `bio`, `visibility`, `theme` and no
Spotify tokens. Expired/unknown sessions return 401. Logout deletes the current
digest and cookie; other sessions are not revoked.

**Tests:** `test_spotify_auth.py`, `test_persistent_auth.py`,
`test_repositories.py::test_session_lifecycle_and_connection_upsert` in backend/tests.

**Verification:** sign in, open `/dashboard`, restart FastAPI, then refresh within
one hour and confirm the profile still loads. Click Log out and confirm landing
page navigation and `/api/me` returns 401. Open dashboard while signed out and
confirm reconnect/retry controls. Backend tests cover expiry without waiting.

## Profile settings preview (unsaved)

**User purpose:** preview username, display name, bio, visibility, and one of three
themes before any save integration exists.

**Entry points:** dashboard's Edit profile link; `/settings/profile`.

**Implementation:** `frontend/src/app/settings/profile/page.tsx` (`ProfileForm`,
`THEMES`, loader, local validation and draft/preview state).

**Backend/data:** GET `/api/me` supplies the initial owner profile. This page does
not call PATCH. Preview and Reset edits only change local state; private/public
is a preview label, and there is no public-profile sharing route.

**Tests:** no frontend automated behavior tests. Backend owner read tests cover
the source response, but not the form. Lint/typecheck/build cover compilation.

**Verification:** sign in, open settings, enter a username such as `music_fan`
(generated first-login usernames may exceed the form limit), change bio/theme,
and click Preview changes. Confirm the preview changes, Reset edits restores
loaded values, and refresh discards edits. With a missing session verify the
Connect Spotify prompt. Stop the API and reload to verify error/retry state.

## Owner profile persistence API

**User purpose:** persist owner profile edits; backend capability awaiting UI wiring.

**Entry point:** authenticated PATCH `/api/me/profile`; API docs at
`http://127.0.0.1:8000/docs`. There is no save button in settings yet.

**Implementation:** `backend/app/api/routes/profiles.py`, `app/schemas/profile.py`,
`app/repositories/profiles.py`, `app/models/profile.py` (paths relative to backend).

**Backend/data:** active session establishes ownership. Partial fields:
`username`, `display_name`, `bio`, `visibility`, `theme: {"preset": ...}`.
Unknown fields/nulls/empty patches are rejected; unavailable usernames yield 409.
Response uses `displayName`. PostgreSQL uniqueness resolves username races.

**Tests:** `backend/tests/test_profile_update_api.py` checks persistence, omitted
fields, owner enforcement, conflicts, validation, extra fields, and nulls;
`test_repositories.py` covers repository update/rollback.

**Verification:** run full verification. For manual API persistence while signed
in, open browser DevTools on the frontend and run:

```js
await fetch("http://127.0.0.1:8000/api/me/profile", {
  method: "PATCH", credentials: "include",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({ bio: "My edited bio" }),
}).then(async r => ({ status: r.status, body: await r.json() }));
```

If you configured a different API URL, substitute it. Expect 200 and the new bio;
refresh settings and confirm it loads. This intentionally changes your profile;
record the old bio first if you want to restore it. Signed-out PATCH should be 401.

## Local persistence and fixture tools

**User purpose:** prepare a repeatable local database for development and diagnose
connectivity; these are developer commands, not browser features.

**Entry points (from backend):** `uv run alembic upgrade head`,
`uv run alembic check`, `uv run python -m app.db.seed --local`,
`uv run python -m app.db.check`.

**Implementation:** `compose.yaml`, `backend/migrations/`, `backend/app/db/seed.py`,
`backend/app/db/check.py`, `backend/app/services/accounts.py`, repositories/models.

**Backend/data:** configured PostgreSQL and four tables. Seed creates
`mosaic_local_test` / `Local Test User` for `mosaic-local-test-user`, preserves
existing edits, and creates neither Spotify connection nor login session.

**Tests:** `backend/tests/test_migrations.py`, `backend/tests/test_repositories.py`
(identity uniqueness, rollback, session lifecycle, connection upserts, seed
idempotency); API tests use migrated databases through `conftest.py`.

**Verification:** on a local development DB, migrate and run `alembic check`;
run the seed twice and confirm no duplicates/overwritten edits. DB connectivity
command should print `Database replied: 1`. Full verification does its DB checks
in a separate temporary container. See [persistence checklist](phase-2-verification.md).

## API health

**User purpose:** confirm the API process responds.

**Entry point:** GET `/api/health`.

**Implementation:** `backend/app/main.py`; the similarly named route module is
currently unregistered. **Backend/data:** no query to PostgreSQL or Spotify.
Application import still needs backend settings. **Tests:** `backend/tests/test_health.py`.

**Verification:** with API running, request `http://127.0.0.1:8000/api/health`;
expect 200 and `{"status":"ok"}`. This is not a database readiness check.
