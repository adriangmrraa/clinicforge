"""
Nova Dental Assistant — Tool definitions & async dispatcher for OpenAI Realtime function calling.

24 tools organized by category:
  A. Pacientes (6)
  B. Turnos (6)
  C. Tratamientos/Facturacion (3)
  D. Analytics/Config (3)
  E. Navegacion (2)
  F. Multi-sede CEO (4)

Each tool returns a plain string that OpenAI Realtime will speak back to the user.
Navigation tools return JSON strings with type="navigation" for frontend handling.
"""

import json
import logging
import uuid
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any, Dict, List, Optional

from db import db

logger = logging.getLogger(__name__)


# =============================================================================
# NOVA_TOOLS_SCHEMA — OpenAI function calling format
# =============================================================================

NOVA_TOOLS_SCHEMA: List[Dict[str, Any]] = [
    # -------------------------------------------------------------------------
    # A. Pacientes (6)
    # -------------------------------------------------------------------------
    {
        "type": "function",
        "name": "buscar_paciente",
        "description": "Busca un paciente por nombre, apellido, DNI o telefono. Retorna hasta 5 resultados.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Nombre, apellido, DNI o telefono del paciente",
                }
            },
            "required": ["query"],
        },
    },
    {
        "type": "function",
        "name": "ver_paciente",
        "description": "Ver ficha completa de un paciente: datos personales, historial, proximos turnos, obra social.",
        "parameters": {
            "type": "object",
            "properties": {
                "patient_id": {
                    "type": "integer",
                    "description": "ID del paciente",
                }
            },
            "required": ["patient_id"],
        },
    },
    {
        "type": "function",
        "name": "registrar_paciente",
        "description": "Crea un paciente nuevo con datos basicos.",
        "parameters": {
            "type": "object",
            "properties": {
                "first_name": {"type": "string", "description": "Nombre del paciente"},
                "last_name": {"type": "string", "description": "Apellido del paciente"},
                "phone_number": {"type": "string", "description": "Telefono del paciente"},
                "dni": {"type": "string", "description": "DNI del paciente"},
                "insurance_provider": {
                    "type": "string",
                    "description": "Obra social (OSDE, Swiss Medical, etc.)",
                },
                "insurance_id": {
                    "type": "string",
                    "description": "Numero de afiliado de la obra social",
                },
            },
            "required": ["first_name", "last_name", "phone_number"],
        },
    },
    {
        "type": "function",
        "name": "actualizar_paciente",
        "description": "Actualiza un campo especifico de un paciente existente.",
        "parameters": {
            "type": "object",
            "properties": {
                "patient_id": {"type": "integer", "description": "ID del paciente"},
                "field": {
                    "type": "string",
                    "enum": [
                        "phone_number",
                        "email",
                        "insurance_provider",
                        "insurance_id",
                        "notes",
                        "preferred_schedule",
                    ],
                    "description": "Campo a actualizar",
                },
                "value": {"type": "string", "description": "Nuevo valor del campo"},
            },
            "required": ["patient_id", "field", "value"],
        },
    },
    {
        "type": "function",
        "name": "historial_clinico",
        "description": "Ver registros clinicos de un paciente: diagnosticos, tratamientos, odontograma. Solo para CEO y profesionales.",
        "parameters": {
            "type": "object",
            "properties": {
                "patient_id": {
                    "type": "integer",
                    "description": "ID del paciente",
                }
            },
            "required": ["patient_id"],
        },
    },
    {
        "type": "function",
        "name": "registrar_nota_clinica",
        "description": "Agrega nota clinica al registro del paciente con diagnostico y datos del odontograma. Solo para profesionales.",
        "parameters": {
            "type": "object",
            "properties": {
                "patient_id": {"type": "integer", "description": "ID del paciente"},
                "diagnosis": {"type": "string", "description": "Diagnostico clinico"},
                "treatment_notes": {
                    "type": "string",
                    "description": "Notas del tratamiento realizado",
                },
                "tooth_number": {
                    "type": "integer",
                    "description": "Numero de pieza dental (nomenclatura FDI)",
                },
                "tooth_status": {
                    "type": "string",
                    "enum": [
                        "caries",
                        "restoration",
                        "extraction",
                        "crown",
                        "implant",
                        "root_canal",
                        "treatment_planned",
                    ],
                    "description": "Estado de la pieza dental",
                },
                "surface": {
                    "type": "string",
                    "enum": ["occlusal", "mesial", "distal", "buccal", "lingual"],
                    "description": "Superficie dental afectada",
                },
            },
            "required": ["patient_id", "diagnosis"],
        },
    },
    # -------------------------------------------------------------------------
    # B. Turnos (6)
    # -------------------------------------------------------------------------
    {
        "type": "function",
        "name": "ver_agenda",
        "description": "Ver turnos de hoy o de una fecha especifica. Muestra horario, paciente, tipo de tratamiento y estado.",
        "parameters": {
            "type": "object",
            "properties": {
                "date": {
                    "type": "string",
                    "description": "Fecha en formato YYYY-MM-DD. Default: hoy",
                },
                "professional_id": {
                    "type": "integer",
                    "description": "ID del profesional. Default: usuario actual si es profesional",
                },
            },
        },
    },
    {
        "type": "function",
        "name": "proximo_paciente",
        "description": "Retorna el siguiente turno del dia para el profesional actual.",
        "parameters": {"type": "object", "properties": {}},
    },
    {
        "type": "function",
        "name": "verificar_disponibilidad",
        "description": "Verifica si hay disponibilidad para un tipo de tratamiento en una fecha determinada.",
        "parameters": {
            "type": "object",
            "properties": {
                "date": {
                    "type": "string",
                    "description": "Fecha en formato YYYY-MM-DD",
                },
                "treatment_type": {
                    "type": "string",
                    "description": "Tipo de tratamiento: checkup, cleaning, extraction, root_canal, etc.",
                },
                "professional_id": {
                    "type": "integer",
                    "description": "ID del profesional especifico (opcional)",
                },
            },
            "required": ["date"],
        },
    },
    {
        "type": "function",
        "name": "agendar_turno",
        "description": "Agenda un turno para un paciente en una fecha y hora especifica.",
        "parameters": {
            "type": "object",
            "properties": {
                "patient_id": {"type": "integer", "description": "ID del paciente"},
                "date": {
                    "type": "string",
                    "description": "Fecha en formato YYYY-MM-DD",
                },
                "time": {
                    "type": "string",
                    "description": "Hora en formato HH:MM (24h)",
                },
                "treatment_type": {
                    "type": "string",
                    "description": "Tipo de tratamiento",
                },
                "professional_id": {
                    "type": "integer",
                    "description": "ID del profesional (opcional)",
                },
                "notes": {
                    "type": "string",
                    "description": "Notas adicionales del turno",
                },
            },
            "required": ["patient_id", "date", "time", "treatment_type"],
        },
    },
    {
        "type": "function",
        "name": "cancelar_turno",
        "description": "Cancela un turno existente.",
        "parameters": {
            "type": "object",
            "properties": {
                "appointment_id": {
                    "type": "string",
                    "description": "UUID del turno a cancelar",
                },
                "reason": {
                    "type": "string",
                    "description": "Motivo de la cancelacion",
                },
            },
            "required": ["appointment_id"],
        },
    },
    {
        "type": "function",
        "name": "confirmar_turnos",
        "description": "Confirma uno o todos los turnos pendientes del dia.",
        "parameters": {
            "type": "object",
            "properties": {
                "appointment_ids": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Lista de UUIDs de turnos. Vacio o ausente = confirmar todos los pendientes de hoy.",
                }
            },
        },
    },
    # -------------------------------------------------------------------------
    # C. Tratamientos y Facturacion (3)
    # -------------------------------------------------------------------------
    {
        "type": "function",
        "name": "listar_tratamientos",
        "description": "Lista tipos de tratamiento disponibles con precios y duracion.",
        "parameters": {
            "type": "object",
            "properties": {
                "category": {
                    "type": "string",
                    "enum": [
                        "prevention",
                        "restorative",
                        "surgical",
                        "orthodontics",
                        "emergency",
                    ],
                    "description": "Filtrar por categoria (opcional)",
                }
            },
        },
    },
    {
        "type": "function",
        "name": "registrar_pago",
        "description": "Registra el pago de un turno completado. Solo para CEO y secretarias.",
        "parameters": {
            "type": "object",
            "properties": {
                "appointment_id": {
                    "type": "string",
                    "description": "UUID del turno",
                },
                "amount": {
                    "type": "number",
                    "description": "Monto pagado",
                },
                "method": {
                    "type": "string",
                    "enum": ["cash", "card", "transfer", "insurance"],
                    "description": "Metodo de pago",
                },
                "notes": {
                    "type": "string",
                    "description": "Notas del pago",
                },
            },
            "required": ["appointment_id", "amount", "method"],
        },
    },
    {
        "type": "function",
        "name": "facturacion_pendiente",
        "description": "Lista turnos completados que aun no tienen pago registrado.",
        "parameters": {"type": "object", "properties": {}},
    },
    # -------------------------------------------------------------------------
    # D. Analytics y Configuracion (3)
    # -------------------------------------------------------------------------
    {
        "type": "function",
        "name": "resumen_semana",
        "description": "Resumen semanal: turnos, cancelaciones, pacientes nuevos, facturacion. Solo para CEO.",
        "parameters": {"type": "object", "properties": {}},
    },
    {
        "type": "function",
        "name": "rendimiento_profesional",
        "description": "Metricas de rendimiento de un profesional: turnos completados, tasa de cancelacion, retencion de pacientes. Solo para CEO.",
        "parameters": {
            "type": "object",
            "properties": {
                "professional_id": {
                    "type": "integer",
                    "description": "ID del profesional a evaluar",
                },
                "period": {
                    "type": "string",
                    "enum": ["week", "month", "quarter"],
                    "description": "Periodo de analisis",
                },
            },
            "required": ["professional_id"],
        },
    },
    {
        "type": "function",
        "name": "actualizar_faq",
        "description": "Agrega o actualiza una pregunta frecuente de la clinica (usada por el agente de WhatsApp).",
        "parameters": {
            "type": "object",
            "properties": {
                "question": {
                    "type": "string",
                    "description": "Pregunta frecuente",
                },
                "answer": {
                    "type": "string",
                    "description": "Respuesta a la pregunta",
                },
            },
            "required": ["question", "answer"],
        },
    },
    # -------------------------------------------------------------------------
    # E. Navegacion (2)
    # -------------------------------------------------------------------------
    {
        "type": "function",
        "name": "ir_a_pagina",
        "description": "Navega a una pagina de ClinicForge en el navegador del usuario.",
        "parameters": {
            "type": "object",
            "properties": {
                "page": {
                    "type": "string",
                    "enum": [
                        "agenda",
                        "pacientes",
                        "chats",
                        "tratamientos",
                        "analytics",
                        "configuracion",
                        "marketing",
                        "leads",
                    ],
                    "description": "Pagina destino",
                }
            },
            "required": ["page"],
        },
    },
    {
        "type": "function",
        "name": "ir_a_paciente",
        "description": "Abre la ficha de un paciente especifico en el navegador del usuario.",
        "parameters": {
            "type": "object",
            "properties": {
                "patient_id": {
                    "type": "integer",
                    "description": "ID del paciente a abrir",
                }
            },
            "required": ["patient_id"],
        },
    },
    # -------------------------------------------------------------------------
    # F. Multi-sede CEO (4)
    # -------------------------------------------------------------------------
    {
        "type": "function",
        "name": "resumen_sedes",
        "description": "Resumen consolidado de todas las sedes: turnos, pacientes, facturacion, score por sede. Solo para CEO.",
        "parameters": {"type": "object", "properties": {}},
    },
    {
        "type": "function",
        "name": "comparar_sedes",
        "description": "Compara metricas entre sedes: cancelaciones, nuevos pacientes, facturacion, ocupacion. Solo para CEO.",
        "parameters": {
            "type": "object",
            "properties": {
                "metric": {
                    "type": "string",
                    "enum": [
                        "cancelaciones",
                        "nuevos_pacientes",
                        "facturacion",
                        "ocupacion",
                        "satisfaccion",
                    ],
                    "description": "Metrica a comparar",
                },
                "period": {
                    "type": "string",
                    "enum": ["hoy", "semana", "mes"],
                    "description": "Periodo de comparacion",
                },
            },
            "required": ["metric"],
        },
    },
    {
        "type": "function",
        "name": "switch_sede",
        "description": "Cambia el contexto activo a otra sede. Solo para CEO.",
        "parameters": {
            "type": "object",
            "properties": {
                "clinic_name": {
                    "type": "string",
                    "description": "Nombre o parte del nombre de la sede",
                }
            },
            "required": ["clinic_name"],
        },
    },
    {
        "type": "function",
        "name": "onboarding_status",
        "description": "Ver estado de configuracion/onboarding de la sede actual o una sede especifica.",
        "parameters": {
            "type": "object",
            "properties": {
                "clinic_name": {
                    "type": "string",
                    "description": "Nombre de la sede (opcional, default: sede actual)",
                }
            },
        },
    },

    # === G. TOOLS QUE FALTAN — Staff operations ===

    {
        "type": "function",
        "function": {
            "name": "listar_profesionales",
            "description": "Lista dentistas/profesionales activos con especialidad, horarios y precio de consulta.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "reprogramar_turno",
            "description": "Reprograma un turno existente a nueva fecha/hora.",
            "parameters": {
                "type": "object",
                "properties": {
                    "appointment_id": {"type": "string", "description": "UUID del turno"},
                    "new_date": {"type": "string", "description": "Nueva fecha YYYY-MM-DD"},
                    "new_time": {"type": "string", "description": "Nueva hora HH:MM (24h)"},
                },
                "required": ["appointment_id", "new_date", "new_time"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "ver_configuracion",
            "description": "Ver configuracion de la clinica: nombre, direccion, horarios, datos bancarios, precio consulta.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "actualizar_configuracion",
            "description": "Actualizar configuracion de la clinica. Solo CEO.",
            "parameters": {
                "type": "object",
                "properties": {
                    "field": {"type": "string", "enum": ["clinic_name", "clinic_location", "clinic_phone", "working_hours_start", "working_hours_end", "bank_cbu", "bank_alias", "bank_holder_name", "consultation_price", "website"]},
                    "value": {"type": "string"},
                },
                "required": ["field", "value"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "crear_tratamiento",
            "description": "Crear nuevo tipo de tratamiento. Solo CEO.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "code": {"type": "string", "description": "Codigo unico (ej: blanqueamiento, ortodoncia)"},
                    "duration_minutes": {"type": "integer"},
                    "base_price": {"type": "number"},
                    "category": {"type": "string", "enum": ["prevention", "restorative", "surgical", "orthodontics", "emergency"]},
                },
                "required": ["name", "code", "duration_minutes"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "editar_tratamiento",
            "description": "Editar un tipo de tratamiento existente. Solo CEO.",
            "parameters": {
                "type": "object",
                "properties": {
                    "code": {"type": "string"},
                    "field": {"type": "string", "enum": ["name", "duration_minutes", "base_price", "category", "is_active"]},
                    "value": {"type": "string"},
                },
                "required": ["code", "field", "value"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "ver_chats_recientes",
            "description": "Ver ultimas conversaciones de WhatsApp/Instagram/Facebook con pacientes.",
            "parameters": {
                "type": "object",
                "properties": {
                    "limit": {"type": "integer", "description": "Cantidad de chats (default 10)"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "enviar_mensaje",
            "description": "Enviar mensaje de WhatsApp a un paciente.",
            "parameters": {
                "type": "object",
                "properties": {
                    "phone": {"type": "string", "description": "Telefono del paciente con codigo de area"},
                    "message": {"type": "string", "description": "Texto del mensaje"},
                },
                "required": ["phone", "message"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "ver_estadisticas",
            "description": "Estadisticas generales: turnos, pacientes, facturacion, cancelaciones. Acepta periodo.",
            "parameters": {
                "type": "object",
                "properties": {
                    "period": {"type": "string", "enum": ["hoy", "semana", "mes", "año"], "description": "Periodo (default: semana)"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "bloquear_agenda",
            "description": "Crear bloque de horario no disponible en la agenda (reunion, descanso, etc).",
            "parameters": {
                "type": "object",
                "properties": {
                    "professional_id": {"type": "integer"},
                    "start_datetime": {"type": "string", "description": "Inicio YYYY-MM-DD HH:MM"},
                    "end_datetime": {"type": "string", "description": "Fin YYYY-MM-DD HH:MM"},
                    "reason": {"type": "string"},
                },
                "required": ["professional_id", "start_datetime", "end_datetime"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "eliminar_paciente",
            "description": "Desactivar un paciente (soft delete). Solo CEO.",
            "parameters": {
                "type": "object",
                "properties": {
                    "patient_id": {"type": "integer"},
                },
                "required": ["patient_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "ver_faqs",
            "description": "Lista las FAQs configuradas para el chatbot de WhatsApp.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "eliminar_faq",
            "description": "Eliminar una FAQ por ID.",
            "parameters": {
                "type": "object",
                "properties": {
                    "faq_id": {"type": "integer"},
                },
                "required": ["faq_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "cambiar_estado_turno",
            "description": "Cambiar estado de un turno: completed, no-show, in-progress.",
            "parameters": {
                "type": "object",
                "properties": {
                    "appointment_id": {"type": "string"},
                    "status": {"type": "string", "enum": ["completed", "no-show", "in-progress", "confirmed"]},
                },
                "required": ["appointment_id", "status"],
            },
        },
    },
    # -------------------------------------------------------------------------
    # H. Anamnesis por voz (NEW)
    # -------------------------------------------------------------------------
    {
        "type": "function",
        "name": "guardar_anamnesis",
        "description": "Guarda datos de anamnesis (ficha médica) del paciente. Usá esta tool cuando el paciente te cuente sus enfermedades, alergias, medicación, cirugías previas, miedos, etc. Podés llamarla múltiples veces para ir completando secciones.",
        "parameters": {
            "type": "object",
            "properties": {
                "patient_id": {"type": "integer", "description": "ID del paciente"},
                "base_diseases": {"type": "string", "description": "Enfermedades de base (diabetes, hipertensión, etc.)"},
                "habitual_medication": {"type": "string", "description": "Medicación habitual"},
                "allergies": {"type": "string", "description": "Alergias (penicilina, anestesia, etc.)"},
                "previous_surgeries": {"type": "string", "description": "Cirugías previas"},
                "is_smoker": {"type": "string", "description": "Si fuma: 'si' o 'no'"},
                "smoker_amount": {"type": "string", "description": "Cantidad de cigarrillos por día"},
                "pregnancy_lactation": {"type": "string", "description": "'embarazo', 'lactancia', 'no_aplica'"},
                "negative_experiences": {"type": "string", "description": "Experiencias negativas previas en dentista"},
                "specific_fears": {"type": "string", "description": "Miedos específicos (agujas, dolor, etc.)"},
            },
            "required": ["patient_id"],
        },
    },
    {
        "type": "function",
        "name": "ver_anamnesis",
        "description": "Lee la ficha médica (anamnesis) completa de un paciente para verificar qué datos ya están cargados y cuáles faltan.",
        "parameters": {
            "type": "object",
            "properties": {
                "patient_id": {"type": "integer", "description": "ID del paciente"},
            },
            "required": ["patient_id"],
        },
    },
    # -------------------------------------------------------------------------
    # I. Consultas de datos avanzadas (NEW)
    # -------------------------------------------------------------------------
    {
        "type": "function",
        "name": "consultar_datos",
        "description": "Consulta cualquier dato de la plataforma: pacientes, turnos, pagos, leads, métricas, tratamientos, profesionales. Describe qué necesitás y te devuelvo los datos.",
        "parameters": {
            "type": "object",
            "properties": {
                "consulta": {"type": "string", "description": "Qué datos necesitás. Ej: 'cuántos turnos hay esta semana', 'pacientes sin turno en 3 meses', 'ingresos del mes', 'leads de Meta sin contactar', 'tasa de no-show por profesional'"},
            },
            "required": ["consulta"],
        },
    },
    {
        "type": "function",
        "name": "resumen_marketing",
        "description": "Obtiene resumen de marketing: inversión en Meta Ads, leads generados, costo por lead, pacientes convertidos, ROI. Usa datos de Meta Graph API si está conectado.",
        "parameters": {
            "type": "object",
            "properties": {
                "periodo": {"type": "string", "enum": ["hoy", "semana", "mes", "trimestre", "año"], "description": "Período del reporte"},
            },
            "required": ["periodo"],
        },
    },
    {
        "type": "function",
        "name": "resumen_financiero",
        "description": "Resumen financiero: ingresos por tratamiento, pagos pendientes, seña cobradas, facturación por profesional. Solo CEO.",
        "parameters": {
            "type": "object",
            "properties": {
                "periodo": {"type": "string", "enum": ["hoy", "semana", "mes", "trimestre", "año"], "description": "Período del reporte"},
            },
            "required": ["periodo"],
        },
    },
]


# =============================================================================
# HELPERS
# =============================================================================

def _role_error(tool_name: str, allowed: List[str]) -> str:
    roles_str = ", ".join(allowed)
    return f"No tenes permiso para usar '{tool_name}'. Solo disponible para: {roles_str}."


def _fmt_date(d: Any) -> str:
    """Format a date/datetime for speech output (dd/mm/yyyy)."""
    if d is None:
        return "sin fecha"
    if isinstance(d, datetime):
        return d.strftime("%d/%m/%Y %H:%M")
    if isinstance(d, date):
        return d.strftime("%d/%m/%Y")
    return str(d)


def _fmt_money(amount: Any) -> str:
    if amount is None:
        return "$0"
    return f"${float(amount):,.2f}"


def _today() -> date:
    return date.today()


async def _get_allowed_tenant_ids() -> List[int]:
    """Return all tenant IDs (for CEO cross-sede queries)."""
    rows = await db.pool.fetch("SELECT id FROM tenants ORDER BY id ASC")
    return [int(r["id"]) for r in rows] if rows else [1]


async def _resolve_professional_id(user_id: str, tenant_id: int) -> Optional[int]:
    """Resolve user_id (UUID) to professional_id."""
    try:
        row = await db.pool.fetchval(
            "SELECT id FROM professionals WHERE user_id = $1 AND tenant_id = $2 AND is_active = true",
            uuid.UUID(user_id),
            tenant_id,
        )
        return int(row) if row is not None else None
    except (ValueError, TypeError):
        return None


# =============================================================================
# TOOL IMPLEMENTATIONS
# =============================================================================

# --- A. Pacientes ---

async def _buscar_paciente(args: Dict, tenant_id: int) -> str:
    q = args.get("query", "").strip()
    if not q:
        return "Necesito un nombre, apellido, DNI o telefono para buscar."

    like_q = f"%{q}%"
    rows = await db.pool.fetch(
        """
        SELECT id, first_name, last_name, phone_number, dni,
               insurance_provider, insurance_id, status
        FROM patients
        WHERE tenant_id = $1
          AND (
            first_name ILIKE $2 OR last_name ILIKE $2
            OR dni ILIKE $2 OR phone_number ILIKE $2
          )
        ORDER BY last_name, first_name
        LIMIT 5
        """,
        tenant_id, like_q,
    )

    if not rows:
        return f"No encontre ningun paciente con '{q}'."

    lines = [f"Encontre {len(rows)} paciente(s):"]
    for r in rows:
        name = f"{r['first_name'] or ''} {r['last_name'] or ''}".strip()
        ins = f" — OS: {r['insurance_provider']}" if r["insurance_provider"] else ""
        lines.append(f"• ID {r['id']}: {name} | Tel: {r['phone_number'] or 'sin tel'} | DNI: {r['dni'] or 'sin DNI'}{ins}")
    return "\n".join(lines)


async def _ver_paciente(args: Dict, tenant_id: int) -> str:
    pid = args.get("patient_id")
    if not pid:
        return "Necesito el ID del paciente."

    row = await db.pool.fetchrow(
        """
        SELECT id, first_name, last_name, phone_number, dni, email,
               insurance_provider, insurance_id, insurance_valid_until,
               birth_date, gender, notes, preferred_schedule, status,
               medical_history, created_at, last_visit
        FROM patients
        WHERE id = $1 AND tenant_id = $2
        """,
        int(pid), tenant_id,
    )
    if not row:
        return "No encontre a ese paciente."

    name = f"{row['first_name'] or ''} {row['last_name'] or ''}".strip()
    parts = [f"Paciente: {name} (ID {row['id']})"]
    parts.append(f"Tel: {row['phone_number'] or 'sin tel'} | DNI: {row['dni'] or 'sin DNI'}")
    if row["email"]:
        parts.append(f"Email: {row['email']}")
    if row["insurance_provider"]:
        valid = f" (valida hasta {_fmt_date(row['insurance_valid_until'])})" if row["insurance_valid_until"] else ""
        parts.append(f"Obra social: {row['insurance_provider']} — Afiliado: {row['insurance_id'] or 'sin numero'}{valid}")
    if row["birth_date"]:
        parts.append(f"Nacimiento: {_fmt_date(row['birth_date'])}")
    if row["notes"]:
        parts.append(f"Notas: {row['notes']}")
    parts.append(f"Estado: {row['status']} | Ultima visita: {_fmt_date(row['last_visit'])}")

    # Next appointments
    appts = await db.pool.fetch(
        """
        SELECT id, appointment_datetime, appointment_type, status,
               professional_id
        FROM appointments
        WHERE patient_id = $1 AND tenant_id = $2
          AND appointment_datetime >= NOW()
          AND status IN ('scheduled', 'confirmed')
        ORDER BY appointment_datetime ASC
        LIMIT 3
        """,
        int(pid), tenant_id,
    )
    if appts:
        parts.append("Proximos turnos:")
        for a in appts:
            parts.append(f"  • {_fmt_date(a['appointment_datetime'])} — {a['appointment_type']} ({a['status']})")
    else:
        parts.append("Sin turnos proximos.")

    return "\n".join(parts)


async def _registrar_paciente(args: Dict, tenant_id: int) -> str:
    first_name = args.get("first_name", "").strip()
    last_name = args.get("last_name", "").strip()
    phone = args.get("phone_number", "").strip()

    if not first_name or not last_name or not phone:
        return "Necesito nombre, apellido y telefono para registrar un paciente."

    # Check duplicate
    existing = await db.pool.fetchval(
        "SELECT id FROM patients WHERE tenant_id = $1 AND phone_number = $2",
        tenant_id, phone,
    )
    if existing:
        return f"Ya existe un paciente con ese telefono (ID {existing})."

    row = await db.pool.fetchrow(
        """
        INSERT INTO patients (tenant_id, first_name, last_name, phone_number, dni,
                              insurance_provider, insurance_id)
        VALUES ($1, $2, $3, $4, $5, $6, $7)
        RETURNING id
        """,
        tenant_id,
        first_name,
        last_name,
        phone,
        args.get("dni"),
        args.get("insurance_provider"),
        args.get("insurance_id"),
    )
    return f"Paciente {first_name} {last_name} registrado con ID {row['id']}."


async def _actualizar_paciente(args: Dict, tenant_id: int) -> str:
    pid = args.get("patient_id")
    field = args.get("field")
    value = args.get("value")

    if not pid or not field or value is None:
        return "Necesito patient_id, field y value."

    allowed_fields = {
        "phone_number", "email", "insurance_provider",
        "insurance_id", "notes", "preferred_schedule",
    }
    if field not in allowed_fields:
        return f"Campo '{field}' no permitido. Campos validos: {', '.join(sorted(allowed_fields))}."

    result = await db.pool.execute(
        f"UPDATE patients SET {field} = $1, updated_at = NOW() WHERE id = $2 AND tenant_id = $3",
        value, int(pid), tenant_id,
    )
    if result == "UPDATE 0":
        return "No encontre a ese paciente."
    return f"Paciente {pid}: campo '{field}' actualizado."


async def _historial_clinico(args: Dict, tenant_id: int, user_role: str) -> str:
    if user_role not in ("ceo", "professional"):
        return _role_error("historial_clinico", ["ceo", "professional"])

    pid = args.get("patient_id")
    if not pid:
        return "Necesito el ID del paciente."

    rows = await db.pool.fetch(
        """
        SELECT cr.id, cr.record_date, cr.diagnosis, cr.clinical_notes,
               cr.odontogram_data, cr.treatments, cr.recommendations,
               p.first_name || ' ' || p.last_name AS professional_name
        FROM clinical_records cr
        LEFT JOIN professionals p ON p.id = cr.professional_id
        WHERE cr.patient_id = $1 AND cr.tenant_id = $2
        ORDER BY cr.record_date DESC
        LIMIT 10
        """,
        int(pid), tenant_id,
    )

    if not rows:
        return "Este paciente no tiene registros clinicos."

    lines = [f"Historial clinico ({len(rows)} registros mas recientes):"]
    for r in rows:
        dt = _fmt_date(r["record_date"])
        diag = r["diagnosis"] or "sin diagnostico"
        prof = r["professional_name"] or "sin profesional"
        lines.append(f"• {dt} — {diag} (Dr. {prof})")
        if r["clinical_notes"]:
            lines.append(f"  Notas: {r['clinical_notes'][:120]}")
        # Odontogram summary
        odata = r["odontogram_data"]
        if odata and isinstance(odata, dict) and len(odata) > 0:
            lines.append(f"  Odontograma: {len(odata)} pieza(s) registrada(s)")
    return "\n".join(lines)


async def _registrar_nota_clinica(args: Dict, tenant_id: int, user_role: str, user_id: str) -> str:
    if user_role != "professional":
        return _role_error("registrar_nota_clinica", ["professional"])

    pid = args.get("patient_id")
    diagnosis = args.get("diagnosis", "").strip()
    if not pid or not diagnosis:
        return "Necesito patient_id y diagnosis."

    # Verify patient exists
    exists = await db.pool.fetchval(
        "SELECT id FROM patients WHERE id = $1 AND tenant_id = $2",
        int(pid), tenant_id,
    )
    if not exists:
        return "No encontre a ese paciente."

    prof_id = await _resolve_professional_id(user_id, tenant_id)

    # Build odontogram entry if tooth data provided
    odontogram_data = {}
    tooth_number = args.get("tooth_number")
    tooth_status = args.get("tooth_status")
    surface = args.get("surface")
    if tooth_number:
        entry = {}
        if tooth_status:
            entry["status"] = tooth_status
        if surface:
            entry["surface"] = surface
        entry["date"] = str(_today())
        odontogram_data[str(tooth_number)] = entry

    record_id = uuid.uuid4()
    await db.pool.execute(
        """
        INSERT INTO clinical_records
            (id, tenant_id, patient_id, professional_id, record_date,
             diagnosis, clinical_notes, odontogram_data)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
        """,
        record_id,
        tenant_id,
        int(pid),
        prof_id,
        _today(),
        diagnosis,
        args.get("treatment_notes"),
        json.dumps(odontogram_data),
    )

    tooth_msg = ""
    if tooth_number:
        tooth_msg = f" Pieza {tooth_number}: {tooth_status or 'registrada'}."
    return f"Nota clinica registrada para paciente {pid}.{tooth_msg}"


# --- B. Turnos ---

async def _ver_agenda(args: Dict, tenant_id: int, user_role: str, user_id: str) -> str:
    target_date = args.get("date", str(_today()))
    prof_id = args.get("professional_id")

    # Default to current professional if role is professional
    if not prof_id and user_role == "professional":
        prof_id = await _resolve_professional_id(user_id, tenant_id)

    query = """
        SELECT a.id, a.appointment_datetime, a.appointment_type, a.status,
               a.notes, a.duration_minutes,
               p.first_name || ' ' || COALESCE(p.last_name, '') AS patient_name,
               pr.first_name || ' ' || pr.last_name AS professional_name
        FROM appointments a
        JOIN patients p ON p.id = a.patient_id
        LEFT JOIN professionals pr ON pr.id = a.professional_id
        WHERE a.tenant_id = $1
          AND a.appointment_datetime::date = $2::date
    """
    params: list = [tenant_id, target_date]

    if prof_id:
        query += " AND a.professional_id = $3"
        params.append(int(prof_id))

    query += " ORDER BY a.appointment_datetime ASC"

    rows = await db.pool.fetch(query, *params)

    if not rows:
        return f"No hay turnos para el {target_date}."

    lines = [f"Agenda del {target_date} ({len(rows)} turnos):"]
    for r in rows:
        time_str = r["appointment_datetime"].strftime("%H:%M") if r["appointment_datetime"] else "?"
        dur = f"{r['duration_minutes']}min" if r["duration_minutes"] else ""
        status_icon = {"scheduled": "⏳", "confirmed": "✅", "completed": "✔", "cancelled": "❌"}.get(r["status"], "•")
        prof = f" — Dr. {r['professional_name']}" if r["professional_name"] and not prof_id else ""
        lines.append(f"{status_icon} {time_str} ({dur}) {r['patient_name']} — {r['appointment_type']} [{r['status']}]{prof}")
    return "\n".join(lines)


async def _proximo_paciente(tenant_id: int, user_role: str, user_id: str) -> str:
    prof_id = await _resolve_professional_id(user_id, tenant_id)
    if not prof_id:
        return "No tenes un perfil de profesional vinculado."

    row = await db.pool.fetchrow(
        """
        SELECT a.id, a.appointment_datetime, a.appointment_type, a.notes,
               a.duration_minutes, a.status,
               p.first_name || ' ' || COALESCE(p.last_name, '') AS patient_name,
               p.phone_number, p.insurance_provider, p.notes AS patient_notes
        FROM appointments a
        JOIN patients p ON p.id = a.patient_id
        WHERE a.professional_id = $1
          AND a.tenant_id = $2
          AND a.appointment_datetime::date = $3
          AND a.status IN ('scheduled', 'confirmed')
          AND a.appointment_datetime > NOW()
        ORDER BY a.appointment_datetime ASC
        LIMIT 1
        """,
        prof_id, tenant_id, _today(),
    )

    if not row:
        return "No tenes mas turnos para hoy."

    time_str = row["appointment_datetime"].strftime("%H:%M")
    ins = f" | OS: {row['insurance_provider']}" if row["insurance_provider"] else ""
    notes = f"\nNotas: {row['notes']}" if row["notes"] else ""
    return (
        f"Tu proximo paciente es {row['patient_name']} a las {time_str}.\n"
        f"Tratamiento: {row['appointment_type']} ({row['duration_minutes'] or 60}min) [{row['status']}]{ins}{notes}"
    )


async def _verificar_disponibilidad(args: Dict, tenant_id: int) -> str:
    target_date = args.get("date")
    if not target_date:
        return "Necesito una fecha para verificar disponibilidad."

    treatment_type = args.get("treatment_type")
    prof_id = args.get("professional_id")

    # Get working hours from tenant
    tenant = await db.pool.fetchrow(
        "SELECT working_hours, clinic_name FROM tenants WHERE id = $1", tenant_id
    )
    if not tenant:
        return "No se encontro la clinica."

    working_hours = tenant["working_hours"]
    if isinstance(working_hours, str):
        working_hours = json.loads(working_hours)

    # Parse target date to get day of week
    try:
        dt = datetime.strptime(target_date, "%Y-%m-%d").date()
    except ValueError:
        return "Formato de fecha invalido. Usa YYYY-MM-DD."

    day_names = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
    day_key = day_names[dt.weekday()]

    day_config = working_hours.get(day_key, {}) if working_hours else {}
    if not day_config or not day_config.get("enabled", False):
        return f"La clinica esta cerrada el {_fmt_date(dt)}."

    start_hour = day_config.get("start", "09:00")
    end_hour = day_config.get("end", "18:00")

    # Get duration for treatment
    duration = 30  # default
    if treatment_type:
        tt_row = await db.pool.fetchval(
            "SELECT default_duration_minutes FROM treatment_types WHERE tenant_id = $1 AND code = $2 AND is_active = true",
            tenant_id, treatment_type,
        )
        if tt_row:
            duration = int(tt_row)

    # Get existing appointments for that date
    query = """
        SELECT appointment_datetime, duration_minutes
        FROM appointments
        WHERE tenant_id = $1
          AND appointment_datetime::date = $2::date
          AND status IN ('scheduled', 'confirmed')
    """
    params: list = [tenant_id, target_date]
    if prof_id:
        query += " AND professional_id = $3"
        params.append(int(prof_id))

    query += " ORDER BY appointment_datetime ASC"
    existing = await db.pool.fetch(query, *params)

    # Build occupied intervals
    occupied = []
    for appt in existing:
        appt_start = appt["appointment_datetime"]
        appt_dur = appt["duration_minutes"] or 30
        appt_end = appt_start + timedelta(minutes=appt_dur)
        occupied.append((appt_start, appt_end))

    # Find free slots
    try:
        sh, sm = map(int, start_hour.split(":"))
        eh, em = map(int, end_hour.split(":"))
    except (ValueError, AttributeError):
        sh, sm, eh, em = 9, 0, 18, 0

    slot_start = datetime(dt.year, dt.month, dt.day, sh, sm)
    day_end = datetime(dt.year, dt.month, dt.day, eh, em)

    free_slots = []
    while slot_start + timedelta(minutes=duration) <= day_end and len(free_slots) < 5:
        slot_end = slot_start + timedelta(minutes=duration)
        conflict = False
        for occ_start, occ_end in occupied:
            occ_start_naive = occ_start.replace(tzinfo=None) if occ_start.tzinfo else occ_start
            occ_end_naive = occ_end.replace(tzinfo=None) if occ_end.tzinfo else occ_end
            if slot_start < occ_end_naive and slot_end > occ_start_naive:
                conflict = True
                break
        if not conflict:
            free_slots.append(slot_start.strftime("%H:%M"))
        slot_start += timedelta(minutes=30)  # check every 30min

    location = day_config.get("location", "")
    loc_msg = f" Sede: {location}." if location else ""

    if not free_slots:
        return f"No hay disponibilidad para el {_fmt_date(dt)}.{loc_msg}"

    slots_str = ", ".join(free_slots[:5])
    tt_msg = f" para {treatment_type}" if treatment_type else ""
    return f"Horarios disponibles el {_fmt_date(dt)}{tt_msg}: {slots_str}.{loc_msg}"


async def _agendar_turno(args: Dict, tenant_id: int) -> str:
    pid = args.get("patient_id")
    target_date = args.get("date")
    time_str = args.get("time")
    treatment_type = args.get("treatment_type")

    if not all([pid, target_date, time_str, treatment_type]):
        return "Necesito patient_id, date, time y treatment_type."

    # Verify patient
    patient = await db.pool.fetchrow(
        "SELECT first_name, last_name FROM patients WHERE id = $1 AND tenant_id = $2",
        int(pid), tenant_id,
    )
    if not patient:
        return "No encontre a ese paciente."

    # Get treatment duration
    tt_row = await db.pool.fetchrow(
        "SELECT default_duration_minutes, name FROM treatment_types WHERE tenant_id = $1 AND code = $2 AND is_active = true",
        tenant_id, treatment_type,
    )
    duration = int(tt_row["default_duration_minutes"]) if tt_row else 30
    tt_name = tt_row["name"] if tt_row else treatment_type

    # Resolve professional
    prof_id = args.get("professional_id")
    if prof_id:
        prof_id = int(prof_id)

    # Build datetime
    try:
        appt_dt = datetime.strptime(f"{target_date} {time_str}", "%Y-%m-%d %H:%M")
    except ValueError:
        return "Formato de fecha/hora invalido. Usa YYYY-MM-DD y HH:MM."

    appt_id = uuid.uuid4()
    await db.pool.execute(
        """
        INSERT INTO appointments
            (id, tenant_id, patient_id, appointment_datetime, duration_minutes,
             appointment_type, professional_id, notes, status, source)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, 'scheduled', 'nova')
        """,
        appt_id,
        tenant_id,
        int(pid),
        appt_dt,
        duration,
        treatment_type,
        prof_id,
        args.get("notes"),
    )

    patient_name = f"{patient['first_name']} {patient['last_name'] or ''}".strip()
    prof_msg = ""
    if prof_id:
        prof_name = await db.pool.fetchval(
            "SELECT first_name || ' ' || last_name FROM professionals WHERE id = $1",
            prof_id,
        )
        if prof_name:
            prof_msg = f" con Dr. {prof_name}"

    return (
        f"Turno agendado: {patient_name} el {_fmt_date(appt_dt.date())} a las {time_str}"
        f" — {tt_name} ({duration}min){prof_msg}."
    )


async def _cancelar_turno(args: Dict, tenant_id: int) -> str:
    appt_id = args.get("appointment_id")
    if not appt_id:
        return "Necesito el ID del turno."

    try:
        appt_uuid = uuid.UUID(appt_id)
    except ValueError:
        return "ID de turno invalido."

    row = await db.pool.fetchrow(
        """
        SELECT a.id, a.appointment_datetime, a.appointment_type, a.status,
               p.first_name || ' ' || COALESCE(p.last_name, '') AS patient_name
        FROM appointments a
        JOIN patients p ON p.id = a.patient_id
        WHERE a.id = $1 AND a.tenant_id = $2
        """,
        appt_uuid, tenant_id,
    )
    if not row:
        return "No encontre ese turno."
    if row["status"] == "cancelled":
        return "Ese turno ya esta cancelado."

    reason = args.get("reason", "Cancelado via Nova")
    await db.pool.execute(
        """
        UPDATE appointments
        SET status = 'cancelled', cancellation_reason = $1, cancellation_by = 'nova',
            updated_at = NOW()
        WHERE id = $2 AND tenant_id = $3
        """,
        reason, appt_uuid, tenant_id,
    )

    return f"Turno cancelado: {row['patient_name']} — {row['appointment_type']} del {_fmt_date(row['appointment_datetime'])}."


async def _confirmar_turnos(args: Dict, tenant_id: int) -> str:
    ids = args.get("appointment_ids") or []

    if ids:
        # Confirm specific appointments
        uuids = []
        for aid in ids:
            try:
                uuids.append(uuid.UUID(aid))
            except ValueError:
                pass
        if not uuids:
            return "IDs de turno invalidos."

        result = await db.pool.execute(
            """
            UPDATE appointments
            SET status = 'confirmed', updated_at = NOW()
            WHERE tenant_id = $1
              AND id = ANY($2::uuid[])
              AND status = 'scheduled'
            """,
            tenant_id, uuids,
        )
        count = int(result.split()[-1]) if result else 0
        return f"{count} turno(s) confirmado(s)."
    else:
        # Confirm all pending today
        result = await db.pool.execute(
            """
            UPDATE appointments
            SET status = 'confirmed', updated_at = NOW()
            WHERE tenant_id = $1
              AND appointment_datetime::date = $2
              AND status = 'scheduled'
            """,
            tenant_id, _today(),
        )
        count = int(result.split()[-1]) if result else 0
        if count == 0:
            return "No hay turnos pendientes de confirmar hoy."
        return f"Se confirmaron {count} turno(s) de hoy."


# --- C. Tratamientos y Facturacion ---

async def _listar_tratamientos(args: Dict, tenant_id: int) -> str:
    category = args.get("category")

    query = """
        SELECT code, name, category, default_duration_minutes, base_price, is_active
        FROM treatment_types
        WHERE tenant_id = $1 AND is_active = true
    """
    params: list = [tenant_id]

    if category:
        query += " AND category = $2"
        params.append(category)

    query += " ORDER BY category, name"
    rows = await db.pool.fetch(query, *params)

    if not rows:
        cat_msg = f" en la categoria '{category}'" if category else ""
        return f"No hay tratamientos configurados{cat_msg}."

    lines = [f"Tratamientos disponibles ({len(rows)}):"]
    current_cat = None
    for r in rows:
        cat = r["category"] or "General"
        if cat != current_cat:
            current_cat = cat
            lines.append(f"\n[{cat.upper()}]")
        price = _fmt_money(r["base_price"]) if r["base_price"] else "sin precio"
        lines.append(f"• {r['name']} ({r['code']}) — {r['default_duration_minutes']}min — {price}")
    return "\n".join(lines)


async def _registrar_pago(args: Dict, tenant_id: int, user_role: str) -> str:
    if user_role not in ("ceo", "secretary"):
        return _role_error("registrar_pago", ["ceo", "secretary"])

    appt_id = args.get("appointment_id")
    amount = args.get("amount")
    method = args.get("method")

    if not appt_id or amount is None or not method:
        return "Necesito appointment_id, amount y method."

    try:
        appt_uuid = uuid.UUID(appt_id)
    except ValueError:
        return "ID de turno invalido."

    # Verify appointment exists
    appt = await db.pool.fetchrow(
        """
        SELECT a.id, a.appointment_type,
               p.first_name || ' ' || COALESCE(p.last_name, '') AS patient_name
        FROM appointments a
        JOIN patients p ON p.id = a.patient_id
        WHERE a.id = $1 AND a.tenant_id = $2
        """,
        appt_uuid, tenant_id,
    )
    if not appt:
        return "No encontre ese turno."

    # Update appointment billing
    await db.pool.execute(
        """
        UPDATE appointments
        SET billing_amount = $1, payment_status = 'paid',
            billing_notes = $2, updated_at = NOW()
        WHERE id = $3 AND tenant_id = $4
        """,
        Decimal(str(amount)),
        args.get("notes"),
        appt_uuid,
        tenant_id,
    )

    # Also create accounting transaction
    await db.pool.execute(
        """
        INSERT INTO accounting_transactions
            (id, tenant_id, patient_id, appointment_id, transaction_type,
             amount, payment_method, description, status)
        SELECT $1, $2, a.patient_id, $3, 'payment', $4, $5, $6, 'completed'
        FROM appointments a WHERE a.id = $3
        """,
        uuid.uuid4(),
        tenant_id,
        appt_uuid,
        Decimal(str(amount)),
        method,
        f"Pago registrado via Nova — {appt['appointment_type']}",
    )

    method_labels = {"cash": "efectivo", "card": "tarjeta", "transfer": "transferencia", "insurance": "obra social"}
    return f"Pago de {_fmt_money(amount)} registrado para {appt['patient_name']} ({method_labels.get(method, method)})."


async def _facturacion_pendiente(tenant_id: int) -> str:
    rows = await db.pool.fetch(
        """
        SELECT a.id, a.appointment_datetime, a.appointment_type,
               p.first_name || ' ' || COALESCE(p.last_name, '') AS patient_name,
               tt.base_price
        FROM appointments a
        JOIN patients p ON p.id = a.patient_id
        LEFT JOIN treatment_types tt ON tt.code = a.appointment_type AND tt.tenant_id = a.tenant_id
        WHERE a.tenant_id = $1
          AND a.status = 'completed'
          AND (a.payment_status = 'pending' OR a.payment_status IS NULL)
        ORDER BY a.appointment_datetime DESC
        LIMIT 20
        """,
        tenant_id,
    )

    if not rows:
        return "No hay facturacion pendiente. Todo al dia."

    lines = [f"Facturacion pendiente ({len(rows)} turnos):"]
    for r in rows:
        dt = _fmt_date(r["appointment_datetime"])
        price = _fmt_money(r["base_price"]) if r["base_price"] else "sin precio"
        lines.append(f"• {r['patient_name']} — {r['appointment_type']} ({dt}) — {price}")
    return "\n".join(lines)


# --- D. Analytics y Configuracion ---

async def _resumen_semana(tenant_id: int, user_role: str) -> str:
    if user_role != "ceo":
        return _role_error("resumen_semana", ["ceo"])

    week_start = _today() - timedelta(days=_today().weekday())
    week_end = week_start + timedelta(days=6)

    stats = await db.pool.fetchrow(
        """
        SELECT
            COUNT(*) FILTER (WHERE status != 'cancelled') AS total_turnos,
            COUNT(*) FILTER (WHERE status = 'completed') AS completados,
            COUNT(*) FILTER (WHERE status = 'cancelled') AS cancelados,
            COUNT(*) FILTER (WHERE status = 'scheduled') AS pendientes,
            COALESCE(SUM(billing_amount) FILTER (WHERE payment_status = 'paid'), 0) AS facturado
        FROM appointments
        WHERE tenant_id = $1
          AND appointment_datetime::date BETWEEN $2 AND $3
        """,
        tenant_id, week_start, week_end,
    )

    new_patients = await db.pool.fetchval(
        """
        SELECT COUNT(*) FROM patients
        WHERE tenant_id = $1 AND created_at::date BETWEEN $2 AND $3
        """,
        tenant_id, week_start, week_end,
    )

    total = stats["total_turnos"] or 0
    completed = stats["completados"] or 0
    cancelled = stats["cancelados"] or 0
    pending = stats["pendientes"] or 0
    revenue = stats["facturado"] or 0
    cancel_rate = f"{(cancelled / (total + cancelled) * 100):.1f}%" if (total + cancelled) > 0 else "0%"

    return (
        f"Resumen semanal ({_fmt_date(week_start)} al {_fmt_date(week_end)}):\n"
        f"• Turnos: {total} ({completed} completados, {pending} pendientes)\n"
        f"• Cancelaciones: {cancelled} (tasa: {cancel_rate})\n"
        f"• Pacientes nuevos: {new_patients}\n"
        f"• Facturado: {_fmt_money(revenue)}"
    )


async def _rendimiento_profesional(args: Dict, tenant_id: int, user_role: str) -> str:
    if user_role != "ceo":
        return _role_error("rendimiento_profesional", ["ceo"])

    prof_id = args.get("professional_id")
    if not prof_id:
        return "Necesito el ID del profesional."

    period = args.get("period", "month")
    days_map = {"week": 7, "month": 30, "quarter": 90}
    days = days_map.get(period, 30)
    since = _today() - timedelta(days=days)

    prof = await db.pool.fetchrow(
        "SELECT first_name, last_name, specialty FROM professionals WHERE id = $1 AND tenant_id = $2",
        int(prof_id), tenant_id,
    )
    if not prof:
        return "No encontre a ese profesional."

    stats = await db.pool.fetchrow(
        """
        SELECT
            COUNT(*) AS total,
            COUNT(*) FILTER (WHERE status = 'completed') AS completados,
            COUNT(*) FILTER (WHERE status = 'cancelled') AS cancelados,
            COUNT(DISTINCT patient_id) AS pacientes_unicos,
            COALESCE(SUM(billing_amount) FILTER (WHERE payment_status = 'paid'), 0) AS facturado
        FROM appointments
        WHERE professional_id = $1 AND tenant_id = $2
          AND appointment_datetime::date >= $3
        """,
        int(prof_id), tenant_id, since,
    )

    total = stats["total"] or 0
    completed = stats["completados"] or 0
    cancelled = stats["cancelados"] or 0
    unique_patients = stats["pacientes_unicos"] or 0
    revenue = stats["facturado"] or 0
    cancel_rate = f"{(cancelled / total * 100):.1f}%" if total > 0 else "0%"

    period_labels = {"week": "la semana", "month": "el mes", "quarter": "el trimestre"}
    prof_name = f"Dr. {prof['first_name']} {prof['last_name']}"

    return (
        f"Rendimiento de {prof_name} ({prof['specialty'] or 'sin especialidad'}) en {period_labels.get(period, period)}:\n"
        f"• Turnos: {total} ({completed} completados)\n"
        f"• Cancelaciones: {cancelled} (tasa: {cancel_rate})\n"
        f"• Pacientes unicos: {unique_patients}\n"
        f"• Facturado: {_fmt_money(revenue)}"
    )


async def _actualizar_faq(args: Dict, tenant_id: int) -> str:
    question = args.get("question", "").strip()
    answer = args.get("answer", "").strip()

    if not question or not answer:
        return "Necesito la pregunta y la respuesta."

    # Try to update existing FAQ with similar question
    existing = await db.pool.fetchval(
        "SELECT id FROM clinic_faqs WHERE tenant_id = $1 AND question ILIKE $2",
        tenant_id, f"%{question}%",
    )

    if existing:
        await db.pool.execute(
            "UPDATE clinic_faqs SET answer = $1, updated_at = NOW() WHERE id = $2 AND tenant_id = $3",
            answer, existing, tenant_id,
        )
        return f"FAQ actualizada: '{question[:60]}...'"
    else:
        await db.pool.execute(
            "INSERT INTO clinic_faqs (tenant_id, question, answer) VALUES ($1, $2, $3)",
            tenant_id, question, answer,
        )
        return f"FAQ creada: '{question[:60]}...'"


# --- E. Navegacion ---

async def _ir_a_pagina(args: Dict) -> str:
    page = args.get("page")
    if not page:
        return "Necesito saber a que pagina queres ir."

    page_labels = {
        "agenda": "Agenda",
        "pacientes": "Pacientes",
        "chats": "Chats",
        "tratamientos": "Tratamientos",
        "analytics": "Analytics",
        "configuracion": "Configuracion",
        "marketing": "Marketing",
        "leads": "Leads",
    }
    label = page_labels.get(page, page)
    return json.dumps({
        "type": "navigation",
        "action": "navigate",
        "page": page,
        "message": f"Abriendo {label}.",
    })


async def _ir_a_paciente(args: Dict, tenant_id: int) -> str:
    pid = args.get("patient_id")
    if not pid:
        return "Necesito el ID del paciente."

    # Verify patient exists
    name = await db.pool.fetchval(
        "SELECT first_name || ' ' || COALESCE(last_name, '') FROM patients WHERE id = $1 AND tenant_id = $2",
        int(pid), tenant_id,
    )
    if not name:
        return "No encontre a ese paciente."

    return json.dumps({
        "type": "navigation",
        "action": "open_patient",
        "patient_id": int(pid),
        "message": f"Abriendo ficha de {name.strip()}.",
    })


# --- F. Multi-sede CEO ---

async def _resumen_sedes(user_role: str) -> str:
    if user_role != "ceo":
        return _role_error("resumen_sedes", ["ceo"])

    tenant_ids = await _get_allowed_tenant_ids()

    lines = ["Resumen de todas las sedes:"]
    for tid in tenant_ids:
        tenant = await db.pool.fetchrow(
            "SELECT clinic_name FROM tenants WHERE id = $1", tid
        )
        if not tenant:
            continue

        stats = await db.pool.fetchrow(
            """
            SELECT
                COUNT(*) FILTER (WHERE appointment_datetime::date = CURRENT_DATE AND status != 'cancelled') AS turnos_hoy,
                COUNT(*) FILTER (WHERE appointment_datetime::date = CURRENT_DATE AND status = 'scheduled') AS sin_confirmar,
                COUNT(*) FILTER (WHERE status = 'completed' AND (payment_status = 'pending' OR payment_status IS NULL)) AS pago_pendiente
            FROM appointments WHERE tenant_id = $1
            """,
            tid,
        )

        patients_count = await db.pool.fetchval(
            "SELECT COUNT(*) FROM patients WHERE tenant_id = $1", tid
        )

        week_revenue = await db.pool.fetchval(
            """
            SELECT COALESCE(SUM(billing_amount), 0)
            FROM appointments
            WHERE tenant_id = $1
              AND payment_status = 'paid'
              AND appointment_datetime::date >= CURRENT_DATE - 7
            """,
            tid,
        )

        name = tenant["clinic_name"]
        turnos = stats["turnos_hoy"] or 0
        sin_conf = stats["sin_confirmar"] or 0
        pend_pago = stats["pago_pendiente"] or 0

        lines.append(
            f"\n📍 {name} (ID {tid}):\n"
            f"  Turnos hoy: {turnos} ({sin_conf} sin confirmar)\n"
            f"  Pacientes: {patients_count}\n"
            f"  Facturado (7d): {_fmt_money(week_revenue)}\n"
            f"  Pagos pendientes: {pend_pago}"
        )

    return "\n".join(lines)


async def _comparar_sedes(args: Dict, user_role: str) -> str:
    if user_role != "ceo":
        return _role_error("comparar_sedes", ["ceo"])

    metric = args.get("metric")
    period = args.get("period", "semana")

    if not metric:
        return "Necesito saber que metrica comparar."

    period_days = {"hoy": 0, "semana": 7, "mes": 30}
    days = period_days.get(period, 7)

    if days == 0:
        date_filter = "appointment_datetime::date = CURRENT_DATE"
        date_filter_created = "created_at::date = CURRENT_DATE"
    else:
        date_filter = "appointment_datetime::date >= CURRENT_DATE - make_interval(days => $2)"
        date_filter_created = "created_at::date >= CURRENT_DATE - make_interval(days => $2)"

    tenant_ids = await _get_allowed_tenant_ids()

    metric_queries = {
        "cancelaciones": f"""
            SELECT COUNT(*) FILTER (WHERE status = 'cancelled') AS valor,
                   COUNT(*) AS total
            FROM appointments WHERE tenant_id = $1 AND {date_filter}
        """,
        "nuevos_pacientes": f"""
            SELECT COUNT(*) AS valor, 0 AS total
            FROM patients WHERE tenant_id = $1
              AND {date_filter_created}
        """,
        "facturacion": f"""
            SELECT COALESCE(SUM(billing_amount), 0) AS valor, COUNT(*) AS total
            FROM appointments WHERE tenant_id = $1
              AND payment_status = 'paid' AND {date_filter}
        """,
        "ocupacion": f"""
            SELECT COUNT(*) AS valor, 0 AS total
            FROM appointments WHERE tenant_id = $1
              AND status != 'cancelled' AND {date_filter}
        """,
    }

    query = metric_queries.get(metric)
    if not query:
        return f"Metrica '{metric}' no disponible. Opciones: cancelaciones, nuevos_pacientes, facturacion, ocupacion."

    query_days = max(days, 1)
    lines = [f"Comparacion de sedes — {metric} ({period}):"]
    for tid in tenant_ids:
        name = await db.pool.fetchval(
            "SELECT clinic_name FROM tenants WHERE id = $1", tid
        )
        if days == 0:
            row = await db.pool.fetchrow(query, tid)
        else:
            row = await db.pool.fetchrow(query, tid, query_days)
        valor = row["valor"] if row else 0

        if metric == "cancelaciones" and row and row["total"]:
            rate = f" ({valor / row['total'] * 100:.1f}%)" if row["total"] > 0 else ""
            lines.append(f"• {name}: {valor} cancelaciones{rate}")
        elif metric == "facturacion":
            lines.append(f"• {name}: {_fmt_money(valor)}")
        else:
            lines.append(f"• {name}: {valor}")

    return "\n".join(lines)


async def _switch_sede(args: Dict, user_role: str) -> str:
    if user_role != "ceo":
        return _role_error("switch_sede", ["ceo"])

    clinic_name = args.get("clinic_name", "").strip()
    if not clinic_name:
        return "Necesito el nombre de la sede."

    row = await db.pool.fetchrow(
        "SELECT id, clinic_name FROM tenants WHERE clinic_name ILIKE $1 ORDER BY id LIMIT 1",
        f"%{clinic_name}%",
    )

    if not row:
        return f"No encontre una sede con el nombre '{clinic_name}'."

    # Return the new tenant_id for the session to update
    return json.dumps({
        "type": "sede_switch",
        "tenant_id": int(row["id"]),
        "clinic_name": row["clinic_name"],
        "message": f"Cambiado a sede: {row['clinic_name']}. Las proximas consultas se refieren a esta sede.",
    })


async def _onboarding_status(args: Dict, tenant_id: int, user_role: str) -> str:
    if user_role != 'ceo':
        return "Solo el CEO puede consultar el estado de onboarding."

    clinic_name = args.get("clinic_name")

    target_tid = tenant_id
    target_name = None

    if clinic_name:
        # Look up specific sede
        row = await db.pool.fetchrow(
            "SELECT id, clinic_name FROM tenants WHERE clinic_name ILIKE $1 ORDER BY id LIMIT 1",
            f"%{clinic_name}%",
        )
        if not row:
            return f"No encontre una sede con el nombre '{clinic_name}'."
        target_tid = int(row["id"])
        target_name = row["clinic_name"]
    else:
        target_name = await db.pool.fetchval(
            "SELECT clinic_name FROM tenants WHERE id = $1", target_tid
        )

    # Check each step
    has_professionals = await db.pool.fetchval(
        "SELECT EXISTS(SELECT 1 FROM professionals WHERE tenant_id = $1 AND is_active = true)",
        target_tid,
    )
    has_working_hours = await db.pool.fetchval(
        "SELECT EXISTS(SELECT 1 FROM professionals WHERE tenant_id = $1 AND is_active = true AND working_hours IS NOT NULL AND working_hours != '{}'::jsonb)",
        target_tid,
    )
    has_treatment_types = await db.pool.fetchval(
        "SELECT EXISTS(SELECT 1 FROM treatment_types WHERE tenant_id = $1 AND is_active = true)",
        target_tid,
    )
    has_whatsapp = await db.pool.fetchval(
        "SELECT EXISTS(SELECT 1 FROM credentials WHERE tenant_id = $1 AND category = 'ycloud')",
        target_tid,
    )
    has_google_calendar = await db.pool.fetchval(
        "SELECT EXISTS(SELECT 1 FROM google_oauth_tokens WHERE tenant_id = $1)",
        target_tid,
    )
    has_faqs = await db.pool.fetchval(
        "SELECT COUNT(*) >= 3 FROM clinic_faqs WHERE tenant_id = $1",
        target_tid,
    )

    tenant_data = await db.pool.fetchrow(
        "SELECT bank_cbu, bank_alias, consultation_price FROM tenants WHERE id = $1",
        target_tid,
    )
    has_bank = bool(tenant_data and (tenant_data["bank_cbu"] or tenant_data["bank_alias"]))
    has_price = bool(tenant_data and tenant_data["consultation_price"] is not None)

    checks = [
        ("Profesionales activos", has_professionals),
        ("Horarios configurados", has_working_hours),
        ("Tipos de tratamiento", has_treatment_types),
        ("WhatsApp conectado", has_whatsapp),
        ("Google Calendar", has_google_calendar),
        ("FAQs (3+)", has_faqs),
        ("Datos bancarios", has_bank),
        ("Precio de consulta", has_price),
    ]

    completed = sum(1 for _, v in checks if v)
    total = len(checks)

    lines = [f"Onboarding de {target_name or 'sede actual'}: {completed}/{total} completado(s)"]
    for label, done in checks:
        icon = "✅" if done else "❌"
        lines.append(f"  {icon} {label}")

    # Suggest next step
    next_steps = [label for label, done in checks if not done]
    if next_steps:
        lines.append(f"\nProximo paso: {next_steps[0]}")
    else:
        lines.append("\nOnboarding completo!")

    return "\n".join(lines)


# =============================================================================
# DISPATCHER
# =============================================================================

async def execute_nova_tool(
    name: str,
    args: Dict[str, Any],
    tenant_id: int,
    user_role: str,
    user_id: str,
) -> str:
    """
    Execute a Nova tool by name and return the response string.

    Args:
        name: Tool name (must match one of NOVA_TOOLS_SCHEMA entries)
        args: Tool arguments as parsed from OpenAI function calling
        tenant_id: Current tenant context (resolved from session)
        user_role: User role ('ceo', 'professional', 'secretary')
        user_id: User UUID string (for resolving professional_id)

    Returns:
        String response for OpenAI Realtime to speak
    """
    try:
        # A. Pacientes
        if name == "buscar_paciente":
            return await _buscar_paciente(args, tenant_id)
        elif name == "ver_paciente":
            return await _ver_paciente(args, tenant_id)
        elif name == "registrar_paciente":
            return await _registrar_paciente(args, tenant_id)
        elif name == "actualizar_paciente":
            return await _actualizar_paciente(args, tenant_id)
        elif name == "historial_clinico":
            return await _historial_clinico(args, tenant_id, user_role)
        elif name == "registrar_nota_clinica":
            return await _registrar_nota_clinica(args, tenant_id, user_role, user_id)

        # B. Turnos
        elif name == "ver_agenda":
            return await _ver_agenda(args, tenant_id, user_role, user_id)
        elif name == "proximo_paciente":
            return await _proximo_paciente(tenant_id, user_role, user_id)
        elif name == "verificar_disponibilidad":
            return await _verificar_disponibilidad(args, tenant_id)
        elif name == "agendar_turno":
            return await _agendar_turno(args, tenant_id)
        elif name == "cancelar_turno":
            return await _cancelar_turno(args, tenant_id)
        elif name == "confirmar_turnos":
            return await _confirmar_turnos(args, tenant_id)

        # C. Tratamientos y Facturacion
        elif name == "listar_tratamientos":
            return await _listar_tratamientos(args, tenant_id)
        elif name == "registrar_pago":
            return await _registrar_pago(args, tenant_id, user_role)
        elif name == "facturacion_pendiente":
            return await _facturacion_pendiente(tenant_id)

        # D. Analytics y Configuracion
        elif name == "resumen_semana":
            return await _resumen_semana(tenant_id, user_role)
        elif name == "rendimiento_profesional":
            return await _rendimiento_profesional(args, tenant_id, user_role)
        elif name == "actualizar_faq":
            return await _actualizar_faq(args, tenant_id)

        # E. Navegacion
        elif name == "ir_a_pagina":
            return await _ir_a_pagina(args)
        elif name == "ir_a_paciente":
            return await _ir_a_paciente(args, tenant_id)

        # F. Multi-sede CEO
        elif name == "resumen_sedes":
            return await _resumen_sedes(user_role)
        elif name == "comparar_sedes":
            return await _comparar_sedes(args, user_role)
        elif name == "switch_sede":
            return await _switch_sede(args, user_role)
        elif name == "onboarding_status":
            return await _onboarding_status(args, tenant_id, user_role)

        # G. New staff tools
        elif name == "listar_profesionales":
            return await _listar_profesionales(tenant_id)
        elif name == "reprogramar_turno":
            return await _reprogramar_turno(args, tenant_id)
        elif name == "ver_configuracion":
            return await _ver_configuracion(tenant_id)
        elif name == "actualizar_configuracion":
            return await _actualizar_configuracion(args, tenant_id, user_role)
        elif name == "crear_tratamiento":
            return await _crear_tratamiento(args, tenant_id, user_role)
        elif name == "editar_tratamiento":
            return await _editar_tratamiento(args, tenant_id, user_role)
        elif name == "ver_chats_recientes":
            return await _ver_chats_recientes(args, tenant_id)
        elif name == "enviar_mensaje":
            return await _enviar_mensaje(args, tenant_id, user_role)
        elif name == "ver_estadisticas":
            return await _ver_estadisticas(args, tenant_id)
        elif name == "bloquear_agenda":
            return await _bloquear_agenda(args, tenant_id)
        elif name == "eliminar_paciente":
            return await _eliminar_paciente(args, tenant_id, user_role)
        elif name == "ver_faqs":
            return await _ver_faqs(tenant_id)
        elif name == "eliminar_faq":
            return await _eliminar_faq(args, tenant_id)
        elif name == "cambiar_estado_turno":
            return await _cambiar_estado_turno(args, tenant_id)

        # H. Anamnesis
        elif name == "guardar_anamnesis":
            return await _guardar_anamnesis(args, tenant_id)
        elif name == "ver_anamnesis":
            return await _ver_anamnesis(args, tenant_id)

        # I. Consultas avanzadas
        elif name == "consultar_datos":
            return await _consultar_datos(args, tenant_id, user_role)
        elif name == "resumen_marketing":
            return await _resumen_marketing(args, tenant_id, user_role)
        elif name == "resumen_financiero":
            return await _resumen_financiero(args, tenant_id, user_role)

        else:
            return f"Tool '{name}' no reconocida."

    except Exception as e:
        logger.error(f"Error executing nova tool '{name}': {e}", exc_info=True)
        return f"Error al ejecutar '{name}': {str(e)}"


# =============================================================================
# G. NEW STAFF TOOLS IMPLEMENTATIONS
# =============================================================================

async def _listar_profesionales(tenant_id: int) -> str:
    rows = await db.pool.fetch(
        "SELECT id, first_name, last_name, specialty, consultation_price, is_active FROM professionals WHERE tenant_id = $1 ORDER BY first_name",
        tenant_id,
    )
    if not rows:
        return "No hay profesionales registrados."
    lines = ["Profesionales:"]
    for r in rows:
        status = "activo" if r["is_active"] else "inactivo"
        price = f" — ${r['consultation_price']}" if r.get("consultation_price") else ""
        lines.append(f"• {r['first_name']} {r['last_name']} ({r.get('specialty') or 'general'}) [{status}]{price} (ID: {r['id']})")
    return "\n".join(lines)


async def _reprogramar_turno(args: Dict, tenant_id: int) -> str:
    apt_id = args.get("appointment_id", "")
    new_date = args.get("new_date", "")
    new_time = args.get("new_time", "")
    if not apt_id or not new_date or not new_time:
        return "Necesito appointment_id, new_date (YYYY-MM-DD) y new_time (HH:MM)."
    new_dt = f"{new_date} {new_time}:00"
    await db.pool.execute(
        "UPDATE appointments SET appointment_datetime = $1, status = 'scheduled', updated_at = NOW() WHERE id = $2 AND tenant_id = $3",
        new_dt, apt_id, tenant_id,
    )
    return f"Turno {apt_id} reprogramado para {new_date} a las {new_time}."


async def _ver_configuracion(tenant_id: int) -> str:
    row = await db.pool.fetchrow("SELECT * FROM tenants WHERE id = $1", tenant_id)
    if not row:
        return "Clinica no encontrada."
    lines = [f"Configuracion de {row.get('clinic_name', 'Clinica')}:"]
    for field in ["clinic_name", "clinic_location", "clinic_phone", "website", "working_hours_start", "working_hours_end", "bank_cbu", "bank_alias", "bank_holder_name", "consultation_price", "owner_email"]:
        val = row.get(field)
        if val:
            lines.append(f"• {field}: {val}")
    return "\n".join(lines)


async def _actualizar_configuracion(args: Dict, tenant_id: int, user_role: str) -> str:
    if user_role != "ceo":
        return _role_error("actualizar_configuracion", ["ceo"])
    field = args.get("field", "")
    value = args.get("value", "")
    if not field:
        return "Necesito field y value."
    allowed = ["clinic_name", "clinic_location", "clinic_phone", "working_hours_start", "working_hours_end", "bank_cbu", "bank_alias", "bank_holder_name", "consultation_price", "website"]
    if field not in allowed:
        return f"Campo '{field}' no permitido. Opciones: {', '.join(allowed)}"
    await db.pool.execute(f"UPDATE tenants SET {field} = $1, updated_at = NOW() WHERE id = $2", value, tenant_id)
    return f"Configuracion actualizada: {field} = {value}"


async def _crear_tratamiento(args: Dict, tenant_id: int, user_role: str) -> str:
    if user_role != "ceo":
        return _role_error("crear_tratamiento", ["ceo"])
    name = args.get("name", "")
    code = args.get("code", "")
    duration = args.get("duration_minutes", 30)
    price = args.get("base_price", 0)
    category = args.get("category", "prevention")
    if not name or not code:
        return "Necesito name y code."
    await db.pool.execute(
        """INSERT INTO treatment_types (tenant_id, name, code, default_duration_minutes, base_price, category, is_active, created_at)
           VALUES ($1, $2, $3, $4, $5, $6, true, NOW())""",
        tenant_id, name, code, duration, price, category,
    )
    return f"Tratamiento '{name}' ({code}) creado — {duration} min, ${price}, categoria: {category}."


async def _editar_tratamiento(args: Dict, tenant_id: int, user_role: str) -> str:
    if user_role != "ceo":
        return _role_error("editar_tratamiento", ["ceo"])
    code = args.get("code", "")
    field = args.get("field", "")
    value = args.get("value", "")
    if not code or not field:
        return "Necesito code, field y value."
    field_map = {"name": "name", "duration_minutes": "default_duration_minutes", "base_price": "base_price", "category": "category", "is_active": "is_active"}
    db_field = field_map.get(field)
    if not db_field:
        return f"Campo '{field}' no valido. Opciones: {', '.join(field_map.keys())}"
    await db.pool.execute(f"UPDATE treatment_types SET {db_field} = $1 WHERE tenant_id = $2 AND code = $3", value, tenant_id, code)
    return f"Tratamiento '{code}' actualizado: {field} = {value}"


async def _ver_chats_recientes(args: Dict, tenant_id: int) -> str:
    limit = args.get("limit", 10)
    rows = await db.pool.fetch(
        """SELECT cc.customer_phone, cc.channel, cc.updated_at,
                  (SELECT content FROM chat_messages WHERE conversation_id = cc.id ORDER BY created_at DESC LIMIT 1) as last_msg
           FROM chat_conversations cc WHERE cc.tenant_id = $1 ORDER BY cc.updated_at DESC LIMIT $2""",
        tenant_id, limit,
    )
    if not rows:
        return "No hay conversaciones recientes."
    lines = ["Conversaciones recientes:"]
    for r in rows:
        phone = r["customer_phone"] or "?"
        channel = r["channel"] or "whatsapp"
        last = (r["last_msg"] or "")[:60]
        when = r["updated_at"].strftime("%d/%m %H:%M") if r["updated_at"] else "?"
        lines.append(f"• {phone} ({channel}) — {when}: {last}")
    return "\n".join(lines)


async def _enviar_mensaje(args: Dict, tenant_id: int, user_role: str) -> str:
    if user_role not in ("ceo", "secretary"):
        return _role_error("enviar_mensaje", ["ceo", "secretary"])
    phone = args.get("phone", "")
    message = args.get("message", "")
    if not phone or not message:
        return "Necesito phone y message."
    try:
        import httpx
        from core.credentials import get_tenant_credential
        ycloud_key = await get_tenant_credential(tenant_id, "YCLOUD_API_KEY")
        if not ycloud_key:
            return "No hay YCloud API key configurada para este tenant."
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                "https://api.ycloud.com/v2/whatsapp/messages/sendDirectly",
                headers={"X-API-Key": ycloud_key, "Content-Type": "application/json"},
                json={"from": os.getenv("BOT_PHONE_NUMBER", ""), "to": phone, "type": "text", "text": {"body": message}},
            )
        if resp.status_code == 200:
            return f"Mensaje enviado a {phone}: '{message[:50]}...'"
        return f"Error enviando mensaje: {resp.status_code}"
    except Exception as e:
        return f"Error: {e}"


async def _ver_estadisticas(args: Dict, tenant_id: int) -> str:
    period = args.get("period", "semana")
    days_map = {"hoy": 0, "semana": 7, "mes": 30, "año": 365}
    days = days_map.get(period, 7)

    if days == 0:
        date_filter = "AND DATE(appointment_datetime) = CURRENT_DATE"
    else:
        date_filter = f"AND appointment_datetime >= NOW() - make_interval(days => {days})"

    total = await db.pool.fetchval(f"SELECT COUNT(*) FROM appointments WHERE tenant_id = $1 {date_filter}", tenant_id) or 0
    completed = await db.pool.fetchval(f"SELECT COUNT(*) FROM appointments WHERE tenant_id = $1 AND status = 'completed' {date_filter}", tenant_id) or 0
    cancelled = await db.pool.fetchval(f"SELECT COUNT(*) FROM appointments WHERE tenant_id = $1 AND status = 'cancelled' {date_filter}", tenant_id) or 0
    no_shows = await db.pool.fetchval(f"SELECT COUNT(*) FROM appointments WHERE tenant_id = $1 AND status = 'no-show' {date_filter}", tenant_id) or 0
    new_patients = await db.pool.fetchval(f"SELECT COUNT(*) FROM patients WHERE tenant_id = $1 AND created_at >= NOW() - make_interval(days => {max(days, 1)})", tenant_id) or 0
    revenue = await db.pool.fetchval(f"SELECT COALESCE(SUM(billing_amount), 0) FROM appointments WHERE tenant_id = $1 AND payment_status = 'paid' {date_filter}", tenant_id) or 0

    return f"""Estadisticas ({period}):
• Turnos totales: {total}
• Completados: {completed}
• Cancelados: {cancelled}
• No-shows: {no_shows}
• Pacientes nuevos: {new_patients}
• Facturacion: ${revenue:,.0f}
• Tasa completitud: {(completed/total*100) if total > 0 else 0:.1f}%"""


async def _bloquear_agenda(args: Dict, tenant_id: int) -> str:
    prof_id = args.get("professional_id")
    start = args.get("start_datetime", "")
    end = args.get("end_datetime", "")
    reason = args.get("reason", "Bloqueado")
    if not prof_id or not start or not end:
        return "Necesito professional_id, start_datetime y end_datetime."
    await db.pool.execute(
        """INSERT INTO google_calendar_blocks (tenant_id, professional_id, start_time, end_time, title, source, created_at)
           VALUES ($1, $2, $3, $4, $5, 'manual', NOW())""",
        tenant_id, prof_id, start, end, reason,
    )
    return f"Agenda bloqueada: {start} a {end} — {reason}"


async def _eliminar_paciente(args: Dict, tenant_id: int, user_role: str) -> str:
    if user_role != "ceo":
        return _role_error("eliminar_paciente", ["ceo"])
    patient_id = args.get("patient_id")
    if not patient_id:
        return "Necesito patient_id."
    await db.pool.execute("UPDATE patients SET status = 'archived' WHERE id = $1 AND tenant_id = $2", patient_id, tenant_id)
    return f"Paciente {patient_id} archivado."


async def _ver_faqs(tenant_id: int) -> str:
    rows = await db.pool.fetch("SELECT id, question, answer FROM clinic_faqs WHERE tenant_id = $1 ORDER BY id", tenant_id)
    if not rows:
        return "No hay FAQs configuradas."
    lines = ["FAQs del chatbot:"]
    for r in rows:
        lines.append(f"• [{r['id']}] {r['question']}\n  → {(r['answer'] or '')[:80]}")
    return "\n".join(lines)


async def _eliminar_faq(args: Dict, tenant_id: int) -> str:
    faq_id = args.get("faq_id")
    if not faq_id:
        return "Necesito faq_id."
    await db.pool.execute("DELETE FROM clinic_faqs WHERE id = $1 AND tenant_id = $2", faq_id, tenant_id)
    return f"FAQ {faq_id} eliminada."


async def _cambiar_estado_turno(args: Dict, tenant_id: int) -> str:
    apt_id = args.get("appointment_id", "")
    status = args.get("status", "")
    if not apt_id or not status:
        return "Necesito appointment_id y status."
    allowed = ["completed", "no-show", "in-progress", "confirmed", "cancelled"]
    if status not in allowed:
        return f"Estado '{status}' no valido. Opciones: {', '.join(allowed)}"
    if status == "completed":
        await db.pool.execute("UPDATE appointments SET status = $1, completed_at = NOW(), updated_at = NOW() WHERE id = $2 AND tenant_id = $3", status, apt_id, tenant_id)
    else:
        await db.pool.execute("UPDATE appointments SET status = $1, updated_at = NOW() WHERE id = $2 AND tenant_id = $3", status, apt_id, tenant_id)
    return f"Turno {apt_id} → estado: {status}"


# =============================================================================
# H. ANAMNESIS POR VOZ (NEW)
# =============================================================================

async def _guardar_anamnesis(args: Dict, tenant_id: int) -> str:
    """Guarda datos de anamnesis en medical_history JSONB del paciente."""
    patient_id = args.get("patient_id")
    if not patient_id:
        return "Necesito el ID del paciente."

    # Build update data from provided fields
    fields = {}
    for key in ["base_diseases", "habitual_medication", "allergies", "previous_surgeries",
                "is_smoker", "smoker_amount", "pregnancy_lactation", "negative_experiences", "specific_fears"]:
        val = args.get(key)
        if val and str(val).strip():
            fields[key] = str(val).strip()

    if not fields:
        return "No me pasaste ningún dato para guardar. Decime qué querés cargar: enfermedades, alergias, medicación, cirugías previas, miedos..."

    # Merge with existing medical_history (don't overwrite)
    existing = await db.pool.fetchval(
        "SELECT medical_history FROM patients WHERE id = $1 AND tenant_id = $2",
        patient_id, tenant_id
    )
    current = {}
    if existing:
        if isinstance(existing, str):
            try:
                current = json.loads(existing)
            except Exception:
                current = {}
        elif isinstance(existing, dict):
            current = existing

    # Merge new fields (overwrite only what's provided)
    current.update(fields)
    current["anamnesis_completed_at"] = datetime.now().isoformat()
    current["anamnesis_source"] = "nova_voice"

    await db.pool.execute(
        "UPDATE patients SET medical_history = $1::jsonb, updated_at = NOW() WHERE id = $2 AND tenant_id = $3",
        json.dumps(current, ensure_ascii=False), patient_id, tenant_id
    )

    saved_fields = ", ".join(fields.keys())
    logger.info(f"🎙️ NOVA: Anamnesis saved for patient {patient_id}: {saved_fields}")
    return f"Guardé en la ficha médica: {saved_fields}. Hay algo más que quieras agregar? Puedo cargar: enfermedades de base, medicación, alergias, cirugías previas, si fuma, embarazo/lactancia, experiencias negativas, miedos."


async def _ver_anamnesis(args: Dict, tenant_id: int) -> str:
    """Lee la anamnesis completa de un paciente."""
    patient_id = args.get("patient_id")
    if not patient_id:
        return "Necesito el ID del paciente."

    row = await db.pool.fetchrow(
        "SELECT first_name, last_name, medical_history FROM patients WHERE id = $1 AND tenant_id = $2",
        patient_id, tenant_id
    )
    if not row:
        return "Paciente no encontrado."

    name = f"{row['first_name'] or ''} {row['last_name'] or ''}".strip()
    mh = row.get("medical_history")
    if not mh:
        return f"{name} no tiene ficha médica cargada. Querés que la completemos ahora?"

    if isinstance(mh, str):
        try:
            mh = json.loads(mh)
        except Exception:
            return f"{name} tiene datos pero no puedo leerlos."

    labels = {
        "base_diseases": "Enfermedades de base",
        "habitual_medication": "Medicación habitual",
        "allergies": "Alergias",
        "previous_surgeries": "Cirugías previas",
        "is_smoker": "Fumador",
        "smoker_amount": "Cigarrillos/día",
        "pregnancy_lactation": "Embarazo/Lactancia",
        "negative_experiences": "Experiencias negativas",
        "specific_fears": "Miedos específicos",
    }

    parts = [f"Ficha médica de {name}:"]
    filled = []
    missing = []
    for key, label in labels.items():
        val = mh.get(key)
        if val and str(val).strip() and str(val).strip().lower() not in ["no", "none", "null", ""]:
            parts.append(f"- {label}: {val}")
            filled.append(label)
        else:
            missing.append(label)

    if missing:
        parts.append(f"\nFaltan: {', '.join(missing)}")

    return "\n".join(parts)


# =============================================================================
# I. CONSULTAS AVANZADAS (NEW)
# =============================================================================

async def _consultar_datos(args: Dict, tenant_id: int, user_role: str) -> str:
    """Consulta flexible de datos de la plataforma."""
    consulta = args.get("consulta", "").lower()

    if not consulta:
        return "Decime qué datos necesitás."

    try:
        # Turnos de hoy/semana
        if any(w in consulta for w in ["turno", "agenda", "cita", "appointment"]):
            if "hoy" in consulta:
                start = date.today()
                end = start
            elif "semana" in consulta:
                start = date.today()
                end = start + timedelta(days=7)
            elif "mes" in consulta:
                start = date.today()
                end = start + timedelta(days=30)
            else:
                start = date.today()
                end = start + timedelta(days=7)

            rows = await db.pool.fetch("""
                SELECT a.appointment_datetime, a.status, a.appointment_type, a.payment_status,
                       p.first_name || ' ' || COALESCE(p.last_name, '') as patient_name,
                       prof.first_name as prof_name
                FROM appointments a
                JOIN patients p ON a.patient_id = p.id
                LEFT JOIN professionals prof ON a.professional_id = prof.id
                WHERE a.tenant_id = $1 AND DATE(a.appointment_datetime) BETWEEN $2 AND $3
                ORDER BY a.appointment_datetime ASC LIMIT 20
            """, tenant_id, start, end)

            if not rows:
                return f"No hay turnos entre {start} y {end}."

            parts = [f"{len(rows)} turnos encontrados:"]
            for r in rows:
                dt = r['appointment_datetime']
                parts.append(f"- {dt.strftime('%d/%m %H:%M')} | {r['patient_name']} | {r['appointment_type'] or 'consulta'} | {r['prof_name'] or '?'} | {r['status']} | pago: {r['payment_status'] or 'pendiente'}")
            return "\n".join(parts)

        # Pacientes
        elif any(w in consulta for w in ["paciente", "patient", "registrado"]):
            count = await db.pool.fetchval("SELECT COUNT(*) FROM patients WHERE tenant_id = $1", tenant_id)
            new_month = await db.pool.fetchval(
                "SELECT COUNT(*) FROM patients WHERE tenant_id = $1 AND created_at >= NOW() - INTERVAL '30 days'", tenant_id
            )
            return f"Total pacientes: {count}. Nuevos último mes: {new_month}."

        # Ingresos / pagos
        elif any(w in consulta for w in ["ingreso", "pago", "facturación", "revenue", "cobr"]):
            row = await db.pool.fetchrow("""
                SELECT COUNT(*) as total, COUNT(*) FILTER (WHERE payment_status = 'paid') as paid,
                       COALESCE(SUM(billing_amount) FILTER (WHERE payment_status = 'paid'), 0) as revenue
                FROM appointments WHERE tenant_id = $1 AND appointment_datetime >= NOW() - INTERVAL '30 days'
            """, tenant_id)
            return f"Últimos 30 días: {row['total']} turnos, {row['paid']} pagados, ${int(row['revenue']):,} facturados.".replace(",", ".")

        # Leads
        elif any(w in consulta for w in ["lead", "prospecto", "meta", "formulario"]):
            rows = await db.pool.fetch("""
                SELECT status, COUNT(*) as cnt FROM patients
                WHERE tenant_id = $1 AND acquisition_source IS NOT NULL
                GROUP BY status
            """, tenant_id)
            if not rows:
                return "No hay leads registrados."
            parts = ["Leads por estado:"]
            for r in rows:
                parts.append(f"- {r['status'] or 'sin estado'}: {r['cnt']}")
            return "\n".join(parts)

        # No-shows
        elif "no-show" in consulta or "no show" in consulta or "ausencia" in consulta:
            row = await db.pool.fetchrow("""
                SELECT COUNT(*) as total,
                       COUNT(*) FILTER (WHERE status = 'no_show') as no_shows
                FROM appointments WHERE tenant_id = $1 AND appointment_datetime >= NOW() - INTERVAL '30 days'
            """, tenant_id)
            rate = (row['no_shows'] / row['total'] * 100) if row['total'] > 0 else 0
            return f"Últimos 30 días: {row['no_shows']} no-shows de {row['total']} turnos ({rate:.1f}%)."

        # Cancelaciones
        elif "cancel" in consulta:
            row = await db.pool.fetchrow("""
                SELECT COUNT(*) as total,
                       COUNT(*) FILTER (WHERE status = 'cancelled') as cancelled
                FROM appointments WHERE tenant_id = $1 AND appointment_datetime >= NOW() - INTERVAL '30 days'
            """, tenant_id)
            rate = (row['cancelled'] / row['total'] * 100) if row['total'] > 0 else 0
            return f"Últimos 30 días: {row['cancelled']} cancelaciones de {row['total']} turnos ({rate:.1f}%)."

        # Generic fallback
        else:
            # Try a broad stats query
            stats = await db.pool.fetchrow("""
                SELECT
                    (SELECT COUNT(*) FROM patients WHERE tenant_id = $1) as patients,
                    (SELECT COUNT(*) FROM appointments WHERE tenant_id = $1 AND status IN ('scheduled', 'confirmed') AND appointment_datetime > NOW()) as upcoming,
                    (SELECT COUNT(*) FROM appointments WHERE tenant_id = $1 AND status = 'completed' AND appointment_datetime >= NOW() - INTERVAL '30 days') as completed_month
            """, tenant_id)
            return f"Resumen: {stats['patients']} pacientes, {stats['upcoming']} turnos próximos, {stats['completed_month']} completados este mes."

    except Exception as e:
        logger.error(f"consultar_datos error: {e}")
        return f"Error consultando datos: {str(e)}"


async def _resumen_marketing(args: Dict, tenant_id: int, user_role: str) -> str:
    """Resumen de marketing con datos de Meta Ads si están disponibles."""
    if user_role not in ("ceo",):
        return "Solo el CEO puede ver datos de marketing."

    periodo = args.get("periodo", "mes")
    days = {"hoy": 1, "semana": 7, "mes": 30, "trimestre": 90, "año": 365}.get(periodo, 30)

    try:
        # Leads por fuente
        leads = await db.pool.fetch("""
            SELECT COALESCE(acquisition_source, 'DIRECTO') as source, COUNT(*) as cnt
            FROM patients WHERE tenant_id = $1 AND created_at >= NOW() - INTERVAL '1 day' * $2
            GROUP BY acquisition_source ORDER BY cnt DESC
        """, tenant_id, days)

        # Ads spend from meta if available
        ad_spend = await db.pool.fetchval("""
            SELECT COALESCE(SUM(spend), 0) FROM meta_ad_insights
            WHERE tenant_id = $1 AND date_start >= NOW() - INTERVAL '1 day' * $2
        """, tenant_id, days) if await _table_exists("meta_ad_insights") else 0

        total_leads = sum(r['cnt'] for r in leads) if leads else 0
        cost_per_lead = float(ad_spend) / total_leads if total_leads > 0 and ad_spend else 0

        parts = [f"Marketing últimos {days} días:"]
        if ad_spend:
            parts.append(f"Inversión Meta Ads: ${int(float(ad_spend)):,}".replace(",", "."))
        parts.append(f"Total leads: {total_leads}")
        if cost_per_lead > 0:
            parts.append(f"Costo por lead: ${int(cost_per_lead):,}".replace(",", "."))
        if leads:
            parts.append("Por fuente:")
            for r in leads:
                parts.append(f"  - {r['source']}: {r['cnt']}")
        return "\n".join(parts)

    except Exception as e:
        logger.error(f"resumen_marketing error: {e}")
        return f"Error obteniendo datos de marketing: {str(e)}"


async def _resumen_financiero(args: Dict, tenant_id: int, user_role: str) -> str:
    """Resumen financiero detallado."""
    if user_role not in ("ceo",):
        return "Solo el CEO puede ver datos financieros."

    periodo = args.get("periodo", "mes")
    days = {"hoy": 1, "semana": 7, "mes": 30, "trimestre": 90, "año": 365}.get(periodo, 30)

    try:
        # Revenue by treatment
        by_treatment = await db.pool.fetch("""
            SELECT a.appointment_type, COUNT(*) as cnt,
                   COALESCE(SUM(a.billing_amount), 0) as revenue,
                   COUNT(*) FILTER (WHERE a.payment_status = 'paid') as paid
            FROM appointments a
            WHERE a.tenant_id = $1 AND a.appointment_datetime >= NOW() - INTERVAL '1 day' * $2
            AND a.status IN ('completed', 'confirmed', 'scheduled')
            GROUP BY a.appointment_type ORDER BY revenue DESC
        """, tenant_id, days)

        # Revenue by professional
        by_prof = await db.pool.fetch("""
            SELECT prof.first_name, COUNT(*) as cnt,
                   COALESCE(SUM(a.billing_amount), 0) as revenue
            FROM appointments a
            LEFT JOIN professionals prof ON a.professional_id = prof.id
            WHERE a.tenant_id = $1 AND a.appointment_datetime >= NOW() - INTERVAL '1 day' * $2
            AND a.status IN ('completed', 'confirmed', 'scheduled')
            GROUP BY prof.first_name ORDER BY revenue DESC
        """, tenant_id, days)

        # Pending payments
        pending = await db.pool.fetchrow("""
            SELECT COUNT(*) as cnt, COALESCE(SUM(billing_amount), 0) as amount
            FROM appointments WHERE tenant_id = $1 AND payment_status = 'pending'
            AND billing_amount > 0 AND status IN ('scheduled', 'confirmed')
        """, tenant_id)

        total_revenue = sum(float(r['revenue']) for r in by_treatment)
        parts = [f"Finanzas últimos {days} días:"]
        parts.append(f"Facturación total: ${int(total_revenue):,}".replace(",", "."))
        parts.append(f"Pagos pendientes: {pending['cnt']} turnos (${int(float(pending['amount'])):,})".replace(",", "."))

        if by_treatment:
            parts.append("\nPor tratamiento:")
            for r in by_treatment:
                parts.append(f"  - {r['appointment_type'] or 'consulta'}: {r['cnt']} turnos, ${int(float(r['revenue'])):,} ({r['paid']} pagados)".replace(",", "."))

        if by_prof:
            parts.append("\nPor profesional:")
            for r in by_prof:
                parts.append(f"  - {r['first_name'] or '?'}: {r['cnt']} turnos, ${int(float(r['revenue'])):,}".replace(",", "."))

        return "\n".join(parts)

    except Exception as e:
        logger.error(f"resumen_financiero error: {e}")
        return f"Error obteniendo datos financieros: {str(e)}"


async def _table_exists(table_name: str) -> bool:
    """Check if a table exists in the database."""
    try:
        exists = await db.pool.fetchval(
            "SELECT EXISTS(SELECT 1 FROM information_schema.tables WHERE table_name = $1)",
            table_name
        )
        return bool(exists)
    except Exception:
        return False
