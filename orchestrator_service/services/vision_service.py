import logging
import os
import base64
import asyncio
from typing import Optional, List, Dict
from openai import AsyncOpenAI
import urllib.parse

logger = logging.getLogger(__name__)

# Instancia global de cliente OpenAI (puede reutilizarse la configurarción existente)
aclient = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Límites para procesamiento de adjuntos
MAX_IMAGES = 10
MAX_PDFS = 5
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5 MB
VISION_TIMEOUT = 30  # segundos por archivo
MAX_CONCURRENT_VISION_CALLS = 5  # límite de concurrencia para rate limiting


async def analyze_image_url(image_url: str, tenant_id: int) -> Optional[str]:
    """
    Analiza una imagen usando GPT-4o y devuelve una descripción detallada.

    Args:
        image_url: URL de la imagen (puede ser local /media/... o externa)
        tenant_id: ID del tenant (contexto)

    Returns:
        str: Descripción de la imagen o None si falla.
    """
    try:
        # Si la URL es relativa (/media/...), construir la URL completa interna o externa
        # Para OpenAI, necesitamos una URL pública accesible.
        # SI estamos en local/docker sin URL pública, esto fallará a menos que la imagen sea base64.
        # ESTRATEGIA: Si es /media/ local, leer archivo y enviar como base64.

        vision_messages = []

        # Detectar si es path local o URL relativa
        is_local = (
            image_url.startswith("/media/")
            or image_url.startswith("/uploads/")
            or "localhost" in image_url
            or "orchestrator" in image_url
        )

        if is_local:
            # 1. Resolver path físico del archivo
            if image_url.startswith("http"):
                parsed = urllib.parse.urlparse(image_url)
                path = parsed.path
            else:
                path = image_url

            # Determinar directorio base y path relativo
            if path.startswith("/uploads/"):
                base_dir = os.getenv(
                    "UPLOADS_DIR", os.path.join(os.getcwd(), "uploads")
                )
                # Remove /uploads/ prefix since base_dir already points to uploads dir
                rel_path = path.replace("/uploads/", "", 1)
            elif path.startswith("/media/"):
                base_dir = os.getenv("MEDIA_ROOT", os.getcwd())
                rel_path = path.lstrip("/")
            else:
                base_dir = os.getcwd()
                rel_path = path.lstrip("/")

            local_path = os.path.join(base_dir, rel_path)
            logger.info(
                f"👁️ Vision: Resolving path: base={base_dir} rel={rel_path} → {local_path}"
            )

            if not os.path.exists(local_path):
                logger.error(f"❌ Vision: Archivo local no encontrado: {local_path}")
                return None

            # 2. Leer y codificar en base64
            with open(local_path, "rb") as image_file:
                base64_image = base64.b64encode(image_file.read()).decode("utf-8")

            # 3. Determinar mime type
            ext = os.path.splitext(local_path)[1].lower()
            mime = "image/jpeg"  # Default
            if ext == ".png":
                mime = "image/png"
            elif ext == ".webp":
                mime = "image/webp"
            elif ext == ".gif":
                mime = "image/gif"

            # 4. Construir payload visión
            vision_messages = [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": "Actúa como un asistente dental experto. Describe esta imagen detalladamente con enfoque clínico. Detecta: 1) Signos de dolor, inflamación, sangrado o caries visibles. 2) Dientes rotos o faltantes. 3) Aparatos (brackets, prótesis, implantes). 4) Si es un documento, describe de qué tipo es (estudio, receta, presupuesto). Sé muy preciso y profesional.",
                        },
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:{mime};base64,{base64_image}"},
                        },
                    ],
                }
            ]
        else:
            # URL Externa (accesible públicamente)
            vision_messages = [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": "Describe esta imagen detalladamente. Céntrate en detalles clínicos dentales si los hay, o contexto relevante para atención al cliente.",
                        },
                        {"type": "image_url", "image_url": {"url": image_url}},
                    ],
                }
            ]

        logger.info(f"👁️ Iniciando análisis de visión para: {image_url[:50]}...")

        # Llamada a OpenAI GPT-4o ("gpt-4o" tiene capacidades visuales nativas)
        response = await aclient.chat.completions.create(
            model="gpt-4o",
            messages=vision_messages,
            max_tokens=300,
        )

        description = response.choices[0].message.content
        logger.info(f"✅ Visión completada: {description[:100]}...")

        return description

    except Exception as e:
        logger.error(f"❌ Error en servicio de visión: {e}")
        return None


