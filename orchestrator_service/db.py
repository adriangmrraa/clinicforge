import asyncpg
import os
import json
import uuid
import logging
from typing import List, Tuple, Optional, Any, Dict

POSTGRES_DSN = os.getenv("POSTGRES_DSN")

logger = logging.getLogger(__name__)

class Database:
    def __init__(self):
        self.pool: Optional[asyncpg.Pool] = None

    async def connect(self):
        """Conecta al pool de PostgreSQL. Migraciones manejadas por Alembic."""
        if not self.pool:
            if not POSTGRES_DSN:
                logger.critical("POSTGRES_DSN environment variable is not set!")
                return

            dsn = POSTGRES_DSN.replace("postgresql+asyncpg://", "postgresql://")

            async def _init_connection(conn):
                """Register pgvector codec on each new connection so asyncpg
                understands the 'vector' type natively. Without this, vectors
                are returned as bytea and queries fail with 'cannot cast bytea to vector'."""
                try:
                    from pgvector.asyncpg import register_vector
                    await register_vector(conn)
                except Exception as e:
                    # pgvector extension may not be installed in this DB — that's OK,
                    # the JSON fallback path in embedding_service will be used instead.
                    logger.debug(f"pgvector codec registration skipped: {e}")

            try:
                self.pool = await asyncpg.create_pool(
                    dsn,
                    min_size=int(os.getenv("DB_POOL_MIN", "10")),
                    max_size=int(os.getenv("DB_POOL_MAX", "40")),
                    command_timeout=float(os.getenv("DB_COMMAND_TIMEOUT", "60")),
                    max_inactive_connection_lifetime=300.0,
                    init=_init_connection,
                )
                logger.info(
                    f"DB pool initialized: min={os.getenv('DB_POOL_MIN', '10')} "
                    f"max={os.getenv('DB_POOL_MAX', '40')} "
                    f"command_timeout={os.getenv('DB_COMMAND_TIMEOUT', '60')}s "
                    f"(pgvector codec registration enabled)"
                )
            except Exception as e:
                logger.critical(f"Failed to create database pool: {e}")
                return
    
    # Legacy migration methods removed — Alembic is the sole migration tool.
    # See orchestrator_service/alembic/ and models.py.

    async def disconnect(self):
        if self.pool:
            await self.pool.close()

    async def try_insert_inbound(self, provider: str, provider_message_id: str, event_id: str, from_number: str, payload: dict, correlation_id: str) -> bool:
        """Try to insert inbound message. Returns True if inserted, False if duplicate."""
        query = """
        INSERT INTO inbound_messages (provider, provider_message_id, event_id, from_number, payload, status, correlation_id)
        VALUES ($1, $2, $3, $4, $5, 'received', $6)
        ON CONFLICT (provider, provider_message_id) DO NOTHING
        RETURNING id
        """
        async with self.pool.acquire() as conn:
            result = await conn.fetchval(query, provider, provider_message_id, event_id, from_number, json.dumps(payload), correlation_id)
            return result is not None

    async def mark_inbound_processing(self, provider: str, provider_message_id: str):
        query = "UPDATE inbound_messages SET status = 'processing' WHERE provider = $1 AND provider_message_id = $2"
        async with self.pool.acquire() as conn:
            await conn.execute(query, provider, provider_message_id)

    async def mark_inbound_done(self, provider: str, provider_message_id: str):
        query = "UPDATE inbound_messages SET status = 'done', processed_at = NOW() WHERE provider = $1 AND provider_message_id = $2"
        async with self.pool.acquire() as conn:
            await conn.execute(query, provider, provider_message_id)

    async def mark_inbound_failed(self, provider: str, provider_message_id: str, error: str):
        query = "UPDATE inbound_messages SET status = 'failed', processed_at = NOW(), error = $3 WHERE provider = $1 AND provider_message_id = $2"
        async with self.pool.acquire() as conn:
            await conn.execute(query, provider, provider_message_id, error)

    async def append_chat_message(self, from_number: str, role: str, content: str, correlation_id: str, tenant_id: int = 1, conversation_id: Optional[str] = None, content_attributes: Optional[dict] = None) -> Optional[int]:
        if not conversation_id:
            if not self.pool:
                return None
            # Fallback: Resolver conversación si no viene explícita
            res = await self.pool.fetchrow(
                "SELECT id FROM chat_conversations WHERE tenant_id = $1 AND channel = 'whatsapp' AND external_user_id = $2 LIMIT 1",
                tenant_id, from_number
            )
            if res:
                conversation_id = str(res['id'])

        query = """
        INSERT INTO chat_messages (from_number, role, content, correlation_id, tenant_id, conversation_id, content_attributes) 
        VALUES ($1, $2, $3, $4, $5, $6, $7::jsonb)
        RETURNING id
        """
        msg_id = None
        async with self.pool.acquire() as conn:
            msg_id = await conn.fetchval(query, from_number, role, content, correlation_id, tenant_id, 
                               uuid.UUID(conversation_id) if conversation_id else None, 
                               json.dumps(content_attributes) if content_attributes is not None else '[]')
        
        # Sincronizar conversación (Spec 18)
        await self.sync_conversation(tenant_id, "whatsapp", from_number, content, role == "user")
        return msg_id

    async def sync_conversation(self, tenant_id: int, channel: str, external_user_id: str, last_message: str, is_user: bool):
        """
        Actualiza los metadatos de la conversación.
        Si es un mensaje del usuario, actualiza last_user_message_at (Ventana 24h).
        """
        sql = """
            INSERT INTO chat_conversations (tenant_id, channel, external_user_id, last_message_at, last_message_preview, last_user_message_at, updated_at)
            VALUES ($1, $2, $3, NOW(), LEFT($4, 255), CASE WHEN $5 THEN NOW() ELSE NULL END, NOW())
            ON CONFLICT (tenant_id, channel, external_user_id)
            DO UPDATE SET
                last_message_at = NOW(),
                last_message_preview = EXCLUDED.last_message_preview,
                last_user_message_at = CASE WHEN $5 THEN NOW() ELSE chat_conversations.last_user_message_at END,
                updated_at = NOW()
        """
        async with self.pool.acquire() as conn:
            await conn.execute(sql, tenant_id, channel, external_user_id, last_message, is_user)
    
    async def get_or_create_conversation(
        self,
        tenant_id: int,
        channel: str,  # "whatsapp", "instagram", "facebook"
        external_user_id: str,  # Phone number o user_id
        display_name: Optional[str] = None,
        external_chatwoot_id: Optional[int] = None,
        external_account_id: Optional[int] = None,
        avatar_url: Optional[str] = None,
        provider: Optional[str] = None
    ) -> uuid.UUID:
        """
        Obtiene conversación existente o crea una nueva (Spec 20).
        Garantiza UNA sola conversación por external_user_id + channel.
        Soporta persistencia de IDs de Chatwoot (Spec 34) para respuesta de la IA.
        """
        # 1. Buscar conversación existente
        # ✅ Fase 2: Buscar por ID de Chatwoot primero para evitar splits de ID numérico vs Handle
        existing = None
        if external_chatwoot_id:
            existing = await self.pool.fetchrow("""
                SELECT id, external_user_id FROM chat_conversations
                WHERE tenant_id = $1 AND external_chatwoot_id = $2
            """, tenant_id, external_chatwoot_id)
        
        if not existing:
            existing = await self.pool.fetchrow("""
                SELECT id, external_user_id FROM chat_conversations
                WHERE tenant_id = $1 AND channel = $2 AND external_user_id = $3
            """, tenant_id, channel, external_user_id)
        
        if existing:
            # Si existe pero no tenía IDs de Chatwoot, o cambió el user_id (split fix), actualizamos
            # ✅ Fase 2: Si el handle (external_user_id) cambió, verificar que no colisione con otra fila
            target_user_id = external_user_id
            if external_user_id and existing['external_user_id'] != external_user_id:
                collision = await self.pool.fetchval("""
                    SELECT id FROM chat_conversations 
                    WHERE tenant_id = $1 AND channel = $2 AND external_user_id = $3 AND id != $4
                """, tenant_id, channel, external_user_id, existing['id'])
                if collision:
                    logger.warning(f"⚠️ Collision detected for handle '{external_user_id}'. Sticking with existing row {existing['id']} but not updating user_id.")
                    target_user_id = existing['external_user_id'] # No cambiarlo para evitar error de UNICIDAD

            await self.pool.execute("""
                UPDATE chat_conversations 
                SET external_chatwoot_id = COALESCE($1, external_chatwoot_id),
                    external_account_id = COALESCE($2, external_account_id),
                    external_user_id = COALESCE($3, external_user_id),
                    display_name = COALESCE($4, display_name),
                    provider = COALESCE($5, provider),
                    updated_at = NOW()
                WHERE id = $6
            """, external_chatwoot_id, external_account_id, target_user_id, display_name, provider, existing['id'])

            # Si existe y tiene avatar nuevo, lo fusionamos
            if avatar_url:
                await self.pool.execute("""
                    UPDATE chat_conversations 
                    SET meta = meta || $1::jsonb,
                        updated_at = NOW()
                    WHERE id = $2
                """, json.dumps({"customer_avatar": avatar_url}), existing['id'])
            return existing['id']
        
        # 2. Crear nueva conversación (ON CONFLICT para race conditions)
        conv_id = await self.pool.fetchval("""
            INSERT INTO chat_conversations (
                tenant_id, channel, external_user_id, display_name,
                external_chatwoot_id, external_account_id,
                last_message_at, updated_at, meta, provider
            )
            VALUES ($1, $2, $3, $4, $5, $6, NOW(), NOW(), $7::jsonb, $8)
            ON CONFLICT (tenant_id, channel, external_user_id) 
            DO UPDATE SET 
                updated_at = NOW(),
                display_name = COALESCE(EXCLUDED.display_name, chat_conversations.display_name),
                external_chatwoot_id = COALESCE(EXCLUDED.external_chatwoot_id, chat_conversations.external_chatwoot_id),
                external_account_id = COALESCE(EXCLUDED.external_account_id, chat_conversations.external_account_id),
                provider = COALESCE(EXCLUDED.provider, chat_conversations.provider),
                meta = chat_conversations.meta || EXCLUDED.meta
            RETURNING id
        """, tenant_id, channel, external_user_id, display_name or external_user_id, 
           external_chatwoot_id, external_account_id, 
           json.dumps({"customer_avatar": avatar_url}) if avatar_url else '{}',
           provider)
        
        logger.info(f"✅ New conversation created: {conv_id} with Chatwoot IDs: {external_chatwoot_id}/{external_account_id}")
        return conv_id

    async def ensure_patient_exists(self, phone_number: Optional[str], tenant_id: int, first_name: str = 'Visitante', status: str = 'guest', external_id: Optional[dict] = None, create_if_missing: bool = True):
        """
        Asegura que exista un registro de paciente/lead.
        Soporta búsqueda por phone_number (WhatsApp) o por external_id (Meta/IG/FB).
        Si create_if_missing=False, retorna None cuando no existe (no crea "Visitante").
        """
        # 1. Intentar buscar por external_id si viene (ej: {"instagram": "user_id"})
        if external_id:
            for platform, platform_id in external_id.items():
                query_lookup = """
                    SELECT id, status FROM patients
                    WHERE tenant_id = $1 AND external_ids->>$2 = $3
                    LIMIT 1
                """
                async with self.pool.acquire() as conn:
                    row = await conn.fetchrow(query_lookup, tenant_id, platform, str(platform_id))
                    if row:
                        return row

        # 2. Intentar buscar por phone_number si viene
        if phone_number:
            query_lookup_phone = """
                SELECT id, status FROM patients
                WHERE tenant_id = $1 AND phone_number = $2
                LIMIT 1
            """
            async with self.pool.acquire() as conn:
                row = await conn.fetchrow(query_lookup_phone, tenant_id, phone_number)
                if row:
                    # Si encontramos por teléfono y traemos external_id, actualizamos para vincular
                    if external_id:
                        await conn.execute("""
                            UPDATE patients SET external_ids = external_ids || $1::jsonb, updated_at = NOW()
                            WHERE id = $2
                        """, json.dumps(external_id), row['id'])
                    return row

        # 3. Si no existe y create_if_missing=False, retornar None (no crear Visitante)
        if not create_if_missing:
            return None

        # 4. Crear nuevo (Lead o Paciente según status)
        query_insert = """
        INSERT INTO patients (tenant_id, phone_number, first_name, status, external_ids, created_at)
        VALUES ($1, $2, $3, $4, $5::jsonb, NOW())
        ON CONFLICT (tenant_id, phone_number) WHERE phone_number IS NOT NULL
        DO UPDATE SET
            first_name = CASE
                WHEN patients.status = 'guest'
                     OR patients.first_name IS NULL
                     OR patients.first_name IN ('Visitante', 'Paciente', 'Visitante ', 'Paciente ')
                THEN EXCLUDED.first_name
                ELSE patients.first_name
            END,
            status = CASE WHEN patients.status = 'guest' AND EXCLUDED.status = 'active' THEN 'active' ELSE patients.status END,
            external_ids = patients.external_ids || EXCLUDED.external_ids,
            updated_at = NOW()
        RETURNING id, status
        """
        async with self.pool.acquire() as conn:
            return await conn.fetchrow(query_insert, tenant_id, phone_number, first_name, status, json.dumps(external_id or {}))

    async def get_chat_history(self, from_number: str, limit: int = 15, tenant_id: Optional[int] = None) -> List[dict]:
        """Returns list of {'role': ..., 'content': ..., 'content_attributes': ...} in chronological order."""
        if tenant_id is not None:
            query = "SELECT role, content, content_attributes FROM chat_messages WHERE from_number = $1 AND tenant_id = $2 ORDER BY created_at DESC LIMIT $3"
            async with self.pool.acquire() as conn:
                rows = await conn.fetch(query, from_number, tenant_id, limit)
                return [dict(row) for row in reversed(rows)]
        query = "SELECT role, content, content_attributes FROM chat_messages WHERE from_number = $1 ORDER BY created_at DESC LIMIT $2"
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(query, from_number, limit)
            return [dict(row) for row in reversed(rows)]

    # --- WRAPPER METHODS PARA TOOLS (acceso directo al pool) ---
    async def fetch(self, query: str, *args):
        """Wrapper para pool.fetch - usado por check_availability."""
        async with self.pool.acquire() as conn:
            return await conn.fetch(query, *args)
    
    async def fetchrow(self, query: str, *args):
        """Wrapper para pool.fetchrow - usado por book_appointment."""
        async with self.pool.acquire() as conn:
            return await conn.fetchrow(query, *args)
    
    async def fetchval(self, query: str, *args):
        """Wrapper para pool.fetchval."""
        async with self.pool.acquire() as conn:
            return await conn.fetchval(query, *args)
    
    async def execute(self, query: str, *args):
        """Wrapper para pool.execute - usado por book_appointment."""
        async with self.pool.acquire() as conn:
            return await conn.execute(query, *args)

