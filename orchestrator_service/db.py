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
        """Conecta al pool de PostgreSQL y ejecuta auto-migraciones."""
        if not self.pool:
            if not POSTGRES_DSN:
                print("❌ ERROR: POSTGRES_DSN environment variable is not set!")
                return

            # asyncpg no soporta el esquema 'postgresql+asyncpg', solo 'postgresql' o 'postgres'
            dsn = POSTGRES_DSN.replace("postgresql+asyncpg://", "postgresql://")
            
            try:
                self.pool = await asyncpg.create_pool(dsn)
            except Exception as e:
                print(f"❌ ERROR: Failed to create database pool: {e}")
                return
            
            # Auto-Migration: Ejecutar dentalogic_schema.sql si las tablas no existen
            await self._run_auto_migrations()
    
    async def _run_auto_migrations(self):
        """
        Sistema de Auto-Migración (Maintenance Robot / Schema Surgeon).
        Se asegura de que la base de datos esté siempre actualizada y saludable.
        """
        try:
            # 1. Auditoría de Salud: ¿Existe la base mínima?
            async with self.pool.acquire() as conn:
                schema_exists = await conn.fetchval("""
                    SELECT EXISTS (
                        SELECT FROM information_schema.tables 
                        WHERE table_name = 'tenants'
                    )
                """)
            
            # 2. Aplicar Base (Foundation) si es un Fresh Install
            if not schema_exists:
                logger.warning("⚠️ Base de datos vacía, aplicando Foundation...")
                await self._apply_foundation(logger)
            
            # 3. Evolución Continua (Pipeline de Cirugía)
            # Aquí agregamos parches específicos que deben correr siempre de forma segura
            await self._run_evolution_pipeline(logger)
            
            logger.info("✅ Base de datos verificada y actualizada (Maintenance Robot OK)")
            
        except Exception as e:
            import traceback
            logger.error(f"❌ Error en Maintenance Robot: {e}")
            logger.error(traceback.format_exc())

    async def _apply_foundation(self, logger):
        """Ejecuta el esquema base dentalogic_schema.sql"""
        possible_paths = [
            os.path.join(os.path.dirname(__file__), "..", "db", "init", "dentalogic_schema.sql"),
            os.path.join(os.path.dirname(__file__), "db", "init", "dentalogic_schema.sql"),
            "/app/db/init/dentalogic_schema.sql"
        ]
        
        schema_path = next((p for p in possible_paths if os.path.exists(p)), None)
        if not schema_path:
            logger.error("❌ Foundation schema not found!")
            return

        with open(schema_path, "r", encoding="utf-8") as f:
            schema_sql = f.read()

        # Limpiar comentarios y separar sentencias respetando $$
        clean_lines = [line.split('--')[0].rstrip() for line in schema_sql.splitlines()]
        clean_sql = "\n".join(clean_lines)
        
        statements = []
        current_stmt = []
        in_dollar = False
        for line in clean_sql.splitlines():
            if "$$" in line:
                in_dollar = not in_dollar if line.count("$$") % 2 != 0 else in_dollar
            current_stmt.append(line)
            if not in_dollar and ";" in line:
                full = "\n".join(current_stmt).strip()
                if full: statements.append(full)
                current_stmt = []
        
        if current_stmt:
            leftover = "\n".join(current_stmt).strip()
            if leftover: statements.append(leftover)

        async with self.pool.acquire() as conn:
            async with conn.transaction():
                for i, stmt in enumerate(statements):
                    await conn.execute(stmt)
        logger.info(f"✅ Foundation aplicada ({len(statements)} sentencias)")

    async def _run_evolution_pipeline(self, logger):
        """
        Pipeline de Cirugía: Parches acumulativos e independientes.
        Agrega aquí bloques DO $$ que aseguren la evolución del esquema.
        """
        patches = [
            # Parche 1: Asegurar tabla 'users' y columna 'user_id' en 'professionals'
            """
            DO $$ 
            BEGIN 
                -- Asegurar columna user_id en professionals
                IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='professionals' AND column_name='user_id') THEN
                    ALTER TABLE professionals ADD COLUMN user_id UUID REFERENCES users(id) ON DELETE SET NULL;
                END IF;
            END $$;
            """,
            # Parche 2: Auto-activación del primer CEO (Protocolo Omega Prime)
            """
            DO $$ 
            BEGIN 
                -- Si existe un usuario CEO en estado pending, lo activamos
                UPDATE users SET status = 'active' 
                WHERE role = 'ceo' AND status = 'pending';
                
                -- Aseguramos que su perfil profesional también esté activo
                UPDATE professionals SET is_active = TRUE 
                WHERE email IN (SELECT email FROM users WHERE role = 'ceo' AND status = 'active');
            END $$;
            """,
            # Agrega más parches aquí en el futuro...
            # Parche 3: Permitir DNI y Apellido nulos para 'guests' (Chat Users)
            """
            DO $$ 
            BEGIN 
                -- Hacer dni nullable
                ALTER TABLE patients ALTER COLUMN dni DROP NOT NULL;
                
                -- Hacer last_name nullable
                ALTER TABLE patients ALTER COLUMN last_name DROP NOT NULL;
                
                -- El constraint de unique dni debe ignorar nulos (Postgres lo hace por defecto, pero revisamos index)
            EXCEPTION
                WHEN others THEN null; -- Ignorar si ya se aplicó o falla
            END $$;
            """,
            # Parche 4: Asegurar updated_at en tabla credentials
            """
            DO $$ 
            BEGIN 
                IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='credentials' AND column_name='updated_at') THEN
                    ALTER TABLE credentials ADD COLUMN updated_at TIMESTAMPTZ DEFAULT NOW();
                END IF;
            END $$;
            """,
            # Parche 5: Asegurar constraint unique (tenant_id, name) en credentials
            """
            DO $$ 
            BEGIN 
                IF NOT EXISTS (SELECT 1 FROM information_schema.table_constraints WHERE table_name='credentials' AND constraint_name='idx_credentials_tenant_name_unique') THEN
                    ALTER TABLE credentials ADD CONSTRAINT idx_credentials_tenant_name_unique UNIQUE (tenant_id, name);
                END IF;
            END $$;
            """,
            # Parche 6: Asegurar constraint unique (tenant_id, phone_number) en patients
            """
            DO $$ 
            BEGIN 
                IF NOT EXISTS (
                    SELECT 1 FROM pg_constraint WHERE conname = 'patients_tenant_id_phone_number_key'
                ) THEN
                    ALTER TABLE patients ADD CONSTRAINT patients_tenant_id_phone_number_key UNIQUE (tenant_id, phone_number);
                END IF;
            END $$;
            """,
            # Parche 5: Agregar urgencia a la tabla patients para tracking de leads
            """
            DO $$ 
            BEGIN 
                IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='patients' AND column_name='urgency_level') THEN
                    ALTER TABLE patients ADD COLUMN urgency_level VARCHAR(20) DEFAULT 'normal';
                END IF;
                IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='patients' AND column_name='urgency_reason') THEN
                    ALTER TABLE patients ADD COLUMN urgency_reason TEXT;
                END IF;
            END $$;
            """,
            # Parche 6: Evolucionar treatment_plan a JSONB en clinical_records
            """
            DO $$ 
            BEGIN 
                -- Si la columna existe y es de tipo text/varchar, la convertimos a JSONB
                IF EXISTS (
                    SELECT 1 FROM information_schema.columns 
                    WHERE table_name='clinical_records' AND column_name='treatment_plan' 
                    AND data_type IN ('text', 'character varying')
                ) THEN
                    ALTER TABLE clinical_records ALTER COLUMN treatment_plan TYPE JSONB USING treatment_plan::jsonb;
                END IF;
                
                -- Si no existe, la creamos
                IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='clinical_records' AND column_name='treatment_plan') THEN
                    ALTER TABLE clinical_records ADD COLUMN treatment_plan JSONB DEFAULT '{}';
                END IF;
            END $$;
            """,
            # Parche 7: Asegurar nombres en tabla users para gestión unificada
            """
            DO $$ 
            BEGIN 
                IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='users' AND column_name='first_name') THEN
                    ALTER TABLE users ADD COLUMN first_name VARCHAR(100);
                END IF;
                IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='users' AND column_name='last_name') THEN
                    ALTER TABLE users ADD COLUMN last_name VARCHAR(100);
                END IF;
            END $$;
            
            -- Copiar datos existentes de professionals a users (opcional pero recomendado)
            UPDATE users u
            SET first_name = p.first_name, last_name = p.last_name
            FROM professionals p
            WHERE u.id = p.user_id AND u.first_name IS NULL;
            """,
            # Parche 8: Agregar google_calendar_id a la tabla de profesionales
            """
            DO $$ 
            BEGIN 
                IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='professionals' AND column_name='google_calendar_id') THEN
                    ALTER TABLE professionals ADD COLUMN google_calendar_id VARCHAR(255);
                END IF;
            END $$;
            """,
            # Parche 9: Agregar working_hours a la tabla profesionales
            """
            DO $$ 
            BEGIN 
                IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='professionals' AND column_name='working_hours') THEN
                    ALTER TABLE professionals ADD COLUMN working_hours JSONB DEFAULT '{}';
                END IF;
            END $$;
            """,
            # Parche 10: Inicializar working_hours para profesionales existentes
            """
            DO $$ 
            BEGIN 
                UPDATE professionals 
                SET working_hours = '{
                    "monday": {"enabled": true, "slots": [{"start": "09:00", "end": "18:00"}]},
                    "tuesday": {"enabled": true, "slots": [{"start": "09:00", "end": "18:00"}]},
                    "wednesday": {"enabled": true, "slots": [{"start": "09:00", "end": "18:00"}]},
                    "thursday": {"enabled": true, "slots": [{"start": "09:00", "end": "18:00"}]},
                    "friday": {"enabled": true, "slots": [{"start": "09:00", "end": "18:00"}]},
                    "saturday": {"enabled": true, "slots": [{"start": "09:00", "end": "18:00"}]},
                    "sunday": {"enabled": false, "slots": []}
                }'::jsonb
                WHERE working_hours = '{}'::jsonb OR working_hours IS NULL;
            END $$;
            """,
            # Parche 11: Columna config (JSONB) en tenants para calendar_provider y demás opciones
            """
            DO $$ 
            BEGIN 
                IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='tenants' AND column_name='config') THEN
                    ALTER TABLE tenants ADD COLUMN config JSONB DEFAULT '{}';
                END IF;
                -- Asegurar que tenants existentes tengan calendar_provider por defecto
                UPDATE tenants SET config = jsonb_set(COALESCE(config, '{}'), '{calendar_provider}', '"local"')
                WHERE config IS NULL OR config->>'calendar_provider' IS NULL;
            END $$;
            """,
            # Parche 12: tenant_id en professionals (idempotente, no rompe datos existentes)
            """
            DO $$
            BEGIN
                IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema = 'public' AND table_name = 'professionals' AND column_name = 'tenant_id') THEN
                    ALTER TABLE professionals ADD COLUMN tenant_id INTEGER DEFAULT 1;
                    UPDATE professionals SET tenant_id = 1 WHERE tenant_id IS NULL;
                    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema = 'public' AND table_name = 'tenants') THEN
                        ALTER TABLE professionals ADD CONSTRAINT fk_professionals_tenant FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE;
                    END IF;
                END IF;
            END $$;
            CREATE INDEX IF NOT EXISTS idx_professionals_tenant ON professionals(tenant_id);
            """,
            # Parche 12b: registration_id en professionals (matrícula; BD puede tener license_number)
            """
            DO $$
            BEGIN
                IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema = 'public' AND table_name = 'professionals' AND column_name = 'registration_id') THEN
                    ALTER TABLE professionals ADD COLUMN registration_id VARCHAR(50);
                    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema = 'public' AND table_name = 'professionals' AND column_name = 'license_number') THEN
                        UPDATE professionals SET registration_id = license_number WHERE license_number IS NOT NULL;
                    END IF;
                END IF;
            END $$;
            """,
            # Parche 12c: updated_at en professionals (algunos esquemas antiguos no lo tienen)
            """
            DO $$
            BEGIN
                IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema = 'public' AND table_name = 'professionals' AND column_name = 'updated_at') THEN
                    ALTER TABLE professionals ADD COLUMN updated_at TIMESTAMPTZ DEFAULT NOW();
                    UPDATE professionals SET updated_at = NOW() WHERE updated_at IS NULL;
                END IF;
            END $$;
            """,
            # Parche 12d: phone_number en professionals (esquemas antiguos pueden no tenerla)
            """
            DO $$
            BEGIN
                IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema = 'public' AND table_name = 'professionals' AND column_name = 'phone_number') THEN
                    ALTER TABLE professionals ADD COLUMN phone_number VARCHAR(20);
                END IF;
            END $$;
            """,
            # Parche 12e: specialty en professionals (esquemas antiguos pueden no tenerla)
            """
            DO $$
            BEGIN
                IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema = 'public' AND table_name = 'professionals' AND column_name = 'specialty') THEN
                    ALTER TABLE professionals ADD COLUMN specialty VARCHAR(100);
                END IF;
            END $$;
            """,
            # Parche 13: tenant_id, source y google_calendar_event_id en appointments (idempotente)
            """
            DO $$
            BEGIN
                IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema = 'public' AND table_name = 'appointments' AND column_name = 'tenant_id') THEN
                    ALTER TABLE appointments ADD COLUMN tenant_id INTEGER DEFAULT 1;
                    UPDATE appointments SET tenant_id = 1 WHERE tenant_id IS NULL;
                    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema = 'public' AND table_name = 'tenants') THEN
                        ALTER TABLE appointments ADD CONSTRAINT fk_appointments_tenant FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE;
                    END IF;
                END IF;
                IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema = 'public' AND table_name = 'appointments' AND column_name = 'source') THEN
                    ALTER TABLE appointments ADD COLUMN source VARCHAR(20) DEFAULT 'ai';
                END IF;
                IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema = 'public' AND table_name = 'appointments' AND column_name = 'google_calendar_event_id') THEN
                    ALTER TABLE appointments ADD COLUMN google_calendar_event_id VARCHAR(255);
                END IF;
            END $$;
            CREATE INDEX IF NOT EXISTS idx_appointments_tenant ON appointments(tenant_id);
            CREATE INDEX IF NOT EXISTS idx_appointments_source ON appointments(source);
            """,
            # Parche 14: tenant_id en treatment_types (idempotente)
            """
            DO $$
            BEGIN
                IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema = 'public' AND table_name = 'treatment_types' AND column_name = 'tenant_id') THEN
                    ALTER TABLE treatment_types ADD COLUMN tenant_id INTEGER DEFAULT 1;
                    UPDATE treatment_types SET tenant_id = 1 WHERE tenant_id IS NULL;
                    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema = 'public' AND table_name = 'tenants') THEN
                        ALTER TABLE treatment_types ADD CONSTRAINT fk_treatment_types_tenant FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE;
                    END IF;
                END IF;
            END $$;
            CREATE INDEX IF NOT EXISTS idx_treatment_types_tenant ON treatment_types(tenant_id);
            """,
            # Parche 15: tenant_id en chat_messages (conversaciones por clínica, buffer/override independientes)
            """
            DO $$
            BEGIN
                IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema = 'public' AND table_name = 'chat_messages' AND column_name = 'tenant_id') THEN
                    ALTER TABLE chat_messages ADD COLUMN tenant_id INTEGER DEFAULT 1;
                    UPDATE chat_messages SET tenant_id = 1 WHERE tenant_id IS NULL;
                    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema = 'public' AND table_name = 'tenants') THEN
                        ALTER TABLE chat_messages ADD CONSTRAINT fk_chat_messages_tenant FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE;
                    END IF;
                END IF;
            END $$;
            CREATE INDEX IF NOT EXISTS idx_chat_messages_tenant_id ON chat_messages(tenant_id);
            CREATE INDEX IF NOT EXISTS idx_chat_messages_tenant_from_created ON chat_messages(tenant_id, from_number, created_at DESC);
            """,
            # Parche 16: Chatwoot - chat_conversations y credentials (spec version_estable_clinicas)
            """
            CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
            CREATE TABLE IF NOT EXISTS chat_conversations (
                id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
                tenant_id INTEGER NOT NULL,
                channel VARCHAR(50) NOT NULL DEFAULT 'whatsapp',
                channel_source VARCHAR(32) DEFAULT 'whatsapp',
                provider VARCHAR(32) NOT NULL DEFAULT 'ycloud',
                external_user_id VARCHAR(255) NOT NULL,
                external_chatwoot_id INTEGER,
                external_account_id INTEGER,
                display_name VARCHAR(255),
                status VARCHAR(20) DEFAULT 'open',
                human_override_until TIMESTAMP WITH TIME ZONE,
                meta JSONB DEFAULT '{}',
                last_message_at TIMESTAMP WITH TIME ZONE,
                last_message_preview VARCHAR(255),
                last_read_at TIMESTAMP WITH TIME ZONE DEFAULT '1970-01-01 00:00:00+00',
                created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
            );
            CREATE INDEX IF NOT EXISTS idx_chat_conv_tenant ON chat_conversations(tenant_id);
            CREATE INDEX IF NOT EXISTS idx_chat_conv_tenant_channel ON chat_conversations(tenant_id, channel);
            CREATE UNIQUE INDEX IF NOT EXISTS idx_chat_conv_tenant_channel_user ON chat_conversations(tenant_id, channel, external_user_id);
            """,
            # Parche 16b: FK tenant_id en chat_conversations si existe tenants
            """
            DO $$
            BEGIN
                IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'chat_conversations_tenant_id_fkey') AND EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'tenants') THEN
                    ALTER TABLE chat_conversations ADD CONSTRAINT chat_conversations_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE;
                END IF;
            END $$;
            """,
            # Parche 17: Extensión chat_messages para Chatwoot (conversation_id nullable; no tocar from_number)
            """
            DO $$
            BEGIN
                IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema = 'public' AND table_name = 'chat_messages' AND column_name = 'conversation_id') THEN
                    ALTER TABLE chat_messages ADD COLUMN conversation_id UUID NULL;
                    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema = 'public' AND table_name = 'chat_conversations') THEN
                        ALTER TABLE chat_messages ADD CONSTRAINT chat_messages_conversation_id_fkey FOREIGN KEY (conversation_id) REFERENCES chat_conversations(id) ON DELETE SET NULL;
                    END IF;
                END IF;
                IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema = 'public' AND table_name = 'chat_messages' AND column_name = 'content_attributes') THEN
                    ALTER TABLE chat_messages ADD COLUMN content_attributes JSONB DEFAULT '[]'::jsonb;
                ELSE
                    -- Si ya existe pero el default es {}, lo cambiamos a []
                    ALTER TABLE chat_messages ALTER COLUMN content_attributes SET DEFAULT '[]'::jsonb;
                    -- Fix existing {} to []
                    UPDATE chat_messages SET content_attributes = '[]'::jsonb WHERE content_attributes = '{}'::jsonb OR content_attributes IS NULL;
                END IF;
                IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema = 'public' AND table_name = 'chat_messages' AND column_name = 'platform_metadata') THEN
                    ALTER TABLE chat_messages ADD COLUMN platform_metadata JSONB DEFAULT '{}';
                END IF;
                IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema = 'public' AND table_name = 'chat_messages' AND column_name = 'platform_message_id') THEN
                    ALTER TABLE chat_messages ADD COLUMN platform_message_id VARCHAR(255);
                END IF;
            END $$;
            CREATE INDEX IF NOT EXISTS idx_chat_messages_conversation_id ON chat_messages(conversation_id) WHERE conversation_id IS NOT NULL;
            """,
            # Parche 18: Tabla credentials (Vault por tenant)
            """
            CREATE TABLE IF NOT EXISTS credentials (
                id SERIAL PRIMARY KEY,
                tenant_id INTEGER NOT NULL,
                name VARCHAR(255) NOT NULL,
                value TEXT,
                created_at TIMESTAMPTZ DEFAULT NOW(),
                updated_at TIMESTAMPTZ DEFAULT NOW(),
                UNIQUE(tenant_id, name)
            );
            CREATE INDEX IF NOT EXISTS idx_credentials_tenant ON credentials(tenant_id);
            CREATE INDEX IF NOT EXISTS idx_credentials_tenant_name ON credentials(tenant_id, name);
            """,
            # Parche 19: Asegurar last_read_at en chat_conversations (Spec 14 / Notificaciones)
            """
            DO $$ 
            BEGIN 
                IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='chat_conversations' AND column_name='last_read_at') THEN
                    ALTER TABLE chat_conversations ADD COLUMN last_read_at TIMESTAMP WITH TIME ZONE DEFAULT '1970-01-01 00:00:00+00';
                END IF;
            END $$;
            """,
            # Parche 20: Meta Ads - Atribución 360 en tabla patients (idempotente)
            """
            DO $$
            BEGIN
                IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema = 'public' AND table_name = 'patients' AND column_name = 'acquisition_source') THEN
                    ALTER TABLE patients ADD COLUMN acquisition_source VARCHAR(50) DEFAULT 'ORGANIC';
                END IF;
                IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema = 'public' AND table_name = 'patients' AND column_name = 'meta_campaign_id') THEN
                    ALTER TABLE patients ADD COLUMN meta_campaign_id VARCHAR(255);
                END IF;
                IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema = 'public' AND table_name = 'patients' AND column_name = 'meta_ad_id') THEN
                    ALTER TABLE patients ADD COLUMN meta_ad_id VARCHAR(255);
                END IF;
                IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema = 'public' AND table_name = 'patients' AND column_name = 'meta_ad_headline') THEN
                    ALTER TABLE patients ADD COLUMN meta_ad_headline TEXT;
                END IF;
                IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema = 'public' AND table_name = 'patients' AND column_name = 'meta_ad_body') THEN
                    ALTER TABLE patients ADD COLUMN meta_ad_body TEXT;
                END IF;
            END $$;
            CREATE INDEX IF NOT EXISTS idx_patients_acquisition_source ON patients(acquisition_source);
            """,
            # Parche 20: Soporte de Identidad Multi-plataforma (JSONB)
            """
            DO $$
            BEGIN
                IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema = 'public' AND table_name = 'patients' AND column_name = 'external_ids') THEN
                    ALTER TABLE patients ADD COLUMN external_ids JSONB DEFAULT '{}';
                    CREATE INDEX IF NOT EXISTS idx_patients_external_ids ON patients USING GIN (external_ids);
                END IF;
            END $$;
            """,
            # Parche 21: Ventana de 24h - Tracking del último mensaje del usuario
            """
            DO $$
            BEGIN
                IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'chat_conversations' AND column_name = 'last_user_message_at') THEN
                    ALTER TABLE chat_conversations ADD COLUMN last_user_message_at TIMESTAMP WITH TIME ZONE;
                    -- Inicializar con el last_message_at actual para no romper ventanas existentes
                    UPDATE chat_conversations SET last_user_message_at = last_message_at WHERE last_user_message_at IS NULL;
                END IF;
            END $$;
            """,
            # Parche 22: Fix Critical - Agregar last_derivhumano_at (Spec Handoff Banner)
            """
            DO $$ 
            BEGIN 
                IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='chat_conversations' AND column_name='last_derivhumano_at') THEN
                    ALTER TABLE chat_conversations ADD COLUMN last_derivhumano_at TIMESTAMP WITH TIME ZONE;
                END IF;
            END $$;
            """,
            # Parche 23: Soporte para Timezones en Tenants (HSM Scheduling)
            """
            DO $$ 
            BEGIN 
                IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='tenants' AND column_name='timezone') THEN
                    ALTER TABLE tenants ADD COLUMN timezone VARCHAR(100) DEFAULT 'America/Argentina/Buenos_Aires';
                END IF;
            END $$;
            """,
            # Parche 24: Tracking de Feedback en Citas
            """
            DO $$ 
            BEGIN 
                IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='appointments' AND column_name='feedback_sent') THEN
                    ALTER TABLE appointments ADD COLUMN feedback_sent BOOLEAN DEFAULT FALSE;
                END IF;
            END $$;
            """,
            # Parche 25: Tabla de Logs de Automatización (HSM Audit)
            """
            CREATE TABLE IF NOT EXISTS automation_logs (
                id SERIAL PRIMARY KEY,
                tenant_id INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
                patient_id INTEGER REFERENCES patients(id) ON DELETE SET NULL,
                trigger_type VARCHAR(50) NOT NULL,
                target_id VARCHAR(100),
                status VARCHAR(20) DEFAULT 'pending',
                meta JSONB DEFAULT '{}',
                error_details TEXT,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
            );
            CREATE INDEX IF NOT EXISTS idx_auto_logs_tenant ON automation_logs(tenant_id);
            CREATE INDEX IF NOT EXISTS idx_auto_logs_trigger ON automation_logs(trigger_type);
            CREATE INDEX IF NOT EXISTS idx_auto_logs_target ON automation_logs(target_id);
            """,
            # Parche 26: Asegurar base_price en treatment_types para Revenue Estimado
            """
            DO $$ 
            BEGIN 
                IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='treatment_types' AND column_name='base_price') THEN
                    ALTER TABLE treatment_types ADD COLUMN base_price DECIMAL(12,2) DEFAULT 0;
                END IF;
            END $$;
            """,
        ]

        async with self.pool.acquire() as conn:
            async with conn.transaction():
                for i, patch in enumerate(patches):
                    try:
                        await conn.execute(patch)
                    except Exception as e:
                        logger.error(f"❌ Error aplicando parche evolutivo {i+1}: {e}")
                        # En evolución, a veces es mejor fallar rápido para no corromper
                        raise e

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

    async def ensure_patient_exists(self, phone_number: Optional[str], tenant_id: int, first_name: str = 'Visitante', status: str = 'guest', external_id: Optional[dict] = None):
        """
        Asegura que exista un registro de paciente/lead.
        Soporta búsqueda por phone_number (WhatsApp) o por external_id (Meta/IG/FB).
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

        # 3. Si no existe, crear nuevo (Lead o Paciente según status)
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
