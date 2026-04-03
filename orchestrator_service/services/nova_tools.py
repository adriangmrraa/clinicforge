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
import os
import uuid
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any, Dict, List, Optional

from db import db

logger = logging.getLogger(__name__)


# =============================================================================
# Helper: emit Socket.IO events from Nova tools (for real-time UI sync)
# =============================================================================
async def _nova_emit(event: str, data: Dict[str, Any]):
    """Emit a Socket.IO event so the frontend updates in real-time."""
    try:
        from main import sio, to_json_safe

        await sio.emit(event, to_json_safe(data))
        logger.info(f"📡 NOVA Socket: {event} → {list(data.keys())}")
    except Exception as e:
        logger.warning(f"📡 NOVA Socket emit failed ({event}): {e}")


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
                "phone_number": {
                    "type": "string",
                    "description": "Telefono del paciente",
                },
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
        "description": "Registra el pago de un turno completado o de un plan de tratamiento. Solo para CEO y secretarias.",
        "parameters": {
            "type": "object",
            "properties": {
                "appointment_id": {
                    "type": "string",
                    "description": "UUID del turno (opcional si se proporciona plan_id)",
                },
                "plan_id": {
                    "type": "string",
                    "description": "UUID del plan de tratamiento (opcional si se proporciona appointment_id)",
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
            "required": ["amount", "method"],
        },
    },
    {
        "type": "function",
        "name": "registrar_pago_plan",
        "description": "Registra un pago en un plan de tratamiento. Solo para CEO y secretarias.",
        "parameters": {
            "type": "object",
            "properties": {
                "plan_id": {
                    "type": "string",
                    "description": "UUID del plan de tratamiento",
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
                "payment_date": {
                    "type": "string",
                    "description": "Fecha de pago en formato YYYY-MM-DD (opcional, por defecto hoy)",
                },
            },
            "required": ["plan_id", "amount", "method"],
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
    # === G. Staff operations ===
    {
        "type": "function",
        "name": "listar_profesionales",
        "description": "Lista dentistas/profesionales activos con especialidad, horarios y precio de consulta.",
        "parameters": {"type": "object", "properties": {}},
    },
    {
        "type": "function",
        "name": "reprogramar_turno",
        "description": "Reprograma un turno existente a nueva fecha/hora.",
        "parameters": {
            "type": "object",
            "properties": {
                "appointment_id": {"type": "string", "description": "UUID del turno"},
                "new_date": {"type": "string", "description": "Nueva fecha YYYY-MM-DD"},
                "new_time": {"type": "string", "description": "Nueva hora HH:MM"},
            },
            "required": ["appointment_id", "new_date", "new_time"],
        },
    },
    {
        "type": "function",
        "name": "ver_configuracion",
        "description": "Ver configuracion de la clinica: nombre, direccion, horarios, datos bancarios, precio consulta.",
        "parameters": {"type": "object", "properties": {}},
    },
    {
        "type": "function",
        "name": "actualizar_configuracion",
        "description": "Actualizar configuracion de la clinica. Solo CEO.",
        "parameters": {
            "type": "object",
            "properties": {
                "field": {
                    "type": "string",
                    "enum": [
                        "clinic_name",
                        "address",
                        "clinic_phone",
                        "bank_cbu",
                        "bank_alias",
                        "bank_holder_name",
                        "consultation_price",
                        "website",
                        "owner_email",
                    ],
                },
                "value": {"type": "string"},
            },
            "required": ["field", "value"],
        },
    },
    {
        "type": "function",
        "name": "crear_tratamiento",
        "description": "Crear nuevo tipo de tratamiento. Solo CEO.",
        "parameters": {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "code": {"type": "string"},
                "duration_minutes": {"type": "integer"},
                "base_price": {"type": "number"},
                "category": {
                    "type": "string",
                    "enum": [
                        "prevention",
                        "restorative",
                        "surgical",
                        "orthodontics",
                        "emergency",
                    ],
                },
            },
            "required": ["name", "code", "duration_minutes"],
        },
    },
    {
        "type": "function",
        "name": "editar_tratamiento",
        "description": "Editar un tipo de tratamiento existente. Solo CEO.",
        "parameters": {
            "type": "object",
            "properties": {
                "code": {"type": "string"},
                "field": {
                    "type": "string",
                    "enum": [
                        "name",
                        "duration_minutes",
                        "base_price",
                        "category",
                        "is_active",
                    ],
                },
                "value": {"type": "string"},
            },
            "required": ["code", "field", "value"],
        },
    },
    {
        "type": "function",
        "name": "ver_chats_recientes",
        "description": "Ver ultimas conversaciones de WhatsApp/Instagram/Facebook.",
        "parameters": {
            "type": "object",
            "properties": {
                "limit": {
                    "type": "integer",
                    "description": "Cantidad de chats (default 10)",
                }
            },
        },
    },
    {
        "type": "function",
        "name": "enviar_mensaje",
        "description": "Enviar mensaje de WhatsApp a un paciente. Podés pasar el teléfono directo O el nombre/ID del paciente (el sistema busca su teléfono). Si decís 'mandále un mensaje a García diciendo X', usá patient_name='García' y message='X'. SIEMPRE usá esta tool cuando te pidan contactar, avisar, recordar o mandar mensaje a un paciente.",
        "parameters": {
            "type": "object",
            "properties": {
                "phone": {
                    "type": "string",
                    "description": "Teléfono directo con código de área (opcional si pasás patient_id o patient_name)",
                },
                "patient_id": {
                    "type": "integer",
                    "description": "ID del paciente (el sistema busca su teléfono automáticamente)",
                },
                "patient_name": {
                    "type": "string",
                    "description": "Nombre del paciente para buscar (si no tenés phone ni patient_id)",
                },
                "message": {
                    "type": "string",
                    "description": "Texto del mensaje a enviar",
                },
            },
            "required": ["message"],
        },
    },
    {
        "type": "function",
        "name": "ver_estadisticas",
        "description": "Estadisticas generales: turnos, pacientes, facturacion, cancelaciones.",
        "parameters": {
            "type": "object",
            "properties": {
                "period": {"type": "string", "enum": ["hoy", "semana", "mes", "año"]}
            },
        },
    },
    {
        "type": "function",
        "name": "bloquear_agenda",
        "description": "Crear bloque de horario no disponible.",
        "parameters": {
            "type": "object",
            "properties": {
                "professional_id": {"type": "integer"},
                "start_datetime": {
                    "type": "string",
                    "description": "Inicio YYYY-MM-DD HH:MM",
                },
                "end_datetime": {
                    "type": "string",
                    "description": "Fin YYYY-MM-DD HH:MM",
                },
                "reason": {"type": "string"},
            },
            "required": ["professional_id", "start_datetime", "end_datetime"],
        },
    },
    {
        "type": "function",
        "name": "eliminar_paciente",
        "description": "Desactivar paciente (soft delete). Solo CEO.",
        "parameters": {
            "type": "object",
            "properties": {"patient_id": {"type": "integer"}},
            "required": ["patient_id"],
        },
    },
    {
        "type": "function",
        "name": "ver_faqs",
        "description": "Lista FAQs del chatbot.",
        "parameters": {"type": "object", "properties": {}},
    },
    {
        "type": "function",
        "name": "eliminar_faq",
        "description": "Eliminar FAQ por ID.",
        "parameters": {
            "type": "object",
            "properties": {"faq_id": {"type": "integer"}},
            "required": ["faq_id"],
        },
    },
    {
        "type": "function",
        "name": "cambiar_estado_turno",
        "description": "Cambiar estado de turno: completed, no-show, in-progress, confirmed.",
        "parameters": {
            "type": "object",
            "properties": {
                "appointment_id": {"type": "string"},
                "status": {
                    "type": "string",
                    "enum": ["completed", "no-show", "in-progress", "confirmed"],
                },
            },
            "required": ["appointment_id", "status"],
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
                "base_diseases": {
                    "type": "string",
                    "description": "Enfermedades de base (diabetes, hipertensión, etc.)",
                },
                "habitual_medication": {
                    "type": "string",
                    "description": "Medicación habitual",
                },
                "allergies": {
                    "type": "string",
                    "description": "Alergias (penicilina, anestesia, etc.)",
                },
                "previous_surgeries": {
                    "type": "string",
                    "description": "Cirugías previas",
                },
                "is_smoker": {"type": "string", "description": "Si fuma: 'si' o 'no'"},
                "smoker_amount": {
                    "type": "string",
                    "description": "Cantidad de cigarrillos por día",
                },
                "pregnancy_lactation": {
                    "type": "string",
                    "description": "'embarazo', 'lactancia', 'no_aplica'",
                },
                "negative_experiences": {
                    "type": "string",
                    "description": "Experiencias negativas previas en dentista",
                },
                "specific_fears": {
                    "type": "string",
                    "description": "Miedos específicos (agujas, dolor, etc.)",
                },
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
    # H2. Odontograma
    # -------------------------------------------------------------------------
    {
        "type": "function",
        "name": "ver_odontograma",
        "description": "Muestra el estado actual COMPLETO del odontograma de un paciente. Llamá SIEMPRE esta tool antes de modificar el odontograma para ver el estado actual. Muestra cada pieza con su estado y superficies afectadas. Soporta dentición permanente (32 piezas) y temporal/decidua (20 piezas).",
        "parameters": {
            "type": "object",
            "properties": {
                "patient_id": {"type": "integer", "description": "ID del paciente"},
                "denticion": {
                    "type": "string",
                    "enum": ["permanente", "temporal"],
                    "description": "Tipo de dentición: 'permanente' (32 piezas, FDI 11-48) o 'temporal' (20 piezas, FDI 51-85). Por defecto 'permanente'.",
                },
            },
            "required": ["patient_id"],
        },
    },
    {
        "type": "function",
        "name": "modificar_odontograma",
        "description": """Modifica el estado de UNA O VARIAS piezas dentales en el odontograma del paciente. Los cambios se persisten en el registro clínico más reciente (o se crea uno nuevo si no existe).
IMPORTANTE — REGLAS QUIRÚRGICAS:
1. SIEMPRE llamá 'ver_odontograma' ANTES para conocer el estado actual.
2. OBLIGATORIO: el parámetro 'piezas' con los números FDI exactos. Si el usuario NO dice números de piezas → NO llamar esta tool, PREGUNTAR primero cuáles son.
3. NUNCA asumas números de piezas. Si el usuario dice 'tiene caries' sin decir qué pieza → preguntá: '¿En qué pieza o piezas?'
4. Nomenclatura FDI permanente: 1.1-1.8 (superior derecho), 2.1-2.8 (superior izquierdo), 3.1-3.8 (inferior izquierdo), 4.1-4.8 (inferior derecho). Nomenclatura temporal: 5.1-5.5 (superior derecho), 6.1-6.5 (superior izquierdo), 7.1-7.5 (inferior izquierdo), 8.1-8.5 (inferior derecho). Pasá como número entero sin punto: 16, 18, 21, 36, 51, 55, etc.
5. Podés modificar varias piezas en una sola llamada pasando múltiples entradas en 'piezas'.
6. Soporta dentición permanente (32 piezas) y temporal/decidua (20 piezas).""",
        "parameters": {
            "type": "object",
            "properties": {
                "patient_id": {"type": "integer", "description": "ID del paciente"},
                "denticion": {
                    "type": "string",
                    "enum": ["permanente", "temporal"],
                    "description": "Tipo de dentición: 'permanente' (32 piezas) o 'temporal' (20 piezas). Por defecto 'permanente'.",
                },
                "piezas": {
                    "type": "array",
                    "description": "Lista de piezas a modificar. Cada entrada tiene número FDI, estado y opcionalmente superficies afectadas.",
                    "items": {
                        "type": "object",
                        "properties": {
                            "numero": {
                                "type": "integer",
                                "description": "Número FDI de la pieza (ej: 16, 21, 36, 48, 51, 55, etc.). SIN punto.",
                            },
                            "estado": {
                                "type": "string",
                                "enum": [
                                    "healthy",
                                    "caries",
                                    "restauracion_resina",
                                    "restauracion_amalgama",
                                    "restauracion_temporal",
                                    "sellador_fisuras",
                                    "carilla",
                                    "puente",
                                    "corona_porcelana",
                                    "corona_resina",
                                    "corona_metalceramica",
                                    "corona_temporal",
                                    "incrustacion",
                                    "onlay",
                                    "poste",
                                    "perno",
                                    "fibras_ribbond",
                                    "tratamiento_conducto",
                                    "implante",
                                    "radiografia",
                                    "protesis_fija",
                                    "protesis_removible",
                                    "blanqueamiento",
                                    "fluorosis",
                                    "hipoplasia",
                                    "desgaste",
                                    "caries_incipiente",
                                    "caries_recurrente",
                                    "caries_radicular",
                                    "fractura",
                                    "fisura",
                                    "absceso",
                                    "fistula",
                                    "sinus",
                                    "periodontitis",
                                    "gingivitis",
                                    "recesion_gingival",
                                    "movilidad_dental",
                                    "necrosis",
                                    "pulpotomia",
                                    "apicogenesis",
                                    "apicificacion",
                                    "extraction",
                                    "treatment_planned",
                                    "crown",
                                    "missing",
                                    "prosthesis",
                                    "root_canal",
                                ],
                                "description": "Estado de la pieza (42 opciones): healthy=sano, caries=caries, restauracion_resina=resina, restauracion_amalgama=amalgama, restauracion_temporal=restauración temporal, sellador_fisuras=sellador, carilla=carilla, puente=puente, corona_porcelana=corona porcelana, corona_resina=corona resina, corona_metalceramica=corona metalcerámica, corona_temporal=corona temporal, incrustacion=incrustación, onlay=onlay, poste=poste, perno=perno, fibras_ribbond=fibras ribbond, tratamiento_conducto=tratamiento de conducto, implante=implante, radiografia=radiografía, protesis_fija=prótesis fija, protesis_removible=prótesis removible, blanqueamiento=blanqueamiento, fluorosis=fluorosis, hipoplasia=hipoplasia, desgaste=desgaste, caries_incipiente=caries incipiente, caries_recurrente=caries recurrente, caries_radicular=caries radicular, fractura=fractura, fisura=fisura, absceso=absceso, fistula=fístula, sinus=sinus, periodontitis=periodontitis, gingivitis=gingivitis, recesion_gingival=recesión gingival, movilidad_dental=movilidad, necrosis=necrosis, pulpotomia=pulpotomía, apicogenesis=apicogénesis, apicificacion=apicificación, extraction=extracción, treatment_planned=planificado, crown=corona, missing=ausente, prosthesis=prótesis, root_canal=conducto",
                            },
                            "superficies": {
                                "type": "object",
                                "description": "Superficies afectadas (opcional). Solo pasar las que cambian.",
                                "properties": {
                                    "occlusal": {
                                        "type": "string",
                                        "description": "Estado de superficie oclusal (cualquiera de los 42 estados)",
                                    },
                                    "vestibular": {
                                        "type": "string",
                                        "description": "Estado de superficie vestibular/bucal",
                                    },
                                    "lingual": {
                                        "type": "string",
                                        "description": "Estado de superficie lingual/palatino",
                                    },
                                    "mesial": {
                                        "type": "string",
                                        "description": "Estado de superficie mesial",
                                    },
                                    "distal": {
                                        "type": "string",
                                        "description": "Estado de superficie distal",
                                    },
                                },
                            },
                            "notas": {
                                "type": "string",
                                "description": "Nota clínica para esta pieza (opcional)",
                            },
                        },
                        "required": ["numero", "estado"],
                    },
                },
                "diagnostico": {
                    "type": "string",
                    "description": "Diagnóstico general asociado a estos cambios (opcional, ej: 'Caries en piezas 16 y 18')",
                },
            },
            "required": ["patient_id", "piezas"],
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
                "consulta": {
                    "type": "string",
                    "description": "Qué datos necesitás. Ej: 'cuántos turnos hay esta semana', 'pacientes sin turno en 3 meses', 'ingresos del mes', 'leads de Meta sin contactar', 'tasa de no-show por profesional'",
                },
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
                "periodo": {
                    "type": "string",
                    "enum": ["hoy", "semana", "mes", "trimestre", "año"],
                    "description": "Período del reporte",
                },
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
                "periodo": {
                    "type": "string",
                    "enum": ["hoy", "semana", "mes", "trimestre", "año"],
                    "description": "Período del reporte",
                },
            },
            "required": ["periodo"],
        },
    },
    # -------------------------------------------------------------------------
    # J. CRUD GENÉRICO — Acceso directo a TODA la infraestructura
    # -------------------------------------------------------------------------
    {
        "type": "function",
        "name": "obtener_registros",
        "description": "Obtiene registros de CUALQUIER tabla de la plataforma. Tablas: patients, appointments, professionals, treatment_types, tenants, chat_messages, chat_conversations, patient_documents, clinical_records, automation_logs, patient_memories, meta_ad_insights. Podés filtrar por cualquier campo y limitar resultados.",
        "parameters": {
            "type": "object",
            "properties": {
                "tabla": {
                    "type": "string",
                    "description": "Nombre de la tabla: patients, appointments, professionals, treatment_types, tenants, clinical_records, patient_documents, automation_logs, chat_conversations, patient_memories",
                },
                "filtros": {
                    "type": "string",
                    "description": "Filtros en lenguaje natural. Ej: 'status=scheduled', 'created_at > 2026-03-01', 'patient_id=32', 'professional_id=2 AND status=completed'",
                },
                "campos": {
                    "type": "string",
                    "description": "Campos a devolver separados por coma. Ej: 'id,first_name,last_name,phone_number'. Dejar vacío para todos.",
                },
                "limite": {
                    "type": "integer",
                    "description": "Máximo de registros (default 10)",
                },
                "orden": {
                    "type": "string",
                    "description": "Campo y dirección. Ej: 'created_at DESC', 'appointment_datetime ASC'",
                },
            },
            "required": ["tabla"],
        },
    },
    {
        "type": "function",
        "name": "actualizar_registro",
        "description": "Actualiza campos de UN registro en cualquier tabla. Requiere el ID del registro. Solo CEO puede modificar tenants y professionals.",
        "parameters": {
            "type": "object",
            "properties": {
                "tabla": {"type": "string", "description": "Nombre de la tabla"},
                "registro_id": {
                    "type": "string",
                    "description": "ID del registro a actualizar (puede ser integer o UUID)",
                },
                "campos": {
                    "type": "string",
                    "description": 'Campos a actualizar en formato JSON. Ej: \'{"status": "completed", "billing_amount": 15000}\'',
                },
            },
            "required": ["tabla", "registro_id", "campos"],
        },
    },
    {
        "type": "function",
        "name": "crear_registro",
        "description": "Crea un nuevo registro en cualquier tabla. Principalmente para: patients, appointments, clinical_records, patient_documents, clinic_faqs.",
        "parameters": {
            "type": "object",
            "properties": {
                "tabla": {"type": "string", "description": "Nombre de la tabla"},
                "datos": {
                    "type": "string",
                    "description": 'Datos del registro en formato JSON. Ej: \'{"first_name": "Juan", "last_name": "Pérez", "phone_number": "+5493704123456"}\'',
                },
            },
            "required": ["tabla", "datos"],
        },
    },
    {
        "type": "function",
        "name": "contar_registros",
        "description": "Cuenta registros en cualquier tabla con filtros opcionales. Útil para estadísticas rápidas: cuántos pacientes, turnos del mes, cancelaciones, etc.",
        "parameters": {
            "type": "object",
            "properties": {
                "tabla": {"type": "string", "description": "Nombre de la tabla"},
                "filtros": {
                    "type": "string",
                    "description": "Filtros. Ej: 'status=cancelled AND appointment_datetime > 2026-03-01'",
                },
            },
            "required": ["tabla"],
        },
    },
    {
        "type": "function",
        "name": "buscar_en_base_conocimiento",
        "description": "Busca información relevante en la base de conocimiento de la clínica usando búsqueda semántica (RAG). Útil para consultar FAQs, protocolos o información que no recordás. Ejemplo: 'qué dice nuestra FAQ sobre blanqueamiento?'",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Consulta en lenguaje natural. Ej: 'precio de ortodoncia', 'protocolo de implantes'",
                },
                "tipo": {
                    "type": "string",
                    "enum": ["faq"],
                    "description": "Tipo de búsqueda. Por ahora solo 'faq'.",
                },
            },
            "required": ["query"],
        },
    },
    # -------------------------------------------------------------------------
    # L. Obras sociales y derivación (2)
    # -------------------------------------------------------------------------
    {
        "type": "function",
        "name": "consultar_obra_social",
        "description": "Consultar si la clínica trabaja con una obra social específica y en qué condiciones.",
        "parameters": {
            "type": "object",
            "properties": {
                "nombre": {
                    "type": "string",
                    "description": "Nombre de la obra social a consultar",
                }
            },
            "required": ["nombre"],
        },
    },
    {
        "type": "function",
        "name": "ver_reglas_derivacion",
        "description": "Ver todas las reglas de derivación de pacientes configuradas en la clínica (quién atiende qué perfil de paciente).",
        "parameters": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    # -------------------------------------------------------------------------
    # M. Fichas Digitales (2)
    # -------------------------------------------------------------------------
    {
        "type": "function",
        "name": "generar_ficha_digital",
        "description": "Generar una ficha digital (informe clínico, post-quirúrgico, evaluación odontológica o solicitud de autorización) para un paciente. Usa IA para redactar el contenido basándose en los datos clínicos del paciente.",
        "parameters": {
            "type": "object",
            "properties": {
                "patient_id": {
                    "type": "integer",
                    "description": "ID del paciente",
                },
                "tipo_documento": {
                    "type": "string",
                    "enum": [
                        "clinical_report",
                        "post_surgery",
                        "odontogram_art",
                        "authorization_request",
                    ],
                    "description": "Tipo de documento: clinical_report (informe clínico), post_surgery (post-quirúrgico), odontogram_art (evaluación odontológica), authorization_request (solicitud de autorización)",
                },
            },
            "required": ["patient_id", "tipo_documento"],
        },
    },
    {
        "type": "function",
        "name": "enviar_ficha_digital",
        "description": "Enviar una ficha digital por email con el PDF adjunto. Si no se especifica record_id, envía la más reciente del paciente. Si no se especifica email, usa el email del paciente.",
        "parameters": {
            "type": "object",
            "properties": {
                "patient_id": {
                    "type": "integer",
                    "description": "ID del paciente",
                },
                "record_id": {
                    "type": "string",
                    "description": "ID de la ficha digital (opcional, usa la más reciente si no se especifica)",
                },
                "email": {
                    "type": "string",
                    "description": "Email de destino (opcional, usa el del paciente si no se especifica)",
                },
            },
            "required": ["patient_id"],
        },
    },
    # O. Treatment Plans / Budget (NEW)
    # -------------------------------------------------------------------------
    {
        "type": "function",
        "name": "ver_presupuesto_paciente",
        "description": "Muestra el/los presupuesto(s) de tratamiento de un paciente: items, precios, pagos y saldo pendiente. Si hay múltiples pacientes, pide aclarar. Si no hay planes activos, informa claramente.",
        "parameters": {
            "type": "object",
            "properties": {
                "patient_id": {
                    "type": "integer",
                    "description": "ID del paciente (opcional si se busca por nombre)",
                },
                "patient_name": {
                    "type": "string",
                    "description": "Nombre del paciente para buscar (opcional si se usa patient_id)",
                },
                "plan_id": {
                    "type": "string",
                    "description": "ID específico del plan a ver (opcional)",
                },
                "include_completed": {
                    "type": "boolean",
                    "description": "Incluir planes completados (default: false)",
                },
            },
        },
    },
    # O2. Aprobar presupuesto
    # -------------------------------------------------------------------------
    {
        "type": "function",
        "name": "aprobar_presupuesto",
        "description": "Aprueba un plan de tratamiento fijando el precio final. Solo CEO puede aprobar presupuestos.",
        "parameters": {
            "type": "object",
            "properties": {
                "plan_id": {
                    "type": "string",
                    "description": "ID UUID del plan a aprobar",
                },
                "patient_id": {
                    "type": "integer",
                    "description": "ID del paciente (opcional si se pasa plan_id)",
                },
                "patient_name": {
                    "type": "string",
                    "description": "Nombre del paciente para buscar (opcional)",
                },
                "approved_total": {
                    "type": "number",
                    "description": "Monto total aprobado (puede diferir del estimado)",
                },
                "notes": {
                    "type": "string",
                    "description": "Notas adicionales de la aprobación",
                },
            },
            "required": ["approved_total"],
        },
    },
]


# =============================================================================
# HELPERS
# =============================================================================


def _role_error(tool_name: str, allowed: List[str]) -> str:
    roles_str = ", ".join(allowed)
    return (
        f"No tenes permiso para usar '{tool_name}'. Solo disponible para: {roles_str}."
    )


def _parse_date_str(d: Any) -> date:
    """Parse string to date object. Handles YYYY-MM-DD and other formats."""
    if isinstance(d, date):
        return d
    if isinstance(d, datetime):
        return d.date()
    s = str(d).strip()
    try:
        return datetime.strptime(s[:10], "%Y-%m-%d").date()
    except ValueError:
        try:
            return datetime.strptime(s[:10], "%d/%m/%Y").date()
        except ValueError:
            return date.today()


def _parse_datetime_str(d: Any) -> datetime:
    """Parse string to datetime object. Handles various formats."""
    if isinstance(d, datetime):
        return d
    if isinstance(d, date):
        return datetime.combine(d, datetime.min.time())
    s = str(d).strip()
    for fmt in [
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%dT%H:%M",
        "%Y-%m-%d",
    ]:
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    return datetime.now()


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


def _normalize_for_search(text: str) -> str:
    """Remove accents and normalize for fuzzy search."""
    import unicodedata

    nfkd = unicodedata.normalize("NFKD", text.lower())
    return "".join(c for c in nfkd if not unicodedata.combining(c))


async def _buscar_paciente(args: Dict, tenant_id: int) -> str:
    q = args.get("query", "").strip()
    if not q:
        return "Necesito un nombre, apellido, DNI o telefono para buscar."

    _TRANSLATE = (
        "TRANSLATE(LOWER({field}), 'áéíóúüñàèìòùâêîôûäëïöü', 'aeiounaeiouaeiouaeiou')"
    )
    like_q = f"%{q}%"
    words = q.split()

    # ── NIVEL 1: Búsqueda exacta (nombre completo, campos individuales, sin acentos) ──
    rows = await db.pool.fetch(
        f"""
        SELECT id, first_name, last_name, phone_number, dni,
               insurance_provider, insurance_id, status
        FROM patients
        WHERE tenant_id = $1
          AND (
            (first_name || ' ' || COALESCE(last_name, '')) ILIKE $2
            OR first_name ILIKE $2 OR last_name ILIKE $2
            OR dni ILIKE $2 OR phone_number ILIKE $2
            OR REGEXP_REPLACE(phone_number, '[^0-9]', '', 'g') LIKE REGEXP_REPLACE($2, '[^0-9]', '', 'g')
            OR {_TRANSLATE.format(field="first_name")} LIKE {_TRANSLATE.format(field="$2")}
            OR {_TRANSLATE.format(field="last_name")} LIKE {_TRANSLATE.format(field="$2")}
            OR {_TRANSLATE.format(field="first_name || ' ' || COALESCE(last_name, '')")} LIKE {_TRANSLATE.format(field="$2")}
          )
        ORDER BY
          CASE WHEN LOWER(first_name) = LOWER($3) OR LOWER(last_name) = LOWER($3) THEN 0
               WHEN LOWER(first_name || ' ' || COALESCE(last_name, '')) = LOWER($3) THEN 0
               ELSE 1 END,
          last_name, first_name
        LIMIT 5
        """,
        tenant_id,
        like_q,
        q,
    )
    if rows:
        return _format_patient_results(rows, q)

    # ── NIVEL 2: Multi-palabra con AND (cada palabra en algún campo) ──
    if len(words) > 1:
        conditions = []
        params: list = [tenant_id]
        for i, word in enumerate(words):
            idx = i + 2
            params.append(f"%{word}%")
            conditions.append(
                f"((first_name || ' ' || COALESCE(last_name, '')) ILIKE ${idx} "
                f"OR {_TRANSLATE.format(field='first_name || chr(32) || COALESCE(last_name, chr(32))')} LIKE {_TRANSLATE.format(field=f'${idx}')})"
            )
        where_clause = " AND ".join(conditions)
        rows = await db.pool.fetch(
            f"""
            SELECT id, first_name, last_name, phone_number, dni,
                   insurance_provider, insurance_id, status
            FROM patients
            WHERE tenant_id = $1 AND ({where_clause})
            ORDER BY last_name, first_name LIMIT 5
            """,
            *params,
        )
        if rows:
            return _format_patient_results(rows, q)

    # ── NIVEL 3: Multi-palabra con OR (cualquier palabra matchea algo) ──
    if len(words) > 1:
        or_conditions = []
        params2: list = [tenant_id]
        for i, word in enumerate(words):
            idx = i + 2
            params2.append(f"%{word}%")
            or_conditions.append(f"(first_name ILIKE ${idx} OR last_name ILIKE ${idx})")
        or_clause = " OR ".join(or_conditions)
        rows = await db.pool.fetch(
            f"""
            SELECT id, first_name, last_name, phone_number, dni,
                   insurance_provider, insurance_id, status
            FROM patients
            WHERE tenant_id = $1 AND ({or_clause})
            ORDER BY last_name, first_name LIMIT 5
            """,
            *params2,
        )
        if rows:
            return _format_patient_results(rows, q, partial=True)

    # ── NIVEL 4: Prefijo (primeros 3+ caracteres de cada palabra) ──
    prefix_conditions = []
    params3: list = [tenant_id]
    for i, word in enumerate(words):
        prefix = word[:3] if len(word) >= 3 else word
        idx = i + 2
        params3.append(f"{prefix}%")
        prefix_conditions.append(
            f"(LOWER(first_name) LIKE LOWER(${idx}) OR LOWER(last_name) LIKE LOWER(${idx}))"
        )
    prefix_clause = " OR ".join(prefix_conditions)
    rows = await db.pool.fetch(
        f"""
        SELECT id, first_name, last_name, phone_number, dni,
               insurance_provider, insurance_id, status
        FROM patients
        WHERE tenant_id = $1 AND ({prefix_clause})
        ORDER BY last_name, first_name LIMIT 5
        """,
        *params3,
    )
    if rows:
        return _format_patient_results(rows, q, partial=True)

    # ── NIVEL 5: Fonético (letras duplicadas removidas, consonantes similares) ──
    # "Gamara" → "Gamarra", "Lukas" → "Lucas", "Gonzales" → "González"
    normalized_q = _normalize_for_search(q)
    # Remove doubled consonants: "gamarra" → "gamara", "gonzalez" → "gonzalez"
    import re as _re

    simplified_q = _re.sub(r"(.)\1+", r"\1", normalized_q)
    if simplified_q != normalized_q or len(simplified_q) >= 3:
        rows = await db.pool.fetch(
            """
            SELECT id, first_name, last_name, phone_number, dni,
                   insurance_provider, insurance_id, status
            FROM patients
            WHERE tenant_id = $1
              AND (
                REGEXP_REPLACE(TRANSLATE(LOWER(first_name), 'áéíóúüñàèìòùâêîôûäëïöü', 'aeiounaeiouaeiouaeiou'), '(.)\\1+', '\\1', 'g') LIKE '%' || $2 || '%'
                OR REGEXP_REPLACE(TRANSLATE(LOWER(last_name), 'áéíóúüñàèìòùâêîôûäëïöü', 'aeiounaeiouaeiouaeiou'), '(.)\\1+', '\\1', 'g') LIKE '%' || $2 || '%'
                OR REGEXP_REPLACE(TRANSLATE(LOWER(first_name || ' ' || COALESCE(last_name, '')), 'áéíóúüñàèìòùâêîôûäëïöü', 'aeiounaeiouaeiouaeiou'), '(.)\\1+', '\\1', 'g') LIKE '%' || $2 || '%'
              )
            ORDER BY last_name, first_name LIMIT 5
            """,
            tenant_id,
            simplified_q,
        )
        if rows:
            return _format_patient_results(rows, q, partial=True)

    # ── NIVEL 6: ÚLTIMO RECURSO — mostrar pacientes recientes como sugerencia ──
    recent = await db.pool.fetch(
        """
        SELECT id, first_name, last_name, phone_number, dni,
               insurance_provider, insurance_id, status
        FROM patients
        WHERE tenant_id = $1 AND status != 'archived'
        ORDER BY updated_at DESC NULLS LAST, created_at DESC
        LIMIT 8
        """,
        tenant_id,
    )
    if recent:
        lines = [f"No encontré '{q}'. Estos son los pacientes mas recientes:"]
        for r in recent:
            name = f"{r['first_name'] or ''} {r['last_name'] or ''}".strip()
            lines.append(
                f"• ID {r['id']}: {name} | Tel: {r['phone_number'] or 'sin tel'}"
            )
        lines.append("\nDecime cuál de estos es o dame otro dato para buscar.")
        return "\n".join(lines)

    return f"No hay pacientes registrados en esta clinica."


def _format_patient_results(rows, query: str, partial: bool = False) -> str:
    """Format patient search results."""
    prefix = f"Encontré {len(rows)} paciente(s)"
    if partial:
        prefix += f" (coincidencia parcial con '{query}')"
    prefix += ":"
    lines = [prefix]
    for r in rows:
        name = f"{r['first_name'] or ''} {r['last_name'] or ''}".strip()
        ins = f" — OS: {r['insurance_provider']}" if r.get("insurance_provider") else ""
        lines.append(
            f"• ID {r['id']}: {name} | Tel: {r['phone_number'] or 'sin tel'} | DNI: {r['dni'] or 'sin DNI'}{ins}"
        )
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
        int(pid),
        tenant_id,
    )
    if not row:
        return "No encontre a ese paciente."

    name = f"{row['first_name'] or ''} {row['last_name'] or ''}".strip()
    parts = [f"Paciente: {name} (ID {row['id']})"]
    parts.append(
        f"Tel: {row['phone_number'] or 'sin tel'} | DNI: {row['dni'] or 'sin DNI'}"
    )
    if row["email"]:
        parts.append(f"Email: {row['email']}")
    if row["insurance_provider"]:
        valid = (
            f" (valida hasta {_fmt_date(row['insurance_valid_until'])})"
            if row["insurance_valid_until"]
            else ""
        )
        parts.append(
            f"Obra social: {row['insurance_provider']} — Afiliado: {row['insurance_id'] or 'sin numero'}{valid}"
        )
    if row["birth_date"]:
        parts.append(f"Nacimiento: {_fmt_date(row['birth_date'])}")
    if row["notes"]:
        parts.append(f"Notas: {row['notes']}")
    parts.append(
        f"Estado: {row['status']} | Ultima visita: {_fmt_date(row['last_visit'])}"
    )

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
        int(pid),
        tenant_id,
    )
    if appts:
        parts.append("Proximos turnos:")
        for a in appts:
            parts.append(
                f"  • {_fmt_date(a['appointment_datetime'])} — {a['appointment_type']} ({a['status']})"
            )
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
        tenant_id,
        phone,
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
    await _nova_emit(
        "PATIENT_UPDATED",
        {"patient_id": row["id"], "tenant_id": tenant_id, "action": "created"},
    )
    return f"Paciente {first_name} {last_name} registrado con ID {row['id']}."


