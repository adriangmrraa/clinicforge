"""
digital_records_service.py — Layer 1: Data Gathering for Digital Patient Records.

Fetches all patient-related data from the DB in parallel and normalizes it into
a single structured JSON payload ready for rendering/templating.

Rules:
- All queries include tenant_id (multi-tenant isolation)
- Returns None for missing fields; NEVER infers or guesses
- Handles asyncpg returning JSONB as strings (known project pattern)
- Odontogram is normalized from legacy and v2 formats to a canonical v2 shape
"""

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)


# =============================================================================
# HELPERS
# =============================================================================


def _safe_json(value) -> object:
    """Parse a value that asyncpg may return as a raw JSON string or already-parsed object."""
    if value is None:
        return None
    if isinstance(value, str):
        try:
            return json.loads(value)
        except (json.JSONDecodeError, ValueError):
            return None
    return value


def format_date(d) -> Optional[str]:
    """Format a date/datetime value as DD/MM/YYYY. Returns None for falsy input."""
    if d is None:
        return None
    if isinstance(d, str):
        return d
    try:
        return d.strftime("%d/%m/%Y")
    except Exception:
        return None


def format_time(dt) -> Optional[str]:
    """Extract HH:MM from a datetime. Returns None for falsy input."""
    if dt is None:
        return None
    if isinstance(dt, str):
        return dt
    try:
        return dt.strftime("%H:%M")
    except Exception:
        return None


def normalize_odontogram(raw) -> dict:
    """
    Normalize odontogram data to canonical v2 format:
        {"teeth": [...], "affected_count": int, "format_version": "2.0"}

    Handles:
    - None / missing
    - Strings (JSONB returned as str by asyncpg)
    - v2 dicts with {"teeth": [...]}
    - Legacy dicts keyed by tooth number e.g. {"18": "caries", "17": "healthy"}
    """
    empty = {"teeth": [], "affected_count": 0, "format_version": "2.0"}

    if raw is None:
        return empty

    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except (json.JSONDecodeError, ValueError):
            return empty

    if not isinstance(raw, dict):
        return empty

    # v3 format: {"version": "3.0", "permanent": {"teeth": [...]}, "deciduous": {"teeth": [...]}}
    if raw.get("version") == "3.0" and ("permanent" in raw or "deciduous" in raw):
        teeth = []
        for dentition_key in ("permanent", "deciduous"):
            dentition = raw.get(dentition_key, {})
            if isinstance(dentition, dict):
                for t in dentition.get("teeth", []):
                    if not isinstance(t, dict):
                        continue
                    # Flatten v3 surfaces {sk: {state, condition, color}} → {sk: state_str}
                    flat_surfaces = {}
                    for sk, sv in t.get("surfaces", {}).items():
                        if isinstance(sv, dict):
                            flat_surfaces[sk] = sv.get("state", "healthy")
                        elif isinstance(sv, str):
                            flat_surfaces[sk] = sv
                    teeth.append({
                        "id": t.get("id"),
                        "state": t.get("state", "healthy"),
                        "surfaces": flat_surfaces,
                        "notes": t.get("notes", ""),
                    })
        affected = sum(1 for t in teeth if t.get("state", "healthy") != "healthy")
        return {"teeth": teeth, "affected_count": affected, "format_version": "2.0"}

    # v2 format: {"teeth": [...]}
    if "teeth" in raw and isinstance(raw["teeth"], list):
        teeth = raw["teeth"]
        affected = sum(1 for t in teeth if t.get("state", "healthy") != "healthy")
        return {"teeth": teeth, "affected_count": affected, "format_version": "2.0"}

    # Legacy format: {"18": "caries", "17": "healthy"} or {"18": {"status": "caries"}}
    if raw and all(str(k).isdigit() for k in raw.keys()):
        teeth = []
        for k, v in raw.items():
            if isinstance(v, str):
                state = v
            elif isinstance(v, dict):
                state = v.get("status", "healthy")
            else:
                state = "healthy"
            teeth.append({"id": int(k), "state": state})
        affected = sum(1 for t in teeth if t.get("state", "healthy") != "healthy")
        return {"teeth": teeth, "affected_count": affected, "format_version": "2.0"}

    return empty


