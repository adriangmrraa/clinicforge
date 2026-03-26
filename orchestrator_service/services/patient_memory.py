"""
Patient Memory System — Lightweight persistent memory for dental AI agent.
Inspired by Mem0/OpenClaw but custom-built for ClinicForge.
Uses existing PostgreSQL, no external dependencies.
Cost: ~$0.0001 per memory extraction (gpt-4o-mini, ~200 tokens)
"""
import logging
import json
import os
from datetime import datetime
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)


async def ensure_memory_table(pool):
    """Create patient_memories table if not exists. Called once on startup."""
    await pool.execute("""
        CREATE TABLE IF NOT EXISTS patient_memories (
            id SERIAL PRIMARY KEY,
            tenant_id INTEGER NOT NULL,
            patient_phone TEXT NOT NULL,
            memory TEXT NOT NULL,
            category TEXT DEFAULT 'general',
            confidence REAL DEFAULT 0.8,
            source TEXT DEFAULT 'conversation',
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW(),
            is_active BOOLEAN DEFAULT TRUE
        )
    """)
    # Index for fast retrieval
    await pool.execute("""
        CREATE INDEX IF NOT EXISTS idx_patient_memories_phone_tenant
        ON patient_memories (patient_phone, tenant_id) WHERE is_active = TRUE
    """)
    logger.info("patient_memories table ensured")


async def get_memories(pool, patient_phone: str, tenant_id: int, limit: int = 10) -> List[str]:
    """Retrieve active memories for a patient. Returns list of memory strings."""
    rows = await pool.fetch("""
        SELECT memory, category FROM patient_memories
        WHERE patient_phone = $1 AND tenant_id = $2 AND is_active = TRUE
        ORDER BY confidence DESC, updated_at DESC
        LIMIT $3
    """, patient_phone, tenant_id, limit)
    return [r['memory'] for r in rows] if rows else []


async def format_memories_for_prompt(pool, patient_phone: str, tenant_id: int) -> str:
    """Get memories formatted for injection into system prompt or user input."""
    memories = await get_memories(pool, patient_phone, tenant_id, limit=8)
    if not memories:
        return ""
    lines = ["MEMORIA DEL PACIENTE (datos aprendidos de conversaciones anteriores):"]
    for m in memories:
        lines.append(f"• {m}")
    lines.append("Usá esta información para personalizar la interacción. NO repitas estos datos al paciente a menos que sea relevante.")
    return "\n".join(lines)


async def extract_and_store_memories(
    pool,
    patient_phone: str,
    tenant_id: int,
    user_message: str,
    ai_response: str,
    patient_name: str = ""
):
    """
    After each conversation turn, extract memorable facts and store them.
    Uses gpt-4o-mini for extraction (~200 tokens, ~$0.0001).
    Only extracts if the conversation contains extractable information.
    """
    import httpx

    # Quick filter: skip short/trivial messages
    combined = f"{user_message} {ai_response}"
    if len(combined) < 50:
        return

    # Skip if message is just scheduling logistics
    skip_patterns = ["a las", "para el", "dale", "perfecto", "gracias", "chau", "hola", "si", "no", "ok"]
    user_lower = user_message.lower().strip()
    if user_lower in skip_patterns or len(user_message) < 10:
        return

    # Check existing memories to avoid duplicates
    existing = await get_memories(pool, patient_phone, tenant_id, limit=20)
    existing_text = "\n".join(existing) if existing else "Ninguna"

    api_key = os.getenv("OPENAI_API_KEY", "")
    if not api_key:
        return

    extraction_prompt = f"""Analiza esta conversación entre un paciente dental y el asistente virtual.
Extrae SOLO hechos nuevos y relevantes sobre el paciente que serían útiles para futuras interacciones.

Conversación:
Paciente: {user_message}
Asistente: {ai_response}

Memorias existentes del paciente:
{existing_text}

Reglas:
- Solo extraer hechos NUEVOS (no repetir los existentes)
- Solo hechos sobre el PACIENTE (no sobre el sistema o la clínica)
- Categorías válidas: preferencia, miedo, salud, familia, logistica, comportamiento
- Ejemplos de buenos hechos: "Le tiene miedo a las agujas", "Prefiere turnos de mañana", "Tiene una hija de 5 años que también se atiende", "Es alérgico a la penicilina", "Trabaja de noche, solo puede venir de mañana", "Viene derivado del Dr. García"
- NO extraer: datos administrativos (nombre, DNI, teléfono), citas específicas (horarios), saludos
- Si no hay nada nuevo que memorizar, retornar lista vacía

Retorna JSON: {{"memories": [{{"text": "...", "category": "..."}}]}}
Si no hay nada nuevo: {{"memories": []}}
Solo JSON, sin explicaciones."""

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json={
                    "model": "gpt-4o-mini",
                    "messages": [{"role": "user", "content": extraction_prompt}],
                    "temperature": 0,
                    "max_tokens": 200,
                    "response_format": {"type": "json_object"}
                }
            )
            result = resp.json()
            # Track token usage
            usage_data = result.get("usage", {})
            if usage_data:
                try:
                    from dashboard.token_tracker import track_service_usage
                    await track_service_usage(
                        pool, tenant_id, "gpt-4o-mini",
                        usage_data.get("prompt_tokens", 0), usage_data.get("completion_tokens", 0),
                        source="patient_memory", phone=patient_phone
                    )
                except Exception:
                    pass
            content = result.get("choices", [{}])[0].get("message", {}).get("content", "{}")
            data = json.loads(content)
            new_memories = data.get("memories", [])

            for mem in new_memories:
                text = mem.get("text", "").strip()
                category = mem.get("category", "general").strip()
                if text and len(text) > 5:
                    # Check if very similar memory already exists
                    similar = await pool.fetchval("""
                        SELECT COUNT(*) FROM patient_memories
                        WHERE patient_phone = $1 AND tenant_id = $2 AND is_active = TRUE
                        AND memory ILIKE $3
                    """, patient_phone, tenant_id, f"%{text[:30]}%")

                    if not similar or similar == 0:
                        await pool.execute("""
                            INSERT INTO patient_memories (tenant_id, patient_phone, memory, category, source)
                            VALUES ($1, $2, $3, $4, 'ai_extraction')
                        """, tenant_id, patient_phone, text, category)
                        logger.info(f"🧠 Memory stored for {patient_phone}: [{category}] {text}")

    except Exception as e:
        logger.warning(f"⚠️ Memory extraction failed: {e}")


async def add_manual_memory(pool, patient_phone: str, tenant_id: int, memory: str, category: str = "general"):
    """Manually add a memory (e.g., from clinical notes or admin input)."""
    await pool.execute("""
        INSERT INTO patient_memories (tenant_id, patient_phone, memory, category, source)
        VALUES ($1, $2, $3, $4, 'manual')
    """, tenant_id, patient_phone, memory, category)


async def deactivate_memory(pool, memory_id: int, tenant_id: int):
    """Soft-delete a memory."""
    await pool.execute("""
        UPDATE patient_memories SET is_active = FALSE, updated_at = NOW()
        WHERE id = $1 AND tenant_id = $2
    """, memory_id, tenant_id)
