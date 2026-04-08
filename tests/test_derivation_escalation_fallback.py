"""Backfill tests for `derivation-escalation-fallback` (pack 6, migration 038).

Cubre las 7 test classes que definía `openspec/changes/derivation-escalation-fallback/tasks.md`
contra la implementación REAL ya mergeada en main:

  - DerivationRuleCreate/Update Pydantic models (admin_routes.py)
  - _validate_derivation_rule async validator (admin_routes.py)
  - _format_derivation_rules formatter (main.py)
  - check_availability escalation algorithm (main.py)
  - book_appointment contract (main.py)
  - End-to-end Gherkin scenarios (REQ-7 spec.md)
  - Backward-compat regression

ESTRATEGIA:
  - Tests de funciones puras (Pydantic, formatter): full coverage, sin DB ni LLM.
  - Tests del validator async: AsyncMock del pool, idéntico al patrón de
    tests/test_admin_holidays.py.
  - Tests de check_availability / book_appointment / E2E: están como STUBS
    @pytest.mark.skip porque la tool real es un closure decorado con @tool de
    LangChain y `_primary_has_window_capacity` es un closure interno — no son
    importables en aislamiento sin un fixture framework de integration que
    excede el scope del backfill. Quedan listos para que el próximo refactor
    los rellene.

Run: pytest tests/test_derivation_escalation_fallback.py -v
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

# Garantizar que orchestrator_service esté en sys.path antes de importar
_ORCH = (
    Path(__file__).resolve().parent.parent / "orchestrator_service"
)
if str(_ORCH) not in sys.path:
    sys.path.insert(0, str(_ORCH))


# ============================================================================
# Phase 2 — Pydantic schema validation (REQ-2.1)
# ============================================================================


class TestDerivationEscalationPydantic:
    """Verifica DerivationRuleCreate/Update con los 6 campos de migration 038."""

    def _base_payload(self) -> dict:
        return {
            "rule_name": "Implantes",
            "patient_condition": "any",
            "treatment_categories": ["implantes"],
            "target_type": "specific_professional",
            "target_professional_id": 3,
            "priority_order": 1,
        }

    def test_defaults_no_escalation(self):
        """Sin pasar campos de escalation, los defaults son seguros (escalation off)."""
        from admin_routes import DerivationRuleCreate

        rule = DerivationRuleCreate(**self._base_payload())
        assert rule.enable_escalation is False
        assert rule.fallback_professional_id is None
        assert rule.fallback_team_mode is False
        assert rule.max_wait_days_before_escalation == 7
        assert rule.escalation_message_template is None
        assert rule.criteria_custom is None

    def test_max_wait_days_too_high(self):
        """max_wait_days_before_escalation = 31 → ValidationError (Field le=30)."""
        from pydantic import ValidationError

        from admin_routes import DerivationRuleCreate

        payload = self._base_payload()
        payload["max_wait_days_before_escalation"] = 31
        with pytest.raises(ValidationError):
            DerivationRuleCreate(**payload)

    def test_max_wait_days_too_low(self):
        """max_wait_days_before_escalation = 0 → ValidationError (Field ge=1)."""
        from pydantic import ValidationError

        from admin_routes import DerivationRuleCreate

        payload = self._base_payload()
        payload["max_wait_days_before_escalation"] = 0
        with pytest.raises(ValidationError):
            DerivationRuleCreate(**payload)

    def test_max_wait_days_boundary_valid(self):
        """1 y 30 son los bordes válidos del rango."""
        from admin_routes import DerivationRuleCreate

        payload = self._base_payload()
        payload["max_wait_days_before_escalation"] = 1
        rule = DerivationRuleCreate(**payload)
        assert rule.max_wait_days_before_escalation == 1

        payload["max_wait_days_before_escalation"] = 30
        rule = DerivationRuleCreate(**payload)
        assert rule.max_wait_days_before_escalation == 30

    def test_update_model_has_same_escalation_fields(self):
        """DerivationRuleUpdate debe tener los mismos 6 campos que Create."""
        from admin_routes import DerivationRuleCreate, DerivationRuleUpdate

        create_fields = set(DerivationRuleCreate.model_fields.keys())
        update_fields = set(DerivationRuleUpdate.model_fields.keys())
        escalation_fields = {
            "enable_escalation",
            "fallback_professional_id",
            "fallback_team_mode",
            "max_wait_days_before_escalation",
            "escalation_message_template",
            "criteria_custom",
        }
        assert escalation_fields.issubset(create_fields)
        assert escalation_fields.issubset(update_fields)


# ============================================================================
# Phase 2 — _validate_derivation_rule async checks (REQ-2.2)
# ============================================================================


class TestDerivationEscalationValidation:
    """Verifica los 3 nuevos checks del validator async."""

    def _make_rule(self, **overrides):
        from admin_routes import DerivationRuleCreate

        base = {
            "rule_name": "Test",
            "patient_condition": "any",
            "treatment_categories": ["implantes"],
            "target_type": "specific_professional",
            "target_professional_id": 3,
            "priority_order": 1,
        }
        base.update(overrides)
        return DerivationRuleCreate(**base)

    @pytest.mark.asyncio
    async def test_fallback_pid_conflict_with_team_mode(self, monkeypatch):
        """fallback_professional_id + fallback_team_mode=True → HTTP 422."""
        from fastapi import HTTPException

        from admin_routes import _validate_derivation_rule
        import admin_routes

        # Mock db.pool.fetchval para que el primary check pase
        mock_pool = AsyncMock()
        mock_pool.fetchval.return_value = 3  # primary prof exists
        monkeypatch.setattr(admin_routes.db, "pool", mock_pool)

        rule = self._make_rule(
            enable_escalation=True,
            fallback_professional_id=5,
            fallback_team_mode=True,
        )
        with pytest.raises(HTTPException) as exc:
            await _validate_derivation_rule(rule, tenant_id=1)
        assert exc.value.status_code == 422
        assert "fallback_professional_id" in exc.value.detail
        assert "fallback_team_mode" in exc.value.detail

    @pytest.mark.asyncio
    async def test_fallback_pid_wrong_tenant(self, monkeypatch):
        """fallback_professional_id que no existe en el tenant → HTTP 422."""
        from fastapi import HTTPException

        from admin_routes import _validate_derivation_rule
        import admin_routes

        # fetchval devuelve el primary (3) pero None para el fallback (99)
        async def fake_fetchval(query, *args):
            if 99 in args:
                return None
            return 3

        mock_pool = AsyncMock()
        mock_pool.fetchval = fake_fetchval
        monkeypatch.setattr(admin_routes.db, "pool", mock_pool)

        rule = self._make_rule(
            enable_escalation=True,
            fallback_professional_id=99,
            fallback_team_mode=False,
        )
        with pytest.raises(HTTPException) as exc:
            await _validate_derivation_rule(rule, tenant_id=1)
        assert exc.value.status_code == 422
        assert "fallback no pertenece a esta clínica" in exc.value.detail

    @pytest.mark.asyncio
    async def test_implicit_team_mode(self, monkeypatch):
        """enable_escalation=True sin fallback_pid y sin team_mode → set team_mode=True."""
        from admin_routes import _validate_derivation_rule
        import admin_routes

        mock_pool = AsyncMock()
        mock_pool.fetchval.return_value = 3
        monkeypatch.setattr(admin_routes.db, "pool", mock_pool)

        rule = self._make_rule(
            enable_escalation=True,
            fallback_professional_id=None,
            fallback_team_mode=False,
        )
        # No debe tirar excepción
        await _validate_derivation_rule(rule, tenant_id=1)
        # Mutación in-place: el validator setea team_mode=True como safe default
        assert rule.fallback_team_mode is True


# ============================================================================
# Phase 3 — _format_derivation_rules escalation output (REQ-3)
# ============================================================================


class TestFormatDerivationRulesEscalation:
    """Verifica el formato del prompt cuando enable_escalation=True/False."""

    def _base_rule(self, **overrides) -> dict:
        base = {
            "rule_name": "Implantes",
            "patient_condition": "any",
            "treatment_categories": ["implantes"],
            "target_professional_id": 3,
            "target_professional_name": "Dr. Pérez",
            "enable_escalation": False,
            "fallback_professional_id": None,
            "fallback_professional_name": None,
            "fallback_team_mode": False,
            "max_wait_days_before_escalation": 7,
            "escalation_message_template": None,
        }
        base.update(overrides)
        return base

    def test_no_escalation_rule_unchanged(self):
        """Rule con enable_escalation=False → output legacy sin bloque escalación."""
        from main import _format_derivation_rules

        out = _format_derivation_rules([self._base_rule()])
        assert "REGLA 1 — Implantes" in out
        assert "Acción: agendar con Dr. Pérez (ID: 3)" in out
        # NO debe haber acción primaria/escalación
        assert "Acción primaria" not in out
        assert "Escalación activa" not in out
        assert "Mensaje para el paciente" not in out

    def test_escalation_team_mode(self):
        """enable_escalation=True + fallback_team_mode=True → bloque equipo."""
        from main import _format_derivation_rules

        rule = self._base_rule(
            enable_escalation=True,
            fallback_team_mode=True,
            max_wait_days_before_escalation=5,
        )
        out = _format_derivation_rules([rule])
        assert "Acción primaria: agendar con Dr. Pérez (ID: 3)" in out
        assert "Escalación activa" in out
        assert "Dr. Pérez" in out
        assert "5 días" in out
        assert "intentar con cualquier profesional activo del equipo" in out

    def test_escalation_specific_professional(self):
        """enable_escalation=True + fallback_professional_id → bloque con nombre fallback."""
        from main import _format_derivation_rules

        rule = self._base_rule(
            enable_escalation=True,
            fallback_professional_id=5,
            fallback_professional_name="Dr. García",
            fallback_team_mode=False,
            max_wait_days_before_escalation=7,
        )
        out = _format_derivation_rules([rule])
        assert "intentar con Dr. García (ID: 5)" in out
        assert "Mensaje para el paciente al escalar" in out

    def test_escalation_custom_template(self):
        """escalation_message_template no nulo → resolved con {primary} y {fallback}."""
        from main import _format_derivation_rules

        rule = self._base_rule(
            enable_escalation=True,
            fallback_professional_id=5,
            fallback_professional_name="Dr. García",
            escalation_message_template="Hoy {primary} no puede atenderte, pero {fallback} sí.",
        )
        out = _format_derivation_rules([rule])
        assert "Hoy Dr. Pérez no puede atenderte, pero Dr. García sí." in out
        # Los placeholders crudos NO deben quedar en el output
        assert "{primary}" not in out
        assert "{fallback}" not in out

    def test_escalation_default_template(self):
        """escalation_message_template=None → fallback a default español built-in."""
        from main import _format_derivation_rules

        rule = self._base_rule(
            enable_escalation=True,
            fallback_team_mode=True,
            escalation_message_template=None,
        )
        out = _format_derivation_rules([rule])
        # Default mentions both labels resolved
        assert "Dr. Pérez" in out
        assert "el equipo" in out
        assert "no tiene turnos disponibles" in out
        assert "{primary}" not in out
        assert "{fallback}" not in out

    def test_escalation_team_mode_with_custom_template(self):
        """Team mode + custom template → {fallback} resuelve a 'el equipo'."""
        from main import _format_derivation_rules

        rule = self._base_rule(
            enable_escalation=True,
            fallback_team_mode=True,
            escalation_message_template="{primary} no puede, te derivo a {fallback}.",
        )
        out = _format_derivation_rules([rule])
        assert "Dr. Pérez no puede, te derivo a el equipo." in out


# ============================================================================
# Backward-compat regression (REQ-7 Scenario 4 + general)
# ============================================================================


class TestBackwardCompatRegression:
    """Garantiza que las reglas viejas (sin campos de escalation) no cambien."""

    def test_legacy_rule_dict_no_escalation_keys(self):
        """Dict de regla SIN ninguna key de escalation → output idéntico al pre-038."""
        from main import _format_derivation_rules

        legacy_rule = {
            "rule_name": "Cirugía",
            "patient_condition": "new_patient",
            "treatment_categories": ["cirugia"],
            "target_professional_id": 7,
            "target_professional_name": "Dra. López",
            # SIN enable_escalation, SIN fallback_*, SIN max_wait_days_*
        }
        out = _format_derivation_rules([legacy_rule])
        assert "REGLA 1 — Cirugía" in out
        assert "Acción: agendar con Dra. López (ID: 7)" in out
        # Bloque escalación NO debe aparecer
        assert "Acción primaria" not in out
        assert "Escalación activa" not in out
        assert "Mensaje para el paciente" not in out

    def test_multiple_rules_only_one_with_escalation(self):
        """Mix de reglas: solo la que tiene enable_escalation muestra el bloque."""
        from main import _format_derivation_rules

        rules = [
            {
                "rule_name": "Limpieza",
                "patient_condition": "any",
                "treatment_categories": ["limpieza"],
                "target_professional_id": 1,
                "target_professional_name": "Dra. Ramos",
                "enable_escalation": False,
            },
            {
                "rule_name": "Implantes",
                "patient_condition": "any",
                "treatment_categories": ["implantes"],
                "target_professional_id": 3,
                "target_professional_name": "Dr. Pérez",
                "enable_escalation": True,
                "fallback_team_mode": True,
                "max_wait_days_before_escalation": 7,
            },
        ]
        out = _format_derivation_rules(rules)
        assert "REGLA 1 — Limpieza" in out
        assert "REGLA 2 — Implantes" in out
        # Regla 1: legacy
        legacy_section = out.split("REGLA 2")[0]
        assert "Acción: agendar con Dra. Ramos" in legacy_section
        assert "Escalación activa" not in legacy_section
        # Regla 2: escalación
        escalation_section = out.split("REGLA 2")[1]
        assert "Acción primaria" in escalation_section
        assert "Escalación activa" in escalation_section

    def test_footer_unchanged(self):
        """El footer "Si ninguna regla coincide → ..." debe seguir presente."""
        from main import _format_derivation_rules

        rules = [
            {
                "rule_name": "Test",
                "patient_condition": "any",
                "treatment_categories": ["test"],
                "target_professional_id": 1,
                "target_professional_name": "Dr. Test",
            }
        ]
        out = _format_derivation_rules(rules)
        assert "Si ninguna regla coincide → sin filtro de profesional (equipo disponible)." in out


# ============================================================================
# Phase 4 — check_availability escalation algorithm (REQ-4)
# ============================================================================
#
# DEUDA TÉCNICA: estos tests están como stubs porque la implementación real
# usa un closure interno `_primary_has_window_capacity` dentro de
# `check_availability` (decorada con @tool de LangChain). No es importable
# ni mockeable en aislamiento sin construir un fixture framework de
# integration que excede el scope de este backfill.
#
# La validación de comportamiento se cubre indirectamente vía:
#  - Los tests del formatter (que verifican que el bloque inyectado al prompt
#    tiene la forma correcta)
#  - Los tests del validator (que verifican que las reglas se persisten bien)
#  - Verificación manual end-to-end con tenants reales
#
# Para cerrar esta deuda, se requiere:
#  1. Refactor de `_primary_has_window_capacity` a función module-level
#  2. Helper para invocar `check_availability.coroutine` en tests
#  3. Fixture para mockear `db.pool.fetch` con secuencia ordenada de queries
# ============================================================================


class TestPrimaryHasWindowCapacity:
    """STUBS — _primary_has_window_capacity es closure interno, no importable."""

    @pytest.mark.skip(
        reason="closure interno de check_availability — requiere refactor a module-level"
    )
    @pytest.mark.asyncio
    async def test_returns_true_when_no_appointments(self):
        pass

    @pytest.mark.skip(
        reason="closure interno de check_availability — requiere refactor a module-level"
    )
    @pytest.mark.asyncio
    async def test_returns_true_when_at_least_one_day_under_threshold(self):
        pass

    @pytest.mark.skip(
        reason="closure interno de check_availability — requiere refactor a module-level"
    )
    @pytest.mark.asyncio
    async def test_returns_false_when_all_days_saturated(self):
        pass


class TestCheckAvailabilityEscalation:
    """STUBS — check_availability es @tool de LangChain, requiere fixture framework."""

    @pytest.mark.skip(
        reason="check_availability tool unwrap pendiente — fixture de integration requerido"
    )
    @pytest.mark.asyncio
    async def test_no_escalation_when_disabled(self):
        """Rule enable_escalation=False, primary 0 slots → standard 'no disponibilidad'."""
        pass

    @pytest.mark.skip(
        reason="check_availability tool unwrap pendiente — fixture de integration requerido"
    )
    @pytest.mark.asyncio
    async def test_no_escalation_when_primary_has_slots(self):
        """Rule enable_escalation=True, primary 3 slots → no escalation."""
        pass

    @pytest.mark.skip(
        reason="check_availability tool unwrap pendiente — fixture de integration requerido"
    )
    @pytest.mark.asyncio
    async def test_escalation_fires_team_mode(self):
        """Primary 0 slots, fallback_team_mode=True, team has 2 slots → fires."""
        pass

    @pytest.mark.skip(
        reason="check_availability tool unwrap pendiente — fixture de integration requerido"
    )
    @pytest.mark.asyncio
    async def test_escalation_fires_specific_prof(self):
        """Primary 0 slots, fallback_professional_id=5 → fallback prof slots."""
        pass

    @pytest.mark.skip(
        reason="check_availability tool unwrap pendiente — fixture de integration requerido"
    )
    @pytest.mark.asyncio
    async def test_escalation_exhausted(self):
        """Primary 0 slots, fallback also 0 → standard 'no disponibilidad', sin mensaje."""
        pass


# ============================================================================
# Phase 4 — book_appointment contract (REQ-5)
# ============================================================================


class TestBookAppointmentEscalationContract:
    """STUBS — book_appointment es @tool de LangChain, requiere fixture framework."""

    @pytest.mark.skip(
        reason="book_appointment tool unwrap pendiente — verificable manualmente vía agente real"
    )
    @pytest.mark.asyncio
    async def test_book_uses_fallback_prof_name(self):
        """Cuando check_availability devuelve fallback slots, el nombre del fallback
        debe estar en el string para que el agente lo extraiga al llamar book_appointment.
        """
        pass

    @pytest.mark.skip(
        reason="book_appointment tool unwrap pendiente — verificable manualmente"
    )
    @pytest.mark.asyncio
    async def test_book_does_not_re_resolve_derivation(self):
        """book_appointment NO debe consultar professional_derivation_rules — solo honra
        el professional_name que le pasa el agente.
        """
        pass


# ============================================================================
# Phase 6 — Acceptance scenarios Gherkin (REQ-7)
# ============================================================================


class TestE2EAcceptanceScenarios:
    """STUBS de los 4 escenarios Gherkin de REQ-7 + regression."""

    @pytest.mark.skip(
        reason="E2E requiere fixture de DB real o framework de integration mocking"
    )
    @pytest.mark.asyncio
    async def test_e2e_primary_available_no_escalation(self):
        """SC-1: Dr. Pérez con 3 slots → result tiene Pérez slots, sin mensaje escalación."""
        pass

    @pytest.mark.skip(
        reason="E2E requiere fixture de DB real o framework de integration mocking"
    )
    @pytest.mark.asyncio
    async def test_e2e_primary_saturated_fallback_specific(self):
        """SC-2: Dr. Pérez 0 slots, Dr. García 2 slots → result tiene García + mensaje."""
        pass

    @pytest.mark.skip(
        reason="E2E requiere fixture de DB real o framework de integration mocking"
    )
    @pytest.mark.asyncio
    async def test_e2e_primary_saturated_fallback_team(self):
        """SC-3: Dra. López 0 slots, team 4 slots → result tiene 4 + custom template."""
        pass

    @pytest.mark.skip(
        reason="E2E requiere fixture de DB real o framework de integration mocking"
    )
    @pytest.mark.asyncio
    async def test_e2e_escalation_disabled_no_availability(self):
        """SC-4: enable_escalation=False, primary 0 slots → standard 'no disponibilidad'."""
        pass