async def analyze_pdf_url(pdf_url: str, tenant_id: int) -> Optional[str]:
    """
    Analiza un documento PDF usando GPT-4o Vision y devuelve una descripción detallada.

    Args:
        pdf_url: URL del PDF (puede ser local /media/... o externa)
        tenant_id: ID del tenant (contexto)

    Returns:
        str: Descripción del documento o None si falla.
    """
    try:
        # Detectar si es path local o URL relativa
        is_local = (
            pdf_url.startswith("/media/")
            or pdf_url.startswith("/uploads/")
            or "localhost" in pdf_url
            or "orchestrator" in pdf_url
        )

        vision_messages = []

        if is_local:
            # 1. Resolver path físico del archivo
            if pdf_url.startswith("http"):
                parsed = urllib.parse.urlparse(pdf_url)
                path = parsed.path
            else:
                path = pdf_url

            # Determinar directorio base y path relativo
            if path.startswith("/uploads/"):
                base_dir = os.getenv(
                    "UPLOADS_DIR", os.path.join(os.getcwd(), "uploads")
                )
                # Remove /uploads/ prefix since base_dir already points to uploads dir
                rel_path = path.replace("/uploads/", "", 1)
            elif path.startswith("/media/"):
                base_dir = os.getenv("MEDIA_ROOT", os.getcwd())
                rel_path = path.lstrip("/")
            else:
                base_dir = os.getcwd()
                rel_path = path.lstrip("/")

            local_path = os.path.join(base_dir, rel_path)
            logger.info(
                f"👁️ Vision PDF: Resolving path: base={base_dir} rel={rel_path} → {local_path}"
            )

            if not os.path.exists(local_path):
                logger.error(
                    f"❌ Vision PDF: Archivo local no encontrado: {local_path}"
                )
                return None

            # 2. Verificar tamaño máximo (5MB)
            file_size = os.path.getsize(local_path)
            if file_size > MAX_FILE_SIZE:
                logger.warning(
                    f"⚠️ Vision PDF: Archivo demasiado grande ({file_size} bytes > {MAX_FILE_SIZE} bytes), omitiendo análisis"
                )
                return None

            # 3. Leer y codificar en base64
            with open(local_path, "rb") as pdf_file:
                base64_pdf = base64.b64encode(pdf_file.read()).decode("utf-8")

            # 4. Construir payload visión con mime type application/pdf
            vision_messages = [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": "Actúa como un asistente dental experto. Describe este documento detalladamente con enfoque clínico. Detecta: 1) Tipo de documento (estudio, receta, presupuesto, informe médico, radiografía). 2) Información relevante como fechas, nombres, diagnósticos, tratamientos. 3) Sellos, firmas, logotipos de clínicas o profesionales. 4) Si es un comprobante de pago, indica banco, monto, fecha. Sé muy preciso y profesional.",
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:application/pdf;base64,{base64_pdf}"
                            },
                        },
                    ],
                }
            ]
        else:
            # URL Externa (accesible públicamente)
            vision_messages = [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": "Describe este documento detalladamente. Céntrate en detalles clínicos dentales si los hay, o contexto relevante para atención al cliente.",
                        },
                        {"type": "image_url", "image_url": {"url": pdf_url}},
                    ],
                }
            ]

        logger.info(f"👁️ Iniciando análisis de PDF para: {pdf_url[:50]}...")

        # Llamada a OpenAI GPT-4o ("gpt-4o" tiene capacidades visuales nativas)
        response = await aclient.chat.completions.create(
            model="gpt-4o",
            messages=vision_messages,
            max_tokens=300,
        )

        description = response.choices[0].message.content
        logger.info(f"✅ Visión PDF completada: {description[:100]}...")

        return description

    except Exception as e:
        logger.error(f"❌ Error en servicio de visión PDF: {e}")
        return None


