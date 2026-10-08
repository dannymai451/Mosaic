# Feature map

This map describes implemented behavior, not the project-plan PDF's previous
roadmap. Monthly listening artwork is the primary product; manual editing and
public profiles below remain legacy features.
Use [README](../README.md) to start PostgreSQL, migrate, and run both servers.
Use `http://127.0.0.1:3000` for browser checks. The standard automated command is
`uv run --project backend --locked python scripts/verify.py` from the repo root.
Automated Spotify calls are mocked; a live sign-in requires developer-app settings,
an encryption key, and an allowlisted Spotify account.

## Monthly listening artwork and private archive

**User purpose:** generate a personal monthly music snapshot, revisit saved months,
and preview the associated song before opening it on Spotify.

**Entry points:** landing Spotify connection, dashboard's Monthly artwork link,
`/monthly`; GET/POST `/api/me/monthly-mosaics`;
GET `/api/me/monthly-mosaics/{id}/albums/{album_id}`.

**Implementation:** `frontend/src/app/monthly/page.tsx`, the shared
`mosaic-canvas.tsx`, `album-detail.tsx`, and scoped `monthly-artwork.ts` loader;
backend monthly routes, service, schema,
repository/model, migration, and `services/spotify.py` (top-track integration).

**Backend/data:** authenticated owner-only archive; current month is determined
server-side in UTC. Spotify `user-top-read` consent is required for new generation
and catalog resolution, but no saved/Featured Albums are required. Up to 50
short-term top tracks represent approximately the preceding four weeks; this is
not an exact calendar-month log or play-count report. Tracks group into albums,
ranked by represented track count then earliest track rank. The deterministic
monthly Heart/Star/Music note preset is shared across accounts, with a Pumpkin
override for new October snapshots. The pumpkin uses a 12x12 jack-o'-lantern
with a bent stem, triangular eye openings, and a toothy
grin. Pumpkin covers use tighter two-pixel spacing. Selected albums
are capped to shape capacity and repeat across cells.

One immutable snapshot per profile/month is saved atomically; repeat generation
returns the existing snapshot before any Spotify request. A uniqueness constraint
and profile lock prevent duplicate concurrent writes. Previous months remain
unchanged, and clients cannot backdate generation. Empty usable data/provider
failures save nothing. Only IDs, coordinates, dimensions/preset, month, creation
time, source track count, each selected album's highest-ranked song ID, and new
tiles' song IDs persist. Repeated covers cycle original ranked songs within that
album. Older layouts keep their original representative-song fallback.
Existing snapshots have no retroactively inferred songs. A one-time data correction
changes pre-feature October 2026 hearts to pumpkins using only their saved album
order; it preserves record identity, listening data, song IDs, and creation time.
Other months retain their original layouts. Subsequent generation remains immutable.
A follow-up correction refines 9x9 October 2026 pumpkins by repeating their saved
tile payloads into the new shape; every existing album/song pair, representative
mapping, and generation timestamp is preserved without contacting Spotify.
Artwork/catalog metadata are resolved on
demand; successful song lookups include album covers and avoid separate album
requests. Missing/unavailable songs use an album fallback; song rate limits
propagate Retry-After and stop artwork loading. Credentials never appear in
responses. Detail reads verify owner and tile
membership; optional `track_id` must match that album on a saved tile. Monthly history stays private even when a legacy profile is public;
Featured Album removal does not modify snapshots.

Fresh generation returns a transient `artwork` map and expiry from the same
top-tracks response, so initial display needs no per-song detail reads. A valid
cached access token makes generation one Spotify request; a cold token makes it
two, excluding image downloads and retries. The server caches verified monthly
metadata for five minutes; warm detail reads make no Spotify calls while still
checking session, ownership, membership, and scope. Cache misses resolve the
original saved songs. Caches are bounded, per process, and cleared on restart.

