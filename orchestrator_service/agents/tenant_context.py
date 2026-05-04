"""Multi-agent tenant context builder.

Builds the tenant-configured prompt blocks ONCE per turn, stores them in
AgentState["tenant_context"], and each specialist reads only the subset
whitelisted for its role via select_blocks_for_specialist().

All DB queries filter by tenant_id (Sovereignty Protocol §1).
Every per-block helper is wrapped in try/except — a single failure returns
"" (or {}) for that block and never crashes the builder.

See openspec/changes/multi-agent-tenant-context-parity/ for the full spec.
"""
from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)


# Canonical list of all block keys the builder produces.
# `sede_info` is the only dict value; everything else is a formatted string.
ALL_BLOCK_KEYS: tuple[str, ...] = (
    "clinic_basics",
    "insurance_section",
    "payment_section",
    "special_conditions_block",
    "support_policy_block",
    "derivation_rules_section",
    "holidays_section",
    "faqs_section",
    "bank_info",
    "sede_info",          # dict
    "sede_info_text",     # string rendering of sede_info for prompt interpolation
)


# Per-specialist block whitelist (REQ-4.1 / design D3).
SPECIALIST_BLOCKS: dict[str, list[str]] = {
    "reception": ["clinic_basics", "faqs_section", "holidays_section"],
    "booking":   ["clinic_basics", "holidays_section", "derivation_rules_section", "sede_info_text"],
    "triage":    ["clinic_basics", "special_conditions_block"],
    "billing":   ["clinic_basics", "insurance_section", "payment_section", "bank_info"],
    "anamnesis": ["clinic_basics", "special_conditions_block"],
    "handoff":   ["clinic_basics", "support_policy_block"],
}

# Invariant check: every whitelisted block must exist in ALL_BLOCK_KEYS.
_unknown = {k for keys in SPECIALIST_BLOCKS.values() for k in keys} - set(ALL_BLOCK_KEYS)
assert not _unknown, f"SPECIALIST_BLOCKS references unknown keys: {_unknown}"


# --- Import formatters from main (graceful fallback, design D4) ---
try:
    from main import (  # type: ignore
        _format_insurance_providers,
        _format_payment_options,
        _format_special_conditions,
        _format_support_policy,
        _format_derivation_rules,
    )
    _MAIN_FORMATTERS_AVAILABLE = True
except Exception as exc:  # pragma: no cover - import guard
    logger.error(f"agents.tenant_context: failed to import main formatters: {exc}")
    _MAIN_FORMATTERS_AVAILABLE = False

    def _format_insurance_providers(*a, **k): return ""        # type: ignore
    def _format_payment_options(*a, **k): return ""            # type: ignore
    def _format_special_conditions(*a, **k): return ""         # type: ignore
    def _format_support_policy(*a, **k): return ""             # type: ignore
    def _format_derivation_rules(*a, **k): return ""           # type: ignore


# ---------------------------------------------------------------------------
# Pure helpers
# ---------------------------------------------------------------------------


def select_blocks_for_specialist(state: dict, specialist_name: str) -> dict[str, str]:
    """Return only the blocks whitelisted for the given specialist.

    Pure function, no I/O. Missing keys default to empty string so
    specialist prompt templates always format cleanly.
    Unknown specialist names fall back to clinic_basics only (safe default).
    """
    ctx = state.get("tenant_context") or {}
    allowed = SPECIALIST_BLOCKS.get(specialist_name, ["clinic_basics"])
    return {key: (ctx.get(key) or "") for key in allowed}


def _format_clinic_basics(tenant_row: dict | None) -> str:
    """Always-present identity block (design D7). ~50-150 tokens."""
    if not tenant_row:
        return ""
    bot_name = (tenant_row.get("bot_name") or "TORA").strip() or "TORA"
    clinic_name = (tenant_row.get("clinic_name") or "la clínica").strip() or "la clínica"
    specialty = (tenant_row.get("system_prompt_template") or "").strip()
    parts = [
        "## CLÍNICA",
        f"Sos {bot_name}, del equipo de {clinic_name}.",
    ]
    if specialty:
        parts.append(f"\n{specialty}")
    return "\n".join(parts)


