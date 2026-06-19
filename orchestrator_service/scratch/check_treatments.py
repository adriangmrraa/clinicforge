import asyncio
import json
import os
# Asegurar que la variable de entorno POSTGRES_DSN esté definida si hace falta,
# db.py la lee automáticamente.
from db import db

async def main():
    await db.connect()
    if not db.pool:
        print("No se pudo conectar a la base de datos.")
        return
    
    # Primero busquemos los tenants para saber el id de Dra. Laura Delgado
    tenants = await db.pool.fetch("SELECT id, clinic_name FROM tenants")
    print("--- TENANTS ---")
    for t in tenants:
        print(f"ID: {t['id']}, Name: {t['clinic_name']}")
    
    # Listar tratamientos para cada tenant
    print("\n--- TREATMENT TYPES ---")
    for t in tenants:
        print(f"\nTenant {t['clinic_name']} (ID: {t['id']}):")
        treatments = await db.pool.fetch(
            "SELECT id, code, name, patient_display_name, category, is_active, is_available_for_booking FROM treatment_types WHERE tenant_id = $1",
            t['id']
        )
        for tr in treatments:
            print(f"  - Code: {tr['code']}, Name: {tr['name']}, Display: {tr['patient_display_name']}, Active: {tr['is_active']}, Booking: {tr['is_available_for_booking']}")
            
    await db.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