def extract_anamnesis(medical_history) -> Optional[dict]:
    """
    Extract anamnesis fields from the patients.medical_history JSONB column.
    Returns None if the column is empty/null or unparseable.
    """
    if not medical_history:
        return None

    if isinstance(medical_history, str):
        try:
            medical_history = json.loads(medical_history)
        except (json.JSONDecodeError, ValueError):
            return None

    if not isinstance(medical_history, dict):
        return None

    # All keys may be absent — return None for each missing key (not empty string)
    return {
        "base_diseases": medical_history.get("base_diseases") or None,
        "allergies": medical_history.get("allergies") or None,
        "habitual_medication": medical_history.get("habitual_medication") or None,
        "previous_surgeries": medical_history.get("previous_surgeries") or None,
        "is_smoker": medical_history.get("is_smoker"),  # Boolean — preserve False
        "pregnancy_lactation": medical_history.get("pregnancy_lactation") or None,
    }


def _anamnesis_completeness(anamnesis: Optional[dict]) -> str:
    """Return 'complete', 'partial', or 'empty' based on how many fields are filled."""
    if anamnesis is None:
        return "empty"
    filled = sum(1 for v in anamnesis.values() if v is not None)
    if filled == 0:
        return "empty"
    if filled == len(anamnesis):
        return "complete"
    return "partial"


def _patient_completeness(patient_row) -> str:
    """'complete' if all key identity fields present, else 'partial'."""
    required = ["first_name", "last_name", "dni", "birth_date", "phone_number", "email"]
    if patient_row is None:
        return "partial"
    missing = sum(1 for f in required if not patient_row.get(f))
    return "complete" if missing == 0 else "partial"


# =============================================================================
# MAIN GATHER FUNCTION
# =============================================================================


