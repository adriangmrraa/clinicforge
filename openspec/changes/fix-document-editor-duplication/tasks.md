# Tasks: Fix Document Editor Text Duplication

## Phase 1: Frontend — Editor Fix

- [ ] 1.1 Fix `htmlToText()` in `DigitalRecordsTab.tsx` (line 110-113) — replace `.textContent` with proper `<p>`→`\n` and `<br>`→`\n` conversion. Remove headings before extracting text.
- [ ] 1.2 Add `editTexts: Record<string, string>` state after line 141. Initialize in `handleStartEdit()` by calling `htmlToText()` once per editable section.
- [ ] 1.3 Simplify `handleSectionTextChange()` (line 231-235) — set text in `editTexts` only, no `textToHtml()` call.
- [ ] 1.4 Fix `handleSaveEdit()` (line 237-249) — convert `editTexts` to HTML via `textToHtml()` at save time, then `rebuildHtml()`.
- [ ] 1.5 Fix textarea binding (line 320-326) — `value={editTexts[section.id]}`, `rows` from text state.

## Phase 2: Backend — 422 Fix

- [ ] 2.1 Modify GET `/admin/appointments` endpoint (admin_routes.py ~line 6865) — make `start_date`/`end_date` optional, add optional `patient_id: int`, `status: str`, `limit: int` query params. Add conditional WHERE clauses and LIMIT. Ensure tenant_id filter.

## Phase 3: Verification

- [ ] 3.1 Manual QA: type, delete, multi-line in authorization request editor — no duplication.
- [ ] 3.2 Manual QA: edit→save→re-edit preserves line breaks.
- [ ] 3.3 Manual QA: console shows no 422 on patient detail page load.
