# Design: Agenda Export & Sticky Headers

## Technical Approach

Backend: new service + Jinja2 template + endpoint following budget_service.py pattern. WeasyPrint for PDF, `write_png()` for images. Frontend: replace window.print() with API call, enable stickyHeaderDates.

## Architecture Decisions

### D1: PDF generation approach
| Option | Decision |
|--------|----------|
| WeasyPrint (existing pattern) | **Chosen** — already used for budgets, battle-tested |
| Playwright headless | Rejected — overkill, not in PDF pipeline |

### D2: Image export
| Option | Decision |
|--------|----------|
| WeasyPrint `write_png()` | **Chosen** — renders first page as PNG natively |
| Pillow from PDF | Rejected — extra dependency, lossy |

### D3: Sticky headers
| Option | Decision |
|--------|----------|
| `stickyHeaderDates={true}` + remove custom CSS | **Chosen** — FC native feature |
| Keep custom CSS hacks | Rejected — doesn't work with external scroll container |

## Data Flow

```
Frontend "Descargar PDF" click
  → GET /admin/agenda/export?format=pdf&start_date=X&end_date=Y
  → gather_agenda_data(pool, tenant_id, start, end)
    → Query appointments + professionals + tenant info
    → Group by time_slot × day (grid), by day (lists), alphabetical (full list)
  → render_agenda_html(data) via Jinja2 template
  → WeasyPrint HTML → PDF (or PNG)
  → FileResponse
```

## File Changes

| File | Action | Description |
|------|--------|-------------|
| `orchestrator_service/services/agenda_export_service.py` | Create | gather + render + generate functions |
| `orchestrator_service/templates/agenda/agenda_semanal.html` | Create | 3-section Jinja2 template matching PDF example |
| `orchestrator_service/admin_routes.py` | Modified | New GET /admin/agenda/export endpoint |
| `frontend_react/src/views/AgendaView.tsx` | Modified | Download dropdown + sticky fix |

## Template Structure (agenda_semanal.html)

```
@page { size: A4 landscape; margin: 1.5cm; }
@page footer { "Agenda Semanal · {date}" + "Pág. N/M" }

Section 1: Grilla Semanal
  <h1>Agenda Semanal — Grilla semanal</h1>
  <p>date · N turnos · M personas</p>
  <table> Horario | Lunes | Martes | ... | Viernes </table>
  (page-break-after)

Section 2: Listas por Día
  <h1>Listas por día</h1>
  {% for day in days %}
    <div class="day-header" style="background: day.color">Día — N personas</div>
    <table> Persona | Horario | Responsable </table>
  {% endfor %}
  (page-break-after)

Section 3: Listado Completo
  <h1>Listado completo (orden alfabético)</h1>
  <table> # | Persona | Día | Horario | Responsable </table>
```

## Day Colors (from PDF example)
- Lunes: #5b4a9e (purple)
- Martes: #2e6ca4 (blue)
- Miércoles: #1a6b5a (teal/green)
- Jueves: #6b5a1a (dark gold)
- Viernes: #8b4513 (brown)
- Sábado: #4a4a4a (gray)

## Sticky Fix

Change in AgendaView.tsx:
```
stickyHeaderDates={false}  →  stickyHeaderDates={true}
```
Remove the custom sticky CSS hack (lines 1022-1029) since FC handles it natively.
