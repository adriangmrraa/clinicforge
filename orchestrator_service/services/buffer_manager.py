import asyncio
import json
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

class AtomicRedisProcessor:
    """Procesador atómico para operaciones Redis."""

    @staticmethod
    async def atomic_buffer_fetch(redis_client, buffer_key: str):
        """Fetch atómico de buffer completo."""
        message_count = await redis_client.llen(buffer_key)
        if message_count == 0:
            return [], 0
        
        # Pipeline atómico: leer y limpiar en una operación
        pipe = redis_client.pipeline()
        pipe.lrange(buffer_key, 0, message_count - 1)
        pipe.ltrim(buffer_key, message_count, -1)
        results = await pipe.execute()
        
        raw_items = results[0]
        parsed_items = [json.loads(item) for item in raw_items]
        
        return parsed_items, message_count

class BufferManager:
    """Manager central para buffers multi-canal con Reglas de Negocio Robustas."""
    
    # Valores por defecto globales unificados como fallback (Regla C5)
    GLOBAL_DEFAULTS = {
        "whatsapp": {
            "debounce_seconds": 11,
            "bubble_delay": 4,
            "max_message_length": 400,
            "typing_indicator": True
        },
        "instagram": {
            "debounce_seconds": 8,
            "bubble_delay": 3,
            "max_message_length": 300,
            "typing_indicator": True
        },
        "facebook": {
            "debounce_seconds": 8,
            "bubble_delay": 3,
            "max_message_length": 300,
            "typing_indicator": True
        },
        "chatwoot": {
            "debounce_seconds": 10,
            "bubble_delay": 3,
            "max_message_length": 350,
            "typing_indicator": False
        }
    }
    
    @classmethod
    def get_buffer_key(cls, provider: str, tenant_id: int, external_user_id: str) -> str:
        return f"buffer:{provider}:{tenant_id}:{external_user_id}"
    
    @classmethod
    def get_timer_key(cls, provider: str, tenant_id: int, external_user_id: str) -> str:
        return f"timer:{provider}:{tenant_id}:{external_user_id}"
    
    @classmethod
    def get_lock_key(cls, provider: str, tenant_id: int, external_user_id: str) -> str:
        return f"active_task:{provider}:{tenant_id}:{external_user_id}"
    
    @classmethod
    async def get_config(cls, pool, provider: str, channel: str, tenant_id: int, key: str, default=None):
        """Obtiene configuración para canal específico, primero desde BD, sino Fallback global."""
        try:
            if pool:
                async with pool.acquire() as conn:
                    # Sovereignty Check: WHERE tenant_id explícito
                    row = await conn.fetchrow(
                        "SELECT config FROM channel_configs WHERE tenant_id = $1 AND provider = $2 AND channel = $3",
                        tenant_id, provider, channel
                    )
                    if row and row['config']:
                        config_dict = json.loads(row['config']) if isinstance(row['config'], str) else row['config']
                        if key in config_dict:
                            return config_dict[key]
        except Exception as e:
            logger.warning(f"No se pudo obtener config DB para {tenant_id}/{provider}/{channel}: {e}")
            
        # Fallback a GLOBAL_DEFAULTS
        # Mapeamos provider a la llave correcta si viene genérico como chatwoot o específico (instagram/facebook)
        config_key = channel if channel in cls.GLOBAL_DEFAULTS else provider
        fallback_config = cls.GLOBAL_DEFAULTS.get(config_key, {})
        return fallback_config.get(key, default)
    
    @classmethod
    async def enqueue_message(cls, redis_client, db_pool, provider: str, channel: str, tenant_id: int, 
                            external_user_id: str, message_data: Dict[str, Any]):
        """Agrega mensaje al buffer y programa procesamiento con Graceful Interruption."""
        buffer_key = cls.get_buffer_key(provider, tenant_id, external_user_id)
        timer_key = cls.get_timer_key(provider, tenant_id, external_user_id)
        lock_key = cls.get_lock_key(provider, tenant_id, external_user_id)
        
        # 1. Agregar mensaje al buffer
        await redis_client.rpush(buffer_key, json.dumps(message_data))
        
        # 2. Reiniciar timer (debounce)
        debounce_seconds = await cls.get_config(db_pool, provider, channel, tenant_id, "debounce_seconds", 10)
        await redis_client.setex(timer_key, debounce_seconds, "1")
        
        # 3. Iniciar tarea de procesamiento si no hay una activa
        # Graceful Interruption: Si existe un lock, NO interrumpimos, el while loop de process_user_buffer
        # detectará la extensión del timer y el aumento del buffer naturalmente si aún no ha hecho el fetch atómico.
        # Si ya hizo el fetch atómico, el proceso actual terminará y enviará su respuesta, 
        # y este IF arrancará UN NUEVO lock para la nueva oleada de mensajes que quedará encolada.
        if not await redis_client.get(lock_key):
            # Lock inicial por un tiempo largo (ej. 300s/5min) previendo demoras de LLM + Envíos lerdos burbuja a burbuja
            await redis_client.setex(lock_key, 300, "1")  
            asyncio.create_task(
                cls.process_user_buffer(
                    redis_client, db_pool, provider, channel, tenant_id, external_user_id,
                    message_data.get("business_info", {}),
                    message_data.get("correlation_id", "unknown")
                )
            )
    
    @classmethod
    async def process_user_buffer(cls, redis_client, db_pool, provider: str, channel: str, tenant_id: int,
                                external_user_id: str, business_info: Dict[str, Any],
                                correlation_id: str):
        """Procesa buffer de usuario despachándolo al orquestador."""
        buffer_key = cls.get_buffer_key(provider, tenant_id, external_user_id)
        timer_key = cls.get_timer_key(provider, tenant_id, external_user_id)
        lock_key = cls.get_lock_key(provider, tenant_id, external_user_id)
        
        try:
            # Graceful Interruption Loop
            while True:
                # 1. FASE DEBOUNCE: Esperar hasta que timer expire
                while True:
                    await asyncio.sleep(2)
                    ttl = await redis_client.ttl(timer_key)
                    if ttl <= 0:  # Timer expiró, el usuario terminó de escribir la ráfaga
                        break
                
                # 2. FETCH ATÓMICO: Obtener todos los mensajes encolados de manera segura
                parsed_items, message_count = await AtomicRedisProcessor.atomic_buffer_fetch(redis_client, buffer_key)
                if message_count == 0:
                    break # Buffer vacío, salir del loop maestro
                
                # 3. UNIR TEXTO
                joined_text = "\n".join([item.get("text", "") for item in parsed_items if item.get("text")])
                media_list = []
                for item in parsed_items:
                    if item.get("media"):
                        # Si es lista lo sumamos, si es dict único armamos lista
                        if isinstance(item["media"], list):
                            media_list.extend(item["media"])
                        else:
                            media_list.append(item["media"])
                
                if not joined_text and not media_list:
                    # Nada válido
                    continue
                
                # Extender lock fuertemente antes de ir a Inteligencia Artificial para evitar que otro worker
                # intercepte este hilo si el LLM demora mucho. 
                await redis_client.expire(lock_key, 300)
                
                # Lanzar pings defensivos de "typing_on" (Regla C1) si consideramos oportuno
                typing_ping_task = None
                typing_enabled = await cls.get_config(db_pool, provider, channel, tenant_id, "typing_indicator", True)
                
                if typing_enabled:
                    typing_ping_task = asyncio.create_task(cls._typing_pinger(provider, channel, tenant_id, business_info))

                # 4. PROCESAR CON IA (usar buffer_task logic u orchestrator main entrypoint)
                try:
                    from services.buffer_task import process_buffer_task
                    # El Orquestador ahora debe encargarse de procesar y, cuando tenga la respuesta, 
                    # utilizar el ResponseSender asociado al provider/channel respetando la Lógica Estricta de Mezcla y Burbuja (Reglas C3).
                    await process_buffer_task(
                        tenant_id=tenant_id,
                        conversation_id=business_info.get("conversation_id"),
                        external_user_id=external_user_id,
                        messages=[joined_text], # En un futuro se podría pasar media_list también aquí.
                        provider=provider,
                        channel=channel
                    )
                finally:
                    if typing_ping_task:
                        typing_ping_task.cancel() # Detenemos los pings preventivos
                
                # 5. VERIFICAR NUEVOS MENSAJES (llegaron mientras hablábamos con la IA o enviábamos burbujas)
                # Gracias a Graceful Interruption (Regla C2), terminamos el envío en process_buffer_task.
                # Ahora verificamos si durante ese periodo el user nos mandó algo más; si es así, el loop 
                # volverá a arrancar el timer.
                if await redis_client.llen(buffer_key) > 0:
                    debounce_seconds = await cls.get_config(db_pool, provider, channel, tenant_id, "debounce_seconds", 10)
                    await redis_client.setex(timer_key, debounce_seconds, "1")
                    # Reiniciamos el ciclo para el nuevo lote encolado
                else:
                    break # Terminamos todo y no hay nada nuevo en la cola
                    
        except Exception as e:
            logger.error(f"Buffer processing error: {e}", extra={
                "provider": provider,
                "tenant_id": tenant_id,
                "correlation_id": correlation_id
            })
        finally:
            # Cleanup seguro del lock
            await redis_client.delete(lock_key)

    @classmethod
    async def _typing_pinger(cls, provider: str, channel: str, tenant_id: int, business_info: dict):
        """Envía eventos typing preventivos cada 8 segundos mientras corre el LLM"""
        try:
            while True:
                await asyncio.sleep(8) # Usualmente Whatsapp apaga el typing a los ~10s 
                # Dependiendo del provider, hace un POST
                # FIXME: Se delegará la llamada real a la respectiva API (Ycloud o Chatwoot) aquí.
                logger.info(f"Ping Preventivo [typing_on] enviado a {provider}/{channel} para id {business_info.get('conversation_id')}")
        except asyncio.CancelledError:
            pass # Tarea cancelada normalmente cuando termina la IA