async def analyze_attachments_batch(
    attachments: List[Dict],
    tenant_id: int,
    max_concurrent: int = MAX_CONCURRENT_VISION_CALLS,
) -> List[Dict]:
    """
    Procesa múltiples adjuntos en paralelo usando Vision API.

    Args:
        attachments: Lista de diccionarios con keys: url, mime_type, index
        tenant_id: ID del tenant (contexto)
        max_concurrent: Máximo de llamadas concurrentes a Vision API (rate limit)

    Returns:
        Lista de diccionarios con keys: index, vision_description, error
    """
    semaphore = asyncio.Semaphore(max_concurrent)
    results = []

    # Separar imágenes y PDFs para aplicar límites (opcional, el caller ya puede filtrar)
    images = [a for a in attachments if a.get("mime_type", "").startswith("image/")]
    pdfs = [a for a in attachments if a.get("mime_type") == "application/pdf"]

    if len(images) > MAX_IMAGES:
        logger.warning(
            f"⚠️ Número de imágenes ({len(images)}) excede el límite ({MAX_IMAGES}), procesando solo las primeras {MAX_IMAGES}"
        )
        images = images[:MAX_IMAGES]
    if len(pdfs) > MAX_PDFS:
        logger.warning(
            f"⚠️ Número de PDFs ({len(pdfs)}) excede el límite ({MAX_PDFS}), procesando solo los primeros {MAX_PDFS}"
        )
        pdfs = pdfs[:MAX_PDFS]

    filtered_attachments = images + pdfs
    total = len(filtered_attachments)

    async def process_one(attachment: Dict) -> Dict:
        url = attachment["url"]
        mime_type = attachment.get("mime_type", "")
        index = attachment["index"]

        # Verificar tipo de archivo soportado
        if not (mime_type.startswith("image/") or mime_type == "application/pdf"):
            logger.warning(f"⚠️ Tipo de archivo no soportado: {mime_type}, omitiendo")
            return {
                "index": index,
                "vision_description": None,
                "error": "unsupported_mime_type",
            }

        async def analyze_with_semaphore():
            async with semaphore:
                logger.info(
                    f"👁️ Analizando attachment {index + 1}/{total}: {url[:50]}..."
                )
                if mime_type.startswith("image/"):
                    return await analyze_image_url(url, tenant_id)
                else:  # application/pdf
                    return await analyze_pdf_url(url, tenant_id)

        try:
            description = await asyncio.wait_for(
                analyze_with_semaphore(), timeout=VISION_TIMEOUT
            )
            if description is None:
                logger.warning(
                    f"⚠️ Attachment {index} no pudo ser analizado (descripción nula)"
                )
                return {
                    "index": index,
                    "vision_description": None,
                    "error": "vision_failed",
                }
            return {
                "index": index,
                "vision_description": description,
                "error": None,
            }
        except asyncio.TimeoutError:
            logger.error(f"❌ Timeout analizando attachment {index}")
            return {"index": index, "vision_description": None, "error": "timeout"}
        except Exception as e:
            logger.error(f"❌ Error inesperado analizando attachment {index}: {e}")
            return {"index": index, "vision_description": None, "error": str(e)}

    # Ejecutar en paralelo con gather
    logger.info(
        f"🚀 Iniciando procesamiento por lotes de {total} adjuntos (máx {max_concurrent} concurrentes)"
    )
    tasks = [process_one(att) for att in filtered_attachments]
    batch_results = await asyncio.gather(*tasks, return_exceptions=False)

    # Ordenar por índice original
    sorted_results = sorted(batch_results, key=lambda x: x["index"])
    success_count = sum(1 for r in sorted_results if r.get("vision_description"))
    logger.info(
        f"✅ Procesamiento por lotes completado: {success_count}/{total} éxitos"
    )

    return sorted_results


async def process_vision_task(message_id: int, image_url: str, tenant_id: int):
    """
    Tarea de fondo (Background Task):
    1. Analiza la imagen.
    2. Si tiene éxito, actualiza el mensaje en la DB agregando la descripción al attribute.
    """
    if not message_id:
        logger.warning("vision_task_skipped: no message_id provided")
        return

    description = await analyze_image_url(image_url, tenant_id)
    if not description:
        return

    try:
        from db import get_pool
        import json

        pool = get_pool()

        # Leemos atributos actuales
        row = await pool.fetchrow(
            "SELECT content_attributes FROM chat_messages WHERE id = $1", message_id
        )
        if not row:
            logger.warning(f"vision_task_failed: message {message_id} not found")
            return

        current_attrs_json = row["content_attributes"]
        if not current_attrs_json:
            return

        attrs = json.loads(current_attrs_json)
        updated = False

        # Buscamos el adjunto por URL y le pegamos la descripción
        for att in attrs:
            # Comparación simple de URL (podría mejorarse si la URL cambia)
            if att.get("url") == image_url:
                att["description"] = description
                updated = True
                # También podríamos inyectar la descripción en el campo 'content' del mensaje para que Buffer Task lo vea directo?
                # No, mejor mantener la pureza de los datos y que Buffer Task componga.

        if updated:
            await pool.execute(
                "UPDATE chat_messages SET content_attributes = $1::jsonb WHERE id = $2",
                json.dumps(attrs),
                message_id,
            )
            logger.info(f"💾 Descripción de imagen guardada en mensaje {message_id}")

    except Exception as e:
        logger.error(f"❌ Error guardando descripción de visión en DB: {e}")
