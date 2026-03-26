"""
Public routes — no authentication required.
Used for patient-facing forms like the anamnesis checklist.
"""
import json
import logging
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from db import db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/public", tags=["Public"])


class AnamnesisFormSubmission(BaseModel):
    base_diseases: Optional[List[str]] = None
    base_diseases_other: Optional[str] = None
    habitual_medication: Optional[str] = None
    allergies: Optional[List[str]] = None
    allergies_other: Optional[str] = None
    previous_surgeries: Optional[str] = None
    is_smoker: Optional[str] = None
    smoker_amount: Optional[str] = None
    pregnancy_lactation: Optional[str] = None
    negative_experiences: Optional[str] = None
    specific_fears: Optional[List[str]] = None
    specific_fears_other: Optional[str] = None


@router.get("/anamnesis/{tenant_id}/{token}")
async def get_anamnesis_form(tenant_id: int, token: str):
    """
    Get patient basic info (name, clinic) WITHOUT medical data.
    Medical data requires DNI verification first.
    """
    patient = await db.pool.fetchrow(
        """SELECT id, first_name, last_name, dni
           FROM patients WHERE tenant_id = $1 AND anamnesis_token = $2""",
        tenant_id, token
    )
    if not patient:
        raise HTTPException(status_code=404, detail="Formulario no encontrado o link inválido.")

    tenant = await db.pool.fetchrow(
        "SELECT clinic_name FROM tenants WHERE id = $1", tenant_id
    )

    # Only return basic info — medical data requires DNI verification
    has_dni = bool(patient.get("dni") and patient["dni"].strip())
    return {
        "patient_name": f"{patient['first_name'] or ''} {patient['last_name'] or ''}".strip(),
        "clinic_name": tenant["clinic_name"] if tenant else "Clínica",
        "requires_dni": has_dni,  # If patient has DNI, require verification
        "existing_data": {},  # Empty until verified
    }


class DniVerification(BaseModel):
    dni: str


@router.post("/anamnesis/{tenant_id}/{token}/verify")
async def verify_anamnesis_dni(tenant_id: int, token: str, body: DniVerification):
    """
    Verify patient DNI to unlock the anamnesis form.
    Returns medical data only after successful verification.
    """
    patient = await db.pool.fetchrow(
        """SELECT id, first_name, last_name, dni, medical_history
           FROM patients WHERE tenant_id = $1 AND anamnesis_token = $2""",
        tenant_id, token
    )
    if not patient:
        raise HTTPException(status_code=404, detail="Formulario no encontrado.")

    # Clean both DNIs for comparison (remove dots, spaces, dashes)
    import re
    clean_input = re.sub(r'[^0-9]', '', body.dni.strip())
    clean_stored = re.sub(r'[^0-9]', '', (patient["dni"] or "").strip())

    if not clean_stored:
        # Patient has no DNI stored — allow access (first time)
        pass
    elif clean_input != clean_stored:
        raise HTTPException(status_code=403, detail="DNI incorrecto. Verificá e intentá de nuevo.")

    mh = patient["medical_history"] or {}
    if isinstance(mh, str):
        try:
            mh = json.loads(mh)
        except Exception:
            mh = {}

    return {
        "verified": True,
        "patient_name": f"{patient['first_name'] or ''} {patient['last_name'] or ''}".strip(),
        "existing_data": mh,
    }


