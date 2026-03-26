"""
Patient Memory System v2 — Persistent long-term memory for the dental AI agent.
Inspired by Mem0/OpenClaw. Built on PostgreSQL, zero external deps.

Design principles:
- NEVER forget. A patient from 2 years ago gets the same recognition as yesterday's.
- Memories are extracted from EVERY conversation turn (not just patient_row ones).
- Periodic compaction merges old memories to keep the prompt lean.
- Works across channels: WhatsApp (phone), Instagram (PSID), Facebook (PSID).

Cost: ~$0.0002 per extraction (gpt-4o-mini, ~300 tokens avg)
"""
import logging
import json
import os
from datetime import datetime, timedelta, timezone
from typing import List, Optional

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────
# Schema
# ─────────────────────────────────────────────────────────────

async def ensure_memory_table(pool):
    """Create/upgrade patient_memories table. Idempotent, called on startup."""
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
    # Add importance column if missing (v2 upgrade)
    try:
        await pool.execute("""
            ALTER TABLE patient_memories ADD COLUMN IF NOT EXISTS importance INTEGER DEFAULT 5
        """)
    except Exception:
        pass  # Column already exists or DB doesn't support IF NOT EXISTS on ALTER
    logger.info("patient_memories table ensured (v2)")


# ─────────────────────────────────────────────────────────────
# Read
# ─────────────────────────────────────────────────────────────

MEMORY_CATEGORIES = {
    "salud":         "Condiciones médicas, alergias, medicamentos, antecedentes",
    "preferencia":   "Preferencias de horario, profesional, tipo de atención",
    "miedo":         "Miedos, fobias, ansiedades del paciente",
    "familia":       "Familiares, hijos, pareja, quien lo acompaña",
    "logistica":     "Dónde vive, cómo llega, trabajo, disponibilidad",
    "comportamiento":"Cómo se comunica, qué le gusta, qué le molesta",
    "referencia":    "Quién lo refirió, cómo conoció la clínica",
    "tratamiento":   "Tratamientos previos, en curso, o de interés futuro",
    "financiero":    "Preferencias de pago, obra social, presupuesto",
    "personal":      "Datos personales relevantes: cumpleaños, ocupación, mascotas",
}


async def get_memories(pool, patient_phone: str, tenant_id: int, limit: int = 30) -> List[dict]:
    """Retrieve active memories for a patient. Returns list of {memory, category, importance}."""
    rows = await pool.fetch("""
        SELECT memory, category, COALESCE(importance, 5) as importance
        FROM patient_memories
        WHERE patient_phone = $1 AND tenant_id = $2 AND is_active = TRUE
        ORDER BY COALESCE(importance, 5) DESC, updated_at DESC
        LIMIT $3
    """, patient_phone, tenant_id, limit)
    return [dict(r) for r in rows] if rows else []


async def format_memories_for_prompt(pool, patient_phone: str, tenant_id: int) -> str:
    """Get memories formatted for injection into system prompt."""
    memories = await get_memories(pool, patient_phone, tenant_id, limit=25)
    if not memories:
        return ""

    # Group by category for cleaner reading
    by_cat: dict[str, list[str]] = {}
    for m in memories:
        cat = m.get("category", "general")
        by_cat.setdefault(cat, []).append(m["memory"])

    lines = ["MEMORIA DEL PACIENTE (aprendido de conversaciones anteriores — PERMANENTE):"]

    # Priority order for categories
    cat_order = ["salud", "miedo", "tratamiento", "preferencia", "familia",
                 "logistica", "referencia", "financiero", "comportamiento", "personal", "general"]

    for cat in cat_order:
        items = by_cat.pop(cat, [])
        if items:
            cat_label = MEMORY_CATEGORIES.get(cat, cat.capitalize())
            lines.append(f"  [{cat.upper()}]")
            for item in items:
                lines.append(f"  • {item}")

    # Any remaining categories not in the priority list
    for cat, items in by_cat.items():
        lines.append(f"  [{cat.upper()}]")
        for item in items:
            lines.append(f"  • {item}")

    lines.append("")
    lines.append("REGLAS DE MEMORIA:")
    lines.append("• Usá esta información para personalizar la interacción de forma natural.")
    lines.append("• Si el paciente mencionó un miedo → sé empático y tranquilizador.")
    lines.append("• Si tiene preferencia de horario → ofrecé ese horario primero.")
    lines.append("• Si tiene familia vinculada → preguntá si quiere turno para ellos también.")
    lines.append("• NO recites la lista de memorias. Usá los datos orgánicamente en la conversación.")
    lines.append("• Si un dato de la memoria contradice algo que el paciente dice AHORA, priorizá lo que dice ahora (puede haber cambiado).")
    return "\n".join(lines)


