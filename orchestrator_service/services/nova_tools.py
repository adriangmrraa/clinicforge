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

        else:
            return f"Tool '{name}' no reconocida."

    except Exception as e:
        logger.error(f"Error executing nova tool '{name}': {e}", exc_info=True)
        return f"Error al ejecutar '{name}': {str(e)}"
