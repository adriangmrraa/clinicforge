"""
Embedding Service for ClinicForge RAG System
Generates and manages vector embeddings for FAQ semantic search.
Uses OpenAI text-embedding-3-small (1536 dimensions).
"""

import os
import json
import logging
import asyncio
from typing import List, Dict, Any, Optional

from db import db

logger = logging.getLogger(__name__)

# Embedding configuration defaults
DEFAULT_EMBEDDING_MODEL = "text-embedding-3-small"
DEFAULT_TOP_K = 5
# Lowered from 0.7 to 0.55 to capture semantic variations (e.g. "demora" vs "dura",
# "cuesta" vs "sale"). text-embedding-3-small needs lower threshold for Spanish synonyms.
DEFAULT_SIMILARITY_THRESHOLD = 0.55

_pgvector_available: Optional[bool] = None


async def check_pgvector_available() -> bool:
    """Check if pgvector extension is available in the database."""
    global _pgvector_available
    if _pgvector_available is not None:
        return _pgvector_available
    try:
        result = await db.pool.fetchval(
            "SELECT EXISTS(SELECT 1 FROM pg_extension WHERE extname = 'vector')"
        )
        _pgvector_available = bool(result)
        if not _pgvector_available:
            logger.info("pgvector extension not available — RAG will use static FAQ fallback")
        else:
            logger.info("pgvector extension detected — RAG semantic search enabled")
        return _pgvector_available
    except Exception as e:
        logger.warning(f"Could not check pgvector availability: {e}")
        _pgvector_available = False
        return False


async def _get_config(key: str, default: str) -> str:
    """Read config from system_config table."""
    try:
        val = await db.pool.fetchval(
            "SELECT value FROM system_config WHERE key = $1", key
        )
        return val or default
    except Exception:
        return default


async def generate_embedding(text: str) -> Optional[List[float]]:
    """Generate embedding vector for a text string using OpenAI API."""
    try:
        import openai
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            logger.warning("OPENAI_API_KEY not set — cannot generate embeddings")
            return None

        model = await _get_config("MODEL_EMBEDDINGS", DEFAULT_EMBEDDING_MODEL)
        client = openai.AsyncOpenAI(api_key=api_key)
        response = await client.embeddings.create(
            input=text,
            model=model
        )

        # Track embedding usage
        try:
            usage = response.usage
            if usage:
                from dashboard.token_tracker import track_service_usage
                from db import db as _db
                await track_service_usage(_db.pool, 0, model, usage.total_tokens, 0, source="rag_embedding", phone="system")
        except Exception:
            pass

        return response.data[0].embedding
    except Exception as e:
        logger.error(f"Error generating embedding: {e}")
        return None


async def _ensure_faq_embeddings_json_table():
    """Create faq_embeddings_json table if it doesn't exist (pgvector-free fallback)."""
    try:
        await db.pool.execute("""
            CREATE TABLE IF NOT EXISTS faq_embeddings_json (
                id SERIAL PRIMARY KEY,
                tenant_id INTEGER NOT NULL,
                faq_id INTEGER NOT NULL,
                content TEXT NOT NULL,
                embedding JSONB NOT NULL,
                updated_at TIMESTAMPTZ DEFAULT NOW(),
                UNIQUE(faq_id)
            )
        """)
        await db.pool.execute(
            "CREATE INDEX IF NOT EXISTS idx_faq_emb_json_tenant ON faq_embeddings_json(tenant_id)"
        )
    except Exception as e:
        logger.debug(f"faq_embeddings_json table check: {e}")


def _cosine_similarity(a: List[float], b: List[float]) -> float:
    """Compute cosine similarity between two vectors in pure Python."""
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = sum(x * x for x in a) ** 0.5
    norm_b = sum(x * x for x in b) ** 0.5
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


