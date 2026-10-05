# Phase 4 end-to-end testing workflow

Phase 4 implements saved-album browsing and a private working set of Featured
Albums. Preset shapes, tile placement, and publishing albums to the public profile
belong to Phase 5. This checklist covers the implemented slice.

## Automated verification

Install the locked dependencies as described in README (`npm ci` in frontend,
`uv sync --locked` in backend), then start Docker Desktop. From the repo root:

```powershell
uv run --project backend --locked python scripts/verify.py
```

Expected: boundary checks, Ruff, frontend lint/types/production build, and all
backend tests pass with **zero skips**. The runner applies migrations to disposable
PostgreSQL; it does not migrate or change the development database. Spotify HTTP
calls are mocked, so no real tokens, accounts, or API quota are needed.

`backend/tests/test_albums.py` covers pagination, normalization, selection persistence
and ownership, validation, library membership, 40-URI batches, atomic failed saves,
empty libraries, missing artwork, details, refresh-token rotation, expired access
and revoked refresh tokens, rate limits, network failures, and malformed responses.
The existing OAuth, profile, public-sharing, repository, and migration tests also run.

## Local setup for the browser test

Use the existing local environment files from README; keep the same
`TOKEN_ENCRYPTION_KEY` that encrypted existing connections. Configure a Spotify
developer app, its callback `http://127.0.0.1:8000/api/auth/spotify/callback`, and an
allowlisted test account. To verify a full first page plus pagination, that account
must have **at least 21 saved albums**, not just saved tracks or followed artists.

From the repo root:

```powershell
docker compose up -d db
Set-Location backend
uv sync --locked
uv run alembic upgrade head
uv run alembic check
uv run fastapi dev
```

This applies the new `d492ab31e706` migration to your configured local database.
An existing profile receives an empty ID list; profile fields are preserved.
Restart an already-running API after migration. In another terminal from the root:

```powershell
Set-Location frontend
npm ci
npm run dev
```

Use `http://127.0.0.1:3000` consistently; `localhost` is a different CORS origin.
The local seed alone has neither a Spotify connection nor a session and cannot
complete the live library flow. Existing users must reconnect once to grant the
new `user-library-read` scope. Approve that permission yourself in Spotify.

## Browser golden path

1. Open `/connect`, connect/reconnect Spotify, and confirm the dashboard loads.
   Confirm existing profile edits remain after reconnecting.
2. Click **Choose albums**. Expect `/settings/albums`, saved selections, and the
   first 20 albums from that account. Compare names/artists with the Spotify library.
3. Click **Load more**. Confirm more albums append without duplicates, and the
   button disappears on the last page. Selections must remain intact across pages.
4. Add two albums, including one beyond the first page. Confirm the counter and
   selected state change and an unsaved notice appears. Remove one, then **Reset
   edits**; the last saved set should return. Unsaved edits disappear on reload.
5. Add both albums again and click **Save Featured Albums**. Wait for the saved
   message, then reload. Both IDs must remain selected. Restart the API and reload
   again to check that persistence does not depend on server memory.
6. An off-page selection initially shows its ID. Click **Details** to resolve its
   current Spotify metadata. Verify title, artists, release date, track count, and
   the **Open in Spotify** link. Click the link and confirm the correct album opens.
7. In `npm run dev`, open details from both a library cover and a selected row.
   The modal must stay open despite React Strict Mode, contain keyboard focus,
   close with Escape or Close details, and return focus to its opener.
8. Remove an album and save. Reload and confirm removal persisted. Selecting or
   removing Featured Albums must not save/unsave anything in Spotify itself.
9. Test at 360, 390, and 430px widths, plus desktop. Check no horizontal overflow,
   readable album names, usable buttons, and a scrollable detail dialog. Include
   short and multiline album titles and artist lists in the same grid row; Spotify
   links and Add album/Selected buttons must align along the bottom of each card,
   with full names visible and no overlap between text and actions.