@router.post("/anamnesis/{tenant_id}/{token}/voice-session")
async def create_anamnesis_voice_session(tenant_id: int, token: str):
    """Create a Nova voice session for guided anamnesis. Public — validated by anamnesis token."""
    import uuid
    patient = await db.pool.fetchrow(
        "SELECT id, first_name, last_name FROM patients WHERE tenant_id = $1 AND anamnesis_token = $2",
        tenant_id, token
    )
    if not patient:
        raise HTTPException(status_code=404, detail="Token inválido.")

    tenant = await db.pool.fetchrow("SELECT clinic_name FROM tenants WHERE id = $1", tenant_id)
    clinic_name = tenant["clinic_name"] if tenant else "Clínica"
    patient_name = f"{patient['first_name'] or ''} {patient['last_name'] or ''}".strip()

    session_id = uuid.uuid4().hex
    session_config = {
        "tenant_id": tenant_id,
        "user_role": "patient",
        "user_id": str(patient["id"]),
        "page": "anamnesis",
        "system_prompt": (
            f"IDIOMA OBLIGATORIO: Español argentino. Voseo.\n"
            f"Sos Nova, asistente de voz de {clinic_name}.\n"
            f"Estás ayudando a {patient_name} a completar su ficha médica (anamnesis) por voz.\n\n"
            "FLUJO: Guiá al paciente pregunta por pregunta:\n"
            "1. Enfermedades de base (diabetes, hipertensión, cardiopatía, problemas de coagulación, hepatitis, HIV/SIDA, osteoporosis, tiroides, epilepsia, asma, enfermedad renal, artritis reumatoidea)\n"
            "2. Medicación habitual\n"
            "3. Alergias (penicilina, amoxicilina, látex, anestesia local, AINES, aspirina, metales)\n"
            "4. Cirugías previas\n"
            "5. Si fuma y cuánto\n"
            "6. Embarazo o lactancia (si aplica)\n"
            "7. Experiencias negativas previas en el dentista\n"
            "8. Miedos específicos (agujas, dolor, ruido del torno, asfixia, sangre, anestesia, sillón dental)\n\n"
            "REGLAS:\n"
            "- Preguntá DE A UNA categoría por vez\n"
            "- Sé conciso: máximo 2 oraciones por pregunta\n"
            "- Si dice 'no' o 'ninguna', avanzá a la siguiente\n"
            "- Al final, resumí lo que registraste y preguntá si está todo bien\n"
            "- Tono cálido y tranquilizador — es info médica sensible\n"
        ),
    }

    try:
        from services.relay import get_redis
        redis = await get_redis()
        await redis.setex(f"nova_session:{session_id}", 600, json.dumps(session_config))
    except Exception as e:
        logger.error(f"Redis error creating anamnesis voice session: {e}")
        raise HTTPException(status_code=500, detail="Error creando sesión de voz.")

    return {"session_id": session_id}


@router.post("/anamnesis/{tenant_id}/{token}")
async def submit_anamnesis_form(tenant_id: int, token: str, data: AnamnesisFormSubmission):
    """
    Save anamnesis from the public form.
    No auth required — token is the patient's unique anamnesis_token.
    """
    patient = await db.pool.fetchrow(
        "SELECT id FROM patients WHERE tenant_id = $1 AND anamnesis_token = $2",
        tenant_id, token
    )
    if not patient:
        raise HTTPException(status_code=404, detail="Formulario no encontrado o link inválido.")

    # Build medical_history JSONB
    mh = {}

    if data.base_diseases:
        items = list(data.base_diseases)
        if data.base_diseases_other:
            items.append(data.base_diseases_other)
        mh["base_diseases"] = ", ".join(items) if items else "Ninguna"

    if data.habitual_medication is not None:
        mh["habitual_medication"] = data.habitual_medication or "Ninguna"

    if data.allergies:
        items = list(data.allergies)
        if data.allergies_other:
            items.append(data.allergies_other)
        mh["allergies"] = ", ".join(items) if items else "Ninguna"

    if data.previous_surgeries is not None:
        mh["previous_surgeries"] = data.previous_surgeries or "Ninguna"

    if data.is_smoker is not None:
        mh["is_smoker"] = data.is_smoker
    if data.smoker_amount is not None:
        mh["smoker_amount"] = data.smoker_amount

    if data.pregnancy_lactation is not None:
        mh["pregnancy_lactation"] = data.pregnancy_lactation

    if data.negative_experiences is not None:
        mh["negative_experiences"] = data.negative_experiences or "Ninguna"

    if data.specific_fears:
        items = list(data.specific_fears)
        if data.specific_fears_other:
            items.append(data.specific_fears_other)
        mh["specific_fears"] = ", ".join(items) if items else "Ninguno"

    mh["anamnesis_completed_at"] = datetime.now(timezone.utc).isoformat()
    mh["anamnesis_completed_via"] = "public_form"

    try:
        await db.pool.execute(
            """UPDATE patients
               SET medical_history = COALESCE(medical_history, '{}'::jsonb) || $1::jsonb,
                   updated_at = NOW()
               WHERE id = $2 AND tenant_id = $3""",
            json.dumps(mh), patient["id"], tenant_id
        )

        # Emit Socket.IO event for real-time UI update
        try:
            from main import app
            sio = getattr(app.state, "sio", None)
            to_json_safe = getattr(app.state, "to_json_safe", lambda x: x)
            if sio:
                await sio.emit('PATIENT_UPDATED', to_json_safe({
                    'patient_id': patient["id"],
                    'tenant_id': tenant_id,
                    'update_type': 'anamnesis_saved',
                }))
        except Exception:
            pass

        return {"status": "ok", "message": "Ficha médica guardada correctamente."}
    except Exception as e:
        logger.error(f"Error saving public anamnesis: {e}")
        raise HTTPException(status_code=500, detail="Error al guardar la ficha médica.")
