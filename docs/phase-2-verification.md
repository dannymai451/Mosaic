# Phase 2 acceptance verification

Phase 2 is PostgreSQL schema and migrations: connected users persist locally and database changes are versioned.

## Automated acceptance checks

From the repository root, with Docker running:

```bash
cd backend
uv sync --locked
uv run python scripts/verify_phase2.py
```

Expected: **all tests pass, no skips**, exit code zero (the suite has grown since Phase 2).
For the standard whole-repository check, run
`uv run --project backend --locked python scripts/verify.py` from the root.
The database script uses a temporary PostgreSQL 18 container on a random loopback port, creates a random database, migrates it from blank, and removes both afterward. It leaves the development database untouched. Spotify HTTP calls are mocked; no Spotify account or real credentials are needed.

| Requirement | Automated evidence |
| --- | --- |
| `alembic upgrade head` builds a blank database | The fixture creates a new database and applies every migration; `test_migrations_match_models` runs `alembic check`. |
| OAuth callback upserts the same user on repeat login | `test_repeat_login_restart_expiry_and_logout` follows start/callback twice over HTTP and checks one user, one profile, and one connection with the same IDs. Profile edits survive. |
| Repository tests use a disposable database | All four repository scenarios run against the temporary database, with isolated schemas for each scenario. |
| One local user/profile fixture | The repository seed test verifies repeated seeding preserves edits and produces one pair. |
| Connected users survive process restart | The HTTP test sends the session cookie to a new Python interpreter and verifies `/api/me` returns the persisted profile. |
| Server-side credentials and durable logout | Tests decrypt stored ciphertext with the test key, verify the cookie is stored only as a digest, and check logout/expired/unknown cookies return 401. |
| Atomic failure handling | A first login lacking a refresh token rolls back the user and sets no session cookie. |

A direct `uv run pytest -ra` needs `TEST_DATABASE_URL` pointing to PostgreSQL with CREATE DATABASE permission. The wrapper above supplies this automatically. Seeing skips is not an acceptance pass.

## Local app setup

From the repository root:

```bash
docker compose up -d db
cd backend
uv sync --locked
```

Keep real Spotify settings in `backend/.env`. Set `DATABASE_URL` to match the root Compose `.env`. Generate an encryption key once if none exists:

```bash
uv run python - <<'PY'
from pathlib import Path
from cryptography.fernet import Fernet
from dotenv import dotenv_values, set_key
path = Path('.env')
if not dotenv_values(path).get('TOKEN_ENCRYPTION_KEY'):
    set_key(path, 'TOKEN_ENCRYPTION_KEY', Fernet.generate_key().decode())
print('Local encryption key configured.')
PY
uv run alembic upgrade head
uv run alembic check
uv run python -m app.db.seed --local
uv run python -m app.db.seed --local
uv run fastapi dev
```

Expected: migrations reach `c81e702f41d2`, Alembic reports no new upgrade operations, and both seed runs report the same local fixture. Keep the key stable across restarts so existing tokens remain decryptable. Fernet provides authenticated encryption ([official documentation](https://cryptography.io/en/latest/fernet/)); the key stays in the ignored `.env`.

In a second terminal:

```bash
cd frontend
npm ci
npm run dev
```

## Live end-to-end browser checklist

Use the configured frontend origin consistently (normally `http://127.0.0.1:3000`) and the Spotify developer app's registered redirect URI. Use an allowlisted Spotify account.

1. Open `/connect`, connect Spotify, and confirm `/dashboard` displays your name and avatar. In browser Network tools, `/api/me` returns 200 with `username`, `displayName`, `images`, `bio`, `visibility`, and `theme`, and no Spotify tokens. The live identity-response contract is not covered by mocks; see [known architectural debt](ARCHITECTURE.md#known-architectural-debt).
2. From the repository root, inspect persistence without printing token values:

   ```bash
   docker compose exec db sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB"' <<'SQL'
   SELECT u.id, u.spotify_account_id, p.id AS profile_id, p.username,
          p.display_name, p.visibility
   FROM users u JOIN profiles p ON p.user_id = u.id ORDER BY u.created_at;
   SELECT spotify_account_id, count(*) FROM users GROUP BY spotify_account_id;
   SELECT count(*) AS connection_count FROM spotify_connections;
   SELECT length(id) AS digest_length, expires_at FROM sessions;
   SELECT count(*) AS fixture_count FROM profiles WHERE username = 'mosaic_local_test';
   SQL
   ```

   Expected: one row for your Spotify account, a private profile with a generated `user_...` username, one connection per connected user, 64-character session digests, and one fixture. The fixture has no Spotify connection.
3. Record your user ID and profile ID. Connect again with the same Spotify account (open `/connect` while signed in). Run the queries again. Expected: same IDs and one user/profile/connection for that account. Each successful login creates a fresh session; multiple session rows are expected until logout or expiry.
4. Stop and restart only FastAPI. Refresh `/dashboard` within one hour, keeping the browser cookie. Expected: still signed in and `/api/me` returns 200. No reconnect is needed.
5. Click logout. Expected: logout returns 204, the cookie disappears, and `/api/me` returns 401. The current session row is deleted; user/profile/connection remain. An older session from a different login remains valid until its expiry or its own logout.
6. Connect once more. Expected: same user/profile IDs; a new valid session.
7. Confirm browser storage and `/api/me` contain no Spotify access or refresh tokens. The `mosaic_session` cookie is HttpOnly. Local HTTP cookies become Secure when production HTTPS configuration is introduced.

The automated suite verifies expiry by setting the test session's expiry into the past; there is no need to wait an hour or edit the development database.

## Historical Phase 2 completion record

At Phase 2 completion, all 10 then-existing tests passed with no skips, including a fresh-process session read and a blank-database migration check. Local migration and seed validation were recorded during that implementation. This historical count is not the current suite size. The live Spotify/browser checklist requires your Spotify login and has not been claimed as performed by automation.
