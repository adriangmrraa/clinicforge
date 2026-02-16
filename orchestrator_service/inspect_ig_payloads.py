import asyncio
import asyncpg
import os
import json

POSTGRES_DSN = os.getenv("POSTGRES_DSN")

async def inspect_instagram_payloads():
    if not POSTGRES_DSN:
        print("❌ POSTGRES_DSN not set")
        return

    conn = await asyncpg.connect(POSTGRES_DSN)
    try:
        # Buscar mensajes récientes de Instagram que tengan contenido [Attachment]
        rows = await conn.fetch("""
            SELECT content, platform_metadata, content_attributes 
            FROM chat_messages 
            WHERE content LIKE '%[Attachment]%' 
            ORDER BY created_at DESC 
            LIMIT 5
        """)
        
        for i, row in enumerate(rows):
            print(f"\n--- MESSAGE {i+1} ---")
            print(f"Content: {row['content']}")
            print(f"Content Attributes (Extracted): {row['content_attributes']}")
            
            meta = row['platform_metadata']
            if isinstance(meta, str):
                try:
                    meta = json.loads(meta)
                except:
                    pass
            
            if meta:
                # Buscar attachments en el payload crudo
                print("RAW PAYLOAD KEYS:", meta.keys() if isinstance(meta, dict) else "Not a dict")
                if isinstance(meta, dict):
                    # Dump relevant parts
                    msg = meta.get('message', {})
                    print("MESSAGE KEYS:", msg.keys())
                    print("MESSAGE ATTACHMENTS:", msg.get('attachments'))
                    if 'attachments' not in msg:
                        print("FULL PAYLOAD DUMP (first 2000 chars):", json.dumps(meta)[:2000])
            else:
                print("No platform_metadata available")

    finally:
        await conn.close()

if __name__ == "__main__":
    asyncio.run(inspect_instagram_payloads())
