# Delta for Backend: YCloud Full Message Sync

**Change:** `ycloud-sync`
**Date:** 2026-04-10
**Status:** Spec

---

## 1. Overview

This specification defines the backend requirements for synchronizing historical WhatsApp messages from YCloud API v2 to the local database. The current system only captures new messages via webhooks; historical messages and media are not stored locally.

## 2. ADDED Requirements

### Requirement: YCloud API v2 Message Fetch

The system MUST support fetching paginated messages from YCloud API v2 using cursor-based pagination.

#### Scenario: Fetch messages with pagination

- GIVEN YCloud API key is configured for tenant `tenant_id`
- WHEN `fetch_messages(limit=100, pageAfter=null)` is called for the first time
- THEN the API returns up to 100 messages with a cursor for the next page
- AND subsequent calls use the cursor to fetch older messages until no cursor remains

#### Scenario: Handle empty response

- GIVEN no messages exist in YCloud for the tenant
- WHEN `fetch_messages(limit=100, pageAfter=null)` is called
- THEN the API returns `{items: [], cursor: {after: null}, length: 0, limit: 100}`

---

### Requirement: Database Schema - whatsapp_messages

The system MUST create a new table `whatsapp_messages` to store synchronized messages with the following schema:

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| `id` | BIGINT | PK, autoincrement | Internal ID |
| `tenant_id` | INTEGER | FK → tenants.id, NOT NULL | Clinic identifier |
| `external_id` | VARCHAR(64) | UNIQUE | YCloud message ID |
| `wamid` | VARCHAR(64) | INDEX | WhatsApp message ID |
| `from_number` | VARCHAR(32) | NOT NULL, E.164 | Sender phone |
| `to_number` | VARCHAR(32) | NOT NULL, E.164 | Receiver phone |
| `direction` | VARCHAR(16) | NOT NULL, CHECK(in/outbound) | Message direction |
| `message_type` | VARCHAR(32) | NOT NULL | text/image/audio/video/document/sticker/location/interactive |
| `content` | TEXT | NULL | Text body or caption |
| `media_url` | VARCHAR(512) | NULL | Local storage path after download |
| `media_id` | VARCHAR(128) | NULL | YCloud media ID for download |
| `status` | VARCHAR(16) | NOT NULL, DEFAULT='synced' | sent/delivered/read/failed/synced |
| `patient_id` | INTEGER | FK → patients.id, NULL | Linked patient (matched by phone) |
| `conversation_id` | UUID | FK → chat_conversations.id, NULL | Linked conversation |
| `created_at` | TIMESTAMP | NOT NULL, INDEX | Timestamp from YCloud |
| `synced_at` | TIMESTAMP | NOT NULL, DEFAULT=now() | When record was created |

**Indexes:**
- `external_id` UNIQUE
- `from_number` INDEX
- `tenant_id + created_at` COMPOSITE INDEX

---

### Requirement: Patient Matching Logic

The system MUST link messages to patients by normalizing and matching phone numbers.

#### Scenario: Match existing patient by phone

- GIVEN a message with `from_number="+5491155551234"` and tenant has a patient with `phone_number="5491155551234"`
- WHEN patient matching is attempted
- THEN `patient_id` is set to the matched patient's ID
- AND the message is linked to the patient's conversation

#### Scenario: No patient match (orphan message)

- GIVEN a message from `+5491155559999` and no patient exists with that phone
- WHEN patient matching is attempted
- THEN `patient_id` remains NULL (orphan)
- AND the message is stored without patient linking

#### Scenario: Phone number normalization

- GIVEN phone numbers in various formats: `+54 9 11 5555-1234`, `+5491155551234`, `01155551234`, `5491155551234`
- WHEN normalization is applied (remove +, spaces, dashes; add `549` if Argentine)
- THEN all variants resolve to `5491155551234` for matching

---

### Requirement: Media Download Protocol

The system MUST download and store media files from YCloud for non-text messages.

#### Scenario: Download image media

- GIVEN a message with `message_type="image"` and `media_id="abc123"` exists in YCloud
- WHEN media download is triggered
- THEN the system calls `GET /v2/whatsapp/media/{mediaId}` to get the download URL
- AND downloads the file with a 30-second timeout
- AND saves to `uploads/{tenant_id}/whatsapp_media/{message_id}.{extension}`
- AND updates `media_url` with the local path
- AND sets `status='synced'`

#### Scenario: Media download failure

- GIVEN a message with `media_id` but the download fails (network timeout, 4xx/5xx error)
- WHEN download is attempted
- THEN the error is logged as warning
- AND the message is saved without `media_url`
- AND sync continues to the next message

