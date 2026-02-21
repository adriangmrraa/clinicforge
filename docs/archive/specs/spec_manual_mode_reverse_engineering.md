# Specification: Manual Mode Parity (YCloud vs Chatwoot)

## 1. Analysis: How YCloud Works (The "Gold Standard")
In `ChatsView.tsx`, YCloud manual mode is managed via the `sessions` state array and `selectedSession`.

### Data Structure
- `ChatSession` interface has a `status` field: `'active' | 'human_handling' | 'paused' | 'silenced'`.
- "Manual Mode" is active when `status` is `'silenced'` or `'human_handling'`.

### Visual Feedback
1.  **Banner**: Checks `selectedSession.status`.
2.  **Button**: Checks `selectedSession.status`.
3.  **Avatar/List**: Derives visuals from `status`.

### State Updates
1.  **Optimistic (Local)**: `handleToggleHumanMode` updates `sessions` and `selectedSession` immediately before/after the API call.
2.  **Real-time (Socket)**: `HUMAN_OVERRIDE_CHANGED` listener finds the session by `phone_number` and updates the `status`.

## 2. Analysis: How Chatwoot Currently Works (The "Defect")
Chatwoot is managed via `chatwootList` and `selectedChatwoot`.

### Data Structure
- `ChatSummaryItem` has an `is_locked` boolean.
- "Manual Mode" is active when `is_locked` is `true`.

### Visual Feedback
1.  **Banner**: Checks `selectedChatwoot.is_locked`.
2.  **Button**: Checks `selectedChatwoot.is_locked`.

### The Discrepancy
The issue likely lies in **how** React detects the `selectedChatwoot` change.
- In YCloud socket listener: `setSelectedSession` is called with a **new object** derived from the updated list.
- In Chatwoot socket listener: We implemented matching logic, but we must ensure `setSelectedChatwoot` receives a **new object reference** that triggers the re-render.

## 3. Discrepancy Details
- **YCloud**:
  ```typescript
  // Matches by unique phone number
  s.phone_number === data.phone_number
  ```
- **Chatwoot**:
  We recently added matching by `conversation_id`.
  **CRITICAL FINDING**: The backend might be sending `conversation_id` as a UUID string, but `ChatSummaryItem.id` (from Chatwoot API) might be an **Integer** ID converted to string, or the internal DB ID.
  - `ChatSummaryItem.id` in `chat_api.py` (summary endpoint) usually comes from `chat_conversations.id` (UUID).
  - But `ChatwootAdapter` might be using the *external* Chatwoot ID.
  
  **Verification Needed**:
  - Check `chatsApi.fetchChatsSummary` response structure.
  - Check if `selectedChatwoot.id` matches the `conversation_id` sent by the socket.

## 4. Proposed Solution (The Fix)
1.  **Unify Identification**: Ensure `selectedChatwoot.id` IS the UUID from our DB (`chat_conversations.id`), NOT the integer ID from Chatwoot.
2.  **Force Re-render**: In the socket listener, use a functional update for `setSelectedChatwoot` that guarantees a new object reference if the ID matches.
3.  **Consistent Optimistic Update**: Extract the Chatwoot toggle logic into a standalone function `handleToggleChatwootLock` mimicking `handleToggleHumanMode`.

## 5. Verification Plan
1.  Log the `id` of `selectedChatwoot` in the console.
2.  Log the `conversation_id` coming from the socket.
3.  Ensure they are identical strings.
