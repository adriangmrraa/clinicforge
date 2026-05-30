# Design: YCloud Full Message Sync

## Technical Approach

Implementar un servicio de sincronización híbrida asíncrona que:
1. Extiende el `YCloudClient` existente con métodos para fetch paginado y media
2. Crea una nueva tabla `whatsapp_messages` dedicada (no reutiliza ChatMessage)
3. Usa BackgroundTasks de FastAPI para ejecución async sin blocking
4. Persiste progreso en Redis con estructura `ycloud_sync:{tenant_id}:{task_id}`

## Architecture Decisions

### Decision: Nueva tabla whatsapp_messages vs extensión de ChatMessage

**Choice**: Nueva tabla específica `whatsapp_messages` con 16 campos
**Alternatives considered**: Extender ChatMessage con campos adicionales
**Rationale**: ChatMessage tiene schema complejo para el agente (role, content_attributes). Los mensajes de YCloud son estructurados diferentes (direction, message_type, status).分开 mejora mantenibilidad y permite índices optimizados para el caso de uso sync.

---

### Decision: Cursor-based pagination

**Choice**: Cursor-based, 100 mensajes por página, máximo 10,000 total
**Alternatives considered**: Offset-based, timestamp-based
**Rationale**: YCloud API v2 soporta cursor native. Offset tiene problemas con mensajes nuevos que aparecen durante el sync. Timestamp-based requiere que la API filtre por rango, no todos los providers lo soportan.

---

### Decision: Almacenamiento de media en uploads/{tenant_id}/whatsapp_media/

**Choice**: Local filesystem en UPLOADS_DIR
**Alternatives considered**: S3-compatible storage, Redis con expiry
**Rationale**: El proyecto ya usa uploads local (ver UPLOADS_DIR en db.py). Media expira en YCloud a los 30 días, el backup local persiste. No introduce dependencia externa nueva.

---

### Decision: Exponential backoff para rate limiting

**Choice**: Backoff 1s → 2s → 4s → 8s → max 60s, hasta 5 retry
**Alternatives considered**: Fixed delay, linear backoff
**Rationale**: YCloud puede retornar 429 frecuentemente. Exponential permite recuperación rápida cuando es transient, pero limita daño cuando es sostenido.

---

### Decision: Phone normalization E.164

**Choice**: Normalizar a E.164 (549 + area + número) removiendo +, espacios, guiones
**Alternatives considered**: Guardar formato original sin normalizar, usar libphone-number
**Rationale**: La tabla patients.phone_number ya usa E.164 según el modelo existente. Simplicidad > precise library para el caso Argentina.

---

### Decision: Lock por tenant en Redis

**Choice**: Redis key `ycloud_sync_lock:{tenant_id}` con TTL 30 min
**Alternatives considered**: Database lock (pg_advisory), process mutex
**Rationale**: Redis es más rápido de chequear y ya está en el stack. El TTL actúa como timeout automático si el proceso muere.

---

### Decision: Timeout global de 30 minutos

**Choice**: 30 min max por sync task
**Alternatives considered**: Sin timeout, timeout 60 min
**Rationale**: 10,000 msgs × 100/page = 100 páginas. Con backoff promedio 2s = 200s + DB inserts. 30 min es suficiente y previene sync eternos.

---

## Data Flow

