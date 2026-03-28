# Spec 07: ROI Dashboard Consolidado + Sistema RAG para Agente IA

**Fecha:** 2026-03-28
**Prioridad:** Alta
**Complejidad:** Alta (multi-capa: DB, backend, AI pipeline, frontend)

---

## 1. Contexto y Objetivos

### Problema 1 — ROI Analytics Fragmentado
Existen dos servicios paralelos que calculan ROI de formas distintas:
- `metrics_service.py`: Endpoints completos (`/admin/metrics/*`) pero usa **placeholders** (spend=$100, value=$500) en vez de datos reales.
- `marketing_service.py`: Tiene datos reales de Meta API pero endpoints limitados (`/admin/marketing/stats/roi`).

**Resultado:** El frontend (`MarketingHubView`) solo consume `/admin/marketing/stats`. Los 7 endpoints de métricas unificadas (`/admin/metrics/*`) no tienen frontend. No existe dashboard de ROI con atribución first/last touch, tendencias ni mix.

### Problema 2 — Sin RAG (Retrieval-Augmented Generation)
El agente IA inyecta **las 20 FAQs completas** en cada prompt sin filtro semántico. Esto:
- Desperdicia ~500-800 tokens por request (se inyectan FAQs irrelevantes).
- No escala: si un tenant tiene 50+ FAQs, excede el límite de 20 y pierde información.
- No permite búsqueda semántica sobre documentos clínicos ni notas.

### Objetivos
1. **ROI Dashboard**: Consolidar métricas reales en un dashboard dedicado con atribución, tendencias y comparaciones.
2. **RAG System**: Implementar búsqueda semántica con pgvector para FAQs y documentos clínicos, optimizando tokens y mejorando precisión del agente.

---

## 2. Requerimientos Técnicos

### 2.A — Backend: ROI Consolidation

#### 2.A.1: Eliminar placeholders de `metrics_service.py`
- **Archivo:** `orchestrator_service/services/metrics_service.py`
- Reemplazar `estimated_spend = 100` (línea ~337) con llamada real a `marketing_service.get_roi_stats()` para obtener spend de Meta API.
- Si no hay token Meta configurado → usar `tenants.consultation_price * total_patients` como estimación (ya disponible en DB).
- Agregar campo `data_source: "meta_api" | "estimated"` en la respuesta para transparencia.

#### 2.A.2: Unificar fuente de datos
- `MetricsService.get_roi_dashboard()` debe llamar a `MarketingService.get_roi_stats()` para obtener spend real.
- Mantener ambos servicios separados (métricas = cálculo/agregación, marketing = integración con APIs externas).
- Agregar al dashboard: `revenue_from_billing` calculado desde `appointments.billing_amount WHERE payment_status IN ('paid', 'partial')`.

#### 2.A.3: Nuevo endpoint de resumen ejecutivo
- **Ruta:** `GET /admin/metrics/executive-summary`
- **Response:**
```json
{
  "period": "last_30d",
  "total_spend": 1500.00,
  "total_revenue": 8500.00,
  "roi_percentage": 466.7,
  "total_leads": 45,
  "total_conversions": 12,
  "conversion_rate": 26.7,
  "cost_per_lead": 33.33,
  "cost_per_conversion": 125.00,
  "top_campaign": { "name": "Implantes Premium", "roi": 580.0 },
  "data_source": "meta_api",
  "platforms": ["meta"]
}
```

### 2.B — Backend: RAG System

#### 2.B.1: Alembic Migration — pgvector + embeddings tables
- **Migration:** `007_pgvector_embeddings.py`
- Habilitar extensión `vector` en PostgreSQL.
- Crear tabla `faq_embeddings`:

```sql
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE faq_embeddings (
    id SERIAL PRIMARY KEY,
    tenant_id INTEGER NOT NULL REFERENCES tenants(id),
    faq_id INTEGER NOT NULL REFERENCES clinic_faqs(id) ON DELETE CASCADE,
    content TEXT NOT NULL,           -- question + answer concatenados
    embedding vector(1536) NOT NULL, -- OpenAI text-embedding-3-small
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(faq_id)
);

CREATE INDEX idx_faq_embeddings_tenant ON faq_embeddings(tenant_id);
CREATE INDEX idx_faq_embeddings_vector ON faq_embeddings
    USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);
```

- Crear tabla `document_embeddings` (fase 2, opcional):

```sql
CREATE TABLE document_embeddings (
    id SERIAL PRIMARY KEY,
    tenant_id INTEGER NOT NULL REFERENCES tenants(id),
    source_type VARCHAR(50) NOT NULL,  -- 'clinical_record', 'patient_document', 'patient_memory'
    source_id INTEGER NOT NULL,
    content TEXT NOT NULL,
    embedding vector(1536) NOT NULL,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(source_type, source_id)
);

CREATE INDEX idx_doc_embeddings_tenant ON document_embeddings(tenant_id);
CREATE INDEX idx_doc_embeddings_vector ON document_embeddings
    USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);
```