# ─────────────────────────────────────────────────────────────
# Extract & Store
# ─────────────────────────────────────────────────────────────

# Messages that NEVER contain extractable info
TRIVIAL_EXACT = {
    "hola", "buenas", "buen dia", "buenos dias", "buenas tardes", "buenas noches",
    "hi", "hello", "hey", "ok", "okey", "oka", "dale", "listo", "gracias",
    "muchas gracias", "genial", "perfecto", "excelente", "si", "sí", "no",
    "chau", "nos vemos", "hasta luego", "bye", "1", "2", "3",
    "👍", "👌", "🙏", "😊", "😁", "👋",
}


async def extract_and_store_memories(
    pool,
    patient_phone: str,
    tenant_id: int,
    user_message: str,
    ai_response: str,
    patient_name: str = "",
    full_conversation: str = "",
):
    """
    After each conversation turn, extract memorable facts and store them.
    Uses gpt-4o-mini for extraction.

    Args:
        full_conversation: Optional full chat history for richer extraction.
                          If empty, uses only user_message + ai_response.
    """
    import httpx

    # Quick filter: truly trivial messages
    user_clean = user_message.strip().lower().rstrip(".!?")
    if user_clean in TRIVIAL_EXACT:
        return
    if len(user_message.strip()) < 8:
        return

    # Get existing memories to avoid duplicates
    existing = await get_memories(pool, patient_phone, tenant_id, limit=30)
    existing_text = "\n".join([f"- [{m['category']}] {m['memory']}" for m in existing]) if existing else "Ninguna aún"

    api_key = os.getenv("OPENAI_API_KEY", "")
    if not api_key:
        return

    # Build conversation context
    conv_block = ""
    if full_conversation:
        # Use last ~2000 chars of full conversation for context
        conv_block = f"Historial reciente de la conversación:\n{full_conversation[-2000:]}\n\n"

    extraction_prompt = f"""Sos un sistema de memoria para un agente dental AI. Tu trabajo es extraer hechos PERMANENTES sobre el paciente.

{conv_block}Último intercambio:
Paciente ({patient_name or patient_phone}): {user_message}
Asistente: {ai_response}

Memorias ya guardadas del paciente:
{existing_text}

REGLAS DE EXTRACCIÓN:
1. SOLO extraer hechos NUEVOS que NO estén ya en las memorias existentes.
2. SOLO hechos sobre el PACIENTE como persona (no sobre la clínica, el sistema, ni el turno específico).
3. Priorizar hechos que serán útiles en FUTURAS conversaciones (meses o años después).
4. Cada memoria debe ser auto-contenida (entendible sin contexto de la conversación).
5. NO extraer: saludos, confirmaciones, datos administrativos puros (DNI, teléfono — esos ya están en la ficha).
6. SÍ extraer: miedos, preferencias, condiciones médicas, situación familiar, laboral, cómo conoció la clínica, tratamientos de interés, etc.
7. Si el paciente ACTUALIZÓ un dato que ya está en memoria (ej: "ahora trabajo de noche"), marcar como update.

Categorías válidas: {', '.join(MEMORY_CATEGORIES.keys())}
Importancia (1-10): 10=crítico médico, 8=preferencia fuerte, 5=dato útil, 3=detalle menor

Ejemplos de buenas memorias:
- [salud/10] "Alérgico a la penicilina"
- [miedo/9] "Le tiene mucho miedo a las agujas, necesita contención"
- [preferencia/7] "Prefiere turnos de mañana porque trabaja de tarde"
- [familia/6] "Tiene una hija de 5 años llamada Sofía que también se atiende"
- [referencia/5] "Viene derivado del Dr. García del Hospital Central"
- [logistica/5] "Vive en zona norte, le queda lejos la clínica"
- [tratamiento/7] "Interesado en hacerse implantes el año que viene"
- [financiero/6] "Tiene obra social OSDE"
- [personal/4] "Es profesora de yoga"
- [comportamiento/5] "Es muy puntual y se molesta si lo hacen esperar"

Retorná JSON:
{{"memories": [{{"text": "...", "category": "...", "importance": N}}, ...], "updates": [{{"old_text_fragment": "...", "new_text": "...", "category": "..."}}]}}

Si no hay nada nuevo ni actualizaciones: {{"memories": [], "updates": []}}
Solo JSON, sin markdown ni explicaciones."""

    # Read model from config (fallback: gpt-4o-mini)
    memory_model = "gpt-4o-mini"
    try:
        row = await pool.fetchrow(
            "SELECT value FROM system_config WHERE key = 'MODEL_PATIENT_MEMORY' AND tenant_id = $1", tenant_id
        )
        if row and row.get("value"):
            memory_model = str(row["value"]).strip()
    except Exception:
        pass

    try:
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json={
                    "model": memory_model,
                    "messages": [{"role": "user", "content": extraction_prompt}],
                    "temperature": 0,
                    "max_tokens": 500,
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
                        pool, tenant_id, memory_model,
                        usage_data.get("prompt_tokens", 0), usage_data.get("completion_tokens", 0),
                        source="patient_memory", phone=patient_phone
                    )
                except Exception:
                    pass

            content = result.get("choices", [{}])[0].get("message", {}).get("content", "{}")
            data = json.loads(content)

            # 1. Store new memories
            new_memories = data.get("memories", [])
            stored_count = 0
            for mem in new_memories:
                text = mem.get("text", "").strip()
                category = mem.get("category", "general").strip()
                importance = min(10, max(1, int(mem.get("importance", 5))))
                if text and len(text) > 5:
                    # Fuzzy dedup: check if something very similar already exists
                    # Use first 40 chars as a signature
                    signature = text[:40].replace("'", "''")
                    similar = await pool.fetchval("""
                        SELECT COUNT(*) FROM patient_memories
                        WHERE patient_phone = $1 AND tenant_id = $2 AND is_active = TRUE
                        AND (memory ILIKE $3 OR memory ILIKE $4)
                    """, patient_phone, tenant_id, f"%{signature}%", f"%{text[:20]}%")

                    if not similar or similar == 0:
                        await pool.execute("""
                            INSERT INTO patient_memories (tenant_id, patient_phone, memory, category, source, importance)
                            VALUES ($1, $2, $3, $4, 'ai_extraction', $5)
                        """, tenant_id, patient_phone, text, category, importance)
                        stored_count += 1
                        logger.info(f"🧠 Memory stored [{category}/{importance}] for {patient_phone}: {text[:60]}")

            # 2. Process updates (patient corrected or updated info)
            updates = data.get("updates", [])
            for upd in updates:
                old_fragment = upd.get("old_text_fragment", "").strip()
                new_text = upd.get("new_text", "").strip()
                category = upd.get("category", "general").strip()
                if old_fragment and new_text:
                    # Find and deactivate old memory
                    old_row = await pool.fetchrow("""
                        SELECT id FROM patient_memories
                        WHERE patient_phone = $1 AND tenant_id = $2 AND is_active = TRUE
                        AND memory ILIKE $3
                        LIMIT 1
                    """, patient_phone, tenant_id, f"%{old_fragment}%")
                    if old_row:
                        await pool.execute("""
                            UPDATE patient_memories SET is_active = FALSE, updated_at = NOW()
                            WHERE id = $1
                        """, old_row["id"])
                        await pool.execute("""
                            INSERT INTO patient_memories (tenant_id, patient_phone, memory, category, source, importance)
                            VALUES ($1, $2, $3, $4, 'ai_update', 7)
                        """, tenant_id, patient_phone, new_text, category)
                        logger.info(f"🧠 Memory UPDATED for {patient_phone}: '{old_fragment[:30]}' → '{new_text[:60]}'")

            if stored_count > 0:
                logger.info(f"🧠 Total new memories stored for {patient_phone}: {stored_count}")

    except Exception as e:
        logger.warning(f"⚠️ Memory extraction failed (non-fatal): {e}")


