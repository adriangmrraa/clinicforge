# Tasks: Link Chat Unique Violation Fix

## Phase 1: Core Implementation

- [x] 1.1 Import `os` at the top of `orchestrator_service/admin_routes.py` or inside the `link_chat_to_patient` function.
- [x] 1.2 Update the filename parsing inside `link_chat_to_patient` attachments loop: split base/ext, generate 8-char random hex suffix (`uuid.uuid4().hex[:8]`), and construct `{base}_{suffix}{ext}`. Use `chat_doc_{msg['id']}` base if `file_name` is missing.
- [x] 1.3 Update the duplicate-check SQL query in `link_chat_to_patient` to filter by `tenant_id`, `patient_id`, `source_message_id` (in `source_details`), and `file_path = $4` (using `media_url`).

## Phase 2: Testing

- [x] 2.1 Create `tests/test_link_chat_unique_violation.py` for testing `/chat/link-to-patient` behavior.
- [x] 2.2 Add tests to mock `db.pool` and check that filename suffixing preserves semantic name parts while guaranteeing unique filenames.
- [x] 2.3 Add test for duplicate filenames in different messages, ensuring they are both migrated without conflicts.
- [x] 2.4 Add test for multiple attachments in one message with missing filenames, verifying they get distinct `chat_doc_{msg_id}_{suffix}` names.
- [x] 2.5 Add test to verify that re-running migration skips already migrated attachments matching both message ID and file path.

## Phase 3: Verification & Review

- [x] 3.1 Run pytest on the new test file to verify logic: `pytest tests/test_link_chat_unique_violation.py`.
- [x] 3.2 Perform code review to ensure strict tenant isolation is maintained.

