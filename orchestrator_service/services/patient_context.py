"""PatientContext service — minimal multi-layer context for multi-agent core (C3 F3).

Layers (MVP):
- Profile: from `patients` + `medical_history` + recent appointments (read on each turn)
- Working: Redis hash `patient_ctx_working:{tenant_id}:{phone}` TTL 1800s

CRITICAL: All SQL MUST filter by tenant_id.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

# SQLAlchemy removed — migrated to db.pool asyncpg direct queries

logger = logging.getLogger(__name__)

WORKING_TTL_SECONDS = 1800


@dataclass
class PatientProfile:
    name: Optional[str] = None
    dni: Optional[str] = None
    email: Optional[str] = None
    is_new_lead: bool = True
    human_override_until: Optional[Any] = None
    medical_history: dict = field(default_factory=dict)
    recent_turns: list[dict] = field(default_factory=list)
    future_appointments: list[dict] = field(default_factory=list)
    # Phase 1 — CRITICAL (CE1-CE6)
    phone_number: Optional[str] = None       # CE1 — only set if not SIN-TEL
    assigned_professional: Optional[dict] = None  # CE2 — {id, name}
    next_appointment: Optional[dict] = None        # CE3 — {treatment_name, professional_name, date_time}
    last_appointment: Optional[dict] = None         # CE4 — {treatment_name, professional_name, date_time, days_since, status}
    treatment_plan: Optional[dict] = None           # CE5 — {id, name, status, approved_total, paid, pending, ...}
    family_members: list[dict] = field(default_factory=list)  # CE6 — [{name, phone, next_appointment, ...}]
    patient_memories: Optional[str] = None          # RAG memories from format_memories_for_prompt()
    # Phase 2 — HIGH (CE7-CE9)
    children_dependents: list[dict] = field(default_factory=list)  # CE7 — [{name, dni, phone, anamnesis_url, next_appointment}]
    visit_count: Optional[int] = None               # CE8
    anamnesis_status: Optional[dict] = None          # CE9 — {completed: bool, url: str}
    # Phase 3 — MEDIUM (CE11)
    birth_date: Optional[str] = None                # CE11 — ISO string


def _working_key(tenant_id: int, phone_number: str) -> str:
    return f"patient_ctx_working:{tenant_id}:{phone_number}"


class PatientContext:
    def __init__(self, tenant_id: int, phone_number: str, profile: PatientProfile):
        self._tenant_id = tenant_id
        self._phone_number = phone_number
        self._profile = profile

    @property
    def profile(self) -> PatientProfile:
        return self._profile

    @classmethod
    async def load(cls, tenant_id: int, phone_number: str, family_patient_ids: Optional[list[int]] = None) -> "PatientContext":
        """Load profile from DB. Fails safe to empty profile on errors."""
        profile = PatientProfile()
        try:
            from db import db
        except Exception as e:
            logger.warning(f"PatientContext.load: db.pool unavailable: {e}")
            return cls(tenant_id, phone_number, profile)

        try:
            pool = db.pool
            if pool is None:
                logger.warning("PatientContext.load: db.pool is None")
                return cls(tenant_id, phone_number, profile)

            # Patient profile (tenant-scoped) — all phone variants matched via $2
            row = await pool.fetchrow(
                """
                SELECT id, first_name, last_name, dni, email, human_override_until,
                       phone_number, assigned_professional_id, birth_date, anamnesis_token,
                       medical_history
                FROM patients
                WHERE tenant_id = $1 AND (
                    phone_number = $2
                    OR REGEXP_REPLACE(phone_number, '[^0-9]', '', 'g') = REGEXP_REPLACE($2, '[^0-9]', '', 'g')
                    OR instagram_psid = $2
                    OR facebook_psid = $2
                    OR external_ids->>'instagram' = $2
                    OR external_ids->>'facebook' = $2
                    OR external_ids->>'chatwoot' = $2
                )
                ORDER BY updated_at DESC NULLS LAST
                LIMIT 1
                """,
                tenant_id, phone_number,
            )

            if not row:
                return cls(tenant_id, phone_number, profile)

            profile.is_new_lead = False
            row_dict = dict(row)
            fn = (row_dict.get("first_name") or "")
            ln = (row_dict.get("last_name") or "")
            profile.name = (fn + " " + ln).strip() or None
            profile.dni = row_dict.get("dni")
            profile.email = row_dict.get("email")
            profile.human_override_until = row_dict.get("human_override_until")
            patient_id = row_dict.get("id")

            # CE1 — Phone number (skip SIN-TEL prefixed)
            p_phone = row_dict.get("phone_number") or ""
            if p_phone and not p_phone.startswith("SIN-TEL"):
                profile.phone_number = p_phone

            # CE11 — Birth date
            if row_dict.get("birth_date"):
                bd = row_dict["birth_date"]
                profile.birth_date = bd.isoformat() if hasattr(bd, 'isoformat') else str(bd)

            # Medical history (from medical_history TABLE)
            try:
                mh = await pool.fetchrow(
                    "SELECT * FROM medical_history WHERE tenant_id = $1 AND patient_id = $2 LIMIT 1",
                    tenant_id, patient_id,
                )
                if mh:
                    mh_dict = dict(mh)
                    profile.medical_history = {k: v for k, v in mh_dict.items()
                                               if k not in ("id", "tenant_id", "patient_id")}
            except Exception as e:
                logger.debug(f"medical_history load failed: {e}")

            # Future appointments (legacy list — kept for agents that reference it)
            try:
                appts = await pool.fetch(
                    """
                    SELECT id, date_time, treatment_type, status, professional_id
                    FROM appointments
                    WHERE tenant_id = $1 AND patient_id = $2
                      AND date_time >= NOW()
                    ORDER BY date_time ASC
                    LIMIT 5
                    """,
                    tenant_id, patient_id,
                )
                profile.future_appointments = [
                    {
                        "id": a["id"],
                        "date_time": a["date_time"].isoformat() if a["date_time"] else None,
                        "treatment_type": a.get("treatment_type"),
                        "status": a.get("status"),
                        "professional_id": a.get("professional_id"),
                    }
                    for a in (appts or [])
                ]
            except Exception as e:
                logger.debug(f"future_appointments load failed: {e}")

            # Recent chat turns
            try:
                turns = await pool.fetch(
                    """
                    SELECT role, content
                    FROM chat_messages
                    WHERE tenant_id = $1 AND phone_number = $2
                    ORDER BY created_at DESC
                    LIMIT 10
                    """,
                    tenant_id, phone_number,
                )
                profile.recent_turns = list(reversed([
                    {"role": t["role"], "content": t["content"]} for t in (turns or [])
                ]))
            except Exception as e:
                logger.debug(f"recent_turns load failed: {e}")

            # ============= New parallel queries (all independent) =============
            from services.patient_memory import format_memories_for_prompt

            async def _load_assigned_prof():
                """CE2 — Resolve assigned professional name."""
                if row_dict.get("assigned_professional_id"):
                    try:
                        prof = await pool.fetchrow(
                            "SELECT id, first_name, last_name FROM professionals WHERE id = $1 AND tenant_id = $2 AND is_active = true",
                            row_dict["assigned_professional_id"], tenant_id,
                        )
                        if prof:
                            pname = f"{prof['first_name']} {prof.get('last_name') or ''}".strip()
                            profile.assigned_professional = {"id": prof["id"], "name": pname}
                    except Exception as e:
                        logger.debug(f"assigned_professional load failed: {e}")

            async def _load_appointments():
                """CE3 — Next appointment with resolved names."""
                try:
                    next_a = await pool.fetchrow("""
                        SELECT a.date_time, tt.name as treatment_name,
                               prof.first_name as prof_first_name, prof.last_name as prof_last_name
                        FROM appointments a
                        LEFT JOIN treatment_types tt ON a.treatment_type = tt.code
                        LEFT JOIN professionals prof ON a.professional_id = prof.id
                        WHERE a.tenant_id = $1 AND a.patient_id = $2
                          AND a.date_time >= NOW() AND a.status IN ('scheduled','confirmed')
                        ORDER BY a.date_time ASC LIMIT 1
                    """, tenant_id, patient_id)
                    if next_a:
                        dt = next_a["date_time"]
                        profile.next_appointment = {
                            "treatment_name": next_a.get("treatment_name") or "Consulta",
                            "professional_name": f"{next_a.get('prof_first_name') or ''} {next_a.get('prof_last_name') or ''}".strip(),
                            "date_time": dt.isoformat() if dt else None,
                        }
                except Exception as e:
                    logger.debug(f"next_appointment load failed: {e}")

                """CE4 — Last appointment + days_since."""
                try:
                    last_a = await pool.fetchrow("""
                        SELECT a.date_time, tt.name as treatment_name,
                               prof.first_name as prof_first_name, prof.last_name as prof_last_name, a.status
                        FROM appointments a
                        LEFT JOIN treatment_types tt ON a.treatment_type = tt.code
                        LEFT JOIN professionals prof ON a.professional_id = prof.id
                        WHERE a.tenant_id = $1 AND a.patient_id = $2
                          AND a.date_time < NOW() AND a.status IN ('completed','confirmed','scheduled')
                        ORDER BY a.date_time DESC LIMIT 1
                    """, tenant_id, patient_id)
                    if last_a:
                        ldt = last_a["date_time"]
                        days_since = (datetime.now(timezone.utc) - ldt).days if ldt else None
                        profile.last_appointment = {
                            "treatment_name": last_a.get("treatment_name") or "Consulta",
                            "professional_name": f"{last_a.get('prof_first_name') or ''} {last_a.get('prof_last_name') or ''}".strip(),
                            "date_time": ldt.isoformat() if ldt else None,
                            "days_since": days_since,
                            "status": last_a.get("status"),
                        }
                except Exception as e:
                    logger.debug(f"last_appointment load failed: {e}")

                """CE8 — Visit count."""
                try:
                    vc = await pool.fetchval("""
                        SELECT COUNT(*) FROM appointments
                        WHERE tenant_id = $1 AND patient_id = $2
                          AND status IN ('completed','confirmed','scheduled')
                    """, tenant_id, patient_id)
                    profile.visit_count = vc or 0
                except Exception as e:
                    logger.debug(f"visit_count load failed: {e}")

            async def _load_treatment_plan():
                """CE5 — Active treatment plan with payments."""
                try:
                    plan_row = await pool.fetchrow("""
                        SELECT tp.id, tp.name, tp.status, tp.approved_total, tp.estimated_total, tp.notes,
                               COALESCE(SUM(tpp.amount), 0) AS total_paid
                        FROM treatment_plans tp
                        LEFT JOIN treatment_plan_payments tpp ON tpp.plan_id = tp.id AND tpp.tenant_id = tp.tenant_id
                        WHERE tp.tenant_id = $1 AND tp.patient_id = $2
                          AND tp.status IN ('draft','approved','in_progress')
                        GROUP BY tp.id ORDER BY tp.created_at DESC LIMIT 1
                    """, tenant_id, patient_id)
                    if plan_row:
                        approved = float(plan_row.get("approved_total") or plan_row.get("estimated_total") or 0)
                        paid = float(plan_row["total_paid"] or 0)
                        pending = round(approved - paid, 2)
                        notes = {}
                        if plan_row.get("notes"):
                            try:
                                notes = json.loads(plan_row["notes"]) if isinstance(plan_row["notes"], str) else plan_row["notes"]
                            except Exception:
                                pass
                        installments = int(notes.get("installments") or 1)
                        profile.treatment_plan = {
                            "id": plan_row["id"],
                            "name": plan_row["name"],
                            "status": plan_row["status"],
                            "approved_total": approved,
                            "paid": paid,
                            "pending": pending,
                            "installments": installments,
                            "per_installment": round(pending / installments, 2) if installments > 0 and pending > 0 else 0,
                            "discount_pct": float(notes.get("discount_pct") or 0),
                            "discount_amount": float(notes.get("discount_amount") or 0),
                            "conditions": notes.get("payment_conditions"),
                        }
                except Exception as e:
                    logger.debug(f"treatment_plan load failed: {e}")

            async def _load_children():
                """CE7 — Children/dependents via guardian_phone matching."""
                try:
                    chat_phone_clean = re.sub(r'\D', '', phone_number) if phone_number else ""
                    patient_phone_clean = re.sub(r'\D', '', row_dict.get("phone_number") or "") if row_dict else ""
                    guardian_phones = list(set(filter(None, [chat_phone_clean, patient_phone_clean])))
                    if guardian_phones:
                        minor_rows = await pool.fetch("""
                            SELECT id, first_name, last_name, dni, phone_number, anamnesis_token
                            FROM patients WHERE tenant_id = $1
                            AND REGEXP_REPLACE(COALESCE(guardian_phone, ''), '[^0-9]', '', 'g') = ANY($2::text[])
                        """, tenant_id, guardian_phones)
                        if minor_rows:
                            children = []
                            frontend_url = os.getenv("FRONTEND_URL", "http://localhost:4173").split(",")[0].strip().rstrip("/")
                            for m in minor_rows:
                                m_name = f"{m['first_name'] or ''} {m.get('last_name') or ''}".strip()
                                m_token = m.get("anamnesis_token") or str(uuid.uuid4())
                                m_url = f"{frontend_url}/anamnesis/{tenant_id}/{m_token}"
                                # Child's next appointment
                                m_next = await pool.fetchrow("""
                                    SELECT a.date_time FROM appointments a
                                    WHERE a.tenant_id = $1 AND a.patient_id = $2
                                      AND a.date_time >= NOW() AND a.status IN ('scheduled','confirmed')
                                    ORDER BY a.date_time ASC LIMIT 1
                                """, tenant_id, m["id"])
                                children.append({
                                    "name": m_name,
                                    "dni": m.get("dni"),
                                    "phone": m["phone_number"],
                                    "anamnesis_url": m_url,
                                    "next_appointment": m_next["date_time"].isoformat() if (m_next and m_next.get("date_time")) else None,
                                })
                            profile.children_dependents = children
                except Exception as e:
                    logger.debug(f"children load failed: {e}")

            async def _load_anamnesis():
                """CE9 — Anamnesis status from patients.medical_history JSONB."""
                try:
                    mh_jsonb = row_dict.get("medical_history")
                    if isinstance(mh_jsonb, str):
                        mh_jsonb = json.loads(mh_jsonb) if mh_jsonb else {}
                    anamnesis_completed = bool(mh_jsonb and isinstance(mh_jsonb, dict) and mh_jsonb.get("anamnesis_completed_at"))
                    anamnesis_token = row_dict.get("anamnesis_token")
                    if not anamnesis_token:
                        anamnesis_token = str(uuid.uuid4())
                    frontend_url = os.getenv("FRONTEND_URL", "http://localhost:4173").split(",")[0].strip().rstrip("/")
                    profile.anamnesis_status = {
                        "completed": anamnesis_completed,
                        "url": f"{frontend_url}/anamnesis/{tenant_id}/{anamnesis_token}",
                    }
                except Exception as e:
                    logger.debug(f"anamnesis status load failed: {e}")

            async def _load_family_members():
                """CE6 — Family members from family_patient_ids parameter."""
                if family_patient_ids:
                    fmembers = []
                    for fid in family_patient_ids:
                        try:
                            frow = await pool.fetchrow(
                                "SELECT id, first_name, last_name, phone_number FROM patients WHERE id = $1 AND tenant_id = $2",
                                fid, tenant_id,
                            )
                            if frow:
                                fname = f"{frow['first_name'] or ''} {frow.get('last_name') or ''}".strip()
                                fphone = frow.get("phone_number") or ""
                                # Next appointment
                                fn = await pool.fetchrow("""
                                    SELECT a.date_time, tt.name as treatment_name,
                                           prof.first_name as prof_fn, prof.last_name as prof_ln
                                    FROM appointments a
                                    LEFT JOIN treatment_types tt ON a.treatment_type = tt.code
                                    LEFT JOIN professionals prof ON a.professional_id = prof.id
                                    WHERE a.tenant_id = $1 AND a.patient_id = $2
                                      AND a.date_time >= NOW() AND a.status IN ('scheduled','confirmed')
                                    ORDER BY a.date_time ASC LIMIT 1
                                """, tenant_id, fid)
                                # Last appointment
                                fl = await pool.fetchrow("""
                                    SELECT a.date_time, tt.name as treatment_name, a.status
                                    FROM appointments a
                                    LEFT JOIN treatment_types tt ON a.treatment_type = tt.code
                                    WHERE a.tenant_id = $1 AND a.patient_id = $2
                                      AND a.date_time < NOW() AND a.status IN ('completed','confirmed','scheduled')
                                    ORDER BY a.date_time DESC LIMIT 1
                                """, tenant_id, fid)
                                # Visit count
                                fv = await pool.fetchval("""
                                    SELECT COUNT(*) FROM appointments
                                    WHERE tenant_id = $1 AND patient_id = $2
                                      AND status IN ('completed','confirmed','scheduled')
                                """, tenant_id, fid)
                                # Latest clinical record
                                fdiag = await pool.fetchrow("""
                                    SELECT diagnosis, treatment_plan
                                    FROM clinical_records
                                    WHERE tenant_id = $1 AND patient_id = $2
                                    ORDER BY created_at DESC LIMIT 1
                                """, tenant_id, fid)

                                next_apt_str = None
                                if fn and fn.get("date_time"):
                                    fndt = fn["date_time"]
                                    next_apt_str = f"{fn.get('treatment_name') or 'Consulta'} con Dr/a. {fn.get('prof_fn') or ''} {fn.get('prof_ln') or ''} el {fndt.isoformat() if hasattr(fndt, 'isoformat') else str(fndt)}"

                                last_apt_str = None
                                if fl and fl.get("date_time"):
                                    fldt = fl["date_time"]
                                    fldays = (datetime.now(timezone.utc) - fldt).days if hasattr(fldt, 'isoformat') else None
                                    last_apt_str = f"{fl.get('treatment_name') or 'Consulta'} el {fldt.isoformat() if hasattr(fldt, 'isoformat') else str(fldt)} (hace {fldays} días). Estado: {fl.get('status')}"

                                fmembers.append({
                                    "name": fname,
                                    "phone": fphone,
                                    "next_appointment_str": next_apt_str,
                                    "last_appointment_str": last_apt_str,
                                    "visits": fv or 0,
                                    "diagnosis": fdiag["diagnosis"] if (fdiag and fdiag.get("diagnosis")) else None,
                                    "treatment_plan_text": fdiag["treatment_plan"] if (fdiag and fdiag.get("treatment_plan")) else None,
                                })
                        except Exception as e:
                            logger.debug(f"family member {fid} load failed: {e}")
                    profile.family_members = fmembers

            async def _load_patient_memories():
                """CE6 — RAG memories from format_memories_for_prompt."""
                try:
                    mem_text = await format_memories_for_prompt(pool, phone_number, tenant_id, query="")
                    if mem_text:
                        profile.patient_memories = mem_text
                except Exception as e:
                    logger.debug(f"patient_memories load failed: {e}")

            # Run all independent queries in parallel
            await asyncio.gather(
                _load_assigned_prof(),
                _load_appointments(),
                _load_treatment_plan(),
                _load_children(),
                _load_anamnesis(),
                _load_family_members(),
                _load_patient_memories(),
                return_exceptions=True,
            )

        except Exception as e:
            logger.exception(f"PatientContext.load failed for tenant={tenant_id} phone={phone_number}: {e}")

        return cls(tenant_id, phone_number, profile)

    async def get_working(self) -> dict:
        try:
            from services.relay import get_redis
            r = get_redis()
            if r is None:
                return {}
            raw = await r.get(_working_key(self._tenant_id, self._phone_number))
            if not raw:
                return {}
            return json.loads(raw)
        except Exception as e:
            logger.warning(f"get_working failed: {e}")
            return {}

    async def set_working(self, **updates) -> None:
        try:
            from services.relay import get_redis
            r = get_redis()
            if r is None:
                return
            current = await self.get_working()
            current.update(updates)
            await r.set(
                _working_key(self._tenant_id, self._phone_number),
                json.dumps(current, default=str),
                ex=WORKING_TTL_SECONDS,
            )
        except Exception as e:
            logger.warning(f"set_working failed: {e}")

    async def reset_working(self) -> None:
        try:
            from services.relay import get_redis
            r = get_redis()
            if r is None:
                return
            await r.delete(_working_key(self._tenant_id, self._phone_number))
        except Exception as e:
            logger.warning(f"reset_working failed: {e}")
