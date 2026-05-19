"""
One-time backfill: Vincula pacientes existentes con sus conversaciones de chat.

Puede ejecutarse como:
  - Comando CLI: python -m orchestrator_service.scripts.link_chat_patients
  - Función importada: await link_chat_patients()
  - Inline desde start.sh: python -c "from orchestrator_service.scripts.link_chat_patients import run; run()"
"""

import asyncio
import logging
import os
import re
import sys
from typing import Optional, Tuple

logger = logging.getLogger(__name__)

# ── cuando se importa desde start.sh inline, agregar el path ──
_script_dir = os.path.dirname(os.path.abspath(__file__))
_project_root = os.path.abspath(os.path.join(_script_dir, ".."))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)


def normalize_phone(phone: str) -> str:
    clean = re.sub(r"\D", "", phone)
    return "+" + clean


async def link_chat_patients(
    pool=None, tenant_id: Optional[int] = None, dry_run: bool = False
) -> Tuple[int, int, int, int]:
    """
    Busca pacientes sin linked_patient_id y los vincula con sus conversaciones.
    Retorna (linkeados, saltados, ya_linkeados, errores).
    """
    import asyncpg

    if pool is None:
        from orchestrator_service.db import db

        await db.connect()
        pool = db.pool

    linked = skipped = already = errors = 0

    async with pool.acquire() as conn:
        tenants = (
            [{"id": tenant_id}]
            if tenant_id
            else await conn.fetch("SELECT id FROM tenants ORDER BY id")
        )

        for t in tenants:
            tid = t["id"]
            patients = await conn.fetch(
                """SELECT id, phone_number, first_name
                   FROM patients
                   WHERE tenant_id = $1
                     AND phone_number IS NOT NULL AND phone_number != ''
                   ORDER BY id""",
                tid,
            )

            for pat in patients:
                phone = pat["phone_number"]
                if not phone:
                    skipped += 1
                    continue

                normalized = normalize_phone(phone)
                raw = re.sub(r"\D", "", phone)

                conv = await conn.fetchrow(
                    """SELECT id, linked_patient_id FROM chat_conversations
                       WHERE tenant_id = $1
                         AND channel = 'whatsapp'
                         AND (external_user_id = $2 OR external_user_id = $3)
                       ORDER BY updated_at DESC LIMIT 1""",
                    tid,
                    normalized,
                    raw,
                )

                if not conv:
                    logger.info(
                        "[SKIP] Tenant %s: patient %s (%s) no tiene conversación",
                        tid, pat["id"], phone,
                    )
                    skipped += 1
                    continue

                if conv["linked_patient_id"] == pat["id"]:
                    already += 1
                    continue

                if conv["linked_patient_id"] is not None:
                    logger.info(
                        "[SKIP] Tenant %s: patient %s — conv %s linkeada a otro",
                        tid, pat["id"], conv["id"],
                    )
                    skipped += 1
                    continue

                if dry_run:
                    logger.info("[DRY-RUN] Tenant %s: patient %s → conv %s", tid, pat["id"], conv["id"])
                    linked += 1
                else:
                    await conn.execute(
                        "UPDATE chat_conversations SET linked_patient_id = $1, linked_at = NOW() WHERE id = $2",
                        pat["id"], conv["id"],
                    )
                    logger.info("[OK] Tenant %s: patient %s → conv %s", tid, pat["id"], conv["id"])
                    linked += 1

    logger.info("Resumen: linkeados=%s saltados=%s ya_linkeados=%s errores=%s", linked, skipped, already, errors)
    return linked, skipped, already, errors


def run(tenant_id: Optional[int] = None, dry_run: bool = False):
    """Entry point síncrono para usar desde bash / start.sh."""
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    result = asyncio.run(link_chat_patients(tenant_id=tenant_id, dry_run=dry_run))
    return result


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Link existing patients to chat conversations")
    parser.add_argument("--tenant", type=int, help="Specific tenant ID")
    parser.add_argument("--dry-run", action="store_true", help="Preview only")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(message)s")
    print(f"Iniciando backfill{' (DRY RUN)' if args.dry_run else ''}...")

    async def _main():
        from orchestrator_service.db import db
        await db.connect()
        try:
            await link_chat_patients(pool=db.pool, tenant_id=args.tenant, dry_run=args.dry_run)
        finally:
            await db.close()

    asyncio.run(_main())
