"""Unit tests for _format_payment_options() — Phase 3.

Cubren los 17 casos de tasks.md Task 3.1 + 1 integración con build_system_prompt.
No requieren DB ni LLM — es una función pura que arma el bloque de texto que se
inyecta al system prompt.

Run: pytest tests/test_payment_formatter.py -v
"""

import sys
from pathlib import Path

import pytest

_ORCH = (
    Path(__file__).resolve().parent.parent / "orchestrator_service"
)
if str(_ORCH) not in sys.path:
    sys.path.insert(0, str(_ORCH))

from main import _format_payment_options  # noqa: E402


class TestFormatPaymentOptions:
    # --- empty / no-config (backward compat) --------------------------------

    def test_empty_config_returns_empty_string(self):
        assert _format_payment_options() == ""

    def test_none_payment_methods_returns_empty_string(self):
        assert _format_payment_options(payment_methods=None) == ""

    # --- payment_methods ----------------------------------------------------

    def test_payment_methods_emits_labels(self):
        output = _format_payment_options(payment_methods=["cash", "credit_card"])
        assert "Efectivo" in output
        assert "Tarjeta de crédito" in output

    def test_unknown_method_token_falls_back_to_token(self):
        output = _format_payment_options(payment_methods=["other_new"])
        # No debe crashear, y debe exponer el token crudo
        assert "other_new" in output

    # --- financing block ----------------------------------------------------

    def test_financing_block_emitted_when_true(self):
        output = _format_payment_options(
            financing_available=True,
            max_installments=6,
            installments_interest_free=True,
            financing_provider="MP",
        )
        assert "6 cuotas sin interés" in output
        assert "MP" in output

    def test_financing_block_not_emitted_when_false(self):
        output = _format_payment_options(
            financing_available=False,
            max_installments=6,
        )
        assert "cuotas" not in output

    def test_installments_with_interest(self):
        output = _format_payment_options(
            financing_available=True,
            max_installments=3,
            installments_interest_free=False,
        )
        assert "con interés" in output

    def test_financing_notes_included(self):
        output = _format_payment_options(
            financing_available=True,
            financing_notes="Solo Visa",
        )
        assert "Solo Visa" in output

    # --- cash discount ------------------------------------------------------

    def test_cash_discount_emitted(self):
        output = _format_payment_options(cash_discount_percent=10.0)
        assert "10%" in output
        assert "efectivo" in output.lower()

    def test_cash_discount_zero_not_emitted(self):
        output = _format_payment_options(cash_discount_percent=0.0)
        # 0% no genera línea
        assert "Descuento" not in output

    def test_cash_discount_none_not_emitted(self):
        output = _format_payment_options(cash_discount_percent=None)
        assert "Descuento" not in output

    def test_integer_discount_no_decimal_point(self):
        output = _format_payment_options(cash_discount_percent=10.0)
        assert "10%" in output
        assert "10.0%" not in output

    # --- crypto -------------------------------------------------------------

    def test_accepts_crypto_emitted(self):
        output = _format_payment_options(accepts_crypto=True)
        assert "criptomonedas" in output.lower()

    def test_accepts_crypto_false_not_emitted(self):
        output = _format_payment_options(accepts_crypto=False)
        assert "criptomonedas" not in output.lower()

    # --- disclaimer ---------------------------------------------------------

    def test_disclaimer_present_when_any_field_set(self):
        output = _format_payment_options(payment_methods=["cash"])
        assert "Información orientativa" in output

    def test_disclaimer_absent_when_empty(self):
        output = _format_payment_options()
        assert "Información orientativa" not in output

    # --- full sample --------------------------------------------------------

    def test_full_config_sample_output(self):
        output = _format_payment_options(
            payment_methods=["cash", "credit_card", "debit_card", "mercado_pago"],
            financing_available=True,
            max_installments=6,
            installments_interest_free=True,
            financing_provider="Mercado Pago",
            financing_notes="Válido solo con Visa y Mastercard, hasta dic 2026.",
            cash_discount_percent=10.0,
        )
        assert "## MEDIOS DE PAGO Y FINANCIACIÓN" in output
        assert "Medios de pago aceptados:" in output
        assert "Efectivo" in output
        assert "Tarjeta de crédito" in output
        assert "Tarjeta de débito" in output
        assert "Mercado Pago" in output
        assert "6 cuotas sin interés" in output
        assert "Válido solo con Visa" in output
        assert "10%" in output
        assert "Información orientativa" in output


class TestBuildSystemPromptIntegration:
    """Verifica que build_system_prompt inyecta el payment_section cuando corresponde
    y que NO rompe el baseline cuando los kwargs de payment están en default.
    """

    def test_build_system_prompt_with_payment_section(self):
        from main import build_system_prompt

        prompt = build_system_prompt(
            clinic_name="Test Clinic",
            current_time="2026-04-08 10:00",
            response_language="es",
            payment_methods=["cash", "credit_card"],
            cash_discount_percent=15.0,
        )
        assert "## MEDIOS DE PAGO Y FINANCIACIÓN" in prompt
        assert "Efectivo" in prompt
        assert "Tarjeta de crédito" in prompt
        assert "15%" in prompt

    def test_build_system_prompt_backward_compat_no_payment(self):
        """Tenant sin config de payment → el prompt NO debe contener la sección."""
        from main import build_system_prompt

        prompt = build_system_prompt(
            clinic_name="Test Clinic",
            current_time="2026-04-08 10:00",
            response_language="es",
        )
        assert "## MEDIOS DE PAGO Y FINANCIACIÓN" not in prompt
