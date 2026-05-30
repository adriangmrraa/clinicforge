# Script FAQ Embeddings Sync — Specification

## Purpose

Ensure that FAQ entries inserted via SQL scripts (bypassing application hooks) have their vector embeddings generated and stored for RAG semantic search. Fix import bug, guarantee startup sync, and provide optional admin endpoint for manual sync.

## Requirements

### Requirement: Startup Embedding Sync

The system **MUST** synchronize embeddings for all FAQ entries that lack embeddings when the orchestrator service starts.

#### Scenario: Service Startup with Missing Embeddings

- GIVEN the orchestrator service is starting
- AND there are FAQ entries in `clinic_faqs` table without corresponding rows in `faq_embeddings`
- WHEN the startup sync task runs
- THEN the system **MUST** generate embeddings for each missing FAQ entry
- AND store them in `faq_embeddings` table
- AND log the count of embeddings created per tenant

#### Scenario: Startup Sync with pgvector Unavailable

- GIVEN pgvector extension is not installed or not accessible
- WHEN the startup sync task runs
- THEN the system **MUST** skip embedding generation
- AND log a warning that RAG is unavailable

#### Scenario: Startup Sync with No Missing Embeddings

- GIVEN all FAQ entries already have embeddings
- WHEN the startup sync task runs
- THEN the system **SHALL** not generate any new embeddings
- AND log that zero embeddings were created

### Requirement: Import Bug Fix

The system **MUST** correctly import `sync_all_tenants_embeddings` function from `services.embedding_service` in `main.py`.

#### Scenario: Service Startup with Fixed Import

- GIVEN the import statement in `main.py` is corrected
- WHEN the orchestrator service starts
- THEN the startup sync task **MUST** execute without ImportError
- AND embeddings **MUST** be synchronized as expected

### Requirement: Admin Manual Sync Endpoint (Optional)

The system **MAY** provide an admin endpoint to trigger manual synchronization of embeddings without restarting the service.

#### Scenario: Admin Triggers Manual Sync via API

- GIVEN an authenticated admin user with valid `X‑Admin‑Token`
- WHEN they POST to `/admin/rag/sync‑embeddings`
- THEN the system **MUST** initiate synchronization of missing embeddings for all tenants
- AND return a JSON response with `{"status": "started", "message": "Sync initiated"}`
- AND the sync **MUST** run asynchronously in the background

#### Scenario: Manual Sync While Sync Already Running

- GIVEN a sync task is already in progress
- WHEN another manual sync request arrives
- THEN the system **MUST** return a `409 Conflict` response indicating sync already running
- AND **MUST NOT** start a duplicate sync task

### Requirement: Tenant Isolation

Embedding synchronization **MUST** be isolated per tenant; each tenant's FAQs **MUST** only be matched with embeddings within the same tenant.

#### Scenario: Multi‑tenant Embedding Sync

- GIVEN two active tenants A and B
- AND tenant A has missing FAQ embeddings
- WHEN the sync runs (startup or manual)
- THEN embeddings **MUST** be generated only for tenant A's missing FAQs
- AND tenant B's data **MUST NOT** be affected

### Requirement: Idempotent Sync

The sync operation **MUST** be idempotent; running it multiple times **SHALL** not create duplicate embeddings or change existing embeddings unless the underlying FAQ content has changed.

#### Scenario: Repeated Sync with Unchanged FAQs

- GIVEN all FAQ entries already have up‑to‑date embeddings
- WHEN the sync runs a second time
- THEN the system **SHALL** not modify any existing embedding rows
- AND the log **SHOULD** indicate zero embeddings created

## Out of Scope

- Modifying the embedding generation algorithm (OpenAI model, vector dimensions)
- Adding real‑time sync hooks for SQL INSERT operations (outside application layer)
- Sync of other embedding types (insurance, derivation, treatment instructions) – may be added later

## Acceptance Criteria

1. Service starts without ImportError referencing `sync_all_tenants_embeddings`
2. On startup, missing FAQ embeddings are generated and stored in `faq_embeddings`
3. Sync respects tenant isolation (embeddings are created only for the tenant's missing FAQs)
4. Admin endpoint `/admin/rag/sync‑embeddings` returns `202 Accepted` and triggers background sync (optional)
5. Concurrent sync requests are prevented (409 Conflict)
6. Sync is idempotent – no duplicate embeddings created on repeated runs