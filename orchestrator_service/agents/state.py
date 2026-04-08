"""LangGraph-compatible state for the multi-agent graph (C3 F3)."""
from __future__ import annotations

from typing import Any, Optional, TypedDict


class AgentState(TypedDict, total=False):
    # Identity
    tenant_id: int
    phone_number: str
    thread_id: str
    turn_id: str

    # Input
    user_message: str

    # Patient context (loaded once per turn)
    patient_profile: dict
    chat_history: list[dict]
    working_state: dict

    # Model config (resolved once per turn from system_config — see model_resolver.py)
    # Shape: {"model": str, "api_key": str, "base_url": Optional[str], "provider": str}
    # All agents must read model from here, NEVER hardcode.
    model_config: dict

    # Graph control
    active_agent: str  # supervisor | reception | booking | triage | billing | anamnesis | handoff | END
    hop_count: int
    max_hops: int

    # Output accumulator
    agent_output: str
    tools_called: list[dict]
    handoff_reason: Optional[str]

    # Tenant-configured context blocks (built once per turn by tenant_context.build_tenant_context_blocks)
    # Shape: dict[str, str | dict] — see agents/tenant_context.py ALL_BLOCK_KEYS
    # NotRequired: existing callers that build AgentState without it remain valid.
    tenant_context: dict[str, Any]

    # Metadata
    start_time: float
