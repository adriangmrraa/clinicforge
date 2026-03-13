---
name: "Subsystem Documentation Architect"
description: "Genera especificaciones técnicas exhaustivas de subsistemas o funcionalidades específicas del proyecto mediante reverse engineering."
trigger: "documentar funcionalidad, analizar subsistema, spec de feature, reverse engineering, documentar integración, cómo funciona, explicar implementación"
scope: "DOCUMENTATION"
auto-invoke: true
---

# Subsystem Documentation Architect - Platform AI Solutions

## 1. Concepto: Reverse Engineering Documental

### Filosofía
Este skill transforma código existente en **documentación técnica estructurada** mediante un proceso de análisis exhaustivo de:
- **Backend**: Endpoints, lógica de negocio, modelos de datos
- **Frontend**: Componentes UI, gestión de estado, flujos de usuario
- **Database**: Esquemas, relaciones, índices
- **Integraciones**: APIs externas, webhooks, flujos de autenticación

### Diferencia con Spec Architect
- **Spec Architect**: De idea → especificación (diseño hacia adelante)
- **Subsystem Documentation Architect**: De código existente → especificación (reverse engineering)

---

## 2. Metodología de Análisis (The 7-Phase Protocol)

### Fase 1: Identificación de Alcance
**Input del usuario**: Funcionalidad específica a documentar (ej: "Chatwoot integration", "RAG upload flow", "Payment processing")

**Acciones**:
1. Preguntar al usuario por clarificaciones si la funcionalidad no está clara
2. Identificar palabras clave para búsqueda (nombres de tablas, endpoints, componentes)

**Ejemplo**:
```
Usuario: "Documentar carga de archivos vectoriales para RAG"
Keywords: rag, upload, vectorization, embeddings, documents
```

---

### Fase 2: Exploración de Documentación Existente

**Directorios a revisar**:
- `docs/` → Buscar guías relacionadas
- `.agent/skills/` → Buscar skills relacionadas
- `README.md` → Contexto general

**Herramientas**:
```bash
grep_search query="rag upload" path="docs/"
find_by_name pattern="*rag*" directory=".agent/skills/"
```

**Output**: Lista de archivos relevantes para contexto inicial

---

### Fase 3: Análisis de Backend

**Objetivos**:
- Identificar endpoints de API relacionados
- Analizar modelos de datos (Pydantic, SQLAlchemy)
- Mapear flujo de procesamiento

**Archivos típicos**:
- `orchestrator_service/admin_routes.py` → Endpoints
- `orchestrator_service/app/models/*.py` → Modelos ORM
- `*_service/main.py` → Microservicios especializados

**Patrón de análisis**:
1. Buscar endpoints con `grep_search query="/api/rag" path="orchestrator_service/"`
2. Ver modelos con `view_code_item` de las clases detectadas
3. Seguir imports para entender dependencias

**Información a extraer**:
- Request/Response schemas
- Validaciones de negocio
- Llamadas a servicios externos
- Manejo de errores

---

### Fase 4: Análisis de Database

**Objetivos**:
- Identificar tablas involucradas
- Documentar relaciones y constraints
- Capturar índices y triggers

**Archivos a revisar**:
- `orchestrator_service/app/models/*.py` → Modelos SQLAlchemy
- `db/migrations/*.sql` → Migraciones (si existen)
- Scripts en `scripts/*.sql`

**Patrón de análisis**:
```python
# Buscar modelos con nombre relacionado
grep_search query="class.*Document.*Base" path="orchestrator_service/app/models/"
view_code_item file="app/models/rag.py" nodes=["Document", "DocumentChunk"]
```

**Output**: 
- Definición SQL de tablas
- Diagramas ER (Mermaid)
- Índices y constraints

---

### Fase 5: Análisis de Frontend

**Objetivos**:
- Identificar componentes UI relacionados
- Analizar estados y hooks
- Mapear flujo de usuario

**Archivos típicos**:
- `frontend_react/src/views/*.tsx` → Vistas principales
- `frontend_react/src/components/*.tsx` → Componentes reutilizables
- `frontend_react/src/hooks/*.ts` → Custom hooks

**Patrón de análisis**:
```typescript
// Buscar componentes
find_by_name pattern="*Upload*.tsx" directory="frontend_react/src/"
view_file path="frontend_react/src/views/RAGUpload.tsx"
```

**Información a extraer**:
- Estados de React (useState, useEffect)
- Llamadas a API (endpoints)
- Validaciones de formulario
- Manejo de archivos (FileReader, FormData)

---

### Fase 6: Análisis de Integraciones

**Objetivos**:
- Identificar APIs externas
- Documentar flujo de autenticación
- Mapear webhooks (entrada/salida)

**Archivos típicos**:
- `*_service/*_client.py` → Clientes HTTP
- `orchestrator_service/admin_routes.py` → Webhook receivers
- `app/core/credentials.py` → Gestión de tokens