async def upsert_faq_embedding(tenant_id: int, faq_id: int, question: str, answer: str) -> bool:
    """Generate and store embedding for a FAQ entry. Works with or without pgvector."""
    content = f"{question} {answer}"
    embedding = await generate_embedding(content)
    if not embedding:
        return False

    # Try pgvector first
    if await check_pgvector_available():
        try:
            # pgvector codec is registered in db.py:_init_connection
            try:
                import numpy as np
                embedding_param = np.array(embedding, dtype=np.float32)
            except ImportError:
                embedding_param = embedding
            await db.pool.execute("""
                INSERT INTO faq_embeddings (tenant_id, faq_id, content, embedding, updated_at)
                VALUES ($1, $2, $3, $4, NOW())
                ON CONFLICT (faq_id) DO UPDATE SET
                    content = EXCLUDED.content,
                    embedding = EXCLUDED.embedding,
                    updated_at = NOW()
            """, tenant_id, faq_id, content, embedding_param)
            logger.debug(f"Upserted FAQ embedding (pgvector): tenant={tenant_id} faq={faq_id}")
            return True
        except Exception as e:
            logger.error(f"Error upserting FAQ embedding (pgvector): {e}")
            return False

    # Fallback: JSON table (no pgvector needed)
    try:
        await _ensure_faq_embeddings_json_table()
        embedding_json = json.dumps(embedding)
        await db.pool.execute("""
            INSERT INTO faq_embeddings_json (tenant_id, faq_id, content, embedding, updated_at)
            VALUES ($1, $2, $3, $4::jsonb, NOW())
            ON CONFLICT (faq_id) DO UPDATE SET
                content = EXCLUDED.content,
                embedding = EXCLUDED.embedding,
                updated_at = NOW()
        """, tenant_id, faq_id, content, embedding_json)
        logger.debug(f"Upserted FAQ embedding (JSON): tenant={tenant_id} faq={faq_id}")
        return True
    except Exception as e:
        logger.error(f"Error upserting FAQ embedding (JSON fallback): {e}")
        return False


async def delete_faq_embedding(faq_id: int, tenant_id: Optional[int] = None) -> bool:
    """Delete embedding when a FAQ is removed. Uses tenant_id for isolation when available."""
    try:
        if tenant_id:
            await db.pool.execute(
                "DELETE FROM faq_embeddings WHERE faq_id = $1 AND tenant_id = $2",
                faq_id, tenant_id
            )
        else:
            # CASCADE from clinic_faqs deletion handles this, but be explicit
            await db.pool.execute("DELETE FROM faq_embeddings WHERE faq_id = $1", faq_id)
        return True
    except Exception as e:
        logger.error(f"Error deleting FAQ embedding: {e}")
        return False


async def search_similar_faqs(
    tenant_id: int,
    query: str,
    top_k: Optional[int] = None,
    threshold: Optional[float] = None
) -> List[Dict[str, Any]]:
    """
    Search for semantically similar FAQs using vector cosine similarity.
    Works with pgvector (fast, DB-side) or JSON fallback (Python-side).
    Returns top-K FAQs sorted by relevance.
    """
    query_embedding = await generate_embedding(query)
    if not query_embedding:
        return []

    if top_k is None:
        top_k_str = await _get_config("RAG_TOP_K", str(DEFAULT_TOP_K))
        top_k = int(top_k_str)
    if threshold is None:
        thresh_str = await _get_config("RAG_SIMILARITY_THRESHOLD", str(DEFAULT_SIMILARITY_THRESHOLD))
        threshold = float(thresh_str)

    # Try pgvector first (fast, DB-side similarity)
    if await check_pgvector_available():
        try:
            # pgvector codec is registered in db.py:_init_connection, so we can
            # pass the embedding as a Python list and asyncpg handles the conversion.
            # As fallback we also accept the textual representation '[1,2,3]'.
            try:
                import numpy as np
                embedding_param = np.array(query_embedding, dtype=np.float32)
            except ImportError:
                embedding_param = query_embedding  # asyncpg handles list[float]

            results = await db.pool.fetch("""
                SELECT
                    fe.faq_id,
                    fe.content,
                    cf.question,
                    cf.answer,
                    cf.category,
                    1 - (fe.embedding <=> $1) AS similarity
                FROM faq_embeddings fe
                JOIN clinic_faqs cf ON cf.id = fe.faq_id
                WHERE fe.tenant_id = $2
                AND 1 - (fe.embedding <=> $1) >= $3
                ORDER BY fe.embedding <=> $1
                LIMIT $4
            """, embedding_param, tenant_id, threshold, top_k)

            logger.info(f"📚 RAG pgvector: found {len(results)} FAQs above threshold {threshold} for tenant {tenant_id}")

            return [
                {
                    "faq_id": row["faq_id"],
                    "question": row["question"],
                    "answer": row["answer"],
                    "category": row["category"],
                    "similarity": round(float(row["similarity"]), 4),
                }
                for row in results
            ]
        except Exception as e:
            logger.error(f"Error searching FAQs (pgvector): {e}")
            return []

    # Fallback: JSON table + Python cosine similarity
    try:
        await _ensure_faq_embeddings_json_table()
        rows = await db.pool.fetch("""
            SELECT fej.faq_id, fej.embedding, cf.question, cf.answer, cf.category
            FROM faq_embeddings_json fej
            JOIN clinic_faqs cf ON cf.id = fej.faq_id
            WHERE fej.tenant_id = $1
        """, tenant_id)

        if not rows:
            return []

        scored = []
        for row in rows:
            stored_embedding = row["embedding"]
            if isinstance(stored_embedding, str):
                stored_embedding = json.loads(stored_embedding)
            sim = _cosine_similarity(query_embedding, stored_embedding)
            if sim >= threshold:
                scored.append({
                    "faq_id": row["faq_id"],
                    "question": row["question"],
                    "answer": row["answer"],
                    "category": row["category"],
                    "similarity": round(sim, 4),
                })

        scored.sort(key=lambda x: x["similarity"], reverse=True)
        return scored[:top_k]

    except Exception as e:
        logger.error(f"Error searching FAQs (JSON fallback): {e}")
        return []


