"""
Sistema de fallback elegante - FASE 2
Implementa cascada de intentos para manejar malentendidos
"""

import logging
from typing import Dict, List, Optional, Tuple, Any
from enum import Enum
import random

logger = logging.getLogger(__name__)


class FallbackStrategy(Enum):
    """Estrategias de fallback en cascada"""
    REPHRASE = "rephrase"
    MULTIPLE_CHOICE = "multiple_choice"
    SIMPLIFY_LANGUAGE = "simplify_language"
    CLARIFY_SPECIFIC = "clarify_specific"
    DERIVE_HUMAN = "derive_human"


class FallbackHandler:
    """Manejador de fallback elegante con cascada de intentos"""
    
    def __init__(self):
        self.strategies = [
            FallbackStrategy.REPHRASE,
            FallbackStrategy.MULTIPLE_CHOICE,
            FallbackStrategy.SIMPLIFY_LANGUAGE,
            FallbackStrategy.CLARIFY_SPECIFIC,
            FallbackStrategy.DERIVE_HUMAN
        ]
        
        # Contador de fallbacks por conversación
        self.fallback_counters: Dict[str, int] = {}
        
        # Frases para rephrasing
        self.rephrase_phrases = [
            "Perdoná, no entendí bien. ¿Podrías decirlo de otra forma?",
            "Disculpá, me confundí. ¿Me lo decís de nuevo?",
            "No capté del todo. ¿Podés reformularlo?",
            "Creo que no entendí. ¿Me lo explicás de otra manera?",
            "Perdoná la confusión. ¿Podrías repetirlo con otras palabras?"
        ]
        
        # Frases para simplificar lenguaje
        self.simplify_phrases = [
            "Voy a intentar ser más claro. ",
            "Déjame explicarlo más simple. ",
            "Quizás me expresé mal. Te lo digo más fácil: ",
            "Perdoná si fui confuso. En palabras simples: "
        ]
        
        # Frases para clarificación específica
        self.clarify_phrases = [
            "Para ayudarte mejor, ¿podés aclararme específicamente sobre {aspect}?",
            "No estoy seguro de entender la parte de {aspect}. ¿Me lo explicás?",
            "Para poder asistirte, necesito que me aclares: {aspect}",
            "¿Podrías contarme más sobre {aspect}?"
        ]
    
    def _get_conversation_key(self, patient_id: str, tenant_id: int) -> str:
        """Genera clave única para conversación"""
        return f"{tenant_id}:{patient_id}"
    
    def increment_fallback_count(self, patient_id: str, tenant_id: int):
        """Incrementa contador de fallbacks para esta conversación"""
        key = self._get_conversation_key(patient_id, tenant_id)
        self.fallback_counters[key] = self.fallback_counters.get(key, 0) + 1
        
        count = self.fallback_counters[key]
        logger.info(f"Fallback count para {key}: {count}")
        
        # Limpiar contadores viejos (simulación, en producción usaría TTL)
        if count > 10:
            self.fallback_counters.pop(key, None)
    
    def get_fallback_count(self, patient_id: str, tenant_id: int) -> int:
        """Obtiene contador de fallbacks para esta conversación"""
        key = self._get_conversation_key(patient_id, tenant_id)
        return self.fallback_counters.get(key, 0)
    
    def reset_fallback_count(self, patient_id: str, tenant_id: int):
        """Reinicia contador de fallbacks"""
        key = self._get_conversation_key(patient_id, tenant_id)
        self.fallback_counters.pop(key, None)
    
    def select_strategy(self, patient_id: str, tenant_id: int, 
                       error_type: str = "general") -> FallbackStrategy:
        """
        Selecciona estrategia de fallback basada en:
        1. Número de fallbacks previos
        2. Tipo de error
        3. Contexto de la conversación
        """
        fallback_count = self.get_fallback_count(patient_id, tenant_id)
        
        # Cascada basada en número de intentos fallidos
        if fallback_count == 0:
            # Primer fallback: intentar rephrasing
            return FallbackStrategy.REPHRASE
        
        elif fallback_count == 1:
            # Segundo fallback: ofrecer opciones múltiples
            return FallbackStrategy.MULTIPLE_CHOICE
        
        elif fallback_count == 2:
            # Tercer fallback: simplificar lenguaje
            return FallbackStrategy.SIMPLIFY_LANGUAGE
        
        elif fallback_count == 3:
            # Cuarto fallback: pedir clarificación específica
            return FallbackStrategy.CLARIFY_SPECIFIC
        
        else:
            # Quinto+ fallback: derivar a humano
            return FallbackStrategy.DERIVE_HUMAN
    
    def generate_response(self, strategy: FallbackStrategy, 
                         context: Dict[str, Any] = None) -> str:
        """
        Genera respuesta de fallback según la estrategia seleccionada
        """
        context = context or {}
        original_message = context.get("original_message", "")
        error_details = context.get("error_details", "")
        conversation_topic = context.get("conversation_topic", "")
        
        if strategy == FallbackStrategy.REPHRASE:
            return random.choice(self.rephrase_phrases)
        
        elif strategy == FallbackStrategy.MULTIPLE_CHOICE:
            return self._generate_multiple_choice(context)
        
        elif strategy == FallbackStrategy.SIMPLIFY_LANGUAGE:
            base_phrase = random.choice(self.simplify_phrases)
            
            if conversation_topic:
                topics = {
                    "booking": "estás preguntando por turnos. Decime qué tratamiento necesitás y para cuándo.",
                    "info": "querés información. Decime sobre qué tratamiento querés saber.",
                    "location": "querés saber dónde estamos. Estamos en Calle Córdoba 431, Neuquén Capital.",
                    "urgency": "tenés una urgencia. Contame qué síntomas tenés."
                }
                topic_help = topics.get(conversation_topic, "qué necesitás.")
                return base_phrase + topic_help
            else:
                return base_phrase + "¿En qué te puedo ayudar?"
        
        elif strategy == FallbackStrategy.CLARIFY_SPECIFIC:
            aspect = self._identify_unclear_aspect(original_message, error_details)
            phrase_template = random.choice(self.clarify_phrases)
            return phrase_template.format(aspect=aspect)
        
        elif strategy == FallbackStrategy.DERIVE_HUMAN:
            return self._generate_derivation_message(context)
        
        # Fallback por defecto
        return "Perdoná, no entendí. ¿Podrías decirlo de otra forma?"
    
    def _generate_multiple_choice(self, context: Dict[str, Any]) -> str:
        """Genera opciones múltiples basadas en contexto"""
        conversation_topic = context.get("conversation_topic", "")
        
        if conversation_topic == "booking":
            options = [
                "1. Sacar turno para limpieza dental",
                "2. Consultar por implantes",
                "3. Preguntar por blanqueamiento",
                "4. Otra cosa"
            ]
            prompt = "Para ayudarte mejor, decime cuál de estas opciones se acerca a lo que necesitás:\n"
        
        elif conversation_topic == "info":
            options = [
                "1. Información sobre tratamientos",
                "2. Precios y formas de pago",
                "3. Horarios de atención",
                "4. Dirección del consultorio"
            ]
            prompt = "Sobre qué necesitás información específica:\n"
        
        elif conversation_topic == "urgency":
            options = [
                "1. Dolor dental intenso",
                "2. Hinchazón o inflamación",
                "3. Sangrado que no para",
                "4. Accidente o trauma dental"
            ]
            prompt = "Para priorizar tu urgencia, contame cuál de estos síntomas tenés:\n"
        
        else:
            options = [
                "1. Sacar un turno",
                "2. Consultar por un tratamiento",
                "3. Preguntar por ubicación u horarios",
                "4. Otra consulta"
            ]
            prompt = "Para poder asistirte, decime cuál de estas opciones describe mejor lo que necesitás:\n"
        
        options_text = "\n".join(options)
        return prompt + options_text + "\n\nRespondé con el número o decime con tus palabras."
    
    def _identify_unclear_aspect(self, original_message: str, error_details: str) -> str:
        """Identifica aspecto específico que necesita clarificación"""
        message_lower = original_message.lower()
        
        # Detectar aspectos basados en palabras clave
        if any(word in message_lower for word in ["fecha", "día", "cuándo", "mañana", "lunes"]):
            return "la fecha o día que te queda bien"
        
        elif any(word in message_lower for word in ["hora", "horario", "tarde", "mañana"]):
            return "el horario que preferís"
        
        elif any(word in message_lower for word in ["tratamiento", "limpieza", "implante", "blanqueamiento"]):
            return "el tratamiento específico que necesitás"
        
        elif any(word in message_lower for word in ["nombre", "llamo", "apellido"]):
            return "tu nombre y apellido"
        
        elif any(word in message_lower for word in ["dni", "documento", "identificación"]):
            return "tu número de DNI"
        
        elif "dolor" in message_lower or "duele" in message_lower:
            return "los síntomas específicos que tenés"
        
        # Analizar error details si están disponibles
        if error_details:
            if "fecha" in error_details.lower():
                return "la fecha (ej: mañana, el lunes, 15/03)"
            elif "tratamiento" in error_details.lower():
                return "el nombre exacto del tratamiento"
            elif "dni" in error_details.lower():
                return "tu DNI (solo números, sin puntos)"
        
        return "lo que necesitás exactamente"
    
    def _generate_derivation_message(self, context: Dict[str, Any]) -> str:
        """Genera mensaje para derivar a humano"""
        fallback_count = context.get("fallback_count", 0)
        
        messages = [
            "Perdoná, estoy teniendo dificultades para entenderte. Voy a derivarte con un operador humano para que te ayude mejor.",
            "Parece que no estoy pudiendo asistirte adecuadamente. Te voy a conectar con un asistente humano para que resuelva tu consulta.",
            "Para asegurarme de que recibas la mejor atención, te voy a transferir a un operador que te podrá ayudar personalmente.",
            "Lamento las confusiones. Un asistente humano se hará cargo de tu consulta para darte una respuesta precisa."
        ]
        
        base_message = random.choice(messages)
        
        # Agregar contexto si está disponible
        if context.get("conversation_topic"):
            topic = context["conversation_topic"]
            if topic == "urgency":
                base_message += " Por favor, describí tus síntomas al operador para priorizar tu caso."
            elif topic == "booking":
                base_message += " El operador te ayudará a encontrar el mejor horario disponible."
        
        return base_message
    
    def should_derive_to_human(self, patient_id: str, tenant_id: int, 
                              emotional_state: str = "calm") -> bool:
        """
        Determina si se debe derivar a humano basado en:
        1. Número de fallbacks
        2. Estado emocional del paciente
        3. Complejidad de la consulta
        """
        fallback_count = self.get_fallback_count(patient_id, tenant_id)
        
        # Derivar si hay muchos fallbacks
        if fallback_count >= 4:
            return True
        
        # Derivar si el paciente está enojado o frustrado
        if emotional_state in ["angry", "frustrated"]:
            return True
        
        return False
    
    def analyze_conversation_topic(self, message: str) -> str:
        """Analiza el mensaje para identificar el tema de conversación"""
        message_lower = message.lower()
        
        # Palabras clave para cada tema
        booking_keywords = ["turno", "agendar", "sacar cita", "reservar", "cita", "consultorio"]
        info_keywords = ["información", "info", "contame", "explicame", "cómo funciona"]
        location_keywords = ["dónde", "ubicación", "dirección", "maps", "google maps", "llegar"]
        urgency_keywords = ["dolor", "duele", "emergencia", "urgencia", "hinchazón", "sangrado"]
        pricing_keywords = ["precio", "costo", "cuánto sale", "valor", "pago", "obra social"]
        
        # Contar coincidencias
        scores = {
            "booking": sum(1 for kw in booking_keywords if kw in message_lower),
            "info": sum(1 for kw in info_keywords if kw in message_lower),
            "location": sum(1 for kw in location_keywords if kw in message_lower),
            "urgency": sum(1 for kw in urgency_keywords if kw in message_lower),
            "pricing": sum(1 for kw in pricing_keywords if kw in message_lower)
        }
        
        # Obtener tema con mayor score
        max_score = max(scores.values())
        if max_score > 0:
            for topic, score in scores.items():
                if score == max_score:
                    return topic
        
        return "general"


