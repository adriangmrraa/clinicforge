"""E2E scenario verification — clinic-payment-financing-config (Phase 5).

Cubre los 5 escenarios patient-query de REQ-4 + regresión backward-compat
(task 5.6) definidos en `openspec/changes/clinic-payment-financing-config/tasks.md`.

Estrategia: prompt-contract tests. Construyen tenant configs realistas, llaman
a `build_system_prompt()` con los kwargs de payment, y verifican que el string
resultante contiene la información concreta que el LLM necesita para responder
cada pregunta del paciente. No invocan al LLM real ni al DB.

Run: pytest tests/test_payment_e2e_scenarios.py -v
"""

import sys
from pathlib import Path

import pytest

_ORCH = (
    Path(__file__).resolve().parent.parent / "orchestrator_service"
)
if str(_ORCH) not in sys.path:
    sys.path.insert(0, str(_ORCH))

from main import build_system_prompt  # noqa: E402


def _baseline_kwargs() -> dict:
    """Config mínima de tenant para armar un prompt sin ruido."""
    return {
        "clinic_name": "Test Clinic",
        "current_time": "2026-04-08 10:00",
        "response_language": "es",
    }


class TestPaymentScenarios:
    def test_q1_card_acceptance(self):
        """REQ-4 Q1: '¿aceptan tarjeta?' — el prompt debe exponer las tarjetas."""
        prompt = build_system_prompt(
            **_baseline_kwargs(),
            payment_methods=["credit_card", "debit_card"],
        )
        assert "## MEDIOS DE PAGO Y FINANCIACIÓN" in prompt
        assert "Tarjeta de crédito" in prompt
        assert "Tarjeta de débito" in prompt
        # Consistencia con flujo de LLM: no debe decir que no tiene info
        assert "no tengo información" not in prompt

    def test_q2_installments(self):
        """REQ-4 Q2: '¿hacen cuotas?' — el prompt debe exponer cuotas y proveedor."""
        prompt = build_system_prompt(
            **_baseline_kwargs(),
            financing_available=True,
            max_installments=6,
            installments_interest_free=True,
            financing_provider="Mercado Pago",
        )
        assert "6 cuotas sin interés" in prompt
        assert "Mercado Pago" in prompt

    def test_q3_cash_discount(self):
        """REQ-4 Q3: '¿hay descuento por efectivo?' — el prompt debe exponer el %."""
        prompt = build_system_prompt(
            **_baseline_kwargs(),
            cash_discount_percent=10.0,
        )
        assert "10%" in prompt
        assert "efectivo" in prompt.lower()

    def test_q4_mercado_pago(self):
        """REQ-4 Q4: '¿trabajan con Mercado Pago?' — debe aparecer en medios de pago."""
        prompt = build_system_prompt(
            **_baseline_kwargs(),
            payment_methods=["transfer", "mercado_pago"],
        )
        assert "Mercado Pago" in prompt
        assert "Transferencia bancaria" in prompt

    def test_q5_crypto_not_accepted(self):
        """REQ-4 Q5: tenant sin crypto ni config payment → NO debe aparecer la sección.

        Esto confirma que el agente NO tiene contenido en el prompt para
        afirmar que acepta crypto — el LLM contestará que no trabajan con eso.
        """
        prompt = build_system_prompt(**_baseline_kwargs())
        assert "## MEDIOS DE PAGO Y FINANCIACIÓN" not in prompt
        assert "criptomonedas" not in prompt.lower()


class TestBackwardCompat:
    def test_backward_compat_no_payment_fields(self):
        """Task 5.6: Tenant existente (Dra. Laura Delgado hoy) sin payment config.

        El prompt NO debe contener la sección ni cambiar el baseline — esto
        garantiza que tenants sin configurar ven cero cambio en el prompt.
        """
        prompt = build_system_prompt(**_baseline_kwargs())
        assert "## MEDIOS DE PAGO Y FINANCIACIÓN" not in prompt
        assert "Medios de pago aceptados" not in prompt
        assert "Financiación disponible" not in prompt
        assert "Descuento por pago en efectivo" not in prompt
        assert "Información orientativa" not in prompt

    def test_all_none_defaults_no_section(self):
        """Pasar todos los kwargs de payment en None/False → sin sección."""
        prompt = build_system_prompt(
            **_baseline_kwargs(),
            payment_methods=None,
            financing_available=False,
            max_installments=None,
            installments_interest_free=True,
            financing_provider="",
            financing_notes="",
            cash_discount_percent=None,
            accepts_crypto=False,
        )
        assert "## MEDIOS DE PAGO Y FINANCIACIÓN" not in prompt

    def test_empty_payment_methods_list_no_section(self):
        """Lista vacía → no genera bloque (payment_methods=[] es falsy)."""
        prompt = build_system_prompt(
            **_baseline_kwargs(),
            payment_methods=[],
        )
        assert "## MEDIOS DE PAGO Y FINANCIACIÓN" not in prompt