# Global instance
db = Database()


def get_pool():
    """Para módulos Chatwoot (chat_api, credentials, etc.) que esperan get_pool()."""
    if db.pool is None:
        raise RuntimeError("Database pool not initialized. Call await db.connect() first.")
    return db.pool


# ==================== META ADS ATTRIBUTION FUNCTIONS ====================

async def update_patient_attribution_from_referral(patient_id: int, tenant_id: int, referral: dict) -> bool:
    """
    Updates patient attribution from Meta Ads referral object.
    
    Args:
        patient_id: Patient ID to update
        tenant_id: Tenant ID for multi-tenant isolation
        referral: Referral object from WhatsApp webhook
    
    Returns:
        bool: True if attribution was updated, False otherwise
    """
    if not referral:
        return False
    
    # Extract attribution data from referral object
    # WhatsApp referral structure: https://developers.facebook.com/docs/whatsapp/cloud-api/webhooks/components#referral-object
    ad_id = referral.get("ad_id")
    if not ad_id:
        return False
    
    # Build attribution update
    attribution_update = {
        "acquisition_source": "META_ADS",
        "meta_ad_id": ad_id,
        "meta_ad_name": referral.get("ad_name"),
        "meta_ad_headline": referral.get("headline"),
        "meta_ad_body": referral.get("body"),
        "meta_adset_id": referral.get("adset_id"),
        "meta_adset_name": referral.get("adset_name"),
        "meta_campaign_id": referral.get("campaign_id"),
        "meta_campaign_name": referral.get("campaign_name"),
        "updated_at": "NOW()"
    }
    
    # Filter out None values
    attribution_update = {k: v for k, v in attribution_update.items() if v is not None}
    
    if not attribution_update:
        return False
    
    # Build dynamic SQL update
    set_clauses = []
    params = []
    param_index = 1
    
    for key, value in attribution_update.items():
        if key == "updated_at":
            set_clauses.append(f"{key} = NOW()")
        else:
            set_clauses.append(f"{key} = ${param_index}")
            params.append(value)
            param_index += 1
    
    # Add patient_id and tenant_id as final parameters
    params.extend([patient_id, tenant_id])
    
    query = f"""
        UPDATE patients 
        SET {', '.join(set_clauses)}
        WHERE id = ${param_index} AND tenant_id = ${param_index + 1}
    """
    
    try:
        pool = get_pool()
        async with pool.acquire() as conn:
            result = await conn.execute(query, *params)
            updated = result.split()[1]  # Get "UPDATE X" count
            
            if updated == "1":
                logger.info(f"✅ Patient {patient_id} attribution updated from Meta Ads referral: {ad_id}")
                return True
            else:
                logger.warning(f"⚠️ Patient {patient_id} not found or not updated")
                return False
                
    except Exception as e:
        logger.error(f"❌ Error updating patient attribution: {e}")
        return False