**Frontend:** explicit Generate action saves immediately; opening the page writes
nothing. Current saved artwork and month navigation appear in the private archive.
Generation shows an indeterminate bar during the save, then measured album/image
loading progress; the complete canvas appears after all covers finish or reach a
bounded failure fallback. Saved artwork uses the same loading path. Every tile
opens a compact native dialog with the song title as its heading, the artist, a
single Spotify song action. The song response also supplies its album cover.
The plain X has an accessible Close details label; Escape and focus restoration
remain available. Dates and track counts are omitted. Scrollbar chrome is hidden
and background scrolling is locked, while overflow content remains reachable.
Tiles show cover artwork without visible title captions; accessible names/tooltips
identify each tile's resolved song. Older artwork uses its saved representative
song, or a short missing-song explanation and album action when no song was saved.
Failed metadata or images leave usable placeholders and retry; older snapshots show album details.
The page explains the approximate four-week source and handles empty,
loading, expired-session, reconnect, provider-error, and rate-limit states.

**Tests:** `backend/tests/test_monthly_mosaics.py` exercises period parameters,
album grouping, per-tile songs and cross-album membership, representative songs/relinking, seasonal presets, persistence/month
rollover, repeat/concurrent generation, ownership/privacy, empty data, safe provider
failures, and constraints. `test_monthly_migration.py` verifies that the new song-ID
column backfills older records without changing their archived layout.
Frontend behavior is verified in the browser; lint/types/build remain standard.

**Verification:** run full verification and follow
[monthly acceptance](monthly-mosaics-verification.md). Synthetic checks establish
application behavior; live OAuth/reconnect/top-track/catalog acceptance remains
dependent on the Spotify developer-app setup.

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

## Profile settings and saving

**User purpose:** preview username, display name, bio, visibility, and one of three
themes, then save those edits to the owner profile.

**Entry points:** dashboard's Account settings link; `/settings/profile`.

**Implementation:** `frontend/src/app/settings/profile/page.tsx` (`ProfileForm`,
loader, validation and saved/draft/preview state),
`frontend/src/components/profile-card.tsx`, `share-profile.tsx`.

**Backend/data:** GET `/api/me` supplies the initial owner profile. This page does
call PATCH `/api/me/profile` to persist changed fields. Preview changes only
updates local state; Reset edits restores the last successful save. Failed saves
keep the draft and show validation, conflict, expiry, or retry feedback. Controls
are disabled during saving. Sharing uses the saved username and visibility.

**Tests:** no frontend automated behavior tests. Backend owner read tests cover
the source response, but not the form. Lint/typecheck/build cover compilation.

**Verification:** sign in, open settings, enter a username such as `music_fan`
(new generated usernames fit the form limit; older names may remain unchanged), change bio/theme,
and click Preview changes. Confirm the preview changes, Reset edits restores
last saved values, and refresh discards unsaved edits. Save changes and refresh
to confirm persistence. Try a taken username and confirm the draft is retained.
With a missing session verify the
Connect Spotify prompt. Stop the API and reload to verify error/retry state.

## Owner profile persistence API

**User purpose:** persist owner profile edits from settings.

**Entry point:** authenticated PATCH `/api/me/profile`; API docs at
`http://127.0.0.1:8000/docs`; Save changes in `/settings/profile`.

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

## Read-only public profiles and sharing

**User purpose:** share a saved public profile with logged-out visitors.

**Entry points:** settings' View public profile / Share profile / Copy link;
`/@username`; GET `/api/profiles/{username}/public`.

**Implementation:** `backend/app/api/routes/profiles.py`,
`frontend/src/app/[handle]/page.tsx` and `not-found.tsx`,
`frontend/src/components/profile-card.tsx` and `share-profile.tsx`.

**Backend/data:** public reads do not require a session. Private and nonexistent
profiles both return 404 with the same message, even to owners. The public DTO
contains only username, displayName, images, bio, theme, and an active mosaic layout (or null), with no internal IDs
or Spotify tokens. The API and server fetch disable caching so subsequent
requests respect visibility changes. The public endpoint supports GET only;
all writes still derive ownership from the active session.

