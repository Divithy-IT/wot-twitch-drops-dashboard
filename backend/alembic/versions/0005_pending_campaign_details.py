"""allow officially confirmed campaigns to await details"""
import sqlalchemy as sa

from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column("campaigns", "starts_at", existing_type=sa.DateTime(timezone=True), nullable=True)
    op.alter_column("campaigns", "ends_at", existing_type=sa.DateTime(timezone=True), nullable=True)
    op.alter_column("campaigns", "required_minutes", existing_type=sa.Integer(), nullable=True)
    op.execute("DELETE FROM app_settings WHERE key = 'drop_qualification_rules'")


def downgrade():
    # A downgrade would require inventing dates for campaigns awaiting details.
    raise RuntimeError("Downgrade requires manual completion of missing campaign details")
