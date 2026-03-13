---
description: Genera especificación técnica completa de un subsistema existente mediante reverse engineering (Backend, Frontend, DB, Diagramas).
---

# 📚 Antigravity Document

Transforma código existente en documentación técnica exhaustiva tipo "Chatwoot Integration Spec".

## Objetivo

Este workflow orquesta el análisis de subsistemas ya implementados para generar especificaciones técnicas que sirvan como:
- **Onboarding** para nuevos desarrolladores
- **Referencia arquitectónica** para el equipo
- **Base de conocimiento** para futuras modificaciones

---

## Pasos del Workflow

### 1. 🎯 Identificación del Subsistema

**Pregunta al usuario**:
- "¿Qué funcionalidad o subsistema quieres documentar?"
- Ejemplos: "Carga de archivos RAG", "Sistema de pagos", "OAuth Meta", "Templates HSM"

**Output esperado**: Nombre claro del subsistema a analizar.

---

### 2. 🔍 Búsqueda de Contexto Inicial

**Acciones automáticas**:
```bash
# Buscar documentación existente
grep_search query="[subsystem_keywords]" path="docs/"
find_by_name pattern="*[subsystem]*" directory=".agent/skills/"
```

**Objetivo**: Identificar si ya existe documentación parcial o skills relacionadas que proporcionen contexto.

**Entregable**: Lista de archivos relevantes encontrados (máximo 5).

---

### 3. 🧠 Activación de Skill Especializada

**Invocación obligatoria**:
```
Activar: @Subsystem_Documentation_Architect

Instrucciones:
- Aplicar metodología de 7 fases
- Priorizar análisis de Backend → Database → Frontend → Integraciones
- Generar diagramas Mermaid (mínimo 2)
- Incluir troubleshooting (mínimo 3 problemas comunes)
```

**Advertencia**: NO continuar sin haber invocado explícitamente esta skill.

---

### 4. 📊 Fase de Análisis Profundo

**Backend (Obligatorio)**:
- [ ] Identificar endpoints relacionados (`grep_search` en `*_service/`)
- [ ] Listar modelos de datos implicados (`view_code_item` en `app/models/`)
- [ ] Mapear flujo de procesamiento (seguir imports)
- [ ] Extraer Request/Response schemas

**Database (Obligatorio)**:
- [ ] Ver definiciones de tablas en modelos SQLAlchemy
- [ ] Generar SQL CREATE TABLE con comentarios
- [ ] Crear diagrama ER (Mermaid)

**Frontend (Si aplica)**:
- [ ] Buscar componentes relacionados (`find_by_name` en `frontend_react/src/`)
- [ ] Analizar estados React (useState, useEffect)
- [ ] Documentar llamadas a API
- [ ] Capturar validaciones de formulario

**Integraciones (Si aplica)**:
- [ ] Identificar clientes HTTP (`*_client.py`)
- [ ] Documentar flujo OAuth (si existe)
- [ ] Analizar webhooks (entrada/salida)
- [ ] Extraer gestión de credenciales

---

### 5. 📝 Generación del Documento

**Crear archivo**: `docs/specs/[subsystem_name].spec.md`

**Estructura obligatoria** (usar template de la skill):
```markdown
# Especificación Técnica: [Nombre]

## 📋 Información del Documento
## 🎯 Objetivos de Negocio
## 🏗️ Arquitectura de Integración
### Flujo de Datos End-to-End (Mermaid sequenceDiagram)
### Componentes Clave

## 💾 Modelos de Datos (Database)
### Tabla: [nombre] (SQL completo)

## 🔌 Endpoints de API
### [GET/POST] /ruta
- Query Parameters
- Request Body (JSON Schema)
- Response (JSON Schema)
- Lógica de Procesamiento

## 🎨 Frontend: Vista [Component]
### Arquitectura de Estado (TypeScript interfaces)

## 🔄 Procesos de Negocio (Gherkin)
### Escenario 1: [Nombre]
Given [precondición]
When [acción]
Then [resultado]

## 📊 Diagramas de Arquitectura
### Diagrama de Componentes (Mermaid graph TB)
### Diagrama de Estados (Mermaid stateDiagram-v2)

## 🔐 Seguridad y Aislamiento Multi-Tenant

## 🐛 Troubleshooting
### Problema 1: [Descripción]
- **Diagnóstico**: ...
- **Causas comunes**: ...
- **Solución**: ...

## 📈 Métricas y Monitoreo

## 🚀 Roadmap de Mejoras

## 📚 Referencias
- Documentación Interna (links)
- Código Fuente (file:// con line numbers)
- API Externa (links)
```

**Validación antes de continuar**:
- [ ] Todos los snippets de código son del proyecto real (no inventados)
- [ ] Los SQL schemas corresponden a modelos actuales
- [ ] Las TypeScript interfaces son correctas
- [ ] Mínimo 2 diagramas Mermaid incluidos
- [ ] Mínimo 3 escenarios Gherkin documentados

---

### 6. 📁 Copia al Proyecto Real

**Comando obligatorio**:
```powershell
Copy-Item "artifacts/[subsystem].spec.md" -Destination "docs/specs/[subsystem].spec.md"
```

**Verificación**:
```powershell
Test-Path "docs/specs/[subsystem].spec.md"
```

