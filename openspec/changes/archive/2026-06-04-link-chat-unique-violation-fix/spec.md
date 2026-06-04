# Delta for Patient Documents Migration

## ADDED Requirements

### Requirement: Unique Filename Generation on Chat Linking

When migrating media attachments from chat messages to a patient's documents, the system MUST ensure that every saved file has a unique filename for that patient and tenant to prevent database unique constraint violations on `(tenant_id, patient_id, file_name)`.

For each attachment:
1. Extract the base filename and extension (e.g. `image.png` -> base `image`, ext `.png`). If the filename is missing, use `chat_doc_{message_id}` as the base with no extension.
2. Generate an 8-character random hex string suffix (from `uuid.uuid4().hex[:8]`).
3. Reconstruct the filename as `{base}_{suffix}{ext}`.

### Requirement: Individual Attachment Migration Status

The migration status check for whether an attachment has already been linked to a patient MUST be evaluated per individual attachment (using its unique source message ID and media URL/path), and not per message.

| Property | Type | Rule |
|---|---|---|
| Filename uniqueness | Function | `base_name` + `_` + `8-char hex` + `extension` |
| Migration check | Database | Filter by `tenant_id`, `patient_id`, `source_message_id`, and `file_path` |

#### Scenario: Multiple attachments in one message without filename
- GIVEN a chat message with ID "12345" containing two attachments without filenames
- WHEN the chat is linked to patient "1" under tenant "10"
- THEN both attachments MUST be migrated as separate documents
- AND their filenames MUST be "chat_doc_12345_{suffix1}" and "chat_doc_12345_{suffix2}" respectively

#### Scenario: Attachments with duplicate filenames across messages
- GIVEN message "A" has attachment "receipt.pdf" and message "B" has attachment "receipt.pdf"
- WHEN the chat is linked to patient "1" under tenant "10"
- THEN both attachments MUST be migrated without database unique constraint violations
- AND their saved filenames MUST be unique (e.g. "receipt_{suffixA}.pdf" and "receipt_{suffixB}.pdf")

#### Scenario: Re-run migration with already migrated attachments
- GIVEN a chat containing attachment "receipt.pdf" was already linked to patient "1"
- WHEN the chat linking is triggered again for patient "1"
- THEN the attachment MUST NOT be duplicated in patient documents
