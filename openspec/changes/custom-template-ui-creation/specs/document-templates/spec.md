# Document Templates Specification

## Purpose

Allow clinic administrators to create, edit, and manage custom HTML document templates via the UI, extending the digital records system beyond the four hardcoded template types.

## Requirements

### Requirement: Database Storage

The system SHALL store custom templates in a `document_templates` table with `tenant_id`, `name`, `template_type`, `html_content`, `variables_json`, `is_active`, `created_at`, and `updated_at`. The table SHALL enforce unique `template_type` per tenant.

#### Scenario: Create template
- GIVEN a clinic admin provides name "Post‑Operative Summary" and type "custom_postop"
- WHEN they save the template
- THEN a row SHALL be inserted with the clinic's `tenant_id`

#### Scenario: Prevent duplicate template type per clinic
- GIVEN a clinic already has a template with type "custom_postop"
- WHEN the same clinic attempts to create another template with the same type
- THEN the operation SHALL fail with a unique constraint error

### Requirement: Extended Template Type Validation

The system SHALL allow `template_type` values that are either one of the four hardcoded types (`clinical_report`, `post_surgery`, `odontogram_art`, `authorization_request`) OR any string starting with `custom_`.

#### Scenario: Generate record with custom type
- GIVEN a custom template exists for type "custom_postop"
- WHEN a digital record is generated with that type
- THEN the generation SHALL succeed using the custom template

#### Scenario: Reject invalid template type
- GIVEN a request to generate a record with type "unknown"
- THEN the system SHALL respond with HTTP 400 and an error message

### Requirement: Backend CRUD API

The system SHALL provide RESTful endpoints under `/admin/digital‑records/templates/` for CRUD operations. All endpoints SHALL enforce tenant isolation.

#### Scenario: List templates
- GIVEN a clinic has three templates
- WHEN the admin calls `GET /admin/digital‑records/templates/`
- THEN the response SHALL contain exactly those three templates, isolated from other clinics

#### Scenario: Update template
- GIVEN a template exists
- WHEN the admin sends `PATCH` with new `html_content`
- THEN the template SHALL be updated and `updated_at` SHALL change

### Requirement: HTML Safety and Syntax Validation

The system MUST sanitize HTML content to prevent XSS (using bleach). The system SHOULD validate Jinja2 syntax on save and return a descriptive error for invalid syntax.

#### Scenario: Sanitize unsafe HTML
- GIVEN an admin submits `<script>alert('xss')</script>`
- WHEN the template is saved
- THEN the script tag SHALL be removed from stored content

#### Scenario: Validate Jinja2 syntax
- GIVEN an admin submits `{{ data..patient_name }}` (malformed)
- WHEN the template is saved
- THEN the server SHALL respond with HTTP 400 and a syntax error message

### Requirement: Template Fallback

The `assemble_html()` function SHALL first query `document_templates` for a matching `template_type` and `tenant_id`. If no custom template is found, it SHALL fall back to the existing file‑based template lookup.

#### Scenario: Use custom template
- GIVEN a custom template for "custom_postop" exists
- WHEN `assemble_html()` is called with that type and tenant
- THEN the function SHALL return HTML rendered from the custom template

#### Scenario: Fallback to file‑based template
- GIVEN no custom template exists for "clinical_report"
- WHEN `assemble_html()` is called with that type and tenant
- THEN the function SHALL fall back to `clinical_report.html.j2`

### Requirement: Frontend Template Management UI

The frontend SHALL provide a template management view accessible from Configuración. The view SHALL list templates with name, type, status, and offer create, edit, delete, and preview actions.

#### Scenario: View template list
- GIVEN an admin is logged in
- WHEN they navigate to "Plantillas" in Configuración
- THEN they SHALL see a list of their clinic's templates

#### Scenario: Create new template via UI
- GIVEN the admin clicks "Nueva plantilla"
- WHEN they fill name, type (with "custom_" prefix), HTML content, and save
- THEN the template SHALL be created and appear in the list

#### Scenario: Preview template
- GIVEN a template with placeholders `{{ data.patient_name }}` and `{{ ai.summary }}`
- WHEN the admin clicks "Vista previa"
- THEN a modal SHALL display the template rendered with sample data

### Requirement: Internationalization

All UI text for template management SHALL be translatable via the existing i18n system. Translation keys SHALL be added to `src/locales/{es,en,fr}.json`.

#### Scenario: French UI
- GIVEN the clinic's UI language is French
- WHEN the admin views the template management page
- THEN all labels, buttons, and messages SHALL appear in French