---

### 7. ✅ Entrega y Cierre

**Notificar al usuario**:
```
✅ Especificación técnica generada exitosamente!

📄 Ubicación: docs/specs/[subsystem].spec.md

📊 Contenido:
- Arquitectura completa con [N] diagramas Mermaid
- [N] endpoints de API documentados
- [N] tablas de base de datos con SQL
- [N] escenarios de negocio en Gherkin
- Sección de troubleshooting con [N] problemas comunes
- [N] referencias a código fuente

🎯 Próximos pasos sugeridos:
- Compartir con el equipo para validación
- Agregar al onboarding de nuevos devs
- Actualizar si el subsistema evoluciona
```

**Preguntar** (opcional):
- "¿Quieres documentar otro subsistema?"
- "¿Necesitas expandir alguna sección específica?"

---

## 🚫 Anti-Patrones (Qué NO hacer)

❌ **Especulación sin código**:
```markdown
# MAL
"Probablemente se usa Redis para caché"

# BIEN
"Se usa Redis para caché en linha 234 de main.py"
```

❌ **Diagramas vagos**:
```mermaid
# MAL
graph LR
  A[Frontend] --> B[Backend]
  
# BIEN  
graph TB
    UI[RAGUpload.tsx] -->|POST /rag/upload| API[admin_routes.py:1234]
    API --> VS[VectorStore.ingest]
    VS --> DB[(Supabase pgvector)]
```

❌ **Saltar la skill**:
- **PROHIBIDO** hacer análisis manual sin invocar `@Subsystem_Documentation_Architect`
- La skill garantiza metodología consistente

---

## 📋 Checklist de Calidad Final

Antes de notificar al usuario, verificar:

- [ ] **Skill invocada**: `@Subsystem_Documentation_Architect` fue activada explícitamente
- [ ] **Completitud**:
  - [ ] Backend: Endpoints + lógica de negocio
  - [ ] Database: Tablas + relaciones + SQL completo
  - [ ] Frontend: Componentes + estados + flujo UI (si aplica)
  - [ ] Integraciones: APIs externas + webhooks (si aplica)
- [ ] **Diagramas**:
  - [ ] Mínimo 1 `sequenceDiagram` (flujo end-to-end)
  - [ ] Mínimo 1 `graph TB` (componentes)
  - [ ] `stateDiagram-v2` si hay estados (opcional)
- [ ] **Código verificado**:
  - [ ] Snippets son reales (no inventados)
  - [ ] SQL schemas corresponden a modelos actuales
  - [ ] TypeScript interfaces son correctas
  - [ ] Links `file://` con line numbers incluidos
- [ ] **Troubleshooting**:
  - [ ] Mínimo 3 problemas comunes documentados
  - [ ] Queries SQL o comandos de diagnóstico incluidos
- [ ] **Referencias**:
  - [ ] Links a skills relacionadas
  - [ ] Links a docs internas
  - [ ] Links a APIs externas (si aplica)
- [ ] **Archivo copiado**: `.spec.md` está en `docs/specs/` (no solo en artifacts)

---

## 🎯 Ejemplos de Uso

### Ejemplo 1: Usuario pide documentar RAG
```
Usuario: /document
Antigravity: ¿Qué subsistema quieres documentar?
Usuario: Sistema de carga de archivos RAG
Antigravity: 
[Invoca @Subsystem_Documentation_Architect]
[Analiza orchestrator_service/app/api/rag.py]
[Analiza frontend_react/src/views/RAG.tsx]
[Genera diagramas]
[Crea docs/specs/rag_upload_flow.spec.md]

✅ Especificación generada: docs/specs/rag_upload_flow.spec.md
```

### Ejemplo 2: Usuario pide documentar integración
```
Usuario: Necesito entender cómo funciona la integración con Tienda Nube
Antigravity: 
[Detecta keywords: "tiendanube", "integración"]
[Auto-invoca workflow /document]
[Activa @Subsystem_Documentation_Architect]
[Analiza tiendanube_service/main.py]
[Documenta OAuth flow]
[Genera docs/specs/tiendanube_integration.spec.md]
```

---

## 🔗 Relación con otros Workflows

- **`/specify`**: Para features NUEVAS (diseño hacia adelante)
- **`/document`**: Para features EXISTENTES (reverse engineering)
- **`/plan`**: Usa la spec generada para crear plan de mejoras
- **`/implement`**: Ejecuta cambios basados en la spec actualizada

---

## 🛠️ Troubleshooting del Workflow

### "La spec está incompleta"
**Causa**: No se siguieron todas las fases de análisis  
**Solución**: Revisar checklist de calidad, ampliar keywords de búsqueda

### "Los diagramas Mermaid no compilan"
**Causa**: Sintaxis incorrecta  
**Solución**: Validar en [Mermaid Live Editor](https://mermaid.live/)

### "El código no coincide con el actual"
**Causa**: Se copió snippet antiguo o de otro proyecto  
**Solución**: Siempre usar `view_file` literalmente, agregar links `file://`

---

**Nota final**: Este workflow garantiza que SIEMPRE se genere documentación con el mismo nivel de detalle que `chatwoot_integration.spec.md` (tu nuevo estándar de calidad).
