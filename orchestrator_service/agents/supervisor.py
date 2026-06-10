"""Supervisor agent — deterministic rules + LLM fallback routing (C3 F3)."""
from __future__ import annotations

import logging
import re
from pathlib import Path

from .state import AgentState

logger = logging.getLogger(__name__)


class SupervisorAgent:
    """Router agent. NO hardcoded model — uses the tenant's configured model
    from state["model_config"] when the deterministic rules don't match.
    """

    name = "supervisor"

    EMERGENCY_PATTERNS = [
        r"sangr[ae]",
        r"hinchaz[oó]n",
        r"trauma",
        r"accidente",
        r"dolor (agud|intens|fuert|insoport)",
        r"urgen",
        r"emergen",
    ]
    BOOKING_PATTERNS = [
        r"turno", r"agend", r"disponibilidad", r"reserv", r"cancel", r"reprogram",
        # v8.3: Expanded booking patterns (resolve-13-booking-errors T7) — no magic word gate
        r"implante", r"prótesis", r"protesis", r"consulta", r"evaluación", r"evaluacion",
        r"limpieza", r"blanqueamiento", r"ortodoncia", r"extracción", r"extraccion",
        r"endodoncia", r"conducto", r"corona", r"carilla", r"placa", r"prótesis",
        r"tratamiento", r"operación", r"operacion", r"cirugía", r"cirugia",
        r"saber.*precio", r"cuanto.*cuesta", r"cuánto.*cuesta",
        r"qu[eé] me recomiendan", r"qu[eé] me recomenda",
        r"quiero (info|información|informacion)",
    ]
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

        # Rule 2.5: SLOT_LOCKED state direct routing bypass
        tenant_id = state.get("tenant_id")
        phone_number = state.get("phone_number")
        if tenant_id and phone_number:
            try:
                from services.conversation_state import get_state
                conv_state = await get_state(tenant_id, phone_number)
                if conv_state and conv_state.get("state") == "SLOT_LOCKED":
                    # Exception: human handoff keywords or intent matched
                    is_handoff = False
                    for pat in self.HANDOFF_PATTERNS:
                        if re.search(pat, msg):
                            is_handoff = True
                            break
                    if is_handoff:
                        return "handoff"
                    return "booking"
            except Exception as e:
                logger.warning(f"Supervisor failed to fetch conversation state: {e}")

        # Rule 3: DNI / Confirmation flow priority
        if re.search(r"\b\d{7,11}\b", msg) or any(x in msg for x in ["dni", "mi dni", "nro de documento", "mi documento", "nro documento"]):
            return "booking"

        # Rule 4: emergency/triage
        for pat in self.EMERGENCY_PATTERNS:
            if re.search(pat, msg):
                return "triage"

        # Rule 5: billing
        for pat in self.BILLING_PATTERNS:
            if re.search(pat, msg):
                return "billing"

        # Rule 6: anamnesis
        for pat in self.ANAMNESIS_PATTERNS:
            if re.search(pat, msg):
                return "anamnesis"

        # Rule 7: handoff
        for pat in self.HANDOFF_PATTERNS:
            if re.search(pat, msg):
                return "handoff"

        # Rule 8: booking
        for pat in self.BOOKING_PATTERNS:
            if re.search(pat, msg):
                return "booking"

        # Rule 9: greeting
        for pat in self.GREETING_PATTERNS:
            if re.search(pat, msg):
                return "reception"

        # Fallback: LLM
        return await self._llm_route(state)

    async def _llm_route(self, state: AgentState) -> str:
        """LLM-based routing fallback.

        Uses the tenant's configured model from state["model_config"] — never
        hardcoded. If model_config is missing (shouldn't happen in normal flow),
        falls back to the default model via get_default_model_config().
        """
        try:
            from .specialists import _build_llm_from_config

            cfg = state.get("model_config")
            if not cfg:
                from .model_resolver import get_default_model_config
                cfg = get_default_model_config()
                logger.warning("Supervisor._llm_route: no model_config in state, using default")

            llm = _build_llm_from_config(cfg, temperature=0.0)
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
