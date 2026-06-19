import asyncio
import os
import asyncpg

async def main():
    dsn = os.getenv("POSTGRES_DSN")
    if not dsn:
        # Check root .env file or env
        from dotenv import load_dotenv
        # Try loading .env from project root
        load_dotenv("c:\\Users\\Asus\\Documents\\estabilizacion\\Laura Delgado\\clinicforge\\.env")
        dsn = os.getenv("POSTGRES_DSN")
        if not dsn:
            dsn = "postgresql://postgres:postgres@localhost:5432/dentalogic"
    
    dsn = dsn.replace("postgresql+asyncpg://", "postgresql://")
    conn = await asyncpg.connect(dsn)
    
    # 1. Query the patient table for the number
    print("--- PATIENTS WITH +5493704868421 or 3704868421 ---")
    rows = await conn.fetch("SELECT id, first_name, last_name, phone_number, dni, insurance_provider, status, created_at FROM patients WHERE phone_number LIKE '%3704868421%'")
    for r in rows:
        print(dict(r))

    # 2. Query appointments for the patient
    if rows:
        p_id = rows[0]["id"]
        print(f"\n--- APPOINTMENTS FOR PATIENT {p_id} ---")
        apts = await conn.fetch("SELECT id, appointment_datetime, duration_minutes, appointment_type, status, professional_id, source FROM appointments WHERE patient_id = $1", p_id)
        for a in apts:
            print(dict(a))
            # Get professional name
            prof_id = a["professional_id"]
            if prof_id:
                prof = await conn.fetchrow("SELECT id, first_name, last_name FROM professionals WHERE id = $1", prof_id)
                print("Professional:", dict(prof) if prof else None)
    
    await conn.close()

if __name__ == "__main__":
    asyncio.run(main())
