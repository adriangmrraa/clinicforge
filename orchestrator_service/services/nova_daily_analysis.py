"""
Nova Daily Analysis — Background job that analyzes clinic activity every 12 hours.

Collects conversations + operational stats per tenant, sends to GPT-4o-mini,
and caches structured insights in Redis. Also generates a consolidated
cross-sede CEO view.
"""

import os
import json
import logging
import asyncio
from datetime import datetime, timedelta

import httpx
from httpx import HTTPStatusError

logger = logging.getLogger(__name__)

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

ANALYSIS_SYSTEM_PROMPT = """Analiza la actividad de una clinica dental en las ultimas 24 horas.

DATOS DE CONVERSACIONES (WhatsApp/Instagram/Facebook):
{conversation_summary}

DATOS OPERATIVOS:
- Turnos creados: {created}
- Turnos completados: {completed}
- Cancelaciones: {cancelled} (razones: {cancel_reasons})
- No-shows: {no_shows}
- Derivaciones a humano: {derivations}
- Pacientes nuevos: {new_patients}
- Facturacion: ${revenue}

Retorna un JSON con:
- temas_frecuentes: [3-5 temas mas consultados por pacientes, cada uno con "tema" y "cantidad_aprox"]
- problemas: [situaciones donde el agente respondio mal, derivo innecesariamente, o no supo responder]
- temas_sin_cobertura: [preguntas frecuentes que el agente no pudo responder]
- sugerencias: [2-3 mejoras concretas, cada una con "titulo" y "detalle". Pueden ser: agregar FAQ, ajustar horarios, configurar precios, etc.]
- cancelacion_insights: [analisis de por que se cancelaron turnos, si hay patron]
- satisfaccion_estimada: numero 1-10 basado en tono de conversaciones
- resumen: 2-3 oraciones resumen del dia (incluir datos operativos clave)

Solo JSON valido, sin explicaciones ni markdown.
"""

CONSOLIDATED_PROMPT_TEMPLATE = """Compara el rendimiento de {sede_count} sedes de una clinica dental en las ultimas 24 horas.

DATOS POR SEDE:
{per_sede_json}

Retorna JSON con:
- ranking: lista de sedes ordenadas por rendimiento (mejor a peor), cada una con "sede", "score_estimado" (1-10), "razon"
- mejor_sede: {{"sede", "motivo"}} (la que mejor rindio)
- peor_sede: {{"sede", "motivo", "sugerencia"}} (la que peor rindio, con sugerencia de mejora)
- comparativas: [3-5 insights comparando sedes. Ej: "Sede X tuvo 60% mas cancelaciones que Sede Y"]
- tendencia_global: 1 oracion sobre la tendencia general del grupo de sedes
- resumen_ceo: 2-3 oraciones resumen ejecutivo para el CEO

Solo JSON valido.
"""

REDIS_TTL = 172800  # 48 hours


# ---------------------------------------------------------------------------
# Main loop & orchestrator
# ---------------------------------------------------------------------------


async def nova_daily_analysis_loop(pool, redis):
    """Background loop - runs every 12 hours."""
    while True:
        try:
            await _run_analysis(pool, redis)
        except Exception as e:
            logger.error(f"nova_daily_analysis_error: {e}")
        await asyncio.sleep(12 * 60 * 60)  # 12 hours


async def _run_analysis(pool, redis):
    """Iterate all active tenants, then generate consolidated CEO view."""
    tenant_rows = await pool.fetch(
        "SELECT id, clinic_name FROM tenants ORDER BY id ASC"
    )
    for tenant in tenant_rows:
        try:
            await _analyze_tenant(pool, redis, tenant["id"], tenant["clinic_name"])
        except Exception as e:
            logger.error(f"nova_analysis_tenant_{tenant['id']}_error: {e}")

    # CEO consolidated analysis (cross-sede)
    await _analyze_consolidated(pool, redis, tenant_rows)


