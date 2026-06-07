"""
Digital Patient Records — API routes.
Generates AI-powered clinical documents from structured patient data.
"""
import os
import json
import uuid
import logging
from datetime import datetime
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from core.auth import verify_admin_token, get_resolved_tenant_id
from core.credentials import get_tenant_credential, YCLOUD_API_KEY
from core.security_utils import generate_signed_url
from db import db
from urllib.parse import urlencode

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Digital Records"])


# ---------------------------------------------------------------------------
# Pydantic Models
# ---------------------------------------------------------------------------

class GenerateRecordRequest(BaseModel):
    template_type: str = Field(
        ...,
        pattern="^(clinical_report|post_surgery|odontogram_art|authorization_request)$",
    )
    professional_id: Optional[int] = None


class UpdateRecordRequest(BaseModel):
    html_content: str


class RegenerateSectionRequest(BaseModel):
    section_id: str


class SendEmailRequest(BaseModel):
    to_email: str


class SendWhatsAppRequest(BaseModel):
    message: Optional[str] = None  # custom caption for the WhatsApp document


class DigitalRecordResponse(BaseModel):
    id: str
    template_type: str
    title: str
    html_content: str
    status: str
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    generation_warnings: List[str] = []


class DigitalRecordListItem(BaseModel):
    id: str
    template_type: str
    title: str
    status: str
    created_at: Optional[str] = None
    sent_to_email: Optional[str] = None
    sent_at: Optional[str] = None


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get(
    "/patients/{patient_id}/digital-records",
    dependencies=[Depends(verify_admin_token)],
    summary="Listar fichas digitales del paciente",
)
async def list_digital_records(
    patient_id: int,
    tenant_id: int = Depends(get_resolved_tenant_id),
):
    """List all digital records for a patient. Tenant-isolated."""
    rows = await db.pool.fetch(
        """SELECT id, template_type, title, status, created_at, updated_at, sent_to_email, sent_at,
                  sent_to_whatsapp, sent_via_whatsapp_at
           FROM patient_digital_records
           WHERE patient_id = $1 AND tenant_id = $2
           ORDER BY created_at DESC""",
        patient_id,
        tenant_id,
    )
    return [
        {
            "id": str(r["id"]),
            "template_type": r["template_type"],
            "title": r["title"],
            "status": r["status"],
            "created_at": r["created_at"].isoformat() if r["created_at"] else None,
            "updated_at": r["updated_at"].isoformat() if r["updated_at"] else None,
            "sent_to_email": r["sent_to_email"],
            "sent_at": r["sent_at"].isoformat() if r["sent_at"] else None,
            "sent_to_whatsapp": r["sent_to_whatsapp"],
            "sent_via_whatsapp_at": r["sent_via_whatsapp_at"].isoformat() if r["sent_via_whatsapp_at"] else None,
        }
        for r in rows
    ]


@router.get(
    "/patients/{patient_id}/digital-records/{record_id}",
    dependencies=[Depends(verify_admin_token)],
    summary="Obtener ficha digital completa",
)
async def get_digital_record(
    patient_id: int,
    record_id: str,
    tenant_id: int = Depends(get_resolved_tenant_id),
):
    """Get a single digital record with full HTML content."""
    row = await db.pool.fetchrow(
        """SELECT id, template_type, title, html_content, status, source_data,
                  generation_metadata, created_at, updated_at, sent_to_email, sent_at,
                  sent_to_whatsapp, sent_via_whatsapp_at
           FROM patient_digital_records
           WHERE id = $1 AND patient_id = $2 AND tenant_id = $3""",
        record_id,
        patient_id,
        tenant_id,
    )
    if not row:
        raise HTTPException(status_code=404, detail="Ficha digital no encontrada")

    metadata = row["generation_metadata"] or {}
    if isinstance(metadata, str):
        metadata = json.loads(metadata)
    warnings = metadata.get("validation_warnings", [])

    return {
        "id": str(row["id"]),
        "template_type": row["template_type"],
        "title": row["title"],
        "html_content": row["html_content"],
        "status": row["status"],
        "source_data": row["source_data"],
        "created_at": row["created_at"].isoformat() if row["created_at"] else None,
        "updated_at": row["updated_at"].isoformat() if row["updated_at"] else None,
        "sent_to_email": row["sent_to_email"],
        "sent_at": row["sent_at"].isoformat() if row["sent_at"] else None,
        "sent_to_whatsapp": row["sent_to_whatsapp"],
        "sent_via_whatsapp_at": row["sent_via_whatsapp_at"].isoformat() if row["sent_via_whatsapp_at"] else None,
        "generation_warnings": warnings,
    }