async def _actualizar_paciente(args: Dict, tenant_id: int) -> str:
    pid = args.get("patient_id")
    field = args.get("field")
    value = args.get("value")

    if not pid or not field or value is None:
        return "Necesito patient_id, field y value."

    allowed_fields = {
        "phone_number",
        "email",
        "insurance_provider",
        "insurance_id",
        "notes",
        "preferred_schedule",
    }
    if field not in allowed_fields:
        return f"Campo '{field}' no permitido. Campos validos: {', '.join(sorted(allowed_fields))}."

    result = await db.pool.execute(
        f"UPDATE patients SET {field} = $1, updated_at = NOW() WHERE id = $2 AND tenant_id = $3",
        value,
        int(pid),
        tenant_id,
    )
    if result == "UPDATE 0":
        return "No encontre a ese paciente."
    await _nova_emit(
        "PATIENT_UPDATED", {"patient_id": int(pid), "tenant_id": tenant_id}
    )
    return f"Paciente {pid}: campo '{field}' actualizado."


async def _actualizar_email_paciente(args: Dict, tenant_id: int) -> str:
    """Actualiza el email de un paciente."""
    import re

    pid = args.get("patient_id")
    email = args.get("email")

    if not pid or not email:
        return "Necesito patient_id y email."

    # Validar formato de email
    email_pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
    if not re.match(email_pattern, email):
        return "El formato del email no es valido."

    result = await db.pool.execute(
        "UPDATE patients SET email = $1, updated_at = NOW() WHERE id = $2 AND tenant_id = $3",
        email,
        int(pid),
        tenant_id,
    )
    if result == "UPDATE 0":
        return "No encontre a ese paciente."
    await _nova_emit(
        "PATIENT_UPDATED", {"patient_id": int(pid), "tenant_id": tenant_id}
    )
    return f"Email actualizado para paciente {pid}: {email}"


