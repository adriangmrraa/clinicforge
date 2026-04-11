"""
Professional self-service routes (/my/ prefix).

These endpoints use JWT-based authentication (Bearer token) instead of admin token.
Professionals can ONLY see their own data (filtered by professional_id from JWT).
All endpoints are GET-only (read-only access).
"""

import logging
import os
from datetime import date, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import FileResponse, JSONResponse

from db import db
from core.auth import get_resolved_tenant_id

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/my", tags=["Professional Self-Service"])


# ---------------------------------------------------------------------------
# Auth dependency: extract user info from JWT Bearer token
# ---------------------------------------------------------------------------


async def get_professional_from_jwt(request: Request) -> dict:
    """
    Extract professional_id and tenant_id from the JWT Bearer token.

    The frontend sends: Authorization: Bearer <jwt>
    The JWT contains the user's role, user_id (UUID), and tenant_id.
    We resolve user_id → professional_id via the professionals table.
    """
    authorization = request.headers.get("authorization")
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=401,
            detail="Se requiere autenticación JWT (Bearer token)",
        )

    token = authorization.split(" ", 1)[1]

    # Decode JWT to get user info
    # The orchestrator uses simple JWT tokens stored in cookies/headers
    # We need to resolve the user to a professional
    try:
        # Try to get user info from the token via the existing auth mechanism
        # The token contains user_id (UUID) and role
        import jwt as pyjwt

        # Require explicit JWT secret — try all known env var names
        jwt_secret = (
            os.getenv("JWT_SECRET_KEY")
            or os.getenv("JWT_SECRET")
            or os.getenv("SECRET_KEY")
            or os.getenv("INTERNAL_SECRET_KEY")  # Legacy fallback (matches auth_service.py)
        )
        if not jwt_secret:
            logger.error(
                "CRITICAL: No JWT secret configured. Set JWT_SECRET_KEY env var."
            )
            raise HTTPException(status_code=500, detail="Server configuration error")
        secrets_to_try = [jwt_secret]

        payload = None
        for secret in secrets_to_try:
            try:
                payload = pyjwt.decode(token, secret, algorithms=["HS256"])
                break
            except Exception:
                continue

        if payload is None:
            # Fallback: try HS384 and HS512
            for secret in secrets_to_try:
                for alg in ["HS384", "HS512"]:
                    try:
                        payload = pyjwt.decode(token, secret, algorithms=[alg])
                        break
                    except Exception:
                        continue
                if payload:
                    break

        if payload is None:
            raise HTTPException(
                status_code=401,
                detail="Token JWT inválido o expirado",
            )

        user_id = payload.get("sub") or payload.get("user_id")
        user_role = payload.get("role", "")
        tenant_id = payload.get("tenant_id")

        if not user_id:
            raise HTTPException(
                status_code=401,
                detail="Token no contiene información de usuario",
            )

        if user_role not in ("professional", "ceo"):
            raise HTTPException(
                status_code=403,
                detail="Acceso restringido a profesionales",
            )

        # Resolve user_id → professional_id
        import uuid

        prof_row = await db.pool.fetchrow(
            """
            SELECT id, first_name, last_name, email
            FROM professionals
            WHERE user_id = $1 AND tenant_id = $2 AND is_active = true
            """,
            uuid.UUID(str(user_id)) if not str(user_id).isdigit() else None,
            int(tenant_id) if tenant_id else None,
        )

        if not prof_row:
            # Try resolving by tenant_id from header if not in JWT
            header_tenant = request.headers.get("x-tenant-id")
            if header_tenant:
                prof_row = await db.pool.fetchrow(
                    """
                    SELECT id, first_name, last_name, email
                    FROM professionals
                    WHERE user_id = $1 AND tenant_id = $2 AND is_active = true
                    """,
                    uuid.UUID(str(user_id)) if not str(user_id).isdigit() else None,
                    int(header_tenant),
                )

        if not prof_row:
            raise HTTPException(
                status_code=403,
                detail="No se encontró perfil profesional activo para este usuario",
            )

        return {
            "professional_id": prof_row["id"],
            "tenant_id": prof_row["tenant_id"]
            if "tenant_id" in prof_row
            else (int(tenant_id) if tenant_id else None),
            "full_name": f"{prof_row['first_name']} {prof_row['last_name'] or ''}".strip(),
            "email": prof_row.get("email", ""),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error resolving professional from JWT: {e}", exc_info=True)
        raise HTTPException(
            status_code=401,
            detail="Error de autenticación",
        )


# ---------------------------------------------------------------------------
# EP-PRO-01: GET /my/liquidations
# ---------------------------------------------------------------------------


@router.get(
    "/liquidations",
    summary="List own liquidations for the logged-in professional",
)
async def get_my_liquidations(
    period_start: Optional[str] = Query(None),
    period_end: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    professional: dict = Depends(get_professional_from_jwt),
):
    """
    EP-PRO-01: Returns liquidation records belonging to the current professional.
    Read-only. Filters by professional_id from JWT automatically.
    """
    prof_id = professional["professional_id"]
    tenant_id = professional["tenant_id"]

    if not tenant_id:
        raise HTTPException(
            status_code=400,
            detail="No se pudo determinar la clínica del profesional",
        )

    # Parse optional dates
    parsed_start = None
    parsed_end = None
    if period_start:
        try:
            parsed_start = date.fromisoformat(period_start)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail="Formato de period_start inválido. Usar YYYY-MM-DD.",
            )
    if period_end:
        try:
            parsed_end = date.fromisoformat(period_end)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail="Formato de period_end inválido. Usar YYYY-MM-DD.",
            )

    try:
        # Build dynamic WHERE clauses
        conditions = ["lr.tenant_id = $1", "lr.professional_id = $2"]
        params: list = [tenant_id, prof_id]
        param_idx = 3

        if status:
            conditions.append(f"lr.status = ${param_idx}")
            params.append(status)
            param_idx += 1

        if parsed_start:
            conditions.append(f"lr.period_start >= ${param_idx}")
            params.append(parsed_start)
            param_idx += 1

        if parsed_end:
            conditions.append(f"lr.period_end <= ${param_idx}")
            params.append(parsed_end)
            param_idx += 1

        where_clause = " AND ".join(conditions)

        # Count
        count_sql = f"""
            SELECT COUNT(*) FROM liquidation_records lr
            WHERE {where_clause}
        """
        total = await db.pool.fetchval(count_sql, *params)

        # Data
        data_sql = f"""
            SELECT lr.*
            FROM liquidation_records lr
            WHERE {where_clause}
            ORDER BY lr.created_at DESC
        """
        rows = await db.pool.fetch(data_sql, *params)

        liquidations = []
        for row in rows:
            liquidations.append(
                {
                    "id": row["id"],
                    "professional_id": row["professional_id"],
                    "period_start": str(row["period_start"]),
                    "period_end": str(row["period_end"]),
                    "total_billed": float(row["total_billed"]),
                    "total_paid": float(row["total_paid"]),
                    "total_pending": float(row["total_pending"]),
                    "commission_pct": float(row["commission_pct"]),
                    "commission_amount": float(row["commission_amount"]),
                    "payout_amount": float(row["payout_amount"]),
                    "status": row["status"],
                    "generated_at": row["generated_at"].isoformat()
                    if row["generated_at"]
                    else None,
                    "approved_at": row["approved_at"].isoformat()
                    if row["approved_at"]
                    else None,
                    "paid_at": row["paid_at"].isoformat() if row["paid_at"] else None,
                    "generated_by": row["generated_by"],
                    "created_at": row["created_at"].isoformat()
                    if row["created_at"]
                    else None,
                }
            )

        return JSONResponse(
            content={
                "liquidations": liquidations,
                "total": total,
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching professional liquidations: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error interno del servidor")


# ---------------------------------------------------------------------------
# EP-PRO-02: GET /my/liquidations/{liquidation_id}
# ---------------------------------------------------------------------------


@router.get(
    "/liquidations/{liquidation_id}",
    summary="Get detail of own liquidation (read-only)",
)
async def get_my_liquidation_detail(
    liquidation_id: int,
    professional: dict = Depends(get_professional_from_jwt),
):
    """
    EP-PRO-02: Returns full detail of a liquidation belonging to the current professional.
    Verifies ownership (professional_id + tenant_id).
    """
    prof_id = professional["professional_id"]
    tenant_id = professional["tenant_id"]

    if not tenant_id:
        raise HTTPException(
            status_code=400,
            detail="No se pudo determinar la clínica del profesional",
        )

    try:
        # Verify ownership
        record = await db.pool.fetchrow(
            """
            SELECT lr.*,
                   p.first_name || ' ' || COALESCE(p.last_name, '') AS professional_name
            FROM liquidation_records lr
            JOIN professionals p ON p.id = lr.professional_id AND p.tenant_id = lr.tenant_id
            WHERE lr.id = $1 AND lr.professional_id = $2 AND lr.tenant_id = $3
            """,
            liquidation_id,
            prof_id,
            tenant_id,
        )

        if not record:
            raise HTTPException(
                status_code=404,
                detail="Liquidación no encontrada o no pertenece al profesional",
            )

        # Get treatment groups (reuse same logic as admin detail)
        period_start = record["period_start"]
        period_end = record["period_end"]

        treatment_groups = await db.pool.fetch(
            """
            SELECT
                a.patient_id,
                pat.first_name || ' ' || COALESCE(pat.last_name, '') AS patient_name,
                a.treatment_code,
                tt.name AS treatment_name,
                a.id AS appointment_id,
                a.appointment_date,
                a.billing_amount,
                a.payment_status,
                a.notes AS appointment_notes
            FROM appointments a
            JOIN patients pat ON pat.id = a.patient_id AND pat.tenant_id = a.tenant_id
            LEFT JOIN treatment_types tt ON tt.code = a.treatment_code AND tt.tenant_id = a.tenant_id
            WHERE a.tenant_id = $1
              AND a.professional_id = $2
              AND a.appointment_date >= $3
              AND a.appointment_date <= $4
              AND a.status IN ('completed', 'paid', 'no-show', 'cancelled')
              AND a.billing_amount > 0
            ORDER BY a.patient_id, a.appointment_date
            """,
            tenant_id,
            prof_id,
            period_start,
            period_end,
        )

        # Group by patient + treatment
        groups_map = {}
        for appt in treatment_groups:
            key = f"{appt['patient_id']}_{appt['treatment_code'] or 'unknown'}"
            if key not in groups_map:
                groups_map[key] = {
                    "patient_id": str(appt["patient_id"]),
                    "patient_name": appt["patient_name"],
                    "treatment_code": appt["treatment_code"] or "",
                    "treatment_name": appt["treatment_name"] or "Sin tratamiento",
                    "sessions": [],
                    "total": 0.0,
                }
            session = {
                "appointment_id": str(appt["appointment_id"]),
                "date": str(appt["appointment_date"]),
                "description": appt["appointment_notes"]
                or appt["treatment_name"]
                or "",
                "amount": float(appt["billing_amount"]),
                "payment_status": appt["payment_status"] or "pending",
            }
            groups_map[key]["sessions"].append(session)
            groups_map[key]["total"] += float(appt["billing_amount"])

        treatment_groups_list = list(groups_map.values())

        # Get payouts
        payouts = await db.pool.fetch(
            """
            SELECT *
            FROM professional_payouts
            WHERE liquidation_id = $1 AND tenant_id = $2
            ORDER BY payment_date DESC
            """,
            liquidation_id,
            tenant_id,
        )

        payouts_list = []
        for p in payouts:
            payouts_list.append(
                {
                    "id": str(p["id"]),
                    "liquidation_record_id": str(p["liquidation_record_id"]),
                    "professional_id": p["professional_id"],
                    "amount": float(p["amount"]),
                    "payment_method": p["payment_method"],
                    "payment_date": str(p["payment_date"]),
                    "reference_number": p.get("reference_number"),
                    "notes": p.get("notes"),
                    "created_at": p["created_at"].isoformat()
                    if p["created_at"]
                    else None,
                }
            )

        return JSONResponse(
            content={
                "liquidation": {
                    "id": record["id"],
                    "professional_id": record["professional_id"],
                    "professional_name": record["professional_name"],
                    "period_start": str(record["period_start"]),
                    "period_end": str(record["period_end"]),
                    "total_billed": float(record["total_billed"]),
                    "total_paid": float(record["total_paid"]),
                    "total_pending": float(record["total_pending"]),
                    "commission_pct": float(record["commission_pct"]),
                    "commission_amount": float(record["commission_amount"]),
                    "payout_amount": float(record["payout_amount"]),
                    "status": record["status"],
                    "generated_at": record["generated_at"].isoformat()
                    if record["generated_at"]
                    else None,
                    "approved_at": record["approved_at"].isoformat()
                    if record["approved_at"]
                    else None,
                    "paid_at": record["paid_at"].isoformat()
                    if record["paid_at"]
                    else None,
                    "generated_by": record["generated_by"],
                },
                "treatment_groups": treatment_groups_list,
                "payouts": payouts_list,
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching liquidation detail: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error interno del servidor")


# ---------------------------------------------------------------------------
# EP-PRO-03: GET /my/commissions
# ---------------------------------------------------------------------------


@router.get(
    "/commissions",
    summary="View own commission configuration (read-only)",
)
async def get_my_commissions(
    professional: dict = Depends(get_professional_from_jwt),
):
    """
    EP-PRO-03: Returns the current professional's commission configuration.
    Read-only.
    """
    prof_id = professional["professional_id"]
    tenant_id = professional["tenant_id"]
    full_name = professional["full_name"]

    if not tenant_id:
        raise HTTPException(
            status_code=400,
            detail="No se pudo determinar la clínica del profesional",
        )

    try:
        # Get default commission
        default_row = await db.pool.fetchrow(
            """
            SELECT commission_pct
            FROM professional_commissions
            WHERE tenant_id = $1 AND professional_id = $2 AND treatment_code IS NULL
            """,
            tenant_id,
            prof_id,
        )

        default_pct = float(default_row["commission_pct"]) if default_row else 0.0

        # Get per-treatment overrides
        overrides_rows = await db.pool.fetch(
            """
            SELECT pc.treatment_code, pc.commission_pct, tt.name AS treatment_name
            FROM professional_commissions pc
            LEFT JOIN treatment_types tt ON tt.code = pc.treatment_code AND tt.tenant_id = pc.tenant_id
            WHERE pc.tenant_id = $1 AND pc.professional_id = $2 AND pc.treatment_code IS NOT NULL
            ORDER BY tt.name
            """,
            tenant_id,
            prof_id,
        )

        per_treatment = []
        for row in overrides_rows:
            per_treatment.append(
                {
                    "treatment_code": row["treatment_code"],
                    "treatment_name": row["treatment_name"] or row["treatment_code"],
                    "commission_pct": float(row["commission_pct"]),
                }
            )

        return JSONResponse(
            content={
                "professional_id": prof_id,
                "professional_name": full_name,
                "default_commission_pct": default_pct,
                "per_treatment": per_treatment,
                "warning": "Sin configuración de comisiones"
                if default_pct == 0
                else None,
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching commission config: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error interno del servidor")


# ---------------------------------------------------------------------------
# EP-PRO-04: GET /my/liquidations/{liquidation_id}/pdf
# ---------------------------------------------------------------------------


@router.get(
    "/liquidations/{liquidation_id}/pdf",
    summary="Download PDF of own liquidation",
)
async def get_my_liquidation_pdf(
    liquidation_id: int,
    professional: dict = Depends(get_professional_from_jwt),
):
    """
    EP-PRO-04: Generates and serves the PDF of a liquidation belonging to the current professional.
    Verifies ownership before generating.
    """
    from services.liquidation_pdf_service import (
        generate_liquidation_pdf,
        gather_liquidation_pdf_data,
    )

    prof_id = professional["professional_id"]
    tenant_id = professional["tenant_id"]

    if not tenant_id:
        raise HTTPException(
            status_code=400,
            detail="No se pudo determinar la clínica del profesional",
        )

    # Verify ownership
    record = await db.pool.fetchrow(
        """
        SELECT id, status, professional_id
        FROM liquidation_records
        WHERE id = $1 AND professional_id = $2 AND tenant_id = $3
        """,
        liquidation_id,
        prof_id,
        tenant_id,
    )

    if not record:
        raise HTTPException(
            status_code=404,
            detail="Liquidación no encontrada o no pertenece al profesional",
        )

    # Check cached PDF
    pdf_path = f"/app/uploads/liquidations/{tenant_id}/{liquidation_id}.pdf"
    use_cache = False
    if os.path.exists(pdf_path):
        pdf_mtime = os.path.getmtime(pdf_path)
        record_ts = record.get("created_at")
        if record_ts:
            if hasattr(record_ts, "timestamp"):
                record_epoch = record_ts.timestamp()
            else:
                record_epoch = 0
            if pdf_mtime >= record_epoch:
                use_cache = True

    if not use_cache:
        pdf_path = await generate_liquidation_pdf(db.pool, liquidation_id, tenant_id)
        if not pdf_path:
            raise HTTPException(
                status_code=500,
                detail="Error generando PDF de liquidación",
            )

    # Build filename
    data = await gather_liquidation_pdf_data(db.pool, liquidation_id, tenant_id)
    if data:
        prof_name = data["professional"]["full_name"].replace(" ", "_")
        period_label = data["period"]["label"].replace(" ", "_")
        filename = f"Liquidacion_{prof_name}_{period_label}.pdf"
    else:
        filename = f"Liquidacion_{liquidation_id}.pdf"

    return FileResponse(
        pdf_path,
        media_type="application/pdf",
        filename=filename,
    )
