# Proposal: Fix Document Editor Text Duplication

## Intent

When editing authorization request documents in "Ficha Digital", typing in editable sections causes text duplication and prevents editing/deleting. Root cause: HTML↔text round-trip conversion on every keystroke destroys structure.

## Scope

### In Scope
- **Fix textarea duplication bug** — decouple text state from HTML state during editing
- **Fix `htmlToText()` line break loss** — preserve `<p>` and `<br>` as newlines
- **Remove unnecessary `textToHtml()` per-keystroke conversion** — only convert at save time
- **Fix 422 on completed appointments query** — backend validation issue

### Out of Scope
- Restructuring DigitalRecordsTab into sub-components
- Adding rich text editor (contentEditable/TipTap)

## Approach

**Separate plain text state from HTML state.** On "Edit" start: convert HTML→text ONCE into a `Record<sectionId, string>` state. Textarea binds to this plain text state directly (no conversion on keystroke). On "Save": convert text→HTML ONCE and patch.

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `frontend_react/src/components/DigitalRecordsTab.tsx` | Modified | Fix htmlToText, textToHtml, handleSectionTextChange, textarea binding |
| `orchestrator_service/admin_routes.py` | Modified | Fix 422 on /admin/appointments with status=completed |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Existing saved documents with malformed HTML | Low | htmlToText fix handles any valid HTML |
| Line break behavior change | Low | Preserve \n↔\<p> mapping consistently |

## Rollback Plan

Revert DigitalRecordsTab.tsx changes. No data migration involved.

## Success Criteria

- [ ] User can type in editable sections without text duplication
- [ ] User can delete/backspace content normally
- [ ] Line breaks are preserved across edit→save→re-edit cycles
- [ ] 422 error on completed appointments is resolved
