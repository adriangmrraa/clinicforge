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
    """Emit a Socket.IO event so the frontend updates in real-time + notify Telegram."""
    try:
        from main import sio, to_json_safe

        await sio.emit(event, to_json_safe(data))
        logger.info(f"📡 NOVA Socket: {event} → {list(data.keys())}")
    except Exception as e:
        logger.warning(f"📡 NOVA Socket emit failed ({event}): {e}")

    # Mirror to Telegram
    try:
        from services.telegram_notifier import fire_telegram_notification

        fire_telegram_notification(event, data, data.get("tenant_id"))
    except Exception:
        pass


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
        "description": "Crea un paciente nuevo o convierte un lead (contacto de chat sin ficha) en paciente. Si el telefono ya existe como lead/Visitante, lo actualiza a paciente activo. Solo nombre y telefono son obligatorios; apellido es opcional.",
        "parameters": {
            "type": "object",
            "properties": {
                "first_name": {"type": "string", "description": "Nombre del paciente"},
                "last_name": {
                    "type": "string",
                    "description": "Apellido del paciente (opcional)",
                },
                "phone_number": {
                    "type": "string",
                    "description": "Telefono del paciente. Si viene de un chat, usar el numero exacto del chat.",
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
                "email": {"type": "string", "description": "Email del paciente"},
                "city": {"type": "string", "description": "Ciudad del paciente"},
            },
            "required": ["first_name", "phone_number"],
        },
    },
    {
        "type": "function",
        "name": "convertir_lead",
        "description": "Convierte un lead/contacto de chat en paciente. Busca el contacto por telefono en los chats recientes y lo registra como paciente con los datos proporcionados. Util cuando la doctora dice 'cargame al que escribio recien' o 'convertí este lead en paciente'.",
        "parameters": {
            "type": "object",
            "properties": {
                "phone_number": {
                    "type": "string",
                    "description": "Telefono del lead a convertir. Si no lo tenes, usa ver_chats_recientes para buscarlo.",
                },
                "first_name": {"type": "string", "description": "Nombre del paciente"},
                "last_name": {"type": "string", "description": "Apellido (opcional)"},
                "dni": {"type": "string", "description": "DNI (opcional)"},
                "insurance_provider": {
                    "type": "string",
                    "description": "Obra social (opcional)",
                },
            },
            "required": ["phone_number", "first_name"],
        },
    },
    {
        "type": "function",
        "name": "actualizar_paciente",
        "description": "Actualiza un campo especifico de un paciente existente. Podés actualizar nombre, apellido, telefono, email, obra social, DNI, ciudad, notas.",
        "parameters": {
            "type": "object",
            "properties": {
                "patient_id": {"type": "integer", "description": "ID del paciente"},
                "field": {
                    "type": "string",
                    "enum": [
                        "first_name",
                        "last_name",
                        "phone_number",
                        "email",
                        "insurance_provider",
                        "insurance_id",
                        "notes",
                        "preferred_schedule",
                        "city",
                        "dni",
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
                        "consultas",
                        "prevencion",
                        "operatoria",
                        "estetica_facial",
                        "endolifting",
                        "cirugia",
                        "implantes",
                        "regeneracion_osea",
                        "rehabilitacion",
                        "ortodoncia",
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
        "description": "Lista turnos con pago pendiente (seña, saldo). Si se proporciona un nombre de paciente, filtra solo ese paciente. Si no, devuelve todos los pendientes de la clínica.",
        "parameters": {
            "type": "object",
            "properties": {
                "paciente": {
                    "type": "string",
                    "description": "Nombre del paciente para filtrar (opcional). Si el usuario pregunta por un paciente específico, pasar su nombre acá.",
                }
            },
        },
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
                        "consultas",
                        "prevencion",
                        "operatoria",
                        "estetica_facial",
                        "endolifting",
                        "cirugia",
                        "implantes",
                        "regeneracion_osea",
                        "rehabilitacion",
                        "ortodoncia",
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
    {
        "type": "function",
        "name": "completar_tratamiento",
        "description": "Marca un tratamiento como completo para un paciente y envía el mensaje HSM de seguimiento post-tratamiento configurado. Usar cuando el profesional indica que finalizó el tratamiento (diferente de completar un turno individual).",
        "parameters": {
            "type": "object",
            "properties": {
                "appointment_id": {
                    "type": "string",
                    "description": "ID del último turno del tratamiento",
                },
            },
            "required": ["appointment_id"],
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
    {
        "type": "function",
        "name": "enviar_anamnesis",
        "description": "Envía el link del formulario de anamnesis (ficha médica) a un paciente por WhatsApp. Genera el link automáticamente y lo manda.",
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
                                    "implante",
                                    "radiografia",
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
                                    "protesis_removible",
                                    "diente_erupcion",
                                    "diente_no_erupcionado",
                                    "ausente",
                                    "otra_preexistencia",
                                    "treatment_planned",
                                    "mancha_blanca",
                                    "surco_profundo",
                                    "caries",
                                    "caries_penetrante",
                                    "necrosis_pulpar",
                                    "proceso_apical",
                                    "fistula",
                                    "indicacion_extraccion",
                                    "abrasion",
                                    "abfraccion",
                                    "atricion",
                                    "erosion",
                                    "fractura_horizontal",
                                    "fractura_vertical",
                                    "movilidad",
                                    "hipomineralizacion_mih",
                                    "otra_lesion",
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
    # N2. PDF Telegram Tools
    # -------------------------------------------------------------------------
    {
        "type": "function",
        "name": "enviar_pdf_telegram",
        "description": "Envía un PDF de ficha digital existente por el chat de Telegram. Busca el registro en patient_digital_records, genera el PDF si no existe, y lo envía como archivo adjunto.",
        "parameters": {
            "type": "object",
            "properties": {
                "patient_id": {
                    "type": "integer",
                    "description": "ID del paciente",
                },
                "record_id": {
                    "type": "string",
                    "description": "UUID del registro específico (opcional — si no se especifica, busca el más reciente)",
                },
                "tipo_documento": {
                    "type": "string",
                    "enum": [
                        "clinical_report",
                        "post_surgery",
                        "odontogram_art",
                        "authorization_request",
                    ],
                    "description": "Tipo de documento a buscar (opcional — si no se especifica, busca el más reciente de cualquier tipo)",
                },
            },
        },
    },
    {
        "type": "function",
        "name": "generar_reporte_personalizado",
        "description": "Genera un PDF personalizado con el análisis/reporte que escribiste. El PDF tiene logo y branding de la clínica. Usá esto después de recopilar datos y escribir tu análisis como HTML.",
        "parameters": {
            "type": "object",
            "properties": {
                "titulo": {
                    "type": "string",
                    "description": "Título del reporte (ej: 'Comparativa Abril vs Diciembre 2025')",
                },
                "contenido": {
                    "type": "string",
                    "description": "Contenido del reporte en HTML. Usá <h2>, <table>, <ul>, <p>, <b> para formatear.",
                },
                "subtitulo": {
                    "type": "string",
                    "description": "Subtítulo o descripción breve (opcional)",
                },
            },
            "required": ["titulo", "contenido"],
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
    # O3. Crear presupuesto
    # -------------------------------------------------------------------------
    {
        "type": "function",
        "name": "crear_presupuesto",
        "description": "Crea un nuevo plan de tratamiento (presupuesto) en estado borrador para un paciente.",
        "parameters": {
            "type": "object",
            "properties": {
                "patient_id": {
                    "type": "integer",
                    "description": "ID del paciente (requerido si no se provee patient_name)",
                },
                "patient_name": {
                    "type": "string",
                    "description": "Nombre del paciente para buscar (opcional, alternativa a patient_id)",
                },
                "name": {
                    "type": "string",
                    "description": "Nombre del plan (opcional, se auto-genera si no se provee)",
                },
                "professional_id": {
                    "type": "integer",
                    "description": "ID del profesional asignado (opcional)",
                },
                "currency": {
                    "type": "string",
                    "description": "Moneda del presupuesto: ARS (default), USD, PYG, EUR, BRL, CLP, UYU, MXN",
                    "enum": ["ARS", "USD", "PYG", "EUR", "BRL", "CLP", "UYU", "MXN"],
                },
            },
            "required": [],
        },
    },
    # O4. Agregar item a presupuesto
    # -------------------------------------------------------------------------
    {
        "type": "function",
        "name": "agregar_item_presupuesto",
        "description": "Agrega un ítem de tratamiento a un plan de presupuesto existente.",
        "parameters": {
            "type": "object",
            "properties": {
                "plan_id": {
                    "type": "string",
                    "description": "ID UUID del plan de tratamiento",
                },
                "treatment_code": {
                    "type": "string",
                    "description": "Código del tipo de tratamiento (ej: 'ORTODONCIA', 'IMPLANTE')",
                },
                "custom_description": {
                    "type": "string",
                    "description": "Descripción personalizada del ítem (opcional)",
                },
                "estimated_price": {
                    "type": "number",
                    "description": "Precio estimado (opcional, se usa base_price del tratamiento si no se provee)",
                },
            },
            "required": ["plan_id", "treatment_code"],
        },
    },
    # O5. Generar PDF presupuesto
    # -------------------------------------------------------------------------
    {
        "type": "function",
        "name": "generar_pdf_presupuesto",
        "description": "Genera el PDF de un presupuesto de tratamiento. Puede buscar por plan_id, patient_id o nombre del paciente.",
        "parameters": {
            "type": "object",
            "properties": {
                "plan_id": {
                    "type": "string",
                    "description": "ID UUID del plan (opcional)",
                },
                "patient_id": {
                    "type": "integer",
                    "description": "ID del paciente — toma el plan activo más reciente (opcional)",
                },
                "patient_name": {
                    "type": "string",
                    "description": "Nombre del paciente para buscar (opcional)",
                },
            },
            "required": [],
        },
    },
    # O6. Enviar presupuesto por email
    # -------------------------------------------------------------------------
    {
        "type": "function",
        "name": "enviar_presupuesto_email",
        "description": "Genera y envía el PDF de un presupuesto por email al paciente.",
        "parameters": {
            "type": "object",
            "properties": {
                "plan_id": {
                    "type": "string",
                    "description": "ID UUID del plan (opcional)",
                },
                "patient_id": {
                    "type": "integer",
                    "description": "ID del paciente — toma el plan activo más reciente (opcional)",
                },
                "patient_name": {
                    "type": "string",
                    "description": "Nombre del paciente para buscar (opcional)",
                },
                "email": {
                    "type": "string",
                    "description": "Email de destino (opcional, se usa el del paciente si no se provee)",
                },
            },
            "required": [],
        },
    },
    # O7. Editar facturación de turno
    # -------------------------------------------------------------------------
    {
        "type": "function",
        "name": "editar_facturacion_turno",
        "description": "Edita los campos de facturación de un turno: monto, estado de pago y notas.",
        "parameters": {
            "type": "object",
            "properties": {
                "appointment_id": {
                    "type": "string",
                    "description": "ID UUID del turno",
                },
                "billing_amount": {
                    "type": "number",
                    "description": "Monto de facturación (opcional)",
                },
                "payment_status": {
                    "type": "string",
                    "description": "Estado de pago: pending, partial o paid",
                    "enum": ["pending", "partial", "paid"],
                },
                "billing_notes": {
                    "type": "string",
                    "description": "Notas de facturación (opcional)",
                },
            },
            "required": ["appointment_id"],
        },
    },
    # O8. Gestionar usuarios
    # -------------------------------------------------------------------------
    {
        "type": "function",
        "name": "gestionar_usuarios",
        "description": "Gestión de usuarios del sistema: listar, aprobar o suspender. Solo CEO.",
        "parameters": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "description": "Acción a realizar: list, approve o suspend",
                    "enum": ["list", "approve", "suspend"],
                },
                "user_id": {
                    "type": "string",
                    "description": "ID UUID del usuario (requerido para approve/suspend)",
                },
            },
            "required": ["action"],
        },
    },
    # O9. Gestionar obra social
    # -------------------------------------------------------------------------
    {
        "type": "function",
        "name": "gestionar_obra_social",
        "description": "CRUD de obras sociales/seguros de la clínica: listar, crear, actualizar, activar/desactivar o eliminar. Solo CEO.",
        "parameters": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "description": "Acción: list, create, update, toggle o delete",
                    "enum": ["list", "create", "update", "toggle", "delete"],
                },
                "provider_id": {
                    "type": "integer",
                    "description": "ID del proveedor (requerido para update/toggle/delete)",
                },
                "name": {
                    "type": "string",
                    "description": "Nombre de la obra social (requerido para create)",
                },
                "coverage_details": {
                    "type": "string",
                    "description": "Detalles de cobertura / restricciones (opcional)",
                },
            },
            "required": ["action"],
        },
    },
    # O10. Generar PDF liquidación
    # -------------------------------------------------------------------------
    {
        "type": "function",
        "name": "generar_pdf_liquidacion",
        "description": "Genera el PDF de una liquidación profesional. Solo CEO.",
        "parameters": {
            "type": "object",
            "properties": {
                "liquidation_id": {
                    "type": "string",
                    "description": "ID de la liquidación (número entero como string)",
                },
            },
            "required": ["liquidation_id"],
        },
    },
    # O11. Enviar liquidación por email
    # -------------------------------------------------------------------------
    {
        "type": "function",
        "name": "enviar_liquidacion_email",
        "description": "Genera y envía el PDF de una liquidación profesional por email. Solo CEO.",
        "parameters": {
            "type": "object",
            "properties": {
                "liquidation_id": {
                    "type": "string",
                    "description": "ID de la liquidación (número entero como string)",
                },
                "email": {
                    "type": "string",
                    "description": "Email de destino (opcional, se usa el del profesional si no se provee)",
                },
            },
            "required": ["liquidation_id"],
        },
    },
    # O12. Sincronizar turnos a presupuesto
    # -------------------------------------------------------------------------
    {
        "type": "function",
        "name": "sincronizar_turnos_presupuesto",
        "description": "Sincroniza turnos no vinculados del paciente al plan de tratamiento activo, migrando pagos verificados.",
        "parameters": {
            "type": "object",
            "properties": {
                "plan_id": {
                    "type": "string",
                    "description": "ID UUID del plan de tratamiento",
                },
            },
            "required": ["plan_id"],
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
    # -------------------------------------------------------------------------
    # P. Memoria persistente — Engram (3)
    # -------------------------------------------------------------------------
    {
        "type": "function",
        "name": "guardar_memoria",
        "description": "Guarda una nota o decisión importante en la memoria persistente de Nova (Engram). Usá esto para recordar cosas entre sesiones: decisiones del CEO, notas sobre pacientes, recordatorios, preferencias de la clínica, workflows establecidos. La memoria persiste PARA SIEMPRE — no se pierde al cerrar el chat. Si pasás topic_key, hace upsert (actualiza si ya existe esa clave).",
        "parameters": {
            "type": "object",
            "properties": {
                "titulo": {
                    "type": "string",
                    "description": "Título corto y buscable (ej: 'Precio limpieza actualizado', 'García debe seña')",
                },
                "contenido": {
                    "type": "string",
                    "description": "Detalle completo de lo que hay que recordar",
                },
                "tipo": {
                    "type": "string",
                    "enum": [
                        "decision",
                        "feedback",
                        "patient_note",
                        "reminder",
                        "workflow",
                        "preference",
                        "discovery",
                        "general",
                    ],
                    "description": "Tipo semántico de la memoria",
                },
                "topic_key": {
                    "type": "string",
                    "description": "Clave estable para upsert (ej: 'workflow/turno-flow', 'precio/limpieza'). Si ya existe una memoria con esta clave, se actualiza en lugar de crear una nueva.",
                },
            },
            "required": ["titulo", "contenido"],
        },
    },
    {
        "type": "function",
        "name": "buscar_memorias",
        "description": "Busca en la memoria persistente de Nova (Engram). Busca por texto libre en títulos y contenido. Útil para recordar decisiones pasadas, notas de pacientes, preferencias del CEO, etc.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Texto a buscar (ej: 'precio', 'García', 'horarios')",
                },
                "tipo": {
                    "type": "string",
                    "enum": [
                        "decision",
                        "feedback",
                        "patient_note",
                        "reminder",
                        "workflow",
                        "preference",
                        "discovery",
                        "general",
                    ],
                    "description": "Filtrar por tipo (opcional)",
                },
                "limite": {
                    "type": "integer",
                    "description": "Máximo de resultados (default 10)",
                },
            },
            "required": ["query"],
        },
    },
    {
        "type": "function",
        "name": "ver_contexto_memorias",
        "description": "Recupera las memorias más recientes de Nova (Engram), ordenadas por última actualización. Usá esto al inicio de sesión para restaurar contexto de sesiones anteriores.",
        "parameters": {
            "type": "object",
            "properties": {
                "limite": {
                    "type": "integer",
                    "description": "Máximo de memorias a recuperar (default 10)",
                },
                "tipo": {
                    "type": "string",
                    "enum": [
                        "decision",
                        "feedback",
                        "patient_note",
                        "reminder",
                        "workflow",
                        "preference",
                        "discovery",
                        "general",
                    ],
                    "description": "Filtrar por tipo (opcional)",
                },
            },
            "required": [],
        },
    },
    # K3. Patient Memories
    {
        "type": "function",
        "name": "ver_memorias_paciente",
        "description": "Ver las memorias/observaciones guardadas sobre un paciente. Incluye preferencias, comportamiento, miedos, notas familiares, etc. Usá esto cuando necesites contexto personal del paciente que no está en la ficha médica.",
        "parameters": {
            "type": "object",
            "properties": {
                "patient_id": {
                    "type": "integer",
                    "description": "ID del paciente",
                },
            },
            "required": ["patient_id"],
        },
    },
    {
        "type": "function",
        "name": "agregar_memoria_paciente",
        "description": "Guardar una observación/memoria sobre un paciente. Para cosas que NO van en la ficha médica: preferencias (horarios, profesional preferido), comportamiento (llega tarde, es ansioso), familia (mamá acompaña, tiene 2 hijos), logística (vive lejos, necesita presupuesto), etc.",
        "parameters": {
            "type": "object",
            "properties": {
                "patient_id": {
                    "type": "integer",
                    "description": "ID del paciente",
                },
                "memoria": {
                    "type": "string",
                    "description": "La observación a guardar",
                },
                "categoria": {
                    "type": "string",
                    "enum": [
                        "salud",
                        "preferencia",
                        "miedo",
                        "familia",
                        "logistica",
                        "comportamiento",
                        "referencia",
                        "tratamiento",
                        "financiero",
                        "personal",
                        "general",
                    ],
                    "description": "Categoría de la memoria",
                },
                "importancia": {
                    "type": "integer",
                    "description": "Importancia 1-10 (default 7). 10=crítico (alergia), 1=trivial",
                },
            },
            "required": ["patient_id", "memoria"],
        },
    },
    # -------------------------------------------------------------------------
    # N. Plantillas WhatsApp (3)
    # -------------------------------------------------------------------------
    {
        "type": "function",
        "name": "listar_plantillas",
        "description": "Lista las plantillas de WhatsApp aprobadas disponibles para enviar. Muestra nombre, idioma, categoría y variables requeridas de cada una.",
        "parameters": {
            "type": "object",
            "properties": {},
        },
    },
    {
        "type": "function",
        "name": "enviar_plantilla",
        "description": "Enviar una plantilla de WhatsApp a UN paciente específico. Primero usá listar_plantillas para ver cuáles hay. Pasá el nombre de la plantilla y los valores de las variables que requiere.",
        "parameters": {
            "type": "object",
            "properties": {
                "template_name": {
                    "type": "string",
                    "description": "Nombre exacto de la plantilla (de listar_plantillas)",
                },
                "patient_id": {
                    "type": "integer",
                    "description": "ID del paciente (opcional si pasás patient_name o phone)",
                },
                "patient_name": {
                    "type": "string",
                    "description": "Nombre del paciente para buscar (opcional)",
                },
                "phone": {
                    "type": "string",
                    "description": "Teléfono directo (opcional si pasás patient_id o patient_name)",
                },
                "variables": {
                    "type": "object",
                    "description": 'Variables de la plantilla como clave:valor. Ej: {"nombre_paciente": "Juan", "fecha_turno": "15/04"}. Si no se pasan, se auto-completan con datos del paciente cuando sea posible.',
                },
            },
            "required": ["template_name"],
        },
    },
    {
        "type": "function",
        "name": "enviar_plantilla_masiva",
        "description": "Enviar una plantilla de WhatsApp a MUCHOS pacientes que cumplan ciertos filtros. Ideal para campañas: 'mandá la plantilla de limpieza a los que no vinieron en 30 días', 'avisale a los pacientes de implantes que hay promo'. Combina múltiples filtros. Primero muestra la cantidad de pacientes que matchean para confirmar, después envía.",
        "parameters": {
            "type": "object",
            "properties": {
                "template_name": {
                    "type": "string",
                    "description": "Nombre exacto de la plantilla",
                },
                "confirmar": {
                    "type": "boolean",
                    "description": "false=solo contar cuántos matchean (preview). true=enviar de verdad. SIEMPRE mandá false primero para que la CEO confirme la cantidad.",
                },
                "variables": {
                    "type": "object",
                    "description": "Variables de la plantilla. Se pueden usar placeholders: {nombre} se reemplaza por el nombre del paciente automáticamente.",
                },
                "sin_turno_dias": {
                    "type": "integer",
                    "description": "Pacientes que NO tienen turno agendado en los últimos X días. Ej: 30 = no agendaron en el último mes.",
                },
                "ultimo_turno_hace_dias": {
                    "type": "integer",
                    "description": "Pacientes cuyo último turno fue hace más de X días. Ej: 180 = no vinieron en 6 meses.",
                },
                "nunca_agendo": {
                    "type": "boolean",
                    "description": "true = pacientes/leads que NUNCA tuvieron un turno.",
                },
                "tratamiento": {
                    "type": "string",
                    "description": "Filtrar por tipo de tratamiento del último turno. Ej: 'limpieza', 'implante', 'ortodoncia'. Búsqueda parcial.",
                },
                "obra_social": {
                    "type": "string",
                    "description": "Filtrar por obra social/prepaga. Búsqueda parcial. Ej: 'osde', 'swiss medical'.",
                },
                "fuente": {
                    "type": "string",
                    "description": "Filtrar por fuente de captación (first_touch_source). Ej: 'instagram', 'facebook', 'google', 'whatsapp', 'referido'.",
                },
                "edad_min": {
                    "type": "integer",
                    "description": "Edad mínima del paciente.",
                },
                "edad_max": {
                    "type": "integer",
                    "description": "Edad máxima del paciente.",
                },
                "genero": {
                    "type": "string",
                    "enum": ["masculino", "femenino", "otro"],
                    "description": "Filtrar por género.",
                },
                "estado": {
                    "type": "string",
                    "enum": ["active", "inactive"],
                    "description": "Estado del paciente (default: active).",
                },
                "con_anamnesis": {
                    "type": "boolean",
                    "description": "true=solo con anamnesis completada, false=solo SIN anamnesis.",
                },
                "urgencia": {
                    "type": "string",
                    "enum": ["baja", "media", "alta", "urgente"],
                    "description": "Filtrar por nivel de urgencia del triage.",
                },
                "profesional": {
                    "type": "string",
                    "description": "Filtrar por profesional que los atendió. Nombre parcial.",
                },
                "profesional_id": {
                    "type": "integer",
                    "description": "ID del profesional que los atendió.",
                },
                "creado_desde": {
                    "type": "string",
                    "description": "Fecha mínima de creación del paciente. YYYY-MM-DD.",
                },
                "creado_hasta": {
                    "type": "string",
                    "description": "Fecha máxima de creación del paciente. YYYY-MM-DD.",
                },
                "sin_email": {
                    "type": "boolean",
                    "description": "true=pacientes sin email registrado.",
                },
                "con_deuda": {
                    "type": "boolean",
                    "description": "true=pacientes con turnos cuyo payment_status='pending' o 'partial'.",
                },
                "turno_cancelado_dias": {
                    "type": "integer",
                    "description": "Pacientes que cancelaron un turno en los últimos X días (oportunidad de reagendar).",
                },
                "limite": {
                    "type": "integer",
                    "description": "Máximo de pacientes a enviar (default 50, max 200). Seguridad contra envíos accidentales masivos.",
                },
            },
            "required": ["template_name"],
        },
    },
    # -------------------------------------------------------
    # N+1. Acción Masiva (herramienta Jarvis-style)
    # -------------------------------------------------------
    {
        "type": "function",
        "name": "accion_masiva",
        "description": "Herramienta Jarvis-style: combinar filtros de pacientes con CUALQUIER acción (plantilla, mensaje libre, anamnesis, listar, contar, exportar). Ej: 'mandá esto a los que no vinieron en 30 días', 'avisale a los de OSDE que mañana no atiende', 'dame la lista de leads de Instagram sin turno'. NO requiere plantilla_name si la accion es 'listar', 'contar' o 'exportar'.",
        "parameters": {
            "type": "object",
            "properties": {
                "accion": {
                    "type": "string",
                    "enum": [
                        "plantilla",
                        "mensaje_libre",
                        "anamnesis",
                        "listar",
                        "contar",
                        "exportar",
                    ],
                    "description": "Acción a ejecutar sobre los pacientes que matcheen los filtros. plantilla=enviar WhatsApp template, mensaje_libre=enviar texto por WhatsApp, anamnesis=enviar link de anamnesis, listar=devolver lista de pacientes, contar=solo contar cuántos matchean, exportar=generar CSV/texto exportable.",
                },
                "confirmar": {
                    "type": "boolean",
                    "description": "false=solo mostrar cuántos matchean (preview). true=ejecutar la acción. SIEMPRE mandá false primero para que la CEO confirme.",
                },
                "template_name": {
                    "type": "string",
                    "description": "Nombre de la plantilla YCloud (requerido si accion='plantilla'). Usá listar_plantillas para ver disponibles.",
                },
                "mensaje": {
                    "type": "string",
                    "description": "Texto del mensaje (requerido si accion='mensaje_libre'). Se reemplaza {nombre} por el nombre del paciente automáticamente.",
                },
                "variables": {
                    "type": "object",
                    "description": "Variables de la plantilla como clave:valor. Se pueden usar {nombre} que se reemplaza automáticamente.",
                },
                "limite": {
                    "type": "integer",
                    "description": "Máximo de pacientes a procesar (default 50, max 200).",
                },
                # Mismos filtros que enviar_plantilla_masiva
                "sin_turno_dias": {
                    "type": "integer",
                    "description": "Pacientes que NO tienen turno en los últimos X días.",
                },
                "ultimo_turno_hace_dias": {
                    "type": "integer",
                    "description": "Última visita hace más de X días.",
                },
                "nunca_agendo": {
                    "type": "boolean",
                    "description": "true=pacientes/leads que NUNCA tuvieron turno.",
                },
                "tratamiento": {
                    "type": "string",
                    "description": "Filtrar por tipo de tratamiento del último turno.",
                },
                "obra_social": {
                    "type": "string",
                    "description": "Filtrar por obra social/prepaga (búsqueda parcial).",
                },
                "fuente": {
                    "type": "string",
                    "description": "Fuente de captación: instagram, facebook, google, referido.",
                },
                "edad_min": {"type": "integer", "description": "Edad mínima."},
                "edad_max": {"type": "integer", "description": "Edad máxima."},
                "genero": {"type": "string", "enum": ["masculino", "femenino", "otro"]},
                "estado": {
                    "type": "string",
                    "enum": ["active", "inactive"],
                    "description": "Default: active",
                },
                "con_anamnesis": {
                    "type": "boolean",
                    "description": "true=con anamnesis, false=sin anamnesis.",
                },
                "urgencia": {
                    "type": "string",
                    "enum": ["baja", "media", "alta", "urgente"],
                },
                "profesional": {
                    "type": "string",
                    "description": "Filtrar por profesional que atendió.",
                },
                "profesional_id": {
                    "type": "integer",
                    "description": "ID del profesional.",
                },
                "creado_desde": {
                    "type": "string",
                    "description": "Fecha mínima de creación (YYYY-MM-DD).",
                },
                "creado_hasta": {
                    "type": "string",
                    "description": "Fecha máxima de creación (YYYY-MM-DD).",
                },
                "sin_email": {
                    "type": "boolean",
                    "description": "true=pacientes sin email.",
                },
                "con_deuda": {
                    "type": "boolean",
                    "description": "true=con pagos pendientes.",
                },
                "turno_cancelado_dias": {
                    "type": "integer",
                    "description": "Cancelaron turno en los últimos X días.",
                },
            },
            "required": ["accion"],
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

    if not first_name or not phone:
        return "Necesito al menos el nombre y el telefono para registrar un paciente."

    # Check if guest/Visitante exists — upgrade instead of duplicate error
    existing = await db.pool.fetchrow(
        "SELECT id, status, first_name FROM patients WHERE tenant_id = $1 AND phone_number = $2",
        tenant_id,
        phone,
    )
    if existing:
        if existing["status"] == "guest" or existing["first_name"] in (
            "Visitante",
            "Paciente",
            "Sin nombre",
        ):
            # Upgrade guest to active patient
            await db.pool.execute(
                """UPDATE patients SET first_name=$1, last_name=$2, dni=$3,
                   insurance_provider=$4, insurance_id=$5, email=$6, city=$7,
                   status='active', updated_at=NOW()
                   WHERE id=$8 AND tenant_id=$9""",
                first_name,
                last_name or None,
                args.get("dni"),
                args.get("insurance_provider"),
                args.get("insurance_id"),
                args.get("email"),
                args.get("city"),
                existing["id"],
                tenant_id,
            )
            await _nova_emit(
                "PATIENT_CREATED",
                {
                    "patient_id": existing["id"],
                    "phone_number": phone,
                    "tenant_id": tenant_id,
                    "first_name": first_name,
                    "last_name": last_name or "",
                    "status": "active",
                },
            )
            full_name = f"{first_name} {last_name}".strip()
            return f"✅ Paciente {full_name} registrado (convertido desde lead, ID {existing['id']})."
        full_name = f"{existing['first_name']}".strip()
        return f"Ya existe un paciente con ese telefono: {full_name} (ID {existing['id']}). Usa actualizar_paciente si necesitas cambiar datos."

    row = await db.pool.fetchrow(
        """
        INSERT INTO patients (tenant_id, first_name, last_name, phone_number, dni,
                              insurance_provider, insurance_id, email, city, status, created_at)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, 'active', NOW())
        RETURNING id
        """,
        tenant_id,
        first_name,
        last_name or None,
        phone,
        args.get("dni"),
        args.get("insurance_provider"),
        args.get("insurance_id"),
        args.get("email"),
        args.get("city"),
    )
    await _nova_emit(
        "PATIENT_CREATED",
        {
            "patient_id": row["id"],
            "phone_number": phone,
            "tenant_id": tenant_id,
            "first_name": first_name,
            "last_name": last_name or "",
            "status": "active",
        },
    )
    full_name = f"{first_name} {last_name}".strip()
    return f"✅ Paciente {full_name} registrado con ID {row['id']}."


async def _convertir_lead(args: Dict, tenant_id: int) -> str:
    """Convierte un lead de chat en paciente. Busca por teléfono en chats y crea/actualiza el paciente."""
    phone = args.get("phone_number", "").strip()
    first_name = args.get("first_name", "").strip()

    if not phone:
        return "Necesito el teléfono del lead. Usá ver_chats_recientes para ver los leads actuales."
    if not first_name:
        # Try to get name from chat conversation
        conv_name = await db.pool.fetchval(
            "SELECT display_name FROM chat_conversations WHERE tenant_id=$1 AND external_user_id=$2 ORDER BY updated_at DESC LIMIT 1",
            tenant_id,
            phone,
        )
        if conv_name and conv_name != phone:
            first_name = conv_name.split()[0] if conv_name else ""
        if not first_name:
            return "Necesito al menos el nombre del paciente para convertir el lead."

    # Delegate to registrar_paciente (handles guest upgrade)
    return await _registrar_paciente(
        {
            "first_name": first_name,
            "last_name": args.get("last_name", ""),
            "phone_number": phone,
            "dni": args.get("dni"),
            "insurance_provider": args.get("insurance_provider"),
        },
        tenant_id,
    )


async def _actualizar_paciente(args: Dict, tenant_id: int) -> str:
    pid = args.get("patient_id")
    field = args.get("field")
    value = args.get("value")

    if not pid or not field or value is None:
        return "Necesito patient_id, field y value."

    allowed_fields = {
        "first_name",
        "last_name",
        "phone_number",
        "email",
        "insurance_provider",
        "insurance_id",
        "notes",
        "preferred_schedule",
        "city",
        "dni",
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
            lines = [
                f"Encontré {len(draft_plans)} presupuestos en borrador. Especificá cuál querés aprobar usando plan_id:"
            ]
            for dp in draft_plans:
                lines.append(
                    f"  • *{dp['name']}* — {dp['patient_full_name']} [ID: {dp['id']}]"
                )
            return "\n".join(lines)
        plan = draft_plans[0]
        # Ensure plan_id is set for the UPDATE below
        plan_id = str(plan["id"])
        if not patient_id:
            # Recover patient_id for the emit
            patient_id = await db.pool.fetchval(
                "SELECT patient_id FROM treatment_plans WHERE id = $1 AND tenant_id = $2",
                plan["id"],
                tenant_id,
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


# =============================================================================
# O3–O12. NEW BUDGET / BILLING / ADMIN TOOLS
# =============================================================================


async def _crear_presupuesto(args: Dict, tenant_id: int, user_role: str) -> str:
    """Crea un plan de tratamiento en estado draft."""
    if user_role not in ("ceo", "secretary"):
        return _role_error("crear_presupuesto", ["ceo", "secretary"])

    patient_id = args.get("patient_id")
    patient_name = args.get("patient_name")
    name = args.get("name")
    professional_id = args.get("professional_id")

    # Resolver paciente por nombre si no hay patient_id
    if not patient_id and patient_name:
        row = await db.pool.fetchrow(
            """
            SELECT id, first_name, last_name FROM patients
            WHERE tenant_id = $1 AND LOWER(first_name || ' ' || COALESCE(last_name, '')) LIKE $2
            ORDER BY created_at DESC LIMIT 1
            """,
            tenant_id,
            f"%{patient_name.lower()}%",
        )
        if not row:
            return f"No encontré ningún paciente con el nombre '{patient_name}'."
        patient_id = row["id"]
        patient_name = f"{row['first_name']} {row['last_name'] or ''}".strip()
    elif patient_id:
        row = await db.pool.fetchrow(
            "SELECT first_name, last_name FROM patients WHERE id = $1 AND tenant_id = $2",
            int(patient_id),
            tenant_id,
        )
        if not row:
            return f"No encontré el paciente con ID {patient_id}."
        patient_name = f"{row['first_name']} {row['last_name'] or ''}".strip()
    else:
        return "Necesito patient_id o patient_name para crear el presupuesto."

    plan_name = name or f"Tratamiento de {patient_name}"
    plan_id = str(uuid.uuid4())
    currency = args.get("currency", "ARS")
    notes_json = json.dumps({"currency": currency}) if currency != "ARS" else None

    await db.pool.execute(
        """
        INSERT INTO treatment_plans (id, tenant_id, patient_id, professional_id, name, status, estimated_total, notes, created_at, updated_at)
        VALUES ($1, $2, $3, $4, $5, 'draft', 0, $6, NOW(), NOW())
        """,
        plan_id,
        tenant_id,
        int(patient_id),
        int(professional_id) if professional_id else None,
        plan_name,
        notes_json,
    )

    await _nova_emit(
        "TREATMENT_PLAN_UPDATED",
        {"plan_id": plan_id, "tenant_id": tenant_id, "patient_id": patient_id},
    )

    logger.info(f"Nova: crear_presupuesto → plan {plan_id} para paciente {patient_id}")
    return f"✅ Presupuesto creado: *{plan_name}* (ID: {plan_id})\nEstado: borrador. Podés agregar ítems con agregar_item_presupuesto."


async def _agregar_item_presupuesto(args: Dict, tenant_id: int, user_role: str) -> str:
    """Agrega un ítem a un plan de tratamiento."""
    if user_role not in ("ceo", "secretary"):
        return _role_error("agregar_item_presupuesto", ["ceo", "secretary"])

    plan_id = args.get("plan_id")
    treatment_code = args.get("treatment_code")
    custom_description = args.get("custom_description")
    estimated_price = args.get("estimated_price")

    if not plan_id or not treatment_code:
        return "Necesito plan_id y treatment_code para agregar el ítem."

    # Validar plan
    plan = await db.pool.fetchrow(
        "SELECT id, name, patient_id FROM treatment_plans WHERE id = $1 AND tenant_id = $2",
        plan_id,
        tenant_id,
    )
    if not plan:
        return f"No encontré el plan con ID {plan_id}."

    # Obtener precio base del tratamiento si no se proveyó
    if estimated_price is None:
        tt = await db.pool.fetchrow(
            "SELECT base_price, name FROM treatment_types WHERE code = $1 AND tenant_id = $2",
            treatment_code.upper(),
            tenant_id,
        )
        if tt:
            estimated_price = float(tt["base_price"] or 0)
            if not custom_description:
                custom_description = tt["name"]
        else:
            estimated_price = 0.0

    # Calcular sort_order
    max_order = await db.pool.fetchval(
        "SELECT COALESCE(MAX(sort_order), 0) FROM treatment_plan_items WHERE plan_id = $1 AND tenant_id = $2",
        plan_id,
        tenant_id,
    )
    sort_order = (max_order or 0) + 1

    item_id = str(uuid.uuid4())
    await db.pool.execute(
        """
        INSERT INTO treatment_plan_items (id, tenant_id, plan_id, treatment_type_code, custom_description, estimated_price, sort_order, status, created_at, updated_at)
        VALUES ($1, $2, $3, $4, $5, $6, $7, 'pending', NOW(), NOW())
        """,
        item_id,
        tenant_id,
        plan_id,
        treatment_code.upper(),
        custom_description,
        float(estimated_price),
        sort_order,
    )

    # Recalcular estimated_total del plan
    await db.pool.execute(
        """
        UPDATE treatment_plans
        SET estimated_total = (
            SELECT COALESCE(SUM(estimated_price), 0)
            FROM treatment_plan_items
            WHERE plan_id = $1 AND tenant_id = $2
        ), updated_at = NOW()
        WHERE id = $1 AND tenant_id = $2
        """,
        plan_id,
        tenant_id,
    )

    await _nova_emit(
        "TREATMENT_PLAN_UPDATED",
        {"plan_id": plan_id, "tenant_id": tenant_id, "patient_id": plan["patient_id"]},
    )

    desc = custom_description or treatment_code.upper()
    logger.info(f"Nova: agregar_item_presupuesto → plan {plan_id}, item {item_id}")
    return f"✅ Ítem agregado al plan *{plan['name']}*:\n• {desc} — {_fmt_money(estimated_price)}\nTotal actualizado del plan calculado correctamente."


async def _generar_pdf_presupuesto(args: Dict, tenant_id: int, user_role: str) -> str:
    """Genera el PDF de un presupuesto."""
    if user_role not in ("ceo", "secretary"):
        return _role_error("generar_pdf_presupuesto", ["ceo", "secretary"])

    plan_id = args.get("plan_id")
    patient_id = args.get("patient_id")
    patient_name = args.get("patient_name")

    try:
        # Resolver plan_id si no se proveyó directamente
        if not plan_id:
            if patient_id:
                row = await db.pool.fetchrow(
                    """
                    SELECT id FROM treatment_plans
                    WHERE patient_id = $1 AND tenant_id = $2 AND status NOT IN ('cancelled')
                    ORDER BY updated_at DESC LIMIT 1
                    """,
                    int(patient_id),
                    tenant_id,
                )
            elif patient_name:
                row = await db.pool.fetchrow(
                    """
                    SELECT tp.id FROM treatment_plans tp
                    JOIN patients p ON p.id = tp.patient_id
                    WHERE tp.tenant_id = $1 AND p.tenant_id = $1
                      AND LOWER(p.first_name || ' ' || COALESCE(p.last_name, '')) LIKE $2
                      AND tp.status NOT IN ('cancelled')
                    ORDER BY tp.updated_at DESC LIMIT 1
                    """,
                    tenant_id,
                    f"%{patient_name.lower()}%",
                )
            else:
                return (
                    "Necesito plan_id, patient_id o patient_name para generar el PDF."
                )

            if not row:
                return "No encontré ningún plan activo para ese paciente."
            plan_id = str(row["id"])

        from services.budget_service import generate_budget_pdf

        pdf_path = await generate_budget_pdf(db.pool, plan_id, tenant_id)
        if not pdf_path:
            return "Error generando el PDF. Verificá que el plan tenga ítems."

        await _nova_emit(
            "BILLING_UPDATED", {"plan_id": plan_id, "tenant_id": tenant_id}
        )

        logger.info(f"Nova: generar_pdf_presupuesto → {pdf_path}")
        return f"✅ PDF generado correctamente.\nRuta: {pdf_path}"

    except Exception as e:
        logger.error(f"_generar_pdf_presupuesto error: {e}", exc_info=True)
        return f"Error generando el PDF: {str(e)}"


async def _enviar_presupuesto_email(args: Dict, tenant_id: int, user_role: str) -> str:
    """Genera y envía el PDF de un presupuesto por email."""
    if user_role not in ("ceo", "secretary"):
        return _role_error("enviar_presupuesto_email", ["ceo", "secretary"])

    plan_id = args.get("plan_id")
    patient_id = args.get("patient_id")
    patient_name_arg = args.get("patient_name")
    email = args.get("email")

    try:
        # Resolver plan_id
        if not plan_id:
            if patient_id:
                row = await db.pool.fetchrow(
                    """
                    SELECT id FROM treatment_plans
                    WHERE patient_id = $1 AND tenant_id = $2 AND status NOT IN ('cancelled')
                    ORDER BY updated_at DESC LIMIT 1
                    """,
                    int(patient_id),
                    tenant_id,
                )
            elif patient_name_arg:
                row = await db.pool.fetchrow(
                    """
                    SELECT tp.id FROM treatment_plans tp
                    JOIN patients p ON p.id = tp.patient_id
                    WHERE tp.tenant_id = $1 AND p.tenant_id = $1
                      AND LOWER(p.first_name || ' ' || COALESCE(p.last_name, '')) LIKE $2
                      AND tp.status NOT IN ('cancelled')
                    ORDER BY tp.updated_at DESC LIMIT 1
                    """,
                    tenant_id,
                    f"%{patient_name_arg.lower()}%",
                )
            else:
                return "Necesito plan_id, patient_id o patient_name para enviar el presupuesto."

            if not row:
                return "No encontré ningún plan activo para ese paciente."
            plan_id = str(row["id"])

        # Obtener email del paciente si no se proveyó
        if not email:
            patient_row = await db.pool.fetchrow(
                """
                SELECT p.email FROM patients p
                JOIN treatment_plans tp ON tp.patient_id = p.id
                WHERE tp.id = $1 AND tp.tenant_id = $2
                """,
                plan_id,
                tenant_id,
            )
            email = patient_row["email"] if patient_row else None

        if not email:
            return "El paciente no tiene email registrado. Proporcioná un email de destino."

        from services.budget_service import gather_budget_data, generate_budget_pdf

        pdf_path = await generate_budget_pdf(db.pool, plan_id, tenant_id)
        if not pdf_path:
            return "Error generando el PDF. Verificá que el plan tenga ítems."

        data = await gather_budget_data(db.pool, plan_id, tenant_id)
        if not data:
            return "No se pudo obtener los datos del presupuesto."

        from email_service import email_service
        import asyncio as _asyncio

        patient_name = data.get("patient", {}).get("name", "Paciente")
        clinic_name = data.get("clinic", {}).get("name", "Clínica")

        await _asyncio.to_thread(
            lambda: email_service.send_budget_email(
                to_email=email,
                pdf_path=pdf_path,
                patient_name=patient_name,
                clinic_name=clinic_name,
            )
        )

        await _nova_emit(
            "BILLING_UPDATED", {"plan_id": plan_id, "tenant_id": tenant_id}
        )

        logger.info(f"Nova: enviar_presupuesto_email → {email}")
        return f"✅ Presupuesto enviado a {email} para {patient_name}."

    except Exception as e:
        logger.error(f"_enviar_presupuesto_email error: {e}", exc_info=True)
        return f"Error enviando el presupuesto: {str(e)}"


async def _editar_facturacion_turno(args: Dict, tenant_id: int, user_role: str) -> str:
    """Edita los campos de facturación de un turno."""
    if user_role not in ("ceo", "secretary"):
        return _role_error("editar_facturacion_turno", ["ceo", "secretary"])

    appointment_id = args.get("appointment_id")
    billing_amount = args.get("billing_amount")
    payment_status = args.get("payment_status")
    billing_notes = args.get("billing_notes")

    if not appointment_id:
        return "Necesito appointment_id para editar la facturación."

    try:
        appt_uuid = uuid.UUID(str(appointment_id))
    except ValueError:
        return "ID de turno inválido."

    # Validar turno
    appt = await db.pool.fetchrow(
        "SELECT id FROM appointments WHERE id = $1 AND tenant_id = $2",
        appt_uuid,
        tenant_id,
    )
    if not appt:
        return f"No encontré el turno con ID {appointment_id}."

    # Construir SET dinámico
    set_parts = []
    values = []
    idx = 1

    if billing_amount is not None:
        set_parts.append(f"billing_amount = ${idx}")
        values.append(float(billing_amount))
        idx += 1

    if payment_status is not None:
        if payment_status not in ("pending", "partial", "paid"):
            return "payment_status debe ser: pending, partial o paid."
        set_parts.append(f"payment_status = ${idx}")
        values.append(payment_status)
        idx += 1

    if billing_notes is not None:
        set_parts.append(f"billing_notes = ${idx}")
        values.append(billing_notes)
        idx += 1

    if not set_parts:
        return "No se especificó ningún campo a actualizar."

    set_parts.append(f"updated_at = NOW()")
    values.extend([appt_uuid, tenant_id])

    await db.pool.execute(
        f"UPDATE appointments SET {', '.join(set_parts)} WHERE id = ${idx} AND tenant_id = ${idx + 1}",
        *values,
    )

    await _nova_emit(
        "APPOINTMENT_UPDATED",
        {"appointment_id": str(appt_uuid), "tenant_id": tenant_id},
    )

    parts = []
    if billing_amount is not None:
        parts.append(f"monto: {_fmt_money(billing_amount)}")
    if payment_status is not None:
        parts.append(f"estado: {payment_status}")
    if billing_notes is not None:
        parts.append("notas actualizadas")

    logger.info(f"Nova: editar_facturacion_turno → {appointment_id}")
    return f"✅ Facturación del turno actualizada: {', '.join(parts)}."


async def _gestionar_usuarios(args: Dict, tenant_id: int, user_role: str) -> str:
    """Gestión de usuarios: list / approve / suspend. Solo CEO."""
    if user_role != "ceo":
        return _role_error("gestionar_usuarios", ["ceo"])

    action = args.get("action", "list")
    user_id = args.get("user_id")

    if action == "list":
        rows = await db.pool.fetch(
            """
            SELECT id, email, role, status, first_name, last_name, created_at
            FROM users
            WHERE tenant_id = $1
            ORDER BY created_at DESC
            """,
            tenant_id,
        )
        if not rows:
            return "No hay usuarios registrados."
        lines = ["Usuarios del sistema:"]
        for r in rows:
            name = (
                f"{r['first_name'] or ''} {r['last_name'] or ''}".strip() or r["email"]
            )
            lines.append(f"• {name} ({r['role']}) — {r['status']} [ID: {r['id']}]")
        return "\n".join(lines)

    if not user_id:
        return f"Necesito user_id para la acción '{action}'."

    try:
        user_uuid = uuid.UUID(str(user_id))
    except ValueError:
        return "ID de usuario inválido."

    target = await db.pool.fetchrow(
        "SELECT id, email, status, role FROM users WHERE id = $1 AND tenant_id = $2",
        user_uuid,
        tenant_id,
    )
    if not target:
        return f"No encontré el usuario con ID {user_id}."

    if action == "approve":
        if target["status"] == "active":
            return f"El usuario {target['email']} ya está activo."
        await db.pool.execute(
            "UPDATE users SET status = 'active', updated_at = NOW() WHERE id = $1 AND tenant_id = $2",
            user_uuid,
            tenant_id,
        )
        await _nova_emit(
            "RECORD_UPDATED",
            {"entity": "user", "user_id": str(user_uuid), "tenant_id": tenant_id},
        )
        logger.info(f"Nova: gestionar_usuarios approve → {user_id}")
        return f"✅ Usuario {target['email']} aprobado. Ahora puede acceder al sistema."

    if action == "suspend":
        if target["status"] == "suspended":
            return f"El usuario {target['email']} ya está suspendido."
        await db.pool.execute(
            "UPDATE users SET status = 'suspended', updated_at = NOW() WHERE id = $1 AND tenant_id = $2",
            user_uuid,
            tenant_id,
        )
        await _nova_emit(
            "RECORD_UPDATED",
            {"entity": "user", "user_id": str(user_uuid), "tenant_id": tenant_id},
        )
        logger.info(f"Nova: gestionar_usuarios suspend → {user_id}")
        return f"⚠️ Usuario {target['email']} suspendido. No podrá acceder hasta que se apruebe nuevamente."

    return f"Acción '{action}' no reconocida. Usá: list, approve o suspend."


async def _gestionar_obra_social(args: Dict, tenant_id: int, user_role: str) -> str:
    """CRUD de obras sociales / seguros. Solo CEO."""
    if user_role != "ceo":
        return _role_error("gestionar_obra_social", ["ceo"])

    action = args.get("action", "list")
    provider_id = args.get("provider_id")
    name = args.get("name")
    coverage_details = args.get("coverage_details")

    if action == "list":
        rows = await db.pool.fetch(
            """
            SELECT id, provider_name, status, is_active, is_prepaid,
                   default_copay_percent, requires_copay, sort_order
            FROM tenant_insurance_providers
            WHERE tenant_id = $1
            ORDER BY sort_order, provider_name
            """,
            tenant_id,
        )
        if not rows:
            return "No hay obras sociales registradas."
        lines = ["Obras sociales:"]
        for r in rows:
            active = "activa" if r["is_active"] else "inactiva"
            copay = " (requiere copago)" if r["requires_copay"] else ""
            prepaid = " (prepaga)" if r.get("is_prepaid") else ""
            lines.append(
                f"• [{r['id']}] {r['provider_name']}{prepaid} — {r['status']} [{active}]{copay}"
            )
        return "\n".join(lines)

    if action == "create":
        if not name:
            return "Necesito name para crear la obra social."
        # Migration 034: coverage_by_treatment (JSONB) replaces restrictions.
        # Nova's quick-create path stores no per-treatment detail by default;
        # the CEO must use the Clinics UI to configure full coverage.
        new_id = await db.pool.fetchval(
            """
            INSERT INTO tenant_insurance_providers
              (tenant_id, provider_name, status, coverage_by_treatment, is_active,
               requires_copay, sort_order, created_at, updated_at)
            VALUES ($1, $2, 'accepted', '{}'::jsonb, true, true, 0, NOW(), NOW())
            RETURNING id
            """,
            tenant_id,
            name,
        )
        await _nova_emit(
            "RECORD_UPDATED",
            {
                "entity": "insurance_provider",
                "provider_id": new_id,
                "tenant_id": tenant_id,
            },
        )
        logger.info(f"Nova: gestionar_obra_social create → {new_id}")
        return f"✅ Obra social '{name}' creada (ID: {new_id}). Configurá la cobertura por tratamiento desde la página de Clínicas."

    if not provider_id:
        return f"Necesito provider_id para la acción '{action}'."

    existing = await db.pool.fetchrow(
        "SELECT id, provider_name, is_active FROM tenant_insurance_providers WHERE id = $1 AND tenant_id = $2",
        int(provider_id),
        tenant_id,
    )
    if not existing:
        return f"No encontré la obra social con ID {provider_id}."

    if action == "update":
        set_parts = []
        values = []
        idx = 1
        if name:
            set_parts.append(f"provider_name = ${idx}")
            values.append(name)
            idx += 1
        # Nova's quick-update no longer supports per-treatment coverage via a
        # free-text field (migration 034 requires structured JSONB). The CEO
        # should edit coverage from the Clinics UI. coverage_details arg is
        # silently ignored here on purpose to avoid corrupting the JSONB.
        if coverage_details is not None:
            logger.info(
                "Nova: coverage_details ignorado en update de obra social — "
                "requiere edición estructurada desde la UI de Clínicas"
            )
        if not set_parts:
            return "No se especificó ningún campo a actualizar."
        set_parts.append("updated_at = NOW()")
        values.extend([int(provider_id), tenant_id])
        await db.pool.execute(
            f"UPDATE tenant_insurance_providers SET {', '.join(set_parts)} WHERE id = ${idx} AND tenant_id = ${idx + 1}",
            *values,
        )
        await _nova_emit(
            "RECORD_UPDATED",
            {
                "entity": "insurance_provider",
                "provider_id": provider_id,
                "tenant_id": tenant_id,
            },
        )
        logger.info(f"Nova: gestionar_obra_social update → {provider_id}")
        return f"✅ Obra social '{existing['provider_name']}' actualizada."

    if action == "toggle":
        new_state = not existing["is_active"]
        await db.pool.execute(
            "UPDATE tenant_insurance_providers SET is_active = $1, updated_at = NOW() WHERE id = $2 AND tenant_id = $3",
            new_state,
            int(provider_id),
            tenant_id,
        )
        await _nova_emit(
            "RECORD_UPDATED",
            {
                "entity": "insurance_provider",
                "provider_id": provider_id,
                "tenant_id": tenant_id,
            },
        )
        state_str = "activada" if new_state else "desactivada"
        logger.info(f"Nova: gestionar_obra_social toggle → {provider_id} → {new_state}")
        return f"✅ Obra social '{existing['provider_name']}' {state_str}."

    if action == "delete":
        await db.pool.execute(
            "DELETE FROM tenant_insurance_providers WHERE id = $1 AND tenant_id = $2",
            int(provider_id),
            tenant_id,
        )
        await _nova_emit(
            "RECORD_UPDATED",
            {
                "entity": "insurance_provider",
                "provider_id": provider_id,
                "tenant_id": tenant_id,
            },
        )
        logger.info(f"Nova: gestionar_obra_social delete → {provider_id}")
        return f"✅ Obra social '{existing['provider_name']}' eliminada."

    return (
        f"Acción '{action}' no reconocida. Usá: list, create, update, toggle o delete."
    )


async def _generar_pdf_liquidacion(args: Dict, tenant_id: int, user_role: str) -> str:
    """Genera el PDF de una liquidación profesional. Solo CEO."""
    if user_role != "ceo":
        return _role_error("generar_pdf_liquidacion", ["ceo"])

    liquidation_id_raw = args.get("liquidation_id")
    if not liquidation_id_raw:
        return "Necesito liquidation_id para generar el PDF."

    try:
        liquidation_id = int(liquidation_id_raw)
    except (ValueError, TypeError):
        return "liquidation_id debe ser un número entero."

    # Validar que la liquidación pertenece al tenant
    record = await db.pool.fetchrow(
        "SELECT id FROM liquidation_records WHERE id = $1 AND tenant_id = $2",
        liquidation_id,
        tenant_id,
    )
    if not record:
        return f"No encontré la liquidación con ID {liquidation_id}."

    try:
        from services.liquidation_pdf_service import generate_liquidation_pdf

        pdf_path = await generate_liquidation_pdf(db.pool, liquidation_id, tenant_id)
        if not pdf_path:
            return "Error generando el PDF de la liquidación."

        await _nova_emit(
            "BILLING_UPDATED",
            {"liquidation_id": liquidation_id, "tenant_id": tenant_id},
        )

        logger.info(f"Nova: generar_pdf_liquidacion → {pdf_path}")
        return f"✅ PDF de liquidación generado correctamente.\nRuta: {pdf_path}"

    except Exception as e:
        logger.error(f"_generar_pdf_liquidacion error: {e}", exc_info=True)
        return f"Error generando el PDF: {str(e)}"


async def _enviar_liquidacion_email(args: Dict, tenant_id: int, user_role: str) -> str:
    """Genera y envía el PDF de una liquidación por email. Solo CEO."""
    if user_role != "ceo":
        return _role_error("enviar_liquidacion_email", ["ceo"])

    liquidation_id_raw = args.get("liquidation_id")
    email = args.get("email")

    if not liquidation_id_raw:
        return "Necesito liquidation_id para enviar la liquidación."

    try:
        liquidation_id = int(liquidation_id_raw)
    except (ValueError, TypeError):
        return "liquidation_id debe ser un número entero."

    try:
        # Validar y obtener email del profesional
        record = await db.pool.fetchrow(
            """
            SELECT lr.*, p.email AS professional_email
            FROM liquidation_records lr
            JOIN professionals p ON p.id = lr.professional_id AND p.tenant_id = lr.tenant_id
            WHERE lr.id = $1 AND lr.tenant_id = $2
            """,
            liquidation_id,
            tenant_id,
        )
        if not record:
            return f"No encontré la liquidación con ID {liquidation_id}."

        to_email = email or record.get("professional_email")
        if not to_email:
            return "El profesional no tiene email registrado. Proporcioná un email de destino."

        from services.liquidation_pdf_service import (
            gather_liquidation_pdf_data,
            generate_liquidation_pdf,
            render_liquidation_email_html,
        )

        pdf_path = await generate_liquidation_pdf(db.pool, liquidation_id, tenant_id)
        if not pdf_path:
            return "Error generando el PDF de la liquidación."

        data = await gather_liquidation_pdf_data(db.pool, liquidation_id, tenant_id)
        if not data:
            return "No se pudo obtener los datos de la liquidación."

        email_html = render_liquidation_email_html(data)

        from email_service import EmailService
        import asyncio as _asyncio

        email_svc = EmailService()
        await _asyncio.to_thread(
            lambda: email_svc.send_liquidation_email(
                to_email=to_email,
                pdf_path=pdf_path,
                professional_name=data["professional"]["full_name"],
                clinic_name=data["clinic"]["name"],
                period_label=data["period"]["label"],
                payout_amount=data["summary"]["payout_amount"],
                html_body=email_html,
            )
        )

        await _nova_emit(
            "BILLING_UPDATED",
            {"liquidation_id": liquidation_id, "tenant_id": tenant_id},
        )

        logger.info(f"Nova: enviar_liquidacion_email → {to_email}")
        return f"✅ Liquidación enviada a {to_email} para {data['professional']['full_name']}."

    except Exception as e:
        logger.error(f"_enviar_liquidacion_email error: {e}", exc_info=True)
        return f"Error enviando la liquidación: {str(e)}"


async def _sincronizar_turnos_presupuesto(
    args: Dict, tenant_id: int, user_role: str
) -> str:
    """Sincroniza turnos no vinculados al plan de tratamiento."""
    if user_role not in ("ceo", "secretary"):
        return _role_error("sincronizar_turnos_presupuesto", ["ceo", "secretary"])

    plan_id = args.get("plan_id")
    if not plan_id:
        return "Necesito plan_id para sincronizar los turnos."

    try:
        # Obtener plan y patient_id
        plan = await db.pool.fetchrow(
            "SELECT id, patient_id, name FROM treatment_plans WHERE id = $1 AND tenant_id = $2",
            plan_id,
            tenant_id,
        )
        if not plan:
            return f"No encontré el plan con ID {plan_id}."

        patient_id = plan["patient_id"]

        # Buscar turnos del paciente no vinculados a ningún pago del plan
        # (turnos con billing_amount > 0 y payment_status paid/partial que no tienen
        #  entrada en treatment_plan_payments para este plan)
        unlinked = await db.pool.fetch(
            """
            SELECT a.id, a.appointment_datetime, a.billing_amount, a.payment_status,
                   a.payment_receipt_data, a.billing_notes,
                   tt.name AS treatment_name, tt.code AS treatment_code
            FROM appointments a
            LEFT JOIN treatment_types tt ON tt.code = a.appointment_type AND tt.tenant_id = a.tenant_id
            WHERE a.patient_id = $1
              AND a.tenant_id = $2
              AND a.billing_amount > 0
              AND a.payment_status IN ('paid', 'partial')
              AND NOT EXISTS (
                  SELECT 1 FROM treatment_plan_payments tpp
                  WHERE tpp.appointment_id = a.id AND tpp.plan_id = $3
              )
            ORDER BY a.appointment_datetime
            """,
            patient_id,
            tenant_id,
            plan_id,
        )

        if not unlinked:
            return f"No hay turnos pagados sin vincular para el plan *{plan['name']}*."

        linked_count = 0
        total_migrated = 0.0

        for appt in unlinked:
            amount = float(appt["billing_amount"] or 0)
            if amount <= 0:
                continue

            # Buscar si ya hay un ítem con el mismo treatment_code en el plan
            existing_item = None
            if appt.get("treatment_code"):
                existing_item = await db.pool.fetchrow(
                    """
                    SELECT id FROM treatment_plan_items
                    WHERE plan_id = $1 AND tenant_id = $2 AND treatment_type_code = $3
                    LIMIT 1
                    """,
                    plan_id,
                    tenant_id,
                    appt["treatment_code"],
                )

            # Crear ítem si no existe
            if not existing_item and appt.get("treatment_code"):
                item_id = str(uuid.uuid4())
                max_order = await db.pool.fetchval(
                    "SELECT COALESCE(MAX(sort_order), 0) FROM treatment_plan_items WHERE plan_id = $1 AND tenant_id = $2",
                    plan_id,
                    tenant_id,
                )
                await db.pool.execute(
                    """
                    INSERT INTO treatment_plan_items
                      (id, tenant_id, plan_id, treatment_type_code, custom_description, estimated_price, sort_order, status, created_at, updated_at)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, 'completed', NOW(), NOW())
                    """,
                    item_id,
                    tenant_id,
                    plan_id,
                    appt["treatment_code"],
                    appt.get("treatment_name"),
                    amount,
                    (max_order or 0) + 1,
                )

            # Migrar pago verificado al plan
            payment_id = str(uuid.uuid4())
            apt_dt = appt["appointment_datetime"]
            payment_date = apt_dt.date() if hasattr(apt_dt, "date") else apt_dt
            await db.pool.execute(
                """
                INSERT INTO treatment_plan_payments
                  (id, tenant_id, plan_id, amount, payment_method, payment_date, appointment_id, receipt_data, notes, created_at)
                VALUES ($1, $2, $3, $4, 'transfer', $5, $6, $7, $8, NOW())
                """,
                payment_id,
                tenant_id,
                plan_id,
                amount,
                payment_date,
                appt["id"],
                appt.get("payment_receipt_data"),
                appt.get("billing_notes") or f"Migrado desde turno {appt['id']}",
            )

            linked_count += 1
            total_migrated += amount

        # Recalcular estimated_total del plan
        await db.pool.execute(
            """
            UPDATE treatment_plans
            SET estimated_total = (
                SELECT COALESCE(SUM(estimated_price), 0)
                FROM treatment_plan_items
                WHERE plan_id = $1 AND tenant_id = $2
            ), updated_at = NOW()
            WHERE id = $1 AND tenant_id = $2
            """,
            plan_id,
            tenant_id,
        )

        await _nova_emit(
            "TREATMENT_PLAN_UPDATED",
            {"plan_id": plan_id, "tenant_id": tenant_id, "patient_id": patient_id},
        )

        logger.info(
            f"Nova: sincronizar_turnos_presupuesto → plan {plan_id}, {linked_count} turnos, ${total_migrated:,.0f}"
        )
        return (
            f"✅ Sincronización completada para el plan *{plan['name']}*:\n"
            f"• {linked_count} turno(s) vinculados\n"
            f"• {_fmt_money(total_migrated)} migrados como pagos al plan"
        )

    except Exception as e:
        logger.error(f"_sincronizar_turnos_presupuesto error: {e}", exc_info=True)
        return f"Error sincronizando turnos: {str(e)}"


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
        "SELECT first_name, last_name, phone_number FROM patients WHERE id = $1 AND tenant_id = $2",
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

    # Audit log (TIER 3 cap.3 Phase B)
    try:
        from services.audit_log import log_appointment_mutation as _audit

        await _audit(
            pool=db.pool,
            tenant_id=tenant_id,
            appointment_id=str(appt_id),
            action="created",
            actor_type="staff_user",
            actor_id="nova_voice",
            before_values=None,
            after_values={
                "patient_id": int(pid),
                "professional_id": prof_id,
                "appointment_datetime": appt_dt.isoformat()
                if hasattr(appt_dt, "isoformat")
                else str(appt_dt),
                "duration_minutes": duration,
                "appointment_type": treatment_type,
                "status": "scheduled",
                "source": "nova",
                "notes": args.get("notes"),
            },
            source_channel="nova_voice",
            reason=None,
        )
    except Exception as _audit_err:
        import logging as _lg

        _lg.getLogger("nova_tools").warning(
            f"audit_log nova agendar failed (non-blocking): {_audit_err}"
        )

    patient_name = f"{patient['first_name']} {patient['last_name'] or ''}".strip()
    patient_phone = patient.get("phone_number") or ""
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
            "patient_name": patient_name,
            "appointment_datetime": appt_dt.isoformat()
            if hasattr(appt_dt, "isoformat")
            else str(appt_dt),
            "appointment_type": tt_name or treatment_type,
            "professional_name": prof_name.strip() if prof_id and prof_name else None,
        },
    )

    # Check if this was a recovered lead and fire Telegram notification
    try:
        if patient_phone:
            _recovery_count = await db.pool.fetchval(
                "SELECT recovery_touch_count FROM chat_conversations WHERE tenant_id = $1 AND external_user_id = $2 AND recovery_touch_count > 0",
                tenant_id,
                patient_phone,
            )
            if _recovery_count:
                from services.telegram_notifier import fire_telegram_notification

                fire_telegram_notification(
                    "LEAD_RECOVERY_CONVERSION",
                    {
                        "tenant_id": tenant_id,
                        "patient_name": patient_name,
                        "phone": patient_phone,
                        "appointment_datetime": appt_dt.isoformat()
                        if hasattr(appt_dt, "isoformat")
                        else str(appt_dt),
                        "treatment_type": tt_name or treatment_type or "consulta",
                        "recovery_touch_count": _recovery_count,
                        "hours_to_convert": "?",
                    },
                    tenant_id,
                )
    except Exception:
        pass  # Non-blocking

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

    # Audit log (TIER 3 cap.3 Phase B)
    try:
        from services.audit_log import log_appointment_mutation as _audit

        await _audit(
            pool=db.pool,
            tenant_id=tenant_id,
            appointment_id=str(appt_uuid),
            action="cancelled",
            actor_type="staff_user",
            actor_id="nova_voice",
            before_values={"status": row["status"]},
            after_values={
                "status": "cancelled",
                "cancellation_reason": reason,
                "cancellation_by": "nova",
            },
            source_channel="nova_voice",
            reason=reason,
        )
    except Exception as _audit_err:
        import logging as _lg

        _lg.getLogger("nova_tools").warning(
            f"audit_log nova cancelar failed (non-blocking): {_audit_err}"
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
            f"Pago plan '{plan['name']}' - {method_labels.get(method, method)}",
        )
    except Exception as acc_err:
        logger.warning(f"accounting_transaction sync failed (non-fatal): {acc_err}")

    # FIX C7 — Auto-complete plan if fully paid
    try:
        total_paid = await db.pool.fetchval(
            "SELECT COALESCE(SUM(amount), 0) FROM treatment_plan_payments WHERE plan_id = $1 AND tenant_id = $2",
            plan_uuid,
            tenant_id,
        )
        if float(total_paid) >= float(plan["approved_total"]):
            await db.pool.execute(
                "UPDATE treatment_plans SET status = 'completed', updated_at = NOW() WHERE id = $1 AND tenant_id = $2",
                plan_uuid,
                tenant_id,
            )
            logger.info(
                f"Plan {plan_uuid} auto-completed (total_paid={total_paid} >= approved={plan['approved_total']})"
            )
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


async def _facturacion_pendiente(tenant_id: int, paciente: str = None) -> str:
    # Build patient filter
    patient_filter = ""
    params = [tenant_id]
    if paciente and paciente.strip():
        patient_filter = (
            " AND (p.first_name || ' ' || COALESCE(p.last_name, '')) ILIKE $2"
        )
        params.append(f"%{paciente.strip()}%")

    # Turnos con facturación pendiente (seña pendiente o sin pago)
    # Include both 'completed' AND 'scheduled'/'confirmed' with pending payment
    rows = await db.pool.fetch(
        f"""
        SELECT a.id, a.appointment_datetime, a.appointment_type, a.status as apt_status,
               a.payment_status, a.billing_amount,
               p.first_name || ' ' || COALESCE(p.last_name, '') AS patient_name,
               tt.base_price
        FROM appointments a
        JOIN patients p ON p.id = a.patient_id
        LEFT JOIN treatment_types tt ON tt.code = a.appointment_type AND tt.tenant_id = a.tenant_id
        WHERE a.tenant_id = $1
          AND (
              (a.status = 'completed' AND (a.payment_status = 'pending' OR a.payment_status IS NULL))
              OR (a.status IN ('scheduled', 'confirmed') AND a.payment_status IN ('pending', 'partial'))
          )
          AND a.plan_item_id IS NULL
          {patient_filter}
        ORDER BY a.appointment_datetime DESC
        LIMIT 20
        """,
        *params,
    )

    # Planes con saldo pendiente
    plan_params = [tenant_id]
    plan_filter = ""
    if paciente and paciente.strip():
        plan_filter = (
            " AND (pat.first_name || ' ' || COALESCE(pat.last_name, '')) ILIKE $2"
        )
        plan_params.append(f"%{paciente.strip()}%")

    plans = await db.pool.fetch(
        f"""
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
          {plan_filter}
        ORDER BY tp.approved_total - COALESCE(payments.total_paid, 0) DESC
        LIMIT 20
        """,
        *plan_params,
    )

    patient_label = f" de {paciente}" if paciente else ""

    if not rows and not plans:
        return f"No hay facturación pendiente{patient_label}. Todo al día."

    lines = []
    if rows:
        lines.append(f"Facturación pendiente{patient_label} ({len(rows)} turnos):")
        for r in rows:
            dt = _fmt_date(r["appointment_datetime"])
            amount = r.get("billing_amount") or r.get("base_price")
            price = _fmt_money(amount) if amount else "sin precio"
            status = r.get("payment_status") or "sin pago"
            apt_st = r.get("apt_status") or ""
            lines.append(
                f"• {r['patient_name']} — {r['appointment_type']} ({dt}) — {price} — estado pago: {status} — turno: {apt_st}"
            )
    if plans:
        if lines:
            lines.append("")
        lines.append(
            f"Planes con saldo pendiente{patient_label} ({len(plans)} planes):"
        )
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
            COALESCE(SUM(billing_amount) FILTER (WHERE payment_status = 'paid'), 0) AS facturado_turnos
        FROM appointments
        WHERE tenant_id = $1
          AND appointment_datetime::date BETWEEN $2 AND $3
        """,
        tenant_id,
        week_start,
        week_end,
    )

    # Plan payments for the same week
    plan_revenue = (
        await db.pool.fetchval(
            """
        SELECT COALESCE(SUM(amount), 0) FROM treatment_plan_payments
        WHERE tenant_id = $1 AND payment_date::date BETWEEN $2 AND $3
        """,
            tenant_id,
            week_start,
            week_end,
        )
        or 0
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
    revenue = float(stats["facturado_turnos"] or 0) + float(plan_revenue)
    cancel_rate = f"{(cancelled / total * 100):.1f}%" if total > 0 else "0%"

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
            COALESCE(SUM(billing_amount) FILTER (WHERE payment_status = 'paid'), 0) AS facturado_turnos
        FROM appointments
        WHERE professional_id = $1 AND tenant_id = $2
          AND appointment_datetime::date >= $3
        """,
        int(prof_id),
        tenant_id,
        since,
    )

    # Plan payments for this professional's patients
    plan_revenue = (
        await db.pool.fetchval(
            """
        SELECT COALESCE(SUM(tpp.amount), 0)
        FROM treatment_plan_payments tpp
        JOIN treatment_plans tp ON tp.id = tpp.plan_id AND tp.tenant_id = tpp.tenant_id
        WHERE tp.professional_id = $1 AND tp.tenant_id = $2
          AND tpp.payment_date::date >= $3
        """,
            int(prof_id),
            tenant_id,
            since,
        )
        or 0
    )

    total = stats["total"] or 0
    completed = stats["completados"] or 0
    cancelled = stats["cancelados"] or 0
    unique_patients = stats["pacientes_unicos"] or 0
    revenue = float(stats["facturado_turnos"] or 0) + float(plan_revenue)
    cancel_rate = f"{(cancelled / total * 100):.1f}%" if total > 0 else "0%"

    period_labels = {"week": "la semana", "month": "el mes", "quarter": "el trimestre"}
    prof_name = f"Dr. {prof['first_name'] or ''} {prof['last_name'] or ''}".strip()
    if prof_name == "Dr.":
        prof_name = "Dr. (sin nombre)"

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
        "roi": "ROI Dashboard",
        "presupuestos": "Presupuestos",
        "finanzas": "Centro Financiero",
        "liquidaciones": "Liquidaciones",
        "fichas": "Fichas Digitales",
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
# K2. ENGRAM — PERSISTENT MEMORY IMPLEMENTATIONS
# =============================================================================


async def _guardar_memoria(args: Dict, tenant_id: int, user_role: str) -> str:
    """
    Save a memory to nova_memories. Supports upsert via topic_key.
    Caller may inject _source_channel and _created_by into args before dispatch.
    """
    titulo = args.get("titulo", "").strip()
    contenido = args.get("contenido", "").strip()
    tipo = args.get("tipo", "general")
    topic_key = args.get("topic_key") or None
    source_channel = args.pop("_source_channel", "web")
    created_by = args.pop("_created_by", user_role or "nova")

    if not titulo or not contenido:
        return "Necesito al menos 'titulo' y 'contenido' para guardar una memoria."

    try:
        if topic_key:
            # Upsert: check if a memory with this topic_key already exists
            existing = await db.pool.fetchrow(
                "SELECT id FROM nova_memories WHERE tenant_id = $1 AND topic_key = $2",
                tenant_id,
                topic_key,
            )
            if existing:
                await db.pool.execute(
                    """
                    UPDATE nova_memories
                    SET title = $1, content = $2, type = $3, updated_at = NOW()
                    WHERE id = $4
                    """,
                    titulo,
                    contenido,
                    tipo,
                    existing["id"],
                )
                return f"Memoria actualizada (topic: {topic_key}): {titulo}"

        # INSERT new memory
        mem_id = await db.pool.fetchval(
            """
            INSERT INTO nova_memories
                (tenant_id, type, title, content, topic_key, created_by, source_channel)
            VALUES ($1, $2, $3, $4, $5, $6, $7)
            RETURNING id
            """,
            tenant_id,
            tipo,
            titulo,
            contenido,
            topic_key,
            created_by,
            source_channel,
        )
        return f"Memoria guardada (ID {mem_id}): {titulo}"

    except Exception as e:
        logger.error(f"_guardar_memoria error: {e}", exc_info=True)
        return f"Error al guardar memoria: {str(e)}"


async def _buscar_memorias(args: Dict, tenant_id: int) -> str:
    """Search nova_memories by ILIKE on title + content. Optional type filter."""
    query = args.get("query", "").strip()
    tipo = args.get("tipo") or None
    limite = min(int(args.get("limite", 10)), 50)

    if not query:
        return "Necesito un texto de búsqueda."

    try:
        pattern = f"%{query}%"
        if tipo:
            rows = await db.pool.fetch(
                """
                SELECT id, type, title, content, topic_key, source_channel, updated_at
                FROM nova_memories
                WHERE tenant_id = $1
                  AND type = $2
                  AND (title ILIKE $3 OR content ILIKE $3)
                ORDER BY updated_at DESC
                LIMIT $4
                """,
                tenant_id,
                tipo,
                pattern,
                limite,
            )
        else:
            rows = await db.pool.fetch(
                """
                SELECT id, type, title, content, topic_key, source_channel, updated_at
                FROM nova_memories
                WHERE tenant_id = $1
                  AND (title ILIKE $2 OR content ILIKE $2)
                ORDER BY updated_at DESC
                LIMIT $3
                """,
                tenant_id,
                pattern,
                limite,
            )

        if not rows:
            return f"No encontré memorias que coincidan con '{query}'."

        lines = [f"Memorias encontradas ({len(rows)}):"]
        for r in rows:
            fecha = r["updated_at"].strftime("%d/%m/%Y") if r["updated_at"] else "—"
            key_info = f" [{r['topic_key']}]" if r.get("topic_key") else ""
            lines.append(
                f"\n• [{r['type']}]{key_info} {r['title']} ({fecha})\n  {r['content'][:200]}{'...' if len(r['content']) > 200 else ''}"
            )
        return "\n".join(lines)

    except Exception as e:
        logger.error(f"_buscar_memorias error: {e}", exc_info=True)
        return f"Error al buscar memorias: {str(e)}"


async def _ver_contexto_memorias(args: Dict, tenant_id: int) -> str:
    """Return recent memories ordered by updated_at DESC for session context recovery."""
    limite = min(int(args.get("limite", 10)), 50)
    tipo = args.get("tipo") or None

    try:
        if tipo:
            rows = await db.pool.fetch(
                """
                SELECT id, type, title, content, topic_key, source_channel, updated_at
                FROM nova_memories
                WHERE tenant_id = $1 AND type = $2
                ORDER BY updated_at DESC
                LIMIT $3
                """,
                tenant_id,
                tipo,
                limite,
            )
        else:
            rows = await db.pool.fetch(
                """
                SELECT id, type, title, content, topic_key, source_channel, updated_at
                FROM nova_memories
                WHERE tenant_id = $1
                ORDER BY updated_at DESC
                LIMIT $2
                """,
                tenant_id,
                limite,
            )

        if not rows:
            return "No hay memorias guardadas todavía."

        lines = [f"Contexto de memorias recientes ({len(rows)}):"]
        for r in rows:
            fecha = (
                r["updated_at"].strftime("%d/%m/%Y %H:%M") if r["updated_at"] else "—"
            )
            key_info = f" [{r['topic_key']}]" if r.get("topic_key") else ""
            lines.append(
                f"\n• [{r['type']}]{key_info} {r['title']} — {fecha}\n  {r['content'][:300]}{'...' if len(r['content']) > 300 else ''}"
            )
        return "\n".join(lines)

    except Exception as e:
        logger.error(f"_ver_contexto_memorias error: {e}", exc_info=True)
        return f"Error al recuperar contexto: {str(e)}"


async def _ver_memorias_paciente(args: Dict, tenant_id: int) -> str:
    """Get patient memories/observations by patient_id."""
    patient_id = args.get("patient_id")
    if not patient_id:
        return "Necesito el ID del paciente."
    try:
        patient = await db.pool.fetchrow(
            "SELECT phone_number, first_name, last_name FROM patients WHERE id = $1 AND tenant_id = $2",
            int(patient_id),
            tenant_id,
        )
        if not patient:
            return "No encontré a ese paciente."
        phone = patient["phone_number"]
        if not phone:
            return "El paciente no tiene teléfono registrado (necesario para memorias)."

        from services.patient_memory import get_memories

        memories = await get_memories(db.pool, phone, tenant_id)

        name = f"{patient['first_name']} {patient.get('last_name', '')}".strip()
        if not memories:
            return f"No hay memorias guardadas para {name}."

        lines = [f"Memorias de {name} ({len(memories)} registros):"]
        for m in memories:
            cat = m.get("category", "general")
            text = m.get("memory", "")
            imp = m.get("importance", 5)
            lines.append(f"• [{cat}] (imp:{imp}) {text[:200]}")
        return "\n".join(lines)
    except Exception as e:
        logger.error(f"_ver_memorias_paciente error: {e}", exc_info=True)
        return f"Error al buscar memorias: {str(e)[:200]}"


async def _agregar_memoria_paciente(args: Dict, tenant_id: int) -> str:
    """Add a memory/observation about a patient by patient_id."""
    patient_id = args.get("patient_id")
    memoria = args.get("memoria", "").strip()
    categoria = args.get("categoria", "general")
    importancia = int(args.get("importancia", 7))

    if not patient_id or not memoria:
        return "Necesito patient_id y memoria."

    try:
        patient = await db.pool.fetchrow(
            "SELECT phone_number, first_name, last_name FROM patients WHERE id = $1 AND tenant_id = $2",
            int(patient_id),
            tenant_id,
        )
        if not patient:
            return "No encontré a ese paciente."
        phone = patient["phone_number"]
        if not phone:
            return "El paciente no tiene teléfono registrado."

        from services.patient_memory import add_manual_memory

        await add_manual_memory(
            db.pool, phone, tenant_id, memoria, categoria, importancia
        )

        name = f"{patient['first_name']} {patient.get('last_name', '')}".strip()
        return f"Memoria guardada para {name}: [{categoria}] {memoria}"
    except Exception as e:
        logger.error(f"_agregar_memoria_paciente error: {e}", exc_info=True)
        return f"Error guardando memoria: {str(e)[:200]}"


# =============================================================================
# N. Plantillas WhatsApp
# =============================================================================


async def _listar_plantillas(tenant_id: int) -> str:
    """List approved WhatsApp templates from YCloud for this tenant."""
    try:
        from core.credentials import get_tenant_credential, YCLOUD_API_KEY
        import httpx

        api_key = await get_tenant_credential(tenant_id, YCLOUD_API_KEY)
        if not api_key:
            return "No hay API key de YCloud configurada para esta clínica."

        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                "https://api.ycloud.com/v2/whatsapp/templates",
                params={"limit": 50},
                headers={"X-API-Key": api_key},
            )
            if resp.status_code != 200:
                return f"Error al consultar templates: HTTP {resp.status_code}"

            items = resp.json().get("items", [])

        approved = [t for t in items if t.get("status") == "APPROVED"]
        if not approved:
            return "No hay plantillas aprobadas en YCloud."

        import re

        lines = [f"Plantillas aprobadas ({len(approved)}):"]
        for t in approved:
            name = t.get("name", "?")
            lang = t.get("language", "?")
            category = t.get("category", "?")
            # Extract variable names from all components
            var_names = []
            for comp in t.get("components", []):
                text = comp.get("text", "")
                var_names.extend(re.findall(r"\{\{(\w+)\}\}", text))
            vars_str = ", ".join(var_names) if var_names else "sin variables"
            lines.append(f"\n• {name} ({lang}) — {category}\n  Variables: {vars_str}")

        return "\n".join(lines)

    except Exception as e:
        logger.error(f"_listar_plantillas error: {e}", exc_info=True)
        return f"Error listando plantillas: {str(e)[:200]}"


async def _enviar_plantilla(args: Dict, tenant_id: int, user_role: str) -> str:
    """Send a WhatsApp template to a single patient."""
    if user_role not in ("ceo", "secretary"):
        return "Solo CEO o secretaria pueden enviar plantillas."

    template_name = (args.get("template_name") or "").strip()
    if not template_name:
        return "Necesito el nombre de la plantilla. Usá listar_plantillas para ver las disponibles."

    # Resolve patient
    patient_id = args.get("patient_id")
    patient_name = args.get("patient_name")
    phone = args.get("phone")

    try:
        patient = None
        if patient_id:
            patient = await db.pool.fetchrow(
                "SELECT id, phone_number, first_name, last_name FROM patients WHERE id = $1 AND tenant_id = $2",
                int(patient_id),
                tenant_id,
            )
        elif patient_name:
            patient = await db.pool.fetchrow(
                """SELECT id, phone_number, first_name, last_name FROM patients
                   WHERE tenant_id = $1 AND status = 'active'
                     AND (first_name ILIKE $2 OR last_name ILIKE $2 OR (first_name || ' ' || last_name) ILIKE $2)
                   ORDER BY updated_at DESC LIMIT 1""",
                tenant_id,
                f"%{patient_name}%",
            )
        elif phone:
            patient = await db.pool.fetchrow(
                "SELECT id, phone_number, first_name, last_name FROM patients WHERE phone_number = $1 AND tenant_id = $2",
                phone,
                tenant_id,
            )

        if not patient:
            return "No encontré al paciente. Probá con buscar_paciente primero."

        target_phone = patient["phone_number"]
        if not target_phone:
            return f"El paciente {patient['first_name']} no tiene teléfono registrado."

        patient_display = (
            f"{patient['first_name']} {patient.get('last_name', '')}".strip()
        )

        # Send via the generic template sender
        result = await _generic_send_template(
            tenant_id=tenant_id,
            phone=target_phone,
            template_name=template_name,
            patient_name=patient_display,
            custom_vars=args.get("variables") or {},
            source="nova_manual",
        )

        if result["ok"]:
            return f"Plantilla '{template_name}' enviada a {patient_display} ({target_phone})."
        else:
            return f"Error enviando plantilla: {result['error']}"

    except Exception as e:
        logger.error(f"_enviar_plantilla error: {e}", exc_info=True)
        return f"Error: {str(e)[:200]}"


async def _enviar_plantilla_masiva(args: Dict, tenant_id: int, user_role: str) -> str:
    """Send a WhatsApp template to multiple patients matching filters."""
    if user_role != "ceo":
        return "Solo el CEO puede hacer envíos masivos de plantillas."

    template_name = (args.get("template_name") or "").strip()
    confirmar = args.get("confirmar", False)
    limite = min(int(args.get("limite", 50)), 200)

    if not template_name:
        return "Necesito el nombre de la plantilla. Usá listar_plantillas para ver las disponibles."

    try:
        # Build dynamic query with filters
        conditions = ["p.tenant_id = $1", "p.status = $2"]
        params: list = [tenant_id, args.get("estado", "active")]
        param_idx = 3

        # --- Filter: sin_turno_dias (no appointment in last X days) ---
        if args.get("sin_turno_dias"):
            days = int(args["sin_turno_dias"])
            conditions.append(f"""
                NOT EXISTS (
                    SELECT 1 FROM appointments a
                    WHERE a.patient_id = p.id AND a.tenant_id = $1
                      AND a.appointment_datetime >= (NOW() - INTERVAL '{days} days')
                      AND a.status NOT IN ('cancelled', 'no_show')
                )
            """)

        # --- Filter: ultimo_turno_hace_dias (last visit > X days ago) ---
        if args.get("ultimo_turno_hace_dias"):
            days = int(args["ultimo_turno_hace_dias"])
            conditions.append(f"""
                EXISTS (
                    SELECT 1 FROM appointments a
                    WHERE a.patient_id = p.id AND a.tenant_id = $1
                      AND a.status IN ('completed', 'confirmed', 'scheduled')
                ) AND NOT EXISTS (
                    SELECT 1 FROM appointments a
                    WHERE a.patient_id = p.id AND a.tenant_id = $1
                      AND a.appointment_datetime >= (NOW() - INTERVAL '{days} days')
                      AND a.status IN ('completed', 'confirmed', 'scheduled')
                )
            """)

        # --- Filter: nunca_agendo ---
        if args.get("nunca_agendo"):
            conditions.append("""
                NOT EXISTS (
                    SELECT 1 FROM appointments a
                    WHERE a.patient_id = p.id AND a.tenant_id = $1
                )
            """)

        # --- Filter: tratamiento ---
        if args.get("tratamiento"):
            conditions.append(f"""
                EXISTS (
                    SELECT 1 FROM appointments a
                    JOIN treatment_types tt ON tt.code = a.treatment_type AND tt.tenant_id = $1
                    WHERE a.patient_id = p.id AND a.tenant_id = $1
                      AND tt.name ILIKE ${param_idx}
                )
            """)
            params.append(f"%{args['tratamiento']}%")
            param_idx += 1

        # --- Filter: obra_social ---
        if args.get("obra_social"):
            conditions.append(f"p.insurance_provider ILIKE ${param_idx}")
            params.append(f"%{args['obra_social']}%")
            param_idx += 1

        # --- Filter: fuente ---
        if args.get("fuente"):
            conditions.append(f"p.first_touch_source ILIKE ${param_idx}")
            params.append(f"%{args['fuente']}%")
            param_idx += 1

        # --- Filter: edad_min / edad_max ---
        if args.get("edad_min"):
            conditions.append(
                f"p.birth_date <= (CURRENT_DATE - INTERVAL '{int(args['edad_min'])} years')"
            )
        if args.get("edad_max"):
            conditions.append(
                f"p.birth_date >= (CURRENT_DATE - INTERVAL '{int(args['edad_max'])} years')"
            )

        # --- Filter: genero ---
        if args.get("genero"):
            conditions.append(f"LOWER(p.gender) = ${param_idx}")
            params.append(args["genero"].lower())
            param_idx += 1

        # --- Filter: con_anamnesis ---
        if args.get("con_anamnesis") is not None:
            if args["con_anamnesis"]:
                conditions.append(
                    "EXISTS (SELECT 1 FROM medical_history mh WHERE mh.patient_id = p.id AND mh.anamnesis_completed_at IS NOT NULL)"
                )
            else:
                conditions.append(
                    "NOT EXISTS (SELECT 1 FROM medical_history mh WHERE mh.patient_id = p.id AND mh.anamnesis_completed_at IS NOT NULL)"
                )

        # --- Filter: urgencia ---
        if args.get("urgencia"):
            conditions.append(f"p.urgency_level = ${param_idx}")
            params.append(args["urgencia"])
            param_idx += 1

        # --- Filter: profesional / profesional_id ---
        if args.get("profesional_id"):
            conditions.append(f"""
                EXISTS (
                    SELECT 1 FROM appointments a
                    WHERE a.patient_id = p.id AND a.tenant_id = $1
                      AND a.professional_id = ${param_idx}
                )
            """)
            params.append(int(args["profesional_id"]))
            param_idx += 1
        elif args.get("profesional"):
            conditions.append(f"""
                EXISTS (
                    SELECT 1 FROM appointments a
                    JOIN professionals pr ON pr.id = a.professional_id
                    WHERE a.patient_id = p.id AND a.tenant_id = $1
                      AND (pr.first_name ILIKE ${param_idx} OR pr.last_name ILIKE ${param_idx})
                )
            """)
            params.append(f"%{args['profesional']}%")
            param_idx += 1

        # --- Filter: creado_desde / creado_hasta ---
        if args.get("creado_desde"):
            conditions.append(f"p.created_at >= ${param_idx}::date")
            params.append(args["creado_desde"])
            param_idx += 1
        if args.get("creado_hasta"):
            conditions.append(f"p.created_at <= ${param_idx}::date + INTERVAL '1 day'")
            params.append(args["creado_hasta"])
            param_idx += 1

        # --- Filter: sin_email ---
        if args.get("sin_email"):
            conditions.append("(p.email IS NULL OR p.email = '')")

        # --- Filter: con_deuda ---
        if args.get("con_deuda"):
            conditions.append("""
                EXISTS (
                    SELECT 1 FROM appointments a
                    WHERE a.patient_id = p.id AND a.tenant_id = $1
                      AND a.payment_status IN ('pending', 'partial')
                )
            """)

        # --- Filter: turno_cancelado_dias ---
        if args.get("turno_cancelado_dias"):
            days = int(args["turno_cancelado_dias"])
            conditions.append(f"""
                EXISTS (
                    SELECT 1 FROM appointments a
                    WHERE a.patient_id = p.id AND a.tenant_id = $1
                      AND a.status = 'cancelled'
                      AND a.appointment_datetime >= (NOW() - INTERVAL '{days} days')
                )
            """)

        # Exclude patients without phone
        conditions.append("p.phone_number IS NOT NULL")
        conditions.append("p.phone_number != ''")
        # Exclude minor placeholders (phone like %-M%)
        conditions.append("p.phone_number NOT LIKE '%-M%'")

        where_clause = " AND ".join(conditions)

        # COUNT first
        count_sql = f"SELECT COUNT(*) FROM patients p WHERE {where_clause}"
        total = await db.pool.fetchval(count_sql, *params)

        if not confirmar:
            # Preview mode — just show count
            filter_desc = _describe_filters(args)
            return (
                f"Encontré {total} pacientes que cumplen los filtros:\n{filter_desc}\n\n"
                f"Plantilla: {template_name}\n"
                f"Límite de envío: {limite}\n"
                f"Se enviarán a {min(total, limite)} pacientes.\n\n"
                f"¿Confirmo el envío? Decime 'sí, enviá' para proceder."
            )

        # SEND mode
        if total == 0:
            return "No hay pacientes que cumplan esos filtros."

        fetch_sql = f"""
            SELECT p.id, p.phone_number, p.first_name, p.last_name
            FROM patients p
            WHERE {where_clause}
            ORDER BY p.updated_at DESC
            LIMIT {limite}
        """
        patients = await db.pool.fetch(fetch_sql, *params)

        sent = 0
        errors = 0
        custom_vars = args.get("variables") or {}

        for pat in patients:
            pat_name = f"{pat['first_name']} {pat.get('last_name', '')}".strip()
            # Replace {nombre} placeholder in custom vars
            resolved_vars = {}
            for k, v in custom_vars.items():
                resolved_vars[k] = (
                    str(v).replace("{nombre}", pat_name) if isinstance(v, str) else v
                )

            result = await _generic_send_template(
                tenant_id=tenant_id,
                phone=pat["phone_number"],
                template_name=template_name,
                patient_name=pat_name,
                custom_vars=resolved_vars,
                source="nova_bulk",
            )

            if result["ok"]:
                sent += 1
            else:
                errors += 1
                logger.warning(
                    f"Bulk template error for {pat['phone_number']}: {result['error']}"
                )

            # Rate limit: ~1 msg/sec to avoid Meta throttling
            import asyncio

            await asyncio.sleep(1.0)

        return (
            f"Envío masivo completado:\n"
            f"• Enviados: {sent}\n"
            f"• Errores: {errors}\n"
            f"• Total procesados: {sent + errors} de {total} que cumplían los filtros"
        )

    except Exception as e:
        logger.error(f"_enviar_plantilla_masiva error: {e}", exc_info=True)
        return f"Error en envío masivo: {str(e)[:200]}"


def _describe_filters(args: Dict) -> str:
    """Build a human-readable description of applied filters."""
    parts = []
    if args.get("sin_turno_dias"):
        parts.append(f"• Sin turno en los últimos {args['sin_turno_dias']} días")
    if args.get("ultimo_turno_hace_dias"):
        parts.append(
            f"• Última visita hace más de {args['ultimo_turno_hace_dias']} días"
        )
    if args.get("nunca_agendo"):
        parts.append("• Nunca agendaron un turno")
    if args.get("tratamiento"):
        parts.append(f"• Tratamiento: {args['tratamiento']}")
    if args.get("obra_social"):
        parts.append(f"• Obra social: {args['obra_social']}")
    if args.get("fuente"):
        parts.append(f"• Fuente: {args['fuente']}")
    if args.get("edad_min") or args.get("edad_max"):
        rango = f"{args.get('edad_min', '?')}-{args.get('edad_max', '?')} años"
        parts.append(f"• Rango de edad: {rango}")
    if args.get("genero"):
        parts.append(f"• Género: {args['genero']}")
    if args.get("estado") and args["estado"] != "active":
        parts.append(f"• Estado: {args['estado']}")
    if args.get("con_anamnesis") is not None:
        parts.append(
            f"• {'Con' if args['con_anamnesis'] else 'Sin'} anamnesis completada"
        )
    if args.get("urgencia"):
        parts.append(f"• Urgencia: {args['urgencia']}")
    if args.get("profesional") or args.get("profesional_id"):
        parts.append(
            f"• Profesional: {args.get('profesional', args.get('profesional_id'))}"
        )
    if args.get("creado_desde"):
        parts.append(f"• Creado desde: {args['creado_desde']}")
    if args.get("creado_hasta"):
        parts.append(f"• Creado hasta: {args['creado_hasta']}")
    if args.get("sin_email"):
        parts.append("• Sin email registrado")
    if args.get("con_deuda"):
        parts.append("• Con deuda pendiente")
    if args.get("turno_cancelado_dias"):
        parts.append(
            f"• Cancelaron turno en los últimos {args['turno_cancelado_dias']} días"
        )
    return (
        "\n".join(parts)
        if parts
        else "• Sin filtros adicionales (todos los pacientes activos)"
    )


async def _generic_send_template(
    tenant_id: int,
    phone: str,
    template_name: str,
    patient_name: str = "",
    custom_vars: Dict[str, str] = None,
    source: str = "nova",
) -> Dict[str, Any]:
    """
    Generic template sender. Fetches template structure from YCloud,
    maps variables automatically, and sends.

    Returns: {"ok": True} or {"ok": False, "error": "..."}
    """
    try:
        from core.credentials import get_tenant_credential, YCLOUD_API_KEY
        from ycloud_client import YCloudClient
        import httpx
        import re

        api_key = await get_tenant_credential(tenant_id, YCLOUD_API_KEY)
        if not api_key:
            return {"ok": False, "error": "No YCloud API key"}

        # Resolve from_number
        business_number = await db.pool.fetchval(
            "SELECT bot_phone_number FROM tenants WHERE id = $1", tenant_id
        )
        if not business_number:
            from core.credentials import YCLOUD_WHATSAPP_NUMBER

            business_number = await get_tenant_credential(
                tenant_id, YCLOUD_WHATSAPP_NUMBER
            )

        # Fetch template from YCloud to get REAL structure
        real_lang = None
        tpl_components = None
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                "https://api.ycloud.com/v2/whatsapp/templates",
                params={"filter.name": template_name, "limit": 10},
                headers={"X-API-Key": api_key},
            )
            if resp.status_code == 200:
                items = resp.json().get("items", [])
                for tpl in items:
                    if (
                        tpl.get("status") == "APPROVED"
                        and tpl.get("name") == template_name
                    ):
                        real_lang = tpl.get("language")
                        tpl_components = tpl.get("components", [])
                        break

        if not real_lang:
            return {
                "ok": False,
                "error": f"Template '{template_name}' not found or not approved",
            }

        # Extract variable names from template components
        all_var_names = []
        for comp in tpl_components or []:
            text = comp.get("text", "")
            var_names = re.findall(r"\{\{(\w+)\}\}", text)
            all_var_names.extend(var_names)

        # Build variable values: custom_vars override, then auto-fill
        vars_dict = custom_vars or {}
        auto_values = {
            "nombre_paciente": patient_name,
            "nombre": patient_name,
            "1": patient_name,
        }

        # Build send components matching template structure
        send_components = []
        for comp in tpl_components or []:
            comp_type = comp.get("type", "").upper()
            text = comp.get("text", "")
            comp_vars = re.findall(r"\{\{(\w+)\}\}", text)
            if not comp_vars:
                continue

            parameters = []
            for var_name in comp_vars:
                # Priority: custom_vars > auto_values > empty
                value = vars_dict.get(var_name) or auto_values.get(var_name) or ""
                parameters.append(
                    {
                        "type": "text",
                        "text": str(value),
                        "parameter_name": var_name,
                    }
                )

            send_components.append(
                {
                    "type": comp_type.lower(),
                    "parameters": parameters,
                }
            )

        # Send
        yc = YCloudClient(api_key=api_key, business_number=business_number)
        try:
            await yc.send_template(
                to=phone,
                template_name=template_name,
                language_code=real_lang,
                components=send_components if send_components else None,
            )
        except httpx.HTTPStatusError as http_err:
            try:
                err_detail = http_err.response.json()
            except Exception:
                err_detail = http_err.response.text
            return {"ok": False, "error": str(err_detail)[:300]}

        # Persist in chat_conversations + chat_messages
        try:
            import uuid as _uuid
            import json as _json

            conv = await db.pool.fetchrow(
                "SELECT id FROM chat_conversations WHERE tenant_id = $1 AND external_user_id = $2 AND channel = 'whatsapp' ORDER BY updated_at DESC LIMIT 1",
                tenant_id,
                phone,
            )
            preview_label = f"[Plantilla: {template_name}]"
            if conv:
                conv_id = conv["id"]
                await db.pool.execute(
                    "UPDATE chat_conversations SET last_message_preview = $1, updated_at = NOW() WHERE id = $2",
                    preview_label,
                    conv_id,
                )
            else:
                conv_id = _uuid.uuid4()
                await db.pool.execute(
                    "INSERT INTO chat_conversations (id, tenant_id, channel, provider, external_user_id, display_name, last_message_preview, status, updated_at) VALUES ($1, $2, 'whatsapp', 'ycloud', $3, $4, $5, 'active', NOW())",
                    conv_id,
                    tenant_id,
                    phone,
                    patient_name or None,
                    preview_label,
                )

            await db.pool.execute(
                "INSERT INTO chat_messages (tenant_id, conversation_id, role, content, from_number, platform_metadata) VALUES ($1, $2, 'assistant', $3, $4, $5::jsonb)",
                tenant_id,
                conv_id,
                f"📨 Plantilla '{template_name}' enviada a {patient_name}",
                phone,
                _json.dumps(
                    {
                        "source": source,
                        "template": template_name,
                        "patient_name": patient_name,
                    }
                ),
            )
        except Exception as persist_err:
            logger.warning(
                f"Template message persist failed (non-blocking): {persist_err}"
            )

        return {"ok": True}

    except Exception as e:
        logger.error(f"_generic_send_template error: {e}", exc_info=True)
        return {"ok": False, "error": str(e)[:200]}


# =============================================================================
# N+1. Acción Masiva (herramienta Jarvis-style)
# =============================================================================


async def _build_patient_filter_query(
    args: Dict, tenant_id: int
) -> tuple[str, list, int]:
    """
    Build dynamic SQL query with filters. Returns (where_clause, params, param_idx).
    This is SHARED between _enviar_plantilla_masiva and _accion_masiva.
    """
    conditions = ["p.tenant_id = $1", "p.status = $2"]
    params: list = [tenant_id, args.get("estado", "active")]
    param_idx = 3

    # --- Filter: sin_turno_dias ---
    if args.get("sin_turno_dias"):
        days = int(args["sin_turno_dias"])
        conditions.append(f"""
            NOT EXISTS (
                SELECT 1 FROM appointments a
                WHERE a.patient_id = p.id AND a.tenant_id = $1
                  AND a.appointment_datetime >= (NOW() - INTERVAL '{days} days')
                  AND a.status NOT IN ('cancelled', 'no_show')
            )
        """)

    # --- Filter: ultimo_turno_hace_dias ---
    if args.get("ultimo_turno_hace_dias"):
        days = int(args["ultimo_turno_hace_dias"])
        conditions.append(f"""
            EXISTS (
                SELECT 1 FROM appointments a
                WHERE a.patient_id = p.id AND a.tenant_id = $1
                  AND a.status IN ('completed', 'confirmed', 'scheduled')
            ) AND NOT EXISTS (
                SELECT 1 FROM appointments a
                WHERE a.patient_id = p.id AND a.tenant_id = $1
                  AND a.appointment_datetime >= (NOW() - INTERVAL '{days} days')
                  AND a.status IN ('completed', 'confirmed', 'scheduled')
            )
        """)

    # --- Filter: nunca_agendo ---
    if args.get("nunca_agendo"):
        conditions.append("""
            NOT EXISTS (
                SELECT 1 FROM appointments a
                WHERE a.patient_id = p.id AND a.tenant_id = $1
            )
        """)

    # --- Filter: tratamiento ---
    if args.get("tratamiento"):
        conditions.append(f"""
            EXISTS (
                SELECT 1 FROM appointments a
                JOIN treatment_types tt ON tt.code = a.treatment_type AND tt.tenant_id = $1
                WHERE a.patient_id = p.id AND a.tenant_id = $1
                  AND tt.name ILIKE ${param_idx}
            )
        """)
        params.append(f"%{args['tratamiento']}%")
        param_idx += 1

    # --- Filter: obra_social ---
    if args.get("obra_social"):
        conditions.append(f"p.insurance_provider ILIKE ${param_idx}")
        params.append(f"%{args['obra_social']}%")
        param_idx += 1

    # --- Filter: fuente ---
    if args.get("fuente"):
        conditions.append(f"p.first_touch_source ILIKE ${param_idx}")
        params.append(f"%{args['fuente']}%")
        param_idx += 1

    # --- Filter: edad_min / edad_max ---
    if args.get("edad_min"):
        conditions.append(
            f"p.birth_date <= (CURRENT_DATE - INTERVAL '{int(args['edad_min'])} years')"
        )
    if args.get("edad_max"):
        conditions.append(
            f"p.birth_date >= (CURRENT_DATE - INTERVAL '{int(args['edad_max'])} years')"
        )

    # --- Filter: genero ---
    if args.get("genero"):
        conditions.append(f"LOWER(p.gender) = ${param_idx}")
        params.append(args["genero"].lower())
        param_idx += 1

    # --- Filter: con_anamnesis ---
    if args.get("con_anamnesis") is not None:
        if args["con_anamnesis"]:
            conditions.append(
                "EXISTS (SELECT 1 FROM medical_history mh WHERE mh.patient_id = p.id AND mh.anamnesis_completed_at IS NOT NULL)"
            )
        else:
            conditions.append(
                "NOT EXISTS (SELECT 1 FROM medical_history mh WHERE mh.patient_id = p.id AND mh.anamnesis_completed_at IS NOT NULL)"
            )

    # --- Filter: urgencia ---
    if args.get("urgencia"):
        conditions.append(f"p.urgency_level = ${param_idx}")
        params.append(args["urgencia"])
        param_idx += 1

    # --- Filter: profesional / profesional_id ---
    if args.get("profesional_id"):
        conditions.append(f"""
            EXISTS (
                SELECT 1 FROM appointments a
                WHERE a.patient_id = p.id AND a.tenant_id = $1
                  AND a.professional_id = ${param_idx}
            )
        """)
        params.append(int(args["profesional_id"]))
        param_idx += 1
    elif args.get("profesional"):
        conditions.append(f"""
            EXISTS (
                SELECT 1 FROM appointments a
                JOIN professionals pr ON pr.id = a.professional_id
                WHERE a.patient_id = p.id AND a.tenant_id = $1
                  AND (pr.first_name ILIKE ${param_idx} OR pr.last_name ILIKE ${param_idx})
            )
        """)
        params.append(f"%{args['profesional']}%")
        param_idx += 1

    # --- Filter: creado_desde / creado_hasta ---
    if args.get("creado_desde"):
        conditions.append(f"p.created_at >= ${param_idx}::date")
        params.append(args["creado_desde"])
        param_idx += 1
    if args.get("creado_hasta"):
        conditions.append(f"p.created_at <= ${param_idx}::date + INTERVAL '1 day'")
        params.append(args["creado_hasta"])
        param_idx += 1

    # --- Filter: sin_email ---
    if args.get("sin_email"):
        conditions.append("(p.email IS NULL OR p.email = '')")

    # --- Filter: con_deuda ---
    if args.get("con_deuda"):
        conditions.append("""
            EXISTS (
                SELECT 1 FROM appointments a
                WHERE a.patient_id = p.id AND a.tenant_id = $1
                  AND a.payment_status IN ('pending', 'partial')
            )
        """)

    # --- Filter: turno_cancelado_dias ---
    if args.get("turno_cancelado_dias"):
        days = int(args["turno_cancelado_dias"])
        conditions.append(f"""
            EXISTS (
                SELECT 1 FROM appointments a
                WHERE a.patient_id = p.id AND a.tenant_id = $1
                  AND a.status = 'cancelled'
                  AND a.appointment_datetime >= (NOW() - INTERVAL '{days} days')
            )
        """)

    # Exclude patients without phone
    conditions.append("p.phone_number IS NOT NULL")
    conditions.append("p.phone_number != ''")
    conditions.append("p.phone_number NOT LIKE '%-M%'")

    where_clause = " AND ".join(conditions)
    return where_clause, params, param_idx


async def _accion_masiva(args: Dict, tenant_id: int, user_role: str) -> str:
    """
    Jarvis-style unified action tool: combines patient filters with any action.
    Actions: plantilla, mensaje_libre, anamnesis, listar, contar, exportar
    """
    if user_role not in ("ceo", "secretary"):
        return "Solo CEO o secretaria pueden usar acción masiva."

    accion = args.get("accion", "")
    confirmar = args.get("confirmar", False)
    limite = min(int(args.get("limite", 50)), 200)

    if not accion:
        return "Necesito saber qué acción hacer. Opciones: plantilla, mensaje_libre, anamnesis, listar, contar, exportar"

    try:
        # Build filter query
        where_clause, params, _ = await _build_patient_filter_query(args, tenant_id)

        # COUNT first
        count_sql = f"SELECT COUNT(*) FROM patients p WHERE {where_clause}"
        total = await db.pool.fetchval(count_sql, *params)

        filter_desc = _describe_filters(args)

        # Preview mode
        if not confirmar:
            if accion in ("listar", "contar", "exportar"):
                # These don't need confirmation, just show count
                if accion == "contar":
                    return f"Encontré {total} pacientes que cumplen los filtros:\n{filter_desc}"
                # For listar/exportar, return preview with count
                return (
                    f"Encontré {total} pacientes que cumplen los filtros:\n{filter_desc}\n\n"
                    f"Acción: {accion}\n"
                    f"¿Procedo? Decime 'sí, {accion}' para ejecutar."
                )
            else:
                # Actions that send messages need confirmation
                return (
                    f"Encontré {total} pacientes que cumplen los filtros:\n{filter_desc}\n\n"
                    f"Acción: {accion}\n"
                    f"Límite: {limite} (se procesarán {min(total, limite)})\n\n"
                    f"¿Confirmo? Decime 'sí, {accion}' para proceder."
                )

        # Execution mode
        if total == 0:
            return "No hay pacientes que cumplan esos filtros."

        # Fetch patients
        fetch_sql = f"""
            SELECT p.id, p.phone_number, p.first_name, p.last_name, p.email
            FROM patients p
            WHERE {where_clause}
            ORDER BY p.updated_at DESC
            LIMIT {limite}
        """
        patients = await db.pool.fetch(fetch_sql, *params)

        # Handle different actions
        if accion == "contar":
            return f"Total: {total} pacientes."

        elif accion == "listar":
            lines = [f"Lista de {len(patients)} pacientes (de {total} totales):"]
            for p in patients:
                name = f"{p['first_name']} {p.get('last_name', '')}".strip()
                phone = p.get("phone_number", "sin teléfono")
                email = p.get("email") or "sin email"
                lines.append(f"• {name} — {phone} — {email}")
            return "\n".join(lines)

        elif accion == "exportar":
            lines = ["Nombre,Teléfono,Email"]
            for p in patients:
                name = f"{p['first_name']} {p.get('last_name', '')}".strip()
                phone = p.get("phone_number", "")
                email = p.get("email") or ""
                lines.append(f'"{name}","{phone}","{email}"')
            return "📄 CSV exportado:\n\n" + "\n".join(lines)

        else:
            # Actions that send messages: plantilla, mensaje_libre, anamnesis
            sent = 0
            errors = 0
            template_name = args.get("template_name", "")
            mensaje = args.get("mensaje", "")
            variables = args.get("variables", {})

            for pat in patients:
                pat_name = f"{pat['first_name']} {pat.get('last_name', '')}".strip()
                phone = pat["phone_number"]

                try:
                    if accion == "plantilla":
                        # Resolve template vars
                        resolved_vars = {}
                        for k, v in variables.items():
                            resolved_vars[k] = (
                                str(v).replace("{nombre}", pat_name)
                                if isinstance(v, str)
                                else v
                            )
                        result = await _generic_send_template(
                            tenant_id=tenant_id,
                            phone=phone,
                            template_name=template_name,
                            patient_name=pat_name,
                            custom_vars=resolved_vars,
                            source="accion_masiva",
                        )

                    elif accion == "mensaje_libre":
                        # Send free-text WhatsApp message
                        from ycloud_client import YCloudClient
                        from core.credentials import (
                            get_tenant_credential,
                            YCLOUD_API_KEY,
                            YCLOUD_WHATSAPP_NUMBER,
                        )

                        api_key = await get_tenant_credential(tenant_id, YCLOUD_API_KEY)
                        business_number = await db.pool.fetchval(
                            "SELECT bot_phone_number FROM tenants WHERE id = $1",
                            tenant_id,
                        )
                        if not business_number:
                            business_number = await get_tenant_credential(
                                tenant_id, YCLOUD_WHATSAPP_NUMBER
                            )

                        msg_text = mensaje.replace("{nombre}", pat_name)
                        yc = YCloudClient(
                            api_key=api_key, business_number=business_number
                        )
                        await yc.send_message(to=phone, message=msg_text)
                        result = {"ok": True}

                    elif accion == "anamnesis":
                        # Generate and send anamnesis link
                        from core.credentials import (
                            get_tenant_credential,
                            YCLOUD_API_KEY,
                            YCLOUD_WHATSAPP_NUMBER,
                        )
                        import uuid

                        # Get clinic name
                        clinic_name = await db.pool.fetchval(
                            "SELECT clinic_name FROM tenants WHERE id = $1", tenant_id
                        )

                        # Generate unique token
                        token = uuid.uuid4().hex[:12]
                        anamnesis_url = f"https://clinicforge.app/anamnesis/{tenant_id}/{pat['id']}/{token}"

                        # Send via YCloud
                        api_key = await get_tenant_credential(tenant_id, YCLOUD_API_KEY)
                        business_number = await db.pool.fetchval(
                            "SELECT bot_phone_number FROM tenants WHERE id = $1",
                            tenant_id,
                        )
                        if not business_number:
                            business_number = await get_tenant_credential(
                                tenant_id, YCLOUD_WHATSAPP_NUMBER
                            )

                        msg_text = f"¡Hola {pat_name}! 👋\n\n{clinic_name} te invita a completar tu historia clínica antes de tu próxima visita.\n\nCompletá tu anamnesis aquí: {anamnesis_url}\n\n¡Te esperamos!"
                        yc = YCloudClient(
                            api_key=api_key, business_number=business_number
                        )
                        await yc.send_message(to=phone, message=msg_text)
                        result = {"ok": True}

                    else:
                        result = {"ok": False, "error": "Acción desconocida"}

                    if result.get("ok"):
                        sent += 1
                    else:
                        errors += 1
                        logger.warning(
                            f"accion_masiva {accion} error for {phone}: {result.get('error')}"
                        )

                except Exception as e:
                    errors += 1
                    logger.warning(f"accion_masiva error for {phone}: {e}")

                # Rate limit
                import asyncio

                await asyncio.sleep(1.0)

            return (
                f"✅ Acción '{accion}' completada:\n"
                f"• Enviados: {sent}\n"
                f"• Errores: {errors}\n"
                f"• Total procesados: {sent + errors} de {total}"
            )

    except Exception as e:
        logger.error(f"_accion_masiva error: {e}", exc_info=True)
        return f"Error en acción masiva: {str(e)[:200]}"


# =============================================================================
# DISPATCHER
# =============================================================================


def nova_tools_for_chat_completions() -> List[Dict[str, Any]]:
    """
    Convert NOVA_TOOLS_SCHEMA from OpenAI Realtime flat format to Chat Completions format.

    Realtime format:  {"type": "function", "name": ..., "description": ..., "parameters": ...}
    Chat Completions: {"type": "function", "function": {"name": ..., "description": ..., "parameters": ...}}
    """
    tools = []
    for tool in NOVA_TOOLS_SCHEMA:
        tools.append(
            {
                "type": "function",
                "function": {
                    "name": tool["name"],
                    "description": tool.get("description", ""),
                    "parameters": tool.get("parameters", {}),
                },
            }
        )
    return tools


# Tools to exclude per page (navigation tools don't make sense in Telegram/voice)
_EXCLUDED_TOOLS_BY_PAGE: Dict[str, set] = {
    "telegram": {"ir_a_pagina", "ir_a_paciente", "switch_sede", "onboarding_status"},
    "dashboard": {"ir_a_paciente"},
    "agenda": {"onboarding_status"},
}

# Voice (Realtime API) — aggressive filtering for gpt-4o-mini-realtime-preview
# Only essential tools that make sense via voice. 77 tools saturate the mini model.
_VOICE_ALLOWED_TOOLS: set = {
    # Pacientes
    "buscar_paciente", "ver_paciente", "registrar_paciente", "convertir_lead",
    "actualizar_paciente", "historial_clinico", "eliminar_paciente",
    # Agenda
    "ver_agenda", "proximo_paciente", "verificar_disponibilidad",
    "agendar_turno", "cancelar_turno", "confirmar_turnos",
    "reprogramar_turno", "cambiar_estado_turno", "bloquear_agenda",
    # Tratamientos
    "listar_tratamientos", "listar_profesionales",
    # Facturación
    "registrar_pago", "facturacion_pendiente",
    # Analytics
    "resumen_semana", "rendimiento_profesional", "ver_estadisticas",
    # Comunicación
    "ver_chats_recientes", "enviar_mensaje",
    # Anamnesis + Odontograma
    "guardar_anamnesis", "ver_anamnesis", "enviar_anamnesis",
    "ver_odontograma", "modificar_odontograma",
    # Navegación
    "ir_a_pagina", "ir_a_paciente",
    # Memorias
    "guardar_memoria", "buscar_memorias",
}


_META_TOOL_SCHEMA: Dict[str, Any] = {
    "type": "function",
    "name": "herramienta_avanzada",
    "description": (
        "Ejecuta cualquier herramienta avanzada que no esté cargada directamente. "
        "Usá esta tool cuando necesites hacer algo que no podés con las tools disponibles: "
        "generar PDFs, presupuestos, liquidaciones, CRUD de tablas, configuración, FAQs, "
        "obras sociales, fichas digitales, reportes, plantillas masivas, acciones masivas, etc. "
        "Pasá el nombre exacto de la herramienta y sus argumentos."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "tool_name": {
                "type": "string",
                "description": (
                    "Nombre de la herramienta. Opciones: "
                    "obtener_registros, actualizar_registro, crear_registro, contar_registros, "
                    "consultar_datos, resumen_marketing, resumen_financiero, "
                    "generar_ficha_digital, enviar_ficha_digital, enviar_pdf_telegram, "
                    "generar_reporte_personalizado, "
                    "ver_presupuesto_paciente, crear_presupuesto, agregar_item_presupuesto, "
                    "generar_pdf_presupuesto, enviar_presupuesto_email, aprobar_presupuesto, "
                    "sincronizar_turnos_presupuesto, "
                    "editar_facturacion_turno, registrar_pago_plan, "
                    "gestionar_usuarios, gestionar_obra_social, "
                    "generar_pdf_liquidacion, enviar_liquidacion_email, "
                    "ver_configuracion, actualizar_configuracion, "
                    "crear_tratamiento, editar_tratamiento, completar_tratamiento, "
                    "ver_faqs, eliminar_faq, actualizar_faq, "
                    "buscar_en_base_conocimiento, consultar_obra_social, ver_reglas_derivacion, "
                    "resumen_sedes, comparar_sedes, switch_sede, onboarding_status, "
                    "listar_plantillas, enviar_plantilla, enviar_plantilla_masiva, accion_masiva, "
                    "registrar_nota_clinica, ver_contexto_memorias, "
                    "ver_memorias_paciente, agregar_memoria_paciente"
                ),
            },
            "args": {
                "type": "object",
                "description": "Argumentos de la herramienta como objeto JSON. Consultá la descripción de cada tool para saber qué argumentos necesita.",
            },
        },
        "required": ["tool_name"],
    },
}


def nova_tools_for_voice() -> List[Dict[str, Any]]:
    """Return flat-format tools filtered for Realtime API voice (reduced set + meta-tool for the rest)."""
    core = [t for t in NOVA_TOOLS_SCHEMA if t["name"] in _VOICE_ALLOWED_TOOLS]
    core.append(_META_TOOL_SCHEMA)
    return core


def nova_tools_for_page(page: str = "telegram") -> List[Dict[str, Any]]:
    """Return Chat Completions-formatted tools filtered by page context."""
    excluded = _EXCLUDED_TOOLS_BY_PAGE.get(page, set())
    tools = []
    for tool in NOVA_TOOLS_SCHEMA:
        if tool["name"] in excluded:
            continue
        tools.append(
            {
                "type": "function",
                "function": {
                    "name": tool["name"],
                    "description": tool.get("description", ""),
                    "parameters": tool.get("parameters", {}),
                },
            }
        )
    return tools


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
        elif name == "convertir_lead":
            return await _convertir_lead(args, tenant_id)
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
            return await _facturacion_pendiente(tenant_id, args.get("paciente"))

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
        elif name == "completar_tratamiento":
            return await _completar_tratamiento(args, tenant_id)

        # H. Anamnesis
        elif name == "guardar_anamnesis":
            return await _guardar_anamnesis(args, tenant_id)
        elif name == "ver_anamnesis":
            return await _ver_anamnesis(args, tenant_id)
        elif name == "enviar_anamnesis":
            return await _enviar_anamnesis(args, tenant_id)

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
        elif name == "enviar_pdf_telegram":
            return await _enviar_pdf_telegram(args, tenant_id)
        elif name == "generar_reporte_personalizado":
            return await _generar_reporte_personalizado(args, tenant_id)

        # O. Treatment Plans
        elif name == "ver_presupuesto_paciente":
            return await _ver_presupuesto_paciente(args, tenant_id)
        elif name == "aprobar_presupuesto":
            return await _aprobar_presupuesto(args, tenant_id, user_role, user_id)
        elif name == "crear_presupuesto":
            return await _crear_presupuesto(args, tenant_id, user_role)
        elif name == "agregar_item_presupuesto":
            return await _agregar_item_presupuesto(args, tenant_id, user_role)
        elif name == "generar_pdf_presupuesto":
            return await _generar_pdf_presupuesto(args, tenant_id, user_role)
        elif name == "enviar_presupuesto_email":
            return await _enviar_presupuesto_email(args, tenant_id, user_role)
        elif name == "editar_facturacion_turno":
            return await _editar_facturacion_turno(args, tenant_id, user_role)
        elif name == "gestionar_usuarios":
            return await _gestionar_usuarios(args, tenant_id, user_role)
        elif name == "gestionar_obra_social":
            return await _gestionar_obra_social(args, tenant_id, user_role)
        elif name == "generar_pdf_liquidacion":
            return await _generar_pdf_liquidacion(args, tenant_id, user_role)
        elif name == "enviar_liquidacion_email":
            return await _enviar_liquidacion_email(args, tenant_id, user_role)
        elif name == "sincronizar_turnos_presupuesto":
            return await _sincronizar_turnos_presupuesto(args, tenant_id, user_role)

        # J. CRUD genérico
        elif name == "obtener_registros":
            return await _obtener_registros(args, tenant_id, user_role)
        elif name == "actualizar_registro":
            return await _actualizar_registro(args, tenant_id, user_role)
        elif name == "crear_registro":
            return await _crear_registro(args, tenant_id, user_role)
        elif name == "contar_registros":
            return await _contar_registros(args, tenant_id)

        # K2. Engram — Persistent Memory
        elif name == "guardar_memoria":
            return await _guardar_memoria(args, tenant_id, user_role)
        elif name == "buscar_memorias":
            return await _buscar_memorias(args, tenant_id)
        elif name == "ver_contexto_memorias":
            return await _ver_contexto_memorias(args, tenant_id)

        # K3. Patient Memories
        elif name == "ver_memorias_paciente":
            return await _ver_memorias_paciente(args, tenant_id)
        elif name == "agregar_memoria_paciente":
            return await _agregar_memoria_paciente(args, tenant_id)

        # N. Plantillas WhatsApp
        elif name == "listar_plantillas":
            return await _listar_plantillas(tenant_id)
        elif name == "enviar_plantilla":
            return await _enviar_plantilla(args, tenant_id, user_role)
        elif name == "enviar_plantilla_masiva":
            return await _enviar_plantilla_masiva(args, tenant_id, user_role)

        # N+1. Acción Masiva (Jarvis-style)
        elif name == "accion_masiva":
            return await _accion_masiva(args, tenant_id, user_role)

        # Meta-tool: proxy for voice to access all 77 tools
        elif name == "herramienta_avanzada":
            inner_name = args.get("tool_name", "")
            inner_args = args.get("args", {}) or {}
            if not inner_name:
                return "Necesito el nombre de la herramienta (tool_name)."
            logger.info(f"🔧 NOVA meta-tool: {inner_name}({list(inner_args.keys())})")
            return await execute_nova_tool(inner_name, inner_args, tenant_id, user_role, user_id)

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
    # Capture old datetime for audit log
    _old = await db.pool.fetchrow(
        "SELECT appointment_datetime, status FROM appointments WHERE id = $1 AND tenant_id = $2",
        appt_uuid,
        tenant_id,
    )
    result = await db.pool.execute(
        "UPDATE appointments SET appointment_datetime = $1, status = 'scheduled', updated_at = NOW() WHERE id = $2 AND tenant_id = $3",
        new_dt,
        appt_uuid,
        tenant_id,
    )
    if result == "UPDATE 0":
        return "No encontre ese turno."

    # Audit log (TIER 3 cap.3 Phase B)
    try:
        from services.audit_log import log_appointment_mutation as _audit

        _old_dt = _old["appointment_datetime"] if _old else None
        await _audit(
            pool=db.pool,
            tenant_id=tenant_id,
            appointment_id=str(appt_uuid),
            action="rescheduled",
            actor_type="staff_user",
            actor_id="nova_voice",
            before_values={
                "appointment_datetime": _old_dt.isoformat()
                if _old_dt and hasattr(_old_dt, "isoformat")
                else str(_old_dt),
                "status": _old["status"] if _old else None,
            }
            if _old
            else None,
            after_values={
                "appointment_datetime": new_dt.isoformat()
                if hasattr(new_dt, "isoformat")
                else str(new_dt),
                "status": "scheduled",
            },
            source_channel="nova_voice",
            reason=None,
        )
    except Exception as _audit_err:
        import logging as _lg

        _lg.getLogger("nova_tools").warning(
            f"audit_log nova reprogramar failed (non-blocking): {_audit_err}"
        )

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
    category = args.get("category", "consultas")
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
                  p.id as patient_id, p.first_name as patient_first_name, p.status as patient_status,
                  (SELECT content FROM chat_messages WHERE conversation_id = cc.id ORDER BY created_at DESC LIMIT 1) as last_msg
           FROM chat_conversations cc
           LEFT JOIN patients p ON p.phone_number = cc.external_user_id AND p.tenant_id = cc.tenant_id
           WHERE cc.tenant_id = $1 ORDER BY cc.updated_at DESC LIMIT $2""",
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
        # Badge: Lead or Paciente (with ID)
        if r["patient_id"] and r["patient_status"] != "guest":
            badge = f"[PACIENTE ID:{r['patient_id']}]"
        elif r["patient_id"] and r["patient_status"] == "guest":
            badge = f"[LEAD/GUEST ID:{r['patient_id']}]"
        else:
            badge = "[LEAD - sin ficha]"
        name_part = f" {name}" if name else ""
        lines.append(f"• {badge} {phone}{name_part} ({channel}) — {when}: {last}")
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
            await _nova_emit(
                "MESSAGE_SENT",
                {"patient_name": display, "channel": channel, "tenant_id": tenant_id},
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
                await _nova_emit(
                    "MESSAGE_SENT",
                    {
                        "patient_name": display,
                        "channel": channel,
                        "tenant_id": tenant_id,
                    },
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
                await _nova_emit(
                    "MESSAGE_SENT",
                    {
                        "patient_name": display,
                        "channel": "whatsapp",
                        "tenant_id": tenant_id,
                    },
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
    appt_revenue = float(stats["revenue"] or 0)

    # Plan payments for the same period
    if days == 0:
        plan_rev = (
            await db.pool.fetchval(
                "SELECT COALESCE(SUM(amount), 0) FROM treatment_plan_payments WHERE tenant_id = $1 AND payment_date::date = CURRENT_DATE",
                tenant_id,
            )
            or 0
        )
    else:
        plan_rev = (
            await db.pool.fetchval(
                "SELECT COALESCE(SUM(amount), 0) FROM treatment_plan_payments WHERE tenant_id = $1 AND payment_date::date >= $2",
                tenant_id,
                since,
            )
            or 0
        )

    revenue = appt_revenue + float(plan_rev)

    new_patients = (
        await db.pool.fetchval(
            "SELECT COUNT(*) FROM patients WHERE tenant_id = $1 AND created_at::date >= $2",
            tenant_id,
            since,
        )
        or 0
    )

    # Active plans count
    active_plans = (
        await db.pool.fetchval(
            "SELECT COUNT(*) FROM treatment_plans WHERE tenant_id = $1 AND status IN ('draft','approved','in_progress')",
            tenant_id,
        )
        or 0
    )

    return f"""Estadisticas ({period}):
• Turnos totales: {total}
• Completados: {completed}
• Cancelados: {cancelled}
• No-shows: {no_shows}
• Pacientes nuevos: {new_patients}
• Presupuestos activos: {active_plans}
• Facturacion: ${revenue:,.0f} (turnos: ${appt_revenue:,.0f} + planes: ${float(plan_rev):,.0f})
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
    # Capture previous status for audit log
    _prev_status = await db.pool.fetchval(
        "SELECT status FROM appointments WHERE id = $1 AND tenant_id = $2",
        appt_uuid,
        tenant_id,
    )
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

    # Audit log (TIER 3 cap.3 Phase B)
    try:
        from services.audit_log import log_appointment_mutation as _audit

        await _audit(
            pool=db.pool,
            tenant_id=tenant_id,
            appointment_id=str(appt_uuid),
            action="cancelled" if status == "cancelled" else "status_changed",
            actor_type="staff_user",
            actor_id="nova_voice",
            before_values={"status": _prev_status} if _prev_status else None,
            after_values={"status": status},
            source_channel="nova_voice",
            reason=None,
        )
    except Exception as _audit_err:
        import logging as _lg

        _lg.getLogger("nova_tools").warning(
            f"audit_log nova cambiar_estado failed (non-blocking): {_audit_err}"
        )

    await _nova_emit(
        "APPOINTMENT_UPDATED",
        {"appointment_id": str(appt_uuid), "tenant_id": tenant_id, "status": status},
    )
    return f"Turno actualizado → estado: {status}"


async def _completar_tratamiento(args: Dict, tenant_id: int) -> str:
    """Marca tratamiento como completo y envía HSM de seguimiento."""
    apt_id = args.get("appointment_id", "")
    if not apt_id:
        return "Necesito el ID del turno (appointment_id)."

    try:
        appt_uuid = uuid.UUID(str(apt_id))
    except ValueError:
        return "ID de turno inválido."

    # Obtener datos del turno
    apt = await db.pool.fetchrow(
        """
        SELECT a.id, a.appointment_type, a.followup_sent, a.appointment_datetime,
               p.first_name, p.last_name, p.phone_number,
               prof.first_name as prof_first_name, prof.last_name as prof_last_name
        FROM appointments a
        JOIN patients p ON a.patient_id = p.id AND p.tenant_id = a.tenant_id
        LEFT JOIN professionals prof ON a.professional_id = prof.id
        WHERE a.id = $1 AND a.tenant_id = $2
        """,
        appt_uuid,
        tenant_id,
    )

    if not apt:
        return "No encontré ese turno."

    if not apt["appointment_type"]:
        return "Este turno no tiene tipo de tratamiento asignado."

    if apt["followup_sent"]:
        return "El seguimiento HSM ya fue enviado para este turno."

    if not apt["phone_number"]:
        return "El paciente no tiene teléfono registrado."

    patient_name = (
        f"{apt['first_name'] or ''} {apt['last_name'] or ''}".strip() or "paciente"
    )
    professional_name = (
        f"{apt['prof_first_name'] or ''} {apt['prof_last_name'] or ''}".strip()
    )
    apt_date = (
        apt["appointment_datetime"].strftime("%d/%m/%Y")
        if apt["appointment_datetime"]
        else ""
    )

    # Importar y ejecutar la función de envío
    from admin_routes import send_treatment_completion_hsm

    sent = await send_treatment_completion_hsm(
        tenant_id=tenant_id,
        treatment_code=apt["appointment_type"],
        patient_name=patient_name,
        phone_number=apt["phone_number"],
        appointment_id=appt_uuid,
        professional_name=professional_name,
        appointment_date=apt_date,
    )

    if sent:
        return f"✅ Tratamiento '{apt['appointment_type']}' marcado como completo. Seguimiento HSM enviado a {patient_name} ({apt['phone_number']})."
    else:
        return f"⚠️ Tratamiento marcado como completo, pero no se pudo enviar el HSM. Revisá que haya una regla activa para '{apt['appointment_type']}' en HSM Automation."


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


async def _enviar_anamnesis(args: Dict, tenant_id: int) -> str:
    """Envía el link de anamnesis a un paciente por WhatsApp."""
    patient_id = args.get("patient_id")
    if not patient_id:
        return "Necesito el ID del paciente."

    row = await db.pool.fetchrow(
        "SELECT first_name, last_name, phone_number, anamnesis_token FROM patients WHERE id = $1 AND tenant_id = $2",
        int(patient_id),
        tenant_id,
    )
    if not row:
        return "Paciente no encontrado."
    if not row["phone_number"]:
        return "El paciente no tiene teléfono cargado."

    # Generate token if missing
    token = row["anamnesis_token"]
    if not token:
        token = str(uuid.uuid4())
        await db.pool.execute(
            "UPDATE patients SET anamnesis_token = $1 WHERE id = $2 AND tenant_id = $3",
            token,
            int(patient_id),
            tenant_id,
        )

    import os

    frontend_url = (
        os.getenv("FRONTEND_URL", "http://localhost:4173")
        .split(",")[0]
        .strip()
        .rstrip("/")
    )
    link = f"{frontend_url}/anamnesis/{tenant_id}/{token}"
    name = f"{row['first_name'] or ''} {row['last_name'] or ''}".strip()

    # Send via enviar_mensaje
    message = (
        f"¡Hola {row['first_name']}! 👋\n\n"
        f"Para poder atenderte mejor, te pedimos que completes tu ficha médica en este formulario:\n\n"
        f"{link}\n\n"
        f"Es rápido y confidencial. ¡Gracias! 🦷"
    )
    result = await _enviar_mensaje(
        {"phone": row["phone_number"], "message": message},
        tenant_id,
        "ceo",
    )
    return f"✅ Link de anamnesis enviado a {name} ({row['phone_number']}). {result}"


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

        plan_revenue = (
            sum(float(r["total_paid"]) for r in plan_rows) if plan_rows else 0.0
        )
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
        # Billing / Budget
        "treatment_plans",
        "treatment_plan_items",
        "treatment_plan_payments",
        # Financial Command Center
        "professional_commissions",
        "liquidations",
        "liquidation_items",
        # Accounting
        "accounting_transactions",
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
# 42 valid states — EXACT mirror of frontend odontogramStates.ts
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
    "protesis_removible": "prótesis removible",
    "diente_erupcion": "diente en erupción",
    "diente_no_erupcionado": "diente no erupcionado",
    "ausente": "ausente",
    "otra_preexistencia": "otra preexistencia",
    "treatment_planned": "planificado",
    # Lesión (17)
    "mancha_blanca": "mancha blanca",
    "surco_profundo": "surco profundo",
    "caries": "caries",
    "caries_penetrante": "caries penetrante",
    "necrosis_pulpar": "necrosis pulpar",
    "proceso_apical": "proceso apical",
    "fistula": "fístula",
    "indicacion_extraccion": "indicación de extracción",
    "abrasion": "abrasión",
    "abfraccion": "abfracción",
    "atricion": "atrición",
    "erosion": "erosión",
    "fractura_horizontal": "fractura horizontal",
    "fractura_vertical": "fractura vertical",
    "movilidad": "movilidad",
    "hipomineralizacion_mih": "hipomineralización MIH",
    "otra_lesion": "otra lesión",
}