# ─────────────────────────────────────────────────────────────
# Compaction — merge old redundant memories periodically
# ─────────────────────────────────────────────────────────────

async def compact_memories(pool, patient_phone: str, tenant_id: int):
    """
    When a patient has too many memories (>40), compact old low-importance ones.
    Merges related memories within the same category.
    Called lazily (not on every request).
    """
    import httpx

    count = await pool.fetchval("""
        SELECT COUNT(*) FROM patient_memories
        WHERE patient_phone = $1 AND tenant_id = $2 AND is_active = TRUE
    """, patient_phone, tenant_id)

    if count <= 40:
        return  # No compaction needed

    # Get all memories
    rows = await pool.fetch("""
        SELECT id, memory, category, COALESCE(importance, 5) as importance, created_at
        FROM patient_memories
        WHERE patient_phone = $1 AND tenant_id = $2 AND is_active = TRUE
        ORDER BY category, created_at ASC
    """, patient_phone, tenant_id)

    # Group by category
    by_cat: dict[str, list[dict]] = {}
    for r in rows:
        cat = r["category"]
        by_cat.setdefault(cat, []).append(dict(r))

    api_key = os.getenv("OPENAI_API_KEY", "")
    if not api_key:
        return

    # Only compact categories with 5+ memories
    for cat, mems in by_cat.items():
        if len(mems) < 5:
            continue

        mem_list = "\n".join([f"[id:{m['id']}] {m['memory']}" for m in mems])
        compact_prompt = f"""Estas son memorias de un paciente dental en la categoría "{cat}".
Algunas pueden ser redundantes, contradictorias, o fusionables.

Memorias actuales:
{mem_list}

Tareas:
1. Fusiona memorias redundantes en una sola más completa.
2. Si dos memorias se contradicen, quedáte con la más reciente (mayor id = más reciente).
3. Elimina memorias que ya no aportan valor (ej: "preguntó por blanqueamiento" si ya hay "Se hizo blanqueamiento").
4. Mantené TODA la información importante — solo eliminá redundancia.

Retorná JSON:
{{"keep": [ids de memorias que se mantienen sin cambios],
  "merge": [{{"new_text": "texto fusionado", "replace_ids": [ids que se fusionan], "importance": N}}],
  "deactivate": [ids que se eliminan por obsoletos]}}
Solo JSON."""

        try:
            async with httpx.AsyncClient(timeout=25) as client:
                resp = await client.post(
                    "https://api.openai.com/v1/chat/completions",
                    headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                    json={
                        "model": "gpt-4o-mini",
                        "messages": [{"role": "user", "content": compact_prompt}],
                        "temperature": 0,
                        "max_tokens": 500,
                        "response_format": {"type": "json_object"}
                    }
                )
                result = resp.json()
                content = result.get("choices", [{}])[0].get("message", {}).get("content", "{}")
                data = json.loads(content)

                # Deactivate obsolete
                for mid in data.get("deactivate", []):
                    await pool.execute(
                        "UPDATE patient_memories SET is_active = FALSE, updated_at = NOW() WHERE id = $1 AND tenant_id = $2",
                        int(mid), tenant_id
                    )

                # Merge groups
                for merge in data.get("merge", []):
                    new_text = merge.get("new_text", "").strip()
                    replace_ids = merge.get("replace_ids", [])
                    importance = min(10, max(1, int(merge.get("importance", 5))))
                    if new_text and replace_ids:
                        # Deactivate old ones
                        for mid in replace_ids:
                            await pool.execute(
                                "UPDATE patient_memories SET is_active = FALSE, updated_at = NOW() WHERE id = $1 AND tenant_id = $2",
                                int(mid), tenant_id
                            )
                        # Insert merged
                        await pool.execute("""
                            INSERT INTO patient_memories (tenant_id, patient_phone, memory, category, source, importance)
                            VALUES ($1, $2, $3, $4, 'compaction', $5)
                        """, tenant_id, patient_phone, new_text, cat, importance)

                logger.info(f"🧠 Compacted {cat} memories for {patient_phone}: {len(mems)} → kept/merged")

        except Exception as e:
            logger.warning(f"⚠️ Memory compaction failed for {cat}: {e}")


