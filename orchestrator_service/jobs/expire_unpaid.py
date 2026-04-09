"""Background job: auto-cancel appointments with expired unpaid seña.

Runs every 15 minutes. Finds appointments where:
- sena_expires_at < NOW()
- payment_status = 'pending'
- status IN ('scheduled', 'confirmed')

Cancels them, frees the slot, logs the action, and optionally notifies
the patient via the active channel.
"""

import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


async def expire_unpaid_appointments():
    """Cancel appointments with expired seña. Called by scheduler every 15 min."""
    try:
        from db import db

        pool = db.pool
        if not pool:
            return

        # Find all expired unpaid appointments across all tenants
        expired = await pool.fetch(
            """
            SELECT a.id, a.tenant_id, a.patient_id, a.professional_id,
                   a.appointment_datetime, a.appointment_type, a.sena_expires_at,
                   p.phone_number, p.first_name,
                   t.clinic_name
            FROM appointments a
            JOIN patients p ON a.patient_id = p.id
            JOIN tenants t ON a.tenant_id = t.id
            WHERE a.sena_expires_at IS NOT NULL
              AND a.sena_expires_at < NOW()
              AND a.payment_status = 'pending'
              AND a.status IN ('scheduled', 'confirmed')
              AND a.appointment_datetime > NOW()
            ORDER BY a.sena_expires_at ASC
            LIMIT 50
            """
        )

        if not expired:
            return

        logger.info(f"🧹 Found {len(expired)} appointments with expired seña — cancelling")

        for apt in expired:
            try:
                # Cancel the appointment
                await pool.execute(
                    """
                    UPDATE appointments
                    SET status = 'cancelled',
                        cancellation_reason = 'Seña no pagada dentro del plazo',
                        updated_at = NOW()
                    WHERE id = $1
                    """,
                    apt["id"],
                )

                # Audit log (best-effort)
                try:
                    await pool.execute(
                        """
                        INSERT INTO appointment_audit_log (tenant_id, appointment_id, action, actor, details, created_at)
                        VALUES ($1, $2, 'cancelled', 'system/sena_expiry', $3, NOW())
                        """,
                        apt["tenant_id"],
                        apt["id"],
                        f"Auto-cancelled: seña expired at {apt['sena_expires_at'].isoformat()}",
                    )
                except Exception:
                    pass  # audit is best-effort

                # Emit Socket.IO event (best-effort)
                try:
                    from main import sio
                    await sio.emit("APPOINTMENT_DELETED", {
                        "appointment_id": str(apt["id"]),
                        "tenant_id": apt["tenant_id"],
                        "reason": "sena_expired",
                    })
                except Exception:
                    pass

                logger.info(
                    f"🧹 Cancelled apt={apt['id']} tenant={apt['tenant_id']} "
                    f"patient={apt['first_name']} phone={apt['phone_number']} "
                    f"datetime={apt['appointment_datetime']} "
                    f"expired_at={apt['sena_expires_at']}"
                )

            except Exception as e:
                logger.error(f"🧹 Failed to cancel expired apt {apt['id']}: {e}")

        logger.info(f"🧹 Expired seña job complete: {len(expired)} appointments cancelled")

    except Exception as e:
        logger.error(f"🧹 expire_unpaid_appointments job error: {e}")


def register(scheduler):
    """Register this job with the scheduler."""
    scheduler.add_job(expire_unpaid_appointments, 900, run_at_startup=False)  # Every 15 min
    logger.info("📋 Job registrado: expire_unpaid_appointments cada 900s (15 min)")
