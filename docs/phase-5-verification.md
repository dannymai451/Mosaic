# Phase 5 acceptance verification

Phase 5 implements the signature mosaic builder from the project plan: four
coordinate presets, accessible click/keyboard editing, complete-layout persistence,
Reset, Undo, Save, Set Active, and read-only public active designs. One saved design
per profile is the MVP limit; multiple designs remain a stretch goal.

## Automated verification

From the repository root, after the README dependency setup with Docker running:

```sh
uv run --project backend --locked python scripts/verify.py
```

This checks boundaries, Ruff, frontend ESLint/types/build, migrations, and the
entire backend suite against disposable PostgreSQL. Skipped tests fail verification.

`backend/tests/test_mosaics.py` covers:

- Four preset coordinate maps, deterministic repeated-cover filling, empty selections.
- Exact layout replacement/order and reads through fresh request sessions.
- Coordinate uniqueness, bounds, strict integers, dimensions, IDs, tile count,
  unknown fields, and Featured Album membership validation.
- Session-derived ownership, foreign/unknown mosaic IDs, one-design uniqueness.
- Saved versus active public layout, repeat activation, allowlisted public DTOs.
- Anonymous album details restricted to public active tiles; private/missing
  profiles, visibility withdrawal, Spotify 404/429, safe errors and token exclusion.
- Transaction rollback for layouts and Featured Album removal, active tile pruning,
  and profile-to-mosaic cascading deletion.

Existing album tests continue to cover expired sessions and server-side refresh,
rotation, scope checks, bounded retries, and safe provider errors through the shared
dependencies. Migration tests compare the migrated schema against all five models.

## Browser golden path

1. Start PostgreSQL, run `uv run alembic upgrade head` from `backend/`, restart the
   backend, and run the frontend as described in README. Use `127.0.0.1` throughout.
2. Sign in and save at least two Featured Albums in `/settings/albums`. Open
   **Build your mosaic**, or dashboard's **Build mosaic** link.
3. Apply Heart, Star, Music note, and Blank / custom. Heart has 46 cells, Star 41,
   Music note 38, and Blank zero. Verify repeated album covers fill the shapes.
4. Choose a tray album. Click a blank cell, then a filled cell to replace it.
   Verify the chosen cover appears. Tab to a cell and press Enter/Space to place.
5. Enable Erase tiles and clear a cell. Undo restores it. Apply another preset,
   Undo returns to the previous layout. Reset returns to the last saved design.
6. Save a custom or preset layout, refresh, and compare each tile's row/column
   and album to the saved design. Metadata can finish loading after the layout.
7. Set Active. If the profile is private, verify its public URL remains unavailable.
   Make it public in profile settings and open both `/@username` and `/%40username`.
8. Open the shared URL in a signed-out browser. Verify the layout appears without
   editing controls. Tap a tile: artist/name/release/track info and Open in Spotify
   appear. Escape and Close details dismiss the dialog; Tab remains inside it.
9. Check builder/public pages at 360, 390, 430, and desktop widths. Verify square
   covers, unchanged positions, usable controls, and no horizontal overflow.
10. Change a saved active design and save: subsequent public reads update it.
    Remove a Featured Album in album settings and save: all its tiles disappear
    from the saved/public layout. Unsaved builder drafts from another tab may be
    rejected; they stay available for correction/reset.
11. Make the profile private again: subsequent public profile and album-detail
    requests return unavailable, including requests from the owner.

## Failure and empty-state checks

- No Featured Albums: builder loads, offers selection navigation and blank design;
  shape presets are disabled until albums are saved.
- API down or missing/expired session: explicit loading error, retry/connect actions.
- Failed layout save: draft/history remain; controls become usable for correction/retry.
- Set Active with unsaved changes: disabled until saving; activation never changes visibility.
- Missing album/artwork: cover placeholder and Spotify link; layout coordinates remain.
- Spotify scope/refresh/network/429 failure during artwork reads: keep the layout and
  earlier details, stop remaining reads, expose retry/reconnect, respect Retry-After text.
- Refresh/navigation before saving: draft and undo history are discarded.
- First save creates the design then PUTs its full layout. If creation succeeds but
  PUT fails, the blank saved design remains and the draft is retained for retry.

## Verification record: 2026-10-05

- Standard repository verifier: **passed**, 82 backend tests, **zero skips**;
  boundaries, Ruff, ESLint, TypeScript, production build, and schema/model check passed.
- ESLint reports two existing dashboard warnings (raw image and internal navigation);
  they are unrelated to the builder and remain unchanged.
- Chrome browser checks used a temporary frontend copy, the actual FastAPI routes,
  disposable PostgreSQL with all migrations, synthetic album metadata/artwork, and
  a synthetic owner session. Real profile data was untouched. After acceptance,
  the additive Phase 5 migration was applied separately to the verified local
  `127.0.0.1` development database; `alembic check` reported no schema drift.
- Verified all four presets/counts, album choice plus Enter placement, Space erasure,
  Undo, Reset, Save, refresh with 46 occupied cells, Set Active, public rendering,
  literal/encoded `@` routes, album details, and Escape dismissal in development mode.
  After logging out through the dashboard, the shared profile still loaded all 46
  covers and public detail actions.
- Responsive checks found no horizontal overflow at 360/390/430px and 1280px;
  the public layout contained the same 46 tiles and no editing actions.
- Tray alignment follow-up: eight synthetic albums with alternating short/long
  titles and artist names produced equal card heights across rows in the builder
  and saved-album picker at 390px and 1280px. Covers, title/artist rows, Spotify
  links, and picker actions aligned; neither page overflowed horizontally.
  Names display up to two lines, with full text available through the title
  attribute and existing accessible controls. The full verifier still passed.
- Synthetic application/browser checks do not establish compatibility with a live
  Spotify account. Live sign-in, catalog retrieval, and real artwork acceptance
  still require the developer-app setup from README.

## Design limits

Only the selected IDs, coordinates, dimensions, preset, and activation flag are
stored. Catalog details use the existing server-only Spotify refresh mechanism
and [Get Album endpoint](https://developer.spotify.com/documentation/web-api/reference/get-an-album).
Each unique album currently needs its own request/token refresh; there is no shared
catalog/token cache. The UI loads them sequentially and stops at a failure, so a
large working set can load slowly. Cached/batched retrieval is a future improvement
if live acceptance demonstrates a need.

Undo is local, limited to 50 edits, and clears after successful save. The UI uses
9x9 presets/custom grids; the API accepts 1-12 per dimension for a saved layout.
Set Active persists the saved design and later saves update it. There is no separate
publication snapshot, drag/drop, resize UI, or multiple-design selector in this phase.
