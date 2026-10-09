# README screenshots

Captured from the running Mosaic frontend on 2026-10-09.

| File | Source | View |
| --- | --- | --- |
| `mosaic-home.jpg` | `/` | Landing page with the built-in illustrative artwork |
| `mosaic-collection.jpg` | `/monthly` | Saved October collection with real Spotify album covers |
| `mosaic-song-popup.jpg` | `/monthly` → select a cover | Coming Home by beabadoobee with Spotify and song navigation controls |
| `mosaic-studio.jpg` | `/monthly` → Customize | Studio preview using the same saved listening data |

These JPEG files are documentation assets intended to be tracked with the README.
The account owner authorized using their Spotify data for these screenshots.
The collection, song popup, and studio captures use the authenticated application,
not the synthetic QA fixture. Opening and cancelling the customization draft did not
save a variation, replace the listening snapshot, or enable a public artwork link.

To refresh them, run the frontend and API with database migrations applied, open
`http://127.0.0.1:3000/monthly`, and sign in with an account whose owner has agreed
to include its artwork in the repository. Wait for covers to finish loading,
then capture the collection and open Customize for the studio view. Capture the
normal viewport; scroll to include the complete artwork and relevant controls.
Cancel the draft after capturing. Keep file names stable so relative image links
continue to work on GitHub. For a preview without real listening data, use
`/qa-remix` and update the README captions to identify the synthetic content.
