"""Multi-agent tenant context builder.

Builds the tenant-configured prompt blocks ONCE per turn, stores them in
AgentState["tenant_context"], and each specialist reads only the subset
whitelisted for its role via select_blocks_for_specialist().

See openspec/changes/multi-agent-tenant-context-parity/ for the full spec.
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


# Canonical list of all block keys the builder produces.
# `sede_info` is the only dict value; everything else is a formatted string.
ALL_BLOCK_KEYS: tuple[str, ...] = (
    "clinic_basics",
    "insurance_section",
    "payment_section",
    "special_conditions_block",
    "support_policy_block",
    "derivation_rules_section",
    "holidays_section",
    "faqs_section",
    "bank_info",
    "sede_info",          # dict
    "sede_info_text",     # string rendering of sede_info for prompt interpolation
)


# Per-specialist block whitelist (REQ-4.1 / design D3).
# Each specialist sees ONLY the blocks relevant to its stage of TORA's flow.
# Keeps token budget focused and prevents cross-specialist info leak.
SPECIALIST_BLOCKS: dict[str, list[str]] = {
    "reception": ["clinic_basics", "faqs_section", "holidays_section"],
    "booking":   ["clinic_basics", "holidays_section", "derivation_rules_section", "sede_info_text"],
    "triage":    ["clinic_basics", "special_conditions_block"],
    "billing":   ["clinic_basics", "insurance_section", "payment_section", "bank_info"],
    "anamnesis": ["clinic_basics", "special_conditions_block"],
    "handoff":   ["clinic_basics", "support_policy_block"],
}

# Invariant check: every whitelisted block must exist in ALL_BLOCK_KEYS.
_unknown = {k for keys in SPECIALIST_BLOCKS.values() for k in keys} - set(ALL_BLOCK_KEYS)
assert not _unknown, f"SPECIALIST_BLOCKS references unknown keys: {_unknown}"


def select_blocks_for_specialist(state: dict, specialist_name: str) -> dict[str, str]:
    """Return only the blocks whitelisted for the given specialist.

    Pure function, no I/O. Missing keys default to empty string so
    specialist prompt templates always format cleanly.

    Unknown specialist names fall back to clinic_basics only (safe default).
    """
    ctx = state.get("tenant_context") or {}
    allowed = SPECIALIST_BLOCKS.get(specialist_name, ["clinic_basics"])
    return {key: (ctx.get(key) or "") for key in allowed}