async def gather_patient_data(
    pool,
    patient_id: int,
    tenant_id: int,
    template_type: str,
    professional_id: Optional[int] = None,
) -> dict:
    """
    Layer 1: Gather all patient data from DB into structured JSON for digital records.

    Args:
        pool: asyncpg pool (pass db.pool from the caller)
        patient_id: target patient's DB id
        tenant_id: tenant context — ALL queries are scoped to this
        template_type: document type label (e.g. 'historia_clinica', 'informe_odontograma')
        professional_id: optional — if None, falls back to the professional on the last clinical record

    Returns:
        Structured dict ready for rendering.  Missing fields are None, NEVER fabricated.

    Raises:
        ValueError: if the patient is not found for this tenant.
    """
    logger.info(
        "gather_patient_data start | patient_id=%s tenant_id=%s template=%s",
        patient_id,
        tenant_id,
        template_type,
    )

    # ------------------------------------------------------------------
    # Parallel queries — each uses its own connection from the pool
    # (asyncpg does NOT allow concurrent queries on a single connection)
    # ------------------------------------------------------------------
    (
        patient_row,
        clinical_rows,
        odontogram_row,
        appointment_rows,
        tenant_row,
        next_appt_row,
        summary_row,
    ) = await asyncio.gather(
        pool.fetchrow(
            "SELECT * FROM patients WHERE id=$1 AND tenant_id=$2",
            patient_id,
            tenant_id,
        ),
        pool.fetch(
            """
            SELECT id, record_date, diagnosis, clinical_notes, treatments,
                   recommendations, odontogram_data, professional_id
            FROM clinical_records
            WHERE patient_id=$1 AND tenant_id=$2
            ORDER BY record_date DESC
            LIMIT 20
            """,
            patient_id,
            tenant_id,
        ),
        pool.fetchrow(
            """
            SELECT odontogram_data
            FROM clinical_records
            WHERE patient_id=$1 AND tenant_id=$2 AND odontogram_data IS NOT NULL
            ORDER BY created_at DESC
            LIMIT 1
            """,
            patient_id,
            tenant_id,
        ),
        pool.fetch(
            """
            SELECT a.id, a.appointment_datetime, a.status, a.billing_amount,
                   a.payment_status, tt.name AS treatment_name
            FROM appointments a
            LEFT JOIN treatment_types tt
                ON a.appointment_type = tt.code AND a.tenant_id = tt.tenant_id
            WHERE a.patient_id=$1 AND a.tenant_id=$2
            ORDER BY a.appointment_datetime DESC
            LIMIT 10
            """,
            patient_id,
            tenant_id,
        ),
        pool.fetchrow(
            """
            SELECT clinic_name, address, bot_phone_number AS phone, country_code
            FROM tenants WHERE id=$1
            """,
            tenant_id,
        ),
        pool.fetchrow(
            """
            SELECT a.appointment_datetime, tt.name AS treatment_name
            FROM appointments a
            LEFT JOIN treatment_types tt
                ON a.appointment_type = tt.code AND a.tenant_id = tt.tenant_id
            WHERE a.patient_id=$1 AND a.tenant_id=$2
              AND a.status IN ('scheduled', 'confirmed')
              AND a.appointment_datetime > NOW()
            ORDER BY a.appointment_datetime ASC
            LIMIT 1
            """,
            patient_id,
            tenant_id,
        ),
        pool.fetchrow(
            """
            SELECT summary_text, attachments_count, attachments_types, created_at
            FROM clinical_record_summaries
            WHERE patient_id = $1 AND tenant_id = $2
            ORDER BY created_at DESC
            LIMIT 1
            """,
            patient_id,
            tenant_id,
        ),
    )

    # ------------------------------------------------------------------
    # Professional — resolve after the parallel block (depends on clinical_rows)
    # ------------------------------------------------------------------
    prof_row = None
    effective_prof_id = professional_id

    if effective_prof_id is None and clinical_rows:
        # Fall back to the professional on the most recent clinical record
        effective_prof_id = clinical_rows[0].get("professional_id")

        if effective_prof_id is not None:
            prof_row = await pool.fetchrow(
                """
                SELECT p.id,
                       p.first_name || ' ' || p.last_name AS full_name
                FROM professionals p
                JOIN users u ON p.user_id = u.id
                WHERE p.id=$1 AND p.tenant_id=$2
                """,
                effective_prof_id,
                tenant_id,
            )

    # ------------------------------------------------------------------
    # Validate patient exists
    # ------------------------------------------------------------------
    if patient_row is None:
        raise ValueError(f"Patient {patient_id} not found for tenant {tenant_id}")

    # ------------------------------------------------------------------
    # Build professional lookup map (id → name) for clinical records
    # ------------------------------------------------------------------
    # We only resolve names for professional_ids actually referenced in the records
    prof_ids_needed = set()
    for row in clinical_rows:
        pid = row.get("professional_id")
        if pid is not None:
            prof_ids_needed.add(pid)

    prof_name_map: dict[int, str] = {}
    if prof_row is not None and effective_prof_id is not None:
        prof_name_map[effective_prof_id] = prof_row.get("full_name") or ""

    # Fetch names for any other professionals referenced in clinical records
    remaining_ids = prof_ids_needed - set(prof_name_map.keys())
    if remaining_ids:
        async with pool.acquire() as conn2:
            extra_profs = await conn2.fetch(
                """
                SELECT p.id, p.first_name || ' ' || p.last_name AS full_name
                FROM professionals p
                WHERE p.id = ANY($1::int[]) AND p.tenant_id=$2
                """,
                list(remaining_ids),
                tenant_id,
            )
        for ep in extra_profs:
            prof_name_map[ep["id"]] = ep.get("full_name") or ""

    # ------------------------------------------------------------------
    # Assemble output
    # ------------------------------------------------------------------

    # ---- Patient ----
    first_name = patient_row.get("first_name") or ""
    last_name = patient_row.get("last_name") or ""
    full_name = f"{first_name} {last_name}".strip() or None

    patient_section = {
        "full_name": full_name,
        "first_name": first_name or None,
        "last_name": last_name or None,
        "dni": patient_row.get("dni") or None,
        "birth_date": format_date(patient_row.get("birth_date")),
        "phone": patient_row.get("phone_number") or None,
        "email": patient_row.get("email") or None,
        "insurance": patient_row.get("insurance_provider") or None,
        "insurance_id": patient_row.get("insurance_id") or None,
    }

    # ---- Professional ----
    professional_section = {
        "full_name": (prof_row.get("full_name") if prof_row else None) or None,
        "mp": None,  # Not in DB yet — always placeholder
        "specialty": None,  # Not in DB yet — always placeholder
    }

    # ---- Clinic ----
    clinic_section = {
        "name": (tenant_row.get("clinic_name") if tenant_row else None) or "Clínica",
        "address": (tenant_row.get("address") if tenant_row else None) or None,
        "phone": (tenant_row.get("phone") if tenant_row else None) or None,
        "logo_url": (tenant_row.get("logo_url") if tenant_row else None) or None,
        "country_code": (tenant_row.get("country_code") if tenant_row else None)
        or "AR",
    }

    # ---- Clinical Records ----
    clinical_section = []
    source_record_ids = []

    for rec in clinical_rows:
        rec_id = str(rec["id"]) if rec.get("id") is not None else None
        if rec_id:
            source_record_ids.append(rec_id)

        treatments_raw = _safe_json(rec.get("treatments"))
        treatments_list = treatments_raw if isinstance(treatments_raw, list) else []

        rec_prof_id = rec.get("professional_id")
        rec_prof_name = (
            prof_name_map.get(rec_prof_id) if rec_prof_id is not None else None
        )

        clinical_section.append(
            {
                "id": rec_id,
                "date": format_date(rec.get("record_date")),
                "diagnosis": rec.get("diagnosis") or None,
                "clinical_notes": rec.get("clinical_notes") or None,
                "treatments": treatments_list,
                "recommendations": rec.get("recommendations") or None,
                "professional_name": rec_prof_name or None,
            }
        )

    # ---- Odontogram ----
    raw_odontogram = odontogram_row.get("odontogram_data") if odontogram_row else None
    odontogram_section = normalize_odontogram(raw_odontogram)

    # ---- Appointments ----
    appointments_section = []
    source_appointment_ids = []

    for appt in appointment_rows:
        appt_id = str(appt["id"]) if appt.get("id") is not None else None
        if appt_id:
            source_appointment_ids.append(appt_id)

        dt = appt.get("appointment_datetime")
        amount = appt.get("billing_amount")

        appointments_section.append(
            {
                "date": format_date(dt),
                "time": format_time(dt),
                "treatment": appt.get("treatment_name") or None,
                "status": appt.get("status") or None,
                "amount": float(amount) if amount is not None else None,
            }
        )

    # ---- Next Appointment ----
    next_appointment_section = None
    if next_appt_row:
        next_dt = next_appt_row.get("appointment_datetime")
        next_appointment_section = {
            "date": format_date(next_dt),
            "time": format_time(next_dt),
            "reason": next_appt_row.get("treatment_name") or None,
        }

    # ---- Anamnesis ----
    raw_medical_history = _safe_json(patient_row.get("medical_history"))
    anamnesis_section = extract_anamnesis(raw_medical_history)

    # ---- Attachment Summary ----
    attachment_summary = {}
    if summary_row and summary_row.get("summary_text"):
        attachment_summary = {
            "summary_text": summary_row["summary_text"],
            "attachments_count": summary_row["attachments_count"],
            "attachments_types": summary_row["attachments_types"],
            "created_at": summary_row["created_at"].isoformat()
            if summary_row["created_at"]
            else None,
        }

    # ------------------------------------------------------------------
    # _meta — completeness + source IDs
    # ------------------------------------------------------------------
    meta = {
        "source_record_ids": source_record_ids,
        "source_appointment_ids": source_appointment_ids,
        "data_completeness": {
            "patient": _patient_completeness(patient_row),
            "clinical_records": "complete" if clinical_section else "empty",
            "odontogram": "complete" if odontogram_section["teeth"] else "empty",
            "anamnesis": _anamnesis_completeness(anamnesis_section),
            "appointments": "complete" if appointments_section else "empty",
            "next_appointment": "complete" if next_appointment_section else "empty",
        },
    }

    result = {
        "document_type": template_type,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "patient": patient_section,
        "professional": professional_section,
        "clinic": clinic_section,
        "clinical_records": clinical_section,
        "odontogram": odontogram_section,
        "appointments": appointments_section,
        "next_appointment": next_appointment_section,
        "anamnesis": anamnesis_section,
        "attachment_summary": attachment_summary,
        "_meta": meta,
    }

    logger.info(
        "gather_patient_data done | patient_id=%s records=%d appointments=%d odontogram_teeth=%d",
        patient_id,
        len(clinical_section),
        len(appointments_section),
        len(odontogram_section["teeth"]),
    )

    return result