@router.post(
    "/patients/{patient_id}/digital-records/generate",
    dependencies=[Depends(verify_admin_token)],
    summary="Generar ficha digital con IA",
)
async def generate_digital_record(
    patient_id: int,
    body: GenerateRecordRequest,
    tenant_id: int = Depends(get_resolved_tenant_id),
):
    """Generate a new digital record using AI. 3-layer pipeline: gather → narrative → assemble."""
    from services.digital_records_service import (
        gather_patient_data,
        generate_narrative,
        assemble_html,
    )
    from services.odontogram_svg import render_odontogram_svg

    # Layer 1: Gather structured data
    source_data = await gather_patient_data(
        db.pool, patient_id, tenant_id, body.template_type, body.professional_id
    )

    # Layer 2: AI narrative generation
    narrative_result = await generate_narrative(
        db.pool, tenant_id, body.template_type, source_data
    )
    ai_sections = narrative_result.get("sections", {})
    warnings = narrative_result.get("warnings", [])
    model_used = narrative_result.get("model_used", "unknown")

    # Odontogram SVG (empty dict fallback if no odontogram data)
    odontogram_svg = render_odontogram_svg(source_data.get("odontogram", {}))

    # Layer 3: Assemble final HTML
    html_content = assemble_html(body.template_type, source_data, ai_sections, odontogram_svg)

    # Build human-readable title
    template_titles = {
        "clinical_report": "Informe Clínico",
        "post_surgery": "Informe Post-Quirúrgico",
        "odontogram_art": "Evaluación Odontológica",
        "authorization_request": "Solicitud de Autorización",
    }
    patient_name = source_data.get("patient", {}).get("full_name", "Paciente")
    title = f"{template_titles.get(body.template_type, 'Documento')} — {patient_name}"

    # Insert record (always starts as draft)
    record_id = str(uuid.uuid4())
    await db.pool.execute(
        """INSERT INTO patient_digital_records
           (id, tenant_id, patient_id, professional_id, template_type, title, html_content,
            source_data, generation_metadata, status, created_at, updated_at)
           VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, NOW(), NOW())""",
        record_id,
        tenant_id,
        patient_id,
        body.professional_id,
        body.template_type,
        title,
        html_content,
        json.dumps(source_data, default=str),
        json.dumps(
            {
                "model_used": model_used,
                "validation_warnings": warnings,
                "ai_sections_keys": list(ai_sections.keys()),
            }
        ),
        "draft",
    )

    return {
        "id": record_id,
        "template_type": body.template_type,
        "title": title,
        "html_content": html_content,
        "status": "draft",
        "generation_warnings": warnings,
        "created_at": datetime.utcnow().isoformat(),
    }


@router.patch(
    "/patients/{patient_id}/digital-records/{record_id}",
    dependencies=[Depends(verify_admin_token)],
    summary="Editar contenido HTML de la ficha",
)
async def update_digital_record(
    patient_id: int,
    record_id: str,
    body: UpdateRecordRequest,
    tenant_id: int = Depends(get_resolved_tenant_id),
):
    """Update HTML content. Invalidates cached PDF."""
    result = await db.pool.execute(
        """UPDATE patient_digital_records
           SET html_content = $1, pdf_path = NULL, pdf_generated_at = NULL, updated_at = NOW()
           WHERE id = $2 AND patient_id = $3 AND tenant_id = $4""",
        body.html_content,
        record_id,
        patient_id,
        tenant_id,
    )
    if result == "UPDATE 0":
        raise HTTPException(status_code=404, detail="Ficha digital no encontrada")
    return {"success": True, "message": "Ficha actualizada. PDF invalidado."}


