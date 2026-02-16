import asyncpg
import os
import json
import asyncio

POSTGRES_DSN = os.getenv("POSTGRES_DSN", "postgresql://postgres:postgres@localhost:5432/dentalogic")

async def debug():
    # Update DSN if needed
    dsn = POSTGRES_DSN.replace("postgresql+asyncpg://", "postgresql://")
    conn = await asyncpg.connect(dsn)
    
    # Buscar mensajes que tengan [Attachment] o que parezcan ser de Instagram con media
    rows = await conn.fetch("""
        SELECT id, role, content, content_attributes, platform_metadata 
        FROM chat_messages 
        WHERE content = '[Attachment]' 
           OR content_attributes != '[]'::jsonb 
           OR platform_metadata::text ILIKE '%instagram%'
        ORDER BY created_at DESC 
        LIMIT 5
    """)
    
    for r in rows:
        print(f"ID: {r['id']}")
        print(f"Role: {r['role']}")
        print(f"Content: {r['content']}")
        print(f"Content Attributes: {r['content_attributes']}")
        # print(f"Platform Metadata: {r['platform_metadata']}") # Might be too large
        
        meta = r['platform_metadata']
        if meta:
            try:
                if isinstance(meta, str):
                    meta = json.loads(meta)
                # Check for attachments in meta
                print(f"Meta Attachments: {meta.get('attachments')}")
                if 'content_attributes' in meta:
                    print(f"Meta Content Attributes: {meta.get('content_attributes')}")
            except:
                print("Failed to parse metadata")
        print("-" * 20)
    
    await conn.close()

if __name__ == "__main__":
    asyncio.run(debug())