def _format_sede_info_text(sede_info: dict | None) -> str:
    """String rendering of sede_info dict for prompt interpolation (design D8)."""
    if not sede_info:
        return ""
    loc = (sede_info.get("location") or "").strip()
    addr = (sede_info.get("address") or "").strip()
    maps = (sede_info.get("maps_url") or "").strip()
    if not loc and not addr:
        return ""
    parts = ["## SEDE PARA HOY"]
    if loc:
        parts.append(f"Ubicación: {loc}")
    if addr:
        parts.append(f"Dirección: {addr}")
    if maps:
        parts.append(f"Maps: {maps}")
    return "\n".join(parts)


def _format_bank_info(tenant_row: dict | None) -> str:
    """Format bank transfer info block for Billing specialist."""
    if not tenant_row:
        return ""
    cbu = (tenant_row.get("bank_cbu") or "").strip()
    alias = (tenant_row.get("bank_alias") or "").strip()
    holder = (tenant_row.get("bank_holder_name") or "").strip()
    if not (cbu or alias or holder):
        return ""
    parts = ["## DATOS BANCARIOS PARA TRANSFERENCIAS"]
    if holder:
        parts.append(f"Titular: {holder}")
    if cbu:
        parts.append(f"CBU: {cbu}")
    if alias:
        parts.append(f"Alias: {alias}")
    return "\n".join(parts)


def _format_holidays_inline(upcoming_holidays: list) -> str:
    """Inline formatter mirroring main.py:7503 (not exported from main)."""
    if not upcoming_holidays:
        return ""
    hol_lines = []
    for h in upcoming_holidays[:7]:
        ch = h.get("custom_hours")
        if ch:
            hol_lines.append(
                f"• {h['date']}: {h['name']} — HORARIO ESPECIAL {ch['start']}–{ch['end']}"
            )
        else:
            hol_lines.append(f"• {h['date']}: {h['name']} — CERRADO")
    section = "\n## FERIADOS PRÓXIMOS\n" + "\n".join(hol_lines)
    section += (
        "\nREGLA: Si feriado CERRADO → informale al paciente y ofrecé el próximo "
        "día hábil. Si HORARIO ESPECIAL → ofrecer turnos en ese rango."
    )
    return section


def _parse_jsonb(value: Any) -> Any:
    """asyncpg may return JSONB as a string — defensive parser."""
    if isinstance(value, str):
        try:
            return json.loads(value)
        except (json.JSONDecodeError, TypeError):
            return None
    return value


def _resolve_sede_for_today(working_hours: Any) -> dict:
    """Extract sede info for the current weekday from working_hours JSONB."""
    wh = _parse_jsonb(working_hours)
    if not isinstance(wh, dict):
        return {}
    day_keys = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
    today_key = day_keys[datetime.now().weekday()]
    day_conf = wh.get(today_key) or {}
    if not isinstance(day_conf, dict):
        return {}
    return {
        "location": day_conf.get("location") or "",
        "address": day_conf.get("address") or "",
        "maps_url": day_conf.get("maps_url") or "",
    }


# ---------------------------------------------------------------------------
# Async fetchers — each returns "" (or {}) on failure, never raises
# ---------------------------------------------------------------------------


async def _fetch_tenant_row(pool, tenant_id: int) -> dict | None:
    """One big fetch for all tenant-level columns used across blocks."""
    try:
        row = await pool.fetchrow(
            """SELECT clinic_name, address, google_maps_url, working_hours,
                      system_prompt_template, bot_name,
                      bank_cbu, bank_alias, bank_holder_name,
                      payment_methods, financing_available, max_installments,
                      installments_interest_free, financing_provider, financing_notes,
                      cash_discount_percent, accepts_crypto,
                      accepts_pregnant_patients, pregnancy_restricted_treatments,
                      pregnancy_notes, accepts_pediatric, min_pediatric_age_years,
                      pediatric_notes, high_risk_protocols, requires_anamnesis_before_booking,
                      complaint_escalation_email, complaint_escalation_phone,
                      expected_wait_time_minutes, revision_policy, review_platforms,
                      complaint_handling_protocol, auto_send_review_link_after_followup
               FROM tenants WHERE id = $1""",
            tenant_id,
        )
        return dict(row) if row else None
    except Exception as exc:
        logger.debug(f"tenant_context: _fetch_tenant_row failed for tenant {tenant_id}: {exc}")
        return None