10. Log out, then visit `/settings/albums`. Expect an expiry/connect prompt and
    disabled editing. Sign in as a different allowlisted user and confirm their
    selection is independent. Public shared profiles still show the Phase 3 card.

## Failure and recovery checks

| Scenario | How to check | Expected |
| --- | --- | --- |
| Empty library | Use an account with no saved albums | Empty message; saved selections can still be removed. |
| API unavailable | Stop the local API, reload, then restart and Try again | Error instead of endless loading; retry succeeds. |
| Failed save | With a draft, block the PUT request in DevTools or stop the API and save | Draft stays; no success message; retry after recovery. |
| Failed library retry | Block GET `/api/me/albums`, reload, remove a saved selection, unblock, and Try again | Pending removal survives the successful library retry. |
| Failed Load more | Block the next library request, then unblock and retry | Earlier page/selection stays; same offset retries. |
| Old library scope | Visit with a pre-Phase-4 connection | Reconnect prompt; new permission enables browsing. |
| Expired application session | Log out in another tab, then save | 401 and reconnect prompt; draft retained. |
| Invalid selection | Send duplicate/invalid IDs or extra `user_id` through the API | 422; stored selection unchanged. |
| Album no longer saved | Add a draft album, unsave it in Spotify before saving | Newly added ID rejected; previous selection unchanged. |

Expired Spotify access, revoked refresh, 403/429, malformed payloads, and mid-batch
membership failure are tested deterministically in `test_albums.py`. Do not create
real quota exhaustion to test rate limits. The backend retries an upstream 401
once, returns 429 without automatic polling, and exposes Retry-After to the browser.
If it is present, the UI displays the delay before a manual retry.

For API inspection, use the frontend's DevTools console while signed in:

```javascript
const api = "http://127.0.0.1:8000";
await fetch(`${api}/api/me/albums?limit=20&offset=0`, {
  credentials: "include",
}).then(async r => ({ status: r.status, body: await r.json() }));
await fetch(`${api}/api/me/featured-albums`, {
  credentials: "include",
}).then(async r => ({ status: r.status, body: await r.json() }));
```

Album responses contain `id`, `name`, `artists`, `imageUrl`, `spotifyUrl`,
`releaseDate`, and `totalTracks`; pages include `total` and `nextOffset`. Selection
responses contain only `albumIds`. Verify no Spotify access/refresh tokens or
encrypted connection values occur in browser responses or storage. PUT replaces
the complete set with `{ "album_ids": [...] }`; restore your original test selection
after a manual write if needed.

## Verification record and limits

On October 5, 2026, the standard verifier passed: **58 backend tests, zero skips**,
boundary checks, Ruff, frontend lint, type checking, and production build. The two
existing dashboard lint warnings remained warnings.

The implementation is verified with the standard repository command and a manual
browser run against a disposable PostgreSQL database with synthetic Spotify
responses and a fixture owner. Browser checks cover saving/reloading, removal and
reset, paginated loading and retry, off-page detail resolution, dialog dismissal,
draft preservation, failure recovery, and responsive layouts.

The fixture owner bypasses live browser authentication; automated API tests cover
session enforcement and owner isolation. A real Spotify OAuth/library run remains
to be completed using the golden path above. No checked-in Playwright/Vitest suite
has been introduced. Existing dashboard lint warnings and deployment CORS/cookie
configuration are unchanged, apart from exposing Retry-After.

Access tokens are refreshed per Spotify-backed request in this first slice, which
costs an extra token request per page/detail/save with additions. A shared token
cache and mosaic layout persistence are future work. Concurrent complete-set saves
use last-writer-wins behavior, as with current profile editing.

Provider contracts checked for this implementation: [saved albums](https://developer.spotify.com/documentation/web-api/reference/get-users-saved-albums),
[token refresh](https://developer.spotify.com/documentation/web-api/tutorials/refreshing-tokens),
and [library membership](https://developer.spotify.com/documentation/web-api/reference/check-library-contains).
