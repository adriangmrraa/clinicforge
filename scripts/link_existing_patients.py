#!/usr/bin/env python3
"""
Backfill script: Vincula pacientes existentes (creados manualmente) con sus
conversaciones de chat (chat_conversations) mediante linked_patient_id.

Uso:
    python scripts/link_existing_patients.py [--tenant N] [--dry-run]

Ejemplos:
    python scripts/link_existing_patients.py                  # Todos los tenants
    python scripts/link_existing_patients.py --tenant 1       # Solo tenant 1
    python scripts/link_existing_patients.py --dry-run        # Solo mostrar qué se haría
"""

import asyncio
import re
import sys
import os
from typing import Optional

# Agregar el root del proyecto al path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from orchestrator_service.db import db
import asyncpg


def normalize_phone(phone: str) -> str:
    """Normaliza a E.164: +5491144445555"""
    clean = re.sub(r"\D", "", phone)
    return "+" + clean


async def link_patients(tenant_id: Optional[int] = None, dry_run: bool = False):
    """Busca pacientes sin linked_patient_id y los vincula."""
    linked = 0
    skipped = 0
    already = 0
    errors = 0

    conn: asyncpg.Connection = await db.pool.acquire()
    try:
        # Obtener tenants a procesar
        if tenant_id:
            tenants = [{"id": tenant_id}]
        else:
            tenants = await conn.fetch("SELECT id FROM tenants ORDER BY id")

        for t in tenants:
            tid = t["id"]
            # Obtener todos los pacientes del tenant
            patients = await conn.fetch(
                "SELECT id, phone_number, first_name FROM patients WHERE tenant_id = $1 AND phone_number IS NOT NULL AND phone_number != '' ORDER BY id",
                tid,
            )

            for pat in patients:
                phone = pat["phone_number"]
                if not phone:
                    skipped += 1
                    continue

                # Buscar conversaciones por teléfono en ambos formatos
                normalized = normalize_phone(phone)
                raw = re.sub(r"\D", "", phone)

                conv = await conn.fetchrow(
                    """
                    SELECT id, linked_patient_id FROM chat_conversations
                    WHERE tenant_id = $1
                      AND channel = 'whatsapp'
                      AND (external_user_id = $2 OR external_user_id = $3)
                    ORDER BY updated_at DESC
                    LIMIT 1
                    """,
                    tid,
                    normalized,
                    raw,
                )

                if not conv:
                    print(f"  [SKIP] Tenant {tid}: patient {pat['id']} ({phone}) no tiene conversación")
                    skipped += 1
                    continue

                if conv["linked_patient_id"] == pat["id"]:
                    print(f"  [ALREADY] Tenant {tid}: patient {pat['id']} ya linkeado a conv {conv['id']}")
                    already += 1
                    continue

                if conv["linked_patient_id"] is not None:
                    print(f"  [SKIP] Tenant {tid}: patient {pat['id']} — conv {conv['id']} ya linkeada a otro patient {conv['linked_patient_id']}")
                    skipped += 1
                    continue

                if dry_run:
                    print(f"  [DRY-RUN] Tenant {tid}: patient {pat['id']} → conv {conv['id']}")
                    linked += 1
                else:
                    try:
                        await conn.execute(
                            "UPDATE chat_conversations SET linked_patient_id = $1, linked_at = NOW() WHERE id = $2",
                            pat["id"],
                            conv["id"],
                        )
                        print(f"  [OK] Tenant {tid}: linked patient {pat['id']} ({phone}) → conversation {conv['id']}")
                        linked += 1
                    except Exception as e:
                        print(f"  [ERROR] Tenant {tid}: patient {pat['id']} → conv {conv['id']}: {e}")
                        errors += 1

    finally:
        await db.pool.release(conn)

    print(f"\n{'='*50}")
    print(f"RESUMEN:")
    print(f"  Linkeados:   {linked}")
    print(f"  Saltados:    {skipped}")
    print(f"  Ya estaban:  {already}")
    print(f"  Errores:     {errors}")
    print(f"{'='*50}")
    return linked, skipped, already, errors


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Link existing patients to their chat conversations")
    parser.add_argument("--tenant", type=int, help="Specific tenant ID (default: all)")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be done without making changes")
    args = parser.parse_args()

    print(f"Iniciando backfill de pacientes{' (DRY RUN)' if args.dry_run else ''}...")
    asyncio.run(link_patients(tenant_id=args.tenant, dry_run=args.dry_run))
