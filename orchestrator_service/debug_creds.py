import asyncio
import os
from db import db
from dotenv import load_dotenv

async def check():
    load_dotenv()
    await db.connect()
    tenants = await db.pool.fetch("SELECT * FROM tenants")
    print(f"Tenants in DB: {len(tenants)}")
    for t in tenants:
        print(f"ID: {t['id']}, Name: {t['store_name']}, Phone: {t['bot_phone_number']}")
    
    creds = await db.pool.fetch("SELECT name, value, scope FROM credentials WHERE name = 'OPENAI_API_KEY'")
    for c in creds:
        val = c['value']
        masked = val[:7] + "..." + val[-4:] if val else "None"
        print(f"Cred: {c['name']}, Scope: {c['scope']}, Value: {masked}")
    
    env_key = os.getenv("OPENAI_API_KEY")
    masked_env = env_key[:7] + "..." + env_key[-4:] if env_key else "None"
    print(f"Env Key: {masked_env}")
    
    await db.disconnect()

if __name__ == "__main__":
    asyncio.run(check())
