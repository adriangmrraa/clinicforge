# Design: Fix Document Editor Text Duplication

## Technical Approach

Decouple textarea state from HTML state. Store plain text in a `Record<string, string>` during editing. Convert HTML→text once on edit start, text→HTML once on save. Fix htmlToText to preserve line breaks. Add optional query params to /admin/appointments.

## Architecture Decisions

### D1: Text state storage

| Option | Tradeoff | Decision |
|--------|----------|----------|
| Separate `editTexts: Record<string, string>` state | Clean separation, no conversion per keystroke | **Chosen** |
| Fix textToHtml to be idempotent | Still converts every keystroke, perf cost | Rejected |

**Rationale**: The root cause is converting on every keystroke. Fixing the conversion functions alone won't solve the cursor reset and re-render issues.

### D2: 422 fix approach

| Option | Tradeoff | Decision |
|--------|----------|----------|
| Add optional params to existing endpoint | Backwards compatible, simple | **Chosen** |
| Create new endpoint /admin/appointments/search | Unnecessary duplication | Rejected |

**Rationale**: The endpoint at admin_routes.py:6865 only takes `start_date` and `end_date` (both required). Adding optional `patient_id`, `status`, `limit` follows FastAPI patterns. Make `start_date`/`end_date` optional when `patient_id` is provided.

## File Changes

| File | Action | Description |
|------|--------|-------------|
| `frontend_react/src/components/DigitalRecordsTab.tsx` | Modified | Fix htmlToText, remove per-keystroke textToHtml, add editTexts state |
| `orchestrator_service/admin_routes.py` | Modified | Add patient_id, status, limit params to GET /appointments |

## Key Code Changes

### DigitalRecordsTab.tsx

**1. Fix `htmlToText()`** (line 110-113):
```typescript
function htmlToText(html: string): string {
  const doc = new DOMParser().parseFromString(html, 'text/html');
  // Remove headings (h2/h3) — only extract body text
  doc.querySelectorAll('h2, h3').forEach(el => el.remove());
  // Convert <p> and <br> to newlines
  doc.querySelectorAll('p').forEach(el => { el.replaceWith(el.textContent + '\n'); });
  doc.querySelectorAll('br').forEach(el => { el.replaceWith('\n'); });
  return (doc.body.textContent || '').replace(/\n{3,}/g, '\n\n').trim();
}
```

**2. Add `editTexts` state** (after line 141):
```typescript
const [editTexts, setEditTexts] = useState<Record<string, string>>({});
```

**3. Fix `handleStartEdit()`** (line 224-229):
```typescript
const handleStartEdit = () => {
  if (!selectedRecord?.html_content) return;
  const sections = parseSections(selectedRecord.html_content);
  setEditSections(sections);
  // Pre-extract text ONCE
  const texts: Record<string, string> = {};
  sections.forEach(s => { if (s.editable) texts[s.id] = htmlToText(s.content); });
  setEditTexts(texts);
  setViewState('editing');
};
```

**4. Simplify `handleSectionTextChange()`** (line 231-235):
```typescript
const handleSectionTextChange = (sectionId: string, newText: string) => {
  setEditTexts(prev => ({ ...prev, [sectionId]: newText }));
};
```

**5. Fix `handleSaveEdit()`** (line 237-249) — convert text→HTML at save time:
```typescript
const handleSaveEdit = async () => {
  if (!selectedRecord?.html_content) return;
  setSaving(true);
  try {
    // Convert text back to HTML only now
    const updatedSections = editSections.map(s =>
      s.editable && editTexts[s.id] !== undefined
        ? { ...s, content: textToHtml(editTexts[s.id], s.content) }
        : s
    );
    const newHtml = rebuildHtml(selectedRecord.html_content, updatedSections);
    // ... rest same
  }
};
```

**6. Fix textarea binding** (line 320-326):
```typescript
<textarea
  value={editTexts[section.id] ?? htmlToText(section.content)}
  onChange={e => handleSectionTextChange(section.id, e.target.value)}
  rows={Math.max(3, (editTexts[section.id] ?? '').split('\n').length + 1)}
/>
```

### admin_routes.py — GET /appointments (line 6865)

Add optional params:
```python
async def list_appointments(
    start_date: str = None,        # was required
    end_date: str = None,          # was required
    professional_id: Optional[int] = None,
    patient_id: Optional[int] = None,   # NEW
    status: Optional[str] = None,       # NEW
    limit: Optional[int] = None,        # NEW
    tenant_id: int = Depends(get_resolved_tenant_id),
):
```

Add WHERE clauses conditionally and apply LIMIT.

## Testing Strategy

| Layer | What | Approach |
|-------|------|----------|
| Manual QA | Type/delete/multi-line in editor | Browser testing |
| Manual QA | Edit→save→re-edit round-trip | Browser testing |
| Manual QA | 422 fix: fetch completed appointments | Browser devtools |

## Open Questions

None.