# ---------------------------------------------------------------------------
# Per-tenant analysis
# ---------------------------------------------------------------------------


async def _analyze_tenant(pool, redis, tenant_id: int, clinic_name: str):
    """Analyze a single tenant: conversations + operational stats -> GPT -> Redis."""
    conversation_summary = await _get_conversation_summary(pool, tenant_id)
    stats = await _get_operational_stats(pool, tenant_id)

    prompt = ANALYSIS_SYSTEM_PROMPT.format(
        conversation_summary=conversation_summary,
        created=stats["turnos_creados"],
        completed=stats["turnos_completados"],
        cancelled=stats["cancelaciones"],
        cancel_reasons=stats.get("cancel_reasons", "sin datos"),
        no_shows=stats["no_shows"],
        derivations=stats["derivaciones"],
        new_patients=stats["nuevos_pacientes"],
        revenue=stats["facturacion"] or 0,
    )

    analysis = await _analyze_with_gpt(prompt, OPENAI_API_KEY, tenant_id=tenant_id)
    if analysis is None:
        logger.warning(f"nova_analysis_tenant_{tenant_id}: GPT returned no result")
        return

    payload = {
        **analysis,
        "operational_stats": {
            "turnos_creados": stats["turnos_creados"],
            "turnos_completados": stats["turnos_completados"],
            "cancelaciones": stats["cancelaciones"],
            "no_shows": stats["no_shows"],
            "derivaciones": stats["derivaciones"],
            "nuevos_pacientes": stats["nuevos_pacientes"],
            "facturacion": stats["facturacion"],
        },
        "analyzed_at": datetime.utcnow().isoformat(),
    }

    await redis.setex(
        f"nova_daily:{tenant_id}",
        REDIS_TTL,
        json.dumps(payload, ensure_ascii=False),
    )
    logger.info(f"nova_analysis_tenant_{tenant_id}_cached ({clinic_name})")


# ---------------------------------------------------------------------------
# Cross-sede consolidated analysis (CEO)
# ---------------------------------------------------------------------------


async def _analyze_consolidated(pool, redis, tenants):
    """Generate cross-sede comparison for CEO view."""
    per_sede_stats = []
    for t in tenants:
        tid = t["id"]
        stats = await _get_operational_stats(pool, tid)
        per_sede_stats.append(
            {
                "sede": t["clinic_name"],
                "tenant_id": tid,
                **stats,
            }
        )

    prompt = CONSOLIDATED_PROMPT_TEMPLATE.format(
        sede_count=len(tenants),
        per_sede_json=json.dumps(per_sede_stats, indent=2, ensure_ascii=False),
    )

    first_tenant_id = tenants[0]["id"] if tenants else 0
    analysis = await _analyze_with_gpt(
        prompt, OPENAI_API_KEY, tenant_id=first_tenant_id
    )
    if analysis:
        payload = {
            **analysis,
            "analyzed_at": datetime.utcnow().isoformat(),
            "per_sede_stats": per_sede_stats,
        }
        await redis.setex(
            "nova_daily:consolidated",
            REDIS_TTL,
            json.dumps(payload, ensure_ascii=False),
        )
        logger.info("nova_analysis_consolidated_cached")


# ---------------------------------------------------------------------------
# Data helpers
# ---------------------------------------------------------------------------


