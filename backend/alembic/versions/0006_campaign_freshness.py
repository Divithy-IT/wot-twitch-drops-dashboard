"""campaign freshness and archive

Revision ID: 0006
Revises: 0005
"""
import sqlalchemy as sa

from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("detected_events", sa.Column("freshness_status", sa.String(40), nullable=False, server_default="historical"))
    op.add_column("detected_events", sa.Column("detected_date_text", sa.Text(), nullable=False, server_default=""))
    op.add_column("detected_events", sa.Column("date_confidence", sa.String(20), nullable=False, server_default="none"))
    op.create_index("ix_detected_events_freshness_status", "detected_events", ["freshness_status"])
    op.add_column("campaigns", sa.Column("freshness_status", sa.String(40), nullable=False, server_default="historical"))
    op.add_column("campaigns", sa.Column("archived", sa.Boolean(), nullable=False, server_default=sa.text("false")))
    op.create_index("ix_campaigns_freshness_status", "campaigns", ["freshness_status"])
    op.create_index("ix_campaigns_archived", "campaigns", ["archived"])


def downgrade():
    op.drop_index("ix_campaigns_archived", table_name="campaigns")
    op.drop_index("ix_campaigns_freshness_status", table_name="campaigns")
    op.drop_column("campaigns", "archived")
    op.drop_column("campaigns", "freshness_status")
    op.drop_index("ix_detected_events_freshness_status", table_name="detected_events")
    op.drop_column("detected_events", "date_confidence")
    op.drop_column("detected_events", "detected_date_text")
    op.drop_column("detected_events", "freshness_status")
