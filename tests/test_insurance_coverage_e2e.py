"""E2E verification tests — insurance-coverage-by-treatment (Phase 5).

Cubre los 6 escenarios Gherkin de REQ-4 en
`openspec/changes/insurance-coverage-by-treatment/spec.md`.

Estrategia: estos tests validan el contrato entre los datos de
`tenant_insurance_providers` y el bloque de texto que
`_format_insurance_providers` inyecta en el system prompt del agente.
No invocan al LLM ni al DB — verifican que la información concreta que el
agente necesita para responder cada escenario REALMENTE llegue al prompt.
Si el prompt contiene los datos correctos, el LLM puede contestar; si no
los contiene, el agente no tiene forma de hacerlo bien.

Run: pytest tests/test_insurance_coverage_e2e.py -v
"""

import sys
from pathlib import Path

import pytest

# Asegurar que orchestrator_service esté en sys.path para importar main
_ORCH = (
    Path(__file__).resolve().parent.parent / "orchestrator_service"
)
if str(_ORCH) not in sys.path:
    sys.path.insert(0, str(_ORCH))

from main import _format_insurance_providers  # noqa: E402


# ---------------------------------------------------------------------------
# Fixtures — providers y treatment_display_map reutilizables
# ---------------------------------------------------------------------------

TREATMENT_DISPLAY_MAP = {
    "IMPT": "Implante dental",
    "EXTRAC": "Extracción",
    "BLAN": "Blanqueamiento",
    "LIMPZ": "Limpieza",
    "CONS": "Consulta",
}


def _base_provider(**overrides) -> dict:
    """Construye un provider con defaults seguros y permite overrides."""
    base = {
        "id": 1,
        "provider_name": "OSDE",
        "status": "accepted",
        "external_target": None,
        "requires_copay": False,
        "copay_notes": None,
        "ai_response_template": None,
        "sort_order": 0,
        "is_active": True,
        "coverage_by_treatment": {},
        "is_prepaid": False,
        "employee_discount_percent": None,
        "default_copay_percent": None,
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# Scenario A — Copay percentage
# ---------------------------------------------------------------------------


def test_copay_percent_displayed():
    """REQ-4 A: OSDE cubre IMPT con coseguro 30% → el prompt debe exponerlo."""
    providers = [
        _base_provider(
            provider_name="OSDE",
            coverage_by_treatment={
                "IMPT": {"covered": True, "copay_percent": 30},
            },
        )
    ]

    output = _format_insurance_providers(providers, TREATMENT_DISPLAY_MAP)

    assert "OSDE" in output
    assert "Implante dental" in output
    assert "(IMPT)" in output
    assert "cubierto" in output
    assert "coseguro 30%" in output
    # El agente NO debe caer al bullet de fallback legacy cuando hay cobertura
    assert "coseguro estándar" not in output


# ---------------------------------------------------------------------------
# Scenario B — Pre-authorization
# ---------------------------------------------------------------------------


def test_preauthorization_displayed():
    """REQ-4 B: Swiss Medical requiere preautorización (3 días) para EXTRAC."""
    providers = [
        _base_provider(
            provider_name="Swiss Medical",
            is_prepaid=True,
            coverage_by_treatment={
                "EXTRAC": {
                    "covered": True,
                    "copay_percent": 0,
                    "requires_pre_authorization": True,
                    "pre_auth_leadtime_days": 3,
                },
            },
        )
    ]

    output = _format_insurance_providers(providers, TREATMENT_DISPLAY_MAP)

    assert "Swiss Medical" in output
    assert "(prepaga)" in output
    assert "Extracción" in output
    assert "requiere preautorización" in output
    assert "3 días hábiles" in output


# ---------------------------------------------------------------------------
# Scenario C — Waiting period
# ---------------------------------------------------------------------------


def test_waiting_period_displayed():
    """REQ-4 C: OSDE tiene carencia de 180 días para IMPT."""
    providers = [
        _base_provider(
            provider_name="OSDE",
            coverage_by_treatment={
                "IMPT": {
                    "covered": True,
                    "copay_percent": 0,
                    "waiting_period_days": 180,
                },
            },
        )
    ]

    output = _format_insurance_providers(providers, TREATMENT_DISPLAY_MAP)

    assert "OSDE" in output
    assert "Implante dental" in output
    assert "carencia 180 días" in output


# ---------------------------------------------------------------------------
# Scenario D — Not covered
# ---------------------------------------------------------------------------


def test_not_covered_labeled():
    """REQ-4 D: Swiss Medical NO cubre blanqueamiento → debe figurar en NO cubiertos."""
    providers = [
        _base_provider(
            provider_name="Swiss Medical",
            is_prepaid=True,
            coverage_by_treatment={
                "BLAN": {"covered": False},
            },
        )
    ]

    output = _format_insurance_providers(providers, TREATMENT_DISPLAY_MAP)

    assert "Swiss Medical" in output
    assert "NO cubiertos:" in output
    assert "Blanqueamiento" in output
    assert "(BLAN)" in output
    # Y no debe aparecer como cubierto por accidente
    cubiertos_idx = output.find("Cubiertos:")
    no_cubiertos_idx = output.find("NO cubiertos:")
    if cubiertos_idx != -1 and no_cubiertos_idx != -1:
        # Si ambas secciones existen, BLAN debe estar después de "NO cubiertos:"
        assert output.rfind("Blanqueamiento") > no_cubiertos_idx


# ---------------------------------------------------------------------------
# Scenario E — Prepaga vs obra social distinction
# ---------------------------------------------------------------------------


def test_prepaid_flag_shown():
    """REQ-4 E: Swiss Medical es prepaga → flag explícito en el header del provider."""
    providers = [
        _base_provider(
            provider_name="Swiss Medical",
            is_prepaid=True,
            coverage_by_treatment={
                "CONS": {"covered": True, "copay_percent": 0},
            },
        ),
        _base_provider(
            id=2,
            provider_name="OSDE",
            is_prepaid=False,
            coverage_by_treatment={
                "CONS": {"covered": True, "copay_percent": 0},
            },
        ),
    ]

    output = _format_insurance_providers(providers, TREATMENT_DISPLAY_MAP)

    # Swiss Medical debe llevar el flag (prepaga); OSDE no
    assert "Swiss Medical (prepaga)" in output
    # OSDE NO debe tener el flag — buscamos la línea exacta del header
    assert "OSDE (prepaga)" not in output
    assert "OSDE" in output


# ---------------------------------------------------------------------------
# Scenario F — Default copay fallback
# ---------------------------------------------------------------------------


def test_default_copay_fallback():
    """REQ-4 F: OSDE tiene default_copay_percent=20 y no configuró LIMPZ.

    El prompt debe exponer el default_copay a nivel provider para que el LLM
    pueda usarlo como fallback cuando no hay entrada específica del tratamiento.
    """
    providers = [
        _base_provider(
            provider_name="OSDE",
            default_copay_percent=20,
            coverage_by_treatment={
                # Intencionalmente sin LIMPZ — sólo IMPT
                "IMPT": {"covered": True, "copay_percent": 30},
            },
        )
    ]

    output = _format_insurance_providers(providers, TREATMENT_DISPLAY_MAP)

    # El header del provider debe exponer el default copay
    assert "coseguro por defecto: 20%" in output
    assert "OSDE" in output
    # LIMPZ no fue configurado, así que no debe aparecer como entrada
    assert "LIMPZ" not in output
    assert "Limpieza" not in output
    # Pero sí debe estar la entrada configurada
    assert "Implante dental" in output