# Alias map: states the LLM might use → correct valid state ID
_STATE_ALIASES = {
    # English aliases
    "extraction": "indicacion_extraccion",
    "missing": "ausente",
    "crown": "corona_porcelana",
    "prosthesis": "protesis_removible",
    "root_canal": "tratamiento_conducto",
    # Legacy/old aliases
    "necrosis": "necrosis_pulpar",
    "fractura": "fractura_vertical",
    "movilidad_dental": "movilidad",
    "protesis_fija": "puente",
    "caries_incipiente": "mancha_blanca",
    "caries_recurrente": "caries",
    "caries_radicular": "caries_penetrante",
    "absceso": "proceso_apical",
    "sinus": "proceso_apical",
    "periodontitis": "otra_lesion",
    "gingivitis": "otra_lesion",
    "recesion_gingival": "otra_lesion",
    "fisura": "surco_profundo",
    "blanqueamiento": "otra_preexistencia",
    "fluorosis": "otra_preexistencia",
    "hipoplasia": "otra_preexistencia",
    "desgaste": "atricion",
    "pulpotomia": "tratamiento_conducto",
    "apicogenesis": "tratamiento_conducto",
    "apicificacion": "tratamiento_conducto",
}

# All 42 valid states
_VALID_STATES = set(_STATUS_ES.keys())


