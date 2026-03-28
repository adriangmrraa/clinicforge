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
DEFAULT_SIMILARITY_THRESHOLD = 0.7

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
        return response.data[0].embedding
    except Exception as e:
        logger.error(f"Error generating embedding: {e}")
        return None


async def upsert_faq_embedding(tenant_id: int, faq_id: int, question: str, answer: str) -> bool:
    """Generate and store embedding for a FAQ entry."""
    if not await check_pgvector_available():
        return False

    content = f"{question} {answer}"
    embedding = await generate_embedding(content)
    if not embedding:
        return False

    try:
        embedding_str = f"[{','.join(str(x) for x in embedding)}]"
        await db.pool.execute("""
            INSERT INTO faq_embeddings (tenant_id, faq_id, content, embedding, updated_at)
            VALUES ($1, $2, $3, $4::vector, NOW())
            ON CONFLICT (faq_id) DO UPDATE SET
                content = EXCLUDED.content,
                embedding = EXCLUDED.embedding,
                updated_at = NOW()
        """, tenant_id, faq_id, content, embedding_str)
        logger.debug(f"Upserted FAQ embedding: tenant={tenant_id} faq={faq_id}")
        return True
    except Exception as e:
        logger.error(f"Error upserting FAQ embedding: {e}")
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
    Returns top-K FAQs sorted by relevance.
    Falls back to empty list if pgvector is not available.
    """
    if not await check_pgvector_available():
        return []

    query_embedding = await generate_embedding(query)
    if not query_embedding:
        return []

    if top_k is None:
        top_k_str = await _get_config("RAG_TOP_K", str(DEFAULT_TOP_K))
        top_k = int(top_k_str)
    if threshold is None:
        thresh_str = await _get_config("RAG_SIMILARITY_THRESHOLD", str(DEFAULT_SIMILARITY_THRESHOLD))
        threshold = float(thresh_str)

    try:
        embedding_str = f"[{','.join(str(x) for x in query_embedding)}]"
        results = await db.pool.fetch("""
            SELECT
                fe.faq_id,
                fe.content,
                cf.question,
                cf.answer,
                cf.category,
                1 - (fe.embedding <=> $1::vector) AS similarity
            FROM faq_embeddings fe
            JOIN clinic_faqs cf ON cf.id = fe.faq_id
            WHERE fe.tenant_id = $2
            AND 1 - (fe.embedding <=> $1::vector) >= $3
            ORDER BY fe.embedding <=> $1::vector
            LIMIT $4
        """, embedding_str, tenant_id, threshold, top_k)

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
        logger.error(f"Error searching similar FAQs: {e}")
        return []


async def sync_tenant_faq_embeddings(tenant_id: int) -> int:
    """
    Synchronize all FAQ embeddings for a tenant.
    Generates embeddings for FAQs that don't have one yet.
    Returns count of embeddings created.
    """
    if not await check_pgvector_available():
        return 0

    try:
        faqs = await db.pool.fetch("""
            SELECT cf.id, cf.question, cf.answer
            FROM clinic_faqs cf
            LEFT JOIN faq_embeddings fe ON cf.id = fe.faq_id
            WHERE cf.tenant_id = $1 AND fe.id IS NULL
        """, tenant_id)

        count = 0
        for faq in faqs:
            ok = await upsert_faq_embedding(tenant_id, faq["id"], faq["question"], faq["answer"])
            if ok:
                count += 1
            # Small delay to avoid rate limiting
            if count % 10 == 0 and count > 0:
                await asyncio.sleep(0.5)

        if count > 0:
            logger.info(f"Synced {count} FAQ embeddings for tenant {tenant_id}")
        return count
    except Exception as e:
        logger.error(f"Error syncing FAQ embeddings for tenant {tenant_id}: {e}")
        return 0


async def sync_all_tenants_faq_embeddings() -> int:
    """Sync FAQ embeddings for all active tenants. Called on startup."""
    if not await check_pgvector_available():
        return 0

    try:
        tenants = await db.pool.fetch("SELECT id FROM tenants WHERE status = 'active'")
        total = 0
        for t in tenants:
            total += await sync_tenant_faq_embeddings(t["id"])
        if total > 0:
            logger.info(f"Startup FAQ embedding sync complete: {total} embeddings created")
        return total
    except Exception as e:
        logger.error(f"Error syncing all tenant FAQ embeddings: {e}")
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
            lines = ["FAQs RELEVANTES (responder SIEMPRE con estas respuestas cuando aplique):"]
            for faq in relevant_faqs:
                lines.append(f"• {faq['question']}: \"{faq['answer']}\" [relevancia: {faq['similarity']}]")
            return "\n".join(lines)

    # Fallback: static FAQs (original behavior)
    if not static_faqs:
        return ""
    lines = ["FAQs OBLIGATORIAS (responder SIEMPRE con estas respuestas cuando aplique):"]
    for faq in static_faqs[:20]:
        q = faq.get("question", "")
        a = faq.get("answer", "")
        lines.append(f"• {q}: \"{a}\"")
    return "\n".join(lines)
