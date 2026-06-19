# Tasks: Booking Flow Insurance + Min Date

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | ~63 |
| 400-line budget risk | Low |
| Chained PRs recommended | No |
| Suggested split | Single PR |
| Delivery strategy | single-pr |

Decision needed before apply: No
Chained PRs recommended: No
Chain strategy: size-exception
400-line budget risk: Low

> `size:exception` NOT required — estimated ~63 lines, well under 400.

## Phase 1: Foundation — Tenant Context Blocks

- [ ] **1.1** `tenant_context.py`: Add `"min_date_section"` to `ALL_BLOCK_KEYS` (line 27) — must match the invariant check at line 52.
- [ ] **1.2** `tenant_context.py`: Add `"min_date_section"` to `SPECIALIST_BLOCKS["booking"]` (line 44) so the BookingAgent receives it.
- [ ] **1.3** `tenant_context.py`: Add `config` column to `_fetch_tenant_row` SELECT (line 214) — needed to read `min_appointment_date`.
- [ ] **1.4** `tenant_context.py`: Create `_format_min_date_section(tenant_config: dict) -> str` — reads `min_appointment_date` from tenant config, returns `# 📅 FECHA MÍNIMA PARA TURNOS` block (same format as buffer_task.py lines 1391-1398).
- [ ] **1.5** `tenant_context.py`: Wire `_format_min_date_section(tenant_config)` into `build_tenant_context_blocks` — after `sede_info_text` (line 456), parse `tenant_row.get("config")` and call formatter. Assign to `blocks["min_date_section"]`.

## Phase 2: Core Implementation — Prompts & Tools

- [ ] **2.1** `specialists.py`: Add `check_insurance_coverage` to `BookingAgent._get_tools()` (import at line 242, append to return list at line 262).
- [ ] **2.2** `specialists.py`: Insert OS-first instruction block into `BookingAgent` prompt (after line 298, before `INTERPRETACIÓN DE FECHAS`): "⚠️ REGLA CRÍTICA: Si el paciente NO mencionó su obra social, preguntale ANTES de llamar check_availability."
- [ ] **2.3** `specialists.py`: Add min_date + OS days combination instruction to `BookingAgent` prompt (in the min_date section after line 277): "Combiná la FECHA MÍNIMA con los días de espera de la OS (`min_days_wait`). Si la OS pide 40d y la fecha mínima es 16/06, el turno más cercano es 16/06 + 40d."
- [ ] **2.4** `main.py`: Move the "⚠️ REGLA CRÍTICA: OBRAS SOCIALES Y SEMÁFORO" block (lines 10487-10490) to BEFORE "PROACTIVIDAD (LO MÁS IMPORTANTE)" (line 10691). Insert it right after line 10690 as a standalone paragraph.
- [ ] **2.5** `buffer_task.py`: Enhance min_date injection block (lines 1389-1398) with OS combination instruction — add: "Si la obra social del paciente tiene `min_days_wait`, sumalos a esta fecha. Ej: fecha mínima 16/06 + OS con 40d = turno desde 26/07."
- [ ] **2.6** `conversation_state.py`: Add `set_insurance_asked(tenant_id, phone) -> None` helper — reads current payload, sets `"insurance_asked": true`, writes back via `_raw_write`.
- [ ] **2.7** `conversation_state.py`: Add `get_insurance_asked(tenant_id, phone) -> bool` helper — reads `insurance_asked` from payload, defaults to `False`.

## Phase 3: Integration — BookingAgent + Solo Alignment

- [ ] **3.1** `specialists.py`: Add min_date combination instruction also to the existing `# ⚠️ IMPORTANTE - REGLAS DE FECHA MÍNIMA` block (lines 273-277) — append: "Combiná la FECHA MÍNIMA con `min_days_wait` de la OS así: fecha_mínima + min_days_wait = fecha más cercana posible."
- [ ] **3.2** `buffer_task.py`: Inject `insurance_asked` flag into Solo Agent's context — read from conversation state and add `"[INTERNAL] insurance_asked: true/false"` to system_prompt if flag exists (near line 1342 anchor_date injection).

## Phase 4: Verification

- [ ] **4.1** Verify `tenant_context.py` invariant: every new key in `SPECIALIST_BLOCKS` exists in `ALL_BLOCK_KEYS` (line 52 assertion).
- [ ] **4.2** Verify `specialists.py`: `check_insurance_coverage` import resolves (no circular import breakage).
- [ ] **4.3** Run `pytest tests/test_multi_agent_tenant_context.py` — existing tests must pass with the new block.
- [ ] **4.4** Run `pytest tests/test_conversation_state.py` — existing tests must pass with the new helpers.
- [ ] **4.5** Run `pytest tests/test_specialists_social_preamble.py` — existing tests must pass.

## Implementation Order

Phase 1 (tenant_context) first — other tasks depend on `min_date_section` and `insurance_section` being available in the block system. Then Phase 2 (specialists + main + conversation_state) in parallel. Phase 3 integration last. Phase 4 verification at the end.
