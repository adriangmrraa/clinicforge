"""
Webhook Chatwoot & Channels: POST /admin/chatwoot/webhook
CLINICASV1.0 - Unified Channel Normalization (Spec 28)
"""

import json
import logging
import uuid
from typing import Any

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, Request

from core.credentials import resolve_tenant_from_webhook_token
from core.security_utils import generate_signed_url
from db import get_pool, db
from services.channels.service import ChannelService
from services.channels.types import CanonicalMessage, MediaType

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/admin/chatwoot/webhook")
async def receive_chatwoot_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    access_token: str = Query(..., alias="access_token"),
):
    """
    Endpoint unificado de Webhooks.
    Soporta Chatwoot (nativo) y YCloud (si se configura este endpoint por error o legado).
    """
    tenant_id = await resolve_tenant_from_webhook_token(access_token)
    if not tenant_id:
        raise HTTPException(status_code=403, detail="Invalid Access Token")

    try:
        payload = await request.json()
    except Exception:
        return {"status": "ignored", "reason": "invalid_json"}

    # 1. Detectar Provider (Backward Compatibility)
    provider = "chatwoot"
    # YCloud payloads have "type": "message" or "image", Chatwoot has "event"
    if payload.get("type") and payload.get("message") and not payload.get("event"):
        provider = "ycloud"
        logger.info(
            f"⚠️ YCloud payload received on Chatwoot endpoint. Tenant: {tenant_id}"
        )

    # 2. Normalizar Payload
    try:
        messages = await ChannelService.normalize_webhook(provider, payload, tenant_id)
    except Exception as e:
        logger.exception(f"❌ Error normalizing webhook: {e}")
        return {"status": "error", "reason": str(e)}

    if not messages:
        return {
            "status": "ignored",
            "reason": "no_relevant_messages",
            "provider": provider,
        }

    # 2. Bucle de Procesamiento Canonizado
    # Usamos la función compartida para garantizar paridad y reducir duplicación
    # FIX: Pass the detected 'provider' variable instead of hardcoded "chatwoot"
    return await _process_canonical_messages(
        messages, tenant_id, provider, background_tasks
    )


@router.post("/admin/ycloud/webhook")
async def receive_ycloud_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    access_token: str = Query(..., alias="access_token"),
):
    """
    Endpoint dedicado para YCloud.
    """
    # Reutiliza la misma lógica, forzando provider='ycloud'
    # Podríamos refactorizar el body a una función común, pero por ahora llamamos al handler
    # inyectando el provider si fuese necesario, pero el handler ya tiene detección
    # Mejor: Copiar la lógica de llamada es más limpio para evitar recursión HTTP

    tenant_id = await resolve_tenant_from_webhook_token(access_token)
    if not tenant_id:
        raise HTTPException(status_code=403, detail="Invalid Access Token")

    try:
        payload = await request.json()
        logger.info(f"YCLOUD_RAW_PAYLOAD: {json.dumps(payload)}")
    except Exception:
        return {"status": "ignored", "reason": "invalid_json"}

    # Force YCloud normalization
    try:
        messages = await ChannelService.normalize_webhook("ycloud", payload, tenant_id)
    except Exception as e:
        logger.exception(f"❌ Error normalizing YCloud webhook: {e}")
        return {"status": "error", "reason": str(e)}

    # ... repetimos lógica de DB ...
    # Para no duplicar código en este paso (Hotfix/Stabilization), voy a invocar una función shared
    # Defino la función shared abajo y actualizo ambas rutas para usarla.
    return await _process_canonical_messages(
        messages, tenant_id, "ycloud", background_tasks
    )


