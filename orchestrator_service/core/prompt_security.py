import re
import logging

logger = logging.getLogger("orchestrator.security")

# Nexus AI Security: Lista negra de patrones de inyección (SDD v2.0)
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
    for pattern in PROMPT_INJECTION_PATTERNS:
        if re.search(pattern, t, re.IGNORECASE):
            logger.warning(f"🚨 Nexus Security: Prompt Injection detectado! Patrón: '{pattern}'")
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
