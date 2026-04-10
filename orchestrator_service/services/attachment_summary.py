"""
attachment_summary.py — LLM summary generation for multiple attachments.

Generates concise summaries from Vision API analyses of multiple attachments
(payment receipts, clinical documents) and stores them in the database.

Rules:
- Max 500 characters per summary (LLM limit)
- Fallback to simple count if LLM fails
- Save to clinical_record_summaries (upsert by tenant+patient+conversation)
- Update first attachment's source_details.llm_summary
"""

import asyncio
import json
import logging
import os
from typing import Dict, List, Optional, Tuple

from openai import AsyncOpenAI

logger = logging.getLogger(__name__)


async def _get_model_from_db(pool, tenant_id: int) -> str:
    """
    Read OPENAI_MODEL from system_config for the tenant.
    Falls back to 'gpt-4o-mini' if not configured.
    """
    model = "gpt-4o-mini"
    try:
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT value FROM system_config WHERE tenant_id=$1 AND key='OPENAI_MODEL'",
                tenant_id,
            )
        if row and row.get("value"):
            model = str(row["value"]).strip() or model
    except Exception as model_err:
        logger.warning(
            "_get_model_from_db: could not read model from system_config: %s",
            model_err,
        )
    return model


# =============================================================================
# LLM SUMMARY GENERATION
# =============================================================================

_BASE_SYSTEM_PROMPT = """Sos un asistente que genera resúmenes breves de documentos médicos y comprobantes de pago.

OBLIGATORIO:
- El resumen debe ser conciso, máximo 500 caracteres.
- Usá lenguaje formal pero claro.
- Solo usá la información de los análisis proporcionados (no inventes nada).
- Incluí: cantidad total de archivos, tipos detectados (pago vs clínico), descripción breve.
- Si hay montos mencionados en los comprobantes, incluilos.
- Si hay diagnósticos o medicamentos en documentos clínicos, resumilos brevemente.
- No incluyas detalles irrelevantes.

Formato esperado:
"Se recibieron X archivos: Y comprobantes de pago (montos si hay) y Z documentos clínicos (descripción breve)."
"""


async def generate_attachment_summary(analyses: List[Dict], patient_name: str) -> str:
    """
    Generate a concise LLM summary from multiple Vision analyses.

    Args:
        analyses: List of dicts with keys:
            - vision_description: str (Vision API output)
            - document_type: str ('payment_receipt' or 'clinical')
            - index: int
        patient_name: Patient's full name for context

    Returns:
        Summary string (max 500 chars). If LLM fails, returns fallback summary.
    """
    logger.info(
        "generate_attachment_summary start | patient=%s analyses=%d",
        patient_name,
        len(analyses),
    )

    if not analyses:
        return "No hay archivos para resumir."

    # Build user prompt
    analyses_text = []
    for a in analyses:
        analyses_text.append(
            f"[Archivo {a.get('index', 0)} - {a.get('document_type', 'unknown')}]: "
            f"{a.get('vision_description', 'Sin descripción')}"
        )

    user_prompt = f"""Paciente: {patient_name}

Análisis de Vision API por archivo:
{chr(10).join(analyses_text)}

Generá un resumen breve (máximo 500 caracteres) en español.
"""

    client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    try:
        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": _BASE_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.3,
            max_completion_tokens=200,
        )
        summary = response.choices[0].message.content.strip()
        logger.info(
            "generate_attachment_summary success | patient=%s chars=%d",
            patient_name,
            len(summary),
        )

        # Track token usage
        try:
            usage = response.usage
            if usage:
                from dashboard.token_tracker import track_service_usage
                from db import db as _db
                from main import current_tenant_id
                _tid = current_tenant_id.get() or 1
                await track_service_usage(_db.pool, _tid, "gpt-4o-mini", usage.prompt_tokens, usage.completion_tokens, source="attachment_summary", phone="system")
        except Exception:
            pass

        return summary[:500]  # Hard limit
    except Exception as e:
        logger.error(
            "generate_attachment_summary: LLM call failed: %s", e, exc_info=True
        )
        # Fallback: simple count
        payment_count = sum(
            1 for a in analyses if a.get("document_type") == "payment_receipt"
        )
        clinical_count = sum(
            1 for a in analyses if a.get("document_type") == "clinical"
        )
        if payment_count > 0 and clinical_count > 0:
            return f"Se recibieron {len(analyses)} archivos: {payment_count} comprobantes de pago y {clinical_count} documentos clínicos."
        elif payment_count > 0:
            return f"Se recibieron {payment_count} comprobantes de pago."
        elif clinical_count > 0:
            return f"Se recibieron {clinical_count} documentos clínicos."
        else:
            return f"Se recibieron {len(analyses)} archivos. Resumen no disponible."