async def _process_canonical_messages(messages, tenant_id, provider, background_tasks):
    pool = get_pool()
    saved_ids = []

    if not messages:
        return {"status": "ignored", "reason": "no_content"}

    for msg in messages:
        # Track whether we acquired the inbound idempotency lock for this message
        # so we can mark it done on success or release it on failure (avoiding
        # the silent message-loss bug where a partially-processed inbound row
        # blocks all future retries).
        _idem_locked_id: Any = None
        _idem_processed_ok = False
        try:
            # ============================================================
            # HTTP-LEVEL IDEMPOTENCY (Chatwoot retry fix)
            # ------------------------------------------------------------
            # Chatwoot retries the webhook if our handler takes >5s to
            # respond. The retry comes with the SAME provider message_id.
            # We use the inbound_messages UNIQUE(provider, provider_message_id)
            # constraint to atomically reject the duplicate at the very start
            # of the loop, BEFORE doing any DB writes, normalization, or
            # buffer enqueuing. This is the FIRST line of defense against
            # double-replies on IG/FB via Chatwoot.
            #
            # Recovery: if the row is inserted but downstream processing
            # fails, the except clause at the bottom DELETES the inbound row
            # so the next retry gets a clean slate (no silent message loss).
            # ============================================================
            _idem_ext_id = None
            try:
                if provider == "ycloud":
                    _inbound = (msg.raw_payload or {}).get("whatsappInboundMessage", {})
                    _idem_ext_id = (
                        _inbound.get("wamid")
                        or _inbound.get("id")
                        or (msg.raw_payload or {}).get("id")
                    )
                else:
                    _idem_ext_id = (msg.raw_payload or {}).get("id")
            except Exception:
                _idem_ext_id = None

            if _idem_ext_id:
                try:
                    inserted = await db.try_insert_inbound(
                        provider=provider,
                        provider_message_id=str(_idem_ext_id),
                        event_id=str((msg.raw_payload or {}).get("event") or ""),
                        from_number=msg.external_user_id or "",
                        payload=msg.raw_payload or {},
                        correlation_id=str(uuid.uuid4()),
                    )
                    if not inserted:
                        logger.info(
                            f"♻️ Webhook duplicate suppressed at HTTP layer: provider={provider} msg_id={_idem_ext_id} from={msg.external_user_id}"
                        )
                        continue
                    # Lock acquired — track it so the except clause can release it on failure.
                    _idem_locked_id = str(_idem_ext_id)
                except Exception as _idem_err:
                    # Best-effort: if the dedupe table is unavailable, fall through
                    # to the rest of the existing dedup logic so we never DROP a real message.
                    logger.warning(
                        f"⚠️ try_insert_inbound failed (non-blocking): {_idem_err}"
                    )

            # Spec 34: Intentar extraer IDs si vienen en el crudo (para Chatwoot)
            cw_acc_id = None
            cw_conv_id = None
            if msg.raw_payload:
                cw_acc_id = msg.raw_payload.get("account", {}).get("id")
                cw_conv_id = msg.raw_payload.get("conversation", {}).get("id")

            # Fix Chat Name Persistence: Only update name/avatar if not an agent (Spec 34)
            # If msg.is_agent is True, we pass None so DB keeps existing value (COALESCE)
            # or inserts NULL (favors external_user_id) instead of "Adrian Gamarra"
            safe_display_name = msg.display_name if not msg.is_agent else None
            safe_avatar_url = (
                (msg.sender.get("avatar") if msg.sender else None)
                if not msg.is_agent
                else None
            )

            conv_id = await db.get_or_create_conversation(
                tenant_id=tenant_id,
                channel=msg.original_channel,
                external_user_id=msg.external_user_id,
                display_name=safe_display_name,
                external_chatwoot_id=cw_conv_id,
                external_account_id=cw_acc_id,
                avatar_url=safe_avatar_url,
                provider=provider,
            )

            # --- Lead Attribution Logic (Meta Ads) - Spec 05 ---
            if msg.referral:
                try:
                    patient_row = await db.ensure_patient_exists(
                        phone_number=msg.external_user_id,
                        tenant_id=tenant_id,
                        first_name=msg.display_name or "Visitante",
                    )

                    # --- Spec 34: NEW_PATIENT Notification (V7.6) ---
                    # Si el paciente fue creado recientemente (detectado por created_at vs NOW)
                    # o si no tenía acquisition_source previo.
                    if patient_row:
                        # Consideramos "nuevo" si fue creado en los últimos 30 segundos
                        # o si el flag 'is_new' estuviera disponible (db.py no lo devuelve explícitamente pero created_at sí)
                        from datetime import datetime, timezone, timedelta

                        created_at = patient_row.get("created_at")
                        is_new = False
                        if created_at:
                            if created_at.tzinfo is None:
                                created_at = created_at.replace(tzinfo=timezone.utc)
                            if datetime.now(timezone.utc) - created_at < timedelta(
                                seconds=30
                            ):
                                is_new = True

                        if is_new:
                            try:
                                from main import app

                                sio = getattr(app.state, "sio", None)
                                to_json_safe = getattr(
                                    app.state, "to_json_safe", lambda x: x
                                )
                                if sio:
                                    await sio.emit(
                                        "NEW_PATIENT",
                                        to_json_safe(
                                            {
                                                "phone_number": msg.external_user_id,
                                                "tenant_id": tenant_id,
                                                "name": msg.display_name
                                                or "Nuevo Paciente",
                                                "channel": msg.original_channel,
                                            }
                                        ),
                                    )
                                    logger.info(
                                        f"📡 Socket NEW_PATIENT emitted for {msg.external_user_id}"
                                    )
                            except Exception as sio_err:
                                logger.error(
                                    f"⚠️ Error emitting NEW_PATIENT SocketIO event: {sio_err}"
                                )

                    if patient_row:
                        ref_ad_id = msg.referral.get("ad_id")
                        if ref_ad_id:
                            # --- ATRIBUCIÓN LAST CLICK ---
                            # Se actualiza siempre con el anuncio más reciente (Spec Mission 3)
                            # Usamos la nueva función completa de atribución
                            try:
                                from db import update_patient_attribution_from_referral

                                await update_patient_attribution_from_referral(
                                    patient_id=patient_row["id"],
                                    tenant_id=tenant_id,
                                    referral=msg.referral,
                                )
                            except Exception as attr_func_err:
                                logger.error(
                                    f"⚠️ Error usando función attribution: {attr_func_err}"
                                )
                                # Fallback a query directa
                                await pool.execute(
                                    """
                                    UPDATE patients SET 
                                        acquisition_source = 'META_ADS',
                                        meta_ad_id = $1,
                                        meta_ad_headline = $2,
                                        meta_ad_body = $3,
                                        updated_at = NOW()
                                    WHERE id = $4 AND tenant_id = $5
                                """,
                                    ref_ad_id,
                                    msg.referral.get("headline"),
                                    msg.referral.get("body"),
                                    patient_row["id"],
                                    tenant_id,
                                )

                            # Enriquecimiento asíncrono
                            try:
                                from services.tasks import enrich_patient_attribution

                                background_tasks.add_task(
                                    enrich_patient_attribution,
                                    patient_id=patient_row["id"],
                                    ad_id=ref_ad_id,
                                    tenant_id=tenant_id,
                                )
                            except:
                                pass
                        else:
                            # --- MARCADO DE TRÁFICO ORGÁNICO ---
                            # Si no tiene fuente y llega por WhatsApp sin referral, es orgánico
                            await pool.execute(
                                """
                                UPDATE patients SET 
                                    acquisition_source = 'ORGANIC',
                                    updated_at = NOW()
                                WHERE id = $1 AND tenant_id = $2 AND acquisition_source IS NULL
                            """,
                                patient_row["id"],
                                tenant_id,
                            )
                except Exception as attr_err:
                    logger.error(f"⚠️ Error in webhook attribution: {attr_err}")

            # Deduplicación robusta (Spec 34)
            # 1. Contenido idéntico reciente (5s)
            # 2. ID de proveedor coincidente (evitar eco de mensajes salientes de la IA)
            # Deduplicación robusta (Spec 34)
            # 1. Contenido idéntico reciente (5s)
            # 2. ID de proveedor coincidente (evitar eco de mensajes salientes de la IA)

            ext_id_candidate = None
            if provider == "ycloud":
                # YCloud: wamid is the unique WhatsApp message ID (best dedup key)
                inbound = msg.raw_payload.get("whatsappInboundMessage", {})
                ext_id_candidate = (
                    inbound.get("wamid")
                    or inbound.get("id")
                    or msg.raw_payload.get("id")
                )
            else:
                # Chatwoot/Default: ID is top-level 'id'
                ext_id_candidate = msg.raw_payload.get("id")

            external_id_check = (
                str(ext_id_candidate) if ext_id_candidate else "NO_MATCH"
            )

            dup = await pool.fetchval(
                """
                SELECT id FROM chat_messages
                WHERE conversation_id = $1
                  AND (
                    (content = $2 AND content IS NOT NULL AND content != '' AND created_at > NOW() - INTERVAL '5 seconds')
                    OR
                    (platform_metadata->>'provider_message_id' = $3 AND $3 != 'NO_MATCH')
                  )
                LIMIT 1
                """,
                conv_id,
                msg.content,
                external_id_check,
            )
            if dup:
                logger.info(f"♻️ Skipping duplicate message in conv {conv_id}")
                continue

            content_attrs = []
            for m_item in msg.media:
                content_attrs.append(
                    {
                        "type": m_item.type.value,
                        "url": m_item.url,
                        "file_name": m_item.file_name,
                        "file_size": m_item.meta.get("file_size"),
                        "mime_type": m_item.mime_type,
                        "transcription": m_item.transcription,
                    }
                )
                logger.info(
                    f"📎 Media item received: type={m_item.type.value}, url={m_item.url[:80] if m_item.url else 'None'}..., file_name={m_item.file_name}, mime={m_item.mime_type}"
                )

            role = "assistant" if msg.is_agent else "user"
            # Copy raw_payload defensively — we're about to mutate it and we
            # don't want to touch the canonical message that other code paths
            # may still reference.
            platform_meta = dict(msg.raw_payload) if msg.raw_payload else {}
            platform_meta["provider"] = provider
            # Inject provider_message_id at a stable key so the partial UNIQUE
            # index `uniq_chat_messages_conv_provider_msg_id` (migration 030)
            # can dedup across both save paths:
            #   1) response_sender.py saves outbound messages directly with
            #      provider_message_id set in platform_metadata.
            #   2) Chatwoot then echoes the same message as `message_created`
            #      (message_type=outgoing) to this webhook. Without this
            #      injection, the echo row had provider_message_id=NULL, the
            #      partial index skipped it, and both rows coexisted — the
            #      root cause of the "duplicate message in UI" bug for
            #      Instagram/Facebook via Chatwoot. The bug was UI-only: the
            #      patient always received the message exactly once because
            #      response_sender calls chatwoot_client.send_text_message
            #      exactly once per bubble.
            if ext_id_candidate:
                platform_meta["provider_message_id"] = str(ext_id_candidate)

            try:
                msg_id = await pool.fetchval(
                    """
                    INSERT INTO chat_messages (
                        tenant_id, conversation_id, role, content, from_number,
                        platform_metadata, content_attributes, created_at
                    )
                    VALUES ($1, $2, $3, $4, $5, $6::jsonb, $7::jsonb, NOW())
                    RETURNING id
                    """,
                    tenant_id,
                    conv_id,
                    role,
                    msg.content
                    or (f"[{msg.media[0].type.value.upper()}]" if msg.media else "[Media]"),
                    msg.external_user_id,
                    json.dumps(platform_meta),
                    json.dumps(content_attrs),
                )
                saved_ids.append(msg_id)
                logger.info(f"✅ Message saved: {msg_id} (Conv: {conv_id})")
            except Exception as _ins_err:
                # Defensive: catches the partial UNIQUE index on
                # (conversation_id, platform_metadata->>'provider_message_id')
                # added by migration 030. If a duplicate slips past the HTTP
                # idempotency layer, the DB rejects it here and we skip the
                # rest of the per-message processing.
                _err_str = str(_ins_err)
                if "uniq_chat_messages_conv_provider_msg_id" in _err_str or "duplicate key" in _err_str:
                    logger.info(
                        f"♻️ chat_messages duplicate suppressed at DB layer: conv={conv_id} ext_id={external_id_check}"
                    )
                    continue
                raise

            # Sincronizar conversación para el preview (Spec 14 / Bug Fix)
            try:
                # ✅ Fase 2: Robust fallback for previews
                content_preview = msg.content or (
                    f"[{msg.media[0].type.value.upper()}]" if msg.media else "[Media]"
                )

                await db.sync_conversation(
                    tenant_id=tenant_id,
                    channel=msg.original_channel,
                    external_user_id=msg.external_user_id,
                    last_message=content_preview,
                    is_user=(not msg.is_agent),
                )
            except Exception as sync_err:
                logger.error(f"⚠️ Error syncing conversation summary: {sync_err}")

            if msg.is_agent:
                await pool.execute(
                    "UPDATE chat_conversations SET human_override_until = NOW() + INTERVAL '24 hours' WHERE id = $1",
                    conv_id,
                )
                continue

            # Tasks
            for m_item in msg.media:
                # Preserve original URL before it gets rewritten to local path
                original_media_url = m_item.url

                if m_item.type == MediaType.AUDIO:
                    try:
                        from services.whisper_service import transcribe_audio_url

                        background_tasks.add_task(
                            transcribe_audio_url,
                            url=original_media_url,
                            tenant_id=tenant_id,
                            conversation_id=str(conv_id),
                            external_user_id=msg.external_user_id,
                        )
                    except:
                        logger.warning("whisper_service not available")
                elif m_item.type == MediaType.IMAGE:
                    try:
                        from services.vision_service import process_vision_task

                        background_tasks.add_task(
                            process_vision_task,
                            message_id=msg_id,
                            image_url=m_item.url,
                            tenant_id=tenant_id,
                        )
                    except:
                        logger.warning("vision_service not available")

                # --- AUTO-GUARDADO EN FICHA MÉDICA Y PERSISTENCIA (Spec 19/22) ---
                # Descargamos imágenes, documentos y AUDIO para persistencia (evitar expiración)
                if (
                    m_item.type
                    in [MediaType.IMAGE, MediaType.DOCUMENT, MediaType.AUDIO]
                    and not msg.is_agent
                ):
                    try:
                        # Descargar el archivo si no es local
                        local_url = m_item.url
                        if not m_item.url.startswith(
                            "/media/"
                        ) and not m_item.url.startswith("/uploads/"):
                            try:
                                from services.media_downloader import download_media

                                media_type_str = m_item.type.value
                                local_url = await download_media(
                                    m_item.url, tenant_id, media_type_str
                                )

                                # --- FIX: Actualizar el item en content_attrs para persistencia ---
                                # Buscamos el item correspondiente en content_attrs y actualizamos su URL
                                for attr in content_attrs:
                                    if attr.get("url") == m_item.url:
                                        attr["url"] = local_url
                                        logger.info(
                                            f"📍 URL de media actualizada a local: {local_url}"
                                        )

                                # Persistir el cambio en chat_messages inmediatamente
                                await pool.execute(
                                    "UPDATE chat_messages SET content_attributes = $1::jsonb WHERE id = $2",
                                    json.dumps(content_attrs),
                                    msg_id,
                                )
                            except Exception as download_err:
                                logger.error(
                                    f"❌ Error descargando media de {msg.original_channel}: {download_err}"
                                )
                                continue

                        # Solo imágenes y documentos van a la ficha médica (patient_documents)
                        if m_item.type in [MediaType.IMAGE, MediaType.DOCUMENT]:
                            # Intentar identificar al paciente por external_user_id (ID de Instagram/Facebook)
                            # Normalizar teléfono (remover +) para búsqueda más flexible
                            clean_ext_id = (
                                msg.external_user_id.replace("+", "")
                                if msg.external_user_id
                                else ""
                            )

                            patient_row = await pool.fetchrow(
                                """
                                SELECT id FROM patients
                                WHERE tenant_id = $1 AND (
                                    phone_number = $2 OR
                                    phone_number = $3 OR
                                    instagram_psid = $2 OR
                                    facebook_psid = $2 OR
                                    external_ids @> $4::jsonb OR
                                    external_ids @> $5::jsonb
                                )
                                LIMIT 1
                            """,
                                tenant_id,
                                msg.external_user_id,
                                clean_ext_id,
                                json.dumps({"whatsapp_id": msg.external_user_id}),
                                json.dumps({"whatsapp_id": clean_ext_id}),
                            )

                            if patient_row:
                                # Determinar tipo de documento para clasificación
                                # V7.6 Platinum: Clasificación genérica basada en canal y tipo
                                channel_name = msg.original_channel or "whatsapp"
                                media_type_str = m_item.type.value
                                doc_type = f"{channel_name}_{media_type_str}"

                                # Always generate unique filename to avoid duplicate key constraint
                                raw_name = m_item.file_name or doc_type
                                base_no_ext = (
                                    raw_name.rsplit(".", 1)[0]
                                    if "." in raw_name
                                    else raw_name
                                )
                                file_name = f"{base_no_ext}_{uuid.uuid4().hex[:8]}"

                                # Extraer extensión del archivo si está disponible
                                import mimetypes

                                ext = (
                                    mimetypes.guess_extension(m_item.mime_type)
                                    if m_item.mime_type
                                    else None
                                )
                                if not ext:
                                    # Fallback manual para tipos comunes si mimetypes falla
                                    if m_item.type == MediaType.IMAGE:
                                        ext = ".jpg"
                                    elif m_item.type == MediaType.AUDIO:
                                        ext = ".ogg"
                                    elif m_item.type == MediaType.DOCUMENT:
                                        ext = ".pdf"
                                    else:
                                        ext = ".bin"

                                if ext and not file_name.lower().endswith(ext.lower()):
                                    file_name = f"{file_name}{ext}"

                                # Insertar en patient_documents
                                await pool.execute(
                                    """
                                    INSERT INTO patient_documents (
                                        patient_id, tenant_id, file_path, 
                                        document_type, file_name, mime_type,
                                        source, source_details, uploaded_at
                                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, NOW())
                                """,
                                    patient_row["id"],
                                    tenant_id,
                                    local_url,
                                    doc_type,
                                    file_name,
                                    m_item.mime_type,
                                    msg.original_channel,
                                    json.dumps(
                                        {
                                            "provider": provider,
                                            "external_user_id": msg.external_user_id,
                                            "display_name": msg.display_name,
                                            "media_type": m_item.type.value,
                                            "file_size": m_item.meta.get("file_size"),
                                            "conversation_id": str(conv_id),
                                            "message_id": msg_id,
                                        }
                                    ),
                                )
                                logger.info(
                                    f"📁 Archivo de {msg.original_channel} guardado en ficha médica: paciente={patient_row['id']}, tipo={m_item.type.value}, archivo={file_name}"
                                )
                            else:
                                logger.info(
                                    f"⚠️ No se encontró paciente para external_user_id: {msg.external_user_id} (canal: {msg.original_channel})"
                                )

                    except Exception as doc_err:
                        logger.error(
                            f"❌ Error al guardar archivo de {msg.original_channel} en ficha médica: {doc_err}"
                        )
                        # No fallar el flujo principal por error en guardado de documento

            # --- Spec 14: Socket.IO Notification (Real-time) ---
            try:
                from main import app

                sio = getattr(app.state, "sio", None)
                to_json_safe = getattr(app.state, "to_json_safe", lambda x: x)
                if sio:
                    # ✅ FIX: Sign attachment URLs for real-time preview (Spec 19)
                    from urllib.parse import urlencode

                    signed_socket_attachments = []
                    for att in content_attrs:
                        att_url = att.get("url")
                        if att_url:
                            # ✅ FIX: Limpiar de parámetros legacy antes de firmar (Spec 19)
                            clean_att_url = att_url
                            if att_url.startswith("/media/") or att_url.startswith(
                                "/uploads/"
                            ):
                                clean_att_url = att_url.split("?")[0]

                            signature, expires = generate_signed_url(
                                clean_att_url, tenant_id
                            )
                            proxy_params = {
                                "url": clean_att_url,
                                "tenant_id": tenant_id,
                                "signature": signature,
                                "expires": expires,
                            }
                            signed_url = (
                                f"/admin/chat/media/proxy?{urlencode(proxy_params)}"
                            )
                            signed_socket_attachments.append({**att, "url": signed_url})
                        else:
                            signed_socket_attachments.append(att)

                    await sio.emit(
                        "NEW_MESSAGE",
                        to_json_safe(
                            {
                                "phone_number": msg.external_user_id,
                                "tenant_id": tenant_id,
                                "message": msg.content
                                or (
                                    f"[{msg.media[0].type.value.upper()}]"
                                    if msg.media
                                    else ""
                                ),
                                "attachments": signed_socket_attachments,
                                "role": role,
                                "channel": msg.original_channel,
                            }
                        ),
                    )
                    logger.info(
                        f"📡 Socket NEW_MESSAGE emitted for {msg.external_user_id} via {provider}"
                    )
            except Exception as sio_err:
                logger.error(f"⚠️ Error emitting SocketIO event: {sio_err}")

            # --- Spec 24: Buffer / Agent Trigger (Only if not locked) ---
            override_row = await pool.fetchrow(
                "SELECT human_override_until FROM chat_conversations WHERE id = $1",
                conv_id,
            )
            from datetime import datetime, timezone

            utc_now = datetime.now(timezone.utc)
            is_locked = (
                override_row
                and override_row["human_override_until"] is not None
                and (
                    override_row["human_override_until"]
                    if override_row["human_override_until"].tzinfo
                    else override_row["human_override_until"].replace(
                        tzinfo=timezone.utc
                    )
                )
                > utc_now
            )

            logger.info(
                f"🔒 Override check: conv={conv_id} override_until={override_row['human_override_until'] if override_row else 'N/A'} utc_now={utc_now} is_locked={is_locked}"
            )

            # If we got here, the message was successfully persisted to chat_messages
            # and either the buffer task is about to be queued OR human override is active.
            # Either way, mark the inbound row as 'done' so subsequent retries are
            # safely deduped (and we don't accidentally process it twice).
            _idem_processed_ok = True

            if not is_locked:
                # Auto-cleanup: if override expired but status is still human_handling, reset it
                if override_row and override_row["human_override_until"] is not None:
                    try:
                        await pool.execute(
                            "UPDATE chat_conversations SET human_override_until = NULL, status = 'active' WHERE id = $1 AND status IN ('human_handling', 'silenced')",
                            conv_id,
                        )
                        logger.info(f"🔄 Auto-cleared expired human override for conv {conv_id}")
                    except Exception as cleanup_err:
                        logger.warning(f"⚠️ Override cleanup failed: {cleanup_err}")
                try:
                    import os
                    import redis.asyncio as redis
                    from services.buffer_manager import BufferManager

                    redis_url = os.getenv("REDIS_URL", "redis://redis:6379")
                    redis_client = redis.from_url(redis_url, decode_responses=True)

                    message_data = {
                        "text": msg.content,
                        "wamid": ext_id_candidate,
                        "business_info": {"conversation_id": str(conv_id)},
                        "media": content_attrs,
                        "correlation_id": str(uuid.uuid4()),
                    }
                    if msg.referral:
                        message_data["referral"] = msg.referral

                    async def enqueue_bg():
                        try:
                            await BufferManager.enqueue_message(
                                redis_client=redis_client,
                                db_pool=get_pool(),
                                provider=provider,
                                channel=msg.original_channel,
                                tenant_id=tenant_id,
                                external_user_id=msg.external_user_id,
                                message_data=message_data,
                            )
                        finally:
                            await redis_client.aclose()

                    background_tasks.add_task(enqueue_bg)
                    logger.info(f"⏳ Buffer task queued for {msg.external_user_id}")
                except Exception as e:
                    logger.error(f"⚠️ Error queuing buffer task: {e}")
            else:
                logger.info(
                    f"🔇 AI silenced by human override for {msg.external_user_id}"
                )

        except Exception as e:
            logger.error(f"Error processing msg: {e}")
        finally:
            # Idempotency cleanup (TIER chatwoot fix — verify follow-up):
            # - On SUCCESS: mark the inbound row as 'done' so future retries are deduped.
            # - On FAILURE: DELETE the inbound row so the next webhook retry can re-attempt
            #   processing instead of being silently dropped (lost-message bug).
            if _idem_locked_id:
                try:
                    if _idem_processed_ok:
                        await db.mark_inbound_done(provider, _idem_locked_id)
                    else:
                        await pool.execute(
                            "DELETE FROM inbound_messages WHERE provider = $1 AND provider_message_id = $2",
                            provider,
                            _idem_locked_id,
                        )
                        logger.warning(
                            f"🔄 inbound_messages row released for retry: provider={provider} msg_id={_idem_locked_id}"
                        )
                except Exception as _idem_cleanup_err:
                    logger.warning(
                        f"⚠️ inbound_messages cleanup failed (non-blocking): {_idem_cleanup_err}"
                    )

    return {"status": "processed", "count": len(saved_ids)}
