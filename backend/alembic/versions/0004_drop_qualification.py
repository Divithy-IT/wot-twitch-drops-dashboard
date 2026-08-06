"""trusted sources and auditable Drops qualification"""
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade():
    decision = postgresql.ENUM("auto_approve", "manual_review", "auto_ignore",
                               name="qualificationdecision", create_type=False)
    value = postgresql.ENUM("high", "medium", "low", "unknown", name="rewardvalue", create_type=False)
    decision.create(op.get_bind(), checkfirst=True)
    value.create(op.get_bind(), checkfirst=True)
    for column in (
        sa.Column("confidence_score", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("reward_value", value, nullable=False, server_default="unknown"),
        sa.Column("auto_approved", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("verification_reason", sa.Text(), nullable=False, server_default=""),
        sa.Column("verified_at", sa.DateTime(timezone=True)),
    ):
        op.add_column("campaigns", column)
    for column in (
        sa.Column("qualification_decision", decision, nullable=False, server_default="manual_review"),
        sa.Column("confidence_score", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("reward_value", value, nullable=False, server_default="unknown"),
        sa.Column("matched_keywords", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("score_breakdown", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("decision_reason", sa.Text(), nullable=False, server_default=""),
        sa.Column("decided_by", sa.String(30), nullable=False, server_default="automation"),
        sa.Column("decided_at", sa.DateTime(timezone=True)),
        sa.Column("source_verified_at", sa.DateTime(timezone=True)),
        sa.Column("source_content_hash", sa.String(64), nullable=False, server_default=""),
    ):
        op.add_column("detected_events", column)
    op.create_table("trusted_sources",
        sa.Column("id", sa.Integer(), primary_key=True), sa.Column("name", sa.String(160), nullable=False),
        sa.Column("url_pattern", sa.String(600), nullable=False, unique=True),
        sa.Column("enabled", sa.Boolean(), nullable=False), sa.Column("auto_approve", sa.Boolean(), nullable=False),
        sa.Column("max_trust_score", sa.Integer(), nullable=False), sa.Column("ignored", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False))
    op.create_table("decision_history",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("detected_event_id", sa.Integer(), sa.ForeignKey("detected_events.id", ondelete="CASCADE"), nullable=False),
        sa.Column("decision", decision, nullable=False), sa.Column("score", sa.Integer(), nullable=False),
        sa.Column("reward_value", value, nullable=False), sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("score_breakdown", sa.JSON(), nullable=False), sa.Column("matched_keywords", sa.JSON(), nullable=False),
        sa.Column("actor", sa.String(30), nullable=False), sa.Column("action", sa.String(60), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False))
    op.create_index("ix_decision_history_detected_event_id", "decision_history", ["detected_event_id"])
    op.create_index("ix_decision_history_created_at", "decision_history", ["created_at"])
    op.execute("""INSERT INTO trusted_sources
        (name,url_pattern,enabled,auto_approve,max_trust_score,ignored,created_at) VALUES
        ('World of Tanks EU','https://worldoftanks.eu/',true,true,100,false,now()),
        ('Wargaming','https://wargaming.com/',true,true,100,false,now()),
        ('Oficjalny Twitch World of Tanks','https://www.twitch.tv/worldoftanks',true,true,100,false,now())
        ON CONFLICT (url_pattern) DO NOTHING""")


def downgrade():
    op.drop_table("decision_history")
    op.drop_table("trusted_sources")
    for name in ("source_content_hash","source_verified_at","decided_at","decided_by","decision_reason","score_breakdown","matched_keywords","reward_value","confidence_score","qualification_decision"):
        op.drop_column("detected_events", name)
    for name in ("verified_at","verification_reason","auto_approved","reward_value","confidence_score"):
        op.drop_column("campaigns", name)
    sa.Enum(name="qualificationdecision").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="rewardvalue").drop(op.get_bind(), checkfirst=True)