# =============================================================================
# LAYER 2: AI NARRATIVE GENERATION
# =============================================================================

import asyncio as _asyncio
import os
import re
from openai import AsyncOpenAI

_BASE_SYSTEM_PROMPT = """\
Sos un redactor médico legal. Redactás informes clínicos odontológicos formales.

REGLAS ANTI-ALUCINACIÓN (OBLIGATORIAS):
1. SOLO podés usar datos del JSON que te proporcionan. NADA MÁS.
2. Si un dato es null o no está → escribí "No registrado" o dejá la sección vacía.
3. JAMÁS inventés un número de pieza, una fecha, un nombre, un diagnóstico, un tratamiento, un material ni un monto.
4. JAMÁS infierás información que no está explícita en el JSON.
5. Si te falta un dato para una oración → reescribí sin ese dato o indicá "[dato pendiente de completar]".
6. Usá tercera persona pasiva: "se realizó", "se procedió", "se observa", "se informa".
7. NUNCA primera persona, segunda persona, opiniones ni pronósticos.
8. Piezas dentarias: SIEMPRE notación FDI con punto (4.2, 3.1). NUNCA nombres coloquiales.
9. Fechas: DD/MM/AAAA. Montos: $ con punto de miles.
10. VERIFICACIÓN: antes de responder, revisá que CADA pieza, fecha, tratamiento y nombre mencionado esté en el JSON.

FORMATO DE RESPUESTA:
Respondé SOLO con un JSON válido con las secciones que te pido. Cada sección es un string con el texto narrativo.\
"""

