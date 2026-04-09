"""Helper script: generate tests/fixtures/golden_prompt_whatsapp.txt.

Run once via pytest to create the baseline:
  pytest tests/generate_golden_prompt.py -s

This is NOT a test file — it just uses pytest's import machinery.
"""

import os
from pathlib import Path

from main import build_system_prompt  # resolved via pytest.ini pythonpath (orchestrator_service in sys.path)

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "golden_prompt_whatsapp.txt"

GOLDEN_KWARGS = dict(
    clinic_name="Clínica Dra. Laura Delgado",
    current_time="2026-01-01 10:00",
    response_language="es",
    hours_start="09:00",
    hours_end="18:00",
    ad_context="",
    patient_context="",
    clinic_address="Av. Corrientes 1234, CABA",
    clinic_maps_url="https://maps.google.com/?q=test",
    clinic_working_hours=None,
    faqs=[],
    patient_status="new_lead",
    consultation_price=5000.0,
    sede_info=None,
    anamnesis_url="",
    bank_cbu="",
    bank_alias="",
    bank_holder_name="",
    upcoming_holidays=None,
    insurance_providers=None,
    derivation_rules=None,
    specialty_pitch="",
    professional_name="Laura Delgado",
    bot_name="TORA",
    intent_tags=None,
    is_greeting_pending=True,
    treatment_types=None,
    payment_methods=None,
    financing_available=False,
    max_installments=None,
    installments_interest_free=True,
    financing_provider="",
    financing_notes="",
    cash_discount_percent=None,
    accepts_crypto=False,
    special_conditions_block="",
    support_policy_block="",
)


def test_generate_golden_file(capsys):
    """Write the golden file if it doesn't exist yet."""
    result = build_system_prompt(**GOLDEN_KWARGS)
    FIXTURE_PATH.parent.mkdir(parents=True, exist_ok=True)
    FIXTURE_PATH.write_text(result, encoding="utf-8")
    with capsys.disabled():
        print(f"\nGolden file written: {FIXTURE_PATH} ({len(result)} chars)")
    assert len(result) > 0
