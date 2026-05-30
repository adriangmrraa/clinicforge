# Proposal: Agenda Export (PDF + PNG/JPG) & Sticky Headers

## Intent

The print button uses `window.print()` which clips content. Need backend-generated PDF matching the 11-page example (grilla semanal + listas por día + listado alfabético) plus PNG/JPG image export. Week view day headers scroll away — need sticky fix.

## Scope

### In Scope
- **Backend endpoint** `GET /admin/agenda/export` with `format=pdf|png|jpg`, `start_date`, `end_date`
- **Jinja2 HTML template** for agenda semanal matching the PDF example layout
- **3-section PDF**: grilla semanal (Horario × Días), listas por día (Persona/Horario/Responsable), listado completo alfabético
- **PNG/JPG export** via WeasyPrint `write_png()` (grilla page only)
- **Frontend**: replace `window.print()` with API download call
- **Sticky headers fix** in week view

### Out of Scope
- Month view export (future)
- Custom date range picker for export
- Email delivery of agenda PDF

## Approach

1. New service `agenda_export_service.py` following budget_service.py pattern (gather → render → generate)
2. New template `templates/agenda/agenda_semanal.html` with @page CSS for multi-page print
3. New endpoint returning FileResponse (PDF) or image bytes (PNG/JPG)
4. Frontend: download button calls endpoint, sticky fix via `stickyHeaderDates={true}` + CSS adjustment

## Affected Areas

| Area | Impact |
|------|--------|
| `orchestrator_service/services/agenda_export_service.py` | New |
| `orchestrator_service/templates/agenda/agenda_semanal.html` | New |
| `orchestrator_service/admin_routes.py` | Modified — new endpoint |
| `frontend_react/src/views/AgendaView.tsx` | Modified — download button + sticky fix |

## Risks

| Risk | Mitigation |
|------|------------|
| WeasyPrint rendering differences | Use simple table-based HTML, tested CSS |
| Large agenda (100+ appointments) | Paginated template with @page breaks |

## Rollback Plan
Delete new files + revert AgendaView changes. No migration needed.

## Success Criteria
- [ ] PDF downloads with 3 sections matching the example
- [ ] PNG/JPG downloads with grilla image
- [ ] Week view headers stay visible on scroll