async def _ver_presupuesto_paciente(args: Dict, tenant_id: int) -> str:
    """
    Muestra el/los presupuesto(s) de tratamiento de un paciente:
    items, precios, pagos y saldo pendiente.
    """

    patient_id = args.get("patient_id")
    patient_name = args.get("patient_name")
    plan_id = args.get("plan_id")
    include_completed = args.get("include_completed", False)

    # 1. Buscar paciente
    if patient_id:
        patient = await db.pool.fetchrow(
            "SELECT id, first_name, last_name FROM patients WHERE id = $1 AND tenant_id = $2",
            int(patient_id),
            tenant_id,
        )
        if not patient:
            return f"No encontré un paciente con ID {patient_id}."
    elif patient_name:
        patients = await db.pool.fetch(
            "SELECT id, first_name, last_name FROM patients WHERE tenant_id = $1 AND LOWER(first_name || ' ' || COALESCE(last_name, '')) LIKE $2",
            tenant_id,
            f"%{patient_name.lower()}%",
        )
        if len(patients) > 1:
            names = ", ".join(
                [f"{p['first_name']} {p['last_name']}" for p in patients[:5]]
            )
            return f"Hay múltiples pacientes con ese nombre: {names}. Por favor usá el patient_id."
        if not patients:
            return f"No encontré ningún paciente con nombre '{patient_name}'."
        patient = patients[0]
        patient_id = patient["id"]
    else:
        return "Necesito patient_id o patient_name para buscar el presupuesto."

    # 2. Obtener planes del paciente
    status_filter = "" if include_completed else "AND tp.status != 'completed'"
    plans = await db.pool.fetch(
        f"""
        SELECT tp.id, tp.name, tp.status, tp.estimated_total, tp.approved_total, tp.created_at,
               prof.first_name as professional_name
        FROM treatment_plans tp
        LEFT JOIN professionals prof ON tp.professional_id = prof.id
        WHERE tp.patient_id = $1 AND tp.tenant_id = $2 {status_filter}
        ORDER BY tp.created_at DESC
        """,
        patient["id"],
        tenant_id,
    )

    if not plans:
        return f"El paciente {patient['first_name']} {patient['last_name']} no tiene presupuestos activos."

    # 3. Si hay plan_id específico, obtener detalle
    if plan_id:
        plan = next((p for p in plans if str(p["id"]) == plan_id), None)
        if not plan:
            return f"No encontré el plan con ID {plan_id} para este paciente."
        return await _format_plan_detail(plan, tenant_id)

    # 4. Mostrar lista de planes o detalle según cantidad
    if len(plans) == 1:
        return await _format_plan_detail(plans[0], tenant_id)

    # Múltiples planes - mostrar lista
    lines = [f"Presupuestos de {patient['first_name']} {patient['last_name']}:"]
    for p in plans:
        status_emoji = {
            "draft": "📝",
            "approved": "✅",
            "in_progress": "⏳",
            "completed": "🎉",
            "cancelled": "❌",
        }.get(p["status"], "❓")
        est = float(p["estimated_total"] or 0)
        app = float(p["approved_total"] or 0)
        total = app if app > 0 else est
        lines.append(
            f"{status_emoji} *{p['name']}* — ${total:,.0f} ({p['status']}) [ID: {p['id']}]"
        )
        if p["professional_name"]:
            lines.append(f"   Profesional: {p['professional_name']}")

    lines.append("\nPara ver el detalle de un plan específico, usá plan_id.")
    return "\n".join(lines)


async def _format_plan_detail(plan, tenant_id: int) -> str:
    """Formatea el detalle de un plan de tratamiento."""
    from db import db

    plan_id = str(plan["id"])

    # Obtener items
    items = await db.pool.fetch(
        """
        SELECT tpi.id, tpi.treatment_type_code, tpi.custom_description,
               tpi.estimated_price, tpi.approved_price, tpi.status,
               tt.name as treatment_name
        FROM treatment_plan_items tpi
        LEFT JOIN treatment_types tt ON tpi.treatment_type_code = tt.code AND tpi.tenant_id = tt.tenant_id
        WHERE tpi.plan_id = $1 AND tpi.tenant_id = $2 AND tpi.status != 'cancelled'
        ORDER BY tpi.sort_order
        """,
        plan_id,
        tenant_id,
    )

    # Obtener pagos
    payments = await db.pool.fetch(
        """
        SELECT amount, payment_method, payment_date, notes
        FROM treatment_plan_payments
        WHERE plan_id = $1 AND tenant_id = $2
        ORDER BY payment_date DESC
        """,
        plan_id,
        tenant_id,
    )

    # Calcular totales
    estimated_total = float(plan["estimated_total"] or 0)
    approved_total = float(plan["approved_total"] or 0)
    total = approved_total if approved_total > 0 else estimated_total

    paid_total = sum(float(p["amount"]) for p in payments)
    pending = max(total - paid_total, 0)

    status_emoji = {
        "draft": "📝",
        "approved": "✅",
        "in_progress": "⏳",
        "completed": "🎉",
        "cancelled": "❌",
    }.get(plan["status"], "❓")

    lines = [
        f"📋 *{plan['name']}* {status_emoji}",
        f"Estado: {plan['status']}",
        f"",
        f"💰 FINANCIERO:",
        f"  Total estimado: ${estimated_total:,.0f}",
        f"  Total aprobado: ${approved_total:,.0f}"
        if approved_total > 0
        else f"  Total: ${total:,.0f}",
        f"  Pagado: ${paid_total:,.0f}",
        f"  Pendiente: ${pending:,.0f}",
        f"  Progreso: {int((paid_total / total) * 100)}%"
        if total > 0
        else "  Progreso: 0%",
        f"",
    ]

    if items:
        lines.append("📦 TRATAMIENTOS:")
        for item in items:
            name = (
                item["custom_description"]
                or item["treatment_name"]
                or item["treatment_type_code"]
                or "Tratamiento"
            )
            est = float(item["estimated_price"] or 0)
            app = item["approved_price"]
            price = f"${app:,.0f}" if app else f"${est:,.0f}"
            status_icon = {"pending": "⏳", "in_progress": "🔄", "completed": "✅"}.get(
                item["status"], "❓"
            )
            lines.append(f"  • {name} — {price} [{status_icon} {item['status']}]")
    else:
        lines.append("📦 Sin tratamientos registrados.")

    if payments:
        lines.append(f"\n💳 PAGOS ({len(payments)}):")
        for p in payments:
            method_icon = {"cash": "💵", "transfer": "🏦", "card": "💳"}.get(
                p["payment_method"], "💰"
            )
            lines.append(
                f"  {method_icon} ${p['amount']:,.0f} ({p['payment_method']}) — {p['payment_date']}"
            )
    else:
        lines.append("\n💳 Sin pagos registrados.")

    return "\n".join(lines)


async def _aprobar_presupuesto(
    args: Dict, tenant_id: int, user_role: str, user_id: str
) -> str:
    """
    Aprueba un plan de tratamiento fijando el precio final.
    Solo CEO puede aprobar presupuestos.
    """

    # Validar que es CEO
    if user_role != "ceo":
        return _role_error("aprobar_presupuesto", ["ceo"])

    plan_id = args.get("plan_id")
    patient_id = args.get("patient_id")
    patient_name = args.get("patient_name")
    approved_total = args.get("approved_total")
    notes = args.get("notes", "")

    if not approved_total:
        return "Necesito el approved_total (monto aprobado)."

    # Buscar plan
    if plan_id:
        plan = await db.pool.fetchrow(
            "SELECT id, name, status FROM treatment_plans WHERE id = $1 AND tenant_id = $2",
            plan_id,
            tenant_id,
        )
        if not plan:
            return f"No encontré el plan con ID {plan_id}."
    elif patient_id and patient_name:
        # Buscar por paciente y nombre
        plan = await db.pool.fetchrow(
            """
            SELECT tp.id, tp.name, tp.status
            FROM treatment_plans tp
            JOIN patients p ON tp.patient_id = p.id
            WHERE p.id = $1 AND p.tenant_id = $2 AND LOWER(tp.name) LIKE $3
            """,
            int(patient_id),
            tenant_id,
            f"%{patient_name.lower()}%",
        )
        if not plan:
            return f"No encontré un plan '{patient_name}' para ese paciente."
    elif patient_name and not patient_id:
        # FIX H9 — solo patient_name: fuzzy search en pacientes, luego en planes draft
        patients = await db.pool.fetch(
            "SELECT id, first_name, last_name FROM patients WHERE tenant_id = $1 AND LOWER(first_name || ' ' || COALESCE(last_name, '')) LIKE $2",
            tenant_id,
            f"%{patient_name.lower()}%",
        )
        if not patients:
            return f"No hay presupuestos en borrador para ese paciente ('{patient_name}' no encontrado)."

        patient_ids = [p["id"] for p in patients]
        draft_plans = await db.pool.fetch(
            """
            SELECT tp.id, tp.name, tp.status,
                   p.first_name || ' ' || COALESCE(p.last_name, '') AS patient_full_name
            FROM treatment_plans tp
            JOIN patients p ON tp.patient_id = p.id
            WHERE tp.tenant_id = $1 AND tp.status = 'draft' AND tp.patient_id = ANY($2::int[])
            ORDER BY tp.created_at DESC
            """,
            tenant_id,
            patient_ids,
        )
        if not draft_plans:
            return f"No hay presupuestos en borrador para ese paciente."
        if len(draft_plans) > 1:
            lines = [f"Encontré {len(draft_plans)} presupuestos en borrador. Especificá cuál querés aprobar usando plan_id:"]
            for dp in draft_plans:
                lines.append(f"  • *{dp['name']}* — {dp['patient_full_name']} [ID: {dp['id']}]")
            return "\n".join(lines)
        plan = draft_plans[0]
        # Ensure plan_id is set for the UPDATE below
        plan_id = str(plan["id"])
        if not patient_id:
            # Recover patient_id for the emit
            patient_id = await db.pool.fetchval(
                "SELECT patient_id FROM treatment_plans WHERE id = $1 AND tenant_id = $2",
                plan["id"], tenant_id
            )
    else:
        return "Necesito plan_id, o patient_name (solo nombre), o (patient_id + patient_name)."

    # Validar estado
    if plan["status"] != "draft":
        return f"El plan '{plan['name']}' no está en estado 'draft' (actual: {plan['status']}). Solo se pueden aprobar planes en borrador."

    # Actualizar plan
    await db.pool.execute(
        """
        UPDATE treatment_plans
        SET status = 'approved', approved_total = $1, approved_by = $2, approved_at = NOW(), notes = COALESCE(notes, '') || $3, updated_at = NOW()
        WHERE id = $4 AND tenant_id = $5
        """,
        float(approved_total),
        user_id,
        f"\n[Aprobado: {notes}]" if notes else "",
        plan_id,
        tenant_id,
    )

    await _nova_emit(
        "TREATMENT_PLAN_UPDATED",
        {"plan_id": plan_id, "tenant_id": tenant_id, "patient_id": patient_id},
    )

    return f"✅ Presupuesto aprobado: *{plan['name']}*\nMonto aprobado: ${float(approved_total):,.0f}\nEl plan ahora está activo y se pueden registrar pagos."


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
        int(pid),
        tenant_id,
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


