# Monthly listening mosaics

Mosaic's primary experience is a private collection of monthly music artwork.
Connect Spotify, generate the current month's artwork, and revisit saved months.
There are no followers, feeds, likes, comments, or background generation jobs.

## Listening period and artwork decisions

The first release uses Spotify's top 50 tracks with `time_range=short_term`,
`limit=50`, and `offset=0`. Spotify describes short term as approximately the last
four weeks, ranked by calculated affinity. This is a monthly snapshot taken when
the user generates it, not a calendar-month listening log, exact play counts, or
a replacement for Spotify Wrapped. Earlier months cannot be backfilled from this
endpoint. See [Spotify's top-items reference](https://developer.spotify.com/documentation/web-api/reference/get-users-top-artists-and-tracks).

Tracks are grouped by their album. Albums with more represented tracks rank first;
ties retain the earliest track's rank. Local/unavailable tracks are skipped. The
number of source tracks describes usable returned tracks, not listening frequency.
Selected albums are capped by the month's shape capacity, and covers repeat to
fill the shape. Heart, Star, and Music note rotate deterministically by month,
with a Pumpkin shape for October artwork. Everyone gets the same shape for
that month with their own album covers.

Correction after the initial refinement: a one-time migration converts already
saved October 2026 hearts to pumpkins, preserving the original listening snapshot,
IDs, song associations, and saved date. Other months retain their saved shapes.

The server assigns the current month in UTC at request start and binds its saved
generation timestamp to that same instant, including requests crossing midnight.
Generation saves one immutable
snapshot per profile and month, including its creation time. Generating again
returns the existing record, including when Spotify is unavailable. No request
can choose a historical month, change another owner's archive, or replace a saved
snapshot. Empty listening data leaves the archive unchanged so the user can retry.

Monthly records are separate from existing manually edited mosaics. This preserves
existing designs and their public URLs without making the monthly archive public.
Removing Featured Albums or changing profile visibility does not alter the archive.
The main navigation now emphasizes monthly artwork; the older editor, picker,
and public-profile settings remain available at their existing routes.

Only album IDs, tile song IDs, representative song IDs, coordinates, preset/dimensions, month,
generation time, and source track count are persisted. The highest-ranked valid
song for each selected album comes from the original top-track response. New
tiles cycle ranked songs within their album so matching covers can open different
songs. Existing layouts are unchanged and use their representative-song fallback. Album
and song names and artwork are resolved from Spotify when viewing a saved design,
so metadata availability can change. Older snapshots have no song association;
their migration defaults to an empty mapping without rewriting the artwork.

Generation displays an indeterminate saving bar, followed by measured progress
through unique album/song metadata pairs and image decoding. The canvas appears together
after completion or bounded failure fallbacks. Missing artwork does not remove
saved tiles. Tapping a tile opens a minimal song-first dialog: cover, song title,
artist and a single song link. A plain
X dismisses it; release dates/track counts are omitted. Hidden scrollbar chrome
does not prevent reaching overflow content; background scrolling is locked while
open. Song lookup failures leave the album usable.

## Stack decisions

| Technology | Responsibility and reason |
| --- | --- |
| Next.js and React | Existing routes, interactive generation/archive selection, and the shared responsive canvas. |
| TypeScript | Checks the frontend album/layout/API contracts. |
| Tailwind CSS | Styles the responsive artwork and archive without adding a UI dependency. |
| Python and FastAPI | Existing secure Spotify integration, deterministic album selection/generation, and owner-only HTTP endpoints. |
| PostgreSQL | Durable accounts, sessions, and monthly archives; a unique profile/month constraint protects against duplicate generation. |
| SQLAlchemy and Alembic | Caller-owned transactions and an additive, versioned schema change. |
| OAuth and Fernet | Spotify consent and encrypted server-side refresh-token storage; tokens never appear in browser DTOs. |
| Docker, pytest/respx, Ruff, ESLint, TypeScript/build checks | Repeatable PostgreSQL verification, synthetic provider failure tests, and static checks. Docker currently hosts PostgreSQL only. |

Genre-driven shapes, exact calendar-month collection, scheduled generation, exports,
and social features are outside this release. No new dependency is required.

## Automated verification

After the README dependency setup, with Docker running, from the repository root:

```sh
uv run --project backend --locked python scripts/verify.py
```

This runs architecture boundaries, Ruff, frontend lint/types/build, and the entire
backend suite against disposable PostgreSQL with migrations. Skips are failures.
`backend/tests/test_monthly_mosaics.py` exercises the monthly flow with synthetic
Spotify responses; these checks do not establish live provider compatibility.

## Browser acceptance

1. Start the database, apply migrations with `uv run alembic upgrade head` from
   `backend/`, and restart the API/frontend as described in README.
2. Reconnect Spotify to grant `user-top-read`. The monthly flow does not require
   saved albums or a Featured Album selection.
3. Open the dashboard's monthly artwork link or `/monthly`. A new account has an
   empty archive and an explicit generate action. Opening the page alone writes
   nothing to the archive.
4. Generate. Observe the saving bar, followed by cover preparation progress. With
   delayed covers, no tiles appear before preparation settles. Verify the month,
   generation date, approximate four-week explanation, and complete shape. New
   October records use a Pumpkin with stem and face openings; the one-time
   October 2026 correction also updates pre-feature hearts. Tab to a tile and activate it: a
   native dialog shows the song as its heading and the album in a smaller box.
   Verify separate song and album Spotify links, a plain X, no date/track count,
   Escape dismissal, and focus returning to the tile. For new artwork, two covers
   from the same album can show different saved song names and song destinations.
5. Reload. Verify the exact saved ID, album IDs, and coordinates remain. Repeat
   generation through the API returns the same record; the UI indicates the
   current month's artwork is already saved.
6. With saved records from separate months in a disposable fixture, switch archive
   entries and verify their dates and layouts. The newest month appears first.
7. Verify mobile widths 360/390/430px and desktop: square tiles, readable month
   navigation, usable controls, and no horizontal overflow.
8. Sign out: archive/layout/detail endpoints require authentication. Another
   owner's ID and albums outside a saved snapshot return 404. Making a legacy
   profile public does not publish the monthly archive.

## Failure checks

- Missing/expired session: sign-in action; no saved data displayed to visitors.
- Missing top-track permission: reconnect action; existing archive remains readable.
- Empty usable top tracks: explanatory retry state, no empty monthly entry created.
- Spotify 429: sanitized Retry-After guidance, no empty/partial save.
- Provider/network/malformed-response failure: safe error and retry; no snapshot
  saved on failure. Generation buttons recover after a failed request.
- Artwork/catalog failure: settle with complete saved coordinates, placeholders,
  and usable album dialogs/Spotify actions; retain successfully loaded details
  and offer an artwork retry. A broken or stalled image must not keep the loader
  running indefinitely. Retry and archived-month switches must not expose stale
  partial artwork.
- Song-detail failure: album remains usable with an unavailable explanation.
  Older snapshots explain that song details were not saved; never use current
  listening to infer a historical song. Verify both original track provenance and
  album membership, including relinking, before displaying a song action.
- A session 401 during album preparation must hide the private archive and canvas,
  even if the preceding archive request succeeded. A Spotify permission/provider
  failure still preserves the owner's saved archive with reconnect/retry guidance.
- Concurrent generation: one persisted snapshot for the month; no overwritten
  previous-month record.

## Verification record: 2026-10-05

- Standard repository verifier: **passed**, **112 backend tests, zero skips**.
  Boundaries, Ruff, frontend ESLint, TypeScript, production build, and Alembic
  schema/model checks passed against disposable PostgreSQL 18.
- Two existing dashboard lint warnings remain (avatar image and internal logout
  navigation). They did not fail verification and were left outside this change.
- Read-only review caught and corrected rotated-token rollback on reduced scopes
  and stale private artwork after session revocation. The token regression is in
  the backend suite; archive clearing was reproduced and verified in the browser.
- In-app browser checks used a temporary frontend copy, actual FastAPI routes,
  all migrations in disposable PostgreSQL, a synthetic owner session, mocked
  Spotify responses, and locally served sample covers. Real listening/profile
  data was untouched. The temporary linked-dependency frontend used an explicit
  Turbopack root; production repository configuration was unchanged.
- Verified initial signed-out/empty states, empty-listening rejection, rate-limit
  guidance, generation/save/reload, October-to-November rollover, newest-first
  archive selection, Heart/Star layouts (46/41 tiles), catalog failure preserving
  all links/geometry, and successful artwork retry. Keyboard activation of a tile
  opened its expected Spotify album in a separate tab.
- Responsive checks at 360/390/430px and 1280px showed no horizontal overflow.
  All 41 Star tiles and artwork remained present at each width.
- Revoking the synthetic session and refreshing removed both the archive and all
  displayed tile links, leaving sign-in/retry guidance.
- After verification, the additive migration was applied to the verified local
  `127.0.0.1:5432/mosaic` development database. `alembic check` reported no schema
  drift. Existing designs were preserved; synthetic QA data was kept separate.
- Live OAuth, top tracks, real artwork, and permission-reconnect acceptance remain
  unverified. They require the configured Spotify developer app; synthetic checks
  do not establish provider compatibility.
- QA servers and the disposable database were stopped after acceptance. Automatic
  approval review blocked temporary-folder removal; its files remain outside Git
  under the operating system's temporary directory.

## Refinement verification: 2026-10-05

- Standard repository verifier passed after the final changes: **123 backend tests,
  zero skips**, including boundaries, Ruff, frontend lint/types/build, real
  PostgreSQL integration, and migration/model checks. The two existing dashboard
  lint warnings remain unchanged.
- Added coverage for original representative track selection, verified song and
  album membership, relinking, safe song-detail failure fallback, owner privacy,
  the monthly-only Pumpkin, and immutable previous October shapes. A separate
  migration test upgrades a pre-provenance Heart snapshot, downgrades/upgrades
  the added column, and verifies empty provenance and preserved coordinates.
- Synthetic in-app browser checks used the actual API and new migrations in
  disposable PostgreSQL with locally served sample covers. Three-second delayed
  covers showed preparation progress with zero displayed tiles/images; completion
  revealed all 53 Pumpkin tiles with decoded covers. Broken cover responses settled
  to a complete shape with usable song/album dialogs; Retry restored all covers.
  A twelve-second stalled image reached the ten-second image timeout and revealed
  all 53 tiles with a placeholder and retry, without a stuck progress bar.
- Song 404 responses kept album actions and exposed an unavailable notice. Retry
  after provider recovery restored the original song title/action. Native-dialog
  Escape dismissal returned focus to the originating tile. Pumpkin and popup checks
  at 360/390/430px and desktop showed no horizontal overflow.
  Switching October/November selected the complete 53-tile Pumpkin/41-tile Star
  respectively. An empty-provenance fixture showed the older-artwork explanation
  and album action, with no fabricated song link.
- Review caught detail-request 401 handling and cached failed-song retry gaps.
  Both were fixed. A successful archive GET followed by a detail 401 was verified
  to clear the archive and all tiles, show Connect Spotify, and avoid a canvas
  reveal. Provider failures retain usable owner-only placeholders.
- The provenance migration was applied to the verified local development database
  at `127.0.0.1:5432/mosaic`; `alembic check` reported no drift. Existing artwork
  keeps its original layout and cannot gain song associations retroactively.
- Live Spotify OAuth, real top tracks/covers/song catalog, and reconnect acceptance
  remain unverified; all provider responses in this record are synthetic.
- QA servers and the disposable database were stopped afterward. Temporary QA
  files remain outside Git; the repository keeps no harness, sample covers, or
  generated browser output.

## Saved October theme correction: 2026-10-05

The initial refinement only changed new generations, so an existing October 2026
record still displayed its saved Heart. Migration `b17ea42c093d` corrects those
records using the original ordered album IDs, without Spotify calls or changes to
snapshot identity, listening counts, song provenance, or generation date. Only
October 2026 Heart layouts are corrected; other months and manual mosaics stay
unchanged. Downgrade retains the intentional data correction.

Full verification passed: **123 backend tests, zero skips**, plus static checks,
frontend lint/types/build, and migration/model checks. The migration regression
checks the exact pumpkin layout, unchanged listening/date/provenance, unaffected
September artwork, and safe migration reapplication. The local migration was
applied at `127.0.0.1:5432/mosaic`; `alembic check` reported no drift.

The actual `/monthly` page reproduced **Heart · 43 albums / 46 tiles** before
the migration. Refresh collection afterward showed **Pumpkin · 43 albums / 53
tiles**, confirming the previously saved artwork was corrected without losing
albums. Existing dashboard lint warnings remain outside this fix.

## Tile-title captions: 2026-10-05 (superseded below)

Monthly tiles show the saved representative song title over the cover. Missing
song details use the album name; old snapshots are not assigned inferred songs.
Long titles truncate within the square tile, with the full song/album label in the
native tooltip and accessible button name and the full title in the popup.
Repeated album covers share their original representative song.

The standard repository verifier passed: **123 backend tests, zero skips**,
lint/types/build and all static checks. Browser checks used the actual shared
canvas in a temporary fixture route with synthetic song names, a long-title case,
and a missing-image/older-song case. All 53 monthly tiles received captions; the
legacy canvas had none. Popup text/actions, Escape dismissal/focus recovery, and
360/390/430px square tiles without horizontal overflow passed. The temporary
fixture and generated screenshots are outside Git; no dependency or API change
was required. Existing dashboard lint warnings remain unchanged.

Reloading the actual saved October page showed all 53 captions. Its older snapshot
has no saved song association, confirmed in the popup, so those captions use album
names. The temporary fixture server was stopped after verification.

## Titles in the popup only: 2026-10-05

Removed the visible tile captions at the user's request. Monthly dialogs now
explicitly label the album and the song from the saved listening snapshot; older
records explain that they predate song details. Song names remain supported by the
existing verified Spotify track lookup; missing original track associations are
not reconstructed from album names or today's listening.

`uv run --project backend --locked python scripts/verify.py` passed: **123 tests,
zero skips**, static checks, frontend lint/types/build, and migrated PostgreSQL
integration. Browser checks confirmed 53 cover-only tiles, full synthetic song
names/actions in the popup, long titles within the 360px mobile dialog, old-record
explanations without a fabricated song link, and unchanged legacy dialogs. The
actual October artwork also showed no captions and the explicit album/song labels
with its older-record explanation. Existing dashboard lint warnings remain.

## Explicit October regeneration: 2026-10-05

The owner explicitly requested regeneration so song titles would appear in the
existing October artwork. A one-time maintenance operation used the established
Spotify service and owner-scoped repositories against the verified local database.
It saved a recoverable copy outside Git before any provider request, fetched current
short-term listening, and replaced the identified current-month snapshot atomically
after owner/profile locking and a concurrent-change check. The artwork retained
its identity and October Pumpkin while updating the generation time and listening
selection. Normal generation still returns an existing immutable record.

The regenerated snapshot has **43 albums, 53 tiles, and 43 saved representative
song associations**. Live calls through the same detail handler used by the popup
verified three album/song pairs: HALO / FAREWELL TOLEDO; <Hyper-Ego> / Pixel Memory;
AsuRaBalBalTa / I turned off the TV... (feat. Yoonmirae & Kwon Jung-yeol).
All returned song details successfully. No credentials or catalog payloads were
written to the archive, and the maintenance script/backup are outside Git.

The standard verifier subsequently passed with **123 backend tests, zero skips**,
plus static checks and frontend lint/types/build. The signed-in monthly page
resolved saved song names in accessible tile labels before the later popup work.

## Minimal song-first popup and per-tile songs: 2026-10-05

The monthly popup now leads with the song title and artist, followed by the primary
song link and a smaller `Album: <title>` section with its album link. The close
control is a plain X with an accessible label; release dates and track counts are
removed. Compact covers prevent ordinary mobile overflow. Scrollbar chrome is
hidden, while keyboard scrolling still reaches content on short screens. The
background page is locked only while the dialog is open. Legacy dialogs keep an
album heading and album action.

New monthly JSONB tiles save an optional `spotifyTrackId` from the generation
response. Repeated covers cycle that album's ranked songs. Detail requests select
the exact song with `track_id`, verified against the owner and saved album/tile
before Spotify access. Metadata keys include both album and song, and repeated
cover URLs decode once per run. No new schema migration is required. Previously
saved artwork keeps its representative-song associations; it is not silently
regenerated with today's listening.

`uv run --project backend --locked python scripts/verify.py` passed: **127 backend
tests, zero skips**, static boundaries, Ruff, frontend lint/types/build, and
disposable PostgreSQL migration checks. The first run exposed a migration-test
expectation that included the new optional null song field; the comparison now
excludes nulls and still verifies unchanged historical tile storage. The subsequent
full run passed. Existing dashboard navigation/image lint warnings remain outside
this change.

Browser checks used the actual components and loader in temporary routes outside
Git. Matching covers opened First song / Second song with distinct track URLs;
preparation displayed progress before the canvas appeared. A successful first
detail followed by a 401 revealed no canvas. Long titles fit at 360x740, 390x660,
and 430x660 without horizontal or internal vertical overflow. At 360x400, keyboard
navigation reached the album link with hidden scrollbar chrome. X/Escape dismissal,
focus restoration, page-scroll restoration, old missing-song fallback, and legacy
album behavior passed. Temporary viewport overrides were reset afterward.

The live owner popup initially showed FAREWELL TOLEDO / Tiffany Day / Album: HALO
with the verified song and album destinations. Spotify later returned 429 with a
long Retry-After, preventing a complete fresh live catalog/per-tile regeneration
check. The saved October layout remains unchanged and keeps its previous album
representatives. The final screenshot uses the current component with the
previously verified transient HALO/song response in a temporary preview; no
provider payload was added to the persisted archive or Git.

## Song response covers and single song action: 2026-10-06

Successful monthly song lookups now supply the cover and album metadata from the
track response, avoiding the separate album endpoint. The popup shows the cover,
song title, artist, and one Open song in Spotify action. Older snapshots without
saved songs and unavailable-song failures retain an album fallback. Song 429s
propagate the safe error and Retry-After immediately, without an album request,
so the existing artwork loader stops further calls.

`uv run --project backend --locked python scripts/verify.py` passed: **128 backend
tests, zero skips**, static boundaries, Ruff, frontend lint/types/build, and
disposable PostgreSQL migration checks. Regression coverage verifies covers from
track payloads with zero album calls, distinct tile-song selection, malformed
embedded album fallback, owner/membership enforcement, and 10514-second Retry-After
propagation without changes to the archive. The two existing dashboard lint
warnings remain outside this change.

Browser checks through the browser skill used a temporary synthetic fixture with
the actual canvas and popup. The cover, song title, artist, and single verified
track destination appeared; Escape restored focus to the tile. The fixture was
removed after verification. No live Spotify requests were made, so provider
recovery from the reported cooldown remains unverified. Per-request token refresh
and metadata cache lifetime remain unchanged and are further traffic-reduction
opportunities.

## Reuse generation metadata and access tokens: 2026-10-06

New generation returns normalized cover/song metadata from the original top-tracks
response, scoped to the saved tile pairs. The frontend consumes this transient
data directly, avoiding per-song requests for a complete fresh response. Archive
rows and archive GET responses retain IDs/layouts only. Bounded server caches keep
monthly metadata for five minutes and access tokens until 30 seconds before expiry;
credential-version keys and authorization checks protect reuse. Caches are local
to each API process and clear on restart.

Regression checks cover a 43-song generation plus all subsequent detail reads with
exactly two Spotify calls (refresh and top tracks), warm-token generation,
metadata/token expiry, reconnects, session/scope/owner/membership checks, failed
commit isolation, OAuth-token reuse, and bounded 401 retries. A concurrency check
exposed the gap between credential commit and cache publication. Per-owner refresh
coordination now covers both, and tests exercise simultaneous cold requests and
simultaneous 401 responses.

Browser checks used the actual monthly components and loader with synthetic fetch
responses in a temporary route: complete fresh metadata made zero detail calls;
one missing song made one detail call; expired seed data was reloaded; and a 401
after one seeded song displayed the reconnect state without revealing the canvas.
The development Strict Mode expired-data case counted three detail attempts for
two unique songs, including its aborted first effect. The temporary route was
removed. No live Spotify calls were made, so recovery from the existing provider
cooldown remains unverified.

`uv run --project backend --locked python scripts/verify.py` passed: **146 backend
tests, zero skips**, static boundaries, Ruff, frontend lint/types/build, and
disposable PostgreSQL migration checks. Two existing dashboard navigation/image
lint warnings remain outside this change. Browser image downloads are separate
from the Spotify API request budgets above; incomplete provider responses, expired
caches, and bounded retries can require additional requests.

## Cleaner Halloween pumpkin: 2026-10-06

The October shape now uses 84 cover tiles on a 12x12 grid, with a bent stem,
symmetric rounded body, larger triangular eye openings, and a two-tooth grin.
Pumpkin-only spacing decreases to two pixels so the silhouette reads as one shape.
The existing grid/tile limits and Spotify request behavior remain unchanged.

Migration `c28fb53d104e` refines existing 9x9 October 2026 pumpkins by cycling their
saved tile payloads through the new coordinates. It preserves all album/song
pairs, representative-song mappings, identity, selection, and generation time.
It makes no Spotify calls and leaves other months and already-refined layouts
untouched. Like the prior seasonal correction, downgrade retains the new shape.

Browser review used the actual canvas with synthetic covers, comparing old and new
silhouettes at desktop size and a 276-pixel canvas inside a 300-pixel compact card.
The triangular eyes, bent stem, and teeth remained recognizable at both sizes;
cover buttons still opened the correct detail dialog and its close control worked.
The temporary preview route was removed after review. Provider recovery from the
previous rate limit was not tested.

`uv run --project backend --locked python scripts/verify.py` passed: **146 backend
tests, zero skips**, static boundaries, Ruff, frontend lint/types/build, and
disposable PostgreSQL migration checks. The migration regression includes mixed
legacy/song-bearing tiles, preservation of every song ID, an unchanged earlier
month, and downgrade/re-upgrade stability. Two pre-existing dashboard lint warnings
remain outside this change.

The local database was backed up for the affected snapshot before applying
`uv run --locked alembic upgrade head`. One saved pumpkin was corrected. A follow-up
database comparison confirmed all original album/song pairs and every field
outside coordinates/dimensions were preserved; the corrected layout has 84 tiles.

## Explicit generation request-budget verification: 2026-10-06

The request-budget integration test now checks a four-case matrix: 43 or 50
distinct songs, each with a cached access token or a token refresh required.
Each case generates the 84-tile pumpkin, reads details for every tile, reads the
archive, and repeats generation for the same month. It asserts the exact outbound
HTTP method/endpoint sequence, so any extra track, album, or token request fails
the check. Expected totals are one top-tracks GET with a cached token, or one
token POST plus that GET otherwise. Cached detail reads and the repeated generation
add zero Spotify requests.

These are integration checks against disposable PostgreSQL with Spotify HTTP
mocked, not measurements of live provider traffic. The frontend's initial artwork
path was also reviewed: complete unexpired generation metadata skips detail fetches.
Image downloads and OAuth sign-in are separate. Reopening after metadata expiry,
incomplete provider metadata, and a provider-rejected token can exceed the normal
generation budget; it is not a blanket 1–2 limit on every archive visit.

`uv run --project backend --locked python scripts/verify.py` passed: **149 backend
tests, zero skips**, plus boundaries, Ruff, frontend lint/types/build, and migrations.
All four request-budget cases passed their exact endpoint-count assertions.
The two existing dashboard lint warnings remain unchanged.
