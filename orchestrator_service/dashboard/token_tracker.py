"""
Token Tracker - Sistema de tracking de tokens y costos OpenAI
"""

import asyncio
import os
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from decimal import Decimal
import json

logger = logging.getLogger(__name__)

# Precios por 1M tokens (USD) - Actualizado Marzo 2026 v2
# Providers: openai, deepseek
logger.info("📦 MODEL_PRICING v2 loaded — OpenAI + DeepSeek models")
MODEL_PRICING = {
    # ============ OPENAI ============
    # --- GPT-5.4 Serie (flagship, Marzo 2026) ---
    "gpt-5.4": {"provider": "openai", "input": Decimal("0.00250"), "output": Decimal("0.01500"), "context": 1000000, "type": "text", "description": "GPT-5.4 Flagship (1M ctx)"},
    "gpt-5.4-pro": {"provider": "openai", "input": Decimal("0.00500"), "output": Decimal("0.03000"), "context": 1000000, "type": "text", "description": "GPT-5.4 Pro — Maximo razonamiento"},
    "gpt-5.4-mini": {"provider": "openai", "input": Decimal("0.00025"), "output": Decimal("0.00200"), "context": 1000000, "type": "text", "description": "GPT-5.4 Mini — Rapido y barato (RECOMENDADO)"},
    "gpt-5.4-nano": {"provider": "openai", "input": Decimal("0.00010"), "output": Decimal("0.00080"), "context": 500000, "type": "text", "description": "GPT-5.4 Nano — Ultra economico"},
    # --- GPT-5.3 ---
    "gpt-5.3": {"provider": "openai", "input": Decimal("0.00200"), "output": Decimal("0.01200"), "context": 400000, "type": "text", "description": "GPT-5.3 Balanceado"},
    # --- GPT-5 ---
    "gpt-5": {"provider": "openai", "input": Decimal("0.00250"), "output": Decimal("0.01500"), "context": 400000, "type": "text", "description": "GPT-5 Original"},
    "gpt-5-mini": {"provider": "openai", "input": Decimal("0.00025"), "output": Decimal("0.00200"), "context": 400000, "type": "text", "description": "GPT-5 Mini"},
    # --- GPT-4o (legacy) ---
    "gpt-4o-mini": {"provider": "openai", "input": Decimal("0.00015"), "output": Decimal("0.00060"), "context": 128000, "type": "text", "description": "GPT-4o Mini — Legacy economico"},
    "gpt-4o": {"provider": "openai", "input": Decimal("0.00250"), "output": Decimal("0.01000"), "context": 128000, "type": "text", "description": "GPT-4o Legacy"},
    # --- Realtime (voice) ---
    "gpt-4o-mini-realtime-preview": {"provider": "openai", "input": Decimal("0.00060"), "output": Decimal("0.00240"), "context": 128000, "type": "realtime", "description": "Realtime Mini — Voz"},
    "gpt-4o-realtime-preview": {"provider": "openai", "input": Decimal("0.00500"), "output": Decimal("0.02000"), "context": 128000, "type": "realtime", "description": "Realtime Premium — Voz"},

    # ============ DEEPSEEK ============
    "deepseek-chat": {"provider": "deepseek", "input": Decimal("0.00028"), "output": Decimal("0.00042"), "context": 128000, "type": "text", "description": "DeepSeek V4 Chat — Muy barato, excelente"},
    "deepseek-reasoner": {"provider": "deepseek", "input": Decimal("0.00028"), "output": Decimal("0.00042"), "context": 128000, "type": "text", "description": "DeepSeek V4 Reasoner — Razonamiento profundo"},
}

# Backward compat alias
OPENAI_PRICING = MODEL_PRICING


async def track_service_usage(pool, tenant_id: int, model: str, input_tokens: int, output_tokens: int, source: str = "unknown", phone: str = "system"):
    """
    Helper function to track token usage from ANY service (nova voice, daily analysis, memory extraction).
    Can be called from anywhere without importing the full TokenTracker class.
    """
    try:
        from dashboard.token_tracker import token_tracker
        if not token_tracker:
            return
        cost = token_tracker.calculate_cost(model, input_tokens, output_tokens)
        total = input_tokens + output_tokens
        usage = TokenUsage(
            conversation_id=f"{source}_{tenant_id}",
            patient_phone=phone,
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total,
            cost_usd=cost,
            timestamp=datetime.utcnow(),
            tenant_id=tenant_id,
        )
        await token_tracker.track_usage(usage)
        # Update tenant totals
        await pool.execute(
            "UPDATE tenants SET total_tokens_used = COALESCE(total_tokens_used, 0) + $1, total_tool_calls = COALESCE(total_tool_calls, 0) + 1 WHERE id = $2",
            total, tenant_id
        )
        logger.info(f"📊 Service tokens tracked: {source} | {model} | {total} tokens | ${cost}")
    except Exception as e:
        logger.warning(f"⚠️ Service token tracking failed (non-fatal): {e}")

