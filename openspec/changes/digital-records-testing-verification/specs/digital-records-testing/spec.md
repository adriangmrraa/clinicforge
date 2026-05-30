# Digital Records Testing Verification Specification

## Purpose

Verify that digital records functionality works correctly after redeploy, ensuring PDF downloads, email sending, volume permissions, database migrations, and odontogram SVG rendering function as expected.

## Requirements

### Requirement: PDF Download Works Correctly

The system MUST allow downloading generated digital records as PDF files that open without corruption.

#### Scenario: PDF download via BFF proxy

- GIVEN a generated digital record exists in the system
- WHEN a user requests PDF download via the UI
- THEN the BFF service MUST proxy the binary PDF response correctly
- AND the downloaded PDF MUST open in a PDF viewer without errors

### Requirement: Email Sending with PDF Attachment

The system MUST send emails with PDF attachments that arrive in the recipient's inbox (not spam) with the attachment readable.

#### Scenario: Email delivery verification

- GIVEN a digital record is ready for email sending
- WHEN the system sends the email via the email service
- THEN the email MUST be delivered to the recipient's inbox (not spam folder)
- AND the PDF attachment MUST be present and openable without corruption

### Requirement: WhatsApp Images Save and Display

The system MUST save WhatsApp images to disk and display them in the chat UI, respecting volume permissions.

#### Scenario: WhatsApp image storage

- GIVEN a WhatsApp message with an image is received by the system
- WHEN the image is processed by the WhatsApp service
- THEN the image file MUST be saved to the configured media volume
- AND the image MUST be displayable in the chat UI without permission errors

### Requirement: Database Migration 013 Applied

The `patient_digital_records` table MUST be created with the correct schema after system startup.

#### Scenario: Migration verification on startup

- GIVEN the system has been redeployed with migration 013
- WHEN the orchestrator service starts up
- THEN the alembic upgrade head command MUST run successfully
- AND the `patient_digital_records` table MUST exist with all required columns

### Requirement: Odontogram SVG Renders Correctly in PDF

Odontogram SVG graphics MUST render as vector graphics in generated PDF documents, maintaining print quality.

#### Scenario: Odontogram SVG in PDF generation

- GIVEN a digital record contains an odontogram section
- WHEN the PDF is generated
- THEN the odontogram MUST be included as vector SVG (not rasterized)
- AND the SVG MUST appear correctly scaled and positioned in the PDF