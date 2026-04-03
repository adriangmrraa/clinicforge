# Technical Design: WhatsApp Multi-Attachment Analysis

## 1. System Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         WHATSAPP MESSAGE FLOW                               │
└─────────────────────────────────────────────────────────────────────────────┘

Patient sends: [img1, img2, img3, PDF1, PDF2] (no text)
                              ↓
┌─────────────────────────────────────────────────────────────────────────────┐
│ chat_webhook.py → buffer_manager.py                                        │
│ - Detects multiple media attachments                                        │
│ - Checks limits: MAX_IMAGES=10, MAX_PDFS=5                                  │
│ - Triggers background processing                                           │
└─────────────────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────────────────┐
│ buffer_task.py (MODIFIED)                                                  │
│ - Loop over all media (not just first)                                     │
│ - For each attachment:                                                     │
│   1. Download + analyze with vision_service                                │
│   2. Classify with image_classifier                                        │
│   3. Store in patient_documents                                            │
│ - Generate LLM summary from all analyses                                   │
│ - Store summary in clinical_record_summaries                               │
└─────────────────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────────────────┐
│                           STORAGE LAYER                                    │
├─────────────────────────────────────────────────────────────────────────────┤
│ patient_documents:                                                         │
│   - document_type: 'payment_receipt' | 'clinical'                         │
│   - source_details: {                                                       │
│       vision_description: "...",                                           │
│       llm_summary: "...",                                                   │
│       attachment_index: 0,                                                 │
│       mime_type: "image/jpeg"                                              │
│     }                                                                      │
│                                                                             │
│ clinical_record_summaries (NEW):                                          │
│   - tenant_id, patient_id, conversation_id                                │
│   - summary_text, attachments_count, attachments_types                     │
└─────────────────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────────────────┐
│                           FRONTEND LAYER                                    │
├─────────────────────────────────────────────────────────────────────────────┤
│ PatientDetail.tsx (Pestaña Resumen):                                       │
│ - After Odontogram: <AttachmentSummaryCard />                              │
│ - Shows: summary_text + date + count                                       │
│                                                                             │
│ PatientDetail.tsx (Pestaña Archivos):                                     │
│ - Existing: shows all patient_documents                                    │
│ - Classification visible via document_type                                 │
└─────────────────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────────────────┐
│                      AI DOCUMENTS GENERATION                               │
├─────────────────────────────────────────────────────────────────────────────┤
│ digital_records_service.py:                                                │
│ - Include llm_summary in template data                                      │
│ - Section: "Documentación Adicional"                                      │
└─────────────────────────────────────────────────────────────────────────────┘
```

## 2. Component Design

### 2.1 vision_service.py Extensions

```python
# NEW: PDF Analysis (uses GPT-4o vision capabilities)
async def analyze_pdf_url(pdf_url: str, tenant_id: int) -> Optional[str]:
    """
    Analyze a PDF document using Vision API.
    
    Note: GPT-4o supports PDF directly - no conversion needed.
    Falls back to text extraction if Vision fails.
    """
    # Similar to analyze_image_url but with PDF handling
    # Max size: 5MB, timeout: 30s

# NEW: Batch Processing
async def analyze_attachments_batch(
    attachments: List[Dict],
    tenant_id: int,
    max_concurrent: int = 5
) -> List[Dict]:
    """
    Process multiple attachments in parallel.
    
    Args:
        attachments: List of {url, mime_type, index}
        tenant_id: Tenant context
        max_concurrent: Max parallel Vision calls (rate limit protection)
    
    Returns:
        List of {index, vision_description, error}
    """
    # Use asyncio.gather with semaphore for concurrency control
```

### 2.2 buffer_task.py Modifications

```python
# Current (single image):
if has_recent_media:
    # Process only the latest media
    
# New (multiple attachments):
if has_recent_media:
    # 1. Fetch all media from chat_messages
    all_media = await fetch_all_media_from_message(conversation_id)
    
    # 2. Check limits
    images = [m for m in all_media if m.mime_type.startswith('image/')]
    pdfs = [m for m in all_media if m.mime_type == 'application/pdf']
    
    if len(images) > 10 or len(pdfs) > 5:
        log.warning(f"超越MAX_ATTACHMENTS, truncating")
    
    # 3. Batch analyze
    analyses = await analyze_attachments_batch(
        attachments=filtered_media,
        tenant_id=tenant_id
    )
    
    # 4. Classify each
    for analysis in analyses:
        classification = await classify_message(
            text="",  # No text
            tenant_id=tenant_id,
            vision_description=analysis.vision_description
        )
        
        # 5. Save to patient_documents
        await save_attachment(analysis, classification)
    
    # 6. Generate LLM summary
    summary = await generate_llm_summary(analyses)
    await save_summary(summary)