async def _get_operational_stats(pool, tenant_id: int) -> dict:
    """Fetch operational stats for the last 24 hours."""
    async with pool.acquire() as conn:
        created = await conn.fetchval(
            "SELECT COUNT(*) FROM appointments "
            "WHERE tenant_id = $1 AND created_at >= NOW() - INTERVAL '24 hours'",
            tenant_id,
        )

        completed = await conn.fetchval(
            "SELECT COUNT(*) FROM appointments "
            "WHERE tenant_id = $1 AND status = 'completed' "
            "AND completed_at >= NOW() - INTERVAL '24 hours'",
            tenant_id,
        )

        cancel_row = await conn.fetchrow(
            "SELECT COUNT(*) AS cancelled, "
            "       array_agg(cancellation_reason) AS reasons "
            "FROM appointments "
            "WHERE tenant_id = $1 AND status = 'cancelled' "
            "AND updated_at >= NOW() - INTERVAL '24 hours'",
            tenant_id,
        )
        cancelled = cancel_row["cancelled"] if cancel_row else 0
        raw_reasons = cancel_row["reasons"] if cancel_row else []
        # Filter out None values from reasons array
        cancel_reasons = [r for r in (raw_reasons or []) if r] or ["sin datos"]

        no_shows = await conn.fetchval(
            "SELECT COUNT(*) FROM appointments "
            "WHERE tenant_id = $1 AND status = 'no-show' "
            "AND appointment_datetime >= NOW() - INTERVAL '24 hours'",
            tenant_id,
        )

        derivations = await conn.fetchval(
            "SELECT COUNT(*) FROM chat_messages "
            "WHERE tenant_id = $1 AND role = 'tool' "
            "AND content ILIKE '%derivhumano%' "
            "AND created_at >= NOW() - INTERVAL '24 hours'",
            tenant_id,
        )

        new_patients = await conn.fetchval(
            "SELECT COUNT(*) FROM patients "
            "WHERE tenant_id = $1 AND created_at >= NOW() - INTERVAL '24 hours'",
            tenant_id,
        )

        revenue = await conn.fetchval(
            "SELECT SUM(billing_amount) FROM appointments "
            "WHERE tenant_id = $1 AND status = 'completed' "
            "AND payment_status = 'paid' "
            "AND completed_at >= NOW() - INTERVAL '24 hours'",
            tenant_id,
        )

    return {
        "turnos_creados": created or 0,
        "turnos_completados": completed or 0,
        "cancelaciones": cancelled or 0,
        "cancel_reasons": ", ".join(cancel_reasons),
        "no_shows": no_shows or 0,
        "derivaciones": derivations or 0,
        "nuevos_pacientes": new_patients or 0,
        "facturacion": float(revenue) if revenue else 0,
    }


async def _get_conversation_summary(pool, tenant_id: int) -> str:
    """Fetch last 24h chat messages, format as compact summary."""
    rows = await pool.fetch(
        "SELECT cm.content, cm.role, cc.channel, cc.external_user_id "
        "FROM chat_messages cm "
        "JOIN chat_conversations cc ON cc.id = cm.conversation_id "
        "WHERE cm.tenant_id = $1 "
        "AND cm.created_at >= NOW() - INTERVAL '24 hours' "
        "ORDER BY cm.created_at DESC "
        "LIMIT 100",
        tenant_id,
    )

    if not rows:
        return "Sin conversaciones en las ultimas 24 horas."

    lines = []
    for row in rows:
        role = row["role"] or "unknown"
        content = (row["content"] or "")[:80]
        prefix_map = {"user": "USER", "assistant": "AGENT", "tool": "TOOL"}
        prefix = prefix_map.get(role, role.upper())
        lines.append(f"{prefix}: {content}")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# GPT call
# ---------------------------------------------------------------------------


def _validate_model(model: str) -> tuple[str, bool]:
    """Validate model name and check JSON mode support.
    Returns (validated_model, supports_json_mode).
    """
    try:
        from dashboard.token_tracker import MODEL_PRICING

        if model not in MODEL_PRICING:
            logger.warning(
                f"nova_analysis: model '{model}' not in MODEL_PRICING, falling back to gpt-4o-mini"
            )
            return "gpt-4o-mini", True
        info = MODEL_PRICING[model]
        # Assume OpenAI text models support JSON mode
        supports_json = info.get("provider") == "openai" and info.get("type") == "text"
        return model, supports_json
    except Exception as e:
        logger.warning(
            f"nova_analysis: model validation error: {e}, falling back to gpt-4o-mini"
        )
        return "gpt-4o-mini", True