_TEMPLATE_INSTRUCTIONS: dict[str, str] = {
    "clinical_report": """\

SECCIONES A GENERAR (JSON keys):
- "resumen_clinico": Resumen del estado clínico actual del paciente basado en los registros. 2-3 párrafos.
- "antecedentes": Antecedentes relevantes de la anamnesis (enfermedades base, alergias, medicación). Si no hay datos → "No se registran antecedentes médicos relevantes."
- "estado_dental": Descripción del estado dental basada en el odontograma. Mencionar piezas afectadas con FDI.
- "tratamientos_realizados": Resumen de tratamientos según clinical_records. Fechas y procedimientos.
- "plan_tratamiento": Plan de tratamiento si hay registros con treatment_plan. Si no → "A definir en consulta."
- "recomendaciones": Recomendaciones basadas en recommendations de los registros. Si no hay → sección vacía.
- "documentacion_adicional": Si attachment_summary.summary_text existe, incluir: "Documentación adicional: {attachment_summary.summary_text}". Si no, omitir esta sección.\
""",
    "post_surgery": """\

SECCIONES A GENERAR (JSON keys):
- "contexto": "Se informa que el/la paciente [nombre] se encuentra en seguimiento por [diagnóstico del registro más antiguo]."
- "antecedente_quirurgico": Describir procedimientos previos según clinical_records. Solo si hay más de 1 registro.
- "procedimiento_actual": "En la fecha, se procedió a [tratamiento del registro más reciente], realizándose bajo condiciones clínicas adecuadas, sin complicaciones intraoperatorias." SOLO si los clinical_notes NO mencionan complicaciones.
- "evolucion": "El/la paciente evoluciona dentro de parámetros esperables para el tipo de intervención realizada." Frase fija.
- "conducta": "Se indica control postoperatorio para evaluación de cicatrización y evolución de tejidos blandos."
- "proximo_turno": Solo si next_appointment no es null. "Próximo turno programado:\\nFecha: [fecha]\\nHora: [hora]\\nMotivo: [reason]"
- "constancia": "Se deja constancia que los tiempos de evolución y controles indicados corresponden a la complejidad del procedimiento realizado." Frase fija.\
""",
    "odontogram_art": """\

SECCIONES A GENERAR (JSON keys):
- "tipo_evaluacion": "Se realiza evaluación clínica odontológica y confección de odontograma."
- "hallazgos": Enumerar hallazgos del odontograma: piezas con restauraciones, caries, ausentes, implantes, etc. Agrupar por estado. "Estado bucal general compatible con los hallazgos clínicos observados."
- "observacion": "[Motivo de emisión — dato pendiente de completar]" a menos que haya info de ART/OS en el JSON.\
""",
    "authorization_request": """\

SECCIONES A GENERAR (JSON keys):
- "diagnostico": Diagnóstico detallado basado en clinical_records + odontograma. Mencionar piezas FDI, causa, afectación.
- "tratamiento_realizado": Qué se hizo hasta ahora según clinical_records. Si no hay → "Sin tratamientos previos registrados."
- "tratamiento_solicitado": "[Tratamiento solicitado — dato pendiente de completar]". La AI NO puede inventar qué autorización se pide.
- "material_objetivo": "[Material y objetivo — dato pendiente de completar]" si no hay info.
- "justificacion": "Este tipo de rehabilitación/tratamiento es necesaria/o debido a [diagnóstico del JSON]." Basarse SOLO en datos existentes.
- "valor": Monto si hay billing_amount en appointments. Si no → "[Valor pendiente de completar]"
- "observaciones": Campo vacío para completar manualmente.\
""",
}


