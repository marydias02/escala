"""create webapp schema and sessions table

Revision ID: 20260908_01
Revises: 20260827_01
Create Date: 2026-09-08 00:00:00.000000

Server-side session store for the Dash frontend's OIDC sign-in. The backend owns
the schema — the frontend has no Alembic and no ORM — but the backend never reads
this table; the frontend's custom Flask SessionInterface writes it directly.

It lives in its own `webapp` schema rather than in `public` to keep session rows
out of the application tables' namespace. Right now both the frontend and backend
share one login with full schema access, but this way we keep the option of
creating a separate user for the frontend that can only access this schema.
When/if this user is created run these lines to grant it only access to the webapp schema:

    GRANT USAGE ON SCHEMA webapp TO <frontend_db_user>;
    GRANT SELECT, INSERT, UPDATE, DELETE ON webapp.sessions TO <frontend_db_user>;

`data` is bytes, not JSON, because the payload holds refresh tokens and is
Fernet-encrypted before it ever reaches the database. That also makes the column
opaque to anything but the frontend, which is the point.

`expires_at` is indexed for the periodic `DELETE WHERE expires_at < now()` sweep
(`scripts/sweep_sessions.py`); without the index that sweep degrades into a
sequential scan of every live session on every run.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260908_01"
down_revision: str | Sequence[str] | None = "20260827_01"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute("CREATE SCHEMA IF NOT EXISTS webapp")
    op.create_table(
        "sessions",
        sa.Column("session_id", sa.String(length=64), primary_key=True),
        sa.Column("data", sa.LargeBinary(), nullable=False),
        sa.Column("expires_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        schema="webapp",
    )
    op.create_index(
        "ix_webapp_sessions_expires_at",
        "sessions",
        ["expires_at"],
        schema="webapp",
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(
        "ix_webapp_sessions_expires_at",
        table_name="sessions",
        schema="webapp",
    )
    op.drop_table("sessions", schema="webapp")
    op.execute("DROP SCHEMA IF EXISTS webapp RESTRICT")
