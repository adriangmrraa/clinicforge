import asyncio
import os
# Force 127.0.0.1 to avoid Windows localhost/IPv6 issues
if not os.getenv("POSTGRES_DSN"):
    os.environ["POSTGRES_DSN"] = "postgresql://postgres:password@127.0.0.1:5432/clinica_dental_db"

from db import db

async def main():
    print("🔌 Conectando a Base de Datos (127.0.0.1)...")
    await db.connect()
    
    # Find unique numbers in chat_messages that are NOT in patients
    print("🔍 Buscando conversaciones huérfanas...")
    rows = await db.pool.fetch("""
        SELECT DISTINCT from_number 
        FROM chat_messages 
        WHERE from_number NOT IN (SELECT phone_number FROM patients)
    """)
    
    print(f"⚠️ Encontrados {len(rows)} números sin ficha de paciente.")
    
    for row in rows:
        phone = row['from_number']
        print(f"🛠️ Restaurando ficha para: {phone}")
        await db.ensure_patient_exists(phone)
        
    print("✅ Reparación completada.")
    await db.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