- Actualizar `models.py` con ambas clases ORM.

#### 2.B.2: Embedding Service
- **Archivo nuevo:** `orchestrator_service/services/embedding_service.py`
- Usar OpenAI `text-embedding-3-small` (1536 dims, ~$0.02/1M tokens).
- Funciones:
  - `generate_embedding(text: str) -> list[float]` — genera vector de un texto.
  - `upsert_faq_embedding(tenant_id, faq_id, question, answer)` — genera y guarda embedding de FAQ.
  - `sync_tenant_faq_embeddings(tenant_id)` — sincroniza todos los FAQs de un tenant.
  - `search_similar_faqs(tenant_id, query, top_k=5) -> list[dict]` — búsqueda semántica.
  - `delete_faq_embedding(faq_id)` — elimina embedding al borrar FAQ.

- **Modelo configurable:** Leer de `system_config` tabla, key `MODEL_EMBEDDINGS`, default `text-embedding-3-small`.

#### 2.B.3: Hooks de sincronización
- Cuando se crea/actualiza/elimina un FAQ (`admin_routes.py` endpoints de FAQs), disparar `upsert_faq_embedding` o `delete_faq_embedding` en background (fire-and-forget con `asyncio.create_task`).
- Al startup del servicio, ejecutar `sync_tenant_faq_embeddings` para todos los tenants activos (idempotente).

#### 2.B.4: Integrar RAG en el prompt pipeline
- **Archivo:** `orchestrator_service/main.py`, función `_format_faqs()`
- Cambiar de: inyectar 20 FAQs estáticas → buscar top-5 FAQs semánticamente relevantes al mensaje del usuario.
- **Fallback:** Si pgvector no está disponible o no hay embeddings → usar el sistema actual (las 20 FAQs estáticas). Esto garantiza backwards compatibility.
- Modificar `build_system_prompt()` para recibir `user_message: str` (el mensaje actual del paciente) y usarlo para la búsqueda semántica.
- La búsqueda semántica se ejecuta en `buffer_task.py` antes de construir el prompt, pasando los FAQs relevantes.

#### 2.B.5: Tool de búsqueda para Nova
- Agregar tool `buscar_en_base_conocimiento` a Nova (`nova_tools.py`):
```python
async def buscar_en_base_conocimiento(query: str, tipo: str = "faq") -> str:
    """Busca información relevante en la base de conocimiento de la clínica."""
```
- Permite a Nova hacer búsquedas semánticas on-demand cuando el admin pregunta algo que no está en su contexto.

### 2.C — Frontend: ROI Dashboard

#### 2.C.1: Nueva vista `ROIDashboardView.tsx`
- **Ruta:** `/roi-dashboard` (agregar a `App.tsx` y `Sidebar.tsx`)
- **Icono sidebar:** `TrendingUp` de lucide-react
- **Secciones:**

**Header — KPIs ejecutivos (cards)**
- Total Spend | Total Revenue | ROI % | Leads | Conversions | Cost/Lead
- Fuente: `GET /admin/metrics/executive-summary`
- Badge indicando `data_source` (real vs estimado)

**Sección 1 — Tendencia de ROI (line chart)**
- Eje X: tiempo (configurable daily/weekly/monthly)
- Eje Y: ROI %, leads, conversions
- Fuente: `GET /admin/metrics/trend`

**Sección 2 — Attribution Mix (pie/donut chart)**
- Distribución: First Touch / Last Touch / Conversion / Organic
- Fuente: `GET /admin/metrics/attribution/mix`

**Sección 3 — First vs Last Touch (grouped bar chart)**
- Comparación lado a lado por campaña
- Fuente: `GET /admin/metrics/comparison/first-vs-last`

**Sección 4 — Top Campaigns (tabla)**
- Top 10 campañas con leads, conversiones, ROI, spend
- Sorteable por columna
- Fuente: `GET /admin/metrics/top/campaigns`

**Filtros globales:**
- Período: 7d, 30d, 90d, custom
- Plataforma: Meta / Google / All
- Attribution: First Touch / Last Touch

#### 2.C.2: Componentes reutilizables
- `KPICard.tsx` — Card individual con valor, label, trend arrow, delta %
- `AttributionPieChart.tsx` — Donut chart con leyenda
- `ROITrendChart.tsx` — Line chart multi-serie con Recharts
- `CampaignComparisonChart.tsx` — Grouped bar chart