The shared route decodes its dynamic parameter before validating `@username`.
It renders a mobile profile card and sharing controls, with unavailable and
upstream-error states. Native Web Share falls back to clipboard; Copy link also
copies directly. If clipboard access fails, a selectable link is shown. Native
share cancellation ends quietly. Unsaved edits never change the shared URL.

**Tests:** `backend/tests/test_public_profiles.py` covers anonymous reads, private
profiles, the public DTO, renamed URLs, visibility withdrawal, and attempts by
visitors/other owners to write. Browser acceptance is recorded in
[Phase 3 verification](phase-3-verification.md), including 360/390/430px layouts.

**Verification:** save a public profile, copy its link, and open it signed out.
Verify both `/@username` and `/%40username`. Change the saved username and confirm
the old URL is unavailable. Save as private and reload the shared URL; no profile
details should appear. Featured Album selection is owner-only; only the active
mosaic's used album IDs and coordinates appear publicly. Public album details
are also withdrawn when the profile becomes private.

## Saved albums and private Featured Album selection

**User purpose:** browse the connected Spotify library and save the working set
of albums to use in the mosaic builder.

**Entry points:** legacy `/settings/albums`;
GET `/api/me/albums?limit=20&offset=0`; GET/PUT `/api/me/featured-albums`;
GET `/api/me/albums/{album_id}` for on-demand saved-selection details.

**Implementation:** `frontend/src/components/album-picker.tsx`, `album-detail.tsx`,
`frontend/src/app/settings/albums/page.tsx`; `backend/app/api/routes/albums.py`,
`app/services/spotify.py`, `app/schemas/album.py`, `app/repositories/profiles.py`.

**Backend/data:** requires an active owner session; OAuth now requests
`user-library-read`, so existing connections need reauthorization. Saved-album
pages return an allowlisted album DTO plus total/nextOffset, never Spotify tokens,
raw provider pagination URLs, tracks, or connection data. Refresh tokens stay
encrypted; valid access tokens are reused server-side until shortly before expiry, with one bounded retry
after an upstream 401 and immediate safe errors for 403/429/network failures.

PUT accepts `album_ids` (0-100 unique 22-character Spotify IDs), rejects extra
fields, verifies new additions against the owner's saved library, and persists
the ordered ID list on the profile in one transaction. Removal-only saves do not
call Spotify. No catalog data is stored and the Spotify library is never changed.
The working set is owner-only; public profiles expose only active mosaic tiles.
Removing a Featured Album prunes all of its tiles in the same transaction, so
the active layout never retains a withdrawn selection. Profile PATCH remains unchanged.

**Frontend:** Add/Remove edits a draft; Save persists; Reset restores the last
save. Failed saves retain the draft. Load more appends deduplicated pages, and
failed loads retain earlier albums/edits. Off-page selections show their ID until
Details or a later library page resolves their name. Details uses a native dialog
with a Spotify link, Escape dismissal, and focus trapping. The page has loading,
empty, retry, expiry, reconnect, and rate-limit states.

**Tests:** `backend/tests/test_albums.py` covers 20-item pagination, DTO/token
minimization, persistence/order/removal, owner isolation, scopes/sessions, batching,
validation and atomic failure, empty libraries/artwork, details, token rotation,
bounded 401 retry, safe provider/network/malformed-response errors, and CORS
exposure of Retry-After. Frontend behavior remains a manual browser check.

**Verification:** follow [Phase 4 end-to-end workflow](phase-4-verification.md),
including the live reconnect/load/add/save/reload/remove flow and mobile widths.
Mocked checks establish application behavior, not live Spotify compatibility.

## Mosaic builder and public active designs

**User purpose:** arrange Featured Album covers into a preset/custom shape, save
the exact layout, and show the active mosaic on a public profile.

