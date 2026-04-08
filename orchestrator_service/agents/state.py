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

    # Graph control
    active_agent: str  # supervisor | reception | booking | triage | billing | anamnesis | handoff | END
    hop_count: int
    max_hops: int

    # Output accumulator
    agent_output: str
    tools_called: list[dict]
    handoff_reason: Optional[str]

    # Metadata
    start_time: float