async def _registrar_nota_clinica(
    args: Dict, tenant_id: int, user_role: str, user_id: str
) -> str:
    if user_role != "professional":
        return _role_error("registrar_nota_clinica", ["professional"])

    pid = args.get("patient_id")
    diagnosis = args.get("diagnosis", "").strip()
    if not pid or not diagnosis:
        return "Necesito patient_id y diagnosis."

    # Verify patient exists
    exists = await db.pool.fetchval(
        "SELECT id FROM patients WHERE id = $1 AND tenant_id = $2",
        int(pid),
        tenant_id,
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
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8::jsonb)
        """,
        record_id,
        tenant_id,
        int(pid),
        prof_id,
        _today(),
        diagnosis,
        args.get("treatment_notes"),
        json.dumps(odontogram_data) if odontogram_data else "{}",
    )

    tooth_msg = ""
    if tooth_number:
        tooth_msg = f" Pieza {tooth_number}: {tooth_status or 'registrada'}."
    await _nova_emit(
        "PATIENT_UPDATED", {"patient_id": int(pid), "tenant_id": tenant_id}
    )
    return f"Nota clinica registrada para paciente {pid}.{tooth_msg}"


# --- B. Turnos ---


async def _ver_agenda(args: Dict, tenant_id: int, user_role: str, user_id: str) -> str:
    target_date = _parse_date_str(args.get("date", str(_today())))
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
        time_str = (
            r["appointment_datetime"].strftime("%H:%M")
            if r["appointment_datetime"]
            else "?"
        )
        dur = f"{r['duration_minutes']}min" if r["duration_minutes"] else ""
        status_icon = {
            "scheduled": "⏳",
            "confirmed": "✅",
            "completed": "✔",
            "cancelled": "❌",
        }.get(r["status"], "•")
        prof = (
            f" — Dr. {r['professional_name']}"
            if r["professional_name"] and not prof_id
            else ""
        )
        lines.append(
            f"{status_icon} {time_str} ({dur}) {r['patient_name']} — {r['appointment_type']} [{r['status']}]{prof}"
        )
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
        prof_id,
        tenant_id,
        _today(),
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
    target_date = _parse_date_str(args.get("date", str(_today())))
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

    # target_date is already a date object from _parse_date_str()
    dt = target_date if isinstance(target_date, date) else _parse_date_str(target_date)

    day_names = [
        "monday",
        "tuesday",
        "wednesday",
        "thursday",
        "friday",
        "saturday",
        "sunday",
    ]
    day_key = day_names[dt.weekday()]

    day_config = working_hours.get(day_key, {}) if working_hours else {}
    if not day_config or not day_config.get("enabled", False):
        return f"La clinica esta cerrada el {_fmt_date(dt)}."

    # Verificar feriado
    from services.holiday_service import is_holiday as check_is_holiday

    _is_hol, _hol_name, _custom_hours = await check_is_holiday(db.pool, tenant_id, dt)
    if _is_hol and _custom_hours:
        # Feriado con atención — usar horario especial
        start_hour = _custom_hours["start"]
        end_hour = _custom_hours["end"]
    elif _is_hol:
        return f"El {_fmt_date(dt)} es feriado ({_hol_name}). La clinica no atiende."
    else:
        start_hour = day_config.get("start", "09:00")
        end_hour = day_config.get("end", "18:00")

    # Get duration for treatment
    duration = 30  # default
    if treatment_type:
        tt_row = await db.pool.fetchval(
            "SELECT default_duration_minutes FROM treatment_types WHERE tenant_id = $1 AND code = $2 AND is_active = true",
            tenant_id,
            treatment_type,
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
            occ_start_naive = (
                occ_start.replace(tzinfo=None) if occ_start.tzinfo else occ_start
            )
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
    target_date = str(args.get("date", ""))
    time_str = str(args.get("time", ""))
    treatment_type = args.get("treatment_type")

    if not all([pid, target_date, time_str, treatment_type]):
        return "Necesito patient_id, date (YYYY-MM-DD), time (HH:MM) y treatment_type."

    # Verify patient
    patient = await db.pool.fetchrow(
        "SELECT first_name, last_name FROM patients WHERE id = $1 AND tenant_id = $2",
        int(pid),
        tenant_id,
    )
    if not patient:
        return "No encontre a ese paciente."

    # Get treatment duration
    tt_row = await db.pool.fetchrow(
        "SELECT default_duration_minutes, name FROM treatment_types WHERE tenant_id = $1 AND code = $2 AND is_active = true",
        tenant_id,
        treatment_type,
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

    # Verificar feriado
    from services.holiday_service import is_holiday as check_is_holiday

    _is_hol, _hol_name, _custom_hours = await check_is_holiday(
        db.pool, tenant_id, appt_dt.date()
    )
    if _is_hol and _custom_hours:
        # Feriado con atención — validar que el horario esté dentro del rango especial
        from datetime import time as time_type

        custom_start = time_type.fromisoformat(_custom_hours["start"])
        custom_end = time_type.fromisoformat(_custom_hours["end"])
        apt_time = appt_dt.time()
        if apt_time < custom_start or apt_time >= custom_end:
            return (
                f"No se puede agendar el {target_date}: es {_hol_name} con horario especial de "
                f"{_custom_hours['start']} a {_custom_hours['end']}. "
                f"Elegí un horario dentro de ese rango."
            )
        # Horario válido dentro del rango especial — continuar con el flujo normal
    elif _is_hol:
        return f"No se puede agendar el {target_date}: es feriado ({_hol_name}). Elegí otro día."

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

    await _nova_emit(
        "NEW_APPOINTMENT",
        {
            "patient_id": int(pid),
            "tenant_id": tenant_id,
            "appointment_id": str(appt_id),
        },
    )
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
        appt_uuid,
        tenant_id,
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
        reason,
        appt_uuid,
        tenant_id,
    )

    await _nova_emit(
        "APPOINTMENT_DELETED",
        {"appointment_id": str(appt_uuid), "tenant_id": tenant_id},
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
            tenant_id,
            uuids,
        )
        count = int(result.split()[-1]) if result else 0
        if count > 0:
            await _nova_emit(
                "APPOINTMENT_UPDATED",
                {"tenant_id": tenant_id, "action": "confirmed_batch"},
            )
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
            tenant_id,
            _today(),
        )
        count = int(result.split()[-1]) if result else 0
        if count == 0:
            return "No hay turnos pendientes de confirmar hoy."
        await _nova_emit(
            "APPOINTMENT_UPDATED",
            {"tenant_id": tenant_id, "action": "confirmed_all_today"},
        )
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
        lines.append(
            f"• {r['name']} ({r['code']}) — {r['default_duration_minutes']}min — {price}"
        )
    return "\n".join(lines)


async def _registrar_pago(args: Dict, tenant_id: int, user_role: str) -> str:
    """
    Registra un pago de un turno (appointment_id) o de un plan de tratamiento (plan_id).
    Solo para CEO y secretarias.
    """
    if user_role not in ("ceo", "secretary"):
        return _role_error("registrar_pago", ["ceo", "secretary"])

    plan_id = args.get("plan_id")
    # Si se proporciona plan_id, delegar a la función específica de plan
    if plan_id:
        return await _registrar_pago_plan(args, tenant_id, user_role)

    # Lógica original para pagos de turnos
    appt_id = args.get("appointment_id")
    amount = args.get("amount")
    method = args.get("method")

    if not appt_id or amount is None or not method:
        return "Necesito appointment_id (o plan_id), amount y method."

    try:
        appt_uuid = uuid.UUID(appt_id)
    except ValueError:
        return "ID de turno inválido."

    # Verify appointment exists
    appt = await db.pool.fetchrow(
        """
        SELECT a.id, a.appointment_type,
               p.first_name || ' ' || COALESCE(p.last_name, '') AS patient_name
        FROM appointments a
        JOIN patients p ON p.id = a.patient_id
        WHERE a.id = $1 AND a.tenant_id = $2
        """,
        appt_uuid,
        tenant_id,
    )
    if not appt:
        return "No encontré ese turno."

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

    method_labels = {
        "cash": "efectivo",
        "card": "tarjeta",
        "transfer": "transferencia",
        "insurance": "obra social",
    }
    await _nova_emit(
        "PAYMENT_CONFIRMED", {"appointment_id": str(appt_uuid), "tenant_id": tenant_id}
    )
    return f"Pago de {_fmt_money(amount)} registrado para {appt['patient_name']} ({method_labels.get(method, method)})."


async def _registrar_pago_plan(args: Dict, tenant_id: int, user_role: str) -> str:
    """
    Registra un pago en un plan de tratamiento.
    Solo para CEO y secretarias.
    """
    if user_role not in ("ceo", "secretary"):
        return _role_error("registrar_pago_plan", ["ceo", "secretary"])

    plan_id = args.get("plan_id")
    amount = args.get("amount")
    method = args.get("method")
    notes = args.get("notes", "")
    payment_date = args.get("payment_date")

    if not plan_id or amount is None or not method:
        return "Necesito plan_id, amount y method."

    try:
        plan_uuid = uuid.UUID(plan_id)
    except ValueError:
        return "ID de plan inválido."

    # Verificar que el plan existe y pertenece al tenant
    plan = await db.pool.fetchrow(
        """
        SELECT id, name, patient_id, approved_total,
               (SELECT first_name || ' ' || COALESCE(last_name, '')
                FROM patients WHERE id = tp.patient_id) AS patient_name
        FROM treatment_plans tp
        WHERE id = $1 AND tenant_id = $2
        """,
        plan_uuid,
        tenant_id,
    )
    if not plan:
        return "No encontré ese plan de tratamiento."

    # Insertar pago
    payment_id = uuid.uuid4()
    await db.pool.execute(
        """
        INSERT INTO treatment_plan_payments
            (id, plan_id, amount, payment_method, payment_date,
             notes, recorded_by_user_id, tenant_id)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
        """,
        payment_id,
        plan_uuid,
        Decimal(str(amount)),
        method,
        payment_date if payment_date else _today().isoformat(),
        notes,
        args.get("recorded_by_user_id"),  # Podría ser None, el sistema lo maneja
        tenant_id,
    )

    method_labels = {
        "cash": "efectivo",
        "card": "tarjeta",
        "transfer": "transferencia",
        "insurance": "obra social",
    }

    # FIX C6 — Sync to accounting_transactions
    try:
        await db.pool.execute(
            """INSERT INTO accounting_transactions
               (tenant_id, patient_id, transaction_type, transaction_date, amount,
                payment_method, description, status)
               VALUES ($1, $2, 'payment', NOW(), $3, $4, $5, 'completed')""",
            tenant_id,
            plan["patient_id"],
            Decimal(str(amount)),
            method,
            f"Pago plan '{plan['name']}' - {method_labels.get(method, method)}"
        )
    except Exception as acc_err:
        logger.warning(f"accounting_transaction sync failed (non-fatal): {acc_err}")

    # FIX C7 — Auto-complete plan if fully paid
    try:
        total_paid = await db.pool.fetchval(
            "SELECT COALESCE(SUM(amount), 0) FROM treatment_plan_payments WHERE plan_id = $1 AND tenant_id = $2",
            plan_uuid, tenant_id
        )
        if float(total_paid) >= float(plan["approved_total"]):
            await db.pool.execute(
                "UPDATE treatment_plans SET status = 'completed', updated_at = NOW() WHERE id = $1 AND tenant_id = $2",
                plan_uuid, tenant_id
            )
            logger.info(f"Plan {plan_uuid} auto-completed (total_paid={total_paid} >= approved={plan['approved_total']})")
    except Exception as complete_err:
        logger.warning(f"Auto-complete check failed (non-fatal): {complete_err}")

    # Emitir evento para actualizar frontend
    await _nova_emit(
        "BILLING_UPDATED",
        {
            "plan_id": str(plan_uuid),
            "patient_id": plan["patient_id"],
            "tenant_id": tenant_id,
        },
    )
    return f"Pago de {_fmt_money(amount)} registrado en el plan '{plan['name']}' para {plan['patient_name']} ({method_labels.get(method, method)})."


async def _facturacion_pendiente(tenant_id: int) -> str:
    # Turnos con facturación pendiente (excluye turnos vinculados a planes)
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
          AND a.plan_item_id IS NULL
        ORDER BY a.appointment_datetime DESC
        LIMIT 20
        """,
        tenant_id,
    )

    # Planes con saldo pendiente
    plans = await db.pool.fetch(
        """
        SELECT tp.id, tp.name, tp.approved_total,
               COALESCE(payments.total_paid, 0) as total_paid,
               pat.first_name || ' ' || COALESCE(pat.last_name, '') AS patient_name
        FROM treatment_plans tp
        JOIN patients pat ON tp.patient_id = pat.id AND pat.tenant_id = tp.tenant_id
        LEFT JOIN (
            SELECT plan_id, SUM(amount) as total_paid
            FROM treatment_plan_payments
            WHERE tenant_id = $1
            GROUP BY plan_id
        ) payments ON tp.id = payments.plan_id
        WHERE tp.tenant_id = $1
          AND tp.status IN ('approved', 'in_progress')
          AND tp.approved_total IS NOT NULL
          AND (payments.total_paid IS NULL OR payments.total_paid < tp.approved_total)
        ORDER BY tp.approved_total - COALESCE(payments.total_paid, 0) DESC
        LIMIT 20
        """,
        tenant_id,
    )

    if not rows and not plans:
        return "No hay facturacion pendiente. Todo al dia."

    lines = []
    if rows:
        lines.append(f"Facturacion pendiente ({len(rows)} turnos):")
        for r in rows:
            dt = _fmt_date(r["appointment_datetime"])
            price = _fmt_money(r["base_price"]) if r["base_price"] else "sin precio"
            lines.append(
                f"• {r['patient_name']} — {r['appointment_type']} ({dt}) — {price}"
            )
    if plans:
        if lines:
            lines.append("")  # separator
        lines.append(f"Planes con saldo pendiente ({len(plans)} planes):")
        for p in plans:
            pending = float(p["approved_total"]) - float(p["total_paid"])
            lines.append(
                f"• {p['patient_name']} — {p['name']} — Pendiente: {_fmt_money(pending)} (aprobado: {_fmt_money(p['approved_total'])}, pagado: {_fmt_money(p['total_paid'])})"
            )
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
            COALESCE(SUM(billing_amount) FILTER (WHERE payment_status = 'paid' AND plan_item_id IS NULL), 0) AS facturado
        FROM appointments
        WHERE tenant_id = $1
          AND appointment_datetime::date BETWEEN $2 AND $3
        """,
        tenant_id,
        week_start,
        week_end,
    )

    new_patients = await db.pool.fetchval(
        """
        SELECT COUNT(*) FROM patients
        WHERE tenant_id = $1 AND created_at::date BETWEEN $2 AND $3
        """,
        tenant_id,
        week_start,
        week_end,
    )

    total = stats["total_turnos"] or 0
    completed = stats["completados"] or 0
    cancelled = stats["cancelados"] or 0
    pending = stats["pendientes"] or 0
    revenue = stats["facturado"] or 0
    cancel_rate = (
        f"{(cancelled / (total + cancelled) * 100):.1f}%"
        if (total + cancelled) > 0
        else "0%"
    )

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
        int(prof_id),
        tenant_id,
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
        int(prof_id),
        tenant_id,
        since,
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
        tenant_id,
        f"%{question}%",
    )

    if existing:
        await db.pool.execute(
            "UPDATE clinic_faqs SET answer = $1, updated_at = NOW() WHERE id = $2 AND tenant_id = $3",
            answer,
            existing,
            tenant_id,
        )
        await _nova_emit("FAQ_UPDATED", {"tenant_id": tenant_id})
        return f"FAQ actualizada: '{question[:60]}...'"
    else:
        await db.pool.execute(
            "INSERT INTO clinic_faqs (tenant_id, question, answer) VALUES ($1, $2, $3)",
            tenant_id,
            question,
            answer,
        )
        await _nova_emit("FAQ_UPDATED", {"tenant_id": tenant_id})
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
    return json.dumps(
        {
            "type": "navigation",
            "action": "navigate",
            "page": page,
            "message": f"Abriendo {label}.",
        }
    )


async def _ir_a_paciente(args: Dict, tenant_id: int) -> str:
    pid = args.get("patient_id")
    if not pid:
        return "Necesito el ID del paciente."

    # Verify patient exists
    name = await db.pool.fetchval(
        "SELECT first_name || ' ' || COALESCE(last_name, '') FROM patients WHERE id = $1 AND tenant_id = $2",
        int(pid),
        tenant_id,
    )
    if not name:
        return "No encontre a ese paciente."

    return json.dumps(
        {
            "type": "navigation",
            "action": "open_patient",
            "patient_id": int(pid),
            "message": f"Abriendo ficha de {name.strip()}.",
        }
    )


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
        date_filter = (
            "appointment_datetime::date >= CURRENT_DATE - make_interval(days => $2)"
        )
        date_filter_created = (
            "created_at::date >= CURRENT_DATE - make_interval(days => $2)"
        )

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
    return json.dumps(
        {
            "type": "sede_switch",
            "tenant_id": int(row["id"]),
            "clinic_name": row["clinic_name"],
            "message": f"Cambiado a sede: {row['clinic_name']}. Las proximas consultas se refieren a esta sede.",
        }
    )


async def _onboarding_status(args: Dict, tenant_id: int, user_role: str) -> str:
    if user_role != "ceo":
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
    has_bank = bool(
        tenant_data and (tenant_data["bank_cbu"] or tenant_data["bank_alias"])
    )
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

    lines = [
        f"Onboarding de {target_name or 'sede actual'}: {completed}/{total} completado(s)"
    ]
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
        elif name == "actualizar_email_paciente":
            return await _actualizar_email_paciente(args, tenant_id)
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
        elif name == "registrar_pago_plan":
            return await _registrar_pago_plan(args, tenant_id, user_role)
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

        # H2. Odontograma
        elif name == "ver_odontograma":
            return await _ver_odontograma(args, tenant_id, user_role)
        elif name == "modificar_odontograma":
            return await _modificar_odontograma(args, tenant_id, user_role, user_id)

        # I. Consultas avanzadas
        elif name == "consultar_datos":
            return await _consultar_datos(args, tenant_id, user_role)
        elif name == "resumen_marketing":
            return await _resumen_marketing(args, tenant_id, user_role)
        elif name == "resumen_financiero":
            return await _resumen_financiero(args, tenant_id, user_role)

        # K. RAG / Knowledge Base
        elif name == "buscar_en_base_conocimiento":
            return await _buscar_en_base_conocimiento(args, tenant_id)

        # L. Obras sociales y derivación
        elif name == "consultar_obra_social":
            return await _consultar_obra_social(args, tenant_id)
        elif name == "ver_reglas_derivacion":
            return await _ver_reglas_derivacion(tenant_id)

        # M. Fichas digitales
        elif name == "generar_ficha_digital":
            return await _generar_ficha_digital(args, tenant_id)
        elif name == "enviar_ficha_digital":
            return await _enviar_ficha_digital(args, tenant_id)

        # O. Treatment Plans
        elif name == "ver_presupuesto_paciente":
            return await _ver_presupuesto_paciente(args, tenant_id)
        elif name == "aprobar_presupuesto":
            return await _aprobar_presupuesto(args, tenant_id, user_role, user_id)

        # J. CRUD genérico
        elif name == "obtener_registros":
            return await _obtener_registros(args, tenant_id, user_role)
        elif name == "actualizar_registro":
            return await _actualizar_registro(args, tenant_id, user_role)
        elif name == "crear_registro":
            return await _crear_registro(args, tenant_id, user_role)
        elif name == "contar_registros":
            return await _contar_registros(args, tenant_id)

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
        lines.append(
            f"• {r['first_name']} {r['last_name']} ({r.get('specialty') or 'general'}) [{status}]{price} (ID: {r['id']})"
        )
    return "\n".join(lines)


async def _reprogramar_turno(args: Dict, tenant_id: int) -> str:
    apt_id = args.get("appointment_id", "")
    new_date = args.get("new_date", "")
    new_time = args.get("new_time", "")
    if not apt_id or not new_date or not new_time:
        return "Necesito appointment_id, new_date (YYYY-MM-DD) y new_time (HH:MM)."
    try:
        appt_uuid = uuid.UUID(str(apt_id))
    except ValueError:
        return "ID de turno invalido."
    new_dt = _parse_datetime_str(f"{new_date} {new_time}")
    result = await db.pool.execute(
        "UPDATE appointments SET appointment_datetime = $1, status = 'scheduled', updated_at = NOW() WHERE id = $2 AND tenant_id = $3",
        new_dt,
        appt_uuid,
        tenant_id,
    )
    if result == "UPDATE 0":
        return "No encontre ese turno."
    await _nova_emit(
        "APPOINTMENT_UPDATED",
        {"appointment_id": str(appt_uuid), "tenant_id": tenant_id},
    )
    return f"Turno reprogramado para {_fmt_date(new_dt)}."


async def _ver_configuracion(tenant_id: int) -> str:
    row = await db.pool.fetchrow(
        """SELECT clinic_name, address, bot_phone_number, website, working_hours,
                  bank_cbu, bank_alias, bank_holder_name, consultation_price, owner_email,
                  calendar_provider, max_chairs
           FROM tenants WHERE id = $1""",
        tenant_id,
    )
    if not row:
        return "Clinica no encontrada."
    lines = [f"Configuracion de {row['clinic_name'] or 'Clinica'}:"]
    field_labels = {
        "clinic_name": "Nombre",
        "address": "Direccion",
        "bot_phone_number": "Telefono",
        "website": "Web",
        "bank_cbu": "CBU",
        "bank_alias": "Alias",
        "bank_holder_name": "Titular",
        "consultation_price": "Precio consulta",
        "owner_email": "Email",
        "calendar_provider": "Calendario",
        "max_chairs": "Sillones",
    }
    for field, label in field_labels.items():
        val = row[field]
        if val is not None and str(val).strip():
            lines.append(f"• {label}: {val}")
    # Working hours
    wh = row["working_hours"]
    if wh:
        if isinstance(wh, str):
            wh = json.loads(wh)
        if isinstance(wh, dict):
            day_names = {
                "monday": "Lun",
                "tuesday": "Mar",
                "wednesday": "Mie",
                "thursday": "Jue",
                "friday": "Vie",
                "saturday": "Sab",
                "sunday": "Dom",
            }
            wh_parts = []
            for day, abbr in day_names.items():
                dc = wh.get(day, {})
                if dc.get("enabled"):
                    wh_parts.append(
                        f"{abbr} {dc.get('start', '?')}-{dc.get('end', '?')}"
                    )
            if wh_parts:
                lines.append(f"• Horarios: {', '.join(wh_parts)}")
    return "\n".join(lines)


async def _actualizar_configuracion(args: Dict, tenant_id: int, user_role: str) -> str:
    if user_role != "ceo":
        return _role_error("actualizar_configuracion", ["ceo"])
    field = args.get("field", "")
    value = args.get("value", "")
    if not field:
        return "Necesito field y value."
    allowed = [
        "clinic_name",
        "address",
        "clinic_phone",
        "bank_cbu",
        "bank_alias",
        "bank_holder_name",
        "consultation_price",
        "website",
        "owner_email",
    ]
    if field not in allowed:
        return f"Campo '{field}' no permitido. Opciones: {', '.join(allowed)}"
    # Map clinic_phone to actual DB column
    db_field = "bot_phone_number" if field == "clinic_phone" else field
    # consultation_price needs numeric conversion
    if field == "consultation_price":
        try:
            value = Decimal(str(value))
        except Exception:
            return "El precio debe ser un numero valido."
    await db.pool.execute(
        f"UPDATE tenants SET {db_field} = $1, updated_at = NOW() WHERE id = $2",
        value,
        tenant_id,
    )
    await _nova_emit("CONFIGURATION_UPDATED", {"tenant_id": tenant_id})
    return f"Configuracion actualizada: {field} = {value}"


async def _crear_tratamiento(args: Dict, tenant_id: int, user_role: str) -> str:
    if user_role != "ceo":
        return _role_error("crear_tratamiento", ["ceo"])
    name = args.get("name", "")
    code = args.get("code", "")
    duration = int(args.get("duration_minutes", 30))
    price = Decimal(str(args.get("base_price", 0)))
    category = args.get("category", "prevention")
    if not name or not code:
        return "Necesito name y code."
    await db.pool.execute(
        """INSERT INTO treatment_types (tenant_id, name, code, default_duration_minutes, base_price, category, is_active, created_at)
           VALUES ($1, $2, $3, $4, $5, $6, true, NOW())""",
        tenant_id,
        name,
        code,
        duration,
        price,
        category,
    )
    await _nova_emit("TREATMENT_UPDATED", {"tenant_id": tenant_id})
    return f"Tratamiento '{name}' ({code}) creado — {duration} min, ${price}, categoria: {category}."


async def _editar_tratamiento(args: Dict, tenant_id: int, user_role: str) -> str:
    if user_role != "ceo":
        return _role_error("editar_tratamiento", ["ceo"])
    code = args.get("code", "")
    field = args.get("field", "")
    value = args.get("value", "")
    if not code or not field:
        return "Necesito code, field y value."
    field_map = {
        "name": "name",
        "duration_minutes": "default_duration_minutes",
        "base_price": "base_price",
        "category": "category",
        "is_active": "is_active",
    }
    db_field = field_map.get(field)
    if not db_field:
        return f"Campo '{field}' no valido. Opciones: {', '.join(field_map.keys())}"
    # Cast value to correct type for the DB column
    if field == "duration_minutes":
        try:
            value = int(value)
        except (ValueError, TypeError):
            return "La duración debe ser un número entero (minutos)."
    elif field == "base_price":
        try:
            value = Decimal(str(value))
        except Exception:
            return "El precio debe ser un número válido."
    elif field == "is_active":
        value = str(value).lower() in ("true", "1", "si", "yes", "activo")
    await db.pool.execute(
        f"UPDATE treatment_types SET {db_field} = $1 WHERE tenant_id = $2 AND code = $3",
        value,
        tenant_id,
        code,
    )
    await _nova_emit("TREATMENT_UPDATED", {"tenant_id": tenant_id})
    return f"Tratamiento '{code}' actualizado: {field} = {value}"


async def _ver_chats_recientes(args: Dict, tenant_id: int) -> str:
    limit = args.get("limit", 10)
    rows = await db.pool.fetch(
        """SELECT cc.external_user_id, cc.display_name, cc.channel, cc.updated_at,
                  cc.last_message_preview,
                  (SELECT content FROM chat_messages WHERE conversation_id = cc.id ORDER BY created_at DESC LIMIT 1) as last_msg
           FROM chat_conversations cc WHERE cc.tenant_id = $1 ORDER BY cc.updated_at DESC LIMIT $2""",
        tenant_id,
        int(limit),
    )
    if not rows:
        return "No hay conversaciones recientes."
    lines = [f"Conversaciones recientes ({len(rows)}):"]
    for r in rows:
        phone = r["external_user_id"] or "?"
        name = r["display_name"] or ""
        channel = r["channel"] or "whatsapp"
        last = (r["last_message_preview"] or r["last_msg"] or "")[:60]
        when = r["updated_at"].strftime("%d/%m %H:%M") if r["updated_at"] else "?"
        name_part = f" {name}" if name else ""
        lines.append(f"• {phone}{name_part} ({channel}) — {when}: {last}")
    return "\n".join(lines)


async def _enviar_mensaje(args: Dict, tenant_id: int, user_role: str) -> str:
    if user_role not in ("ceo", "secretary", "professional"):
        return _role_error("enviar_mensaje", ["ceo", "secretary", "professional"])

    phone = args.get("phone", "").strip()
    patient_id = args.get("patient_id")
    patient_name = args.get("patient_name", "").strip()
    message = args.get("message", "").strip()

    if not message:
        return "Necesito el mensaje que querés enviar."

    # ── PASO 1: Resolver paciente (phone, patient_id, o patient_name) ──
    resolved_name = ""
    resolved_patient_id = None

    if patient_id:
        row = await db.pool.fetchrow(
            "SELECT id, phone_number, first_name, last_name FROM patients WHERE id = $1 AND tenant_id = $2",
            int(patient_id),
            tenant_id,
        )
        if not row:
            return f"No encontré al paciente con ID {patient_id}."
        if not phone:
            phone = row["phone_number"] or ""
        resolved_name = f"{row['first_name']} {row['last_name'] or ''}".strip()
        resolved_patient_id = row["id"]

    if not phone and not resolved_patient_id and patient_name:
        rows = await db.pool.fetch(
            """SELECT id, phone_number, first_name, last_name FROM patients
               WHERE tenant_id = $1 AND (
                   first_name ILIKE $2 OR last_name ILIKE $2
                   OR (first_name || ' ' || COALESCE(last_name, '')) ILIKE $2
               )
               ORDER BY created_at DESC LIMIT 5""",
            tenant_id,
            f"%{patient_name}%",
        )
        if not rows:
            return f"No encontré ningún paciente con el nombre '{patient_name}'."
        if len(rows) > 1:
            options = [
                f"  • ID {r['id']}: {r['first_name']} {r['last_name'] or ''} — {r['phone_number'] or 'sin tel'}"
                for r in rows
            ]
            return (
                f"Encontré {len(rows)} pacientes con ese nombre:\n"
                + "\n".join(options)
                + "\n¿A cuál le mando el mensaje?"
            )
        phone = rows[0]["phone_number"] or ""
        resolved_name = f"{rows[0]['first_name']} {rows[0]['last_name'] or ''}".strip()
        resolved_patient_id = rows[0]["id"]

    if not phone and not resolved_patient_id:
        return "Necesito saber a quién enviar el mensaje. Decime el nombre del paciente, su ID, o su teléfono."

    # ── PASO 2: Buscar conversación más reciente del paciente (cualquier canal) ──
    # Prioridad: conversación más reciente con actividad (puede ser WhatsApp, Instagram o Facebook)
    conv = None
    if phone:
        # Buscar por teléfono (normalizado) o external_user_id
        import re as _re

        phone_digits = _re.sub(r"\D", "", phone)
        conv = await db.pool.fetchrow(
            """SELECT id, channel, provider, external_user_id, external_chatwoot_id, external_account_id
               FROM chat_conversations
               WHERE tenant_id = $1 AND (
                   external_user_id = $2
                   OR REGEXP_REPLACE(external_user_id, '[^0-9]', '', 'g') = $3
               )
               ORDER BY last_message_at DESC NULLS LAST
               LIMIT 1""",
            tenant_id,
            phone,
            phone_digits,
        )

    # Si no encontramos por teléfono, buscar por patient_id en la tabla patients → phone → conversación
    if not conv and resolved_patient_id:
        patient_phone = await db.pool.fetchval(
            "SELECT phone_number FROM patients WHERE id = $1 AND tenant_id = $2",
            resolved_patient_id,
            tenant_id,
        )
        if patient_phone:
            phone = patient_phone
            import re as _re

            phone_digits = _re.sub(r"\D", "", phone)
            conv = await db.pool.fetchrow(
                """SELECT id, channel, provider, external_user_id, external_chatwoot_id, external_account_id
                   FROM chat_conversations
                   WHERE tenant_id = $1 AND (
                       external_user_id = $2
                       OR REGEXP_REPLACE(external_user_id, '[^0-9]', '', 'g') = $3
                   )
                   ORDER BY last_message_at DESC NULLS LAST
                   LIMIT 1""",
                tenant_id,
                patient_phone,
                phone_digits,
            )

    display = resolved_name or phone or "paciente"

    # ── PASO 3: Enviar por el canal correcto ──
    try:
        import httpx
        from core.credentials import get_tenant_credential

        channel = conv["channel"] if conv else "whatsapp"
        provider = conv["provider"] if conv else "ycloud"
        external_user_id = conv["external_user_id"] if conv else phone

        logger.info(
            f"📩 NOVA enviar_mensaje: to={display} channel={channel} provider={provider} ext_id={external_user_id}"
        )

        # ── CHATWOOT (Instagram / Facebook / WhatsApp via Chatwoot) ──
        if provider == "chatwoot" and conv and conv.get("external_chatwoot_id"):
            chatwoot_base = await get_tenant_credential(tenant_id, "CHATWOOT_BASE_URL")
            chatwoot_token = await get_tenant_credential(
                tenant_id, "CHATWOOT_API_TOKEN"
            )
            account_id = conv["external_account_id"]
            conv_id = conv["external_chatwoot_id"]

            if not chatwoot_base or not chatwoot_token or not account_id or not conv_id:
                return f"No pude enviar a {display} por {channel}: faltan credenciales de Chatwoot."

            from chatwoot_client import ChatwootClient

            cw = ChatwootClient(chatwoot_base, chatwoot_token)
            await cw.send_text_message(int(account_id), int(conv_id), message)

            # Persist message in DB
            await db.pool.execute(
                "INSERT INTO chat_messages (tenant_id, conversation_id, role, content, from_number, platform_metadata) VALUES ($1, $2, 'assistant', $3, $4, $5::jsonb)",
                tenant_id,
                conv["id"],
                message,
                external_user_id,
                json.dumps({"provider": "chatwoot", "source": "nova"}),
            )
            channel_es = {
                "instagram": "Instagram",
                "facebook": "Facebook Messenger",
                "whatsapp": "WhatsApp",
            }.get(channel, channel)
            logger.info(
                f"📩 NOVA {channel_es} sent via Chatwoot to {display}: {message[:80]}"
            )
            return f'Mensaje enviado a {display} por {channel_es}: "{message[:80]}{"..." if len(message) > 80 else ""}"'

        # ── META DIRECT (Instagram / Facebook via Graph API) ──
        elif provider == "meta_direct" and conv:
            page_token = await get_tenant_credential(tenant_id, "meta_page_token")
            if not page_token:
                return (
                    f"No pude enviar a {display} por {channel}: falta meta_page_token."
                )

            if channel == "whatsapp":
                # Meta Direct WhatsApp — need phone_number_id
                wa_asset = await db.pool.fetchrow(
                    "SELECT content FROM business_assets WHERE tenant_id = $1 AND asset_type = 'whatsapp_waba' AND is_active = true LIMIT 1",
                    tenant_id,
                )
                phone_number_id = None
                wa_token = page_token
                if wa_asset:
                    wa_content = (
                        wa_asset["content"]
                        if isinstance(wa_asset["content"], dict)
                        else json.loads(wa_asset["content"])
                    )
                    phones = wa_content.get("phone_numbers", [])
                    if phones:
                        phone_number_id = phones[0].get("id")
                    waba_token = await get_tenant_credential(
                        tenant_id, f"META_WA_TOKEN_{wa_content.get('id')}"
                    )
                    if waba_token:
                        wa_token = waba_token
                if not phone_number_id:
                    return f"No pude enviar WhatsApp a {display}: falta phone_number_id de Meta."

                async with httpx.AsyncClient(timeout=15) as client:
                    resp = await client.post(
                        f"https://graph.facebook.com/v22.0/{phone_number_id}/messages",
                        headers={
                            "Authorization": f"Bearer {wa_token}",
                            "Content-Type": "application/json",
                        },
                        json={
                            "messaging_product": "whatsapp",
                            "recipient_type": "individual",
                            "to": external_user_id,
                            "type": "text",
                            "text": {"body": message},
                        },
                    )
            else:
                # Instagram DM / Facebook Messenger via Graph API
                async with httpx.AsyncClient(timeout=15) as client:
                    resp = await client.post(
                        "https://graph.facebook.com/v22.0/me/messages",
                        params={"access_token": page_token},
                        json={
                            "recipient": {"id": external_user_id},
                            "message": {"text": message},
                            "messaging_type": "RESPONSE",
                        },
                    )

            if resp.status_code == 200:
                await db.pool.execute(
                    "INSERT INTO chat_messages (tenant_id, conversation_id, role, content, from_number, platform_metadata) VALUES ($1, $2, 'assistant', $3, $4, $5::jsonb)",
                    tenant_id,
                    conv["id"],
                    message,
                    external_user_id,
                    json.dumps({"provider": "meta_direct", "source": "nova"}),
                )
                channel_es = {
                    "instagram": "Instagram",
                    "facebook": "Facebook Messenger",
                    "whatsapp": "WhatsApp",
                }.get(channel, channel)
                logger.info(
                    f"📩 NOVA {channel_es} sent via Meta Direct to {display}: {message[:80]}"
                )
                return f'Mensaje enviado a {display} por {channel_es}: "{message[:80]}{"..." if len(message) > 80 else ""}"'

            error_body = resp.text[:200] if hasattr(resp, "text") else ""
            logger.warning(
                f"📩 NOVA Meta Direct FAILED: status={resp.status_code} body={error_body}"
            )
            if (
                resp.status_code in (400, 403, 10)
                or "window" in error_body.lower()
                or "outside" in error_body.lower()
            ):
                channel_es = {"instagram": "Instagram", "facebook": "Facebook"}.get(
                    channel, channel
                )
                return f"No se pudo enviar el mensaje a {display} por {channel_es}. La ventana de 24 horas puede estar cerrada (el paciente no interactuó recientemente)."
            return f"Error enviando mensaje a {display}: código {resp.status_code}"

        # ── YCLOUD (WhatsApp default) ──
        else:
            ycloud_key = await get_tenant_credential(tenant_id, "YCLOUD_API_KEY")
            if not ycloud_key:
                return "No hay YCloud API key configurada para este tenant."

            tenant_row = await db.pool.fetchrow(
                "SELECT bot_phone_number FROM tenants WHERE id = $1", tenant_id
            )
            bot_phone = (
                tenant_row["bot_phone_number"]
                if tenant_row and tenant_row.get("bot_phone_number")
                else os.getenv("BOT_PHONE_NUMBER", "")
            )

            if not phone:
                return f"El paciente {display} no tiene teléfono cargado."

            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.post(
                    "https://api.ycloud.com/v2/whatsapp/messages/sendDirectly",
                    headers={
                        "X-API-Key": ycloud_key,
                        "Content-Type": "application/json",
                    },
                    json={
                        "from": bot_phone,
                        "to": phone,
                        "type": "text",
                        "text": {"body": message},
                    },
                )

            if resp.status_code == 200:
                # Persist message if we have conversation
                if conv:
                    await db.pool.execute(
                        "INSERT INTO chat_messages (tenant_id, conversation_id, role, content, from_number, platform_metadata) VALUES ($1, $2, 'assistant', $3, $4, $5::jsonb)",
                        tenant_id,
                        conv["id"],
                        message,
                        phone,
                        json.dumps({"provider": "ycloud", "source": "nova"}),
                    )
                logger.info(
                    f"📩 NOVA WhatsApp sent via YCloud to {display} ({phone}): {message[:80]}"
                )
                return f'Mensaje enviado a {display} por WhatsApp: "{message[:80]}{"..." if len(message) > 80 else ""}"'

            error_body = resp.text[:200] if hasattr(resp, "text") else ""
            logger.warning(
                f"📩 NOVA YCloud FAILED to {phone}: status={resp.status_code} body={error_body}"
            )
            if (
                resp.status_code in (400, 403, 470)
                or "template" in error_body.lower()
                or "window" in error_body.lower()
                or "session" in error_body.lower()
            ):
                return (
                    f"No se pudo enviar el mensaje a {display} por WhatsApp. "
                    f"La ventana de 24 horas probablemente está cerrada (el paciente no escribió recientemente). "
                    f"Para contactarlo fuera de la ventana, se necesita un template de mensaje aprobado por Meta."
                )
            return f"Error enviando mensaje a {display}: código {resp.status_code}"

    except Exception as e:
        logger.error(f"📩 NOVA enviar_mensaje error: {e}", exc_info=True)
        return f"Error enviando mensaje: {e}"


async def _ver_estadisticas(args: Dict, tenant_id: int) -> str:
    period = args.get("period", "semana")
    days_map = {"hoy": 0, "semana": 7, "mes": 30, "año": 365}
    days = days_map.get(period, 7)

    since = _today() - timedelta(days=max(days, 1))

    if days == 0:
        # Today only
        stats = await db.pool.fetchrow(
            """
            SELECT
                COUNT(*) AS total,
                COUNT(*) FILTER (WHERE status = 'completed') AS completed,
                COUNT(*) FILTER (WHERE status = 'cancelled') AS cancelled,
                COUNT(*) FILTER (WHERE status = 'no-show') AS no_shows,
                COALESCE(SUM(billing_amount) FILTER (WHERE payment_status = 'paid'), 0) AS revenue
            FROM appointments WHERE tenant_id = $1 AND DATE(appointment_datetime) = CURRENT_DATE
        """,
            tenant_id,
        )
    else:
        stats = await db.pool.fetchrow(
            """
            SELECT
                COUNT(*) AS total,
                COUNT(*) FILTER (WHERE status = 'completed') AS completed,
                COUNT(*) FILTER (WHERE status = 'cancelled') AS cancelled,
                COUNT(*) FILTER (WHERE status = 'no-show') AS no_shows,
                COALESCE(SUM(billing_amount) FILTER (WHERE payment_status = 'paid'), 0) AS revenue
            FROM appointments WHERE tenant_id = $1 AND appointment_datetime::date >= $2
        """,
            tenant_id,
            since,
        )

    total = stats["total"] or 0
    completed = stats["completed"] or 0
    cancelled = stats["cancelled"] or 0
    no_shows = stats["no_shows"] or 0
    revenue = stats["revenue"] or 0
    new_patients = (
        await db.pool.fetchval(
            "SELECT COUNT(*) FROM patients WHERE tenant_id = $1 AND created_at::date >= $2",
            tenant_id,
            since,
        )
        or 0
    )

    return f"""Estadisticas ({period}):