async def _fetch_treatment_display_map(pool, tenant_id: int) -> dict[str, str]:
    try:
        rows = await pool.fetch(
            "SELECT code, COALESCE(patient_display_name, name) AS display_name "
            "FROM treatment_types WHERE tenant_id = $1 AND is_active = true",
            tenant_id,
        )
        return {r["code"]: r["display_name"] for r in rows or []}
    except Exception as exc:
        logger.debug(f"tenant_context: treatment_display_map failed: {exc}")
        return {}


async def _fetch_insurance_section(pool, tenant_id: int, treatment_display_map: dict) -> str:
    try:
        rows = await pool.fetch(
            """SELECT id, provider_name, status, coverage_by_treatment, is_prepaid,
                      employee_discount_percent, default_copay_percent, external_target,
                      requires_copay, copay_notes, ai_response_template
               FROM tenant_insurance_providers
               WHERE tenant_id = $1 AND is_active = true
               ORDER BY sort_order, provider_name""",
            tenant_id,
        )
        providers = []
        for r in rows or []:
            d = dict(r)
            parsed = _parse_jsonb(d.get("coverage_by_treatment"))
            d["coverage_by_treatment"] = parsed if isinstance(parsed, dict) else {}
            providers.append(d)
        if not providers:
            return ""
        return _format_insurance_providers(providers, treatment_display_map) or ""
    except Exception as exc:
        logger.debug(f"tenant_context: insurance_section failed: {exc}")
        return ""


async def _fetch_payment_section(tenant_row: dict | None) -> str:
    if not tenant_row:
        return ""
    try:
        pm = _parse_jsonb(tenant_row.get("payment_methods")) or []
        if not isinstance(pm, list):
            pm = []
        cdp = tenant_row.get("cash_discount_percent")
        try:
            cdp_f = float(cdp) if cdp is not None else None
        except (TypeError, ValueError):
            cdp_f = None
        return _format_payment_options(
            payment_methods=pm,
            financing_available=bool(tenant_row.get("financing_available")),
            max_installments=tenant_row.get("max_installments"),
            installments_interest_free=bool(
                tenant_row.get("installments_interest_free")
                if tenant_row.get("installments_interest_free") is not None else True
            ),
            financing_provider=tenant_row.get("financing_provider") or "",
            financing_notes=tenant_row.get("financing_notes") or "",
            cash_discount_percent=cdp_f,
            accepts_crypto=bool(tenant_row.get("accepts_crypto")),
        ) or ""
    except Exception as exc:
        logger.debug(f"tenant_context: payment_section failed: {exc}")
        return ""


async def _fetch_special_conditions_block(tenant_row: dict | None, treatment_name_map: dict) -> str:
    if not tenant_row:
        return ""
    try:
        return _format_special_conditions(tenant_row, treatment_name_map=treatment_name_map) or ""
    except Exception as exc:
        logger.debug(f"tenant_context: special_conditions failed: {exc}")
        return ""


async def _fetch_support_policy_block(tenant_row: dict | None) -> str:
    if not tenant_row:
        return ""
    try:
        return _format_support_policy(tenant_row) or ""
    except Exception as exc:
        logger.debug(f"tenant_context: support_policy failed: {exc}")
        return ""


async def _fetch_derivation_rules_section(pool, tenant_id: int) -> str:
    try:
        rows = await pool.fetch(
            """SELECT dr.id, dr.rule_name, dr.patient_condition, dr.treatment_categories,
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
               ORDER BY dr.priority_order ASC, dr.id ASC""",
            tenant_id,
        )
        rules = [dict(r) for r in rows or []]
        if not rules:
            return ""
        return _format_derivation_rules(rules) or ""
    except Exception as exc:
        logger.debug(f"tenant_context: derivation_rules failed: {exc}")
        return ""


async def _fetch_holidays_section(pool, tenant_id: int) -> str:
    try:
        from services.holiday_service import get_upcoming_holidays  # type: ignore

        holidays = await get_upcoming_holidays(pool, tenant_id, days_ahead=30)
        return _format_holidays_inline(holidays or [])
    except Exception as exc:
        logger.debug(f"tenant_context: holidays_section failed: {exc}")
        return ""


