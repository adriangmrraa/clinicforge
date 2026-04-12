"""
Variable resolver for Playbook Engine V2.
Loads patient/appointment/treatment/tenant data and returns a dict
of all available {{variables}} for template substitution.
"""

import logging
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)

_DAYS_ES = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]


async def resolve_variables(
    pool,
    tenant_id: int,
    phone_number: str,
    appointment_id: Optional[str] = None,
    context: Optional[dict] = None,
) -> dict:
    """
    Resolve all available variables for a playbook execution.
    Returns a dict like {"nombre_paciente": "María", "tratamiento": "Implante Simple", ...}
    """
    ctx = context or {}
    variables = {
        "nombre_paciente": "",
        "apellido_paciente": "",
        "telefono": phone_number,
        "tratamiento": "",
        "categoria_tratamiento": "",
        "profesional": "",
        "fecha_turno": "",
        "hora_turno": "",
        "dia_semana": "",
        "sede": "",
        "precio": "",
        "saldo_pendiente": "",
        "dias_sin_turno": "",
        "link_anamnesis": "",
        "nombre_clinica": "",
        "nombre_servicio": "",
        # Aliases for YCloud template compatibility
        "first_name": "",
        "last_name": "",
        "appointment_date": "",
        "appointment_time": "",
        "treatment_name": "",
        "clinic_name": "",
        "professional_name": "",
    }

    try:
        # 1. Patient data
        patient = await pool.fetchrow(
            "SELECT id, first_name, last_name, phone_number, anamnesis_token "
            "FROM patients WHERE tenant_id = $1 AND phone_number = $2 LIMIT 1",
            tenant_id, phone_number,
        )
        if patient:
            first = patient["first_name"] or ""
            last = patient["last_name"] or ""
            variables["nombre_paciente"] = first
            variables["apellido_paciente"] = last
            variables["first_name"] = first
            variables["last_name"] = last

            if patient["anamnesis_token"]:
                import os
                frontend_url = os.getenv("FRONTEND_URL", "")
                if frontend_url:
                    variables["link_anamnesis"] = f"{frontend_url}/anamnesis/{tenant_id}/{patient['anamnesis_token']}"

            # Days since last appointment
            last_apt_date = await pool.fetchval(
                "SELECT MAX(appointment_datetime) FROM appointments "
                "WHERE tenant_id = $1 AND patient_id = $2 AND status = 'completed'",
                tenant_id, patient["id"],
            )
            if last_apt_date:
                delta = (datetime.now(last_apt_date.tzinfo) - last_apt_date).days
                variables["dias_sin_turno"] = str(delta)

        # 2. Appointment data (if provided)
        if appointment_id:
            apt = await pool.fetchrow(
                """SELECT a.appointment_datetime, a.appointment_type, a.duration_minutes,
                          a.professional_id, a.billing_amount, a.payment_status
                   FROM appointments a
                   WHERE a.id::text = $1 AND a.tenant_id = $2""",
                str(appointment_id), tenant_id,
            )
            if apt:
                apt_dt = apt["appointment_datetime"]
                variables["fecha_turno"] = apt_dt.strftime("%d/%m")
                variables["hora_turno"] = apt_dt.strftime("%H:%M")
                variables["dia_semana"] = _DAYS_ES[apt_dt.weekday()]
                variables["appointment_date"] = apt_dt.strftime("%d/%m")
                variables["appointment_time"] = apt_dt.strftime("%H:%M")

                if apt["billing_amount"]:
                    variables["precio"] = f"${int(apt['billing_amount']):,}".replace(",", ".")
                if apt.get("payment_status") in ("pending", "partial") and apt.get("billing_amount"):
                    variables["saldo_pendiente"] = f"${int(apt['billing_amount']):,}".replace(",", ".")

                # Treatment data
                if apt["appointment_type"]:
                    tt = await pool.fetchrow(
                        "SELECT name, category, base_price FROM treatment_types "
                        "WHERE tenant_id = $1 AND code = $2",
                        tenant_id, apt["appointment_type"],
                    )
                    if tt:
                        variables["tratamiento"] = tt["name"]
                        variables["treatment_name"] = tt["name"]
                        variables["nombre_servicio"] = tt["name"]
                        variables["categoria_tratamiento"] = tt["category"] or ""
                        if not variables["precio"] and tt["base_price"]:
                            variables["precio"] = f"${int(tt['base_price']):,}".replace(",", ".")

                # Professional data
                if apt["professional_id"]:
                    prof = await pool.fetchrow(
                        "SELECT first_name, last_name FROM professionals WHERE id = $1",
                        apt["professional_id"],
                    )
                    if prof:
                        prof_name = f"{prof['first_name']} {prof['last_name'] or ''}".strip()
                        variables["profesional"] = prof_name
                        variables["professional_name"] = prof_name

        # 3. Tenant data
        tenant = await pool.fetchrow(
            "SELECT clinic_name, working_hours, address FROM tenants WHERE id = $1",
            tenant_id,
        )
        if tenant:
            variables["nombre_clinica"] = tenant["clinic_name"] or ""
            variables["clinic_name"] = tenant["clinic_name"] or ""

            # Sede (from working_hours if available)
            wh = tenant["working_hours"]
            if wh and isinstance(wh, dict):
                today_key = _DAYS_ES[datetime.now().weekday()]
                day_config = wh.get(today_key, {})
                if isinstance(day_config, dict) and day_config.get("location"):
                    variables["sede"] = day_config["location"]
            if not variables["sede"] and tenant.get("address"):
                variables["sede"] = tenant["address"]

        # 4. Override with execution context (highest priority)
        for key, val in ctx.items():
            if key in variables and val:
                variables[key] = str(val)

    except Exception as e:
        logger.error(f"Error resolving playbook variables: {e}")

    return variables


def substitute_variables(text: str, variables: dict) -> str:
    """Replace {{variable_name}} placeholders in text with resolved values."""
    if not text:
        return text
    result = text
    for key, value in variables.items():
        result = result.replace(f"{{{{{key}}}}}", str(value or ""))
    return result