#### Scenario: Skip audio over 10MB

- GIVEN a message with `message_type="audio"` and the file size is 15MB
- WHEN download is attempted
- THEN the download is skipped (size exceeds limit)
- AND the error is logged as warning
- AND sync continues

---

### Requirement: Backend Endpoints

The system MUST expose the following endpoints for sync management:

#### S1: POST /admin/ycloud/sync/start
- **Auth:** CEO role required (verify_ceo_token)
- **Body:** `{ tenant_id: number, password: string }`
- **Response:** `{ task_id: string, status: "queued", messages_fetched: 0, messages_saved: 0, media_downloaded: 0 }`
- **Errors:** 401 Unauthorized, 403 Password invalid, 429 Rate limited (sync in progress)

#### S2: GET /admin/ycloud/sync/status/{task_id}
- **Auth:** CEO role required
- **Response:** `{ task_id, status, messages_fetched, messages_saved, media_downloaded, errors[], started_at, completed_at }`
- **Status values:** queued | processing | completed | error | cancelled

#### S3: GET /admin/ycloud/sync/cancel/{task_id}
- **Auth:** CEO role required
- **Response:** `{ task_id, status: "cancelled" }`

#### S4: GET /admin/ycloud/sync/config
- **Auth:** CEO role required
- **Response:** `{ last_sync_at: string | null, sync_enabled: true, rate_limit_minutes: 60 }`

#### S5: POST /admin/ycloud/sync/config
- **Auth:** CEO role required
- **Body:** `{ sync_enabled: boolean }`
- **Response:** Updated config

#### S6: GET /admin/ycloud/sync/tasks
- **Auth:** CEO role required
- **Response:** `[{ task_id, tenant_id, status, messages_fetched, started_at, completed_at }]`

#### S7: GET /admin/ycloud/sync/history
- **Auth:** CEO role required
- **Query:** `?tenant_id=N&limit=50`
- **Response:** `[{ task_id, tenant_id, messages_fetched, messages_saved, media_downloaded, started_at, completed_at, status }]`

#### S8: GET /admin/whatsapp-messages
- **Auth:** CEO role required
- **Query:** `?tenant_id=N&patient_id=M&from_number=X&limit=50&offset=0`
- **Response:** Paginated list of whatsapp_messages

---

### Requirement: Rate Limiting

The system MUST enforce rate limits to prevent API abuse.

#### Scenario: Prevent duplicate sync

- GIVEN a sync task for tenant is already running (status: processing)
- WHEN a new sync is requested via POST /admin/ycloud/sync/start
- THEN the request returns HTTP 429 with message "Sync already in progress"
- AND the user must wait or cancel the existing task

#### Scenario: Minimum interval between syncs

- GIVEN the last successful sync completed less than 60 minutes ago
- WHEN a new sync is requested
- THEN the request returns HTTP 429 with message "Rate limited: wait X minutes"

---

### Requirement: Progress Tracking via Redis

The system MUST track sync progress in real-time using Redis.

#### Scenario: Progress tracking structure

- GIVEN a sync task starts with `task_id="abc123"` for tenant `tenant_id=1`
- WHEN the task is created
- THEN Redis key `ycloud_sync:1:abc123` is set with:
  ```
  {
    status: "queued",
    tenant_id: 1,
    messages_fetched: 0,
    messages_saved: 0,
    media_downloaded: 0,
    errors: [],
    started_at: null,
    completed_at: null
  }
  ```

#### Scenario: Update progress during sync

- GIVEN the sync is processing and has fetched 150 messages
- WHEN the progress is updated
- THEN the fields `messages_fetched`, `messages_saved`, `media_downloaded` reflect current counts
- AND `errors` contains any non-fatal errors encountered

#### Scenario: Finalize sync

- GIVEN the sync completes (success or error)
- WHEN the task finishes
- THEN `status` is set to `completed` or `error`
- AND `completed_at` is set to the current timestamp
- AND `errors` contains any fatal errors if applicable

---

## 3. MODIFIED Requirements

### Requirement: YCloudClient Extension

The YCloudClient class MUST be extended with new methods for message fetching and media download.

(Previously: Only send methods existed)

#### Scenario: fetch_messages method signature

```python
async def fetch_messages(
    self,
    limit: int = 100,
    page_after: str | None = None
) -> dict:
    """
    Fetch paginated messages from YCloud API v2.
    Returns: {items: [...], cursor: {after: "..."}, length: N, limit: N}
    """
```

#### Scenario: get_media_url method signature

