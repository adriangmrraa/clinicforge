
import logging
import os
import base64
from typing import Optional
from openai import AsyncOpenAI
import urllib.parse

logger = logging.getLogger(__name__)

# Instancia global de cliente OpenAI (puede reutilizarse la configurarción existente)
aclient = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))

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
        is_local = image_url.startswith("/media/") or "localhost" in image_url or "orchestrator" in image_url
        
        if is_local:
            # 1. Resolver path físico del archivo
            if image_url.startswith("http"):
                parsed = urllib.parse.urlparse(image_url)
                path = parsed.path
            else:
                path = image_url
            
            # Quitar slash inicial si existe para join
            rel_path = path.lstrip("/")
            local_path = os.path.join(os.getcwd(), rel_path)
            
            if not os.path.exists(local_path):
                logger.error(f"❌ Vision: Archivo local no encontrado: {local_path}")
                return None
                
            # 2. Leer y codificar en base64
            with open(local_path, "rb") as image_file:
                base64_image = base64.b64encode(image_file.read()).decode('utf-8')
                
            # 3. Determinar mime type
            ext = os.path.splitext(local_path)[1].lower()
            mime = "image/jpeg" # Default
            if ext == ".png": mime = "image/png"
            elif ext == ".webp": mime = "image/webp"
            elif ext == ".gif": mime = "image/gif"
            
            # 4. Construir payload visión
            vision_messages = [
                {
                    "role": "user", 
                    "content": [
                        {"type": "text", "text": "Describe esta imagen detalladamente. Céntrate en detalles clínicos dentales si los hay (dientes, encías, aparatos), o describe el documento/foto si es administrativo. Sé conciso pero preciso."},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:{mime};base64,{base64_image}"
                            }
                        }
                    ]
                }
            ]
        else:
            # URL Externa (accesible públicamente)
            vision_messages = [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "Describe esta imagen detalladamente. Céntrate en detalles clínicos dentales si los hay, o contexto relevante para atención al cliente."},
                        {
                            "type": "image_url",
                            "image_url": {"url": image_url}
                        }
                    ]
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
        row = await pool.fetchrow("SELECT content_attributes FROM chat_messages WHERE id = $1", message_id)
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
                message_id
            )
            logger.info(f"💾 Descripción de imagen guardada en mensaje {message_id}")
            
    except Exception as e:
        logger.error(f"❌ Error guardando descripción de visión en DB: {e}")
