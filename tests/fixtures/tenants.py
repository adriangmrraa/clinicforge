"""Canonical tenant row factory.

Provides a single source of truth for building tenant dict fixtures in tests.
Every column in the ``tenants`` table that is NOT NULL (or commonly needed by
service code) is represented here with a sensible default.

Usage::

    from tests.fixtures.tenants import make_tenant_row

    # Minimal — all NOT NULL columns filled:
    tenant = make_tenant_row()

    # With overrides:
    tenant = make_tenant_row(country_code="US", language="en")

The ``language`` key is not a real column — it mirrors the value read by
``holiday_service.py`` via ``COALESCE(config->>'language', ...)`` and is also
used to build pool.fetchrow mocks in holiday tests.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

# Minimal 7-day working_hours structure that passes holiday/availability logic.
# Each day has open=True so the clinic appears to work on all days.
_DEFAULT_WORKING_HOURS: dict = {
    "monday":    {"open": True,  "start": "09:00", "end": "18:00", "location": None},
    "tuesday":   {"open": True,  "start": "09:00", "end": "18:00", "location": None},
    "wednesday": {"open": True,  "start": "09:00", "end": "18:00", "location": None},
    "thursday":  {"open": True,  "start": "09:00", "end": "18:00", "location": None},
    "friday":    {"open": True,  "start": "09:00", "end": "18:00", "location": None},
    "saturday":  {"open": False, "start": "09:00", "end": "13:00", "location": None},
    "sunday":    {"open": False, "start": None,    "end": None,    "location": None},
}


def make_tenant_row(**overrides: Any) -> dict:
    """Return a dict representing a tenants table row with all NOT NULL columns.

    Args:
        **overrides: Any key overrides. ``language`` is a virtual key used by
            holiday_service to pick the locale — default is ``"es"``.

    Returns:
        dict suitable for use as a pool.fetchrow mock return value or as an
        INSERT fixture in integration tests.
    """
    base: dict = {
        # Primary key
        "id": 1,
        # NOT NULL columns (from models.py Tenant class)
        "clinic_name": "Test Clinic",
        "bot_phone_number": f"+54911{uuid.uuid4().int % 10_000_000:07d}",
        "country_code": "AR",
        "ai_engine_mode": "solo",
        "auto_send_review_link_after_followup": False,
        # Commonly used nullable columns (set to safe defaults)
        "config": {},
        "working_hours": _DEFAULT_WORKING_HOURS,
        "consultation_price": None,
        "bank_cbu": None,
        "bank_alias": None,
        "bank_holder_name": None,
        "timezone": "America/Argentina/Buenos_Aires",
        "max_chairs": 2,
        "bot_name": None,
        "owner_email": None,
        "address": None,
        "google_maps_url": None,
        "derivation_email": None,
        # Timestamps
        "created_at": datetime.utcnow(),
        # Virtual key — mirrors COALESCE(config->>'language', 'es') read by holiday_service
        "language": "es",
    }
    base.update(overrides)
    return base


def make_pool_fetchrow(**overrides: Any) -> dict:
    """Shorthand for tests that only need country_code + language in fetchrow mocks.

    Most holiday_service tests mock pool.fetchrow to return just these two fields.
    This helper ensures the ``language`` key is always present alongside
    ``country_code`` so that new columns added to the query don't silently break
    existing tests.
    """
    return make_tenant_row(**overrides)
