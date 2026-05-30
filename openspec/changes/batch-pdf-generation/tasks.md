# Tasks: Batch PDF Generation for Multiple Patients

## Phase 1: Extend digital_records_service with batch method

- [ ] 1.1 Add `batch_generate_pdfs(record_ids: List[str], tenant_id: int)` function in `orchestrator_service/services/digital_records_service.py`
- [ ] 1.2 Implement validation query to check all record IDs belong to tenant (single SQL query with ANY)
- [ ] 1.3 For each valid record, fetch existing pdf_path; if missing or stale, call `generate_pdf` asynchronously
- [ ] 1.4 Collect resulting file paths and return list of (record_id, title, pdf_path) dicts
- [ ] 1.5 Add configuration constant `BATCH_PDF_SYNC_LIMIT = 10` (configurable via env)

## Phase 2: Create synchronous ZIP endpoint

- [ ] 2.1 Add Pydantic model `BatchPdfRequest` with `record_ids: List[str]` in `orchestrator_service/routes/digital_records.py`
- [ ] 2.2 Add POST `/digital-records/batch-pdf` endpoint with `verify_admin_token` dependency
- [ ] 2.3 Validate batch size against `BATCH_PDF_SYNC_LIMIT` (return 400 if exceeded)
- [ ] 2.4 Call `batch_generate_pdfs` and collect PDF paths
- [ ] 2.5 Create in‑memory ZIP archive using `zipfile.ZipFile` with sanitized filenames (`{record_id}_{title}.pdf`)
- [ ] 2.6 Return `FileResponse` with `application/zip` media type and `Content-Disposition` header
- [ ] 2.7 Clean up temporary ZIP file after sending (or use `tempfile.NamedTemporaryFile`)

## Phase 3: Add optional asynchronous processing via Redis

- [ ] 3.1 Define new Redis job type `batch_pdf_generation` in `orchestrator_service/services/relay.py` (or separate job service)
- [ ] 3.2 Add `create_batch_pdf_job(tenant_id, record_ids)` that pushes job to Redis queue
- [ ] 3.3 Add POST `/digital-records/batch-pdf/async` endpoint returning `{ job_id }`
- [ ] 3.4 Add worker function `process_batch_pdf_job` that calls `batch_generate_pdfs` and creates ZIP
- [ ] 3.5 Store resulting ZIP file in shared storage (e.g., uploads folder) with 24‑hour expiration
- [ ] 3.6 Add GET `/digital-records/batch-pdf/jobs/{job_id}` endpoint returning status and download URL
- [ ] 3.7 Implement job status polling: `pending`, `processing`, `completed`, `failed`

## Phase 4: Testing and verification

- [ ] 4.1 Write unit tests for `batch_generate_pdfs` validation and error cases
- [ ] 4.2 Write integration test for synchronous ZIP endpoint (happy path)
- [ ] 4.3 Write integration test for cross‑tenant rejection and missing records
- [ ] 4.4 Write integration test for async job flow (mock Redis)
- [ ] 4.5 Verify ZIP file contains correct PDFs with correct filenames
- [ ] 4.6 Update `orchestrator_service/tests/conftest.py` if needed for test fixtures

## Phase 5: Frontend multi‑select UI (optional)

- [ ] 5.1 Add checkbox column to `DigitalRecordsTab.tsx` for multi‑selection
- [ ] 5.2 Add "Download selected as ZIP" button visible when ≥1 record selected
- [ ] 5.3 Implement frontend logic to call synchronous endpoint (≤10) or prompt async for larger batches
- [ ] 5.4 Add i18n keys for batch actions in `src/locales/{es,en,fr}.json`
- [ ] 5.5 Add loading state and progress indication for async jobs