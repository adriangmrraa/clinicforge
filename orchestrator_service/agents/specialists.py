"""Specialized agents: Reception, Booking, Triage, Billing, Anamnesis, Handoff (C3 F3).

Each agent wraps a bounded LangChain AgentExecutor over a subset of DENTAL_TOOLS
from `main`. Tools are imported lazily inside `_get_tools` to avoid circular imports.

IMPORTANT: No agent hardcodes a model name. The model is read from
`state["model_config"]`, which is populated in graph.run_turn() via
`model_resolver.resolve_tenant_model(tenant_id)`. Source of truth:
`system_config.OPENAI_MODEL` (Tokens & Metrics admin page).
"""
from __future__ import annotations

import logging
from typing import Any

from langchain.agents import AgentExecutor, create_openai_tools_agent
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_openai import ChatOpenAI

from .base import BaseAgent
from .state import AgentState

logger = logging.getLogger(__name__)


def _build_llm_from_config(cfg: dict[str, Any], temperature: float = 0.2) -> ChatOpenAI:
    """Instantiate a ChatOpenAI from a model_config dict.

    Shape expected: {"model": str, "api_key": str, "base_url": Optional[str], "provider": str}
    Auto-routes to OpenAI or DeepSeek base URL based on the `base_url` field.
    NEVER hardcodes a model.
    """
    model = cfg.get("model") or ""
    api_key = cfg.get("api_key") or ""
    base_url = cfg.get("base_url")

    kwargs: dict[str, Any] = {
        "model": model,
        "temperature": temperature,
        "openai_api_key": api_key,
    }
    if base_url:
        kwargs["openai_api_base"] = base_url
    return ChatOpenAI(**kwargs)


def _build_executor(tools, cfg: dict[str, Any], system_prompt: str, temperature: float = 0.2) -> AgentExecutor:
    """Build a bounded AgentExecutor using the tenant's model config."""
    llm = _build_llm_from_config(cfg, temperature=temperature)
    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        MessagesPlaceholder(variable_name="chat_history", optional=True),
        ("human", "{input}"),
        MessagesPlaceholder(variable_name="agent_scratchpad"),
    ])
    agent = create_openai_tools_agent(llm, tools, prompt)
    return AgentExecutor(agent=agent, tools=tools, verbose=False, max_iterations=4)


def _history_to_messages(chat_history: list[dict]) -> list:
    """Convert [{role, content}, ...] to LangChain messages."""
    from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
    out = []
    for m in chat_history or []:
        role = (m.get("role") or "").lower()
        content = m.get("content") or ""
        if role in ("user", "human"):
            out.append(HumanMessage(content=content))
        elif role in ("assistant", "ai", "bot"):
            out.append(AIMessage(content=content))
        elif role == "system":
            out.append(SystemMessage(content=content))
    return out


def _get_model_config(state: AgentState) -> dict[str, Any]:
    """Read model_config from state or fallback to default.

    All agents must call this helper instead of hardcoding a model.
    """
    cfg = state.get("model_config")
    if cfg and cfg.get("model"):
        return cfg
    # Fallback (should not happen in normal flow — graph.run_turn populates it)
    from .model_resolver import get_default_model_config
    logger.warning("Agent: no model_config in state, using default")
    return get_default_model_config()


class ReceptionAgent(BaseAgent):
    name = "reception"

    def _get_tools(self):
        from main import list_professionals, list_services  # type: ignore
        return [list_professionals, list_services]

    async def run(self, state: AgentState) -> AgentState:
        tools = self._get_tools()
        cfg = _get_model_config(state)
        prompt = (
            "Sos la recepcionista virtual de una clínica dental. "
            "Respondés saludos, preguntas generales sobre la clínica, listás servicios y profesionales. "
            "Sos cálida, breve y profesional. Respondé en español rioplatense (voseo). "
            "Si el paciente pide agendar un turno, decile que lo estás conectando con el sistema de turnos."
        )
        executor = _build_executor(tools, cfg, prompt)
        try:
            result = await executor.ainvoke({
                "input": state.get("user_message", ""),
                "chat_history": _history_to_messages(state.get("chat_history", [])),
            })
            state["agent_output"] = result.get("output", "") or ""
        except Exception:
            logger.exception("ReceptionAgent failed")
            state["agent_output"] = "Disculpá, tuve un problema procesando tu mensaje. ¿Me lo podés repetir?"

        state["active_agent"] = "END"
        return state


class BookingAgent(BaseAgent):
    name = "booking"

    def _get_tools(self):
        from main import (  # type: ignore
            book_appointment,
            cancel_appointment,
            check_availability,
            confirm_slot,
            list_my_appointments,
            list_services,
            reschedule_appointment,
        )
        return [
            check_availability, confirm_slot, book_appointment,
            list_my_appointments, cancel_appointment, reschedule_appointment, list_services,
        ]

    async def run(self, state: AgentState) -> AgentState:
        tools = self._get_tools()
        cfg = _get_model_config(state)
        prompt = (
            "Sos el agente de turnos de una clínica dental. "
            "Tu único rol: manejar disponibilidad, reservar, cancelar y reprogramar turnos. "
            "Usá las tools disponibles. Cuando el paciente confirma un horario explícitamente "
            "('agendame el del X', 'quiero ese', '1', '2'), llamá confirm_slot y luego book_appointment. "
            "NUNCA re-llames check_availability si el paciente ya eligió un slot. "
            "Respondé en español rioplatense. Sé conciso."
        )
        executor = _build_executor(tools, cfg, prompt)
        try:
            result = await executor.ainvoke({
                "input": state.get("user_message", ""),
                "chat_history": _history_to_messages(state.get("chat_history", [])),
            })
            state["agent_output"] = result.get("output", "") or ""
        except Exception:
            logger.exception("BookingAgent failed")
            state["agent_output"] = "No pude procesar tu pedido de turno en este momento. ¿Me lo repetís?"

        state["active_agent"] = "END"
        return state