• Turnos totales: {total}
• Completados: {completed}
• Cancelados: {cancelled}
• No-shows: {no_shows}
• Pacientes nuevos: {new_patients}
• Facturacion: ${revenue:,.0f}
• Tasa completitud: {(completed / total * 100) if total > 0 else 0:.1f}%"""


async def _bloquear_agenda(args: Dict, tenant_id: int) -> str:
    prof_id = args.get("professional_id")
    start = args.get("start_datetime", "")
    end = args.get("end_datetime", "")
    reason = args.get("reason", "Bloqueado")
    if not prof_id or not start or not end:
        return "Necesito professional_id, start_datetime y end_datetime."
    start_dt = _parse_datetime_str(start)
    end_dt = _parse_datetime_str(end)
    block_id = uuid.uuid4()
    await db.pool.execute(
        """INSERT INTO google_calendar_blocks (id, tenant_id, google_event_id, professional_id, start_datetime, end_datetime, title, sync_status, created_at)
           VALUES ($1, $2, $3, $4, $5, $6, $7, 'manual', NOW())""",
        block_id,
        tenant_id,
        f"nova-block-{block_id}",
        int(prof_id),
        start_dt,
        end_dt,
        reason,
    )
    await _nova_emit(
        "APPOINTMENT_UPDATED", {"tenant_id": tenant_id, "action": "schedule_blocked"}
    )
    return f"Agenda bloqueada: {_fmt_date(start_dt)} a {_fmt_date(end_dt)} — {reason}"


async def _eliminar_paciente(args: Dict, tenant_id: int, user_role: str) -> str:
    if user_role != "ceo":
        return _role_error("eliminar_paciente", ["ceo"])
    patient_id = args.get("patient_id")
    if not patient_id:
        return "Necesito patient_id."
    result = await db.pool.execute(
        "UPDATE patients SET status = 'archived', updated_at = NOW() WHERE id = $1 AND tenant_id = $2",
        int(patient_id),
        tenant_id,
    )
    if result == "UPDATE 0":
        return "No encontre a ese paciente."
    await _nova_emit(
        "PATIENT_UPDATED",
        {"patient_id": int(patient_id), "tenant_id": tenant_id, "action": "archived"},
    )
    return f"Paciente {patient_id} archivado."


async def _ver_faqs(tenant_id: int) -> str:
    rows = await db.pool.fetch(
        "SELECT id, question, answer FROM clinic_faqs WHERE tenant_id = $1 ORDER BY id",
        tenant_id,
    )
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
    result = await db.pool.execute(
        "DELETE FROM clinic_faqs WHERE id = $1 AND tenant_id = $2",
        int(faq_id),
        tenant_id,
    )
    if result == "DELETE 0":
        return "No encontre esa FAQ."
    await _nova_emit("FAQ_UPDATED", {"tenant_id": tenant_id})
    return f"FAQ {faq_id} eliminada."


async def _cambiar_estado_turno(args: Dict, tenant_id: int) -> str:
    apt_id = args.get("appointment_id", "")
    status = args.get("status", "")
    if not apt_id or not status:
        return "Necesito appointment_id y status."
    try:
        appt_uuid = uuid.UUID(str(apt_id))
    except ValueError:
        return "ID de turno invalido."
    allowed = ["completed", "no-show", "in-progress", "confirmed", "cancelled"]
    if status not in allowed:
        return f"Estado '{status}' no valido. Opciones: {', '.join(allowed)}"
    if status == "completed":
        result = await db.pool.execute(
            "UPDATE appointments SET status = $1, completed_at = NOW(), updated_at = NOW() WHERE id = $2 AND tenant_id = $3",
            status,
            appt_uuid,
            tenant_id,
        )
    else:
        result = await db.pool.execute(
            "UPDATE appointments SET status = $1, updated_at = NOW() WHERE id = $2 AND tenant_id = $3",
            status,
            appt_uuid,
            tenant_id,
        )
    if result == "UPDATE 0":
        return "No encontre ese turno."
    await _nova_emit(
        "APPOINTMENT_UPDATED",
        {"appointment_id": str(appt_uuid), "tenant_id": tenant_id, "status": status},
    )
    return f"Turno actualizado → estado: {status}"


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
    for key in [
        "base_diseases",
        "habitual_medication",
        "allergies",
        "previous_surgeries",
        "is_smoker",
        "smoker_amount",
        "pregnancy_lactation",
        "negative_experiences",
        "specific_fears",
    ]:
        val = args.get(key)
        if val and str(val).strip():
            fields[key] = str(val).strip()

    if not fields:
        return "No me pasaste ningún dato para guardar. Decime qué querés cargar: enfermedades, alergias, medicación, cirugías previas, miedos..."

    # Merge with existing medical_history (don't overwrite)
    existing = await db.pool.fetchval(
        "SELECT medical_history FROM patients WHERE id = $1 AND tenant_id = $2",
        int(patient_id),
        tenant_id,
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
        json.dumps(current, ensure_ascii=False),
        int(patient_id),
        tenant_id,
    )

    saved_fields = ", ".join(fields.keys())
    logger.info(f"🎙️ NOVA: Anamnesis saved for patient {patient_id}: {saved_fields}")
    await _nova_emit(
        "PATIENT_UPDATED", {"patient_id": int(patient_id), "tenant_id": tenant_id}
    )
    return f"Guardé en la ficha médica: {saved_fields}. Hay algo más que quieras agregar? Puedo cargar: enfermedades de base, medicación, alergias, cirugías previas, si fuma, embarazo/lactancia, experiencias negativas, miedos."


async def _ver_anamnesis(args: Dict, tenant_id: int) -> str:
    """Lee la anamnesis completa de un paciente."""
    patient_id = args.get("patient_id")
    if not patient_id:
        return "Necesito el ID del paciente."

    row = await db.pool.fetchrow(
        "SELECT first_name, last_name, medical_history FROM patients WHERE id = $1 AND tenant_id = $2",
        int(patient_id),
        tenant_id,
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
        if (
            val
            and str(val).strip()
            and str(val).strip().lower() not in ["no", "none", "null", ""]
        ):
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

            rows = await db.pool.fetch(
                """
                SELECT a.appointment_datetime, a.status, a.appointment_type, a.payment_status,
                       p.first_name || ' ' || COALESCE(p.last_name, '') as patient_name,
                       prof.first_name as prof_name
                FROM appointments a
                JOIN patients p ON a.patient_id = p.id
                LEFT JOIN professionals prof ON a.professional_id = prof.id
                WHERE a.tenant_id = $1 AND DATE(a.appointment_datetime) BETWEEN $2 AND $3
                ORDER BY a.appointment_datetime ASC LIMIT 20
            """,
                tenant_id,
                start,
                end,
            )

            if not rows:
                return f"No hay turnos entre {start} y {end}."

            parts = [f"{len(rows)} turnos encontrados:"]
            for r in rows:
                dt = r["appointment_datetime"]
                parts.append(
                    f"- {dt.strftime('%d/%m %H:%M')} | {r['patient_name']} | {r['appointment_type'] or 'consulta'} | {r['prof_name'] or '?'} | {r['status']} | pago: {r['payment_status'] or 'pendiente'}"
                )
            return "\n".join(parts)

        # Pacientes
        elif any(w in consulta for w in ["paciente", "patient", "registrado"]):
            count = await db.pool.fetchval(
                "SELECT COUNT(*) FROM patients WHERE tenant_id = $1", tenant_id
            )
            new_month = await db.pool.fetchval(
                "SELECT COUNT(*) FROM patients WHERE tenant_id = $1 AND created_at >= NOW() - INTERVAL '30 days'",
                tenant_id,
            )
            return f"Total pacientes: {count}. Nuevos último mes: {new_month}."

        # Ingresos / pagos
        elif any(
            w in consulta for w in ["ingreso", "pago", "facturación", "revenue", "cobr"]
        ):
            row = await db.pool.fetchrow(
                """
                SELECT COUNT(*) as total, COUNT(*) FILTER (WHERE payment_status = 'paid') as paid,
                       COALESCE(SUM(billing_amount) FILTER (WHERE payment_status = 'paid'), 0) as revenue
                FROM appointments WHERE tenant_id = $1 AND appointment_datetime >= NOW() - INTERVAL '30 days'
            """,
                tenant_id,
            )
            return f"Últimos 30 días: {row['total']} turnos, {row['paid']} pagados, ${int(row['revenue']):,} facturados.".replace(
                ",", "."
            )

        # Leads
        elif any(w in consulta for w in ["lead", "prospecto", "meta", "formulario"]):
            rows = await db.pool.fetch(
                """
                SELECT status, COUNT(*) as cnt FROM patients
                WHERE tenant_id = $1 AND acquisition_source IS NOT NULL
                GROUP BY status
            """,
                tenant_id,
            )
            if not rows:
                return "No hay leads registrados."
            parts = ["Leads por estado:"]
            for r in rows:
                parts.append(f"- {r['status'] or 'sin estado'}: {r['cnt']}")
            return "\n".join(parts)

        # No-shows
        elif "no-show" in consulta or "no show" in consulta or "ausencia" in consulta:
            row = await db.pool.fetchrow(
                """
                SELECT COUNT(*) as total,
                       COUNT(*) FILTER (WHERE status = 'no-show') as no_shows
                FROM appointments WHERE tenant_id = $1 AND appointment_datetime >= NOW() - INTERVAL '30 days'
            """,
                tenant_id,
            )
            rate = (row["no_shows"] / row["total"] * 100) if row["total"] > 0 else 0
            return f"Últimos 30 días: {row['no_shows']} no-shows de {row['total']} turnos ({rate:.1f}%)."

        # Cancelaciones
        elif "cancel" in consulta:
            row = await db.pool.fetchrow(
                """
                SELECT COUNT(*) as total,
                       COUNT(*) FILTER (WHERE status = 'cancelled') as cancelled
                FROM appointments WHERE tenant_id = $1 AND appointment_datetime >= NOW() - INTERVAL '30 days'
            """,
                tenant_id,
            )
            rate = (row["cancelled"] / row["total"] * 100) if row["total"] > 0 else 0
            return f"Últimos 30 días: {row['cancelled']} cancelaciones de {row['total']} turnos ({rate:.1f}%)."

        # Generic fallback
        else:
            # Try a broad stats query
            stats = await db.pool.fetchrow(
                """
                SELECT
                    (SELECT COUNT(*) FROM patients WHERE tenant_id = $1) as patients,
                    (SELECT COUNT(*) FROM appointments WHERE tenant_id = $1 AND status IN ('scheduled', 'confirmed') AND appointment_datetime > NOW()) as upcoming,
                    (SELECT COUNT(*) FROM appointments WHERE tenant_id = $1 AND status = 'completed' AND appointment_datetime >= NOW() - INTERVAL '30 days') as completed_month
            """,
                tenant_id,
            )
            return f"Resumen: {stats['patients']} pacientes, {stats['upcoming']} turnos próximos, {stats['completed_month']} completados este mes."

    except Exception as e:
        logger.error(f"consultar_datos error: {e}")
        return f"Error consultando datos: {str(e)}"


async def _resumen_marketing(args: Dict, tenant_id: int, user_role: str) -> str:
    """Resumen de marketing con datos de Meta Ads si están disponibles."""
    if user_role not in ("ceo",):
        return "Solo el CEO puede ver datos de marketing."

    periodo = args.get("periodo", "mes")
    days = {"hoy": 1, "semana": 7, "mes": 30, "trimestre": 90, "año": 365}.get(
        periodo, 30
    )

    try:
        # Leads por fuente
        leads = await db.pool.fetch(
            """
            SELECT COALESCE(acquisition_source, 'DIRECTO') as source, COUNT(*) as cnt
            FROM patients WHERE tenant_id = $1 AND created_at >= NOW() - INTERVAL '1 day' * $2
            GROUP BY acquisition_source ORDER BY cnt DESC
        """,
            tenant_id,
            days,
        )

        # Ads spend from meta if available
        ad_spend = (
            await db.pool.fetchval(
                """
            SELECT COALESCE(SUM(spend), 0) FROM meta_ad_insights
            WHERE tenant_id = $1 AND date_start >= NOW() - INTERVAL '1 day' * $2
        """,
                tenant_id,
                days,
            )
            if await _table_exists("meta_ad_insights")
            else 0
        )

        total_leads = sum(r["cnt"] for r in leads) if leads else 0
        cost_per_lead = (
            float(ad_spend) / total_leads if total_leads > 0 and ad_spend else 0
        )

        parts = [f"Marketing últimos {days} días:"]
        if ad_spend:
            parts.append(
                f"Inversión Meta Ads: ${int(float(ad_spend)):,}".replace(",", ".")
            )
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
    days = {"hoy": 1, "semana": 7, "mes": 30, "trimestre": 90, "año": 365}.get(
        periodo, 30
    )

    try:
        # Revenue by treatment (excluye turnos vinculados a planes para evitar doble conteo)
        by_treatment = await db.pool.fetch(
            """
            SELECT a.appointment_type, COUNT(*) as cnt,
                   COALESCE(SUM(a.billing_amount), 0) as revenue,
                   COUNT(*) FILTER (WHERE a.payment_status = 'paid') as paid
            FROM appointments a
            WHERE a.tenant_id = $1 AND a.appointment_datetime >= NOW() - INTERVAL '1 day' * $2
            AND a.status IN ('completed', 'confirmed', 'scheduled')
            AND a.plan_item_id IS NULL
            GROUP BY a.appointment_type ORDER BY revenue DESC
        """,
            tenant_id,
            days,
        )

        # Revenue by professional (excluye turnos vinculados a planes para evitar doble conteo)
        by_prof = await db.pool.fetch(
            """
            SELECT prof.first_name, COUNT(*) as cnt,
                   COALESCE(SUM(a.billing_amount), 0) as revenue
            FROM appointments a
            LEFT JOIN professionals prof ON a.professional_id = prof.id
            WHERE a.tenant_id = $1 AND a.appointment_datetime >= NOW() - INTERVAL '1 day' * $2
            AND a.status IN ('completed', 'confirmed', 'scheduled')
            AND a.plan_item_id IS NULL
            GROUP BY prof.first_name ORDER BY revenue DESC
        """,
            tenant_id,
            days,
        )

        # Pending payments (excluye turnos vinculados a planes)
        pending = await db.pool.fetchrow(
            """
            SELECT COUNT(*) as cnt, COALESCE(SUM(billing_amount), 0) as amount
            FROM appointments WHERE tenant_id = $1 AND payment_status = 'pending'
            AND billing_amount > 0 AND status IN ('scheduled', 'confirmed')
            AND plan_item_id IS NULL
        """,
            tenant_id,
        )

        # Planes de tratamiento activos (todos, sin filtro por período)
        plan_rows = await db.pool.fetch(
            """
            SELECT tp.name, tp.approved_total, tp.status,
                   pat.first_name || ' ' || COALESCE(pat.last_name, '') as patient_name,
                   COALESCE(payments.total_paid, 0) as total_paid
            FROM treatment_plans tp
            JOIN patients pat ON tp.patient_id = pat.id AND pat.tenant_id = tp.tenant_id
            LEFT JOIN (
                SELECT plan_id, SUM(amount) as total_paid
                FROM treatment_plan_payments WHERE tenant_id = $1
                GROUP BY plan_id
            ) payments ON tp.id = payments.plan_id
            WHERE tp.tenant_id = $1
              AND tp.status IN ('approved', 'in_progress')
            ORDER BY tp.approved_total DESC
            LIMIT 10
            """,
            tenant_id,
        )

        plan_revenue = sum(float(r["total_paid"]) for r in plan_rows) if plan_rows else 0.0
        total_revenue = sum(float(r["revenue"]) for r in by_treatment) + plan_revenue
        parts = [f"Finanzas últimos {days} días:"]
        parts.append(f"Facturación total: ${int(total_revenue):,}".replace(",", "."))
        parts.append(
            f"Pagos pendientes: {pending['cnt']} turnos (${int(float(pending['amount'])):,})".replace(
                ",", "."
            )
        )
        # Sección de planes de tratamiento activos (detalle por plan)
        if plan_rows:
            parts.append(f"\nPlanes de tratamiento activos ({len(plan_rows)}):")
            for p in plan_rows:
                pending_amount = float(p["approved_total"]) - float(p["total_paid"])
                parts.append(
                    f"  • {p['patient_name']} — {p['name']}: ${int(float(p['approved_total'])):,} total, ${int(float(p['total_paid'])):,} pagado, ${int(pending_amount):,} pendiente".replace(
                        ",", "."
                    )
                )

        if by_treatment:
            parts.append("\nPor tratamiento:")
            for r in by_treatment:
                parts.append(
                    f"  - {r['appointment_type'] or 'consulta'}: {r['cnt']} turnos, ${int(float(r['revenue'])):,} ({r['paid']} pagados)".replace(
                        ",", "."
                    )
                )

        if by_prof:
            parts.append("\nPor profesional:")
            for r in by_prof:
                parts.append(
                    f"  - {r['first_name'] or '?'}: {r['cnt']} turnos, ${int(float(r['revenue'])):,}".replace(
                        ",", "."
                    )
                )

        return "\n".join(parts)

    except Exception as e:
        logger.error(f"resumen_financiero error: {e}")
        return f"Error obteniendo datos financieros: {str(e)}"


def _coerce_crud_value(field: str, value: Any, tabla: str) -> Any:
    """Coerce a CRUD value to the correct Python type for asyncpg based on field name."""
    if value is None:
        return None
    # Date/datetime fields
    if "datetime" in field or field in (
        "created_at",
        "updated_at",
        "completed_at",
        "last_visit",
        "reminder_sent_at",
        "followup_sent_at",
        "uploaded_at",
        "last_message_at",
        "last_read_at",
        "record_date",
        "date_start",
        "date_stop",
        "insurance_valid_until",
    ):
        if isinstance(value, str):
            return _parse_datetime_str(value)
        return value
    # ID fields
    if field == "id":
        if tabla in UUID_ID_TABLES:
            return uuid.UUID(str(value)) if not isinstance(value, uuid.UUID) else value
        return int(value)
    if field.endswith("_id") and field not in (
        "external_user_id",
        "google_event_id",
        "insurance_id",
    ):
        try:
            return int(value)
        except (ValueError, TypeError):
            try:
                return uuid.UUID(str(value))
            except ValueError:
                return value
    # Money fields
    if field in (
        "billing_amount",
        "base_price",
        "consultation_price",
        "amount",
        "spend",
        "cost_per_result",
        "cost_per_click",
    ):
        return Decimal(str(value))
    # Integer fields
    if field in (
        "duration_minutes",
        "default_duration_minutes",
        "billing_installments",
        "max_chairs",
        "chair_id",
        "impressions",
        "clicks",
        "conversions",
    ):
        return int(value)
    # Boolean fields
    if field in (
        "is_active",
        "reminder_sent",
        "feedback_sent",
        "followup_sent",
        "all_day",
    ):
        if isinstance(value, bool):
            return value
        return str(value).lower() in ("true", "1", "si", "yes")
    # Numeric-looking strings
    if isinstance(value, str) and value.isdigit():
        return int(value)
    return value


# =============================================================================
# J. CRUD GENÉRICO — Acceso a toda la infraestructura
# =============================================================================

# Tables that Nova can access (whitelist for security)
ALLOWED_TABLES = frozenset(
    {
        "patients",
        "appointments",
        "professionals",
        "treatment_types",
        "tenants",
        "chat_messages",
        "chat_conversations",
        "patient_documents",
        "clinical_records",
        "automation_logs",
        "patient_memories",
        "clinic_faqs",
        "google_calendar_blocks",
        "meta_ad_insights",
        "treatment_type_professionals",
        "users",
    }
)


def _safe_table_name(tabla: str) -> str:
    """Validate and return safe table name. Raises ValueError if not allowed."""
    clean = tabla.strip().lower()
    if clean not in ALLOWED_TABLES:
        raise ValueError(f"Table '{tabla}' not allowed")
    return clean


# Tables that require CEO role to modify
CEO_ONLY_TABLES = {"tenants", "professionals", "users", "treatment_types"}

# Tables that use UUID as primary key (vs integer)
UUID_ID_TABLES = {
    "appointments",
    "chat_conversations",
    "google_calendar_blocks",
    "clinical_records",
    "patient_documents",
}

# Max results to prevent context explosion
MAX_RESULTS = 15


async def _obtener_registros(args: Dict, tenant_id: int, user_role: str) -> str:
    """GET — Obtiene registros de cualquier tabla con filtros."""
    try:
        tabla = _safe_table_name(args.get("tabla", ""))
    except ValueError:
        return f"Tabla '{args.get('tabla', '')}' no disponible. Tablas: {', '.join(sorted(ALLOWED_TABLES))}"

    filtros = args.get("filtros", "")
    campos = args.get("campos", "")
    limite = min(args.get("limite", 10), MAX_RESULTS)
    orden = args.get("orden", "")

    try:
        # Sanitize campo names to prevent SQL injection
        if campos:
            safe_fields = []
            for f in campos.split(","):
                f = f.strip()
                if f and all(c.isalnum() or c == "_" for c in f):
                    safe_fields.append(f)
            select_fields = ", ".join(safe_fields) if safe_fields else "*"
        else:
            select_fields = "*"
        query = f"SELECT {select_fields} FROM {tabla} WHERE tenant_id = $1"

        # Parse simple filters (field=value AND field>value)
        params = [tenant_id]
        if filtros:
            # Security: only allow simple comparisons, no subqueries
            for part in filtros.split(" AND "):
                part = part.strip()
                for op in [">=", "<=", "!=", ">", "<", "="]:
                    if op in part:
                        field, value = part.split(op, 1)
                        field = field.strip()
                        value = value.strip().strip("'\"")
                        # Sanitize field name (only alphanumeric + underscore)
                        if not all(c.isalnum() or c == "_" for c in field):
                            continue
                        # Auto-detect and convert types for asyncpg
                        if (
                            "date" in field
                            or "datetime" in field
                            or "created_at" in field
                            or "updated_at" in field
                        ):
                            try:
                                value = _parse_datetime_str(value)
                            except Exception:
                                pass
                        elif field.endswith("_id") and field != "external_user_id":
                            # ID fields: try int first (patients, professionals), then UUID (appointments)
                            try:
                                value = int(value)
                            except (ValueError, TypeError):
                                try:
                                    value = uuid.UUID(str(value))
                                except ValueError:
                                    pass  # keep as string
                        elif isinstance(value, str) and (
                            value.isdigit()
                            or (value.startswith("-") and value[1:].isdigit())
                        ):
                            value = int(value)
                        params.append(value)
                        query += f" AND {field} {op} ${len(params)}"
                        break

        if orden:
            safe_order = orden.split()[0] if orden else ""
            direction = "DESC" if "DESC" in orden.upper() else "ASC"
            if safe_order and all(c.isalnum() or c == "_" for c in safe_order):
                query += f" ORDER BY {safe_order} {direction}"

        query += f" LIMIT {limite}"

        rows = await db.pool.fetch(query, *params)
        if not rows:
            return f"Sin resultados en {tabla} con esos filtros."

        # Format results concisely
        results = []
        for r in rows:
            row_data = dict(r)
            # Convert special types
            for k, v in row_data.items():
                if isinstance(v, (datetime, date)):
                    row_data[k] = v.isoformat()
                elif isinstance(v, Decimal):
                    row_data[k] = float(v)
                elif isinstance(v, uuid.UUID):
                    row_data[k] = str(v)
            results.append(row_data)

        # Truncate large fields
        output = json.dumps(results, ensure_ascii=False, default=str)
        if len(output) > 3000:
            output = output[:3000] + "... (truncado)"

        return f"{len(rows)} registros de {tabla}:\n{output}"

    except Exception as e:
        logger.error(f"obtener_registros error: {e}")
        return f"Error consultando {tabla}: {str(e)}"


async def _actualizar_registro(args: Dict, tenant_id: int, user_role: str) -> str:
    """PUT — Actualiza campos de un registro."""
    try:
        tabla = _safe_table_name(args.get("tabla", ""))
    except ValueError:
        return f"Tabla '{args.get('tabla', '')}' no disponible."
    registro_id = args.get("registro_id", "")
    campos_str = args.get("campos", "{}")

    if tabla in CEO_ONLY_TABLES and user_role != "ceo":
        return f"Solo el CEO puede modificar {tabla}."
    if not registro_id:
        return "Necesito el ID del registro."

    try:
        campos = json.loads(campos_str)
        if not campos:
            return "No especificaste qué campos actualizar."

        # Build UPDATE query with type coercion
        sets = []
        params = [tenant_id]
        for field, value in campos.items():
            if not all(c.isalnum() or c == "_" for c in field):
                continue
            try:
                value = _coerce_crud_value(field, value, tabla)
            except Exception:
                pass  # keep original value
            params.append(value)
            sets.append(f"{field} = ${len(params)}")

        if not sets:
            return "No hay campos válidos para actualizar."

        sets.append("updated_at = NOW()")
        # Parse ID to correct type (UUID for some tables, integer for others)
        if tabla in UUID_ID_TABLES:
            try:
                parsed_id = uuid.UUID(str(registro_id))
            except ValueError:
                return f"ID invalido para {tabla} (se espera UUID)."
        else:
            try:
                parsed_id = int(registro_id)
            except (ValueError, TypeError):
                return f"ID invalido para {tabla} (se espera numero)."
        params.append(parsed_id)

        query = f"UPDATE {tabla} SET {', '.join(sets)} WHERE id = ${len(params)} AND tenant_id = $1"
        result = await db.pool.execute(query, *params)
        if result == "UPDATE 0":
            return f"No encontre registro {registro_id} en {tabla}."

        logger.info(
            f"🎙️ NOVA CRUD: UPDATE {tabla} id={registro_id} fields={list(campos.keys())}"
        )
        await _nova_emit("RECORD_UPDATED", {"tenant_id": tenant_id, "table": tabla})
        return f"Actualizado registro {registro_id} en {tabla}: {', '.join(f'{k}={v}' for k, v in campos.items())}"

    except json.JSONDecodeError:
        return "Los campos deben estar en formato JSON válido."
    except Exception as e:
        logger.error(f"actualizar_registro error: {e}")
        return f"Error actualizando {tabla}: {str(e)}"


async def _crear_registro(args: Dict, tenant_id: int, user_role: str) -> str:
    """POST — Crea un nuevo registro."""
    try:
        tabla = _safe_table_name(args.get("tabla", ""))
    except ValueError:
        return f"Tabla '{args.get('tabla', '')}' no disponible."
    datos_str = args.get("datos", "{}")

    if tabla in CEO_ONLY_TABLES and user_role != "ceo":
        return f"Solo el CEO puede crear en {tabla}."

    try:
        datos = json.loads(datos_str)
        if not datos:
            return "No especificaste datos para el registro."

        datos["tenant_id"] = tenant_id
        # Auto-generate UUID for tables that need it
        if "id" not in datos and tabla in UUID_ID_TABLES:
            datos["id"] = uuid.uuid4()
        elif "id" in datos and tabla in UUID_ID_TABLES:
            try:
                datos["id"] = uuid.UUID(str(datos["id"]))
            except ValueError:
                datos["id"] = uuid.uuid4()

        fields = []
        values = []
        params = []
        for field, value in datos.items():
            if not all(c.isalnum() or c == "_" for c in field):
                continue
            try:
                value = _coerce_crud_value(field, value, tabla)
            except Exception:
                pass
            fields.append(field)
            params.append(value)
            values.append(f"${len(params)}")

        query = f"INSERT INTO {tabla} ({', '.join(fields)}) VALUES ({', '.join(values)}) RETURNING id"
        row = await db.pool.fetchrow(query, *params)
        new_id = row["id"] if row else "desconocido"

        logger.info(
            f"🎙️ NOVA CRUD: INSERT {tabla} id={new_id} fields={list(datos.keys())}"
        )
        await _nova_emit("RECORD_UPDATED", {"tenant_id": tenant_id, "table": tabla})
        return f"Registro creado en {tabla} con ID: {new_id}"

    except json.JSONDecodeError:
        return "Los datos deben estar en formato JSON válido."
    except Exception as e:
        logger.error(f"crear_registro error: {e}")
        return f"Error creando registro en {tabla}: {str(e)}"


async def _contar_registros(args: Dict, tenant_id: int) -> str:
    """COUNT — Cuenta registros con filtros."""
    try:
        tabla = _safe_table_name(args.get("tabla", ""))
    except ValueError:
        return f"Tabla '{args.get('tabla', '')}' no disponible."
    filtros = args.get("filtros", "")

    try:
        query = f"SELECT COUNT(*) as cnt FROM {tabla} WHERE tenant_id = $1"
        params = [tenant_id]

        if filtros:
            for part in filtros.split(" AND "):
                part = part.strip()
                for op in [">=", "<=", "!=", ">", "<", "="]:
                    if op in part:
                        field, value = part.split(op, 1)
                        field = field.strip()
                        value = value.strip().strip("'\"")
                        if not all(c.isalnum() or c == "_" for c in field):
                            continue
                        # Auto-detect types (same logic as obtener_registros)
                        if (
                            "date" in field
                            or "datetime" in field
                            or "created_at" in field
                            or "updated_at" in field
                        ):
                            try:
                                value = _parse_datetime_str(value)
                            except Exception:
                                pass
                        elif field.endswith("_id") and field != "external_user_id":
                            try:
                                value = int(value)
                            except (ValueError, TypeError):
                                try:
                                    value = uuid.UUID(str(value))
                                except ValueError:
                                    pass
                        elif isinstance(value, str) and (
                            value.isdigit()
                            or (value.startswith("-") and value[1:].isdigit())
                        ):
                            value = int(value)
                        params.append(value)
                        query += f" AND {field} {op} ${len(params)}"
                        break

        count = await db.pool.fetchval(query, *params)
        return f"{count} registros en {tabla}" + (
            f" con filtro: {filtros}" if filtros else ""
        )

    except Exception as e:
        logger.error(f"contar_registros error: {e}")
        return f"Error contando en {tabla}: {str(e)}"


# =============================================================================
# K. RAG / KNOWLEDGE BASE TOOLS
# =============================================================================


async def _buscar_en_base_conocimiento(args: Dict, tenant_id: int) -> str:
    """Semantic search over clinic knowledge base (FAQs)."""
    query = str(args.get("query", "")).strip()
    if not query:
        return "Necesito una consulta para buscar. Ej: 'precio ortodoncia'"

    try:
        from services.embedding_service import (
            search_similar_faqs,
            check_pgvector_available,
        )

        if not await check_pgvector_available():
            # Fallback: simple text search in clinic_faqs
            rows = await db.pool.fetch(
                """
                SELECT question, answer, category
                FROM clinic_faqs
                WHERE tenant_id = $1
                AND (LOWER(question) LIKE $2 OR LOWER(answer) LIKE $2)
                LIMIT 5
            """,
                tenant_id,
                f"%{query.lower()}%",
            )
            if not rows:
                return f"No encontré FAQs relacionadas con '{query}'."
            lines = [f"Resultados para '{query}' (búsqueda por texto):"]
            for r in rows:
                lines.append(f"  [{r['category']}] {r['question']}: {r['answer']}")
            return "\n".join(lines)

        results = await search_similar_faqs(tenant_id, query, top_k=5)
        if not results:
            return f"No encontré información relevante sobre '{query}' en la base de conocimiento."

        lines = [f"Resultados para '{query}' (búsqueda semántica):"]
        for r in results:
            sim_pct = round(r["similarity"] * 100)
            lines.append(
                f"  [{r['category']}] {r['question']}: {r['answer']} ({sim_pct}% relevancia)"
            )
        return "\n".join(lines)
    except Exception as e:
        logger.error(f"buscar_en_base_conocimiento error: {e}")
        return f"Error buscando en base de conocimiento: {str(e)}"


# =============================================================================
# H2. ODONTOGRAMA TOOLS
# =============================================================================

# FDI tooth names for human-readable output - PERMANENT
_FDI_NAMES = {
    18: "3er molar sup-der",
    17: "2do molar sup-der",
    16: "1er molar sup-der",
    15: "2do premolar sup-der",
    14: "1er premolar sup-der",
    13: "canino sup-der",
    12: "incisivo lateral sup-der",
    11: "incisivo central sup-der",
    21: "incisivo central sup-izq",
    22: "incisivo lateral sup-izq",
    23: "canino sup-izq",
    24: "1er premolar sup-izq",
    25: "2do premolar sup-izq",
    26: "1er molar sup-izq",
    27: "2do molar sup-izq",
    28: "3er molar sup-izq",
    38: "3er molar inf-izq",
    37: "2do molar inf-izq",
    36: "1er molar inf-izq",
    35: "2do premolar inf-izq",
    34: "1er premolar inf-izq",
    33: "canino inf-izq",
    32: "incisivo lateral inf-izq",
    31: "incisivo central inf-izq",
    41: "incisivo central inf-der",
    42: "incisivo lateral inf-der",
    43: "canino inf-der",
    44: "1er premolar inf-der",
    45: "2do premolar inf-der",
    46: "1er molar inf-der",
    47: "2do molar inf-der",
    48: "3er molar inf-der",
}

# FDI tooth names - DECIDUOUS (temporary/primary teeth)
_FDI_NAMES_DECIDUOUS = {
    55: "2do molar temp sup-der",
    54: "1er molar temp sup-der",
    53: "canino temp sup-der",
    52: "incisivo lateral temp sup-der",
    51: "incisivo central temp sup-der",
    61: "incisivo central temp sup-izq",
    62: "incisivo lateral temp sup-izq",
    63: "canino temp sup-izq",
    64: "1er molar temp sup-izq",
    65: "2do molar temp sup-izq",
    85: "2do molar temp inf-der",
    84: "1er molar temp inf-der",
    83: "canino temp inf-der",
    82: "incisivo lateral temp inf-der",
    81: "incisivo central temp inf-der",
    71: "incisivo central temp inf-izq",
    72: "incisivo lateral temp inf-izq",
    73: "canino temp inf-izq",
    74: "1er molar temp inf-izq",
    75: "2do molar temp inf-izq",
}

# State translations - 42 states v3.0
_STATUS_ES = {
    # Preexistente (25)
    "healthy": "sano",
    "implante": "implante",
    "radiografia": "radiografía",
    "restauracion_resina": "resina",
    "restauracion_amalgama": "amalgama",
    "restauracion_temporal": "restauración temporal",
    "sellador_fisuras": "sellador",
    "carilla": "carilla",
    "puente": "puente",
    "corona_porcelana": "corona porcelana",
    "corona_resina": "corona resina",
    "corona_metalceramica": "corona metalcerámica",
    "corona_temporal": "corona temporal",
    "incrustacion": "incrustación",
    "onlay": "onlay",
    "poste": "poste",
    "perno": "perno",
    "fibras_ribbond": "fibras ribbond",
    "tratamiento_conducto": "tratamiento de conducto",
    "protesis_fija": "prótesis fija",
    "protesis_removible": "prótesis removible",
    "blanqueamiento": "blanqueamiento",
    "fluorosis": "fluorosis",
    "hipoplasia": "hipoplasia",
    "desgaste": "desgaste",
    # Lesión (17)
    "caries": "caries",
    "caries_incipiente": "caries incipiente",
    "caries_recurrente": "caries recurrente",
    "caries_radicular": "caries radicular",
    "fractura": "fractura",
    "fisura": "fisura",
    "absceso": "absceso",
    "fistula": "fístula",
    "sinus": "sinus",
    "periodontitis": "periodontitis",
    "gingivitis": "gingivitis",
    "recesion_gingival": "recesión gingival",
    "movilidad_dental": "movilidad",
    "necrosis": "necrosis",
    "pulpotomia": "pulpotomía",
    "apicogenesis": "apicogénesis",
    "apicificacion": "apicificación",
}

# All valid states (42)
_VALID_STATES = set(_STATUS_ES.keys())

# Valid FDI for permanent and deciduous
_VALID_FDI = set(_FDI_NAMES.keys())
_VALID_FDI_DECIDUOUS = set(_FDI_NAMES_DECIDUOUS.keys())


# All 32 FDI teeth in standard order
_ALL_TEETH_FDI = [
    18,
    17,
    16,
    15,
    14,
    13,
    12,
    11,
    21,
    22,
    23,
    24,
    25,
    26,
    27,
    28,
    48,
    47,
    46,
    45,
    44,
    43,
    42,
    41,
    31,
    32,
    33,
    34,
    35,
    36,
    37,
    38,
]


def _build_default_teeth() -> list:
    """Build a full 32-tooth array with all healthy (matches frontend format)."""
    return [
        {"id": t, "state": "healthy", "surfaces": {}, "notes": ""}
        for t in _ALL_TEETH_FDI
    ]


def _parse_odontogram_data(odata) -> list:
    """
    Parsea odontogram_data y retorna lista de teeth en formato v3.
    Delegado al parser unificado en shared/odontogram_utils.py
    """
    from shared.odontogram_utils import normalize_to_v3

    v3 = normalize_to_v3(odata)
    # Retorna los dientes permanentes por default (retrocompat con callers existentes)
    return v3.get("permanent", {}).get("teeth", [])


async def _get_latest_odontogram(patient_id: int, tenant_id: int):
    """Returns (record_id, teeth_array) for the most recent clinical record."""
    row = await db.pool.fetchrow(
        """
        SELECT id, odontogram_data
        FROM clinical_records
        WHERE patient_id = $1 AND tenant_id = $2
        ORDER BY record_date DESC, created_at DESC
        LIMIT 1
        """,
        patient_id,
        tenant_id,
    )
    if not row:
        return None, _build_default_teeth()
    teeth = _parse_odontogram_data(row["odontogram_data"])
    return row["id"], teeth


async def _ver_odontograma(args: Dict, tenant_id: int, user_role: str) -> str:
    """Shows the full current odontogram for a patient (v3 format)."""
    if user_role not in ("ceo", "professional"):
        return _role_error("ver_odontograma", ["ceo", "professional"])

    pid = args.get("patient_id")
    if not pid:
        return "Necesito el ID del paciente."

    patient = await db.pool.fetchrow(
        "SELECT first_name, last_name FROM patients WHERE id = $1 AND tenant_id = $2",
        int(pid),
        tenant_id,
    )
    if not patient:
        return "No encontré a ese paciente."

    record_id, _ = await _get_latest_odontogram(int(pid), tenant_id)
    name = f"{patient['first_name']} {patient['last_name'] or ''}".strip()

    # Read and normalize to v3
    from shared.odontogram_utils import normalize_to_v3

    raw_data = None
    if record_id:
        raw_data = await db.pool.fetchval(
            "SELECT odontogram_data FROM clinical_records WHERE id = $1 AND tenant_id = $2",
            record_id,
            tenant_id,
        )
    v3_data = normalize_to_v3(raw_data)

    # Determine which dentition to show
    denticion = args.get("denticion", "permanente")
    dentition_key = "deciduous" if denticion == "temporal" else "permanent"
    teeth = v3_data.get(dentition_key, {}).get("teeth", [])

    def _surface_state(s):
        """Extract state string from v3 surface (dict or string)."""
        if isinstance(s, dict):
            return s.get("state", "healthy")
        if isinstance(s, str):
            return s
        return "healthy"

    # Count non-healthy teeth (including surface-level)
    modified = []
    for t in teeth:
        tooth_state = t.get("state", "healthy")
        surfaces = t.get("surfaces", {})
        has_surface_change = False
        if isinstance(surfaces, dict):
            has_surface_change = any(
                _surface_state(surfaces.get(sk, {})) != "healthy"
                for sk in ["occlusal", "vestibular", "lingual", "mesial", "distal"]
            )
        if tooth_state != "healthy" or has_surface_change:
            modified.append(t)

    dentition_label = "temporal" if denticion == "temporal" else "permanente"
    total = len(teeth)
    if not modified:
        return f"Odontograma de {name} ({dentition_label}): todas las {total} piezas están sanas."

    lines = [
        f"Odontograma de {name} — dentición {dentition_label} ({len(modified)} pieza(s) con hallazgos):\n"
    ]

    quadrants: Dict[int, list] = {}
    for t in modified:
        num = t.get("id", 0)
        q = num // 10
        if q not in quadrants:
            quadrants[q] = []

        state = t.get("state", "healthy")
        status_es = _STATUS_ES.get(state, state)
        fdi_name = _FDI_NAMES.get(num, f"pieza {num}")
        detail = f"  Pieza {num} ({fdi_name}): {status_es}"

        # Show per-surface states
        surfaces = t.get("surfaces", {})
        if isinstance(surfaces, dict):
            affected = []
            for sk in ["occlusal", "vestibular", "lingual", "mesial", "distal"]:
                sv = _surface_state(surfaces.get(sk, {}))
                if sv != "healthy":
                    affected.append(f"{sk}={_STATUS_ES.get(sv, sv)}")
            if affected:
                detail += f" [{', '.join(affected)}]"

        notes = t.get("notes", "")
        if notes:
            detail += f" — {notes}"

        quadrants[q].append(detail)

    q_names = {
        1: "Superior Derecho (Q1)",
        2: "Superior Izquierdo (Q2)",
        3: "Inferior Izquierdo (Q3)",
        4: "Inferior Derecho (Q4)",
        5: "Superior Derecho temporal (Q5)",
        6: "Superior Izquierdo temporal (Q6)",
        7: "Inferior Izquierdo temporal (Q7)",
        8: "Inferior Derecho temporal (Q8)",
    }
    for q in sorted(quadrants.keys()):
        if quadrants[q]:
            lines.append(f"{q_names.get(q, f'Cuadrante {q}')}:")
            lines.extend(quadrants[q])
            lines.append("")

    lines.append(f"Las {total - len(modified)} piezas restantes están sanas.")
    return "\n".join(lines)


async def _modificar_odontograma(
    args: Dict, tenant_id: int, user_role: str, user_id: str
) -> str:
    """Modifies one or more teeth in the patient's odontogram. Changes persist."""
    if user_role not in ("ceo", "professional"):
        return _role_error("modificar_odontograma", ["ceo", "professional"])

    pid = args.get("patient_id")
    piezas = args.get("piezas", [])
    diagnostico = args.get("diagnostico", "")

    if not pid:
        return "Necesito el ID del paciente."
    if not piezas or not isinstance(piezas, list) or len(piezas) == 0:
        return "Necesito saber qué piezas modificar. Decime los números FDI de las piezas y el estado nuevo."

    # Validate all pieces BEFORE writing anything
    errors = []
    for i, pieza in enumerate(piezas):
        num = pieza.get("numero")
        estado = pieza.get("estado", "")
        if not num:
            errors.append(f"Pieza #{i + 1}: falta el número FDI.")
            continue
        if int(num) not in _VALID_FDI:
            errors.append(
                f"Pieza {num}: número FDI inválido. Usá nomenclatura FDI (11-48)."
            )
            continue
        if estado and estado not in _VALID_STATES:
            errors.append(
                f"Pieza {num}: estado '{estado}' no válido. Opciones: {', '.join(_VALID_STATES)}"
            )

    if errors:
        return "Errores de validación:\n" + "\n".join(errors)

    # Verify patient exists
    patient = await db.pool.fetchrow(
        "SELECT id, first_name, last_name FROM patients WHERE id = $1 AND tenant_id = $2",
        int(pid),
        tenant_id,
    )
    if not patient:
        return "No encontré a ese paciente."

    # Get or create clinical record
    record_id, current_teeth = await _get_latest_odontogram(int(pid), tenant_id)

    prof_id = (
        await _resolve_professional_id(user_id, tenant_id)
        if user_role == "professional"
        else None
    )

    if not record_id:
        # Create a new clinical record for this odontogram
        record_id = uuid.uuid4()
        await db.pool.execute(
            """
            INSERT INTO clinical_records
                (id, tenant_id, patient_id, professional_id, record_date, diagnosis, odontogram_data)
            VALUES ($1, $2, $3, $4, $5, $6, '{}'::jsonb)
            """,
            record_id,
            tenant_id,
            int(pid),
            prof_id,
            _today(),
            diagnostico or "Actualización de odontograma",
        )
        current_teeth = _build_default_teeth()

    # Surface name mapping: Spanish/legacy → canonical v3 keys
    surface_map = {
        "oclusal": "occlusal",
        "occlusal": "occlusal",
        "mesial": "mesial",
        "distal": "distal",
        "bucal": "vestibular",
        "buccal": "vestibular",
        "vestibular": "vestibular",
        "lingual": "lingual",
        "palatino": "lingual",
    }
    SURFACE_KEYS = ["occlusal", "vestibular", "lingual", "mesial", "distal"]

    # Determine dentition type from the pieces
    denticion = args.get("denticion", "permanente")
    is_deciduous = denticion == "temporal" or any(
        int(p.get("numero", 0)) >= 51 for p in piezas
    )

    # Read current v3 data from DB
    from shared.odontogram_utils import normalize_to_v3
    from datetime import datetime as _dt

    raw_data = (
        await db.pool.fetchval(
            "SELECT odontogram_data FROM clinical_records WHERE id = $1 AND tenant_id = $2",
            record_id,
            tenant_id,
        )
        if record_id
        else None
    )

    v3_data = normalize_to_v3(raw_data)
    dentition_key = "deciduous" if is_deciduous else "permanent"
    target_teeth = v3_data.get(dentition_key, {}).get("teeth", [])
    teeth_map = {t["id"]: t for t in target_teeth}

    changes_summary = []
    for pieza in piezas:
        num = int(pieza["numero"])
        estado = pieza["estado"]

        if num not in teeth_map:
            continue

        tooth = teeth_map[num]

        # Update surfaces: if specific surfaces given, only change those.
        # Otherwise, set ALL surfaces to the new state.
        surfaces_input = pieza.get("superficies", {})
        if surfaces_input and isinstance(surfaces_input, dict):
            for s_name, s_val in surfaces_input.items():
                en_name = surface_map.get(s_name.lower(), s_name.lower())
                if en_name in SURFACE_KEYS:
                    tooth["surfaces"][en_name] = {
                        "state": s_val,
                        "condition": None,
                        "color": None,
                    }
        else:
            # No specific surfaces → apply state to ALL surfaces
            for sk in SURFACE_KEYS:
                tooth["surfaces"][sk] = {
                    "state": estado,
                    "condition": None,
                    "color": None,
                }

        # Compute tooth-level state from surfaces
        non_healthy = set()
        for sk in SURFACE_KEYS:
            s = tooth["surfaces"].get(sk, {})
            st = s.get("state", "healthy") if isinstance(s, dict) else s
            if st != "healthy":
                non_healthy.add(st)
        tooth["state"] = (
            non_healthy.pop()
            if len(non_healthy) == 1
            else ("healthy" if not non_healthy else estado)
        )

        notas = pieza.get("notas", "")
        if notas:
            tooth["notes"] = notas

        fdi_name = _FDI_NAMES.get(num, f"pieza {num}")
        status_es = _STATUS_ES.get(estado, estado)

        # Add surface detail to summary
        surf_details = []
        if surfaces_input and isinstance(surfaces_input, dict):
            for s_name, s_val in surfaces_input.items():
                en_name = surface_map.get(s_name.lower(), s_name.lower())
                surf_details.append(f"{en_name}={_STATUS_ES.get(s_val, s_val)}")

        summary = f"  Pieza {num} ({fdi_name}) → {status_es}"
        if surf_details:
            summary += f" [{', '.join(surf_details)}]"
        changes_summary.append(summary)

    # Rebuild v3 data
    v3_data[dentition_key]["teeth"] = list(teeth_map.values())
    v3_data["last_updated"] = _dt.now().isoformat()

    # Persist v3 to database
    await db.pool.execute(
        """
        UPDATE clinical_records
        SET odontogram_data = $1::jsonb, updated_at = NOW()
        WHERE id = $2 AND tenant_id = $3
        """,
        json.dumps(v3_data),
        record_id,
        tenant_id,
    )

    if diagnostico:
        await db.pool.execute(
            "UPDATE clinical_records SET diagnosis = $1 WHERE id = $2 AND tenant_id = $3",
            diagnostico,
            record_id,
            tenant_id,
        )

    name = f"{patient['first_name']} {patient['last_name'] or ''}".strip()
    logger.info(
        f"🦷 NOVA Odontograma: patient={pid} ({name}) updated {len(piezas)} teeth, record={record_id}"
    )

    # Emit real-time Socket.IO event with v3 data
    await _nova_emit(
        "ODONTOGRAM_UPDATED",
        {
            "patient_id": int(pid),
            "record_id": str(record_id),
            "tenant_id": tenant_id,
            "odontogram_data": v3_data,
        },
    )

    result = f"Odontograma de {name} actualizado ({len(piezas)} pieza(s)):\n"
    result += "\n".join(changes_summary)
    return result