# =============================================================================
# DATABASE PERSISTENCE
# =============================================================================


async def save_summary_to_db(
    pool,
    tenant_id: int,
    patient_id: int,
    conversation_id: Optional[str],
    summary_text: str,
    analyses: List[Dict],
    first_document_id: Optional[int] = None,
) -> Tuple[bool, Optional[int]]:
    """
    Save LLM summary to clinical_record_summaries (upsert) and optionally
    update the first attachment's source_details.

    Args:
        pool: asyncpg pool
        tenant_id: Tenant ID
        patient_id: Patient ID
        conversation_id: WhatsApp conversation ID (optional)
        summary_text: Generated summary
        analyses: Original analyses list (for counts/types)
        first_document_id: If provided, update its source_details.llm_summary

    Returns:
        (success: bool, summary_id: Optional[int])
    """
    # Compute counts and types
    attachments_count = len(analyses)
    attachments_types = []
    for a in analyses:
        doc_type = a.get("document_type")
        if doc_type == "payment_receipt":
            attachments_types.append("payment")
        elif doc_type == "clinical":
            attachments_types.append("clinical")
        else:
            attachments_types.append("unknown")

    try:
        async with pool.acquire() as conn:
            # Upsert into clinical_record_summaries
            row = await conn.fetchrow(
                """
                INSERT INTO clinical_record_summaries
                    (tenant_id, patient_id, conversation_id,
                     summary_text, attachments_count, attachments_types)
                VALUES ($1, $2, $3, $4, $5, $6::jsonb)
                ON CONFLICT (tenant_id, patient_id, conversation_id)
                DO UPDATE SET
                    summary_text = EXCLUDED.summary_text,
                    attachments_count = EXCLUDED.attachments_count,
                    attachments_types = EXCLUDED.attachments_types,
                    created_at = NOW()
                RETURNING id
            """,
                tenant_id,
                patient_id,
                conversation_id,
                summary_text,
                attachments_count,
                json.dumps(attachments_types),
            )

            summary_id = row["id"] if row else None

            # Update first attachment's source_details.llm_summary if document_id provided
            if first_document_id is not None:
                await conn.execute(
                    """
                    UPDATE patient_documents
                    SET source_details = jsonb_set(
                        COALESCE(source_details, '{}'::jsonb),
                        '{llm_summary}',
                        $1::jsonb
                    )
                    WHERE id = $2 AND tenant_id = $3
                """,
                    json.dumps(summary_text),
                    first_document_id,
                    tenant_id,
                )

            logger.info(
                "save_summary_to_db success | tenant=%d patient=%d summary_id=%d",
                tenant_id,
                patient_id,
                summary_id,
            )
            return True, summary_id

    except Exception as e:
        logger.error(
            "save_summary_to_db failed: %s | tenant=%d patient=%d",
            e,
            tenant_id,
            patient_id,
            exc_info=True,
        )
        return False, None


# =============================================================================
# HIGH-LEVEL ORCHESTRATION
# =============================================================================


async def generate_and_save_summary(
    pool,
    tenant_id: int,
    patient_id: int,
    patient_name: str,
    analyses: List[Dict],
    conversation_id: Optional[str] = None,
    first_document_id: Optional[int] = None,
) -> Tuple[bool, Optional[int], str]:
    """
    Orchestrates LLM summary generation and database persistence.

    Args:
        pool: asyncpg pool
        tenant_id, patient_id, patient_name: Context
        analyses: List of analysis dicts
        conversation_id: Optional conversation ID for upsert
        first_document_id: Optional ID of first attachment to update

    Returns:
        (success: bool, summary_id: Optional[int], summary_text: str)
    """
    # 1. Generate LLM summary
    summary_text = await generate_attachment_summary(analyses, patient_name)

    # 2. Save to DB
    success, summary_id = await save_summary_to_db(
        pool=pool,
        tenant_id=tenant_id,
        patient_id=patient_id,
        conversation_id=conversation_id,
        summary_text=summary_text,
        analyses=analyses,
        first_document_id=first_document_id,
    )

    return success, summary_id, summary_text
