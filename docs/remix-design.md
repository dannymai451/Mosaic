# Monthly remixes and interactive sharing

## Current state and intended change

Monthly snapshots store listening IDs and a fixed layout. They are private and
immutable; catalog details are transient. Tiny mobile tiles currently open a
centered dialog. The requested extension adds saved visual variations, background
photos/colors, flexible frames, minimal story exports, and opt-in interactive links.

## Implementation boundaries

- Keep the listening snapshot intact. A separate `artwork_remixes` table references
  it and stores design settings/layout, an optional normalized background photo,
  and an optional random share token. Limit each snapshot to 12 saved variations.
- Generate Halloween coordinates from existing saved album/song pairs. Every pair
  remains available in the song list; reshaping never contacts Spotify.
- Reuse the current metadata resolver/cache after owner or public-link membership
  checks. Public sharing exposes only that variation, month, display name, and its
  song references. Link revocation applies to metadata and background endpoints too.
- Normalize uploaded JPEG/PNG/WebP images with Pillow, strip metadata, bound input
  bytes/pixels, and store the resulting JPEG in PostgreSQL. This avoids an unconfigured
  external storage dependency for this local app; object storage is the future
  scaling alternative. No remote image URLs are accepted as uploads.
- Share cards are generated in the browser at square/story sizes with minimal
  typography. They use the same frame settings and cover layout as the viewer.
  Native sharing has a download/copy-link fallback. Image cards themselves are
  static; the explicitly enabled link opens the interactive song explorer.
- Shared and private artwork use one mobile explorer with a song list, enlarged
  canvas, zoom controls, and a bottom song card with previous/next navigation.

## Migration and risks

Add a table; do not rewrite monthly rows or change legacy public profiles. Owner
writes lock the profile before enforcing the variation limit. Sharing is disabled
by default and is a separate explicit owner action. Disabling a link invalidates
it; re-enabling creates a new token. All responses are no-store. Uploaded image
and catalog availability failures must preserve the saved design and expose retry.
Metadata cache misses still require Spotify calls; remixing and export do not
re-fetch top tracks. Mobile native sharing requires a supported secure context;
downloads and link copying remain available. Image CORS failures prevent a
misleading partial export and are surfaced to the user.

## Verification

Integration checks cover owner isolation, immutable source data, shape membership,
save/update/delete, share/revoke, public metadata scope, upload normalization and
limits, and unchanged generation budgets. Browser checks cover mobile exploration,
editor drafts/persistence, upload, frames, shared anonymous view, revoked links,
and exported images. Run the repository verifier before local migration.

## Verification record: 2026-10-08

`uv run --project backend --locked python scripts/verify.py` passed: **155 backend
tests, zero skips**, architecture boundaries, Ruff, frontend lint/types/build, and
disposable PostgreSQL migration checks. The QA preview now mounts on the next
browser frame after its fetch mock is installed, fixing the initial lint failure.
The two existing dashboard lint warnings remain unchanged. Spotify requests are
mocked in the automated suite; browser and live-provider acceptance were not rerun
for this commit.
