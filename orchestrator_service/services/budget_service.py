"""
budget_service.py — Generates treatment plan presupuesto PDFs.

Pattern follows digital_records_service.py (gather → render → WeasyPrint → disk).
Key difference: NO AI narrative. This is pure data → Jinja2 template → PDF.

Layers:
  1. gather_budget_data()   — DB queries, data normalization
  2. render_budget_html()   — Jinja2 render
  3. generate_budget_pdf()  — WeasyPrint async (via to_thread), disk cache
"""

import asyncio
import logging
import os
import uuid as _uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

from jinja2 import Environment, FileSystemLoader

from services.digital_records_service import resolve_logo_data_uri

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Jinja2 setup — templates/budget/ relative to orchestrator_service root
# ---------------------------------------------------------------------------
_TEMPLATES_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "templates",
    "budget",
)

_jinja_env = Environment(
    loader=FileSystemLoader(_TEMPLATES_DIR),
    autoescape=True,
)


# ---------------------------------------------------------------------------
# Currency filter — formats as Argentine pesos: 325000 → "325.000"
# ---------------------------------------------------------------------------
def _ars_format(value) -> str:
    """Format a numeric value as ARS with dot thousands separator."""
    try:
        n = float(value or 0)
        # Format with 2 decimals, swap . and , for Spanish convention
        formatted = f"{n:,.0f}".replace(",", ".")
        return formatted
    except (TypeError, ValueError):
        return "0"


_jinja_env.filters["ars"] = _ars_format


# =============================================================================
# LAYER 1: DATA GATHERING
# =============================================================================


async def gather_budget_data(pool, plan_id: str, tenant_id: int) -> Optional[dict]:
    """
    Gather all data needed for a budget PDF.

    All queries are scoped to tenant_id (multi-tenant isolation rule).
    Returns None if the plan is not found.
    """
    # Convert plan_id to UUID for asyncpg
    try:
        plan_uuid = _uuid.UUID(plan_id) if isinstance(plan_id, str) else plan_id
    except ValueError:
        logger.error("gather_budget_data: invalid plan_id %s", plan_id)
        return None

    # ── Plan + patient + professional + clinic (single JOIN query) ──────────
    plan = await pool.fetchrow(
        """
        SELECT
            tp.id,
            tp.name,
            tp.status,
            tp.approved_total,
            tp.created_at,
            tp.approved_at,
            pat.first_name || ' ' || COALESCE(pat.last_name, '') AS patient_name,
            pat.dni,
            pat.phone_number AS patient_phone,
            pat.email AS patient_email,
            prof.first_name || ' ' || COALESCE(prof.last_name, '') AS professional_name,
            prof.specialty,
            t.name AS clinic_name,
            t.address AS clinic_address,
            t.phone AS clinic_phone,
            t.logo_url
        FROM treatment_plans tp
        JOIN patients pat ON pat.id = tp.patient_id AND pat.tenant_id = tp.tenant_id
        LEFT JOIN professionals prof ON prof.id = tp.professional_id AND prof.tenant_id = tp.tenant_id
        JOIN tenants t ON t.id = tp.tenant_id
        WHERE tp.id = $1 AND tp.tenant_id = $2
        """,
        plan_uuid,
        tenant_id,
    )

    if not plan:
        logger.warning(
            "gather_budget_data: plan %s not found for tenant %s", plan_id, tenant_id
        )
        return None

    # ── Items ────────────────────────────────────────────────────────────────
    # treatment_name: prefer treatment_types.name, fall back to custom_description,
    # then treatment_type_code.
    items = await pool.fetch(
        """
        SELECT
            tpi.treatment_type_code,
            tpi.custom_description,
            tpi.estimated_price,
            tpi.approved_price,
            tpi.status,
            COALESCE(tt.name, tpi.custom_description, tpi.treatment_type_code) AS treatment_name
        FROM treatment_plan_items tpi
        LEFT JOIN treatment_types tt
            ON tt.code = tpi.treatment_type_code AND tt.tenant_id = $1
        WHERE tpi.plan_id = $2 AND tpi.tenant_id = $1
        ORDER BY tpi.sort_order, tpi.created_at
        """,
        tenant_id,
        plan_uuid,
    )

    # ── Payments ─────────────────────────────────────────────────────────────
    payments = await pool.fetch(
        """
        SELECT payment_date, amount, payment_method, notes
        FROM treatment_plan_payments
        WHERE plan_id = $1 AND tenant_id = $2
        ORDER BY payment_date DESC
        """,
        plan_uuid,
        tenant_id,
    )

    # ── Totals ───────────────────────────────────────────────────────────────
    estimated = sum(float(i["estimated_price"] or 0) for i in items)
    # approved_total on the plan takes precedence; fall back to sum of estimated
    approved = float(plan["approved_total"] or estimated)
    paid = sum(float(p["amount"] or 0) for p in payments)

    # ── Assemble ─────────────────────────────────────────────────────────────
    return {
        "plan": {
            "name": plan["name"] or "Presupuesto de Tratamiento",
            "status": plan["status"] or "draft",
            "approved_total": approved,
            "estimated_total": estimated,
            "created_at": plan["created_at"].strftime("%d/%m/%Y") if plan["created_at"] else "",
            "approved_at": plan["approved_at"].strftime("%d/%m/%Y") if plan["approved_at"] else None,
        },
        "patient": {
            "name": (plan["patient_name"] or "").strip() or "Paciente",
            "dni": plan["dni"] or "",
            "phone": plan["patient_phone"] or "",
            "email": plan["patient_email"] or "",
        },
        "professional": {
            "name": (plan["professional_name"] or "").strip() or "",
            "specialty": plan["specialty"] or "",
        },
        "clinic": {
            "name": plan["clinic_name"] or "Clínica",
            "address": plan["clinic_address"] or "",
            "phone": plan["clinic_phone"] or "",
            "logo_url": resolve_logo_data_uri(tenant_id) or plan["logo_url"] or "",
        },
        "items": [
            {
                "treatment_name": i["treatment_name"] or "Sin nombre",
                "estimated_price": float(i["estimated_price"] or 0),
                "approved_price": float(i["approved_price"]) if i["approved_price"] is not None else None,
                "status": i["status"] or "pending",
            }
            for i in items
        ],
        "payments": [
            {
                "date": p["payment_date"].strftime("%d/%m/%Y") if p["payment_date"] else "",
                "amount": float(p["amount"] or 0),
                "method": p["payment_method"] or "cash",
                "notes": p["notes"] or "",
            }
            for p in payments
        ],
        "totals": {
            "estimated": round(estimated, 2),
            "approved": round(approved, 2),
            "paid": round(paid, 2),
            "pending": round(approved - paid, 2),
            "progress_pct": round(paid / approved * 100, 1) if approved > 0 else 0,
        },
        "generated_at": datetime.now().strftime("%d/%m/%Y a las %H:%M"),
    }