async def update_patient_attribution_from_meta_webhook(patient_id: int, tenant_id: int, meta_data: dict) -> bool:
    """
    Updates patient attribution from Meta Lead Forms webhook data.
    
    Args:
        patient_id: Patient ID to update
        tenant_id: Tenant ID for multi-tenant isolation
        meta_data: Meta Ads data from lead form webhook
    
    Returns:
        bool: True if attribution was updated, False otherwise
    """
    if not meta_data:
        return False
    
    # Build attribution update from Meta webhook data
    attribution_update = {
        "acquisition_source": "META_ADS",
        "meta_ad_id": meta_data.get("ad_id"),
        "meta_ad_name": meta_data.get("ad_name"),
        "meta_ad_headline": meta_data.get("headline"),
        "meta_ad_body": meta_data.get("body"),
        "meta_adset_id": meta_data.get("adset_id"),
        "meta_adset_name": meta_data.get("adset_name"),
        "meta_campaign_id": meta_data.get("campaign_id"),
        "meta_campaign_name": meta_data.get("campaign_name"),
        "updated_at": "NOW()"
    }
    
    # Filter out None values
    attribution_update = {k: v for k, v in attribution_update.items() if v is not None}
    
    if not attribution_update:
        return False
    
    # Build dynamic SQL update
    set_clauses = []
    params = []
    param_index = 1
    
    for key, value in attribution_update.items():
        if key == "updated_at":
            set_clauses.append(f"{key} = NOW()")
        else:
            set_clauses.append(f"{key} = ${param_index}")
            params.append(value)
            param_index += 1
    
    # Add patient_id and tenant_id as final parameters
    params.extend([patient_id, tenant_id])
    
    query = f"""
        UPDATE patients 
        SET {', '.join(set_clauses)}
        WHERE id = ${param_index} AND tenant_id = ${param_index + 1}
    """
    
    try:
        pool = get_pool()
        async with pool.acquire() as conn:
            result = await conn.execute(query, *params)
            updated = result.split()[1]  # Get "UPDATE X" count
            
            if updated == "1":
                logger.info(f"✅ Patient {patient_id} attribution updated from Meta webhook")
                return True
            else:
                logger.warning(f"⚠️ Patient {patient_id} not found or not updated")
                return False
                
    except Exception as e:
        logger.error(f"❌ Error updating patient attribution from webhook: {e}")
        return False