```
┌─────────────────────────────────────────────────────────────────────┐
│                    Sync Start Flow                                   │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  Frontend        API              Redis              Background Task    │
│    │              │                │                      │            │
│    │  POST /start │                │                      │            │
│    │────────────>│                │                      │            │
│    │             │  Check lock    │                      │            │
│    │             │───────────────>│                      │            │
│    │             │  exists?       │                      │            │
│    │             │<───────────────│                      │            │
│    │             │                │                      │            │
│    │  if locked  │                │                      │            │
│    │<────────────│ (429 error)    │                      │            │
│    │             │                │                      │            │
│    │  else      │                │                      │            │
│    │             │  Set lock     │                      │            │
│    │             │───────────────>│                      │            │
│    │             │  Create task │                      │            │
│    │             │<──────────────│                      │            │
│    │  Response   │                │                      │            │
│    │<────────────│                │                      ▼            │
│    │             │                │        ┌──────────────────┐   │
│    │             │                │        │ YCloudSyncService │   │
│    │             │                │        └──────────────────┘   │
│    │             │                │                      │            │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│              Message Fetch + Persist Flow                            │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  YCloudSyncService    YCloudAPIClient      DB           Redis            │
│         │                 │              │             │                │
│         │  fetch_messages(limit=100)                           │
│         │──────────────────────────────────>│                   │
│         │                 │              │             │                │
│         │<───────────────────────────────────│ (items, cursor)  │
│         │                 │              │             │                │
│         │  for each msg  │              │             │                │
│         │──────────────>│              │             │                │
│         │                 │              │             │                │
│         │              │  INSERT/UPDATE │             │                │
│         │              │───────────────>│             │                │
│         │              │  whatsapp_messages                  │                │
│         │              │<───────────────│             │                │
│         │                 │              │             │                │
│         │  Update progress              │             │                │
│         │────────────────────────────────────────>│                │
│         │                 │              │             │                │
│         │  if cursor exists                                 │
│         │<────────────────────────────────────────        │
│         │                 │              │             │                │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│                 Media Download Flow                                  │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  YCloudSyncService    YCloudAPIClient      Filesystem                 │
│         │                 │              │                         │
│         │  get_media_url(media_id)      │                         │
│         │─────────────────────────────────>│                     │
│         │<─────────────────────────────────│ (url, mime_type)   │
│         │                 │              │                         │
│         │  download_media(url, timeout=30)                         │
│         │─────────────────────────────────>│                     │
│         │<─────────────────────────────────│ (bytes)          │
│         │                 │              │                         │
│         │  Save to UPLOADS_DIR/{tenant_id}/whatsapp_media/{msg_id}.{ext}│
│         │─────────────────────────────────>│                     │
│         │                 │              │                         │
│         │  Update media_url in DB       │                         │
│         │─────────────────────────────────>│                     │
│         │                 │              │                         │
└─────────────────────────────────────────────────────────────────────┘
```

## File Changes

