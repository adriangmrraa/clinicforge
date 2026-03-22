"""Add Meta Direct support: business_assets table, PSIDs on patients, conversation enrichment columns

Revision ID: e5f6g7h8i9j0
Revises: d4e5f6g7h8i9
Create Date: 2026-03-22

Enables Meta Native Connection (Instagram DM, Facebook Messenger, WhatsApp Cloud API)
as a third provider alongside Chatwoot and YCloud.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'e5f6g7h8i9j0'
down_revision: Union[str, Sequence[str]] = 'd4e5f6g7h8i9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. business_assets table (discovered Pages, IG accounts, WABAs)
    op.execute("""
    CREATE TABLE IF NOT EXISTS business_assets (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        tenant_id INTEGER REFERENCES tenants(id) ON DELETE CASCADE,
        asset_type TEXT NOT NULL,
        content JSONB NOT NULL,
        is_active BOOLEAN DEFAULT true,
        created_at TIMESTAMPTZ DEFAULT NOW(),
        updated_at TIMESTAMPTZ DEFAULT NOW()
    );

    CREATE INDEX IF NOT EXISTS idx_business_assets_tenant ON business_assets(tenant_id);
    CREATE INDEX IF NOT EXISTS idx_business_assets_content_id ON business_assets((content->>'id'));
    """)

    # 2. PSIDs on patients (Meta uses PSIDs, not phone numbers for IG/FB)
    op.execute("""
    ALTER TABLE patients ADD COLUMN IF NOT EXISTS instagram_psid TEXT;
    ALTER TABLE patients ADD COLUMN IF NOT EXISTS facebook_psid TEXT;
    CREATE INDEX IF NOT EXISTS idx_patients_ig_psid ON patients(tenant_id, instagram_psid);
    CREATE INDEX IF NOT EXISTS idx_patients_fb_psid ON patients(tenant_id, facebook_psid);
    """)

    # 3. Enrichment columns on chat_conversations
    op.execute("""
    ALTER TABLE chat_conversations ADD COLUMN IF NOT EXISTS source_entity_id TEXT;
    ALTER TABLE chat_conversations ADD COLUMN IF NOT EXISTS platform_origin TEXT;
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS business_assets;")
    op.execute("""
    ALTER TABLE patients DROP COLUMN IF EXISTS instagram_psid;
    ALTER TABLE patients DROP COLUMN IF EXISTS facebook_psid;
    """)
    op.execute("""
    ALTER TABLE chat_conversations DROP COLUMN IF EXISTS source_entity_id;
    ALTER TABLE chat_conversations DROP COLUMN IF EXISTS platform_origin;
    """)