**Patrones comunes**:
- OAuth flows
- Webhook signature validation
- API rate limiting
- Credential rotation

---

### Fase 7: Síntesis y Generación del Documento

**Output**: Archivo `.spec.md` en `docs/specs/[subsystem_name].spec.md`

**Estructura obligatoria**:

```markdown
# Especificación Técnica: [Nombre del Subsistema]

## 📋 Información del Documento
- **Versión**: 1.0
- **Fecha**: [Auto]
- **Sistema**: Platform AI Solutions
- **Alcance**: [Descripción breve]

## 🎯 Objetivos de Negocio
### Propósito Principal
[Qué problema resuelve]

### Diferenciador Clave
[Por qué se implementó de esta forma]

## 🏗️ Arquitectura de Integración
### Flujo de Datos End-to-End
[Diagrama Mermaid secuenceDiagram]

### Componentes Clave
[Lista de servicios, archivos, funciones principales]

## 💾 Modelos de Datos (Database)
### Tabla: [nombre_tabla]
[SQL CREATE TABLE con comentarios]

### Relaciones
[Diagrama ER en Mermaid]

## 🔌 Endpoints de API
### [Método] /ruta/endpoint
**Query Parameters**: ...
**Request Body**: [JSON Schema]
**Response**: [JSON Schema]
**Lógica de Procesamiento**: [Paso a paso]

## 🎨 Frontend: Vista [ComponentName]
### Arquitectura de Estado
[TypeScript interfaces]

### Polling/WebSocket Strategy
[Si aplica]

### Indicadores Visuales
[Estilos, colores, iconos]

## 🔄 Procesos de Negocio (Gherkin)
[Mínimo 3 escenarios en formato Given/When/Then]

## 🛠️ Configuración Multi-Tenant
[Pasos de setup si aplica]

## 📊 Diagramas de Arquitectura
[Mermaid graph TB de componentes]
[Mermaid stateDiagram-v2 de estados si aplica]

## 🔐 Seguridad y Aislamiento Multi-Tenant
[Principios de soberanía específicos]

## 🐛 Troubleshooting
### Problema 1: [Descripción]
**Diagnóstico**: [Queries SQL o logs a revisar]
**Causas comunes**: ...
**Solución**: ...

## 📈 Métricas y Monitoreo
[Logs clave, KPIs a trackear]

## 🚀 Roadmap de Mejoras
[Corto/Mediano/Largo plazo]

## 📚 Referencias
### Documentación Interna
[Links a otros docs]
### Código Fuente
[Links con file:// y line numbers]
### API Externa
[Links a docs externas si aplica]
```

---

## 3. Herramientas de Análisis

### Búsqueda de Código
```python
# Buscar implementaciones
grep_search(query="def upload_document", path="orchestrator_service/", match_per_line=True)

# Buscar configuraciones
grep_search(query="VECTORIZATION", path=".", includes=["*.env.example", "*.py"])
```

### Visualización de Estructura
```python
# Outline de archivo
view_file_outline("orchestrator_service/app/api/rag.py")

# Ver función específica
view_code_item(file="app/api/rag.py", nodes=["upload_document", "process_embeddings"])
```

### Análisis de Dependencias
```python
# Ver imports
view_file(path="app/core/rag.py", start_line=1, end_line=50)

# Buscar uso de una función
grep_search(query="RAGCore.ingest", path="orchestrator_service/")
```

---

## 4. Casos de Uso Reales

### Ejemplo 1: "Documentar carga de archivos RAG"

**Fase 1 - Identificación**:
- Keywords: `rag`, `upload`, `document`, `embeddings`, `vectorization`

**Fase 2 - Documentación existente**:
```bash
find_by_name pattern="*rag*" directory="docs/"
# → docs/RAG_ARCHITECTURE.md
view_file path="docs/RAG_ARCHITECTURE.md"
```

**Fase 3 - Backend**:
```python
grep_search query="/rag/upload" path="orchestrator_service/"
# → admin_routes.py:1234
view_file path="orchestrator_service/admin_routes.py" start=1234 end=1300
```

**Fase 4 - Database**:
```python
view_code_item file="app/models/rag.py" nodes=["Document", "DocumentChunk"]
```

**Fase 5 - Frontend**:
```python
find_by_name pattern="*RAG*.tsx" directory="frontend_react/src/views/"
view_file path="frontend_react/src/views/RAG.tsx"
```

**Fase 6 - Integraciones**:
```python
grep_search query="OpenAI.*embed" path="orchestrator_service/"
# → Encontrar llamadas a OpenAI Embeddings API
```

**Fase 7 - Generación**:
```markdown
Crear: docs/specs/rag_upload_flow.spec.md
Contenido: [Siguiendo template completo]
```

---

### Ejemplo 2: "Documentar integración con Tienda Nube"

