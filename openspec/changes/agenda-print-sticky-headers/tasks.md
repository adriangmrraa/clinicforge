# Tasks: Agenda Export & Sticky Headers

## Phase 1: Backend — Service + Template

- [ ] 1.1 Create `orchestrator_service/services/agenda_export_service.py` with `gather_agenda_data(pool, tenant_id, start_date, end_date, professional_id=None)` — queries appointments, groups into grid (time_slot × day), daily lists (sorted by time), alphabetical list. Returns structured dict.
- [ ] 1.2 Create `orchestrator_service/templates/agenda/agenda_semanal.html` — Jinja2 template with 3 sections: grilla semanal table, listas por día tables, listado completo table. @page CSS for A4 landscape, footer with date + pagination. Day column colors matching example.
- [ ] 1.3 Add `render_agenda_html(data)` and `generate_agenda_pdf(pool, tenant_id, ...)` / `generate_agenda_png(...)` to service. Follow budget_service.py pattern (Jinja2 → WeasyPrint async).

## Phase 2: Backend — Endpoint

- [ ] 2.1 Add `GET /admin/agenda/export` endpoint in admin_routes.py. Params: format (pdf|png|jpg), start_date, end_date, professional_id (optional). Returns FileResponse for PDF, or Response with image/png for images. Tenant_id from auth.

## Phase 3: Frontend — Download + Sticky

- [ ] 3.1 Replace print button in AgendaView.tsx with a dropdown: "Descargar PDF" and "Descargar imagen (PNG)". On click, call GET /admin/agenda/export with current view dates + format. Download the blob.
- [ ] 3.2 Fix sticky headers: change `stickyHeaderDates={false}` to `stickyHeaderDates={true}` in FullCalendar config. Remove custom sticky CSS hack (lines 1022-1029) that conflicts.