async def _analyze_with_gpt(
    prompt: str, api_key: str, tenant_id: int = 0
) -> dict | None:
    """Call GPT for analysis — model configurable from dashboard."""
    if not api_key:
        logger.warning("nova_analysis: OPENAI_API_KEY not set, skipping")
        return None

    # Read model from config (fallback: gpt-4o-mini)
    analysis_model = "gpt-4o-mini"
    if tenant_id:
        try:
            from db import db

            row = await db.pool.fetchrow(
                "SELECT value FROM system_config WHERE key = 'MODEL_INSIGHTS' AND tenant_id = $1",
                tenant_id,
            )
            if row and row.get("value"):
                analysis_model = str(row["value"]).strip()
        except Exception:
            pass

    # Validate model and JSON mode compatibility
    validated_model, supports_json = _validate_model(analysis_model)
    if validated_model != analysis_model:
        logger.warning(
            f"nova_analysis: tenant {tenant_id} configured model '{analysis_model}' invalid or unsupported, "
            f"falling back to '{validated_model}'"
        )
    logger.info(
        f"nova_analysis: tenant {tenant_id} using model '{validated_model}' "
        f"(JSON mode {'enabled' if supports_json else 'disabled'})"
    )

    request_json = {
        "model": validated_model,
        "messages": [
            {
                "role": "system",
                "content": "You are a clinical data analyst. Always respond in valid JSON.",
            },
            {"role": "user", "content": prompt},
        ],
        "temperature": 0,
        "max_tokens": 700,
    }
    if supports_json:
        request_json["response_format"] = {"type": "json_object"}

    max_attempts = 2
    for attempt in range(max_attempts):
        # On second attempt, disable JSON mode
        if attempt == 1:
            if "response_format" in request_json:
                del request_json["response_format"]
                logger.warning(
                    f"nova_analysis: tenant {tenant_id} retrying without JSON mode due to previous error"
                )
            else:
                # Already without JSON mode, no point retrying
                break

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.post(
                    "https://api.openai.com/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json",
                    },
                    json=request_json,
                )
                response.raise_for_status()
                data = response.json()
                content = data["choices"][0]["message"]["content"]
                # Track token usage
                usage = data.get("usage", {})
                if usage:
                    try:
                        from dashboard.token_tracker import track_service_usage
                        from db import db

                        await track_service_usage(
                            db.pool,
                            tenant_id,
                            validated_model,
                            usage.get("prompt_tokens", 0),
                            usage.get("completion_tokens", 0),
                            source="nova_daily_analysis",
                        )
                    except Exception:
                        pass
                return json.loads(content)
        except httpx.HTTPStatusError as e:
            # Log full HTTP response details for debugging
            error_detail = f"HTTP {e.response.status_code}: {e.response.text}"
            logger.error(
                f"nova_analysis_gpt_http_error tenant {tenant_id} attempt {attempt + 1}: {error_detail}"
            )
            # Check if this is a JSON mode incompatibility error
            if e.response.status_code == 400:
                try:
                    error_body = e.response.json()
                    error_msg = str(error_body).lower()
                    if any(
                        keyword in error_msg
                        for keyword in [
                            "json",
                            "response_format",
                            "unsupported",
                            "invalid parameter",
                        ]
                    ):
                        # Likely JSON mode issue, will retry without JSON mode on next attempt
                        continue
                except Exception:
                    pass
            # For other errors, break loop and fail
            break
        except Exception as e:
            logger.error(f"nova_analysis_gpt_error tenant {tenant_id}: {e}")
            break

    # If we exit loop without returning, analysis failed
    logger.error(
        f"nova_analysis_gpt_failed tenant {tenant_id} after {max_attempts} attempts"
    )
    return None
