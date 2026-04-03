# Tasks: WhatsApp Multi-Attachment Analysis

## Phase 1: Backend - Vision & Processing (Foundation)

### 1.1 Extend vision_service.py
- [ ] 1.1.1 Add `analyze_pdf_url()` function - PDF analysis with GPT-4o Vision
- [ ] 1.1.2 Add `analyze_attachments_batch()` with asyncio.gather + semaphore
- [ ] 1.1.3 Handle limits: MAX_IMAGES=10, MAX_PDFS=5, MAX_SIZE=5MB
- [ ] 1.1.4 Add logging for batch processing

### 1.2 Create migration for clinical_record_summaries
- [ ] 1.2.1 Create Alembic migration `016_add_clinical_record_summaries.py`
- [ ] 1.2.2 Define table: id, tenant_id, patient_id, conversation_id, summary_text, attachments_count, attachments_types, created_at
- [ ] 1.2.3 Add indexes for tenant+patient

### 1.3 Enhance image_classifier.py
- [ ] 1.3.1 Extend to accept vision_description as primary input
- [ ] 1.3.2 Add PDF-specific keywords detection
- [ ] 1.3.3 Return classification per attachment

## Phase 2: Backend - Buffer Task Integration

### 2.1 Modify buffer_task.py
- [ ] 2.1.1 Fetch all media from chat_messages (not just latest)
- [ ] 2.1.2 Apply limits check (10 images, 5 PDFs)
- [ ] 2.1.3 Call batch analyze for all attachments
- [ ] 2.1.4 Loop classification for each attachment
- [ ] 2.1.5 Save each to patient_documents with source_details

### 2.2 LLM Summary Generation
- [ ] 2.2.1 Create `generate_attachment_summary()` function
- [ ] 2.2.2 Call LLM with all vision descriptions
- [ ] 2.2.3 Save summary to clinical_record_summaries
- [ ] 2.2.4 Update first attachment's source_details with summary

### 2.3 Error Handling
- [ ] 2.3.1 Handle individual attachment failures (don't break batch)
- [ ] 2.3.2 Log warnings for skipped files (size limit, type)
- [ ] 2.3.3 Graceful fallback if summary generation fails

## Phase 3: Frontend Integration

### 3.1 Create AttachmentSummaryCard Component
- [ ] 3.1.1 Create `frontend_react/src/components/AttachmentSummaryCard.tsx`
- [ ] 3.1.2 Design: rectangular, formal, under odontogram
- [ ] 3.1.3 Display: summary_text, date, attachment count, types

### 3.2 Update PatientDetail.tsx
- [ ] 3.2.1 Import AttachmentSummaryCard
- [ ] 3.2.2 Add to case 'summary': after Odontogram component
- [ ] 3.2.3 Fetch summary data from new endpoint

### 3.3 API Endpoint
- [x] 3.3.1 Add `GET /patients/{id}/attachments-summary` in admin_routes.py
- [x] 3.3.2 Query clinical_record_summaries for latest summary
- [x] 3.3.3 Return: summary_text, attachments_count, attachments_types, created_at

## Phase 4: AI Documents Integration

### 4.1 Modify digital_records_service.py
- [ ] 4.1.1 Fetch llm_summary from patient_documents
- [ ] 4.1.2 Include in gather_patient_data() result
- [ ] 4.1.3 Add section "Documentación Adicional" in templates

### 4.2 Template Updates
- [ ] 4.2.1 Update clinical_report template to include llm_summary
- [ ] 4.2.2 Update odontogram_art template
- [ ] 4.2.3 Update authorization_request template

## Phase 5: AI Agent Context (System Prompt)

### 5.1 Update AGENTS.md
- [ ] 5.1.1 Add "RULE: MULTIPLE ATTACHMENTS HANDLING" section
- [ ] 5.1.2 Explain how agent can access attachment summaries
- [ ] 5.1.3 Document list_patient_documents tool usage

### 5.2 System Prompt Updates
- [ ] 5.2.1 Add context about automatic attachment analysis
- [ ] 5.2.2 Explain when to mention patient's sent documents
- [ ] 5.2.3 Document how to reference llm_summary

## Phase 6: Testing

### 6.1 Unit Tests
- [ ] 6.1.1 Test vision_service batch processing
- [ ] 6.1.2 Test image_classifier with PDF content
- [ ] 6.1.3 Test summary generation LLM call

### 6.2 Integration Tests
- [ ] 6.2.1 Test full flow: 5 images → classification → save → summary
- [ ] 6.2.2 Test PDF processing
- [ ] 6.2.3 Test limit enforcement (11 images should warn)

### 6.3 E2E Tests
- [ ] 6.3.1 Simulate patient sending multiple attachments
- [ ] 6.3.2 Verify summary appears in UI
- [ ] 6.3.3 Verify document generation includes summary

---

## Dependencies Graph
```
1.1 → 1.2 → 1.3
1.1 → 2.1 → 2.2 → 2.3
3.1 → 3.2 → 3.3
2.2 → 4.1 → 4.2
5.1 → 5.2 (independent)
All → 6.x
```

## Effort Estimation
- Small: 4 tasks
- Medium: 10 tasks
- Large: 4 tasks

## Recommended Execution Order
1. **Phase 1** (1.1-1.3) - Backend foundation
2. **Phase 2** (2.1-2.3) - Core processing
3. **Phase 4** (4.1-4.2) - Documents (parallel with 3)
4. **Phase 3** (3.1-3.3) - Frontend
5. **Phase 5** (5.1-5.2) - AI context (anytime)
6. **Phase 6** - Testing (end)