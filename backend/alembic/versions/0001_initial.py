"""initial schema"""
import sqlalchemy as sa

from alembic import op

revision="0001";down_revision=None;branch_labels=None;depends_on=None
def upgrade():
 op.create_table("admins",sa.Column("id",sa.Integer(),primary_key=True),sa.Column("username",sa.String(80),nullable=False,unique=True),sa.Column("password_hash",sa.String(255),nullable=False),sa.Column("created_at",sa.DateTime(timezone=True),nullable=False),sa.Column("session_version",sa.Integer(),nullable=False))
 op.create_table("campaigns",sa.Column("id",sa.Integer(),primary_key=True),sa.Column("title",sa.String(200),nullable=False),sa.Column("description",sa.Text(),nullable=False),sa.Column("starts_at",sa.DateTime(timezone=True),nullable=False,index=True),sa.Column("ends_at",sa.DateTime(timezone=True),nullable=False,index=True),sa.Column("required_minutes",sa.Integer(),nullable=False),sa.Column("eligible_channels",sa.JSON(),nullable=False),sa.Column("category_name",sa.String(120),nullable=False),sa.Column("link_url",sa.String(500),nullable=False),sa.Column("source_type",sa.Enum("twitch","wargaming","manual",name="sourcetype"),nullable=False),sa.Column("source_url",sa.String(500),nullable=False),sa.Column("source_updated_at",sa.DateTime(timezone=True),nullable=False),sa.Column("watched_minutes",sa.Integer(),nullable=False),sa.Column("progress_source",sa.Enum("official","manual","estimated",name="progresssource"),nullable=False),sa.Column("last_progress_at",sa.DateTime(timezone=True)))
 op.create_table("rewards",sa.Column("id",sa.Integer(),primary_key=True),sa.Column("campaign_id",sa.Integer(),sa.ForeignKey("campaigns.id",ondelete="CASCADE"),nullable=False),sa.Column("name",sa.String(200),nullable=False),sa.Column("required_minutes",sa.Integer(),nullable=False),sa.Column("earned",sa.Boolean(),nullable=False),sa.Column("claimed",sa.Boolean(),nullable=False))
 op.create_table("twitch_connections",sa.Column("id",sa.Integer(),primary_key=True),sa.Column("twitch_user_id",sa.String(80),nullable=False),sa.Column("login",sa.String(120),nullable=False),sa.Column("access_token_encrypted",sa.Text(),nullable=False),sa.Column("refresh_token_encrypted",sa.Text(),nullable=False),sa.Column("scopes",sa.JSON(),nullable=False),sa.Column("expires_at",sa.DateTime(timezone=True),nullable=False),sa.Column("last_synced_at",sa.DateTime(timezone=True)))
 op.create_table("app_settings",sa.Column("key",sa.String(100),primary_key=True),sa.Column("value",sa.JSON(),nullable=False))
 op.create_table("event_logs",sa.Column("id",sa.Integer(),primary_key=True),sa.Column("event_type",sa.String(80),nullable=False,index=True),sa.Column("level",sa.String(20),nullable=False),sa.Column("message",sa.String(500),nullable=False),sa.Column("details",sa.JSON(),nullable=False),sa.Column("created_at",sa.DateTime(timezone=True),nullable=False,index=True))
 op.create_table("notification_deliveries",sa.Column("id",sa.Integer(),primary_key=True),sa.Column("dedupe_key",sa.String(250),nullable=False),sa.Column("channel",sa.String(30),nullable=False),sa.Column("sent_at",sa.DateTime(timezone=True),nullable=False),sa.UniqueConstraint("dedupe_key","channel"))
def downgrade():
 for t in ["notification_deliveries","event_logs","app_settings","twitch_connections","rewards","campaigns","admins"]:op.drop_table(t)
 op.execute("DROP TYPE IF EXISTS progresssource");op.execute("DROP TYPE IF EXISTS sourcetype")