def _build_system_prompt(template_type: str) -> str:
    """Combine the base anti-hallucination prompt with template-specific instructions."""
    extra = _TEMPLATE_INSTRUCTIONS.get(template_type, "")
    return _BASE_SYSTEM_PROMPT + extra


async def _call_openai(
    system_prompt: str, user_content: str, model: str = "gpt-4o-mini"
) -> dict:
    """Low-level async OpenAI call with JSON response format."""
    client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    response = await client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ],
        response_format={"type": "json_object"},
        temperature=0.3,
        max_completion_tokens=2000,
    )
    return json.loads(response.choices[0].message.content)


async def generate_narrative(
    pool,
    tenant_id: int,
    template_type: str,
    source_data: dict,
) -> dict:
    """
    Layer 2: Generate AI narrative sections for a digital record.

    1. Reads the AI model from system_config (key OPENAI_MODEL), falls back to gpt-4o-mini.
    2. Builds the system prompt (base anti-hallucination rules + template-specific sections).
    3. Calls OpenAI chat completions with response_format=json_object.
    4. Runs post-validation to detect possible hallucinations.
    5. Returns {"sections": {...}, "warnings": [...], "model_used": "..."}.
    """
    # --- Resolve model from DB ---
    model = "gpt-4o-mini"
    try:
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT value FROM system_config WHERE tenant_id=$1 AND key='OPENAI_MODEL'",
                tenant_id,
            )
        if row and row.get("value"):
            model = str(row["value"]).strip() or model
    except Exception as model_err:
        logger.warning(
            "generate_narrative: could not read model from system_config: %s", model_err
        )

    logger.info(
        "generate_narrative start | tenant_id=%s template=%s model=%s",
        tenant_id,
        template_type,
        model,
    )

    # --- Build prompts ---
    system_prompt = _build_system_prompt(template_type)
    user_content = json.dumps(source_data, default=str, ensure_ascii=False)

    # --- Call OpenAI ---
    try:
        sections = await _call_openai(system_prompt, user_content, model=model)
    except Exception as ai_err:
        logger.error("generate_narrative: OpenAI call failed: %s", ai_err)
        raise

    # --- Post-validation ---
    try:
        warnings = validate_narrative(sections, source_data)
    except Exception as val_err:
        logger.warning("generate_narrative: validation error (non-fatal): %s", val_err)
        warnings = []

    if warnings:
        logger.warning(
            "generate_narrative: %d hallucination warning(s) | tenant_id=%s template=%s",
            len(warnings),
            tenant_id,
            template_type,
        )

    return {
        "sections": sections,
        "warnings": warnings,
        "model_used": model,
    }


# =============================================================================
# LAYER 2b: ANTI-HALLUCINATION VALIDATOR
# =============================================================================


