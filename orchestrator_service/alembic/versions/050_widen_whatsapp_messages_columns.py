"""
050: Widen whatsapp_messages VARCHAR columns for YCloud IDs.

YCloud IDs like '69dc1583b83a111507d2d28b' are 24 chars, but wamid
can be much longer. Widen all ID fields to 256 to be safe.
"""

revision = "050"
down_revision = "049"


def upgrade():
    from alembic import op
    import sqlalchemy as sa

    # Widen all VARCHAR columns that were too short
    op.alter_column("whatsapp_messages", "external_id", type_=sa.String(256))
    op.alter_column("whatsapp_messages", "wamid", type_=sa.String(256))
    op.alter_column("whatsapp_messages", "from_number", type_=sa.String(64))
    op.alter_column("whatsapp_messages", "to_number", type_=sa.String(64))
    op.alter_column("whatsapp_messages", "media_url", type_=sa.String(1024))
    op.alter_column("whatsapp_messages", "media_id", type_=sa.String(256))


def downgrade():
    from alembic import op
    import sqlalchemy as sa

    op.alter_column("whatsapp_messages", "external_id", type_=sa.String(64))
    op.alter_column("whatsapp_messages", "wamid", type_=sa.String(64))
    op.alter_column("whatsapp_messages", "from_number", type_=sa.String(32))
    op.alter_column("whatsapp_messages", "to_number", type_=sa.String(32))
    op.alter_column("whatsapp_messages", "media_url", type_=sa.String(512))
    op.alter_column("whatsapp_messages", "media_id", type_=sa.String(128))
