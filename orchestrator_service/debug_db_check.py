import asyncio
import asyncpg
import os

# Usamos la DSN directa para evitar problemas de importación
DSN = 'postgresql://postgres:password@localhost:5432/clinica_dental_db'

async def main():
    print(f"Connecting to {DSN}...")
    try:
        pool = await asyncpg.create_pool(DSN)
        async with pool.acquire() as conn:
            print("\n--- PATIENTS ---")
            patients = await conn.fetch("SELECT id, phone_number, first_name, last_name FROM patients")
            if not patients:
                print("No patients found.")
            for p in patients:
                print(dict(p))
            
            print("\n--- CHAT MESSAGES (Last 10) ---")
            messages = await conn.fetch("SELECT id, from_number, role, content FROM chat_messages ORDER BY created_at DESC LIMIT 10")
            if not messages:
                print("No messages found.")
            for m in messages:
                print(dict(m))
                
        await pool.close()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(main())
