"""Abstract base for all specialized agents in the multi-agent core (C3 F3)."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from .state import AgentState


class BaseAgent(ABC):
    name: str = "base"
    model: str = "gpt-4o-mini"

    @abstractmethod
    async def run(self, state: AgentState) -> AgentState:
        """Process the turn. Must set state['agent_output'] and
        state['active_agent'] = 'END' (or another agent name for handoff).
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