@router.post(
    "/patients/{patient_id}/digital-records/{record_id}/regenerate-section",
    dependencies=[Depends(verify_admin_token)],
    summary="Regenerar una sección con IA",
)
async def regenerate_section(
    patient_id: int,
    record_id: str,
    body: RegenerateSectionRequest,
    tenant_id: int = Depends(get_resolved_tenant_id),
):
    """Regenerate a single section of a digital record using AI."""
    from services.digital_records_service import generate_narrative, replace_section

    row = await db.pool.fetchrow(
        """SELECT html_content, source_data, template_type
           FROM patient_digital_records
           WHERE id = $1 AND patient_id = $2 AND tenant_id = $3""",
        record_id,
        patient_id,
        tenant_id,
    )
    if not row:
        raise HTTPException(status_code=404, detail="Ficha digital no encontrada")

    source_data = row["source_data"]
    if isinstance(source_data, str):
        source_data = json.loads(source_data)

    # Regenerate only the requested section
    narrative_result = await generate_narrative(
        db.pool, tenant_id, row["template_type"], source_data
    )
    ai_sections = narrative_result.get("sections", {})

    if body.section_id not in ai_sections:
        raise HTTPException(
            status_code=400,
            detail=f"Sección '{body.section_id}' no encontrada en respuesta AI",
        )

    new_content = ai_sections[body.section_id]
    updated_html = replace_section(row["html_content"], body.section_id, new_content)

    await db.pool.execute(
        """UPDATE patient_digital_records
           SET html_content = $1, pdf_path = NULL, pdf_generated_at = NULL, updated_at = NOW()
           WHERE id = $2 AND tenant_id = $3""",
        updated_html,
        record_id,
        tenant_id,
    )

    return {
        "success": True,
        "html_content": updated_html,
        "regenerated_section": body.section_id,
    }


@router.get(
    "/patients/{patient_id}/digital-records/{record_id}/pdf",
    dependencies=[Depends(verify_admin_token)],
    summary="Descargar PDF de la ficha digital",
)
async def download_pdf(
    patient_id: int,
    record_id: str,
    tenant_id: int = Depends(get_resolved_tenant_id),
):
    """Download PDF. Lazy-generates if cache is invalidated."""
    from services.digital_records_service import generate_pdf

    row = await db.pool.fetchrow(
        """SELECT html_content, pdf_path, title
           FROM patient_digital_records
           WHERE id = $1 AND patient_id = $2 AND tenant_id = $3""",
        record_id,
        patient_id,
        tenant_id,
    )
    if not row:
        raise HTTPException(status_code=404, detail="Ficha digital no encontrada")

    pdf_path = row["pdf_path"]

    # Lazy PDF generation when cache is invalidated or missing
    if not pdf_path or not os.path.exists(pdf_path):
        output_dir = f"/app/uploads/digital_records/{tenant_id}"
        os.makedirs(output_dir, exist_ok=True)
        pdf_path = f"{output_dir}/{record_id}.pdf"
        await generate_pdf(row["html_content"], pdf_path)
        await db.pool.execute(
            """UPDATE patient_digital_records
               SET pdf_path = $1, pdf_generated_at = NOW()
               WHERE id = $2 AND tenant_id = $3""",
            pdf_path,
            record_id,
            tenant_id,
        )

    safe_title = (row["title"] or "documento").replace(" ", "_").replace("/", "-")
    return FileResponse(
        pdf_path,
        media_type="application/pdf",
        filename=f"{safe_title}.pdf",
    )


@router.post(
    "/patients/{patient_id}/digital-records/{record_id}/email",
    dependencies=[Depends(verify_admin_token)],
    summary="Enviar ficha por email con PDF adjunto",
)
async def send_record_email(
    patient_id: int,
    record_id: str,
    body: SendEmailRequest,
    tenant_id: int = Depends(get_resolved_tenant_id),
):
    """Send digital record as PDF attachment via email."""
    from services.digital_records_service import generate_pdf
    from email_service import email_service

    row = await db.pool.fetchrow(
        """SELECT html_content, pdf_path, title, status
           FROM patient_digital_records
           WHERE id = $1 AND patient_id = $2 AND tenant_id = $3""",
        record_id,
        patient_id,
        tenant_id,
    )
    if not row:
        raise HTTPException(status_code=404, detail="Ficha digital no encontrada")

    # Ensure PDF exists (lazy generation)
    pdf_path = row["pdf_path"]
    if not pdf_path or not os.path.exists(pdf_path):
        output_dir = f"/app/uploads/digital_records/{tenant_id}"
        os.makedirs(output_dir, exist_ok=True)
        pdf_path = f"{output_dir}/{record_id}.pdf"
        await generate_pdf(row["html_content"], pdf_path)
        await db.pool.execute(
            "UPDATE patient_digital_records SET pdf_path = $1, pdf_generated_at = NOW() WHERE id = $2 AND tenant_id = $3",
            pdf_path,
            record_id,
            tenant_id,
        )

    # Send email with PDF attachment (run in thread to avoid blocking event loop)
    import asyncio
    try:
        await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: email_service.send_digital_record_email(
                to_email=body.to_email,
                pdf_path=pdf_path,
                patient_name=row["title"],
                document_title=row["title"],
            ),
        )
    except Exception as e:
        logger.error(f"Error sending digital record email: {e}")
        raise HTTPException(status_code=500, detail=f"Error al enviar email: {str(e)}")

    # Mark as sent
    await db.pool.execute(
        """UPDATE patient_digital_records
           SET sent_to_email = $1, sent_at = NOW(), status = 'sent', updated_at = NOW()
           WHERE id = $2 AND tenant_id = $3""",
        body.to_email,
        record_id,
        tenant_id,
    )

    return {"success": True, "message": f"Ficha enviada a {body.to_email}"}


