"""
liquidation_pdf_service.py — Generates liquidation statement PDFs.

Pattern follows budget_service.py (gather → render → WeasyPrint → disk cache).

Layers:
  1. gather_liquidation_pdf_data()   — DB queries, data normalization
  2. render_liquidation_html()        — Jinja2 render
  3. generate_liquidation_pdf()       — WeasyPrint async (via to_thread), disk cache
"""

import asyncio
import logging
import os
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Optional

from jinja2 import Environment, FileSystemLoader

from services.digital_records_service import resolve_logo_data_uri

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Jinja2 setup — templates/liquidation/ relative to orchestrator_service root
# ---------------------------------------------------------------------------
_TEMPLATES_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "templates",
    "liquidation",
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
        formatted = f"{n:,.0f}".replace(",", ".")
        return formatted
    except (TypeError, ValueError):
        return "0"


_jinja_env.filters["ars"] = _ars_format


# ---------------------------------------------------------------------------
# Translation dictionaries for PDF (es/en/fr)
# ---------------------------------------------------------------------------
_TRANSLATIONS = {
    "es": {
        "commission_title": "LIQUIDACIÓN DE COMISIONES",
        "professional": "Profesional",
        "name": "Nombre",
        "specialty": "Especialidad",
        "license": "Matrícula",
        "period": "Período",
        "period_range": "Período",
        "generated": "Generado",
        "notes": "Notas",
        "summary": "Resumen",
        "total_sessions": "Total de sesiones",
        "total_billed": "Total facturado",
        "total_paid": "Total cobrado",
        "total_pending": "Total pendiente",
        "commission_pct": "Comisión aplicada",
        "commission_amount": "Monto de comisión",
        "net_payout": "NETO A LIQUIDAR",
        "detail": "Detalle de Sesiones",
        "date": "Fecha",
        "treatment": "Tratamiento",
        "amount": "Monto",
        "pay_status": "Estado",
        "paid": "Pagado",
        "partial": "Parcial",
        "pending": "Pendiente",
        "subtotal": "Subtotal",
        "payout_history": "Historial de Pagos",
        "clinic_signature": "Firma clínica",
        "prof_signature": "Firma profesional",
        "footer_auto": "Documento generado automáticamente por",
        "status_draft": "Borrador",
        "status_generated": "Generada",
        "status_approved": "Aprobada",
        "status_paid": "Pagada",
        "method_transfer": "Transferencia",
        "method_cash": "Efectivo",
        "method_check": "Cheque",
        # Desglose por tratamiento (rediseño 2026-07-10)
        "breakdown_title": "Desglose por tratamiento",
        "qty": "Cant.",
        "collected": "Cobrado",
        "pct_col": "% Prof.",
        "prof_share": "$ Profesional",
        "clinic_share": "$ Clínica",
        "patient": "Paciente",
        "clinic_total": "Total clínica (sobre lo cobrado)",
        "totals": "TOTALES",
        "zero_price_note": "sesiones con precio $0 — cargar el precio real en Tratamientos",
        "no_commission_note": "Sin % de comisión configurado para",
        # Email template
        "email_greeting": "Hola",
        "email_body_intro": "Te adjuntamos tu liquidación correspondiente al período",
        "email_payout_label": "Monto a liquidar",
        "email_attachment_note": "Encontrarás el detalle completo en el documento PDF adjunto.",
        "email_contact_note": "Si tenés alguna consulta, no dudes en comunicarte con la administración de",
        "email_closing": "Saludos,",
        "email_team": "Equipo de",
        "email_footer_auto": "Este email fue enviado automáticamente por",
    },
    "en": {
        "commission_title": "COMMISSION SETTLEMENT",
        "professional": "Professional",
        "name": "Name",
        "specialty": "Specialty",
        "license": "License Number",
        "period": "Period",
        "period_range": "Period",
        "generated": "Generated",
        "notes": "Notes",
        "summary": "Summary",
        "total_sessions": "Total sessions",
        "total_billed": "Total billed",
        "total_paid": "Total paid",
        "total_pending": "Total pending",
        "commission_pct": "Commission applied",
        "commission_amount": "Commission amount",
        "net_payout": "NET PAYOUT",
        "detail": "Session Detail",
        "date": "Date",
        "treatment": "Treatment",
        "amount": "Amount",
        "pay_status": "Status",
        "paid": "Paid",
        "partial": "Partial",
        "pending": "Pending",
        "subtotal": "Subtotal",
        "payout_history": "Payment History",
        "clinic_signature": "Clinic signature",
        "prof_signature": "Professional signature",
        "footer_auto": "Document automatically generated by",
        "status_draft": "Draft",
        "status_generated": "Generated",
        "status_approved": "Approved",
        "status_paid": "Paid",
        "method_transfer": "Transfer",
        "method_cash": "Cash",
        "method_check": "Check",
        # Breakdown by treatment (redesign 2026-07-10)
        "breakdown_title": "Breakdown by treatment",
        "qty": "Qty",
        "collected": "Collected",
        "pct_col": "% Prof.",
        "prof_share": "Professional $",
        "clinic_share": "Clinic $",
        "patient": "Patient",
        "clinic_total": "Clinic total (on collected)",
        "totals": "TOTALS",
        "zero_price_note": "sessions with $0 price — set the real price in Treatments",
        "no_commission_note": "No commission % configured for",
        # Email template
        "email_greeting": "Hello",
        "email_body_intro": "Please find attached your fee statement for the period",
        "email_payout_label": "Payout amount",
        "email_attachment_note": "You will find the complete detail in the attached PDF document.",
        "email_contact_note": "If you have any questions, please don't hesitate to contact the administration of",
        "email_closing": "Best regards,",
        "email_team": "Team",
        "email_footer_auto": "This email was sent automatically by",
    },
    "fr": {
        "commission_title": "RÈGLEMENT DES COMMISSIONS",
        "professional": "Professionnel",
        "name": "Nom",
        "specialty": "Spécialité",
        "license": "Numéro de licence",
        "period": "Période",
        "period_range": "Période",
        "generated": "Généré",
        "notes": "Notes",
        "summary": "Résumé",
        "total_sessions": "Total des séances",
        "total_billed": "Total facturé",
        "total_paid": "Total encaissé",
        "total_pending": "Total en attente",
        "commission_pct": "Commission appliquée",
        "commission_amount": "Montant de la commission",
        "net_payout": "NET À PAYER",
        "detail": "Détail des Séances",
        "date": "Date",
        "treatment": "Traitement",
        "amount": "Montant",
        "pay_status": "Statut",
        "paid": "Payé",
        "partial": "Partiel",
        "pending": "En attente",
        "subtotal": "Sous-total",
        "payout_history": "Historique des Paiements",
        "clinic_signature": "Signature clinique",
        "prof_signature": "Signature professionnelle",
        "footer_auto": "Document généré automatiquement par",
        "status_draft": "Brouillon",
        "status_generated": "Généré",
        "status_approved": "Approuvé",
        "status_paid": "Payé",
        "method_transfer": "Virement",
        "method_cash": "Espèces",
        "method_check": "Chèque",
        # Répartition par traitement (refonte 2026-07-10)
        "breakdown_title": "Répartition par traitement",
        "qty": "Qté",
        "collected": "Encaissé",
        "pct_col": "% Prof.",
        "prof_share": "$ Professionnel",
        "clinic_share": "$ Clinique",
        "patient": "Patient",
        "clinic_total": "Total clinique (sur l'encaissé)",
        "totals": "TOTAUX",
        "zero_price_note": "séances avec prix 0 $ — définir le prix réel dans Traitements",
        "no_commission_note": "Aucun % de commission configuré pour",
        # Email template
        "email_greeting": "Bonjour",
        "email_body_intro": "Veuillez trouver ci-joint votre relevé d'honoraires pour la période",
        "email_payout_label": "Montant à payer",
        "email_attachment_note": "Vous trouverez le détail complet dans le document PDF ci-joint.",
        "email_contact_note": "Si vous avez des questions, n'hésitez pas à contacter l'administration de",
        "email_closing": "Cordialement,",
        "email_team": "Équipe de",
        "email_footer_auto": "Cet email a été envoyé automatiquement par",
    },
}


