"""Mark temporary public demo accounts for expiry cleanup."""
from alembic import op
import sqlalchemy as sa

revision = "0002_public_demo_guests"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("is_demo_guest", sa.Boolean(), server_default=sa.false(), nullable=False),
    )


def downgrade() -> None:
    op.drop_column("users", "is_demo_guest")