# ─────────────────────────────────────────────────────────────
# Manual operations (admin panel / AI tool)
# ─────────────────────────────────────────────────────────────

async def add_manual_memory(pool, patient_phone: str, tenant_id: int, memory: str, category: str = "general", importance: int = 7):
    """Manually add a memory (e.g., from clinical notes or admin input)."""
    await pool.execute("""
        INSERT INTO patient_memories (tenant_id, patient_phone, memory, category, source, importance)
        VALUES ($1, $2, $3, $4, 'manual', $5)
    """, tenant_id, patient_phone, memory, category, importance)
    logger.info(f"🧠 Manual memory added for {patient_phone}: [{category}] {memory[:60]}")


async def deactivate_memory(pool, memory_id: int, tenant_id: int):
    """Soft-delete a memory."""
    await pool.execute("""
        UPDATE patient_memories SET is_active = FALSE, updated_at = NOW()
        WHERE id = $1 AND tenant_id = $2
    """, memory_id, tenant_id)


async def get_memory_stats(pool, tenant_id: int) -> dict:
    """Get memory stats for a tenant (useful for admin dashboard)."""
    total = await pool.fetchval(
        "SELECT COUNT(*) FROM patient_memories WHERE tenant_id = $1 AND is_active = TRUE", tenant_id
    )
    patients_with_memories = await pool.fetchval(
        "SELECT COUNT(DISTINCT patient_phone) FROM patient_memories WHERE tenant_id = $1 AND is_active = TRUE", tenant_id
    )
    by_category = await pool.fetch(
        "SELECT category, COUNT(*) as cnt FROM patient_memories WHERE tenant_id = $1 AND is_active = TRUE GROUP BY category ORDER BY cnt DESC",
        tenant_id
    )
    return {
        "total_memories": total or 0,
        "patients_with_memories": patients_with_memories or 0,
        "by_category": {r["category"]: r["cnt"] for r in by_category} if by_category else {},
    }