async def _fetch_faqs_section(pool, tenant_id: int, user_message_text: str) -> str:
    """Prefer RAG top-K; fall back to static top-20 FAQs if unavailable."""
    try:
        faq_rows = await pool.fetch(
            "SELECT category, question, answer FROM clinic_faqs "
            "WHERE tenant_id = $1 ORDER BY sort_order ASC, id ASC",
            tenant_id,
        )
        faqs = [dict(r) for r in faq_rows or []]
        if not faqs:
            return ""
        # Try RAG first
        try:
            from services.embedding_service import format_all_context_with_rag  # type: ignore

            rag = await format_all_context_with_rag(
                pool, tenant_id, user_message_text or "", faqs
            )
            if isinstance(rag, dict):
                section = rag.get("faqs_section")
                if section:
                    return section
        except Exception as rag_exc:
            logger.debug(f"tenant_context: RAG unavailable, static fallback: {rag_exc}")

        # Static fallback — format top 20
        lines = ["## PREGUNTAS FRECUENTES"]
        for f in faqs[:20]:
            q = (f.get("question") or "").strip()
            a = (f.get("answer") or "").strip()
            if q and a:
                lines.append(f"P: {q}\nR: {a}")
        return "\n".join(lines) if len(lines) > 1 else ""
    except Exception as exc:
        logger.debug(f"tenant_context: faqs_section failed: {exc}")
        return ""


# ---------------------------------------------------------------------------
# Top-level orchestrator
# ---------------------------------------------------------------------------


async def build_tenant_context_blocks(
    pool,
    tenant_id: int,
    user_message_text: str = "",
    intent_tags: set[str] | None = None,
) -> dict[str, Any]:
    """Build all tenant context blocks for a single turn (REQ-1).

    Fetches everything in parallel where independent. Tolerates per-block
    failures (returns "" / {} for that block). Returns a dict with every
    key in ALL_BLOCK_KEYS.
    """
    # Initialize empty shell — guarantees all keys are present on every return path
    blocks: dict[str, Any] = {k: ("" if k != "sede_info" else {}) for k in ALL_BLOCK_KEYS}

    if not _MAIN_FORMATTERS_AVAILABLE:
        logger.warning(
            "tenant_context: main formatters unavailable — local blocks "
            "(clinic_basics/bank_info/sede/holidays) still populate, "
            "main-derived blocks fall back to empty."
        )

    try:
        # Stage 1: fetch the big tenant row + treatment_display_map in parallel.
        # Several downstream blocks depend on these.
        tenant_row, treatment_display_map = await asyncio.gather(
            _fetch_tenant_row(pool, tenant_id),
            _fetch_treatment_display_map(pool, tenant_id),
        )

        # Stage 2: everything that only needs tenant_row or pool — parallel.
        (
            insurance_section,
            payment_section,
            special_conditions_block,
            support_policy_block,
            derivation_rules_section,
            holidays_section,
            faqs_section,
        ) = await asyncio.gather(
            _fetch_insurance_section(pool, tenant_id, treatment_display_map),
            _fetch_payment_section(tenant_row),
            _fetch_special_conditions_block(tenant_row, treatment_display_map),
            _fetch_support_policy_block(tenant_row),
            _fetch_derivation_rules_section(pool, tenant_id),
            _fetch_holidays_section(pool, tenant_id),
            _fetch_faqs_section(pool, tenant_id, user_message_text),
        )

        # Sync helpers (derived from tenant_row)
        clinic_basics = _format_clinic_basics(tenant_row)
        bank_info = _format_bank_info(tenant_row)
        sede_info = _resolve_sede_for_today(tenant_row.get("working_hours")) if tenant_row else {}
        sede_info_text = _format_sede_info_text(sede_info)

        blocks.update(
            {
                "clinic_basics": clinic_basics,
                "insurance_section": insurance_section,
                "payment_section": payment_section,
                "special_conditions_block": special_conditions_block,
                "support_policy_block": support_policy_block,
                "derivation_rules_section": derivation_rules_section,
                "holidays_section": holidays_section,
                "faqs_section": faqs_section,
                "bank_info": bank_info,
                "sede_info": sede_info,
                "sede_info_text": sede_info_text,
            }
        )
    except Exception as exc:
        logger.error(f"tenant_context: build_tenant_context_blocks crashed: {exc}")
        # Fall through and return the (possibly partially-populated) shell.

    return blocks