#### 2.C.3: i18n
- Agregar keys `roi.*` en `es.json`, `en.json`, `fr.json`:
  - `roi.title`, `roi.total_spend`, `roi.total_revenue`, `roi.cost_per_lead`, `roi.conversion_rate`, `roi.attribution_mix`, `roi.trend`, `roi.top_campaigns`, `roi.first_touch`, `roi.last_touch`, `roi.organic`, `roi.estimated_data_badge`, `roi.real_data_badge`, `roi.no_data`, `roi.period_*`

---

## 3. Criterios de Aceptacion (Gherkin)

### ROI Dashboard

```gherkin
Scenario: Dashboard muestra datos reales de Meta API
  Given un tenant con token Meta configurado y campañas activas
  When el admin abre /roi-dashboard
  Then los KPIs muestran spend real de Meta API
  And el badge dice "Datos reales"
  And el ROI se calcula como ((revenue - spend) / spend) * 100

Scenario: Dashboard muestra datos estimados sin token
  Given un tenant SIN token Meta configurado
  When el admin abre /roi-dashboard
  Then los KPIs muestran estimaciones basadas en consultation_price
  And el badge dice "Datos estimados"
  And el cost_per_lead muestra "N/A"

Scenario: Filtro de período cambia todas las secciones
  Given el admin está en /roi-dashboard
  When selecciona período "Últimos 7 días"
  Then los KPIs, tendencias, mix y top campañas se recalculan para 7d
  And los charts se actualizan sin reload de página

Scenario: Attribution mix refleja distribución real
  Given un tenant con 100 pacientes atribuidos
  When el admin ve el donut chart de Attribution Mix
  Then muestra porcentajes correctos de First Touch, Last Touch, Conversion, Organic
  And todos suman 100%

Scenario: Comparación First vs Last Touch
  Given un tenant con campañas atribuidas con ambos modelos
  When el admin ve el bar chart de comparación
  Then muestra barras agrupadas por campaña
  And cada campaña tiene 2 barras (first touch ROI vs last touch ROI)
```

### RAG System

```gherkin
Scenario: FAQ embeddings se generan al crear FAQ
  Given un admin autenticado en tenant_id=1
  When crea un FAQ con pregunta "Cuánto cuesta una limpieza?" y respuesta "La limpieza dental cuesta $5000"
  Then se genera un embedding en faq_embeddings con faq_id correspondiente
  And el embedding tiene dimensión 1536

Scenario: Búsqueda semántica retorna FAQs relevantes
  Given un tenant con 30 FAQs (más que el límite actual de 20)
  And todas tienen embeddings generados
  When un paciente pregunta "Cuánto sale una limpieza?"
  Then el sistema retorna top-5 FAQs semánticamente similares
  And la FAQ sobre precio de limpieza está en el top-3
  And FAQs sobre "horarios de atención" NO están en el resultado

Scenario: Fallback a FAQs estáticas si pgvector no disponible
  Given un tenant con FAQs pero SIN extensión pgvector
  When un paciente envía un mensaje
  Then el sistema usa el método actual (primeras 20 FAQs estáticas)
  And no genera error

Scenario: Sincronización masiva de embeddings al startup
  Given un tenant con 25 FAQs y 0 embeddings
  When el servicio arranca
  Then se generan 25 embeddings
  And la próxima búsqueda semántica funciona correctamente

Scenario: Tenant isolation en búsqueda semántica
  Given tenant_1 con FAQ "Limpieza: $5000" y tenant_2 con FAQ "Limpieza: $3000"
  When un paciente de tenant_1 pregunta "cuánto cuesta limpieza?"
  Then SOLO recibe la FAQ de tenant_1 ($5000)
  And NUNCA la de tenant_2

Scenario: Nova puede buscar en base de conocimiento
  Given un admin usando Nova en tenant_id=1
  When dice "qué dice nuestra FAQ sobre ortodoncia?"
  Then Nova llama a buscar_en_base_conocimiento(query="ortodoncia", tipo="faq")
  And retorna las FAQs más relevantes sobre ortodoncia
```

---

## 4. Esquema de Datos

### Tablas nuevas

```
faq_embeddings
├── id: SERIAL PK
├── tenant_id: INTEGER FK(tenants) NOT NULL
├── faq_id: INTEGER FK(clinic_faqs) ON DELETE CASCADE UNIQUE
├── content: TEXT NOT NULL
├── embedding: vector(1536) NOT NULL
├── created_at: TIMESTAMPTZ
└── updated_at: TIMESTAMPTZ

document_embeddings (Fase 2)
├── id: SERIAL PK
├── tenant_id: INTEGER FK(tenants) NOT NULL
├── source_type: VARCHAR(50) NOT NULL
├── source_id: INTEGER NOT NULL
├── content: TEXT NOT NULL
├── embedding: vector(1536) NOT NULL
├── metadata: JSONB DEFAULT '{}'
├── created_at: TIMESTAMPTZ
└── UNIQUE(source_type, source_id)
```

### Tabla existente modificada

