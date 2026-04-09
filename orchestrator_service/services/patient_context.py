"""PatientContext service — minimal multi-layer context for multi-agent core (C3 F3).

Layers (MVP):
- Profile: from `patients` + `medical_history` + recent appointments (read on each turn)
- Working: Redis hash `patient_ctx_working:{tenant_id}:{phone}` TTL 1800s

CRITICAL: All SQL MUST filter by tenant_id.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any, Optional

from sqlalchemy import text

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
    async def load(cls, tenant_id: int, phone_number: str) -> "PatientContext":
        """Load profile from DB. Fails safe to empty profile on errors."""
        profile = PatientProfile()
        try:
            # Lazy import to avoid circulars
            from main import AsyncSessionLocal  # type: ignore
        except Exception as e:
            logger.warning(f"PatientContext.load: AsyncSessionLocal unavailable: {e}")
            return cls(tenant_id, phone_number, profile)

        try:
            async with AsyncSessionLocal() as session:
                # Patient profile (tenant-scoped)
                row = (await session.execute(
                    text("""
                        SELECT id, first_name, last_name, dni, email, human_override_until
                        FROM patients
                        WHERE tenant_id = :tenant_id AND (
                            phone_number = :phone
                            OR REGEXP_REPLACE(phone_number, '[^0-9]', '', 'g') = REGEXP_REPLACE(:phone, '[^0-9]', '', 'g')
                            OR instagram_psid = :phone
                            OR facebook_psid = :phone
                            OR external_ids->>'instagram' = :phone
                            OR external_ids->>'facebook' = :phone
                            OR external_ids->>'chatwoot' = :phone
                        )
                        ORDER BY updated_at DESC NULLS LAST
                        LIMIT 1
                    """),
                    {"tenant_id": tenant_id, "phone": phone_number},
                )).mappings().first()

                if row:
                    profile.is_new_lead = False
                    fn = row.get("first_name") or ""
                    ln = row.get("last_name") or ""
                    profile.name = (fn + " " + ln).strip() or None
                    profile.dni = row.get("dni")
                    profile.email = row.get("email")
                    profile.human_override_until = row.get("human_override_until")
                    patient_id = row.get("id")

                    # Medical history
                    try:
                        mh = (await session.execute(
                            text("""
                                SELECT * FROM medical_history
                                WHERE tenant_id = :tenant_id AND patient_id = :pid
                                LIMIT 1
                            """),
                            {"tenant_id": tenant_id, "pid": patient_id},
                        )).mappings().first()
                        if mh:
                            profile.medical_history = {k: v for k, v in dict(mh).items()
                                                       if k not in ("id", "tenant_id", "patient_id")}
                    except Exception as e:
                        logger.debug(f"medical_history load failed: {e}")

                    # Future appointments
                    try:
                        appts = (await session.execute(
                            text("""
                                SELECT id, date_time, treatment_type, status, professional_id
                                FROM appointments
                                WHERE tenant_id = :tenant_id AND patient_id = :pid
                                  AND date_time >= NOW()
                                ORDER BY date_time ASC
                                LIMIT 5
                            """),
                            {"tenant_id": tenant_id, "pid": patient_id},
                        )).mappings().all()
                        profile.future_appointments = [
                            {
                                "id": a["id"],
                                "date_time": a["date_time"].isoformat() if a["date_time"] else None,
                                "treatment_type": a.get("treatment_type"),
                                "status": a.get("status"),
                                "professional_id": a.get("professional_id"),
                            }
                            for a in appts
                        ]
                    except Exception as e:
                        logger.debug(f"future_appointments load failed: {e}")

                    # Recent chat turns
                    try:
                        turns = (await session.execute(
                            text("""
                                SELECT role, content
                                FROM chat_messages
                                WHERE tenant_id = :tenant_id AND phone_number = :phone
                                ORDER BY created_at DESC
                                LIMIT 10
                            """),
                            {"tenant_id": tenant_id, "phone": phone_number},
                        )).mappings().all()
                        profile.recent_turns = list(reversed([
                            {"role": t["role"], "content": t["content"]} for t in turns
                        ]))
                    except Exception as e:
                        logger.debug(f"recent_turns load failed: {e}")

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
