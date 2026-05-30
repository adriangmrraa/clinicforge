# Proposal: Digital Records Testing Verification

## Intent

Verify that all digital records functionality works correctly after redeploy, ensuring PDF downloads, email sending, volume permissions, database migrations, and odontogram SVG rendering function as expected. This testing is HIGH PRIORITY to confirm production readiness of the recently implemented digital patient records feature.

## Scope

### In Scope
1. PDF download — verify it opens correctly (BFF binary proxy fix)
2. Email sending — check spam folder, verify PDF attachment arrives
3. Volume permissions — WhatsApp images should save/display now (USER removed)
4. Migration 013 — verify patient_digital_records table created on startup
5. Odontogram in PDF — verify SVG renders correctly in generated documents

### Out of Scope
- Fixing bugs discovered during testing (should be reported as separate changes)
- Implementing new features or enhancements
- Testing other system components unrelated to digital records

## Approach

Manual testing and verification of each item:
1. **PDF download**: Trigger generation of a digital record via UI, download PDF, verify file opens without corruption.
2. **Email sending**: Generate and email a digital record, check spam folder, verify attachment present and readable.
3. **Volume permissions**: Send a WhatsApp image to the system, verify it saves to disk and displays in chat.
4. **Migration 013**: Check database after redeploy to confirm `patient_digital_records` table exists with correct schema.
5. **Odontogram SVG**: Generate a document containing an odontogram, verify SVG renders correctly in PDF.

Logs, database state, and file system will be inspected for each verification.

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `orchestrator_service/services/digital_records_service.py` | Modified | PDF generation and email attachment |
| `bff_service/` | Modified | Binary proxy fix for PDF downloads |
| `orchestrator_service/email_service.py` | Modified | Email sending with PDF attachment |
| `whatsapp_service/` | Modified | Volume permissions for media storage |
| `orchestrator_service/alembic/versions/013_add_patient_digital_records.py` | New | Database migration |
| `orchestrator_service/services/odontogram_svg.py` | New | SVG rendering for PDF |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| PDF generation fails due to missing WeasyPrint dependencies | Medium | Verify Docker image includes system deps; check logs |
| Email delivery blocked by spam filters | High | Check spam folder; verify email service configuration |
| Migration 013 not applied on startup | Low | Confirm alembic upgrade head runs in start.sh |
| Odontogram SVG missing or malformed | Medium | Compare server-side SVG with React component output |
| Volume permissions still problematic | Low | Verify USER directive removed in Dockerfile; test with actual image upload |

## Rollback Plan

If testing reveals critical failures that prevent digital records from functioning:
1. Revert to previous git tag (`git checkout tags/<previous-stable>`)
2. Roll back database migration: `alembic downgrade -1`
3. Restore any modified configuration files from backup
4. Restart services

## Dependencies

- None (testing only)

## Success Criteria

- [ ] PDF download opens correctly in PDF viewer without errors
- [ ] Email with PDF attachment arrives in inbox (not spam) and attachment is readable
- [ ] WhatsApp images save to disk and display in chat UI
- [ ] `patient_digital_records` table exists with correct schema after redeploy
- [ ] Odontogram SVG appears correctly in generated PDF documents