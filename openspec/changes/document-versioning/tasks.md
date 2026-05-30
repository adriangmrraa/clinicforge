# Tasks: Document Versioning for Digital Clinical Records

## Phase 1: Database Migration & Models

- [ ] 1.1 Create `PatientDigitalRecordVersion` SQLAlchemy model in `orchestrator_service/models.py`
  - Columns: `id` (UUID primary key), `patient_digital_record_id` (UUID foreign key to `patient_digital_records`), `version_number` (integer), `html_content` (text), `title` (string), `template_type` (string), `changed_by` (integer foreign key to `professionals`), `changed_at` (timestamp), `tenant_id` (integer foreign key to `tenants`)
  - Add `__table_args__`: UniqueConstraint on (`patient_digital_record_id`, `version_number`), indexes for `tenant_id` and `patient_digital_record_id`
- [ ] 1.2 Generate Alembic migration script (`alembic/versions/XXX_add_patient_digital_record_versions.py`)
  - Create table `patient_digital_record_versions` with all columns and constraints
  - Add foreign key relationships and indexes
  - Include `CheckConstraint` for `template_type` matching parent record values (optional)
- [ ] 1.3 Test migration locally
  - Run `alembic upgrade head` in development environment
  - Verify table structure matches expected schema (columns, constraints, indexes)
  - Ensure `alembic downgrade` works (rollback safety)

## Phase 2: Version Creation Hooks

- [ ] 2.1 Add `create_version_snapshot` helper in `orchestrator_service/services/digital_records_service.py`
  - Signature: `async def create_version_snapshot(db, record_id, changed_by, tenant_id)`
  - Queries current record (`patient_digital_records`) for `html_content`, `title`, `template_type`
  - Computes next `version_number` (max existing + 1, default 1)
  - Inserts new row into `patient_digital_record_versions` with snapshot data
  - Returns new version ID (or raises appropriate error)
- [ ] 2.2 Modify `update_digital_record` endpoint (`orchestrator_service/routes/digital_records.py`, line ~237)
  - Call `create_version_snapshot` before executing the UPDATE
  - Pass `changed_by` from request context (need to extract professional ID from auth token)
  - Maintain existing update logic (preserve PDF invalidation)
- [ ] 2.3 Modify `regenerate_section` endpoint (`orchestrator_service/routes/digital_records.py`, line ~263)
  - Call `create_version_snapshot` before regenerating the section
  - Pass `changed_by` from auth context
- [ ] 2.4 Ensure tenant isolation in version creation
  - All queries in `create_version_snapshot` must include `tenant_id` filter
  - Verify `patient_digital_record_id` belongs to the same tenant (implicit via foreign key)
  - Add defensive check: record's `tenant_id` matches passed `tenant_id`

## Phase 3: Version Listing & Restore APIs

- [ ] 3.1 Add GET endpoint `/patients/{patient_id}/digital-records/{record_id}/versions` in `orchestrator_service/routes/digital_records.py`
  - New Pydantic model `DigitalRecordVersionResponse` with fields: `id`, `version_number`, `changed_by` (professional name), `changed_at`, `title`, `template_type`
  - Route must verify record exists and belongs to tenant
  - Return array sorted by `version_number` ascending (oldest first)
- [ ] 3.2 Implement version listing logic
  - Join `patient_digital_record_versions` with `professionals` to get professional name
  - Exclude `html_content` from response (payload size)
  - Add optional query param `include_html` (boolean) for full snapshot (future)
- [ ] 3.3 Add POST endpoint `/patients/{patient_id}/digital-records/{record_id}/versions/{version_id}/restore`
  - New Pydantic model `RestoreVersionRequest` (empty or with optional comment)
  - Verify version exists and belongs to same tenant and record
  - Create a new version snapshot of the record's **current** state (call `create_version_snapshot`)
  - Update `patient_digital_records` with restored version's `html_content`, `title`, `template_type`
  - Return updated digital record (same shape as `get_digital_record`)
- [ ] 3.4 Ensure tenant isolation in listing/restore endpoints
  - All queries must include `tenant_id` filter (via `WHERE` clause)
  - Use `patient_id` and `record_id` as additional filters (already present)
  - Prevent cross‑tenant access via proper JOIN conditions

## Phase 4: Testing & Verification

- [ ] 4.1 Write unit tests for `create_version_snapshot` helper (`tests/unit/test_digital_records_service.py`)
  - Test version numbering (first version = 1, subsequent increments)
  - Test snapshot integrity (captures correct `html_content`, `title`, `template_type`)
  - Test tenant isolation (cannot create version for wrong tenant)
- [ ] 4.2 Write integration tests for version creation hooks (`tests/integration/test_digital_records_versioning.py`)
  - Test `update_digital_record` creates a version
  - Test `regenerate_section` creates a version
  - Verify version metadata (`changed_by`, `changed_at`) matches request context
- [ ] 4.3 Write integration tests for version listing endpoint
  - Test GET `/patients/{patient_id}/digital‑records/{record_id}/versions` returns ordered list
  - Test response excludes `html_content` by default
  - Test tenant isolation (no cross‑tenant leakage)
- [ ] 4.4 Write integration tests for restore endpoint
  - Test restore creates a new version (capturing current state)
  - Test record content is updated to match restored version
  - Test restore fails for version from different tenant
- [ ] 4.5 Verify acceptance criteria from spec
  - Each update/regenerate creates a version (Requirement 1 & 2)
  - Version listing returns chronologically ordered metadata (Requirement 3)
  - Restore creates new version and updates record (Requirement 4)
  - All operations are tenant‑isolated (Requirement 5)
  - Version numbers are sequential per record starting at 1 (Requirement 1 scenario)

## Phase 5: Cleanup & Documentation (Optional)

- [ ] 5.1 Update API documentation in `docs/` or OpenAPI spec (if applicable)
- [ ] 5.2 Add inline comments explaining versioning logic in critical functions
- [ ] 5.3 Remove any temporary debug logs added during development