def _get_translations(lang: str) -> dict:
    """Return translation dict for the given language, defaulting to Spanish."""
    return _TRANSLATIONS.get(lang, _TRANSLATIONS["es"])


# =============================================================================
# LAYER 1: DATA GATHERING
# =============================================================================


async def gather_liquidation_pdf_data(
    pool, liquidation_id: int, tenant_id: int
) -> Optional[dict]:
    """
    Gather all data needed for a liquidation PDF.

    All queries are scoped to tenant_id (multi-tenant isolation rule).
    Returns None if the liquidation record is not found.
    """
    # ── Liquidation record + professional + clinic ──────────────────────────
    record = await pool.fetchrow(
        """
        SELECT
            lr.*,
            p.first_name || ' ' || COALESCE(p.last_name, '') AS professional_full_name,
            p.specialty,
            p.email AS professional_email,
            t.clinic_name,
            t.address AS clinic_address,
            t.clinic_location AS clinic_phone,
            t.logo_url,
            COALESCE(t.config->>'ui_language', 'es') AS ui_language
        FROM liquidation_records lr
        JOIN professionals p ON p.id = lr.professional_id AND p.tenant_id = lr.tenant_id
        JOIN tenants t ON t.id = lr.tenant_id
        WHERE lr.id = $1 AND lr.tenant_id = $2
        """,
        liquidation_id,
        tenant_id,
    )

    if not record:
        logger.warning(
            "gather_liquidation_pdf_data: liquidation %s not found for tenant %s",
            liquidation_id,
            tenant_id,
        )
        return None

    lang = record["ui_language"] or "es"
    t = _get_translations(lang)

    # ── Treatment groups (same query as get_liquidation_detail) ──────────────
    prof_id = record["professional_id"]
    period_start = record["period_start"]
    period_end = record["period_end"]

    # Rediseño 2026-07-10 (pedido Carlos: "un administrador y un desglosador
    # súper apto", el PDF viejo salía en 56 páginas): misma consulta y mismas
    # reglas de dinero que generate_liquidation — cobrado proporcional al plan,
    # % de comisión punto-en-el-tiempo por tratamiento — para que el documento
    # cierre EXACTO contra el motor.
    from services.liquidation_service import (  # lazy: evita import circular
        liquidation_service as _liq_svc,
    )

    appt_rows = await pool.fetch(
        """
        SELECT
            a.id AS appointment_id,
            a.appointment_datetime,
            a.status AS appointment_status,
            a.appointment_type,
            a.payment_status,
            COALESCE(a.billing_amount, tt.base_price, 0) AS billing_amount,
            a.billing_notes,
            pat.id AS patient_id,
            pat.first_name || ' ' || COALESCE(pat.last_name, '') AS patient_name,
            tt.code AS treatment_code,
            tt.name AS treatment_name,
            COALESCE(tpi.plan_id, active_tp.id) AS plan_id,
            COALESCE(tp.approved_total, active_tp.approved_total) AS plan_approved_total,
            COALESCE(tp.status, active_tp.status) AS plan_status
        FROM appointments a
        JOIN patients pat ON pat.id = a.patient_id AND pat.tenant_id = $1
        LEFT JOIN treatment_types tt ON tt.code = a.appointment_type AND tt.tenant_id = $1
        LEFT JOIN treatment_plan_items tpi ON tpi.id = a.plan_item_id AND tpi.tenant_id = $1
        LEFT JOIN treatment_plans tp ON tp.id = tpi.plan_id AND tp.tenant_id = $1
        LEFT JOIN LATERAL (
            SELECT id, approved_total, status
            FROM treatment_plans
            WHERE tenant_id = $1
              AND patient_id = a.patient_id
              AND status IN ('approved', 'in_progress')
            ORDER BY created_at DESC
            LIMIT 1
        ) active_tp ON tpi.plan_id IS NULL
        WHERE a.tenant_id = $1
          AND a.professional_id = $2
          AND a.appointment_datetime >= $3
          AND a.appointment_datetime < ($4::date + INTERVAL '1 day')
          AND a.status NOT IN ('deleted', 'cancelled', 'no_show')
        ORDER BY a.appointment_datetime
        """,
        tenant_id,
        prof_id,
        period_start,
        period_end,
    )

    # Pagos por plan (criterio del motor: cobrado proporcional a lo pagado del plan)
    plan_ids = {
        r["plan_id"]
        for r in appt_rows
        if r["plan_id"] and r["plan_status"] in ("approved", "in_progress")
    }
    plan_paid_map = {}
    if plan_ids:
        for r in await pool.fetch(
            """
            SELECT plan_id, COALESCE(SUM(amount), 0) AS total_paid
            FROM treatment_plan_payments
            WHERE tenant_id = $1 AND plan_id = ANY($2::uuid[])
            GROUP BY plan_id
            """,
            tenant_id,
            list(plan_ids),
        ):
            plan_paid_map[r["plan_id"]] = Decimal(str(r["total_paid"]))

    # % de comisión a la fecha de cada turno — cache por fecha (≤31 lookups/mes)
    _config_cache: dict = {}

    async def _config_for(day):
        if day not in _config_cache:
            _config_cache[day] = await _liq_svc.get_commission_config_at_date(
                pool, tenant_id, prof_id, day
            )
        return _config_cache[day]

    session_rows_out = []
    breakdown_map: dict = {}
    zero_price_count = 0
    no_commission_treatments = set()
    live_billed = Decimal("0")
    live_paid = Decimal("0")
    live_prof = Decimal("0")

    for row in appt_rows:
        billing = Decimal(str(row["billing_amount"] or 0))
        pstatus = row["payment_status"] or "pending"
        appt_dt = row["appointment_datetime"]
        appt_date = appt_dt.date() if appt_dt else period_start
        t_code = row["treatment_code"] or ""
        t_name = row["treatment_name"] or t_code or "Sin tratamiento"

        cfg = await _config_for(appt_date)
        per_treatment = cfg.get("per_treatment", {})
        if t_code in per_treatment:
            pct = per_treatment[t_code]["commission_pct"]
        else:
            pct = cfg["default_commission_pct"]
        if cfg.get("source") == "default_zero":
            no_commission_treatments.add(t_name)

        is_plan = row["plan_id"] and row["plan_status"] in ("approved", "in_progress")
        if is_plan:
            approved = Decimal(str(row["plan_approved_total"] or 0))
            if approved > 0:
                ratio = plan_paid_map.get(row["plan_id"], Decimal("0")) / approved
                if ratio > Decimal("1"):
                    ratio = Decimal("1")
            else:
                ratio = Decimal("0")
            paid_amt = billing * ratio
            if ratio >= Decimal("0.999"):
                display_status = "paid"
            elif ratio > 0:
                display_status = "partial"
            else:
                display_status = "pending"
        else:
            paid_amt = billing if pstatus == "paid" else Decimal("0")
            display_status = pstatus

        prof_amt = paid_amt * Decimal(str(pct)) / Decimal("100")

        if billing == 0:
            zero_price_count += 1

        live_billed += billing
        live_paid += paid_amt
        live_prof += prof_amt

        treatment_label = t_name
        if row["billing_notes"]:
            treatment_label = f"{t_name} — {row['billing_notes']}"

        session_rows_out.append(
            {
                "date": appt_dt.strftime("%d/%m/%Y") if appt_dt else "",
                "patient_name": (row["patient_name"] or "").strip() or "Paciente",
                "treatment": treatment_label,
                "amount": float(billing),
                "paid_amount": float(paid_amt),
                "payment_status": display_status,
            }
        )

        b = breakdown_map.setdefault(
            t_code or t_name,
            {
                "name": t_name,
                "count": 0,
                "billed": Decimal("0"),
                "paid": Decimal("0"),
                "prof": Decimal("0"),
                "pcts": set(),
            },
        )
        b["count"] += 1
        b["billed"] += billing
        b["paid"] += paid_amt
        b["prof"] += prof_amt
        b["pcts"].add(float(pct))

    treatment_breakdown = []
    for b in sorted(breakdown_map.values(), key=lambda x: x["billed"], reverse=True):
        if len(b["pcts"]) == 1:
            pct_label = f"{next(iter(b['pcts'])):g}%"
        elif b["paid"] > 0:
            # % efectivo cuando la config cambió a mitad del período
            pct_label = f"~{float(b['prof'] / b['paid'] * 100):.0f}%"
        else:
            pct_label = "—"
        treatment_breakdown.append(
            {
                "name": b["name"],
                "count": b["count"],
                "billed": float(b["billed"]),
                "paid": float(b["paid"]),
                "pct_label": pct_label,
                "prof_amount": float(b["prof"]),
                "clinic_amount": float(b["paid"] - b["prof"]),
            }
        )

    live_totals = {
        "billed": float(live_billed),
        "paid": float(live_paid),
        "prof": float(live_prof),
        "clinic": float(live_paid - live_prof),
        "pct_label": (
            f"{float(live_prof / live_paid * 100):.1f}%" if live_paid > 0 else "—"
        ),
    }

    # ── Payouts ──────────────────────────────────────────────────────────────
    payouts = await pool.fetch(
        """
        SELECT amount, payment_method, payment_date, reference_number
        FROM professional_payouts
        WHERE liquidation_record_id = $1 AND tenant_id = $2
        ORDER BY payment_date DESC
        """,
        liquidation_id,
        tenant_id,
    )

    payouts_out = []
    for p in payouts:
        pay_date = p["payment_date"]
        date_str = pay_date.strftime("%d/%m/%Y") if pay_date else ""
        method_label = t.get(f"method_{p['payment_method']}", p["payment_method"])
        payouts_out.append(
            {
                "date": date_str,
                "amount": float(p["amount"]),
                "payment_method": p["payment_method"],
                "method_label": method_label,
                "reference_number": p["reference_number"],
            }
        )

    # ── Period label ─────────────────────────────────────────────────────────
    # Build a human-readable period label
    if isinstance(period_start, str):
        ps = datetime.strptime(period_start, "%Y-%m-%d")
    else:
        ps = period_start
    if isinstance(period_end, str):
        pe = datetime.strptime(period_end, "%Y-%m-%d")
    else:
        pe = period_end

    month_names = {
        "es": [
            "",
            "enero",
            "febrero",
            "marzo",
            "abril",
            "mayo",
            "junio",
            "julio",
            "agosto",
            "septiembre",
            "octubre",
            "noviembre",
            "diciembre",
        ],
        "en": [
            "",
            "January",
            "February",
            "March",
            "April",
            "May",
            "June",
            "July",
            "August",
            "September",
            "October",
            "November",
            "December",
        ],
        "fr": [
            "",
            "janvier",
            "février",
            "mars",
            "avril",
            "mai",
            "juin",
            "juillet",
            "août",
            "septembre",
            "octobre",
            "novembre",
            "décembre",
        ],
    }

    months = month_names.get(lang, month_names["es"])
    if ps.month == pe.month and ps.year == pe.year:
        period_label = f"{months[ps.month].capitalize()} {ps.year}"
    else:
        period_label = f"{ps.strftime('%d/%m/%Y')} — {pe.strftime('%d/%m/%Y')}"

    # ── Status label ─────────────────────────────────────────────────────────
    status = record["status"] or "draft"

    # ── Notes text ───────────────────────────────────────────────────────────
    notes_data = record["notes"]
    if isinstance(notes_data, str):
        import json
        notes_data = json.loads(notes_data) if notes_data else {}
    notes_data = notes_data or {}
    notes_text = notes_data.get("text", "") or ""

    # ── Generated at ─────────────────────────────────────────────────────────
    generated_at = datetime.now().strftime("%d/%m/%Y a las %H:%M")

    # Count total sessions
    total_sessions = len(session_rows_out)

    # ── Assemble ─────────────────────────────────────────────────────────────
    return {
        "lang": lang,
        "t": t,
        # Template keys (flat for direct access in Jinja2)
        "t_title": t["commission_title"],
        "t_professional": t["professional"],
        "t_name": t["name"],
        "t_specialty": t["specialty"],
        "t_license": t["license"],
        "t_period": t["period"],
        "t_period_range": t["period_range"],
        "t_generated": t["generated"],
        "t_notes": t["notes"],
        "t_summary": t["summary"],
        "t_total_sessions": t["total_sessions"],
        "t_total_billed": t["total_billed"],
        "t_total_paid": t["total_paid"],
        "t_total_pending": t["total_pending"],
        "t_commission_pct": t["commission_pct"],
        "t_commission_amount": t["commission_amount"],
        "t_net_payout": t["net_payout"],
        "t_detail": t["detail"],
        "t_date": t["date"],
        "t_treatment": t["treatment"],
        "t_amount": t["amount"],
        "t_pay_status": t["pay_status"],
        "t_paid": t["paid"],
        "t_partial": t["partial"],
        "t_pending": t["pending"],
        "t_subtotal": t["subtotal"],
        "t_breakdown_title": t["breakdown_title"],
        "t_qty": t["qty"],
        "t_collected": t["collected"],
        "t_pct_col": t["pct_col"],
        "t_prof_share": t["prof_share"],
        "t_clinic_share": t["clinic_share"],
        "t_patient": t["patient"],
        "t_clinic_total": t["clinic_total"],
        "t_totals": t["totals"],
        "t_zero_price_note": t["zero_price_note"],
        "t_no_commission_note": t["no_commission_note"],
        "t_payout_history": t["payout_history"],
        "t_clinic_signature": t["clinic_signature"],
        "t_prof_signature": t["prof_signature"],
        "t_footer_auto": t["footer_auto"],
        "t_status": {
            "draft": t["status_draft"],
            "generated": t["status_generated"],
            "approved": t["status_approved"],
            "paid": t["status_paid"],
        },
        # Data
        "clinic": {
            "name": record["clinic_name"] or "Clínica",
            "address": record["clinic_address"] or "",
            "phone": record["clinic_phone"] or "",
            "logo_url": resolve_logo_data_uri(tenant_id) or record["logo_url"] or "",
        },
        "professional": {
            "full_name": (record["professional_full_name"] or "").strip()
            or "Profesional",
            "specialty": record["specialty"] or "",
            "license_number": "",
            "email": record["professional_email"] or "",
        },
        "period": {
            "start": str(period_start),
            "end": str(period_end),
            "label": period_label,
        },
        "summary": {
            "total_sessions": total_sessions,
            "total_billed": round(float(record["total_billed"] or 0), 2),
            "total_paid": round(float(record["total_paid"] or 0), 2),
            "total_pending": round(float(record["total_pending"] or 0), 2),
            "commission_pct": round(float(record["commission_pct"] or 0), 2),
            "commission_amount": round(float(record["commission_amount"] or 0), 2),
            "payout_amount": round(float(record["payout_amount"] or 0), 2),
            # Lo que le queda a la clínica de lo efectivamente cobrado
            "clinic_total": round(
                float(record["total_paid"] or 0) - float(record["payout_amount"] or 0),
                2,
            ),
        },
        "treatment_breakdown": treatment_breakdown,
        "session_rows": session_rows_out,
        "live_totals": live_totals,
        "zero_price_count": zero_price_count,
        "no_commission_treatments": sorted(no_commission_treatments),
        "payouts": payouts_out,
        "generated_at": generated_at,
        "generated_at_label": generated_at,  # alias for @page footer
        "status": status,
        "notes_text": notes_text,
        # For email use
        "professional_email": record["professional_email"] or "",
    }


