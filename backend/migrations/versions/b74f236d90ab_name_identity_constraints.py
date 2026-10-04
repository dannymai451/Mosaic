"""Give existing identity uniqueness constraints stable names.

Revision ID: b74f236d90ab
Revises: 9ee70c8293f1
"""

from alembic import op

revision = "b74f236d90ab"
down_revision = "9ee70c8293f1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE users RENAME CONSTRAINT users_spotify_account_id_key "
        "TO uq_users_spotify_account_id"
    )
    op.execute(
        "ALTER TABLE profiles RENAME CONSTRAINT profiles_username_key "
        "TO uq_profiles_username"
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE profiles RENAME CONSTRAINT uq_profiles_username "
        "TO profiles_username_key"
    )
    op.execute(
        "ALTER TABLE users RENAME CONSTRAINT uq_users_spotify_account_id "
        "TO users_spotify_account_id_key"
    )