# Instancia global del manejador de fallback
fallback_handler = FallbackHandler()


# Funciones de conveniencia para uso en el agente
def handle_misunderstanding(patient_id: str, tenant_id: int, 
                           original_message: str, 
                           error_details: str = "",
                           context: Dict[str, Any] = None) -> Tuple[str, bool]:
    """
    Maneja malentendido y genera respuesta apropiada
    Retorna: (respuesta, debería_derivar_a_humano)
    """
    # Incrementar contador de fallback
    fallback_handler.increment_fallback_count(patient_id, tenant_id)
    
    # Analizar tema de conversación
    conversation_topic = fallback_handler.analyze_conversation_topic(original_message)
    
    # Preparar contexto
    fb_context = {
        "original_message": original_message,
        "error_details": error_details,
        "conversation_topic": conversation_topic,
        "fallback_count": fallback_handler.get_fallback_count(patient_id, tenant_id)
    }
    
    if context:
        fb_context.update(context)
    
    # Seleccionar estrategia
    strategy = fallback_handler.select_strategy(patient_id, tenant_id)
    
    # Verificar si debería derivar a humano
    should_derive = fallback_handler.should_derive_to_human(patient_id, tenant_id)
    
    if should_derive:
        strategy = FallbackStrategy.DERIVE_HUMAN
    
    # Generar respuesta
    response = fallback_handler.generate_response(strategy, fb_context)
    
    logger.info(f"Fallback para {patient_id}: estrategia={strategy.value}, derivar={should_derive}")
    
    return response, should_derive


def reset_conversation_fallback(patient_id: str, tenant_id: int):
    """Reinicia contador de fallbacks (ej: cuando se resuelve un malentendido)"""
    fallback_handler.reset_fallback_count(patient_id, tenant_id)
    logger.debug(f"Fallbacks reiniciados para {patient_id}")