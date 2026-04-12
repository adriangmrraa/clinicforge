"""
3-Layer Response Classifier for Playbook Engine V2.

Layer 1: Button text exact match (instant, free)
Layer 2: Keyword match from step.response_rules (instant, free)
Layer 3: LLM classification (1-3s, ~$0.001) — only if layers 1-2 fail
"""

import logging
import re
from typing import Optional, Tuple

logger = logging.getLogger(__name__)

# Button texts from approved YCloud templates
_CONFIRM_BUTTONS = {
    "confirmar asistencia ✅", "confirmar asistencia", "confirmo el turno",
    "confirmar", "confirmo", "sí, confirmo", "si, confirmo",
}
_RESCHEDULE_BUTTONS = {
    "necesito reprogramar", "quiero reprogramar", "reprogramar",
    "no puedo asistir",
}
_CANCEL_BUTTONS = {
    "quiero cancelar", "cancelar turno", "cancelar",
}


def classify_response(
    message_text: str,
    response_rules: list,
) -> Tuple[str, str, Optional[str]]:
    """
    Classify a patient response using 3 layers.

    Args:
        message_text: The patient's response text
        response_rules: List of rule dicts from automation_steps.response_rules
            Each: {"name": "urgencia", "keywords": ["dolor", "sangra"], "action": "notify_and_pause"}

    Returns:
        (classification, action, matched_rule_name)
        - classification: "confirm", "reschedule", "cancel", "positive", "negative",
                          "urgent", "keyword_match", "unclassified"
        - action: "continue", "abort", "pause", "notify_and_pause", "pass_to_ai"
        - matched_rule_name: Name of the matched rule (or None)
    """
    text = (message_text or "").strip().lower()
    if not text:
        return ("unclassified", "pass_to_ai", None)

    # --- Layer 1: Button text exact match ---
    if text in _CONFIRM_BUTTONS:
        return ("confirm", "continue", "button_confirm")
    if text in _RESCHEDULE_BUTTONS:
        return ("reschedule", "pass_to_ai", "button_reschedule")
    if text in _CANCEL_BUTTONS:
        return ("cancel", "abort", "button_cancel")

    # --- Layer 2: Keyword match from step response_rules ---
    if response_rules:
        for rule in response_rules:
            if not isinstance(rule, dict):
                continue
            keywords = rule.get("keywords", [])
            if not keywords:
                continue
            rule_name = rule.get("name", "unknown")
            action = rule.get("action", "continue")

            for keyword in keywords:
                kw = keyword.lower().strip()
                if not kw:
                    continue
                # Word boundary match to avoid false positives
                # e.g., "dolor" matches "me duele mucho" but also "dolor"
                if kw in text or _fuzzy_keyword_match(kw, text):
                    logger.info(
                        f"🔍 Keyword match: '{kw}' in rule '{rule_name}' → action={action}"
                    )
                    return ("keyword_match", action, rule_name)

    # --- Layer 3: LLM classification (deferred — not called here) ---
    # The executor decides whether to call LLM based on step.on_unclassified
    return ("unclassified", "pass_to_ai", None)


async def classify_with_llm(
    message_text: str,
    tenant_id: int,
    context: str = "",
) -> Tuple[str, str]:
    """
    Layer 3: Use LLM to classify ambiguous responses.
    Returns (classification, action).
    """
    try:
        from dashboard.config_manager import ConfigManager

        model = await ConfigManager.get_config_value("OPENAI_MODEL") or "gpt-4o-mini"

        import openai
        client = openai.AsyncOpenAI()

        prompt = f"""Clasificá esta respuesta de un paciente dental en UNA de estas categorías:
- POSITIVO: el paciente confirma, acepta, está contento, dice que está bien
- NEGATIVO: el paciente rechaza, no quiere, está molesto
- URGENCIA: el paciente reporta dolor, sangrado, fiebre, hinchazón, complicación
- PREGUNTA: el paciente tiene una duda o consulta
- REAGENDAR: el paciente quiere cambiar la fecha/hora
- OTRO: no encaja en ninguna categoría

Respuesta del paciente: "{message_text}"
{f'Contexto: {context}' if context else ''}

Respondé SOLO con la categoría en mayúsculas, nada más."""

        response = await client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=20,
            temperature=0,
        )

        classification = (response.choices[0].message.content or "OTRO").strip().upper()

        action_map = {
            "POSITIVO": ("positive", "continue"),
            "NEGATIVO": ("negative", "pause"),
            "URGENCIA": ("urgent", "notify_and_pause"),
            "PREGUNTA": ("question", "pass_to_ai"),
            "REAGENDAR": ("reschedule", "pass_to_ai"),
            "OTRO": ("unclassified", "pass_to_ai"),
        }

        result = action_map.get(classification, ("unclassified", "pass_to_ai"))
        logger.info(f"🤖 LLM classified '{message_text[:50]}' as {classification} → {result}")
        return result

    except Exception as e:
        logger.error(f"❌ LLM classification failed: {e}")
        return ("unclassified", "pass_to_ai")


def _fuzzy_keyword_match(keyword: str, text: str) -> bool:
    """Check if keyword appears as a word (not substring of another word)."""
    try:
        pattern = r'\b' + re.escape(keyword) + r'\b'
        return bool(re.search(pattern, text, re.IGNORECASE))
    except re.error:
        return keyword in text
