"""Model resolver for the multi-agent core.

Reads the tenant's AI model from `system_config.OPENAI_MODEL` (configurable
from the Tokens & Metrics admin page) and resolves the matching API key and
provider base URL (OpenAI or DeepSeek). Mirrors the logic in
`main.get_agent_executable_for_tenant` so that multi-agent engine uses the
SAME source of truth as the solo engine.

Contract:
    resolve_tenant_model(tenant_id) -> dict {
        "model":    str,            # e.g. "gpt-4o-mini" or "deepseek-chat"
        "api_key":  str,            # tenant-specific or fallback to env var
        "base_url": Optional[str],  # None for OpenAI, DeepSeek URL otherwise
        "provider": "openai" | "deepseek",
    }

Never hardcode a model name in agent code. Always call this resolver once
per turn and propagate the result via AgentState["model_config"].
"""
from __future__ import annotations

import logging
import os
from typing import Any

logger = logging.getLogger(__name__)


# These MUST match the constants in main.py (single source of truth is main.py).
# Kept here to avoid a circular import at module load time. If main.py changes
# these values, update this module too.
DEFAULT_OPENAI_MODEL = os.getenv("DEFAULT_OPENAI_MODEL", "gpt-4o-mini")
DEEPSEEK_MODELS = {"deepseek-chat", "deepseek-reasoner"}
DEEPSEEK_BASE_URL = "https://api.deepseek.com"


async def resolve_tenant_model(tenant_id: int) -> dict[str, Any]:
    """Resolve the model, API key, and base URL for a given tenant.

    Read order (mirrors main.get_agent_executable_for_tenant):
      1. Model ← `system_config.OPENAI_MODEL` for this tenant
         (fallback to DEFAULT_OPENAI_MODEL on miss or DB error)
      2. API key ← `core.credentials.get_tenant_credential(tenant_id, "OPENAI_API_KEY")`
         (fallback to env var OPENAI_API_KEY)
      3. If model ∈ DEEPSEEK_MODELS → switch to DEEPSEEK_API_KEY + DEEPSEEK_BASE_URL
      4. If model == "gpt-3.5-turbo" → override to default (context too small)

    Always returns a valid dict. Failure modes degrade to the default model
    with the env-var API key.
    """
    # ---- 1. Resolve API key (tenant → env fallback) ----
    api_key = ""
    try:
        from core.credentials import get_tenant_credential  # type: ignore
        api_key = await get_tenant_credential(tenant_id, "OPENAI_API_KEY") or ""
    except Exception as e:
        logger.debug(f"model_resolver: get_tenant_credential failed: {e}")

    if not api_key:
        api_key = os.getenv("OPENAI_API_KEY", "")
        logger.info(
            f"model_resolver: tenant={tenant_id} using default OPENAI_API_KEY (no tenant credential)"
        )
    else:
        logger.info(
            f"model_resolver: tenant={tenant_id} using tenant-specific API key"
        )

    # ---- 2. Resolve model from system_config ----
    model = DEFAULT_OPENAI_MODEL
    try:
        from db import pool as db_pool  # type: ignore

        row = await db_pool.fetchrow(
            "SELECT value FROM system_config WHERE key = $1 AND tenant_id = $2",
            "OPENAI_MODEL",
            tenant_id,
        )
        if row and row.get("value"):
            db_model = str(row["value"]).strip()
            # gpt-3.5-turbo has only 16K context — too small for our prompts
            if db_model == "gpt-3.5-turbo":
                logger.warning(
                    f"model_resolver: tenant={tenant_id} has 'gpt-3.5-turbo' "
                    f"(16K limit, too small). Overriding to '{DEFAULT_OPENAI_MODEL}'"
                )
            else:
                model = db_model
                logger.info(
                    f"model_resolver: tenant={tenant_id} model='{model}' (from system_config)"
                )
        else:
            logger.warning(
                f"model_resolver: tenant={tenant_id} no model in system_config, "
                f"using default '{DEFAULT_OPENAI_MODEL}'"
            )
    except Exception as e:
        logger.error(
            f"model_resolver: tenant={tenant_id} failed to read model from system_config: {e}"
        )
        logger.warning(
            f"model_resolver: tenant={tenant_id} falling back to default '{DEFAULT_OPENAI_MODEL}'"
        )

    # ---- 3. Auto-detect provider (OpenAI vs DeepSeek) ----
    if model in DEEPSEEK_MODELS:
        deepseek_key = os.getenv("DEEPSEEK_API_KEY", "")
        if deepseek_key:
            api_key = deepseek_key
        logger.info(
            f"model_resolver: tenant={tenant_id} DeepSeek detected, switching key+base_url"
        )
        return {
            "model": model,
            "api_key": api_key,
            "base_url": DEEPSEEK_BASE_URL,
            "provider": "deepseek",
        }

    # ---- 4. OpenAI (default path) ----
    return {
        "model": model,
        "api_key": api_key,
        "base_url": None,
        "provider": "openai",
    }


def get_default_model_config() -> dict[str, Any]:
    """Return a minimal config for contexts without a tenant (e.g. health probes).

    Uses the default model + env var API key. No DB access.
    """
    return {
        "model": DEFAULT_OPENAI_MODEL,
        "api_key": os.getenv("OPENAI_API_KEY", ""),
        "base_url": None,
        "provider": "openai",
    }
