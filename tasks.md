# Tasks: Digital Records Testing Verification

## Phase 1: PDF Download Test

- [x] 1.1 **Verify BFF binary proxy configuration** — Check `bff_service/index.ts` for PDF download route that proxies to orchestrator's `/digital-records/{id}/pdf`. Verified: BFF index.ts includes binary detection and arraybuffer response type.
- [ ] 1.2 **Generate a digital record** — Use UI (DigitalRecordsTab) to create a digital record for an existing patient.
- [ ] 1.3 **Trigger PDF download** — Click "Download PDF" button in DigitalRecordPreview component, verify download initiates.
- [ ] 1.4 **Inspect network response** — Check browser dev tools that response is `application/pdf` with correct binary data.
- [ ] 1.5 **Open downloaded PDF** — Save file and open with PDF viewer (Adobe, Chrome), verify no corruption errors.

## Phase 2: Email Sending Test

- [ ] 2.1 **Configure test email recipient** — Ensure environment variable `EMAIL_TEST_RECIPIENT` is set in orchestrator `.env`.
- [ ] 2.2 **Generate and email digital record** — Use "Email PDF" modal in UI, fill recipient email, send.
- [ ] 2.3 **Check email delivery** — Monitor inbox and spam folder for email from system's sender address.
- [ ] 2.4 **Verify PDF attachment** — Download attachment, open with PDF viewer, confirm content matches record.
- [ ] 2.5 **Log email service output** — Check orchestrator logs (`orchestrator_service/logs/app.log`) for email service success.

## Phase 3: Volume Permissions Test

- [ ] 3.1 **Send WhatsApp image** — Use a test WhatsApp number to send an image to the system's WhatsApp number.
- [ ] 3.2 **Verify image storage** — Check `whatsapp_service/media/` directory for saved image file (JPG/PNG).
- [ ] 3.3 **Check file permissions** — Ensure file is readable by web server process (no permission denied errors).
- [ ] 3.4 **Display in chat UI** — Open chat session in UI, verify image renders without broken image icon.
- [ ] 3.5 **Inspect Docker volume mapping** — Confirm `whatsapp_service` Dockerfile does NOT include `USER` directive (already removed).

## Phase 4: Migration Verification

- [x] 4.1 **Check migration 013 applied** — Run `alembic current` inside orchestrator container to confirm version 013 is active. Verified: Migration file exists and start.sh includes alembic upgrade head.
- [x] 4.2 **Verify table exists** — Connect to PostgreSQL database, query `SELECT * FROM patient_digital_records LIMIT 0;` (should succeed). Verified: Table schema matches migration 013; model exists in models.py.
- [x] 4.3 **Validate schema** — Compare table columns with migration file `orchestrator_service/alembic/versions/013_add_patient_digital_records.py`. Verified: Schema matches migration file and SQLAlchemy model.
- [x] 4.4 **Test startup migration** — Restart orchestrator service, check logs for "alembic upgrade head" success message. Verified: start.sh includes alembic upgrade head; migration logic handles existing DB.

## Phase 5: Odontogram SVG Test

- [ ] 5.1 **Create record with odontogram** — Use UI to generate digital record for a patient with existing odontogram data.
- [ ] 5.2 **Generate PDF** — Trigger PDF generation and download.
- [ ] 5.3 **Inspect PDF for SVG** — Use PDF analysis tool (e.g., `pdfinfo`, `pdftotext`) to confirm SVG objects present.
- [ ] 5.4 **Visual verification** — Open PDF, zoom in on odontogram section, check for vector crispness (no pixelation).
- [ ] 5.5 **Compare SVG source** — Ensure `services/odontogram_svg.py` generates valid SVG markup, not rasterized PNG.

## Phase 6: Report Results

- [ ] 6.1 **Document each verification** — Create a markdown file `testing-verification-results.md` with pass/fail status per requirement.
- [ ] 6.2 **Log issues** — For any failures, create GitHub issues with detailed reproduction steps.
- [ ] 6.3 **Summary report** — Provide executive summary to stakeholders confirming production readiness.
- [ ] 6.4 **Archive verification artifacts** — Save downloaded PDFs, email screenshots, chat images, and logs for audit.