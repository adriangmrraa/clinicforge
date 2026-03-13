import asyncio
import os
import asyncpg
import json

async def main():
    dsn = os.getenv("POSTGRES_DSN")
    if not dsn:
        print("Error: POSTGRES_DSN not set")
        return
    
    dsn = dsn.replace("postgresql+asyncpg://", "postgresql://")
    conn = await asyncpg.connect(dsn)
    
    query = "SELECT id, tenant_id, code, name, is_active, is_available_for_booking FROM treatment_types WHERE name ILIKE '%beyond%'"
    rows = await conn.fetch(query)
    
    print("--- BEYOND SEARCH ---")
    for r in rows:
        print(dict(r))
        
    query_all = "SELECT code, name FROM treatment_types WHERE is_active = true AND is_available_for_booking = true LIMIT 20"
    rows_all = await conn.fetch(query_all)
    print("\n--- AVAILABLE SERVICES (TOP 20) ---")
    for r in rows_all:
        print(dict(r))
        
    await conn.close()

if __name__ == "__main__":
    asyncio.run(main())
