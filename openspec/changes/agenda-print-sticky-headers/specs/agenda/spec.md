# Agenda Export & Sticky Headers Spec

## ADDED Requirements

### REQ-EXPORT-01: Agenda Export Endpoint

`GET /admin/agenda/export` MUST accept: `format` (pdf|png|jpg), `start_date`, `end_date`, optional `professional_id`. MUST return file with correct Content-Type.

#### Scenario: Download PDF
- GIVEN week of 2026-04-20 has 77 appointments
- WHEN GET /admin/agenda/export?format=pdf&start_date=2026-04-20&end_date=2026-04-24
- THEN returns PDF with Content-Type application/pdf, filename "agenda_semanal_YYYY-MM-DD.pdf"

#### Scenario: Download PNG
- GIVEN same week
- WHEN GET with format=png
- THEN returns PNG image of the grilla semanal (first page only)

### REQ-EXPORT-02: PDF Section 1 — Grilla Semanal

PDF MUST include a weekly grid table: rows = time slots (08:00-09:00, etc.), columns = weekdays (Lunes-Viernes). Each cell shows patient names. Header row with colored backgrounds per day. Title: "Agenda Semanal — Grilla semanal", subtitle: date + total turnos + total personas.

#### Scenario: Grid with appointments
- GIVEN 4 appointments on Jueves 08:00-09:00
- WHEN PDF is generated
- THEN cell [08:00-09:00, Jueves] shows all 4 names on separate lines

### REQ-EXPORT-03: PDF Section 2 — Listas por Día

After the grid, PDF MUST include one table per working day with columns: Persona, Horario, Responsable. Each day section has a colored header with "Día — N personas". Days with color coding matching the grid.

#### Scenario: Day list
- GIVEN Lunes has 28 appointments
- WHEN PDF is generated
- THEN "Lunes — 28 personas" section shows all 28 rows sorted by horario

### REQ-EXPORT-04: PDF Section 3 — Listado Completo Alfabético

Final section: all appointments in one table sorted alphabetically by patient name. Columns: #, Persona, Día, Horario, Responsable. Day column colored to match.

#### Scenario: Alphabetical list
- GIVEN 77 total appointments
- WHEN PDF is generated
- THEN numbered list 1-77 sorted by patient name, each with day colored

### REQ-EXPORT-05: Footer with Pagination

Each page MUST have footer: "Agenda Semanal · {date}" on left, "Pág. {n} / {total}" on right.

## MODIFIED Requirements

### REQ-STICKY-01: Week View Sticky Headers

Day column headers in week view MUST remain visible when scrolling down. FullCalendar `stickyHeaderDates` MUST be enabled.

#### Scenario: Scroll in week view
- GIVEN user is on week view with appointments from 08:00 to 18:00
- WHEN user scrolls down to see 15:00+ slots
- THEN day headers (Lun, Mar, Mié...) remain visible at top

### REQ-BUTTON-01: Download Button (Modified)

Print button MUST be replaced with a dropdown offering: "Descargar PDF", "Descargar imagen (PNG)". Clicking downloads via the backend endpoint.

#### Scenario: Download PDF from button
- GIVEN user is on week view
- WHEN user clicks "Descargar PDF"
- THEN browser downloads the complete agenda PDF
