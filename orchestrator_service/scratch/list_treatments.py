import asyncio
from db import db

async def main():
    await db.connect()
    rows = await db.pool.fetch('SELECT id, name, code, patient_display_name FROM treatment_types WHERE tenant_id = 1')
    print("=== TRATAMIENTOS CARGADOS ===")
    for row in rows:
        print(f"ID: {row['id']} | Name: {row['name']} | Code: {row['code']} | Display: {row['patient_display_name']}")
    await db.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