async def get_patient_attribution_stats(tenant_id: int, time_range: str = "last_30d") -> dict:
    """
    Returns Meta Ads attribution statistics for a tenant.
    
    Args:
        tenant_id: Tenant ID for multi-tenant isolation
        time_range: Time range for stats (last_30d, last_7d, all)
    
    Returns:
        dict: Attribution statistics
    """
    # Build time filter
    time_filters = {
        "last_7d": "AND created_at >= NOW() - INTERVAL '7 days'",
        "last_30d": "AND created_at >= NOW() - INTERVAL '30 days'",
        "all": ""
    }
    time_filter = time_filters.get(time_range, "")
    
    query = f"""
        SELECT 
            acquisition_source,
            COUNT(*) as total_patients,
            COUNT(DISTINCT meta_campaign_id) as unique_campaigns,
            COUNT(DISTINCT meta_ad_id) as unique_ads,
            COUNT(DISTINCT meta_adset_id) as unique_adsets
        FROM patients
        WHERE tenant_id = $1 {time_filter}
        GROUP BY acquisition_source
        ORDER BY total_patients DESC
    """
    
    try:
        pool = get_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch(query, tenant_id)
            
            stats = {
                "total_patients": 0,
                "meta_ads_patients": 0,
                "organic_patients": 0,
                "unique_campaigns": 0,
                "unique_ads": 0,
                "unique_adsets": 0,
                "breakdown": []
            }
            
            for row in rows:
                stats["total_patients"] += row["total_patients"]
                
                if row["acquisition_source"] == "META_ADS":
                    stats["meta_ads_patients"] = row["total_patients"]
                    stats["unique_campaigns"] = row["unique_campaigns"]
                    stats["unique_ads"] = row["unique_ads"]
                    stats["unique_adsets"] = row["unique_adsets"]
                elif row["acquisition_source"] == "ORGANIC":
                    stats["organic_patients"] = row["total_patients"]
                
                stats["breakdown"].append({
                    "source": row["acquisition_source"],
                    "count": row["total_patients"],
                    "unique_campaigns": row["unique_campaigns"],
                    "unique_ads": row["unique_ads"],
                    "unique_adsets": row["unique_adsets"]
                })
            
            # Calculate percentages
            if stats["total_patients"] > 0:
                stats["meta_ads_percentage"] = round((stats["meta_ads_patients"] / stats["total_patients"]) * 100, 1)
                stats["organic_percentage"] = round((stats["organic_patients"] / stats["total_patients"]) * 100, 1)
            else:
                stats["meta_ads_percentage"] = 0
                stats["organic_percentage"] = 0
            
            return stats
            
    except Exception as e:
        logger.error(f"❌ Error getting patient attribution stats: {e}")
        return {
            "total_patients": 0,
            "meta_ads_patients": 0,
            "organic_patients": 0,
            "meta_ads_percentage": 0,
            "organic_percentage": 0,
            "unique_campaigns": 0,
            "unique_ads": 0,
            "unique_adsets": 0,
            "breakdown": [],
            "error": str(e)
        }