async def _table_exists(table_name: str) -> bool:
    """Check if a table exists in the database."""
    try:
        exists = await db.pool.fetchval(
            "SELECT EXISTS(SELECT 1 FROM information_schema.tables WHERE table_name = $1)",
            table_name,
        )
        return bool(exists)
    except Exception:
        return False


# =============================================================================
# L. OBRAS SOCIALES Y DERIVACIÓN TOOLS
# =============================================================================


async def _consultar_obra_social(args: Dict, tenant_id: int) -> str:
    """Consulta si la clínica acepta una obra social y en qué condiciones."""
    nombre = str(args.get("nombre", "")).strip()
    if not nombre:
        return "Necesito el nombre de la obra social a consultar."

    try:
        # 1. Try exact match (case-insensitive)
        row = await db.pool.fetchrow(
            "SELECT * FROM tenant_insurance_providers "
            "WHERE tenant_id = $1 AND LOWER(provider_name) = LOWER($2) AND is_active = true",
            tenant_id,
            nombre,
        )

        # 2. If no exact match, try partial ILIKE
        if not row:
            rows = await db.pool.fetch(
                "SELECT * FROM tenant_insurance_providers "
                "WHERE tenant_id = $1 AND provider_name ILIKE $2 AND is_active = true",
                tenant_id,
                f"%{nombre}%",
            )
            if len(rows) == 1:
                row = rows[0]
            elif len(rows) > 1:
                names = ", ".join(r["provider_name"] for r in rows)
                return f"Encontré varias obras sociales similares: {names}. ¿Cuál querés consultar?"

        # 3. No match
        if not row:
            return (
                f"No hay información sobre '{nombre}' en el catálogo de obras sociales. "
                "Consultá directamente con la clínica."
            )

        # 4. Build response
        status = row["status"]
        name = row["provider_name"]

        if row.get("ai_response_template"):
            return row["ai_response_template"]

        if status == "accepted":
            copay = " Requiere coseguro." if row.get("requires_copay") else ""
            return f"Sí, la clínica trabaja con {name}.{copay}"
        elif status == "restricted":
            return f"La clínica trabaja con {name} con restricciones: {row.get('restrictions', 'consultar con la clínica')}."
        elif status == "external_derivation":
            target = row.get("external_target") or "un centro asociado"
            return (
                f"Para {name} trabajamos a través de {target}. "
                "El paciente debe coordinar directamente con ellos."
            )
        else:  # rejected
            return f"La clínica no trabaja con {name}."

    except Exception as e:
        logger.warning(
            f"_consultar_obra_social error (tabla puede no existir aún): {e}"
        )
        return (
            f"No se pudo verificar la cobertura de '{nombre}' en este momento. "
            "Verificá directamente con la clínica."
        )