# =============================================================================
# LAYER 2: HTML RENDERING (Jinja2)
# =============================================================================


def render_budget_html(data: dict) -> str:
    """Render the presupuesto.html template with gathered data."""
    template = _jinja_env.get_template("presupuesto.html")
    return template.render(**data)


# =============================================================================
# LAYER 3: PDF GENERATION (WeasyPrint, sync in thread)
# =============================================================================


def _generate_pdf_sync(html: str, pdf_path: str) -> str:
    """
    Blocking WeasyPrint call — MUST be called via asyncio.to_thread.

    Falls back to writing an HTML file if WeasyPrint is not installed,
    so development environments don't break.
    """
    os.makedirs(os.path.dirname(pdf_path), exist_ok=True)
    try:
        from weasyprint import HTML as _WP_HTML  # lazy import — optional dep
        _WP_HTML(string=html, base_url=_TEMPLATES_DIR).write_pdf(pdf_path)
        logger.info("_generate_pdf_sync: wrote PDF → %s", pdf_path)
        return pdf_path
    except ImportError:
        logger.warning("WeasyPrint not available — writing HTML fallback")
        html_path = pdf_path.replace(".pdf", ".html")
        Path(html_path).write_text(html, encoding="utf-8")
        return html_path
    except Exception as exc:
        logger.error("_generate_pdf_sync: WeasyPrint failed: %s", exc)
        raise


async def generate_budget_pdf(pool, plan_id: str, tenant_id: int) -> Optional[str]:
    """
    Generate a budget PDF and cache it to disk.

    Output path: /app/uploads/budgets/{tenant_id}/{plan_id}.pdf

    Always regenerates (no stale-cache problem since caller controls when to call).
    Returns the file path on success, None if the plan is not found.
    """
    upload_dir = Path(f"/app/uploads/budgets/{tenant_id}")
    pdf_path = str(upload_dir / f"{plan_id}.pdf")

    data = await gather_budget_data(pool, plan_id, tenant_id)
    if not data:
        return None

    html = render_budget_html(data)

    result = await asyncio.to_thread(_generate_pdf_sync, html, pdf_path)
    return result
