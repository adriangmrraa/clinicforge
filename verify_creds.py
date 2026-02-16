import asyncio
import os
from dotenv import load_dotenv
import asyncpg

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

async def check_creds():
    conn = await asyncpg.connect(DATABASE_URL)
    rows = await conn.fetch("SELECT id, name, category, scope, tenant_id, created_at FROM credentials WHERE category = 'chatwoot' ORDER BY created_at DESC")
    print(f"Found {len(rows)} chatwoot credentials:")
    for r in rows:
        print(dict(r))
    await conn.close()

if __name__ == "__main__":
    asyncio.run(check_creds())
