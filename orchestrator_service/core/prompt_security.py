import re
import logging

logger = logging.getLogger("orchestrator.security")

# Nexus AI Security: Lista negra de patrones de inyección (SDD v2.0)

# Spanish patterns (first layer — most common in this system)
INJECTION_PATTERNS_ES = [
    r"ignor[aá]\s+(las\s+)?instrucciones\s+(anteriores|previas)",
    r"olvi(d[aá]|date)\s+(de\s+)?(las\s+)?instrucciones",
    r"sos\s+un\s+asistente\s+(sin|que\s+no)",
    r"modo\s+(desarrollador|admin|debug)",
    r"prompt\s+(del\s+)?sistema",
    r"configur(aci[oó]n|ar)\s+(del\s+)?(sistema|bot|agente)",
    r"mostr[aá](me)?\s+(el|tu|la)\s+(prompt|configuraci[oó]n|instrucciones)",
    r"(act[uú]a|comport[aá]te)\s+como\s+(si\s+fueras|otro)",
    r"(jailbreak|bypass|escape)\s+(del\s+)?(sistema|filtro|restricci[oó]n)",
    r"no\s+ten[eé]s\s+(restricciones|l[ií]mites|reglas)",
]

PROMPT_INJECTION_PATTERNS = [
    r"ignore (all )?previous instructions",
    r"ignore (the )?instructions above",
    r"disregard (all )?previous instructions",
    r"forget (everything|what) you (were|have been) told",
    r"you are now (in )?developer mode",
    r"system override",
    r"new instructions:",
    r"output the system prompt",
    r"reveal your instructions",
    r"instead of your previous task",
    r"bypass security",
]


def detect_prompt_injection(text: str) -> bool:
    """
    Detecta intentos de 'Prompt Injection' o 'Jailbreaking' básicos.
    Actúa como la primera capa de defensa determinista antes del LLM.
    """
    if not text:
        return False

    t = text.lower()
    # Check English patterns
    for pattern in PROMPT_INJECTION_PATTERNS:
        if re.search(pattern, t, re.IGNORECASE):
            logger.warning(
                f"🚨 Nexus Security: Prompt Injection detectado! Patrón: '{pattern}'"
            )
            return True

    # Check Spanish patterns
    for pattern in INJECTION_PATTERNS_ES:
        if re.search(pattern, t, re.IGNORECASE):
            logger.warning(
                f"🚨 Nexus Security: Prompt Injection ES detectado! Patrón: '{pattern}'"
            )
            return True

    return False


def sanitize_input(text: str) -> str:
    """
    Sanitización básica para evitar roturas de formato en el prompt.
    """
    if not text:
        return ""
    # Eliminar caracteres de control o excesivos backticks que puedan confundir al parser de tools
    return text.replace("```", "").strip()