def _resolve_state(raw_state: str) -> str:
    """Resolve a potentially invalid state ID to a valid one via aliases."""
    if raw_state in _VALID_STATES:
        return raw_state
    resolved = _STATE_ALIASES.get(raw_state)
    if resolved:
        return resolved
    return raw_state  # let validation catch it


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

    # Resolve aliases and validate all pieces BEFORE writing anything
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
        # Auto-resolve aliases (e.g., "necrosis" → "necrosis_pulpar", "missing" → "ausente")
        if estado:
            resolved = _resolve_state(estado)
            if resolved != estado:
                logger.info(f"Odontogram state alias: '{estado}' → '{resolved}'")
                pieza["estado"] = resolved
                estado = resolved
        if estado and estado not in _VALID_STATES:
            errors.append(
                f"Pieza {num}: estado '{estado}' no válido. Opciones: {', '.join(sorted(_VALID_STATES))}"
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

        prepaid_note = " (prepaga)" if row.get("is_prepaid") else ""
        if status == "accepted":
            copay = " Requiere coseguro." if row.get("requires_copay") else ""
            return f"Sí, la clínica trabaja con {name}{prepaid_note}.{copay}"
        elif status == "restricted":
            # Migration 034: show a summary of covered treatments from
            # coverage_by_treatment. Full detail lives in the Clinics UI.
            coverage = row.get("coverage_by_treatment") or {}
            if isinstance(coverage, str):
                import json as _json_cov

                try:
                    coverage = _json_cov.loads(coverage)
                except (ValueError, TypeError):
                    coverage = {}
            covered_codes = (
                [
                    k
                    for k, v in coverage.items()
                    if isinstance(v, dict) and v.get("covered", False)
                ]
                if isinstance(coverage, dict)
                else []
            )
            if covered_codes:
                summary = ", ".join(covered_codes[:5])
                suffix = " y otros" if len(covered_codes) > 5 else ""
                return (
                    f"La clínica trabaja con {name}{prepaid_note} con cobertura limitada: "
                    f"{summary}{suffix}. Consultá detalles de coseguro y carencia."
                )
            return (
                f"La clínica trabaja con {name}{prepaid_note} con restricciones. "
                "Consultá con la clínica para el detalle de cobertura."
            )
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
        from db import db as _db_inst
        import uuid as _uuid

        _pool = _db_inst.pool

        # Layer 1: Gather
        source_data = await gather_patient_data(_pool, patient_id, tenant_id, tipo)

        # Layer 2: AI Narrative
        narrative_result = await generate_narrative(_pool, tenant_id, tipo, source_data)
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


async def _enviar_pdf_telegram(args: Dict, tenant_id: int) -> str:
    """Find an existing digital record and return a PDF_ATTACHMENT marker for Telegram delivery."""
    patient_id = args.get("patient_id")
    record_id = args.get("record_id")
    tipo_documento = args.get("tipo_documento")

    try:
        if record_id:
            row = await db.pool.fetchrow(
                """SELECT id, html_content, pdf_path, title, template_type
                   FROM patient_digital_records
                   WHERE id = $1 AND tenant_id = $2""",
                record_id,
                tenant_id,
            )
        elif patient_id and tipo_documento:
            row = await db.pool.fetchrow(
                """SELECT id, html_content, pdf_path, title, template_type
                   FROM patient_digital_records
                   WHERE patient_id = $1 AND tenant_id = $2 AND template_type = $3
                   ORDER BY created_at DESC LIMIT 1""",
                patient_id,
                tenant_id,
                tipo_documento,
            )
        elif patient_id:
            row = await db.pool.fetchrow(
                """SELECT id, html_content, pdf_path, title, template_type
                   FROM patient_digital_records
                   WHERE patient_id = $1 AND tenant_id = $2
                   ORDER BY created_at DESC LIMIT 1""",
                patient_id,
                tenant_id,
            )
        else:
            return "Necesito al menos patient_id o record_id para buscar la ficha."

        if not row:
            return "No se encontró ninguna ficha digital para este paciente. ¿Querés que la genere?"

        actual_record_id = str(row["id"])
        title = row["title"] or "Ficha Digital"

        # Ensure PDF exists — generate if missing
        pdf_path = row["pdf_path"]
        if not pdf_path or not os.path.exists(pdf_path):
            from services.digital_records_service import generate_pdf

            output_dir = f"/app/uploads/digital_records/{tenant_id}"
            os.makedirs(output_dir, exist_ok=True)
            pdf_path = f"{output_dir}/{actual_record_id}.pdf"
            await generate_pdf(row["html_content"], pdf_path)
            await db.pool.execute(
                "UPDATE patient_digital_records SET pdf_path = $1, pdf_generated_at = NOW() WHERE id = $2",
                pdf_path,
                actual_record_id,
            )

        safe_filename = title.replace("/", "-").replace("\\", "-") + ".pdf"
        return f"[PDF_ATTACHMENT:{pdf_path}|{safe_filename}]\nTe envío {title}."

    except Exception as e:
        logger.error(f"_enviar_pdf_telegram error: {e}", exc_info=True)
        return f"Error al buscar la ficha: {str(e)}"


async def _generar_reporte_personalizado(args: Dict, tenant_id: int) -> str:
    """Generate a custom branded PDF report from Nova-written HTML content."""
    titulo = args.get("titulo", "Reporte")
    contenido = args.get("contenido", "")
    subtitulo = args.get("subtitulo")

    if not contenido:
        return "Necesito el contenido del reporte para generarlo."

    try:
        import uuid as _uuid
        from datetime import datetime
        from jinja2 import Environment, FileSystemLoader
        from services.digital_records_service import generate_pdf, resolve_logo_data_uri

        # Load tenant data
        tenant_row = await db.pool.fetchrow(
            "SELECT clinic_name, address FROM tenants WHERE id = $1",
            tenant_id,
        )
        clinic_name = (tenant_row["clinic_name"] if tenant_row else None) or "Clínica"

        logo_url = resolve_logo_data_uri(tenant_id)

        # Build template data
        import os as _os

        template_dir = _os.path.join(
            _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))),
            "templates",
            "digital_records",
        )

        data = {
            "clinic": {
                "name": clinic_name,
                "logo_url": logo_url,
                "address": tenant_row["address"] if tenant_row else None,
            },
            "titulo": titulo,
            "subtitulo": subtitulo,
            "contenido": contenido,
            "fecha": datetime.now().strftime("%d/%m/%Y %H:%M"),
        }

        env = Environment(loader=FileSystemLoader(template_dir))
        template = env.get_template("custom_report.html")
        html_content = template.render(data=data)

        # Generate PDF
        _os.makedirs("/tmp/nova_reports", exist_ok=True)
        pdf_filename = f"{_uuid.uuid4()}.pdf"
        pdf_path = f"/tmp/nova_reports/{pdf_filename}"
        await generate_pdf(html_content, pdf_path)

        safe_titulo = titulo.replace("/", "-").replace("\\", "-")
        return (
            f"[PDF_ATTACHMENT:{pdf_path}|{safe_titulo}.pdf]\nReporte generado: {titulo}"
        )

    except ImportError:
        return "No se pudo generar el PDF. WeasyPrint no está instalado."
    except Exception as e:
        logger.error(f"_generar_reporte_personalizado error: {e}", exc_info=True)
        return f"Error al generar el reporte: {str(e)}"