async def _ver_reglas_derivacion(tenant_id: int) -> str:
    """Retorna las reglas de derivación de pacientes configuradas."""
    try:
        rows = await db.pool.fetch(
            """
            SELECT pdr.rule_name, pdr.patient_condition, pdr.categories,
                   pdr.priority_order, pdr.target_professional_id,
                   p.first_name as prof_first, p.last_name as prof_last,
                   p.specialty as prof_specialty
            FROM professional_derivation_rules pdr
            LEFT JOIN professionals p ON p.id = pdr.target_professional_id
            WHERE pdr.tenant_id = $1 AND pdr.is_active = true
            ORDER BY pdr.priority_order ASC, pdr.id ASC
            """,
            tenant_id,
        )

        if not rows:
            return "No hay reglas de derivación configuradas para esta clínica."

        lines = [f"Reglas de derivación ({len(rows)} regla(s)):"]
        for i, r in enumerate(rows, start=1):
            rule_name = r["rule_name"] or f"Regla {i}"
            condition = r["patient_condition"] or "cualquier paciente"
            categories = r.get("categories") or ""
            cat_suffix = f" / Categorías: {categories}" if categories else ""

            if r["target_professional_id"] and r["prof_first"]:
                prof_name = f"{r['prof_first']} {r.get('prof_last', '')}".strip()
                spec = f" ({r['prof_specialty']})" if r.get("prof_specialty") else ""
                action = (
                    f"agendar con {prof_name}{spec} (ID: {r['target_professional_id']})"
                )
            else:
                action = "sin filtro de profesional (equipo completo)"

            lines.append(f"  {i}. {rule_name}: {condition}{cat_suffix} → {action}")

        lines.append("\nSi ninguna regla coincide → equipo disponible sin filtro.")
        return "\n".join(lines)

    except Exception as e:
        logger.warning(
            f"_ver_reglas_derivacion error (tabla puede no existir aún): {e}"
        )
        return "No se pudieron obtener las reglas de derivación en este momento."


