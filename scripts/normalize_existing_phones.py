#!/usr/bin/env python3
"""
Backfill: Normaliza teléfonos de pacientes existentes según el país de la clínica.
Corrige formatos como +543704868421 → +5493704868421 (agrega 9 para Argentina).

Uso:
    python scripts/normalize_existing_phones.py [--tenant N] [--dry-run]
"""

import asyncio
import re
import sys
import os
from typing import Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from orchestrator_service.db import db


# Mapa mínimo para el script (independiente del de main.py)
COUNTRY_PHONE_MAP = {
    "AR": {"prefix": "+549", "code": "54", "has_mobile_9": True},
}


def normalize_for_country(phone: str, country_code: str = "AR") -> str:
    if not phone or not phone.strip():
        return phone or ""
    country = COUNTRY_PHONE_MAP.get(country_code, COUNTRY_PHONE_MAP["AR"])
    prefix = country["prefix"]
    code = country["code"]
    has_9 = country["has_mobile_9"]
    digits = re.sub(r"\D", "", phone)
    if not digits:
        return phone

    full_prefix_digits = re.sub(r"\D", "", prefix)
    if digits.startswith(full_prefix_digits):
        return prefix + digits[len(full_prefix_digits):]

    if phone.startswith("+" + code):
        rest = digits[len(code):]
        return (prefix + rest) if has_9 else ("+" + code + rest)

    if digits.startswith(code) and len(digits) > len(code):
        rest = digits[len(code):]
        return (prefix + rest) if has_9 else ("+" + code + rest)

    return prefix + digits


async def normalize_all(tenant_id: Optional[int] = None, dry_run: bool = False):
    conn = await db.pool.acquire()
    try:
        if tenant_id:
            tenants = [{"id": tenant_id}]
        else:
            tenants = await conn.fetch("SELECT id, country_code FROM tenants ORDER BY id")

        fixed = skipped = already = errors = 0

        for t in tenants:
            tid = t["id"]
            country = t.get("country_code") or "AR"
            patients = await conn.fetch(
                "SELECT id, phone_number FROM patients WHERE tenant_id = $1 AND phone_number IS NOT NULL AND phone_number != '' ORDER BY id",
                tid,
            )

            for pat in patients:
                old_phone = pat["phone_number"]
                new_phone = normalize_for_country(old_phone, country)
                if new_phone == old_phone:
                    already += 1
                    continue
                if dry_run:
                    print(f"  [DRY-RUN] Tenant {tid}: patient {pat['id']}: {old_phone} → {new_phone}")
                    fixed += 1
                else:
                    try:
                        await conn.execute(
                            "UPDATE patients SET phone_number = $1 WHERE id = $2 AND phone_number = $3",
                            new_phone, pat["id"], old_phone,
                        )
                        print(f"  [OK] Tenant {tid}: patient {pat['id']}: {old_phone} → {new_phone}")
                        fixed += 1
                    except Exception as e:
                        print(f"  [ERROR] Tenant {tid}: patient {pat['id']}: {e}")
                        errors += 1

        print(f"\nResumen: {fixed} corregidos | {skipped} saltados | {already} ya normalizados | {errors} errores")
        return fixed, skipped, already, errors

    finally:
        await db.pool.release(conn)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--tenant", type=int)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    async def _main():
        await db.connect()
        try:
            await normalize_all(tenant_id=args.tenant, dry_run=args.dry_run)
        finally:
            await db.close()

    asyncio.run(_main())
