"""Seed a sandbox tenant for safe testing. Idempotent — safe to run multiple times."""
import asyncio
import os
import asyncpg

SANDBOX_TENANT_ID = 99999  # Fixed ID, never collides with real tenants


async def seed():
    dsn = os.getenv("POSTGRES_DSN", "postgresql://localhost:5432/clinicforge")
    pool = await asyncpg.create_pool(dsn)

    # Check if already exists
    exists = await pool.fetchval(
        "SELECT EXISTS(SELECT 1 FROM tenants WHERE id = $1)", SANDBOX_TENANT_ID
    )
    if exists:
        print(f"Sandbox tenant {SANDBOX_TENANT_ID} already exists. Skipping.")
        await pool.close()
        return

    # Create sandbox tenant with minimal config
    # config includes "sandbox": true — this flag is checked by response_sender.py
    # to suppress real message delivery (logs only).
    await pool.execute(
        """
        INSERT INTO tenants (id, clinic_name, bot_name, config, working_hours)
        VALUES ($1, 'Clínica Sandbox (TEST)', 'TestBot', '{"sandbox": true}'::jsonb,
                '{"lunes":{"start":"09:00","end":"18:00","enabled":true},"martes":{"start":"09:00","end":"18:00","enabled":true},"miercoles":{"start":"09:00","end":"18:00","enabled":true},"jueves":{"start":"09:00","end":"18:00","enabled":true},"viernes":{"start":"09:00","end":"18:00","enabled":true},"sabado":{"enabled":false},"domingo":{"enabled":false}}'::jsonb)
        """,
        SANDBOX_TENANT_ID,
    )

    # Create a test professional
    await pool.execute(
        """
        INSERT INTO professionals (tenant_id, first_name, last_name, specialty, is_active)
        VALUES ($1, 'Dr. Test', 'Sandbox', 'General', true)
        """,
        SANDBOX_TENANT_ID,
    )

    # Create a test treatment type
    await pool.execute(
        """
        INSERT INTO treatment_types (tenant_id, name, code, default_duration_minutes, is_active)
        VALUES ($1, 'Consulta General Test', 'consulta_test', 30, true)
        """,
        SANDBOX_TENANT_ID,
    )

    print(f"Sandbox tenant {SANDBOX_TENANT_ID} created successfully.")
    await pool.close()


if __name__ == "__main__":
    asyncio.run(seed())
