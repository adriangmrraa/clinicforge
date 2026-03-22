"""
Token Tracker - Sistema de tracking de tokens y costos OpenAI
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from decimal import Decimal
import json

logger = logging.getLogger(__name__)

# Precios por 1K tokens (USD) - Actualizado Marzo 2026
# Fuente: https://openai.com/pricing — Lista completa para selector en dashboard
OPENAI_PRICING = {
    # --- GPT-5 Serie (flagship) ---
    "gpt-5.4": {"input": Decimal("0.00250"), "output": Decimal("0.01500"), "context": 1000000, "description": "GPT-5.4 - Flagship, razonamiento complejo"},
    "gpt-5": {"input": Decimal("0.00250"), "output": Decimal("0.01500"), "context": 400000, "description": "GPT-5 - Chat principal"},
    "gpt-5-mini": {"input": Decimal("0.00025"), "output": Decimal("0.00200"), "context": 400000, "description": "GPT-5 Mini - Baja latencia y costo"},
    "gpt-5.3": {"input": Decimal("0.00200"), "output": Decimal("0.01200"), "context": 400000, "description": "GPT-5.3 - Balanceado"},
    "gpt-5.2": {"input": Decimal("0.00150"), "output": Decimal("0.01000"), "context": 400000, "description": "GPT-5.2 - Versión estándar"},
    "gpt-5.2-instant": {"input": Decimal("0.00150"), "output": Decimal("0.01000"), "context": 400000, "description": "GPT-5.2 Instant - Respuesta rápida"},
    "gpt-5.2-thinking": {"input": Decimal("0.00200"), "output": Decimal("0.01200"), "context": 400000, "description": "GPT-5.2 Thinking - Razonamiento extendido"},
    # --- GPT-4o Serie ---
    "gpt-4o-mini": {"input": Decimal("0.00015"), "output": Decimal("0.00060"), "context": 128000, "description": "GPT-4o Mini - Más rápido y económico"},
    "gpt-4o": {"input": Decimal("0.00250"), "output": Decimal("0.01000"), "context": 128000, "description": "GPT-4o - Balanceado"},
    "gpt-4o-2024-11-20": {"input": Decimal("0.00250"), "output": Decimal("0.01000"), "context": 128000, "description": "GPT-4o (Nov 2024)"},
    "gpt-4o-mini-2024-07-18": {"input": Decimal("0.00015"), "output": Decimal("0.00060"), "context": 128000, "description": "GPT-4o Mini (Jul 2024)"},
    # --- GPT-4 Serie ---
    "gpt-4-turbo": {"input": Decimal("0.01000"), "output": Decimal("0.03000"), "context": 128000, "description": "GPT-4 Turbo - Alta capacidad"},
    "gpt-4-turbo-preview": {"input": Decimal("0.01000"), "output": Decimal("0.03000"), "context": 128000, "description": "GPT-4 Turbo Preview"},
    # --- GPT-3.5 ---
    "gpt-3.5-turbo": {"input": Decimal("0.00050"), "output": Decimal("0.00150"), "context": 16385, "description": "GPT-3.5 Turbo - Más económico"},
    # --- o1 Serie (razonamiento) ---
    "o1-preview": {"input": Decimal("0.01500"), "output": Decimal("0.06000"), "context": 128000, "description": "o1-preview - Razonamiento avanzado"},
    "o1-mini": {"input": Decimal("0.00300"), "output": Decimal("0.01200"), "context": 128000, "description": "o1-mini - Razonamiento económico"},
}

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
        if model not in OPENAI_PRICING:
            model = "gpt-4o-mini"  # Fallback a nuestro modelo por defecto
        
        pricing = OPENAI_PRICING[model]
        
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
    
    async def get_available_models(self) -> List[Dict]:
        """Obtiene lista completa de modelos OpenAI para selector en dashboard (fuente de verdad: DB)"""
        models = []
        for model_id, info in OPENAI_PRICING.items():
            models.append({
                "id": model_id,
                "description": info["description"],
                "context_window": info["context"],
                "input_price_per_1k": float(info["input"]),
                "output_price_per_1k": float(info["output"]),
                "input_price_per_1m": float(info["input"] * 1000),
                "output_price_per_1m": float(info["output"] * 1000)
            })
        
        return sorted(models, key=lambda x: x["input_price_per_1k"])

# Instancia global del tracker
token_tracker = None

def init_token_tracker(db_pool):
    """Inicializa el tracker global"""
    global token_tracker
    token_tracker = TokenTracker(db_pool)
    return token_tracker