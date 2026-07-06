"""Carga la config REAL de un tenant y arma el system prompt REAL del agente.

Reutiliza EXACTAMENTE las mismas consultas que services/buffer_task.py usa para
alimentar build_system_prompt(), de modo que el prompt que prueba el banco es el
mismo que corre en producción/pruebas (no una imitación). Cualquier cambio de
regla en build_system_prompt se refleja automáticamente acá.
"""
from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Optional


def _maybe_json(value: Any) -> Any:
    """asyncpg puede devolver JSONB como string en algunas versiones."""
    if isinstance(value, str):
        try:
            return json.loads(value)
        except (ValueError, TypeError):
            return None
    return value


async def load_prompt_inputs(pool, tenant_id: int) -> dict[str, Any]:
    """Trae de la base todo lo que build_system_prompt necesita para este tenant.

    Espeja el bloque de fetch de buffer_task.py (~1150-1360).
    """
    tenant_row = await pool.fetchrow("SELECT * FROM tenants WHERE id = $1", tenant_id)
    if not tenant_row:
        raise RuntimeError(f"No existe el tenant {tenant_id}")
    t = dict(tenant_row)

    # --- Pitch de especialidad (frase de orientación configurada) ---
    system_prompt_template = (t.get("system_prompt_template") or "").strip()

    # --- Working hours (JSONB) ---
    clinic_working_hours = _maybe_json(t.get("working_hours"))

    # --- Profesional principal (para posicionamiento) ---
    lead_professional_name = ""
    prof_row = await pool.fetchrow(
        "SELECT first_name, last_name FROM professionals "
        "WHERE tenant_id = $1 AND is_active = true ORDER BY id ASC LIMIT 1",
        tenant_id,
    )
    if prof_row:
        lead_professional_name = (
            f"{prof_row['first_name']} {prof_row.get('last_name', '') or ''}".strip()
        )

    # --- FAQs ---
    faq_rows = await pool.fetch(
        "SELECT category, question, answer FROM clinic_faqs "
        "WHERE tenant_id = $1 ORDER BY sort_order ASC, id ASC",
        tenant_id,
    )
    faqs = [dict(r) for r in faq_rows] if faq_rows else []

    # --- Obras sociales ---
    insurance_providers: list[dict] = []
    ins_rows = await pool.fetch(
        """
        SELECT id, provider_name, status, coverage_by_treatment, is_prepaid,
               employee_discount_percent, default_copay_percent, external_target,
               requires_copay, copay_notes, ai_response_template,
               scheduling_mode, scheduling_delay_days
        FROM tenant_insurance_providers
        WHERE tenant_id = $1 AND is_active = true
        ORDER BY sort_order, provider_name
        """,
        tenant_id,
    )
    for r in ins_rows or []:
        d = dict(r)
        cov = _maybe_json(d.get("coverage_by_treatment"))
        d["coverage_by_treatment"] = cov if isinstance(cov, dict) else {}
        insurance_providers.append(d)

    # --- Tratamientos activos ---
    tt_rows = await pool.fetch(
        """
        SELECT code, name, patient_display_name, consultation_requirements
        FROM treatment_types
        WHERE tenant_id = $1 AND is_active = true
        ORDER BY name
        """,
        tenant_id,
    )
    treatment_types_list = [dict(r) for r in tt_rows] if tt_rows else []

    # --- Reglas de derivación ---
    der_rows = await pool.fetch(
        """
        SELECT dr.id, dr.rule_name, dr.patient_condition, dr.treatment_categories,
               dr.target_type, dr.target_professional_id, dr.priority_order,
               dr.enable_escalation, dr.fallback_professional_id,
               dr.fallback_team_mode, dr.max_wait_days_before_escalation,
               dr.escalation_message_template,
               p.first_name AS target_professional_name,
               fp.first_name AS fallback_professional_name
        FROM professional_derivation_rules dr
        LEFT JOIN professionals p ON dr.target_professional_id = p.id
        LEFT JOIN professionals fp ON dr.fallback_professional_id = fp.id
        WHERE dr.tenant_id = $1 AND dr.is_active = true
        ORDER BY dr.priority_order ASC, dr.id ASC
        """,
        tenant_id,
    )
    derivation_rules = [dict(r) for r in der_rows] if der_rows else []

    # --- Bloque de política de soporte (best-effort) ---
    support_policy_block = ""
    try:
        from main import _format_support_policy  # type: ignore

        support_policy_block = _format_support_policy(t) or ""
    except Exception:
        support_policy_block = ""

    return {
        "clinic_name": t.get("clinic_name") or "la clínica",
        "bot_name": t.get("bot_name") or "TORA",
        "consultation_price": t.get("consultation_price"),
        "clinic_address": t.get("address") or "",
        "clinic_maps_url": t.get("maps_url") or "",
        "clinic_working_hours": clinic_working_hours,
        "system_prompt_template": system_prompt_template,
        "lead_professional_name": lead_professional_name,
        "faqs": faqs,
        "insurance_providers": insurance_providers,
        "treatment_types_list": treatment_types_list,
        "derivation_rules": derivation_rules,
        "bank_cbu": t.get("bank_cbu") or "",
        "bank_alias": t.get("bank_alias") or "",
        "bank_holder_name": t.get("bank_holder_name") or "",
        "anamnesis_url": t.get("frontend_url") or "",
        # Pago / financiación (migración 035) — defensivo
        "payment_methods": _maybe_json(t.get("payment_methods")) or [],
        "financing_available": bool(t.get("financing_available")),
        "max_installments": t.get("max_installments"),
        "installments_interest_free": (
            t.get("installments_interest_free")
            if t.get("installments_interest_free") is not None
            else True
        ),
        "financing_provider": t.get("financing_provider") or "",
        "financing_notes": t.get("financing_notes") or "",
        "cash_discount_percent": t.get("cash_discount_percent"),
        "accepts_crypto": bool(t.get("accepts_crypto")),
        "support_policy_block": support_policy_block,
    }


