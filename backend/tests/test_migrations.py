"""The session fixture builds a blank database with Alembic, not create_all."""

import os
import subprocess


def test_migrations_match_models(migrated_database_url):
    subprocess.run(
        ["uv", "run", "alembic", "check"],
        env={**os.environ, "DATABASE_URL": migrated_database_url},
        check=True,
    )