class TriageAgent(BaseAgent):
    name = "triage"

    def _get_tools(self):
        from main import derivhumano, triage_urgency  # type: ignore
        return [triage_urgency, derivhumano]

    async def run(self, state: AgentState) -> AgentState:
        tools = self._get_tools()
        cfg = _get_model_config(state)
        prompt = (
            "Sos el agente de triaje clínico dental. Tu rol: evaluar urgencia de síntomas dentales "
            "(dolor, sangrado, trauma, hinchazón) y decidir si es emergencia. "
            "Siempre usá la tool triage_urgency para analizar síntomas. "
            "Si detectás emergencia (dolor severo 8+, trauma con fractura, sangrado abundante), "
            "usá derivhumano para escalar al staff. "
            "Sé empático pero profesional. Español rioplatense."
        )
        executor = _build_executor(tools, cfg, prompt)
        try:
            result = await executor.ainvoke({
                "input": state.get("user_message", ""),
                "chat_history": _history_to_messages(state.get("chat_history", [])),
            })
            state["agent_output"] = result.get("output", "") or ""
        except Exception:
            logger.exception("TriageAgent failed")
            state["agent_output"] = "Entiendo tu preocupación. Un momento mientras te conectamos con el equipo clínico."

        state["active_agent"] = "END"
        return state


class BillingAgent(BaseAgent):
    name = "billing"

    def _get_tools(self):
        from main import verify_payment_receipt  # type: ignore
        return [verify_payment_receipt]

    async def run(self, state: AgentState) -> AgentState:
        tools = self._get_tools()
        cfg = _get_model_config(state)
        prompt = (
            "Sos el agente de cobros y verificación de pagos. "
            "Verificás comprobantes de transferencia usando la tool verify_payment_receipt. "
            "Si el pago está OK, confirmás al paciente. Si hay problemas (monto incorrecto, titular no coincide), "
            "le explicás qué falta. Español rioplatense, tono profesional y amable."
        )
        executor = _build_executor(tools, cfg, prompt)
        try:
            result = await executor.ainvoke({
                "input": state.get("user_message", ""),
                "chat_history": _history_to_messages(state.get("chat_history", [])),
            })
            state["agent_output"] = result.get("output", "") or ""
        except Exception:
            logger.exception("BillingAgent failed")
            state["agent_output"] = "No pude verificar el comprobante ahora. ¿Me lo podés enviar de nuevo?"

        state["active_agent"] = "END"
        return state


class AnamnesisAgent(BaseAgent):
    name = "anamnesis"

    def _get_tools(self):
        from main import (  # type: ignore
            get_patient_anamnesis,
            save_patient_anamnesis,
            save_patient_email,
        )
        return [save_patient_anamnesis, get_patient_anamnesis, save_patient_email]

    async def run(self, state: AgentState) -> AgentState:
        tools = self._get_tools()
        cfg = _get_model_config(state)
        prompt = (
            "Sos el agente de historia clínica (anamnesis) dental. "
            "Ayudás al paciente a completar su ficha médica: alergias, medicación, condiciones preexistentes. "
            "Podés consultar anamnesis guardada con get_patient_anamnesis y guardar con save_patient_anamnesis. "
            "Si el paciente pide actualizar su email, usá save_patient_email. Español rioplatense."
        )
        executor = _build_executor(tools, cfg, prompt)
        try:
            result = await executor.ainvoke({
                "input": state.get("user_message", ""),
                "chat_history": _history_to_messages(state.get("chat_history", [])),
            })
            state["agent_output"] = result.get("output", "") or ""
        except Exception:
            logger.exception("AnamnesisAgent failed")
            state["agent_output"] = "Disculpá, no pude procesar eso. ¿Podés reformular tu mensaje?"

        state["active_agent"] = "END"
        return state


class HandoffAgent(BaseAgent):
    name = "handoff"

    def _get_tools(self):
        from main import derivhumano  # type: ignore
        return [derivhumano]

    async def run(self, state: AgentState) -> AgentState:
        tools = self._get_tools()
        cfg = _get_model_config(state)
        prompt = (
            "Sos el agente de derivación humana. Cuando el paciente pide hablar con una persona, "
            "o cuando otros agentes fallan, usás derivhumano para enviar al staff clínico. "
            "Confirmás al paciente que un humano se va a contactar pronto. "
            "Español rioplatense, tono tranquilizador."
        )
        executor = _build_executor(tools, cfg, prompt)
        try:
            result = await executor.ainvoke({
                "input": state.get("user_message", ""),
                "chat_history": _history_to_messages(state.get("chat_history", [])),
            })
            state["agent_output"] = result.get("output", "") or ""
        except Exception:
            logger.exception("HandoffAgent failed")
            state["agent_output"] = "Ya avisé al equipo de la clínica, alguien te va a responder en breve."

        state["active_agent"] = "END"
        return state


# Registry (singletons)
AGENTS: dict[str, BaseAgent] = {
    "reception": ReceptionAgent(),
    "booking": BookingAgent(),
    "triage": TriageAgent(),
    "billing": BillingAgent(),
    "anamnesis": AnamnesisAgent(),
    "handoff": HandoffAgent(),
}