# =============================================================================
# LAYER 2: HTML RENDERING (Jinja2)
# =============================================================================


def render_liquidation_html(data: dict) -> str:
    """Render the liquidation_statement.html template with gathered data."""
    template = _jinja_env.get_template("liquidation_statement.html")
    return template.render(**data)


def render_liquidation_email_html(data: dict) -> str:
    """Render the liquidation_email.html template."""
    template = _jinja_env.get_template("liquidation_email.html")
    t = data["t"]
    lang = data.get("lang", "es")
    return template.render(
        lang=lang,
        clinic_name=data["clinic"]["name"],
        professional_name=data["professional"]["full_name"],
        period_label=data["period"]["label"],
        payout_amount=f"{data['summary']['payout_amount']:,.0f}".replace(",", "."),
        t_greeting=t["email_greeting"],
        t_body_intro=t["email_body_intro"],
        t_payout_label=t["email_payout_label"],
        t_attachment_note=t["email_attachment_note"],
        t_contact_note=t["email_contact_note"],
        t_closing=t["email_closing"],
        t_team=t["email_team"],
        t_footer_auto=t["email_footer_auto"],
    )


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


async def generate_liquidation_pdf(
    pool, liquidation_id: int, tenant_id: int
) -> Optional[str]:
    """
    Generate a liquidation PDF and cache it to disk.

    Output path: /app/uploads/liquidations/{tenant_id}/{liquidation_id}.pdf

    Always regenerates (caller controls cache invalidation).
    Returns the file path on success, None if the record is not found.
    """
    upload_dir = Path(f"/app/uploads/liquidations/{tenant_id}")
    pdf_path = str(upload_dir / f"{liquidation_id}.pdf")

    data = await gather_liquidation_pdf_data(pool, liquidation_id, tenant_id)
    if not data:
        return None

    html = render_liquidation_html(data)

    result = await asyncio.to_thread(_generate_pdf_sync, html, pdf_path)
    return result