async def sync_tenant_faq_embeddings(tenant_id: int) -> int:
    """
    Synchronize all FAQ embeddings for a tenant.
    Generates embeddings for FAQs that don't have one yet.
    Returns count of embeddings created.
    """
    if not await check_pgvector_available():
        logger.warning(f"📚 sync_tenant_faq_embeddings({tenant_id}): pgvector NOT available, skipping")
        return 0

    try:
        # First check total FAQs vs total embeddings to see status
        total_faqs = await db.pool.fetchval(
            "SELECT COUNT(*) FROM clinic_faqs WHERE tenant_id = $1", tenant_id
        )
        total_embeddings = await db.pool.fetchval(
            "SELECT COUNT(*) FROM faq_embeddings WHERE tenant_id = $1", tenant_id
        )
        logger.info(
            f"📚 sync_tenant_faq_embeddings(tenant={tenant_id}): "
            f"FAQs={total_faqs}, existing embeddings={total_embeddings}"
        )

        faqs = await db.pool.fetch("""
            SELECT cf.id, cf.question, cf.answer
            FROM clinic_faqs cf
            LEFT JOIN faq_embeddings fe ON cf.id = fe.faq_id AND fe.tenant_id = cf.tenant_id
            WHERE cf.tenant_id = $1 AND fe.id IS NULL
        """, tenant_id)

        logger.info(f"📚 sync_tenant_faq_embeddings(tenant={tenant_id}): {len(faqs)} FAQs need embedding")

        count = 0
        failures = 0
        for faq in faqs:
            ok = await upsert_faq_embedding(tenant_id, faq["id"], faq["question"], faq["answer"])
            if ok:
                count += 1
            else:
                failures += 1
            # Small delay to avoid rate limiting
            if count % 10 == 0 and count > 0:
                await asyncio.sleep(0.5)

        logger.info(
            f"📚 sync_tenant_faq_embeddings(tenant={tenant_id}): "
            f"created {count}, failed {failures}"
        )
        return count
    except Exception as e:
        logger.error(f"📚 Error syncing FAQ embeddings for tenant {tenant_id}: {e}", exc_info=True)
        return 0


async def sync_all_tenants_faq_embeddings() -> int:
    """Sync FAQ embeddings for all active tenants. Called on startup."""
    logger.info("📚 sync_all_tenants_faq_embeddings: starting...")

    if not await check_pgvector_available():
        logger.warning("📚 sync_all_tenants_faq_embeddings: pgvector NOT available, aborting")
        return 0

    try:
        # tenants table has no status column — all rows are considered active
        tenants = await db.pool.fetch("SELECT id FROM tenants")
        logger.info(f"📚 sync_all_tenants_faq_embeddings: processing {len(tenants)} tenants")
        total = 0
        for t in tenants:
            total += await sync_tenant_faq_embeddings(t["id"])
        logger.info(f"📚 sync_all_tenants_faq_embeddings: COMPLETE — {total} embeddings created total")
        return total
    except Exception as e:
        logger.error(f"📚 Error syncing all tenant FAQ embeddings: {e}", exc_info=True)
        return 0