# =============================================================================
# M. FICHAS DIGITALES
# =============================================================================


async def _generar_ficha_digital(args: Dict, tenant_id: int) -> str:
    """Generate a digital record for a patient."""
    patient_id = args.get("patient_id")
    tipo = args.get("tipo_documento", "clinical_report")

    if not patient_id:
        return "Necesito el ID del paciente para generar la ficha."

    try:
        from services.digital_records_service import (
            gather_patient_data,
            generate_narrative,
            assemble_html,
        )
        from services.odontogram_svg import render_odontogram_svg
        import db as _db
        import uuid as _uuid

        # Layer 1: Gather
        source_data = await gather_patient_data(_db.pool, patient_id, tenant_id, tipo)

        # Layer 2: AI Narrative
        narrative_result = await generate_narrative(
            _db.pool, tenant_id, tipo, source_data
        )
        ai_sections = narrative_result.get("sections", {})
        warnings = narrative_result.get("warnings", [])
        model_used = narrative_result.get("model_used", "unknown")

        # Odontogram SVG
        odontogram_svg = render_odontogram_svg(source_data.get("odontogram", {}))

        # Layer 3: Assemble
        html_content = assemble_html(tipo, source_data, ai_sections, odontogram_svg)

        # Build title
        template_titles = {
            "clinical_report": "Informe Clínico",
            "post_surgery": "Informe Post-Quirúrgico",
            "odontogram_art": "Evaluación Odontológica",
            "authorization_request": "Solicitud de Autorización",
        }
        patient_name = source_data.get("patient", {}).get("full_name", "Paciente")
        title = f"{template_titles.get(tipo, 'Documento')} — {patient_name}"

        # Save to DB
        record_id = str(_uuid.uuid4())
        await db.pool.execute(
            """INSERT INTO patient_digital_records
               (id, tenant_id, patient_id, template_type, title, html_content,
                source_data, generation_metadata, status, created_at, updated_at)
               VALUES ($1, $2, $3, $4, $5, $6, $7, $8, 'draft', NOW(), NOW())""",
            record_id,
            tenant_id,
            patient_id,
            tipo,
            title,
            html_content,
            json.dumps(source_data, default=str),
            json.dumps({"model_used": model_used, "validation_warnings": warnings}),
        )

        # Emit WebSocket event so UI updates in real-time
        await _nova_emit(
            "DIGITAL_RECORD_CREATED",
            {
                "patient_id": patient_id,
                "record_id": record_id,
                "template_type": tipo,
                "title": title,
                "tenant_id": tenant_id,
            },
        )

        warning_text = ""
        if warnings:
            warning_text = f"\nAdvertencias: {', '.join(warnings)}"

        return f"Ficha generada: {title}\nID: {record_id}\nEstado: borrador{warning_text}\n\nQuerés que la envíe por email?"

    except ValueError as e:
        return f"Error de validación: {str(e)}"
    except Exception as e:
        logger.error(f"_generar_ficha_digital error: {e}", exc_info=True)
        return f"Error al generar la ficha: {str(e)}"


async def _enviar_ficha_digital(args: Dict, tenant_id: int) -> str:
    """Send a digital record via email."""
    patient_id = args.get("patient_id")
    record_id = args.get("record_id")
    email = args.get("email")

    if not patient_id:
        return "Necesito el ID del paciente."

    try:
        # Get record (specific or most recent)
        if record_id:
            row = await db.pool.fetchrow(
                """SELECT id, html_content, pdf_path, title FROM patient_digital_records
                   WHERE id = $1 AND patient_id = $2 AND tenant_id = $3""",
                record_id,
                patient_id,
                tenant_id,
            )
        else:
            row = await db.pool.fetchrow(
                """SELECT id, html_content, pdf_path, title FROM patient_digital_records
                   WHERE patient_id = $1 AND tenant_id = $2
                   ORDER BY created_at DESC LIMIT 1""",
                patient_id,
                tenant_id,
            )

        if not row:
            return "No se encontró ninguna ficha digital para este paciente."

        record_id = str(row["id"])

        # Get patient email if not provided
        if not email:
            patient = await db.pool.fetchrow(
                "SELECT email FROM patients WHERE id = $1 AND tenant_id = $2",
                patient_id,
                tenant_id,
            )
            email = patient["email"] if patient and patient["email"] else None

        if not email:
            return "El paciente no tiene email registrado. Proporcioná un email de destino."

        # Ensure PDF exists
        pdf_path = row["pdf_path"]
        if not pdf_path or not os.path.exists(pdf_path):
            from services.digital_records_service import generate_pdf

            output_dir = f"/app/uploads/digital_records/{tenant_id}"
            os.makedirs(output_dir, exist_ok=True)
            pdf_path = f"{output_dir}/{record_id}.pdf"
            await generate_pdf(row["html_content"], pdf_path)
            await db.pool.execute(
                "UPDATE patient_digital_records SET pdf_path = $1, pdf_generated_at = NOW() WHERE id = $2",
                pdf_path,
                record_id,
            )

        # Send email
        from email_service import email_service

        success = email_service.send_digital_record_email(
            to_email=email,
            pdf_path=pdf_path,
            patient_name=row["title"],
            document_title=row["title"],
        )

        if success:
            await db.pool.execute(
                "UPDATE patient_digital_records SET sent_to_email = $1, sent_at = NOW(), status = 'sent' WHERE id = $2",
                email,
                record_id,
            )
            await _nova_emit(
                "DIGITAL_RECORD_SENT",
                {
                    "patient_id": patient_id,
                    "record_id": record_id,
                    "sent_to": email,
                    "tenant_id": tenant_id,
                },
            )
            return f"Ficha enviada a {email}"
        else:
            return "Error al enviar el email. Verificá la configuración SMTP."

    except Exception as e:
        logger.error(f"_enviar_ficha_digital error: {e}", exc_info=True)
        return f"Error: {str(e)}"
