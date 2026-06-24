import asyncio
from db import db

async def check():
    await db.connect()
    try:
        # check conversations
        rows = await db.fetch("SELECT external_user_id FROM chat_conversations WHERE external_user_id LIKE '%3704868421%'")
        print("conversations:", [r['external_user_id'] for r in rows])
        
        # check patients
        rows2 = await db.fetch("SELECT phone_number FROM patients WHERE phone_number LIKE '%3704868421%'")
        print("patients:", [r['phone_number'] for r in rows2])
    finally:
        await db.disconnect()

asyncio.run(check())
