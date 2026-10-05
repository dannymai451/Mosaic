# Phase 3 acceptance verification

Source: `Music_Profile_Project_Plan.pdf`, page 13, "Profile CRUD and read-only sharing".
Outcome: owners edit profiles and share a public URL that logged-out visitors read.
No schema migration or new dependencies are required.

## Scope and acceptance evidence

| Requirement | Implementation / verification |
| --- | --- |
| Edit username, display name, bio, visibility, theme | Settings supports preview, save, reset to last save, validation/conflict/expiry feedback, and retained drafts after failure. Browser save and refresh checked. |
| PATCH validation and uniqueness errors | Existing owner API plus `test_profile_update_api.py`; generated first-login usernames now fit its limits. |
| Public DTO and `/@username` shell | Public GET and server page; shared card applies saved theme. Browser checks include encoded handles. |
| Share with copy-link fallback | Native Web Share, direct Copy link, clipboard fallback, selectable URL when copying is unavailable. Native invocation and direct copy checked in Chrome. |
| Private profiles not exposed publicly | `test_public_profiles.py`: private/missing both 404, even with owner cookie; public-to-private transition. Browser private-link withdrawal checked. |
| Logged-out browser opens public link | Browser opened the fixture's public URL before any test session; owner settings simultaneously showed the signed-out prompt. |
| Non-owner writes fail server-side | API tests cover anonymous/unknown sessions, forged identities, other owners, username takeover, and mutation verbs on the public endpoint. Other owners' normal PATCH affects only themselves. |
| Mobile layout at 360-430px | Both public page and populated editor checked at 360, 390, and 430px; no horizontal overflow. Screenshot inspection verified card and form controls. |

## Automated checks

From the root with dependencies installed and Docker running:

```sh
uv run --project backend --locked python scripts/verify.py
```

This includes migration/schema verification, all backend tests in disposable
PostgreSQL, architecture checks, Ruff, frontend lint, types, and production build.
No skipped database tests count as acceptance. Frontend behavior uses the browser
checklist below; there is no frontend unit/browser testing framework.

## Repeatable browser checklist

Use `127.0.0.1` consistently and follow README setup. Use a test owner and record
existing values before editing a real profile.

1. Signed out, open settings: expect Connect Spotify, no editable form.
2. Sign in, open settings. Preview edits without saving: public link retains saved
   data. Reset edits: values return to the last save.
3. Change all editable fields, choose Public and a theme, and Save changes. Expect
   "Profile saved." Refresh: values persist. Edit again and Reset: restore that save.
4. Try a taken username: expect an inline conflict, retained draft, and unchanged
   saved profile/link. Try invalid/blank values: expect validation without saving.
5. View public profile. Copy link: expect "Link copied." and a URL ending in the
   saved username. Open that URL while logged out: name, bio, avatar and theme load.
   No editing controls appear. Test `/@username` and `/%40username`; both must work.
6. Share profile: invoke the platform share UI; cancel without sending to anyone.
   In a browser without native share, expect clipboard copying. When clipboard
   permission is denied/unavailable, expect a selectable URL. Native destination
   delivery is platform-dependent and not part of the automated checks.
7. Rename and save: sharing uses the new URL, and the old URL is unavailable. Save
   Private: sharing controls disappear; reload the shared URL while logged out
   and expect "Profile unavailable" with no profile details. Missing names show
   the same unavailable message.
8. At 360, 390 and 430px, inspect the editor and public page: no horizontal scroll,
   readable labels, wrapping buttons, accessible radio options, and long text
   contained in the card. Try long display names/bios and each theme.
9. Stop the API during loading: retry UI appears. Stop it during saving: edits
   remain and an error appears. Expire/log out the session before saving: expect
   the reconnect prompt. Restart the API and retry.

## Recorded run and limits

On October 5, 2026, the final full verifier passed all 44 tests with no skips,
including lint, types, production build, migrations and guardrails.
Browser checks used temporary fixture accounts in a disposable PostgreSQL
container and the real API, without real Spotify credentials or development data.
They confirmed save/reload, username conflict, rename, privacy withdrawal,
anonymous reading, sharing controls, and mobile widths. The fixture was removed.

Live Spotify sign-in and native share delivery to another app were not exercised.
The existing dashboard has two ESLint warnings (internal navigation and raw image).
Production CORS/cookie configuration remains separate deployment work.
