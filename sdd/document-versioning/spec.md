# Document Versioning for Digital Clinical Records — Specification

## Purpose

Track edit history of digital clinical records for audit trail, compliance, and revert capability. Each update or regeneration creates a version snapshot, enabling full history viewing and restoration to any previous state.

## Requirements

### Requirement: Version Creation on Update

The system **MUST** create a new version snapshot before applying changes to a digital record via the `update_digital_record` endpoint.

#### Scenario: Update Digital Record Creates Version

- GIVEN an existing digital record for a patient
- WHEN a professional calls `PUT /patients/{patient_id}/digital‑records/{record_id}` with new content
- THEN a new row **SHALL** be inserted into `patient_digital_record_versions` with the record's current `html_content`, `title`, and `template_type`
- AND the new version **MUST** be assigned a sequential `version_number` (previous max + 1)
- AND the `changed_by` field **SHALL** be set to the professional's ID
- AND the `changed_at` field **SHALL** be set to the current timestamp
- AND the update **SHALL** proceed with the new content

#### Scenario: First Version on Initial Update

- GIVEN a digital record that has no existing versions
- WHEN the record is updated for the first time
- THEN the created version **MUST** have `version_number = 1`

### Requirement: Version Creation on Regeneration

The system **MUST** create a new version snapshot before regenerating a section of a digital record via the `regenerate_section` endpoint.

#### Scenario: Regenerate Section Creates Version

- GIVEN an existing digital record for a patient
- WHEN a professional calls `POST /patients/{patient_id}/digital‑records/{record_id}/regenerate` with new AI‑generated content
- THEN a new version **SHALL** be created with the record's pre‑regeneration state (same as Requirement 1)
- AND the regeneration **SHALL** proceed with the new AI content

### Requirement: Version Listing

The system **SHALL** provide an endpoint to retrieve all versions of a digital record, ordered chronologically.

#### Scenario: List Versions for a Record

- GIVEN a digital record with multiple versions
- WHEN a professional calls `GET /patients/{patient_id}/digital‑records/{record_id}/versions`
- THEN the endpoint **MUST** return a JSON array of version objects
- AND each version object **SHALL** include `id`, `version_number`, `changed_by` (professional name), `changed_at`, `title`, and `template_type`
- AND the array **MUST** be sorted by `version_number` ascending (oldest first)
- AND the response **SHALL NOT** include the full `html_content` (to avoid payload bloat)

### Requirement: Version Restoration

The system **SHALL** allow restoring a digital record to a previous version, creating a new version that captures the restore action.

#### Scenario: Restore to a Previous Version

- GIVEN a digital record with at least two versions
- WHEN a professional calls `POST /patients/{patient_id}/digital‑records/{record_id}/versions/{version_id}/restore`
- THEN the system **MUST** create a new version snapshot of the record's current state (as per Requirement 1)
- AND the record's `html_content`, `title`, and `template_type` **SHALL** be updated to match the restored version's snapshotted values
- AND the new version's `changed_by` **SHALL** be set to the restoring professional's ID
- AND the response **SHALL** return the updated record with the restored content

### Requirement: Tenant Isolation

All versioning operations **MUST** respect multi‑tenancy; queries **SHALL** include `tenant_id` filters to prevent cross‑clinic data leakage.

#### Scenario: Versions Are Tenant‑Scoped

- GIVEN two clinics (Tenant A and Tenant B) each have a digital record with the same database ID (UUID)
- WHEN a professional from Tenant A lists versions for that record ID
- THEN the endpoint **MUST** return only versions belonging to Tenant A's record (via `tenant_id` inherited from the parent record)
- AND **SHALL NOT** include any versions from Tenant B's record

### Requirement: Version Metadata

Each version **SHALL** store a complete snapshot of the record's `html_content`, `title`, and `template_type` at the time of version creation.

#### Scenario: Version Snapshot Integrity

- GIVEN a digital record with `html_content = "<p>Hello</p>"`, `title = "Report"`, `template_type = "clinical_report"`
- WHEN a version is created during an update
- THEN the version row **MUST** contain exactly those values, regardless of concurrent modifications
- AND the snapshot **SHALL** be immutable after creation

## Out of Scope

- UI for displaying version history or diffs
- Automated versioning on autosave or minor edits
- Compression or differential storage of versions
- Version deletion or purging

## Acceptance Criteria

- [ ] Each update to a digital record (via `update_digital_record` or `regenerate_section`) creates a new version in `patient_digital_record_versions`.
- [ ] GET `/patients/{patient_id}/digital‑records/{record_id}/versions` returns a chronologically ordered list of versions with metadata.
- [ ] POST `/patients/{patient_id}/digital‑records/{record_id}/versions/{version_id}/restore` creates a new version with the restored content and updates the record’s `html_content`.
- [ ] All version operations are isolated by `tenant_id` (no cross‑tenant data leakage).
- [ ] Version numbers are sequential per record and start at 1.