@router.post(
    "/patients/{patient_id}/digital-records/{record_id}/whatsapp",
    dependencies=[Depends(verify_admin_token)],
    summary="Enviar ficha digital por WhatsApp con PDF adjunto",
)
async def send_record_whatsapp(
    patient_id: int,
    record_id: str,
    body: SendWhatsAppRequest,
    request: Request,
    tenant_id: int = Depends(get_resolved_tenant_id),
):
    """Envía una ficha digital al WhatsApp del paciente con el PDF adjunto.

    Patrón espejo de send_treatment_plan_whatsapp (admin_routes.py:15262):
    1. Carga registro + paciente.
    2. Asegura PDF (lazy-generate si no existe o se invalidó).
    3. Normaliza teléfono a E.164.
    4. Credenciales YCloud.
    5. Sube PDF a YCloud Media API + send_document_by_media_id.
    6. Fallback a send_document con URL firmada si la subida falla.
    7. Registra en chat_conversations + chat_messages.
    8. Marca sent_to_whatsapp / sent_via_whatsapp_at.
    """
    from services.digital_records_service import generate_pdf
    from ycloud_client import YCloudClient, normalize_phone_e164

    # 1. Cargar registro
    row = await db.pool.fetchrow(
        """SELECT id, html_content, pdf_path, title
           FROM patient_digital_records
           WHERE id = $1 AND patient_id = $2 AND tenant_id = $3""",
        record_id,
        patient_id,
        tenant_id,
    )
    if not row:
        raise HTTPException(status_code=404, detail="Ficha digital no encontrada")

    # 2. Asegurar PDF
    pdf_path = row["pdf_path"]
    if not pdf_path or not os.path.exists(pdf_path):
        output_dir = f"/app/uploads/digital_records/{tenant_id}"
        os.makedirs(output_dir, exist_ok=True)
        pdf_path = f"{output_dir}/{record_id}.pdf"
        await generate_pdf(row["html_content"], pdf_path)
        await db.pool.execute(
            "UPDATE patient_digital_records SET pdf_path = $1, pdf_generated_at = NOW() WHERE id = $2 AND tenant_id = $3",
            pdf_path,
            record_id,
            tenant_id,
        )

    # 3. Cargar paciente y validar teléfono
    patient = await db.pool.fetchrow(
        "SELECT first_name, last_name, phone_number FROM patients WHERE id = $1 AND tenant_id = $2",
        patient_id,
        tenant_id,
    )
    if not patient or not patient["phone_number"]:
        raise HTTPException(
            status_code=422,
            detail="El paciente no tiene un número de teléfono configurado.",
        )

    phone = patient["phone_number"].strip()
    clean_phone = normalize_phone_e164(phone)
    if len([c for c in clean_phone if c.isdigit()]) < 8:
        raise HTTPException(
            status_code=422,
            detail=f"El número de teléfono del paciente '{phone}' no es válido.",
        )

    # 4. URL firmada (para fallback)
    relative_url = f"/uploads/digital_records/{tenant_id}/{record_id}.pdf"
    signature, expires = generate_signed_url(relative_url, tenant_id)
    query_params = {"signature": signature, "expires": expires}
    api_base = os.getenv("ORCHESTRATOR_PUBLIC_URL", "")
    if not api_base:
        api_base = str(request.base_url).rstrip("/")
    api_base = api_base.rstrip("/")
    signed_pdf_url = f"{api_base}{relative_url}?{urlencode(query_params)}"

    # 5. Credenciales YCloud
    api_key = await get_tenant_credential(tenant_id, YCLOUD_API_KEY)
    if not api_key:
        raise HTTPException(
            status_code=503,
            detail="YCloud credentials not configured",
        )
    from_number = await db.pool.fetchval(
        "SELECT bot_phone_number FROM tenants WHERE id = $1", tenant_id
    )
    if not from_number:
        from_number = await get_tenant_credential(tenant_id, "YCLOUD_WHATSAPP_NUMBER")

    # 6. Enviar por WhatsApp
    yc = YCloudClient(api_key=api_key, business_number=from_number)

    safe_title = (row["title"] or "documento").replace(" ", "_").replace("/", "-")
    filename = f"{safe_title}.pdf"
    patient_name = f"{patient['first_name']} {patient['last_name'] or ''}".strip()
    custom_msg = (body.message or "").strip()
    caption = (
        custom_msg
        if custom_msg
        else f"Hola {patient_name}, te adjuntamos tu ficha digital. ¡Cualquier duda nos avisas!"
    )

    sent_content = f"{caption} (PDF adjunto: {filename})"

    try:
        try:
            media_id = await yc.upload_media(pdf_path, phone_number=from_number)
            await yc.send_document_by_media_id(
                to_number=clean_phone,
                media_id=media_id,
                filename=filename,
                caption=caption,
                from_number=from_number,
            )
        except Exception:
            logger.warning("YCloud media upload failed, falling back to signed URL")
            await yc.send_document(
                to_number=clean_phone,
                document_url=signed_pdf_url,
                filename=filename,
                caption=caption,
                from_number=from_number,
            )

        # 7. Registrar en historial de chats
        conv_id = await db.pool.fetchval(
            "SELECT id FROM chat_conversations WHERE external_user_id = $1 AND tenant_id = $2 AND channel = 'whatsapp'",
            clean_phone,
            tenant_id,
        )
        if not conv_id:
            conv_id = uuid.uuid4()
            await db.pool.execute(
                """
                INSERT INTO chat_conversations (id, tenant_id, channel, provider, external_user_id, display_name, status, created_at, updated_at)
                VALUES ($1, $2, 'whatsapp', 'ycloud', $3, $4, 'active', NOW(), NOW())
                """,
                conv_id,
                tenant_id,
                clean_phone,
                patient_name,
            )

        attachments_payload = [{
            "type": "document",
            "url": relative_url,
            "name": filename,
        }]

        await db.pool.execute(
            """
            INSERT INTO chat_messages (tenant_id, conversation_id, role, content, from_number, content_attributes)
            VALUES ($1, $2, 'human_supervisor', $3, $4, $5::jsonb)
            """,
            tenant_id,
            conv_id,
            sent_content,
            clean_phone,
            json.dumps(attachments_payload),
        )

        await db.sync_conversation(
            tenant_id, "whatsapp", clean_phone, sent_content, is_user=False
        )

        # 8. Marcar como enviado por WhatsApp
        await db.pool.execute(
            """UPDATE patient_digital_records
               SET sent_to_whatsapp = $1, sent_via_whatsapp_at = NOW(), status = 'sent', updated_at = NOW()
               WHERE id = $2 AND tenant_id = $3""",
            clean_phone,
            record_id,
            tenant_id,
        )

        return {
            "success": True,
            "message": f"Ficha enviada correctamente a {phone} vía WhatsApp.",
            "signed_url": signed_pdf_url,
            "phone": clean_phone,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error enviando ficha digital por WhatsApp: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Error al enviar mensaje por WhatsApp: {str(e)}",
        )


@router.delete(
    "/patients/{patient_id}/digital-records/{record_id}",
    dependencies=[Depends(verify_admin_token)],
    summary="Eliminar ficha digital",
)
async def delete_digital_record(
    patient_id: int,
    record_id: str,
    tenant_id: int = Depends(get_resolved_tenant_id),
):
    """Delete a digital record and its associated PDF file."""
    row = await db.pool.fetchrow(
        "SELECT pdf_path FROM patient_digital_records WHERE id = $1 AND patient_id = $2 AND tenant_id = $3",
        record_id,
        patient_id,
        tenant_id,
    )
    if not row:
        raise HTTPException(status_code=404, detail="Ficha digital no encontrada")

    # Delete PDF file if it exists on disk
    if row["pdf_path"] and os.path.exists(row["pdf_path"]):
        try:
            os.remove(row["pdf_path"])
        except OSError as e:
            logger.warning(f"Could not delete PDF file {row['pdf_path']}: {e}")

    await db.pool.execute(
        "DELETE FROM patient_digital_records WHERE id = $1 AND tenant_id = $2",
        record_id,
        tenant_id,
    )
    return {"success": True, "message": "Ficha eliminada"}