```python
async def get_media_url(self, media_id: str) -> dict:
    """
    Get download URL for a media file.
    Returns: {url: "...", mime_type: "...", file_size: N}
    """
```

#### Scenario: download_media method signature

```python
async def download_media(self, url: str, timeout: int = 30) -> bytes:
    """
    Download media file bytes from URL.
    Returns: raw file bytes
    """
```

---

## 4. Edge Cases & Error Handling

### EC-01: YCloud API rate limit (429)

- WHEN the API returns 429 Too Many Requests
- THEN implement exponential backoff starting at 1s, 2s, 4s, 8s, max 60s
- AND retry up to 5 times

### EC-02: Invalid cursor

- GIVEN `pageAfter` cursor is invalid or expired
- WHEN `fetch_messages` is called
- THEN return empty results and stop pagination

### EC-03: Duplicate external_id

- GIVEN a message with `external_id` already exists in database
- WHEN sync attempts to insert
- THEN skip (idempotent upsert behavior)

### EC-04: Task timeout

- GIVEN a sync task runs for more than 30 minutes
- WHEN the timeout is reached
- THEN mark task as `error` with reason "timeout"
- AND log final progress

### EC-05: Database connection failure

- GIVEN database connection is lost during sync
- WHEN an operation fails
- THEN log error to `errors` array
- AND continue processing remaining messages

### EC-06: Orphan conversations

- GIVEN a message has no matching patient and no conversation exists
- WHEN linking is attempted
- THEN create a new conversation in `chat_conversations`
- AND link the message to the new conversation

---

## 5. Acceptance Criteria Summary

| ID | Criterion | Validation Method |
|----|-----------|-------------------|
| AC-01 | CEO can start sync from UI | Manual test: click sync button |
| AC-02 | Messages are fetched with pagination | Verify >100 messages sync correctly |
| AC-03 | No duplicates after re-sync | Run sync twice, check database |
| AC-04 | Patient linking works | Verify patient_id populated |
| AC-05 | Media downloads successfully | Check media_url populated |
| AC-06 | Progress indicator updates | Monitor real-time counter |
| AC-07 | Rate limiting enforced | Try sync within 60 min |
| AC-08 | Task can be cancelled | Call cancel endpoint |
| AC-09 | Timeout stops long sync | Let sync run 30+ min |
| AC-10 | Errors are logged | Check errors array in status |

---

## 6. API Contracts

### Request/Response: POST /admin/ycloud/sync/start

**Request:**
```json
{
  "tenant_id": 1,
  "password": "user_password"
}
```

**Success Response (202):**
```json
{
  "task_id": "sync_1_abc123",
  "status": "queued",
  "messages_fetched": 0,
  "messages_saved": 0,
  "media_downloaded": 0,
  "started_at": null,
  "completed_at": null
}
```

**Error Response (401):**
```json
{
  "detail": "Unauthorized"
}
```

**Error Response (403):**
```json
{
  "detail": "Invalid password"
}
```

**Error Response (429):**
```json
{
  "detail": "Sync already in progress or rate limited"
}
```

---

### Request/Response: GET /admin/ycloud/sync/status/{task_id}

**Success Response (200):**
```json
{
  "task_id": "sync_1_abc123",
  "status": "processing",
  "tenant_id": 1,
  "messages_fetched": 523,
  "messages_saved": 510,
  "media_downloaded": 45,
  "errors": [
    "Failed to download media abc123: timeout"
  ],
  "started_at": "2026-04-10T10:00:00Z",
  "completed_at": null
}
```

---

### Request/Response: GET /admin/whatsapp-messages

**Query Parameters:**
| Param | Type | Required | Default |
|-------|------|----------|---------|
| tenant_id | int | Yes | - |
| patient_id | int | No | null |
| from_number | string | No | null |
| limit | int | No | 50 |
| offset | int | No | 0 |

**Success Response (200):**
```json
{
  "items": [
    {
      "id": 1,
      "tenant_id": 1,
      "external_id": "wamid.123",
      "wamid": "wamid.123",
      "from_number": "5491155551234",
      "to_number": "5491155555678",
      "direction": "inbound",
      "message_type": "text",
      "content": "Hola doctor",
      "media_url": null,
      "media_id": null,
      "status": "synced",
      "patient_id": 5,
      "conversation_id": "uuid",
      "created_at": "2026-04-01T10:00:00Z",
      "synced_at": "2026-04-10T10:00:00Z"
    }
  ],
  "total": 523,
  "limit": 50,
  "offset": 0
}
```

---

**Next Phase:** Design (detailed component specifications, sequence diagrams).