def validate_narrative(narrative_sections: dict, source_data: dict) -> list:
    """
    Post-validation: scan the generated narrative for hallucination signals.

    Checks:
    1. FDI tooth numbers in text not present in the patient's odontogram.
    2. Dates in text not present anywhere in the source data.
    3. Speculative/predictive language.
    4. Medication dosages not present in source data.

    Returns a list of warning strings (empty = clean).
    """
    warnings = []
    full_text = " ".join(str(v) for v in narrative_sections.values())
    source_json_str = json.dumps(source_data, default=str)

    # 1. Detect FDI numbers in text not present in source
    fdi_in_text = set(re.findall(r"\b(\d\.\d)\b", full_text))
    fdi_in_source: set = set()
    for tooth in source_data.get("odontogram", {}).get("teeth", []):
        tid = tooth.get("id", 0)
        if isinstance(tid, int):
            fdi_in_source.add(f"{tid // 10}.{tid % 10}")
    unknown_fdi = fdi_in_text - fdi_in_source
    if unknown_fdi:
        warnings.append(f"Piezas FDI no presentes en datos del paciente: {unknown_fdi}")

    # 2. Detect dates in text not in source
    dates_in_text = set(re.findall(r"\b(\d{1,2}/\d{1,2}/\d{2,4})\b", full_text))
    dates_in_source = set(re.findall(r"\b(\d{1,2}/\d{1,2}/\d{2,4})\b", source_json_str))
    unknown_dates = dates_in_text - dates_in_source
    if unknown_dates:
        warnings.append(f"Fechas no presentes en datos del paciente: {unknown_dates}")

    # 3. Detect speculative language
    speculative = [
        "probablemente",
        "posiblemente",
        "podría",
        "debería mejorar",
        "se espera que",
        "es probable",
        "likely",
        "probably",
        "should improve",
    ]
    for word in speculative:
        if word.lower() in full_text.lower():
            warnings.append(f"Lenguaje especulativo detectado: '{word}'")

    # 4. Detect medication dosages not in source
    dosages = re.findall(r"\b\d+\s*mg\b", full_text, re.IGNORECASE)
    for dosage in dosages:
        if dosage not in source_json_str:
            warnings.append(f"Dosificación no presente en datos: '{dosage}'")

    return warnings


# =============================================================================
# LAYER 3: HTML ASSEMBLY (Jinja2)
# =============================================================================

from jinja2 import Environment, FileSystemLoader

_TEMPLATE_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "templates",
    "digital_records",
)


def _get_jinja_env() -> Environment:
    return Environment(loader=FileSystemLoader(_TEMPLATE_DIR))


def assemble_html(
    template_type: str,
    source_data: dict,
    ai_sections: dict,
    odontogram_svg: str = "",
) -> str:
    """
    Render the Jinja2 HTML template for the given template_type.

    Args:
        template_type: e.g. "clinical_report", "post_surgery"
        source_data: the structured JSON from gather_patient_data()
        ai_sections: the sections dict from generate_narrative()["sections"]
        odontogram_svg: optional SVG string for odontogram templates

    Returns:
        Rendered HTML string.

    Raises:
        jinja2.TemplateNotFound if the template file does not exist.
    """
    try:
        env = _get_jinja_env()
        template = env.get_template(f"{template_type}.html")
        return template.render(
            data=source_data,
            ai=ai_sections,
            odontogram_svg=odontogram_svg,
        )
    except Exception as err:
        logger.error(
            "assemble_html: failed for template_type=%s: %s", template_type, err
        )
        raise


# =============================================================================
# LAYER 4: PDF GENERATION (WeasyPrint)
# =============================================================================


def generate_pdf_sync(html_content: str, output_path: str) -> str:
    """
    Synchronous PDF generation via WeasyPrint.
    Intended to be called via asyncio.to_thread — never call directly from async code.

    Returns the output_path on success.
    """
    try:
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        from weasyprint import HTML as _WP_HTML  # lazy import — optional dependency

        _WP_HTML(string=html_content, base_url=_TEMPLATE_DIR).write_pdf(output_path)
        logger.info("generate_pdf_sync: wrote %s", output_path)
        return output_path
    except Exception as err:
        logger.error("generate_pdf_sync: failed for path=%s: %s", output_path, err)
        raise


async def generate_pdf(html_content: str, output_path: str) -> str:
    """
    Async wrapper for generate_pdf_sync — runs WeasyPrint in a thread pool.

    Returns the output_path on success.
    """
    import asyncio

    return await asyncio.to_thread(generate_pdf_sync, html_content, output_path)


# =============================================================================
# LAYER 5: PER-SECTION REGENERATION HELPER
# =============================================================================


def replace_section(html: str, section_id: str, new_content: str) -> str:
    """
    Replace the inner content of a <div data-section="..."> block in an HTML string.

    Targets the FIRST matching div with attribute data-section="{section_id}".
    The opening and closing tags are preserved; only the inner content is replaced.

    Returns the modified HTML string (original unchanged if no match found).
    """
    try:
        pattern = (
            rf'(<div[^>]*data-section="{re.escape(section_id)}"[^>]*>)(.*?)(</div>)'
        )
        result = re.sub(pattern, rf"\1{new_content}\3", html, flags=re.DOTALL, count=1)
        return result
    except Exception as err:
        logger.error("replace_section: failed for section_id=%s: %s", section_id, err)
        return html
