---
description: Genera una especificación técnica (.spec.md) rigurosa a partir de requerimientos vagos, usando análisis de 3 pilares.
---

# 📝 Specify Workflow — ClinicForge (SDD v2.0)

Transforma requerimientos vagos en una especificación técnica rigurosa antes de escribir una sola línea de código.

## Stack de Referencia (ClinicForge)
- **Backend:** FastAPI + LangChain + asyncpg (`orchestrator_service/`)
  - Core: `main.py` (agent tools, POST /chat), `admin_routes.py` (/admin/*), `auth_routes.py`
  - Servicios: `services/buffer_task.py`, `services/relay.py`, `chatwoot_client.py`, `gcal_service.py`
- **BFF Service:** Express proxy (`bff_service/`) — Frontend → BFF :3000 → Orchestrator :8000
- **Frontend:** React 18 + TypeScript + Vite + Tailwind (`frontend_react/src/`)
  - Vistas: `views/` | Componentes: `components/` | i18n: `locales/es.json`, `en.json`, `fr.json`
- **DB:** PostgreSQL — cambios vía migraciones Alembic en `orchestrator_service/alembic/versions/`
- **ORM:** SQLAlchemy models en `orchestrator_service/models.py`
- **Infra:** Docker Compose / EasyPanel

## Pasos

### 1. Análisis de 3 Pilares (Obligatorio)
Antes de generar la spec, evaluar:
- **Ciencia:** ¿Es técnicamente posible con el stack actual? ¿Requiere nueva dependencia?
- **Mercado:** ¿Resuelve un pain point real de la Dra. Delgado / sus pacientes / su equipo?
- **Soberanía:** ¿Toda query nueva filtra por `tenant_id`? ¿El JWT valida el rol?

### 2. Entrevista Técnica (si hay ambigüedades → ejecutar `/clarify` primero)
- **Entradas:** ¿Qué datos entran? (paciente, turno, anamnesis, webhook, etc.)
- **Salidas:** ¿Qué produce el feature? (respuesta WhatsApp, evento GCal, registro en BD, UI update)
- **Persistencia:** ¿Hay cambio de esquema? → definir tabla/columna/tipo
- **Permisos:** ¿Qué roles pueden usar esto? (CEO / profesional / secretaria / bot)

### 3. Generación del `.spec.md`
Guardar en `specs/YYYY-MM-DD_nombre-feature.spec.md` siguiendo la **Plantilla Maestra SDD v2.0**:

```markdown
# [Nombre del Feature]
> Origen: [issue / conversación / audit]

## 1. Contexto y Objetivos
- **Problema:** [Descripción del dolor]
- **Solución:** [Descripción de la funcionalidad]
- **KPIs:** [Cómo medimos el éxito]

## 2. Esquemas de Datos
- **Entradas:** [Interface TS o descripción JSON]
- **Salidas:** [Interface TS o descripción JSON]
- **Persistencia:** [Tabla, columna, tipo — o "sin cambios en BD"]

## 3. Lógica de Negocio (Invariantes)
- SI [Condición A] ENTONCES [Resultado B]
- RESTRICCIÓN: [Regla de seguridad o negocio inviolable]
- SOBERANÍA: [Cómo se garantiza el aislamiento multi-tenant]

## 4. Stack y Restricciones
- **Backend:** [Archivos exactos + líneas de referencia si aplica]
- **Frontend:** [Componentes o vistas afectadas]
- **API:** [Endpoints nuevos o modificados — método, ruta, auth requerida]
- **DB:** [Migración Alembic si aplica — actualizar también models.py]

## 5. Criterios de Aceptación (Gherkin)
- **Escenario N:**
  - DADO que [Precondición]
  - CUANDO [Acción]
  - ENTONCES [Resultado esperado]

## 6. Archivos Afectados
| Archivo | Tipo | Cambio |
|---|---|---|
| `orchestrator_service/main.py` | MODIFY | ... |

## 7. Casos Borde y Riesgos
| Riesgo | Mitigación |
|---|---|
| ... | ... |
```

### 4. Checkpoints de Soberanía (No-Negociables)
- **Backend SQL:** Toda query nueva incluye `WHERE tenant_id = $x`
- **Frontend:** Scroll Isolation — contenedor padre `h-screen overflow-hidden`, área de contenido `flex-1 min-h-0 overflow-y-auto`
- **Nuevos endpoints:** Validation por JWT + `X-Admin-Token`; `tenant_id` desde JWT, nunca desde query params
- **Cambios de DB:** Migraciones Alembic en `orchestrator_service/alembic/versions/` con `upgrade()` y `downgrade()`. Actualizar `models.py`.
- **Texto visible:** Usar `t('namespace.key')` con keys en `es.json`, `en.json` y `fr.json`

### 5. REGLA DE ORO DE EJECUCIÓN
- NO ejecutar SQL (`psql`) directamente. Proporcionar el comando al usuario y esperar sus resultados.
- NO escribir código sin `.spec.md` aprobado.
- Si la spec cambia durante implementación, actualizarla primero y el código después.