**Proceso similar**:
1. Keywords: `tiendanube`, `oauth`, `products`, `sync`
2. Skill relevante: `TiendaNube_Commerce_Bridge`
3. Backend: `tiendanube_service/main.py`
4. Database: `products`, `orders` tables
5. Frontend: `TiendaNubeSettings.tsx`
6. OAuth flow analysis
7. Spec generada: `tiendanube_integration.spec.md`

---

## 5. Checklist de Calidad

Antes de entregar la especificación, verificar:

- [ ] **Completitud**:
  - [ ] Todos los endpoints documentados
  - [ ] Todos los modelos de DB incluidos
  - [ ] Frontend UI explicado
  - [ ] Flujo end-to-end claro

- [ ] **Diagramas**:
  - [ ] Mínimo 1 secuenceDiagram
  - [ ] Mínimo 1 graph TB de componentes
  - [ ] stateDiagram si hay estados (conversaciones, órdenes, etc.)

- [ ] **Código Verificado**:
  - [ ] Snippets de código son del proyecto real (no inventados)
  - [ ] SQL schemas corresponden a modelos actuales
  - [ ] TypeScript interfaces son correctas

- [ ] **Troubleshooting**:
  - [ ] Mínimo 3 problemas comunes documentados
  - [ ] Queries SQL para diagnóstico incluidas

- [ ] **Referencias**:
  - [ ] Links a código con `file://` y line numbers
  - [ ] Links a skills relacionadas
  - [ ] Links a docs externas si aplica

---

## 6. Anti-Patrones (Qué NO hacer)

### ❌ Especulación sin Código
```markdown
# MAL
"Probablemente se usa Redis para caché"

# BIEN
"Se usa Redis para caché (ver orchestrator_service/main.py:234)"
```

### ❌ Diagramas Vagos
```mermaid
# MAL
graph LR
  A[Frontend] --> B[Backend]
  
# BIEN  
graph TB
    UI[Chats.tsx] -->|GET /chats/summary| API[admin_routes.py:5100]
    API --> DB[(chat_conversations)]
```

### ❌ JSON Schemas Inventados
```typescript
// MAL (inventado)
interface Message {
  text: string;
}

// BIEN (extraído de código real)
interface Message {  // Ver frontend_react/src/views/Chats.tsx:27
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: string;
  attachments?: Attachment[];
}
```

---

## 7. Integración con Workflows

### Uso desde `/specify`
Si el usuario invoca `/specify` sobre un subsistema existente (no una feature nueva):
1. Detectar que el código ya existe
2. Invocar **Subsystem Documentation Architect** en lugar de Spec Architect
3. Generar spec mediante reverse engineering

### Uso independiente
```
Usuario: "Quiero entender cómo funciona el sistema de pagos"
Antigravity: [Invoca Subsystem Documentation Architect]
              [Analiza payment_service/, Stripe integration, etc.]
              [Genera docs/specs/payment_processing.spec.md]
```

---

## 8. Troubleshooting de la Skill

### "La spec está incompleta"
**Causa**: No se encontraron todos los archivos relevantes  
**Solución**: Ampliar keywords de búsqueda, revisar imports manualmente

### "Los diagramas no compilan"
**Causa**: Sintaxis Mermaid incorrecta  
**Solución**: Validar con [Mermaid Live Editor](https://mermaid.live/)

### "El código en la spec no coincide con el real"
**Causa**: Se copió un snippet antiguo o de otro proyecto  
**Solución**: Siempre usar `view_file` y copiar literalmente, agregar links `file://`

---

## 9. Output Final

Al terminar, siempre:

1. **Copiar archivo a proyecto**:
   ```bash
   Copy-Item "artifacts/[subsystem].spec.md" -Destination "docs/specs/"
   ```

2. **Notificar al usuario**:
   ```
   ✅ Especificación técnica generada:
   📄 docs/specs/[subsystem].spec.md
   
   Contenido:
   - Arquitectura completa con diagramas
   - Modelos de datos (SQL + interfaces)
   - Endpoints documentados
   - Flujo end-to-end
   - Troubleshooting guide
   ```

3. **Sugerir próximos pasos** (opcional):
   - "¿Quieres que documente otro subsistema?"
   - "¿Necesitas expandir alguna sección específica?"

---

## 10. Ejemplos de Prompts que Activan la Skill

- ✅ "Documentar cómo funciona la integración con Chatwoot"
- ✅ "Explicar el flujo de carga de archivos vectoriales"
- ✅ "Quiero una spec técnica de cómo se gestionan los pagos"
- ✅ "Analiza cómo está implementado el sistema de agentes de IA"
- ✅ "Reverse engineering de la funcionalidad de templates HSM"

---

**Nota Final**: Esta skill es especialmente útil cuando un nuevo desarrollador se une al equipo y necesita entender subsistemas complejos sin leer miles de líneas de código.
