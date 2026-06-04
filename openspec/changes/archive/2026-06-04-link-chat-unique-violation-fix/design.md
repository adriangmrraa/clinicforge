# Design: Link Chat Unique Violation Fix

## Technical Approach

To prevent database unique constraint violations on `(tenant_id, patient_id, file_name)` during chat-to-patient linking:
1. **Suffix-Based Rename**: Modify `link_chat_to_patient` to extract filename bases and extensions, generating a random 8-character hex string suffix (`_uuid.uuid4().hex[:8]`), and reconstructing the final filename as `{base}_{suffix}{ext}`.
2. **Granular Migration Check**: Refine the migration check query to inspect both `source_message_id` (in JSONB `source_details`) and `file_path` (storing the attachment's `media_url`). This ensures multiple attachments in a single message are checked and migrated individually rather than grouping them per-message.

## Architecture Decisions

| Option | Tradeoff | Decision |
|---|---|---|
| **Simple UUID filenames** | Loses semantic context (e.g. `1a2b3c4d.pdf` instead of `receipt.pdf`) | Rejected. Retaining original filename prefixes preserves human readability. |
| **8-character random hex suffix** | Tiny chance of collision, highly readable | **Chosen**. Appending a random hex suffix preserves readability and ensures unique constraints are met. |
| **Check migration by message ID only** | Prevents migration of multiple attachments sent in a single message | Rejected. Only the first attachment would get migrated. |
| **Check migration by message ID + file path** | Highly granular and allows multi-attachment messages | **Chosen**. Safely identifies if the specific attachment was already linked. |

## Data Flow

```
   [Attachment Array]
          │
          ▼
   ┌──────────────┐
   │ For Each:    │
   │ Split FName/ │
   │ Append Hex   │
   └──────┬───────┘
          │
          ▼
   ┌──────────────┐
   │ Check DB:    │
   │ Msg ID &     │
   │ File Path    │
   └──────┬───────┘
          │
    Exists? ──(Yes)──→ [Skip Attachment]
          │
         (No)
          │
          ▼
   ┌──────────────┐
   │ INSERT INTO  │
   │ patient_docs │
   └──────────────┘
```

## File Changes

| File | Action | Description |
|------|--------|-------------|
| `orchestrator_service/admin_routes.py` | Modify | Update `link_chat_to_patient` endpoint to parse filenames, append unique suffixes, and query migration status per-attachment. |

## Interfaces / Contracts

No new REST endpoints or database migrations are required. The request and response shapes of `/chat/link-to-patient` remain unchanged.

### Modified Logic inside `link_chat_to_patient`
```python
# Filename suffix generation
import os
import uuid as _uuid

filename = att.get("file_name")
if filename:
    base, ext = os.path.splitext(filename)
else:
    base = f"chat_doc_{msg['id']}"
    ext = ""

suffix = _uuid.uuid4().hex[:8]
fname = f"{base}_{suffix}{ext}"
```

## Testing Strategy

| Layer | What to Test | Approach |
|---|---|---|
| Unit | Filename splitting and suffix generation | Test with standard filenames, paths with no extension, and missing filenames. |
| Integration | Prevent duplicate insertion and handle multi-attachments | Mock `db.pool` to simulate already migrated records and verify the query uses `file_path`. |

## Migration / Rollout

No database migrations or configuration overrides are needed. The changes are fully backward-compatible. Existing database records are unaffected and future link runs are idempotent.

## Open Questions

None.
