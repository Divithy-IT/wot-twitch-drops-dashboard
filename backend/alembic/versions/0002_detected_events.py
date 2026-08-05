"""detected events, source cache and watched channels"""
import sqlalchemy as sa

from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None

def upgrade():
    confidence = sa.Enum("low", "medium", "high", name="confidence")
    detection = sa.Enum("pending", "approved", "rejected", "duplicate", name="detectionstatus")
    op.create_table("detected_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("fingerprint", sa.String(64), nullable=False, unique=True),
        sa.Column("title", sa.String(300), nullable=False), sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True)), sa.Column("starts_at", sa.DateTime(timezone=True)),
        sa.Column("ends_at", sa.DateTime(timezone=True)), sa.Column("stream_times", sa.JSON(), nullable=False),
        sa.Column("probable_rewards", sa.JSON(), nullable=False), sa.Column("required_minutes", sa.Integer()),
        sa.Column("source_url", sa.String(600), nullable=False, unique=True),
        sa.Column("source_name", sa.String(120), nullable=False), sa.Column("last_checked_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("excerpt", sa.Text(), nullable=False), sa.Column("confidence", confidence, nullable=False),
        sa.Column("event_type", sa.String(50), nullable=False), sa.Column("status", detection, nullable=False),
        sa.Column("approved_campaign_id", sa.Integer(), sa.ForeignKey("campaigns.id", ondelete="SET NULL")))
    op.create_index("ix_detected_events_fingerprint", "detected_events", ["fingerprint"])
    op.create_table("source_cache", sa.Column("url", sa.String(600), primary_key=True),
        sa.Column("etag", sa.String(300), nullable=False), sa.Column("last_modified", sa.String(300), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False), sa.Column("checked_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_error", sa.String(500), nullable=False))
    op.create_table("watched_channels", sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("login", sa.String(100), nullable=False, unique=True), sa.Column("drops_confirmed", sa.Boolean(), nullable=False),
        sa.Column("drops_source_url", sa.String(600), nullable=False), sa.Column("drops_verified_at", sa.DateTime(timezone=True)))

def downgrade():
    op.drop_table("watched_channels"); op.drop_table("source_cache")
    op.drop_index("ix_detected_events_fingerprint", table_name="detected_events"); op.drop_table("detected_events")
    sa.Enum(name="detectionstatus").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="confidence").drop(op.get_bind(), checkfirst=True)
