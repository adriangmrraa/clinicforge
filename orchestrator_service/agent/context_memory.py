"""
Sistema de memoria contextual por paciente - FASE 2
Almacena estado de conversación y datos recolectados
"""

import json
import asyncio
from typing import Dict, List, Optional, Any, Set
from datetime import datetime, timedelta
import logging
from dataclasses import dataclass, asdict, field
from enum import Enum

logger = logging.getLogger(__name__)


class EmotionalState(Enum):
    """Estados emocionales del paciente"""
    CALM = "calm"
    ANXIOUS = "anxious"
    ANGRY = "angry"
    HAPPY = "happy"
    FRUSTRATED = "frustrated"
    PAIN = "pain"


class ConversationIntent(Enum):
    """Intenciones detectadas en la conversación"""
    BOOKING = "booking"
    INFO_REQUEST = "info_request"
    URGENCY = "urgency"
    LOCATION = "location"
    PRICING = "pricing"
    FOLLOW_UP = "follow_up"
    CANCELLATION = "cancellation"
    RESCHEDULE = "reschedule"
    OTHER = "other"


@dataclass
class PatientConversationState:
    """Estado de conversación para un paciente específico"""
    patient_id: str
    tenant_id: int
    last_intent: Optional[ConversationIntent] = None
    collected_data: Dict[str, Any] = field(default_factory=dict)
    pending_steps: List[str] = field(default_factory=list)
    emotional_state: EmotionalState = EmotionalState.CALM
    last_message_time: datetime = field(default_factory=datetime.now)
    conversation_history: List[Dict[str, Any]] = field(default_factory=list)
    current_treatment: Optional[str] = None
    preferred_date: Optional[str] = None
    preferred_time: Optional[str] = None
    selected_professional: Optional[str] = None
    booking_in_progress: bool = False
    anamnesis_started: bool = False
    anamnesis_data: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convierte a dict para serialización"""
        data = asdict(self)
        data['last_intent'] = self.last_intent.value if self.last_intent else None
        data['emotional_state'] = self.emotional_state.value
        data['last_message_time'] = self.last_message_time.isoformat()
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'PatientConversationState':
        """Crea instancia desde dict"""
        # Convertir strings de vuelta a enums
        if data.get('last_intent'):
            data['last_intent'] = ConversationIntent(data['last_intent'])
        if data.get('emotional_state'):
            data['emotional_state'] = EmotionalState(data['emotional_state'])
        if data.get('last_message_time'):
            data['last_message_time'] = datetime.fromisoformat(data['last_message_time'])
        
        return cls(**data)
    
    def update_intent(self, intent: ConversationIntent):
        """Actualiza la intención detectada"""
        self.last_intent = intent
        self.last_message_time = datetime.now()
    
    def add_collected_data(self, key: str, value: Any):
        """Agrega dato recolectado"""
        self.collected_data[key] = value
        logger.info(f"Dato recolectado para paciente {self.patient_id}: {key}={value}")
    
    def get_collected_data(self, key: str, default: Any = None) -> Any:
        """Obtiene dato recolectado"""
        return self.collected_data.get(key, default)
    
    def has_collected_data(self, key: str) -> bool:
        """Verifica si tiene dato recolectado"""
        return key in self.collected_data
    
    def add_pending_step(self, step: str):
        """Agrega paso pendiente"""
        if step not in self.pending_steps:
            self.pending_steps.append(step)
    
    def complete_pending_step(self, step: str):
        """Completa paso pendiente"""
        if step in self.pending_steps:
            self.pending_steps.remove(step)
    
    def add_conversation_turn(self, role: str, content: str, tool_calls: List[Dict] = None):
        """Agrega turno a historial de conversación"""
        turn = {
            "role": role,
            "content": content,
            "timestamp": datetime.now().isoformat(),
            "tool_calls": tool_calls or []
        }
        self.conversation_history.append(turn)
        
        # Mantener solo últimos 20 turnos para no crecer demasiado
        if len(self.conversation_history) > 20:
            self.conversation_history = self.conversation_history[-20:]
    
    def get_recent_context(self, max_turns: int = 5) -> List[Dict[str, Any]]:
        """Obtiene contexto reciente de la conversación"""
        return self.conversation_history[-max_turns:] if self.conversation_history else []
    
    def is_stale(self, timeout_minutes: int = 60) -> bool:
        """Verifica si el estado está obsoleto (sin actividad)"""
        time_since_last = datetime.now() - self.last_message_time
        return time_since_last > timedelta(minutes=timeout_minutes)


class ConversationMemoryManager:
    """Gestor de memoria de conversaciones por paciente"""
    
    def __init__(self):
        self._memory_store: Dict[str, PatientConversationState] = {}
        self._lock = asyncio.Lock()
    
    def _get_key(self, patient_id: str, tenant_id: int) -> str:
        """Genera clave única para paciente+tenant"""
        return f"{tenant_id}:{patient_id}"
    
    async def get_or_create_state(self, patient_id: str, tenant_id: int) -> PatientConversationState:
        """Obtiene o crea estado de conversación"""
        key = self._get_key(patient_id, tenant_id)
        
        async with self._lock:
            if key not in self._memory_store:
                self._memory_store[key] = PatientConversationState(
                    patient_id=patient_id,
                    tenant_id=tenant_id
                )
                logger.info(f"Nuevo estado de conversación creado para {key}")
            
            return self._memory_store[key]
    
    async def update_state(self, patient_id: str, tenant_id: int, 
                          updates: Dict[str, Any]) -> PatientConversationState:
        """Actualiza estado de conversación"""
        state = await self.get_or_create_state(patient_id, tenant_id)
        
        async with self._lock:
            for key, value in updates.items():
                if hasattr(state, key):
                    setattr(state, key, value)
            
            state.last_message_time = datetime.now()
        
        return state
    
    async def add_conversation_turn(self, patient_id: str, tenant_id: int,
                                   role: str, content: str, tool_calls: List[Dict] = None):
        """Agrega turno a la conversación"""
        state = await self.get_or_create_state(patient_id, tenant_id)
        state.add_conversation_turn(role, content, tool_calls)
    
    async def get_context_summary(self, patient_id: str, tenant_id: int) -> Dict[str, Any]:
        """Obtiene resumen del contexto actual"""
        state = await self.get_or_create_state(patient_id, tenant_id)
        
        return {
            "patient_id": patient_id,
            "tenant_id": tenant_id,
            "last_intent": state.last_intent.value if state.last_intent else None,
            "emotional_state": state.emotional_state.value,
            "current_treatment": state.current_treatment,
            "preferred_date": state.preferred_date,
            "preferred_time": state.preferred_time,
            "collected_data_keys": list(state.collected_data.keys()),
            "pending_steps": state.pending_steps,
            "booking_in_progress": state.booking_in_progress,
            "anamnesis_started": state.anamnesis_started,
            "conversation_turns": len(state.conversation_history),
            "minutes_since_last": (datetime.now() - state.last_message_time).total_seconds() / 60
        }
    
    async def clear_stale_states(self, timeout_minutes: int = 120):
        """Limpia estados obsoletos"""
        async with self._lock:
            stale_keys = []
            for key, state in self._memory_store.items():
                if state.is_stale(timeout_minutes):
                    stale_keys.append(key)
            
            for key in stale_keys:
                del self._memory_store[key]
            
            if stale_keys:
                logger.info(f"Limpieza de {len(stale_keys)} estados obsoletos")
    
    async def save_to_database(self, db_pool, patient_id: str, tenant_id: int):
        """Guarda estado en base de datos para persistencia"""
        state = await self.get_or_create_state(patient_id, tenant_id)
        
        try:
            state_data = state.to_dict()
            
            await db_pool.execute("""
                INSERT INTO patient_conversation_state 
                (patient_id, tenant_id, state_data, updated_at)
                VALUES ($1, $2, $3, NOW())
                ON CONFLICT (patient_id, tenant_id) 
                DO UPDATE SET state_data = $3, updated_at = NOW()
            """, patient_id, tenant_id, json.dumps(state_data))
            
            logger.debug(f"Estado guardado en BD para paciente {patient_id}")
            
        except Exception as e:
            logger.error(f"Error guardando estado en BD: {e}")
    
    async def load_from_database(self, db_pool, patient_id: str, tenant_id: int) -> bool:
        """Carga estado desde base de datos"""
        try:
            result = await db_pool.fetchrow("""
                SELECT state_data FROM patient_conversation_state
                WHERE patient_id = $1 AND tenant_id = $2
            """, patient_id, tenant_id)
            
            if result and result['state_data']:
                state_data = json.loads(result['state_data'])
                state = PatientConversationState.from_dict(state_data)
                
                key = self._get_key(patient_id, tenant_id)
                async with self._lock:
                    self._memory_store[key] = state
                
                logger.info(f"Estado cargado desde BD para paciente {patient_id}")
                return True
            
        except Exception as e:
            logger.error(f"Error cargando estado desde BD: {e}")
        
        return False


# Instancia global del gestor de memoria
memory_manager = ConversationMemoryManager()


# Funciones de utilidad para uso en el agente
async def get_patient_context(patient_id: str, tenant_id: int) -> Dict[str, Any]:
    """Obtiene contexto del paciente para inyección en prompt"""
    summary = await memory_manager.get_context_summary(patient_id, tenant_id)
    
    # Construir contexto legible
    context_parts = []
    
    if summary['current_treatment']:
        context_parts.append(f"Tratamiento actual: {summary['current_treatment']}")
    
    if summary['preferred_date']:
        context_parts.append(f"Fecha preferida: {summary['preferred_date']}")
    
    if summary['preferred_time']:
        context_parts.append(f"Horario preferido: {summary['preferred_time']}")
    
    if summary['collected_data_keys']:
        context_parts.append(f"Datos recolectados: {', '.join(summary['collected_data_keys'])}")
    
    if summary['pending_steps']:
        context_parts.append(f"Pasos pendientes: {', '.join(summary['pending_steps'])}")
    
    if summary['booking_in_progress']:
        context_parts.append("AGENDAMIENTO EN CURSO - No preguntar tratamiento/fecha nuevamente")
    
    if summary['anamnesis_started']:
        context_parts.append("ANAMNESIS EN CURSO - Continuar con preguntas de salud")
    
    if summary['emotional_state'] != 'calm':
        context_parts.append(f"Estado emocional: {summary['emotional_state'].upper()}")
    
    context_text = "\n".join(context_parts) if context_parts else "Sin contexto previo"
    
    return {
        "summary": summary,
        "text": context_text,
        "has_context": len(context_parts) > 0
    }


async def update_conversation_intent(patient_id: str, tenant_id: int, 
                                    intent: ConversationIntent, 
                                    treatment: Optional[str] = None,
                                    date_pref: Optional[str] = None,
                                    time_pref: Optional[str] = None):
    """Actualiza intención y datos relacionados"""
    updates = {}
    
    if treatment:
        updates['current_treatment'] = treatment
    
    if date_pref:
        updates['preferred_date'] = date_pref
    
    if time_pref:
        updates['preferred_time'] = time_pref
    
    if intent == ConversationIntent.BOOKING:
        updates['booking_in_progress'] = True
    
    state = await memory_manager.update_state(patient_id, tenant_id, updates)
    state.update_intent(intent)
    
    logger.info(f"Intención actualizada para {patient_id}: {intent.value}")


async def add_collected_patient_data(patient_id: str, tenant_id: int, 
                                    data_type: str, value: str):
    """Agrega dato recolectado del paciente"""
    state = await memory_manager.get_or_create_state(patient_id, tenant_id)
    state.add_collected_data(data_type, value)
    
    # Si es nombre/apellido/DNI, marcar como datos esenciales recolectados
    if data_type in ['first_name', 'last_name', 'dni']:
        step_key = f"collect_{data_type}"
        state.complete_pending_step(step_key)