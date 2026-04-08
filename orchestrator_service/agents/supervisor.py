"""Supervisor agent — deterministic rules + LLM fallback routing (C3 F3)."""
from __future__ import annotations

import logging
import re
from pathlib import Path

from .state import AgentState

logger = logging.getLogger(__name__)


class SupervisorAgent:
    name = "supervisor"
    model = "gpt-4o-mini"

    EMERGENCY_PATTERNS = [
        r"sangr[ae]",
        r"hinchaz[oó]n",
        r"trauma",
        r"accidente",
        r"dolor (agud|intens|fuert|insoport)",
        r"urgen",
        r"emergen",
    ]
    BOOKING_PATTERNS = [r"turno", r"agend", r"disponibilidad", r"reserv", r"cancel", r"reprogram"]
    BILLING_PATTERNS = [r"pag[oó]", r"seña", r"transfer", r"comprobante", r"cbu", r"alias"]
    ANAMNESIS_PATTERNS = [r"historia m[eé]dica", r"alergi", r"medicaci[oó]n", r"ficha", r"formulari"]
    HANDOFF_PATTERNS = [r"hablar con (alguien|humano|persona|secretar|recepcion)", r"humano", r"queja"]
    GREETING_PATTERNS = [r"^(hola|buenas|buen d[ií]a|buenas tardes|buenas noches|hi|hey)[\s!\.]*$"]

    VALID_AGENTS = {"reception", "booking", "triage", "billing", "anamnesis", "handoff"}

    async def route(self, state: AgentState) -> str:
        """Return the next agent name. Deterministic rules first, LLM fallback."""
        msg = (state.get("user_message") or "").strip().lower()

        # Rule 1: human_override silence → handoff
        if state.get("patient_profile", {}).get("human_override_until"):
            return "handoff"

        # Rule 2: hop_count exhausted
        if state.get("hop_count", 0) >= state.get("max_hops", 5):
            return "handoff"

        # Rule 3: emergency/triage
        for pat in self.EMERGENCY_PATTERNS:
            if re.search(pat, msg):
                return "triage"

        # Rule 4: billing
        for pat in self.BILLING_PATTERNS:
            if re.search(pat, msg):
                return "billing"

        # Rule 5: anamnesis
        for pat in self.ANAMNESIS_PATTERNS:
            if re.search(pat, msg):
                return "anamnesis"

        # Rule 6: handoff
        for pat in self.HANDOFF_PATTERNS:
            if re.search(pat, msg):
                return "handoff"

        # Rule 7: booking
        for pat in self.BOOKING_PATTERNS:
            if re.search(pat, msg):
                return "booking"

        # Rule 8: greeting
        for pat in self.GREETING_PATTERNS:
            if re.search(pat, msg):
                return "reception"

        # Fallback: LLM
        return await self._llm_route(state)

    async def _llm_route(self, state: AgentState) -> str:
        """LLM-based routing fallback."""
        try:
            from core.openai_compat import get_chat_model
            llm = get_chat_model(self.model, temperature=0.0)
            prompt_path = Path(__file__).parent / "prompts" / "supervisor.md"
            system_prompt = prompt_path.read_text(encoding="utf-8")

            response = await llm.ainvoke([
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": state.get("user_message", "")},
            ])
            decision = (response.content or "").strip().lower()
            # Pull the first word (robust to stray punctuation)
            decision = re.split(r"[\s,.\"']+", decision)[0] if decision else ""
            if decision in self.VALID_AGENTS:
                return decision
        except Exception as e:
            logger.warning(f"Supervisor LLM routing failed: {e}")

        # Ultimate fallback: reception is always safe
        return "reception"
