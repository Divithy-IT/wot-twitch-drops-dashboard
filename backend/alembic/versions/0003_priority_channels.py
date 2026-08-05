"""seed priority World of Tanks channels"""
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
        INSERT INTO watched_channels (login, drops_confirmed, drops_source_url)
        VALUES ('worldoftanks', false, ''), ('cyganzor', false, ''), ('german_intelligence', false, '')
        ON CONFLICT (login) DO NOTHING
    """)


def downgrade():
    # Do not delete channels: administrators may have edited their verification metadata.
    pass