| File | Action | Description |
|------|--------|-------------|
| `orchestrator_service/ycloud_client.py` | Modify | Agregar fetch_messages(), get_media_url(), download_media() |
| `orchestrator_service/models.py` | Modify | Agregar WhatsAppMessage model (16 fields) |
| `orchestrator_service/alembic/versions/044_whatsapp_messages.py` | Create | Nueva migración Alembic |
| `orchestrator_service/services/ycloud_sync_service.py` | Create | YCloudSyncService orchestration |
| `orchestrator_service/admin_routes.py` | Modify | Agregar /admin/ycloud/sync/* endpoints |
| `src/components/admin/YCloudSyncSection.tsx` | Create | Componente UI sync |
| `src/views/ConfigView.tsx` | Modify | Integrate YCloudSyncSection en YCloud tab |
| `src/api/ycloud.ts` | Create | API client functions |

## Interfaces / Contracts

### Modelo datos: whatsapp_messages

```python
# orchestrator_service/models.py
class WhatsAppMessage(Base):
    __tablename__ = "whatsapp_messages"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    external_id = Column(String(64), Unique=True)  # YCloud message ID
    wamid = Column(String(64), Index=True)  # WhatsApp message ID
    from_number = Column(String(32), nullable=False)
    to_number = Column(String(32), nullable=False)
    direction = Column(String(16), nullable=False, CheckConstraint("direction IN ('inbound', 'outbound')"))
    message_type = Column(String(32), nullable=False)
    content = Column(Text, nullable=True)
    media_url = Column(String(512), nullable=True)
    media_id = Column(String(128), nullable=True)
    status = Column(String(16), nullable=False, server_default="synced")
    patient_id = Column(Integer, ForeignKey("patients.id"), nullable=True)
    conversation_id = Column(UUID(as_uuid=True), ForeignKey("chat_conversations.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, Index=True)
    synced_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("idx_whatsapp_messages_from_number", "from_number"),
        Index("idx_whatsapp_messages_tenant_created", "tenant_id", "created_at"),
    )
```

### API Endpoints

```python
# Request/Response schemas

class SyncStartRequest(BaseModel):
    tenant_id: int
    password: str

class SyncStartResponse(BaseModel):
    task_id: str
    status: Literal["queued", "processing", "completed", "error", "cancelled"]
    messages_fetched: int
    messages_saved: int
    media_downloaded: int
    started_at: Optional[datetime]
    completed_at: Optional[datetime]

class SyncStatusResponse(BaseModel):
    task_id: str
    status: str
    tenant_id: int
    messages_fetched: int
    messages_saved: int
    media_downloaded: int
    errors: List[str]
    started_at: Optional[datetime]
    completed_at: Optional[datetime]

class WhatsAppMessageResponse(BaseModel):
    id: int
    tenant_id: int
    external_id: str
    wamid: Optional[str]
    from_number: str
    to_number: str
    direction: str
    message_type: str
    content: Optional[str]
    media_url: Optional[str]
    media_id: Optional[str]
    status: str
    patient_id: Optional[int]
    conversation_id: Optional[uuid.UUID]
    created_at: datetime
    synced_at: datetime
```

### Redis Progress Structure

```python
# Key: ycloud_sync:{tenant_id}:{task_id}
# TTL: 35 minutos (timeout + buffer)

{
    "task_id": "sync_1_abc123",
    "status": "processing",  # queued | processing | completed | error | cancelled
    "tenant_id": 1,
    "messages_fetched": 523,
    "messages_saved": 510,
    "media_downloaded": 45,
    "errors": ["Failed to download media abc123: timeout"],
    "started_at": "2026-04-10T10:00:00Z",
    "completed_at": None
}
```

### Frontend Props

```typescript
// YCloudSyncSection.tsx
interface YCloudSyncSectionProps {
  tenantId: number;
  className?: string;
}

interface SyncProgress {
  task_id: string;
  status: 'queued' | 'processing' | 'completed' | 'error' | 'cancelled';
  messages_fetched: number;
  messages_saved: number;
  media_downloaded: number;
  errors: string[];
  started_at: string;
  completed_at: string | null;
}
```

## Testing Strategy

| Layer | What to Test | Approach |
|-------|------------|---------|
| Unit | Phone normalization, backoff logic, deduplication | Mock YCloudClient, test pure functions |
| Integration | fetch_messages pagination, insert to DB | Test single page sync, verify DB state |
| E2E | Full sync flow from UI | Manual test with real YCloud account |

## Migration / Rollout

1. **Pre-migration**: Ninguna data existente que migrar (tabla nueva)
2. **Deploy**: Alembic upgrade sincroniza la nueva tabla
3. **Feature flag**: sync_enabled en tenants.config (default true)
4. **Rollback**: alembic downgrade removes tabla

## Open Questions

- [ ] Confirmar que YCloud API v2 soporta cursor pagination con `pageAfter` param
- [ ] Verificar tamaño máximo de media (spec dice 10MB skip) - confirmar con YCloud docs
- [ ] Necesitamos endpoint para cleanup de media orphaned?

---

## Design Created

**Change**: ycloud-sync  
**Location**: `openspec/changes/ycloud-sync/design.md`

### Summary
- **Approach**: Hybrid async background sync con Redis progress tracking
- **Key Decisions**: 8 documented (pagination, storage, backoff, phone normalization, lock, timeout)
- **Files Affected**: 8 (1 new service, 3 new files, 4 modified)
- **Testing Strategy**: Unit + Integration + Manual E2E

### Open Questions
- YCloud cursor pagination param name confirmation needed
- Media max size verification needed (10MB specified in spec)

### Next Step
Ready for tasks (sdd-tasks).