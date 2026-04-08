"""Abstract base for all specialized agents in the multi-agent core (C3 F3)."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from .state import AgentState


class BaseAgent(ABC):
    """Base class for specialized agents.

    IMPORTANT: Agents MUST read the model from `state["model_config"]`.
    NEVER hardcode a model name as a class attribute. The model comes from
    `system_config.OPENAI_MODEL` per tenant, resolved once per turn by
    `agents.model_resolver.resolve_tenant_model` and propagated via AgentState.
    """

    name: str = "base"

    @abstractmethod
    async def run(self, state: AgentState) -> AgentState:
        """Process the turn. Must set state['agent_output'] and
        state['active_agent'] = 'END' (or another agent name for handoff).

        Read the model config from state["model_config"]:
            cfg = state["model_config"]
            llm = _build_llm(cfg, temperature=0.2)
        """
        ...

    def _log_tool_call(self, state: AgentState, tool_name: str, args: dict, result: Any) -> None:
        tools = state.get("tools_called") or []
        tools.append({
            "tool": tool_name,
            "args": args,
            "result_preview": str(result)[:200],
        })
        state["tools_called"] = tools
