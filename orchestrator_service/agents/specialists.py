"""Specialized agents: Reception, Booking, Triage, Billing, Anamnesis, Handoff (C3 F3).

Each agent wraps a bounded LangChain AgentExecutor over a subset of DENTAL_TOOLS
from `main`. Tools are imported lazily inside `_get_tools` to avoid circular imports.
"""
from __future__ import annotations

import logging

from langchain.agents import AgentExecutor, create_openai_tools_agent
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

from core.openai_compat import get_chat_model

from .base import BaseAgent
from .state import AgentState

logger = logging.getLogger(__name__)


def _build_executor(tools, model: str, system_prompt: str) -> AgentExecutor:
    llm = get_chat_model(model, temperature=0.2)
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


class ReceptionAgent(BaseAgent):
    name = "reception"
    model = "gpt-4o-mini"

    def _get_tools(self):
        from main import list_professionals, list_services  # type: ignore
        return [list_professionals, list_services]

    async def run(self, state: AgentState) -> AgentState:
        tools = self._get_tools()
        prompt = (
            "Sos la recepcionista virtual de una clínica dental. "
            "Respondés saludos, preguntas generales sobre la clínica, listás servicios y profesionales. "
            "Sos cálida, breve y profesional. Respondé en español rioplatense (voseo). "
            "Si el paciente pide agendar un turno, decile que lo estás conectando con el sistema de turnos."
        )
        executor = _build_executor(tools, self.model, prompt)
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
    model = "gpt-4o-mini"

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
        prompt = (
            "Sos el agente de turnos de una clínica dental. "
            "Tu único rol: manejar disponibilidad, reservar, cancelar y reprogramar turnos. "
            "Usá las tools disponibles. Cuando el paciente confirma un horario explícitamente "
            "('agendame el del X', 'quiero ese', '1', '2'), llamá confirm_slot y luego book_appointment. "
            "NUNCA re-llames check_availability si el paciente ya eligió un slot. "
            "Respondé en español rioplatense. Sé conciso."
        )
        executor = _build_executor(tools, self.model, prompt)
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
    model = "gpt-4o"  # More capable for clinical judgment

    def _get_tools(self):
        from main import derivhumano, triage_urgency  # type: ignore
        return [triage_urgency, derivhumano]

    async def run(self, state: AgentState) -> AgentState:
        tools = self._get_tools()
        prompt = (
            "Sos el agente de triaje clínico dental. Tu rol: evaluar urgencia de síntomas dentales "
            "(dolor, sangrado, trauma, hinchazón) y decidir si es emergencia. "
            "Siempre usá la tool triage_urgency para analizar síntomas. "
            "Si detectás emergencia (dolor severo 8+, trauma con fractura, sangrado abundante), "
            "usá derivhumano para escalar al staff. "
            "Sé empático pero profesional. Español rioplatense."
        )
        executor = _build_executor(tools, self.model, prompt)
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
    model = "gpt-4o-mini"

    def _get_tools(self):
        from main import verify_payment_receipt  # type: ignore
        return [verify_payment_receipt]

    async def run(self, state: AgentState) -> AgentState:
        tools = self._get_tools()
        prompt = (
            "Sos el agente de cobros y verificación de pagos. "
            "Verificás comprobantes de transferencia usando la tool verify_payment_receipt. "
            "Si el pago está OK, confirmás al paciente. Si hay problemas (monto incorrecto, titular no coincide), "
            "le explicás qué falta. Español rioplatense, tono profesional y amable."
        )
        executor = _build_executor(tools, self.model, prompt)
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
    model = "gpt-4o-mini"

    def _get_tools(self):
        from main import (  # type: ignore
            get_patient_anamnesis,
            save_patient_anamnesis,
            save_patient_email,
        )
        return [save_patient_anamnesis, get_patient_anamnesis, save_patient_email]

    async def run(self, state: AgentState) -> AgentState:
        tools = self._get_tools()
        prompt = (
            "Sos el agente de historia clínica (anamnesis) dental. "
            "Ayudás al paciente a completar su ficha médica: alergias, medicación, condiciones preexistentes. "
            "Podés consultar anamnesis guardada con get_patient_anamnesis y guardar con save_patient_anamnesis. "
            "Si el paciente pide actualizar su email, usá save_patient_email. Español rioplatense."
        )
        executor = _build_executor(tools, self.model, prompt)
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
    model = "gpt-4o-mini"

    def _get_tools(self):
        from main import derivhumano  # type: ignore
        return [derivhumano]

    async def run(self, state: AgentState) -> AgentState:
        tools = self._get_tools()
        prompt = (
            "Sos el agente de derivación humana. Cuando el paciente pide hablar con una persona, "
            "o cuando otros agentes fallan, usás derivhumano para enviar al staff clínico. "
            "Confirmás al paciente que un humano se va a contactar pronto. "
            "Español rioplatense, tono tranquilizador."
        )
        executor = _build_executor(tools, self.model, prompt)
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