```
system_config (key-value existente)
+ key: 'MODEL_EMBEDDINGS'     value: 'text-embedding-3-small'
+ key: 'RAG_TOP_K'            value: '5'
+ key: 'RAG_SIMILARITY_THRESHOLD' value: '0.7'
```

### Índices

```sql
-- Búsqueda semántica eficiente
CREATE INDEX idx_faq_embeddings_vector ON faq_embeddings
    USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);

-- Filtro por tenant
CREATE INDEX idx_faq_embeddings_tenant ON faq_embeddings(tenant_id);
CREATE INDEX idx_doc_embeddings_tenant ON document_embeddings(tenant_id);
```

---

## 5. Dependencias

### Python (agregar a `requirements.txt`)
- `pgvector>=0.3.0` — Cliente Python para pgvector
- `openai` — Ya existe, se usa para embeddings

### PostgreSQL
- Extensión `vector` debe estar habilitada. En Render/EasyPanel PostgreSQL 13+ soporta pgvector.
- **Si el hosting no soporta pgvector:** El sistema funciona en modo fallback (FAQs estáticas). No se rompe nada.

### Frontend
- `recharts` — Ya existe en el proyecto para charts.

---

## 6. Riesgos y Mitigacion

| Riesgo | Probabilidad | Impacto | Mitigación |
|--------|-------------|---------|------------|
| pgvector no disponible en hosting | Media | Alto | Fallback automático a FAQs estáticas. Feature flag en system_config. |
| Costos de embeddings OpenAI | Baja | Bajo | text-embedding-3-small es ~$0.02/1M tokens. 100 FAQs = ~$0.001. Negligible. |
| Latencia búsqueda semántica | Baja | Medio | pgvector con ivfflat index < 10ms para 1000 embeddings. Cache Redis opcional. |
| Meta API rate limits para ROI | Media | Medio | Cache 6h en marketing_service. Datos en Redis con TTL. |
| Migración Alembic falla en prod | Baja | Alto | `CREATE EXTENSION IF NOT EXISTS` es idempotente. Tablas usan `IF NOT EXISTS`. |
| Token OpenAI expirado para embeddings | Media | Medio | Usar el mismo `OPENAI_API_KEY` del agente. Si falla → fallback silencioso. |

---

## 7. Checkpoints de Soberania

- [ ] **ROI endpoints:** `WHERE tenant_id = $tenant_id` en TODAS las queries de métricas.
- [ ] **faq_embeddings:** `WHERE tenant_id = $tenant_id` en búsqueda semántica. NUNCA cross-tenant.
- [ ] **document_embeddings:** `WHERE tenant_id = $tenant_id` en todas las queries.
- [ ] **Frontend:** `tenant_id` extraído de JWT vía auth context, nunca de URL params.
- [ ] **Scroll Isolation:** ROI Dashboard usa `h-screen overflow-hidden` + `flex-1 min-h-0 overflow-y-auto`.

---

## 8. Orden de Implementacion

### Fase A — Backend ROI (estimado: ~200 LOC)
1. `metrics_service.py` — Eliminar placeholders, wiring con marketing_service
2. `routes/metrics.py` — Agregar endpoint `/executive-summary`
3. Tests de integración para métricas

### Fase B — RAG Backend (estimado: ~400 LOC)
4. `requirements.txt` — Agregar `pgvector`
5. Alembic migration `007_pgvector_embeddings.py`
6. `models.py` — Clases ORM para embedding tables
7. `services/embedding_service.py` — Servicio completo de embeddings
8. `admin_routes.py` — Hooks en CRUD de FAQs
9. `main.py` — Modificar `_format_faqs()` y `build_system_prompt()`
10. `services/buffer_task.py` — Pasar user_message a la búsqueda semántica
11. `services/nova_tools.py` — Tool `buscar_en_base_conocimiento`
12. `main.py` (startup) — Sync embeddings al arrancar

### Fase C — Frontend ROI Dashboard (estimado: ~500 LOC)
13. `ROIDashboardView.tsx` — Vista principal con 4 secciones
14. Componentes: `KPICard`, `AttributionPieChart`, `ROITrendChart`, `CampaignComparisonChart`
15. `App.tsx` + `Sidebar.tsx` — Ruta y navegación
16. `locales/*.json` — Keys i18n para ROI

### Fase D — Verificación
17. Verificar tenant isolation en embeddings
18. Verificar fallback sin pgvector
19. Verificar ROI con/sin token Meta
20. Audit de drift contra esta spec

---

## 9. Fuera de Alcance (Fase 2)

- Document embeddings para clinical_records y patient_documents (tabla creada pero no usada aún).
- Google Ads spend real en ROI dashboard (actualmente solo Meta).
- Alertas automáticas por ROI bajo.
- Reportes PDF exportables.
- A/B testing de modelos de atribución.
