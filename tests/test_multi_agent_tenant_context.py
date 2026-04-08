"""Unit tests for multi-agent tenant context parity (REQ-8).

Pure unit tests — no DB, no HTTP, no LLM. Mocks the asyncpg pool and
exercises the builder + whitelist selection + acceptance scenarios.

Run: pytest tests/test_multi_agent_tenant_context.py
"""
from __future__ import annotations

import sys
import os
from unittest.mock import AsyncMock, MagicMock

import pytest

# Make orchestrator_service importable without running main.py
sys.path.insert(
    0,
    os.path.join(os.path.dirname(__file__), "..", "orchestrator_service"),
)

from agents.tenant_context import (  # noqa: E402
    ALL_BLOCK_KEYS,
    SPECIALIST_BLOCKS,
    build_tenant_context_blocks,
    select_blocks_for_specialist,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_pool(tenant_row=None, insurance_rows=None, treatment_rows=None,
               derivation_rows=None, faq_rows=None):
    """Build an AsyncMock pool that returns the supplied fixtures."""
    pool = MagicMock()

    async def fetchrow(query, *args):
        q = query.lower()
        if "from tenants" in q:
            return tenant_row
        return None

    async def fetch(query, *args):
        q = query.lower()
        if "tenant_insurance_providers" in q:
            return insurance_rows or []
        if "treatment_types" in q:
            return treatment_rows or []
        if "professional_derivation_rules" in q:
            return derivation_rows or []
        if "clinic_faqs" in q:
            return faq_rows or []
        return []

    pool.fetchrow = AsyncMock(side_effect=fetchrow)
    pool.fetch = AsyncMock(side_effect=fetch)
    return pool


# ---------------------------------------------------------------------------
# TestBuildTenantContextBlocks
# ---------------------------------------------------------------------------


class TestBuildTenantContextBlocks:
    @pytest.mark.asyncio
    async def test_returns_all_expected_keys(self):
        pool = _make_pool(tenant_row=None)
        out = await build_tenant_context_blocks(pool, tenant_id=1)
        for key in ALL_BLOCK_KEYS:
            assert key in out, f"missing block: {key}"

    @pytest.mark.asyncio
    async def test_empty_tenant_returns_empty_blocks(self):
        """Legacy clinic — no tenant row, everything should be empty."""
        pool = _make_pool(tenant_row=None)
        out = await build_tenant_context_blocks(pool, tenant_id=999)
        for key in ALL_BLOCK_KEYS:
            val = out[key]
            if key == "sede_info":
                assert val == {} or val is None or val == {"location": "", "address": "", "maps_url": ""}
            else:
                assert val == "" or val is None, f"expected empty for {key}, got {val!r}"

    @pytest.mark.asyncio
    async def test_clinic_basics_populated_from_tenant_row(self):
        tenant_row = {
            "clinic_name": "Clínica Delgado",
            "bot_name": "LUNA",
            "system_prompt_template": "Somos especialistas en implantes.",
            "working_hours": None,
            "bank_cbu": None, "bank_alias": None, "bank_holder_name": None,
        }
        pool = _make_pool(tenant_row=tenant_row)
        out = await build_tenant_context_blocks(pool, tenant_id=1)
        cb = out["clinic_basics"]
        assert "LUNA" in cb
        assert "Clínica Delgado" in cb
        assert "implantes" in cb

    @pytest.mark.asyncio
    async def test_bank_info_populated(self):
        tenant_row = {
            "clinic_name": "X", "bot_name": "TORA", "system_prompt_template": "",
            "working_hours": None,
            "bank_cbu": "1234567890123456789012",
            "bank_alias": "mi.alias.clinica",
            "bank_holder_name": "Laura Delgado",
        }
        pool = _make_pool(tenant_row=tenant_row)
        out = await build_tenant_context_blocks(pool, tenant_id=1)
        bi = out["bank_info"]
        assert "Laura Delgado" in bi
        assert "1234567890123456789012" in bi
        assert "mi.alias.clinica" in bi

    @pytest.mark.asyncio
    async def test_individual_helper_failure_returns_empty_for_that_block(self):
        """A broken fetch on one block must not crash the whole builder."""
        pool = MagicMock()

        async def fetchrow(q, *a):
            raise RuntimeError("simulated DB outage on tenant row")

        async def fetch(q, *a):
            return []

        pool.fetchrow = AsyncMock(side_effect=fetchrow)
        pool.fetch = AsyncMock(side_effect=fetch)
        out = await build_tenant_context_blocks(pool, tenant_id=1)
        # Builder should not raise
        assert out["clinic_basics"] == ""
        # And all keys still present
        for key in ALL_BLOCK_KEYS:
            assert key in out

    @pytest.mark.asyncio
    async def test_intent_tags_accepted(self):
        """intent_tags is forwarded (and optional — None is fine)."""
        pool = _make_pool(tenant_row=None)
        out = await build_tenant_context_blocks(
            pool, tenant_id=1, user_message_text="cuotas", intent_tags={"billing"}
        )
        assert isinstance(out, dict)


# ---------------------------------------------------------------------------
# TestSelectBlocksForSpecialist
# ---------------------------------------------------------------------------


class TestSelectBlocksForSpecialist:
    def _state_with_all_blocks(self) -> dict:
        return {
            "tenant_context": {
                "clinic_basics": "BASICS",
                "faqs_section": "FAQS",
                "holidays_section": "HOLIDAYS",
                "insurance_section": "INSURANCE",
                "payment_section": "PAYMENT",
                "special_conditions_block": "SPECIAL",
                "support_policy_block": "SUPPORT",
                "derivation_rules_section": "DERIV",
                "bank_info": "BANK",
                "sede_info_text": "SEDE",
                "sede_info": {"location": "X"},
            }
        }

    def test_reception_whitelist(self):
        out = select_blocks_for_specialist(self._state_with_all_blocks(), "reception")
        assert set(out.keys()) == {"clinic_basics", "faqs_section", "holidays_section"}
        assert out["clinic_basics"] == "BASICS"
        assert "insurance_section" not in out
        assert "payment_section" not in out

    def test_booking_whitelist(self):
        out = select_blocks_for_specialist(self._state_with_all_blocks(), "booking")
        assert set(out.keys()) == {
            "clinic_basics", "holidays_section", "derivation_rules_section", "sede_info_text",
        }
        # Booking does NOT see insurance/payment
        assert "insurance_section" not in out
        assert "special_conditions_block" not in out

    def test_triage_whitelist(self):
        out = select_blocks_for_specialist(self._state_with_all_blocks(), "triage")
        assert set(out.keys()) == {"clinic_basics", "special_conditions_block"}

    def test_billing_whitelist(self):
        out = select_blocks_for_specialist(self._state_with_all_blocks(), "billing")
        assert set(out.keys()) == {
            "clinic_basics", "insurance_section", "payment_section", "bank_info",
        }
        # Billing does NOT see clinical blocks
        assert "special_conditions_block" not in out

    def test_anamnesis_whitelist(self):
        out = select_blocks_for_specialist(self._state_with_all_blocks(), "anamnesis")
        assert set(out.keys()) == {"clinic_basics", "special_conditions_block"}

    def test_handoff_whitelist(self):
        out = select_blocks_for_specialist(self._state_with_all_blocks(), "handoff")
        assert set(out.keys()) == {"clinic_basics", "support_policy_block"}

    def test_unknown_specialist_returns_clinic_basics_only(self):
        out = select_blocks_for_specialist(self._state_with_all_blocks(), "nonexistent")
        assert set(out.keys()) == {"clinic_basics"}

    def test_missing_tenant_context_returns_empty_strings(self):
        out = select_blocks_for_specialist({}, "booking")
        assert out == {
            "clinic_basics": "",
            "holidays_section": "",
            "derivation_rules_section": "",
            "sede_info_text": "",
        }

    def test_no_specialist_gets_all_blocks(self):
        """Negative test — bound enforcement: no single specialist sees every key."""
        all_keys = set(ALL_BLOCK_KEYS)
        for specialist, allowed in SPECIALIST_BLOCKS.items():
            assert set(allowed) < all_keys, (
                f"{specialist} whitelist should be a strict subset of ALL_BLOCK_KEYS"
            )


# ---------------------------------------------------------------------------
# TestAcceptanceScenarios (REQ-6)
# ---------------------------------------------------------------------------


class TestAcceptanceScenarios:
    def _build_prompt(self, base: str, state: dict, specialist: str) -> str:
        """Mirrors specialists._with_tenant_blocks logic."""
        blocks = select_blocks_for_specialist(state, specialist)
        extras = [v.strip() for v in blocks.values() if v and str(v).strip()]
        if not extras:
            return base
        return base + "\n\n" + "\n\n".join(extras)

    def test_scenario_a_booking_sees_holidays(self):
        state = {
            "tenant_context": {
                "clinic_basics": "## CLÍNICA\nSos TORA",
                "holidays_section": "## FERIADOS\n• 2026-12-25: Navidad — CERRADO",
                "derivation_rules_section": "",
                "sede_info_text": "",
                # Booking should NOT see this:
                "payment_section": "PAYMENT_LEAK",
            }
        }
        prompt = self._build_prompt("Sos el agente de turnos.", state, "booking")
        assert "Navidad" in prompt
        assert "CERRADO" in prompt
        assert "PAYMENT_LEAK" not in prompt  # whitelist enforcement

    def test_scenario_b_billing_answers_payment(self):
        state = {
            "tenant_context": {
                "clinic_basics": "## CLÍNICA\nSos TORA",
                "insurance_section": "## OBRAS SOCIALES\nOSDE: cubierto",
                "payment_section": "## FORMAS DE PAGO\nHasta 12 cuotas sin interés",
                "bank_info": "## DATOS BANCARIOS\nCBU: 123",
                "holidays_section": "HOLIDAYS_LEAK",
            }
        }
        prompt = self._build_prompt("Sos el agente de cobros.", state, "billing")
        assert "12 cuotas" in prompt
        assert "OSDE" in prompt
        assert "HOLIDAYS_LEAK" not in prompt

    def test_scenario_c_triage_applies_special_conditions(self):
        state = {
            "tenant_context": {
                "clinic_basics": "## CLÍNICA",
                "special_conditions_block": "## CONDICIONES\nNo atendemos embarazadas en cirugías",
                "insurance_section": "INSURANCE_LEAK",
            }
        }
        prompt = self._build_prompt("Sos el agente de triaje.", state, "triage")
        assert "embarazadas" in prompt
        assert "INSURANCE_LEAK" not in prompt

    def test_scenario_d_handoff_uses_complaint_protocol(self):
        state = {
            "tenant_context": {
                "clinic_basics": "## CLÍNICA",
                "support_policy_block": "## QUEJAS\nNivel 1: empatizar. Nivel 2: ajuste gratis. Nivel 3: escalar al CEO",
                "payment_section": "PAYMENT_LEAK",
            }
        }
        prompt = self._build_prompt("Sos el agente de derivación.", state, "handoff")
        assert "Nivel 1" in prompt
        assert "empatizar" in prompt
        assert "PAYMENT_LEAK" not in prompt

    def test_scenario_e_empty_config_no_regression(self):
        """Legacy tenant with nothing configured → prompt is just the base."""
        state = {"tenant_context": {}}
        base = "Sos el agente de turnos."
        prompt = self._build_prompt(base, state, "booking")
        assert prompt == base  # exact equality — no bloat added

    def test_scenario_f_token_budget_bound(self):
        """Full config for every specialist stays under a generous char budget."""
        # Rough heuristic: 8000 tokens ~ 32000 chars (4 chars/token).
        big_block = "X" * 2000  # each block ~500 tokens
        state = {
            "tenant_context": {key: big_block for key in ALL_BLOCK_KEYS if key != "sede_info"}
        }
        state["tenant_context"]["sede_info"] = {"location": big_block}

        base_prompt = "A" * 1500  # ~375 tokens of specialist task instructions
        for specialist in SPECIALIST_BLOCKS.keys():
            prompt = self._build_prompt(base_prompt, state, specialist)
            assert len(prompt) < 32000, (
                f"{specialist} prompt exceeds ~8k token budget: {len(prompt)} chars"
            )