@dataclass
class TokenUsage:
    """Registro de uso de tokens para una conversación"""
    conversation_id: str
    patient_phone: str
    model: str
    input_tokens: int
    output_tokens: int
    total_tokens: int
    cost_usd: Decimal
    timestamp: datetime
    tenant_id: int

class TokenTracker:
    """Sistema de tracking de tokens y costos"""
    
    def __init__(self, db_pool):
        self.db_pool = db_pool
        self.logger = logging.getLogger(__name__)
        self._table_ready = False

    async def ensure_table(self):
        """Crea la tabla de tracking de tokens si no existe"""
        if self._table_ready or not self.db_pool:
            return
        create_table_sql = """
        CREATE TABLE IF NOT EXISTS token_usage (
            id SERIAL PRIMARY KEY,
            conversation_id VARCHAR(255) NOT NULL,
            patient_phone VARCHAR(50) NOT NULL,
            model VARCHAR(50) NOT NULL,
            input_tokens INTEGER NOT NULL,
            output_tokens INTEGER NOT NULL,
            total_tokens INTEGER NOT NULL,
            cost_usd DECIMAL(10,6) NOT NULL,
            timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            tenant_id INTEGER NOT NULL,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        );
        CREATE INDEX IF NOT EXISTS idx_token_usage_conversation ON token_usage(conversation_id);
        CREATE INDEX IF NOT EXISTS idx_token_usage_patient ON token_usage(patient_phone);
        CREATE INDEX IF NOT EXISTS idx_token_usage_timestamp ON token_usage(timestamp);
        CREATE INDEX IF NOT EXISTS idx_token_usage_tenant ON token_usage(tenant_id);
        """
        try:
            async with self.db_pool.acquire() as conn:
                await conn.execute(create_table_sql)
            self._table_ready = True
            self.logger.info("✅ Tabla de token_usage verificada/creada")
        except Exception as e:
            self.logger.error(f"❌ Error creando tabla token_usage: {e}")
    
    def calculate_cost(self, model: str, input_tokens: int, output_tokens: int) -> Decimal:
        """Calcula costo en USD basado en tokens y modelo"""
        if model not in MODEL_PRICING:
            model = "gpt-4o-mini"  # Fallback

        pricing = MODEL_PRICING[model]
        
        # Convertir tokens a miles y calcular costo
        input_cost = (Decimal(input_tokens) / 1000) * pricing["input"]
        output_cost = (Decimal(output_tokens) / 1000) * pricing["output"]
        
        total_cost = input_cost + output_cost
        return total_cost.quantize(Decimal('0.000001'))  # 6 decimales
    
    async def track_usage(self, usage: TokenUsage):
        """Registra uso de tokens en la base de datos"""
        try:
            async with self.db_pool.acquire() as conn:
                await conn.execute("""
                    INSERT INTO token_usage 
                    (conversation_id, patient_phone, model, input_tokens, output_tokens, 
                     total_tokens, cost_usd, timestamp, tenant_id)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                """,
                usage.conversation_id,
                usage.patient_phone,
                usage.model,
                usage.input_tokens,
                usage.output_tokens,
                usage.total_tokens,
                float(usage.cost_usd),  # Convertir a float para PostgreSQL
                usage.timestamp,
                usage.tenant_id
                )
                
                self.logger.debug(f"✅ Tokens trackeados: {usage.total_tokens} tokens, ${usage.cost_usd}")
                return True
        except Exception as e:
            self.logger.error(f"❌ Error trackeando tokens: {e}")
            return False
    
    async def get_daily_usage(self, tenant_id: int, days: int = 30) -> List[Dict]:
        """Obtiene uso diario de tokens para un tenant"""
        try:
            async with self.db_pool.acquire() as conn:
                rows = await conn.fetch("""
                    SELECT 
                        DATE(timestamp) as date,
                        SUM(input_tokens) as total_input,
                        SUM(output_tokens) as total_output,
                        SUM(total_tokens) as total_tokens,
                        SUM(cost_usd) as total_cost,
                        COUNT(*) as conversations
                    FROM token_usage
                    WHERE tenant_id = $1 
                    AND timestamp >= NOW() - make_interval(days => $2)
                    GROUP BY DATE(timestamp)
                    ORDER BY date DESC
                """, tenant_id, days)
                
                result = []
                for row in rows:
                    result.append({
                        "date": row["date"].isoformat() if row["date"] else None,
                        "input_tokens": row["total_input"] or 0,
                        "output_tokens": row["total_output"] or 0,
                        "total_tokens": row["total_tokens"] or 0,
                        "cost_usd": float(row["total_cost"] or 0),
                        "conversations": row["conversations"] or 0
                    })
                
                return result
        except Exception as e:
            self.logger.error(f"❌ Error obteniendo uso diario: {e}")
            return []
    
    async def get_model_usage(self, tenant_id: int, days: int = 30) -> List[Dict]:
        """Obtiene uso por modelo"""
        try:
            async with self.db_pool.acquire() as conn:
                rows = await conn.fetch("""
                    SELECT 
                        model,
                        SUM(input_tokens) as total_input,
                        SUM(output_tokens) as total_output,
                        SUM(total_tokens) as total_tokens,
                        SUM(cost_usd) as total_cost,
                        COUNT(*) as conversations
                    FROM token_usage
                    WHERE tenant_id = $1 
                    AND timestamp >= NOW() - make_interval(days => $2)
                    GROUP BY model
                    ORDER BY total_tokens DESC
                """, tenant_id, days)
                
                result = []
                for row in rows:
                    result.append({
                        "model": row["model"],
                        "input_tokens": row["total_input"] or 0,
                        "output_tokens": row["total_output"] or 0,
                        "total_tokens": row["total_tokens"] or 0,
                        "cost_usd": float(row["total_cost"] or 0),
                        "conversations": row["conversations"] or 0,
                        "description": OPENAI_PRICING.get(row["model"], {}).get("description", "Desconocido")
                    })
                
                return result
        except Exception as e:
            self.logger.error(f"❌ Error obteniendo uso por modelo: {e}")
            return []
    
    async def get_total_metrics(self, tenant_id: int, days: int = 30) -> Dict:
        """Obtiene métricas totales"""
        try:
            async with self.db_pool.acquire() as conn:
                # Totales
                total_row = await conn.fetchrow("""
                    SELECT 
                        SUM(input_tokens) as total_input,
                        SUM(output_tokens) as total_output,
                        SUM(total_tokens) as total_tokens,
                        SUM(cost_usd) as total_cost,
                        COUNT(*) as total_conversations,
                        AVG(total_tokens) as avg_tokens_per_conversation,
                        AVG(cost_usd) as avg_cost_per_conversation
                    FROM token_usage
                    WHERE tenant_id = $1 
                    AND timestamp >= NOW() - make_interval(days => $2)
                """, tenant_id, days)
                
                # Hoy
                today_row = await conn.fetchrow("""
                    SELECT 
                        SUM(input_tokens) as today_input,
                        SUM(output_tokens) as today_output,
                        SUM(total_tokens) as today_tokens,
                        SUM(cost_usd) as today_cost,
                        COUNT(*) as today_conversations
                    FROM token_usage
                    WHERE tenant_id = $1 
                    AND DATE(timestamp) = CURRENT_DATE
                """, tenant_id)
                
                # Mes actual
                month_row = await conn.fetchrow("""
                    SELECT 
                        SUM(cost_usd) as month_cost
                    FROM token_usage
                    WHERE tenant_id = $1 
                    AND EXTRACT(MONTH FROM timestamp) = EXTRACT(MONTH FROM CURRENT_DATE)
                    AND EXTRACT(YEAR FROM timestamp) = EXTRACT(YEAR FROM CURRENT_DATE)
                """, tenant_id)
                
                return {
                    "totals": {
                        "input_tokens": total_row["total_input"] or 0,
                        "output_tokens": total_row["total_output"] or 0,
                        "total_tokens": total_row["total_tokens"] or 0,
                        "total_cost_usd": float(total_row["total_cost"] or 0),
                        "total_conversations": total_row["total_conversations"] or 0,
                        "avg_tokens_per_conversation": float(total_row["avg_tokens_per_conversation"] or 0),
                        "avg_cost_per_conversation": float(total_row["avg_cost_per_conversation"] or 0)
                    },
                    "today": {
                        "input_tokens": today_row["today_input"] or 0,
                        "output_tokens": today_row["today_output"] or 0,
                        "total_tokens": today_row["today_tokens"] or 0,
                        "cost_usd": float(today_row["today_cost"] or 0),
                        "conversations": today_row["today_conversations"] or 0
                    },
                    "current_month": {
                        "cost_usd": float(month_row["month_cost"] or 0)
                    },
                    "period_days": days
                }
        except Exception as e:
            self.logger.error(f"❌ Error obteniendo métricas totales: {e}")
            return {}
    
    async def get_service_breakdown(self, tenant_id: int, days: int = 30) -> List[Dict]:
        """Obtiene desglose de consumo por servicio (agente WhatsApp, Nova voice, daily analysis, memory)"""
        try:
            async with self.db_pool.acquire() as conn:
                rows = await conn.fetch("""
                    SELECT
                        CASE
                            WHEN conversation_id LIKE 'nova_voice_%' THEN 'Nova Voz'
                            WHEN conversation_id LIKE 'nova_daily_analysis_%' THEN 'Análisis Diario'
                            WHEN conversation_id LIKE 'patient_memory_%' THEN 'Memoria Pacientes'
                            ELSE 'Agente WhatsApp/IG/FB'
                        END as service,
                        model,
                        SUM(input_tokens) as total_input,
                        SUM(output_tokens) as total_output,
                        SUM(total_tokens) as total_tokens,
                        SUM(cost_usd) as total_cost,
                        COUNT(*) as calls
                    FROM token_usage
                    WHERE tenant_id = $1
                    AND timestamp >= NOW() - make_interval(days => $2)
                    GROUP BY service, model
                    ORDER BY total_cost DESC
                """, tenant_id, days)

                result = []
                for row in rows:
                    result.append({
                        "service": row["service"],
                        "model": row["model"],
                        "input_tokens": row["total_input"] or 0,
                        "output_tokens": row["total_output"] or 0,
                        "total_tokens": row["total_tokens"] or 0,
                        "cost_usd": float(row["total_cost"] or 0),
                        "calls": row["calls"] or 0,
                    })
                return result
        except Exception as e:
            self.logger.error(f"❌ Error obteniendo desglose por servicio: {e}")
            return []

    async def get_available_models(self, model_type: str = None) -> List[Dict]:
        """Fetches live models from OpenAI + DeepSeek APIs. Falls back to hardcoded list on error."""
        models = []

        # 1. Fetch from OpenAI GET /v1/models
        openai_key = os.getenv("OPENAI_API_KEY", "")
        if openai_key:
            try:
                import httpx
                async with httpx.AsyncClient(timeout=10) as client:
                    resp = await client.get("https://api.openai.com/v1/models", headers={"Authorization": f"Bearer {openai_key}"})
                    if resp.status_code == 200:
                        data = resp.json().get("data", [])
                        for m in data:
                            mid = m.get("id", "")
                            # ONLY show models in our curated MODEL_PRICING list
                            # This prevents showing retired/legacy/snapshot models
                            if mid not in MODEL_PRICING:
                                continue

                            known = MODEL_PRICING.get(mid, {})
                            is_realtime = "realtime" in mid
                            if model_type == "realtime" and not is_realtime:
                                continue
                            if model_type == "text" and is_realtime:
                                continue

                            models.append({
                                "id": mid,
                                "provider": "openai",
                                "description": known.get("description", mid),
                                "context_window": known.get("context", 128000),
                                "type": "realtime" if is_realtime else "text",
                                "input_price_per_1k": float(known.get("input", Decimal("0.001"))),
                                "output_price_per_1k": float(known.get("output", Decimal("0.003"))),
                            })
            except Exception as e:
                logger.warning(f"Failed to fetch OpenAI models: {e}")

        # 2. DeepSeek models — add from MODEL_PRICING if API key exists
        deepseek_key = os.getenv("DEEPSEEK_API_KEY", "")
        logger.info(f"🔍 DeepSeek key configured: {bool(deepseek_key)} (len={len(deepseek_key)})")
        if deepseek_key and model_type != "realtime":
            for mid, info in MODEL_PRICING.items():
                if info.get("provider") == "deepseek":
                    models.append({
                        "id": mid,
                        "provider": "deepseek",
                        "description": info["description"],
                        "context_window": info["context"],
                        "type": "text",
                        "input_price_per_1k": float(info["input"]),
                        "output_price_per_1k": float(info["output"]),
                    })
            logger.info(f"✅ DeepSeek models added: {[m['id'] for m in models if m['provider'] == 'deepseek']}")

        # 3. Fallback: if API calls failed, use hardcoded list
        if not models:
            for model_id, info in MODEL_PRICING.items():
                if model_type and info.get("type") != model_type:
                    continue
                provider = info.get("provider", "openai")
                if provider == "deepseek" and not deepseek_key:
                    continue
                models.append({
                    "id": model_id,
                    "provider": provider,
                    "description": info["description"],
                    "context_window": info["context"],
                    "type": info.get("type", "text"),
                    "input_price_per_1k": float(info["input"]),
                    "output_price_per_1k": float(info["output"]),
                })

        # Sort: DeepSeek first (cheaper), then by price
        return sorted(models, key=lambda x: (0 if x["provider"] == "deepseek" else 1, x["input_price_per_1k"]))

# Instancia global del tracker
token_tracker = None

def init_token_tracker(db_pool):
    """Inicializa el tracker global"""
    global token_tracker
    token_tracker = TokenTracker(db_pool)
    return token_tracker