async def format_faqs_with_rag(tenant_id: int, user_message: str, static_faqs: list) -> str:
    """
    Format FAQs for prompt injection using semantic search when available.
    Falls back to static FAQs (first 20) if RAG is not available.

    Args:
        tenant_id: Tenant ID
        user_message: The patient's current message (for semantic search)
        static_faqs: The full list of FAQs from DB (fallback)

    Returns:
        Formatted FAQ string for the system prompt
    """
    # Try semantic search first
    if await check_pgvector_available() and user_message:
        relevant_faqs = await search_similar_faqs(tenant_id, user_message)
        if relevant_faqs:
            # Log retrieved FAQs for debugging FAQ priority issues
            logger.info(
                f"📚 RAG retrieved {len(relevant_faqs)} FAQs for query='{user_message[:80]}': "
                + ", ".join(f"{f['question'][:40]}({f['similarity']})" for f in relevant_faqs)
            )
            lines = [
                "═══════════════════════════════════════════════",
                "FAQs RELEVANTES — VOZ OFICIAL DE LA DOCTORA",
                "═══════════════════════════════════════════════",
                "Usá estas FAQs para responder preguntas de seguimiento y temas generales.",
                "EXCEPCIÓN: Si el paciente menciona un tratamiento por PRIMERA VEZ con interés",
                "amplio y todavía no recibió la presentación (ai_response_template), usá",
                "get_service_details PRIMERO — ver REGLA DE PRIMERA MENCIÓN en el prompt.",
                "Para todo lo demás, respondé con la RESPUESTA OFICIAL tal cual, sin parafrasear.",
                "",
            ]
            for i, faq in enumerate(relevant_faqs, 1):
                cat = faq.get("category", "General") or "General"
                lines.append(f"━━━ FAQ #{i} [{cat}] ━━━")
                lines.append(f"PREGUNTA OFICIAL: {faq['question']}")
                lines.append(f"RESPUESTA OFICIAL (USAR ESTA TAL CUAL): {faq['answer']}")
                lines.append("")
            lines.append("═══════════════════════════════════════════════")
            return "\n".join(lines)

    # Fallback: static FAQs (original behavior)
    if not static_faqs:
        return ""
    logger.info(f"📚 RAG fallback: injecting {min(len(static_faqs), 20)} static FAQs (no pgvector or no relevant matches)")
    lines = [
        "═══════════════════════════════════════════════",
        "FAQs DISPONIBLES — VOZ OFICIAL DE LA DOCTORA",
        "═══════════════════════════════════════════════",
        "Usá estas FAQs para responder preguntas de seguimiento y temas generales.",
        "EXCEPCIÓN: Si el paciente menciona un tratamiento por PRIMERA VEZ con interés",
        "amplio y todavía no recibió la presentación (ai_response_template), usá",
        "get_service_details PRIMERO — ver REGLA DE PRIMERA MENCIÓN en el prompt.",
        "Para todo lo demás, respondé con la RESPUESTA OFICIAL tal cual, sin parafrasear.",
        "",
    ]
    for i, faq in enumerate(static_faqs[:20], 1):
        cat = faq.get("category", "General") or "General"
        q = faq.get("question", "")
        a = faq.get("answer", "")
        lines.append(f"━━━ FAQ #{i} [{cat}] ━━━")
        lines.append(f"PREGUNTA OFICIAL: {q}")
        lines.append(f"RESPUESTA OFICIAL (USAR ESTA TAL CUAL): {a}")
        lines.append("")
    lines.append("═══════════════════════════════════════════════")
    return "\n".join(lines)


async def format_all_context_with_rag(
    tenant_id: int,
    user_message: str,
    static_faqs: list,
    insurance_providers: list = None,
    derivation_rules: list = None,
) -> dict:
    """
    Unified RAG context formatter. Currently only FAQs use semantic search.
    Insurance and derivation are small catalogs — injected statically by build_system_prompt().

    Returns dict with keys: faqs_section, insurance_section, derivation_section, instructions_section
    """
    faqs_section = await format_faqs_with_rag(tenant_id, user_message, static_faqs)

    # Insurance and derivation: return empty — they stay static in build_system_prompt()
    # because catalogs are small (<30 items) and the agent needs full context for inline recognition.
    return {
        "faqs_section": faqs_section,
        "insurance_section": "",
        "derivation_section": "",
        "instructions_section": "",
    }