def build_eval_prompt(
    inputs: dict[str, Any],
    patient_status: str = "new_lead",
    patient_context: str = "",
    current_time: Optional[str] = None,
    is_greeting_pending: bool = True,
) -> str:
    """Arma el system prompt REAL con build_system_prompt() y la config cargada."""
    from main import build_system_prompt  # import perezoso (main es pesado)

    if current_time is None:
        current_time = datetime.now().strftime("%A %d/%m/%Y %H:%M")

    return build_system_prompt(
        clinic_name=inputs["clinic_name"],
        current_time=current_time,
        response_language="es",
        ad_context="",
        patient_context=patient_context,
        clinic_address=inputs["clinic_address"],
        clinic_maps_url=inputs["clinic_maps_url"],
        clinic_working_hours=inputs["clinic_working_hours"],
        faqs=inputs["faqs"],
        patient_status=patient_status,
        consultation_price=inputs["consultation_price"],
        anamnesis_url=inputs["anamnesis_url"],
        bank_cbu=inputs["bank_cbu"],
        bank_alias=inputs["bank_alias"],
        bank_holder_name=inputs["bank_holder_name"],
        upcoming_holidays=[],
        insurance_providers=inputs["insurance_providers"],
        derivation_rules=inputs["derivation_rules"],
        specialty_pitch=inputs["system_prompt_template"],
        professional_name=inputs["lead_professional_name"],
        bot_name=inputs["bot_name"],
        intent_tags=None,
        is_greeting_pending=is_greeting_pending,
        treatment_types=inputs["treatment_types_list"],
        payment_methods=inputs["payment_methods"],
        financing_available=inputs["financing_available"],
        max_installments=inputs["max_installments"],
        installments_interest_free=inputs["installments_interest_free"],
        financing_provider=inputs["financing_provider"],
        financing_notes=inputs["financing_notes"],
        cash_discount_percent=inputs["cash_discount_percent"],
        accepts_crypto=inputs["accepts_crypto"],
        special_conditions_block="",
        support_policy_block=inputs["support_policy_block"],
    )