**Entry points:** legacy album settings' Build your mosaic;
`/builder`; GET `/api/me/mosaic-presets`; GET/POST `/api/me/mosaics`;
PUT `/api/me/mosaics/{id}`; POST `/api/me/mosaics/{id}/activate`;
public profile DTO and GET `/api/profiles/{username}/albums/{album_id}`.

**Implementation:** `frontend/src/components/mosaic-editor.tsx`,
`mosaic-canvas.tsx`, `mosaic-albums.ts`, `public-mosaic.tsx`,
`frontend/src/app/builder/page.tsx`; `backend/app/api/routes/mosaics.py`,
`profiles.py`, `app/api/dependencies.py`, `app/services/mosaic.py`,
`app/schemas/mosaic.py`, `app/repositories/mosaics.py`, `app/models/mosaic.py`.

**Backend/data:** one design per profile (unique FK), stored as dimensions,
preset key, ordered JSONB tiles, and an activation flag. Coordinate presets are
Heart, Star, Music note, and Blank / custom. Preset expansion repeats the owner's
Featured Album IDs to fill the shape; an empty selection produces an empty design.
Complete-layout PUTs allow 0-100 tiles in a 1-12 by 1-12 grid, reject duplicate
coordinates, out-of-bounds/noninteger coordinates, invalid IDs/extra fields, and
any album outside the owner's current Featured Albums. Multiple cells may use
the same album. Identity comes from the session; foreign mosaic IDs return 404.
Writes lock relevant records and flush in a caller-owned transaction. No artwork
or Spotify metadata is persisted. Removing a Featured Album prunes its tiles atomically.

**Frontend:** a 9x9 grid scales with CSS Grid. Apply a preset with one click;
choose a tray album then click a cell, or Tab and Enter/Space. Erase tiles clears
cells; Undo retains up to 50 edits; Reset restores the last save; Save persists
the full draft. Failed saves retain drafts. Controls are disabled during writes.
Set Active requires a saved, clean draft and does not change profile visibility.
Subsequent saves update the active design. Navigation/refresh loses unsaved work.
The album picker and builder are separate screens; return to the builder after
saving a new working set. Album artwork/details load sequentially per unique ID
with timeout/cancellation/retry and a placeholder when an album is unavailable.

**Public view:** uncached profile reads embed only an active design's dimensions,
preset, coordinates, and used album IDs; private/missing profiles remain identical
404s. The read-only canvas shows no placement/save/activation controls. Tiles open
the existing album detail dialog with a Spotify link, or link directly to Spotify
while details are unavailable. Separate detail reads verify public visibility,
activation, and tile membership before resolving normalized metadata server-side.
Spotify outages do not prevent profile/layout reads. Tokens never reach browser DTOs.

**Tests:** `backend/tests/test_mosaics.py` covers all presets, validation,
save/reload/order/repeated albums, activation, anonymous public layout/details,
visibility withdrawal, owner/session enforcement, safe upstream failures, removal
rollback/pruning, layout rollback, unique profile constraint, and cascade deletion.
Frontend behavior is covered by the browser acceptance record; compile checks
remain ESLint/TypeScript/build.

**Verification:** run the standard verifier and follow
[Phase 5 acceptance verification](phase-5-verification.md). The 2026-10-05 record
uses disposable PostgreSQL and synthetic Spotify responses; live OAuth/catalog
acceptance remains outstanding.

## Local persistence and fixture tools

**User purpose:** prepare a repeatable local database for development and diagnose
connectivity; these are developer commands, not browser features.

**Entry points (from backend):** `uv run alembic upgrade head`,
`uv run alembic check`, `uv run python -m app.db.seed --local`,
`uv run python -m app.db.check`.

**Implementation:** `compose.yaml`, `backend/migrations/`, `backend/app/db/seed.py`,
`backend/app/db/check.py`, `backend/app/services/accounts.py`, repositories/models.

**Backend/data:** configured PostgreSQL and six tables. Seed creates
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