```

### 2.3 New Table Schema

```sql
-- clinical_record_summaries
CREATE TABLE clinical_record_summaries (
    id SERIAL PRIMARY KEY,
    tenant_id INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    patient_id INTEGER NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
    conversation_id VARCHAR(100),
    summary_text TEXT NOT NULL,
    attachments_count INTEGER DEFAULT 0,
    attachments_types JSONB DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(tenant_id, patient_id, conversation_id)
);

CREATE INDEX idx_summaries_tenant_patient ON clinical_record_summaries(tenant_id, patient_id);
```

### 2.4 Frontend Component

```tsx
// AttachmentSummaryCard.tsx
interface Props {
  summary: {
    summary_text: string;
    attachments_count: number;
    attachments_types: string[];
    created_at: string;
  };
}

export const AttachmentSummaryCard: React.FC<Props> = ({ summary }) => {
  const typeLabels = {
    payment: 'comprobantes de pago',
    clinical: 'documentos clínicos'
  };
  
  const countByType = summary.attachments_types.reduce((acc, type) => {
    acc[type] = (acc[type] || 0) + 1;
    return acc;
  }, {} as Record<string, number>);
  
  const typeSummary = Object.entries(countByType)
    .map(([type, count]) => `${count} ${typeLabels[type] || type}`)
    .join(', ');
  
  return (
    <div className="bg-white border border-gray-200 rounded-lg p-4 mt-4">
      <h4 className="font-semibold text-gray-800 text-sm mb-2">
        Análisis de Adjuntos Recibidos
      </h4>
      <p className="text-sm text-gray-600 leading-relaxed">
        {summary.summary_text}
      </p>
      <div className="mt-2 pt-2 border-t border-gray-100 text-xs text-gray-400">
        {summary.attachments_count} archivos • {typeSummary} •{' '}
        {new Date(summary.created_at).toLocaleDateString('es-AR')}
      </div>
    </div>
  );
};
```

### 2.5 AI Agent Context Update

The AI sales agent needs to know about this new functionality:

```
RULE: MULTIPLE ATTACHMENTS HANDLING
─────────────────────────────────────
When a patient sends multiple images/PDFs without text:
1. The system automatically analyzes each attachment with Vision AI
2. Each attachment is classified as:
   - "payment_receipt" (comprobante de pago)
   - "clinical" (documento médico: receta, estudio, etc.)
3. All attachments are saved to patient's "Archivos" section
4. A summary is generated and shown in "Resumen" tab (under odontogram)
5. The summary is available for AI document generation

YOU (AI Agent) can reference this by:
- Asking: "list_patient_documents" tool to see all attachments
- The summary is in patient_documents.source_details.llm_summary
- For new documents, mention: "Se adjuntan los documentos que enviaste"

When patient asks about their documents:
- Use list_patient_documents to show what they sent
- Mention the summary was generated automatically
```

## 3. Integration Points

| File | Change Type | Description |
|------|-------------|--------------|
| `services/vision_service.py` | Modify | Add `analyze_pdf_url()`, `analyze_attachments_batch()` |
| `services/image_classifier.py` | Modify | Enhanced classification with vision descriptions |
| `services/buffer_task.py` | Modify | Loop over all media, batch processing |
| `services/digital_records_service.py` | Modify | Include `llm_summary` in document templates |
| `admin_routes.py` | Modify | Add endpoint to fetch attachment summaries |
| `alembic/versions/016_...` | Create | New table `clinical_record_summaries` |
| `frontend/.../PatientDetail.tsx` | Modify | Add `AttachmentSummaryCard` component |
| `AGENTS.md` | Modify | Update AI agent context about multi-attachments |

## 4. Error Handling

| Scenario | Behavior |
|----------|----------|
| Vision API fails for 1 image | Save attachment without description, continue |
| PDF too large (>5MB) | Log warning, skip analysis, save file only |
| All Vision calls fail | Save attachments, mark summary as "no disponible" |
| Rate limit hit | Semaphore queues requests, retries after 1s |
| DB error on save | Rollback batch, log error, notify admin |

## 5. Performance & Cost

| Metric | Value |
|--------|-------|
| Max concurrent Vision calls | 5 |
| Timeout per attachment | 30s |
| Timeout per batch | 300s (5 min) |
| Cost per 5 images | ~$0.007 |
| Cost per 5 PDFs | ~$0.035 |
| DB storage per summary | ~500 bytes |

## 6. Rollback Plan

1. Revert buffer_task.py to single-attachment processing
2. Downgrade migration (drop clinical_record_summaries table)
3. digital_records_service.py removes llm_summary section
4. Frontend: hide AttachmentSummaryCard (or remove)
5. Agent context: remove multi-attachment rules from system prompt