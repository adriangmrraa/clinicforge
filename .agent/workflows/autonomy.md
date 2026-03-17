---
description: Motor de Ejecución Autónoma SDD v2.0. Orquestación completa desde análisis hasta deployment.
---

# ⚡ Antigravity Autonomy Engine — ClinicForge

**Constitución del Motor de Ejecución Autónoma**  
Este workflow es la capa superior de orquestación que integra todo el ecosistema SDD v2.0 en un flujo de ejecución inteligente, autónomo y con checkpoints de calidad.

## Stack Canónico de Referencia (ClinicForge)
| Capa | Tecnología | Ubicación |
|------|------------|-----------|
| Backend (orquestador) | FastAPI + LangChain + asyncpg + Socket.IO | `orchestrator_service/` |
| Agent tools + System Prompt | LangChain tools, `build_system_prompt()` | `orchestrator_service/main.py` |
| Admin API | FastAPI routes | `orchestrator_service/admin_routes.py` |
| DB Migrations | Alembic (migraciones versionadas en startup) | `orchestrator_service/alembic/` |
| BFF Service | Express proxy (Frontend → Orchestrator) | `bff_service/` |
| Mensaje buffer + relay | Buffer 10s texto, 20s imagen | `services/buffer_task.py`, `services/relay.py` |
| Frontend | React 18 + TypeScript + Vite + Tailwind | `frontend_react/src/` |
| i18n | es/en/fr | `frontend_react/src/locales/*.json` |
| Infra | Docker Compose / EasyPanel | `docker-compose.yml` |

---

## 🎯 Filosofía Core

El Motor de Autonomía transforma solicitudes vagas en software funcional siguiendo estas leyes inviolables:

1. **Spec-First, Code-Never-First**: Ninguna línea de código sin `.spec.md` validado.
2. **Confidence Gatekeeper**: El umbral de confianza técnica es la frontera entre planear y ejecutar.
3. **Sovereign Architecture**: Multi-tenancy (`tenant_id`) y Scroll Isolation (`min-h-0`) son requisitos no negociables.
4. **Non-Destructive Evolution**: Toda modificación preserva la lógica existente mediante fusión, nunca reemplazo.
5. **SQL Execution Restriction**: NO ejecutar comandos SQL (`psql`) directamente en el entorno local. Proporcionar los comandos al usuario y que él devuelva el resultado.

---

## 🚀 Fases del Motor

### **Fase 1: Scaffolding (Preparación del Contexto)**

**Objetivo:** Estructurar el entorno de trabajo y activar las capacidades necesarias.

#### Paso 1.1: Inicializar Proyecto
```bash
/newproject
```
- Crea estructura de directorios `.agent/`, `docs/`, `skills/`
- Vincula workflows globales
- Genera memoria del proyecto

#### Paso 1.2: Nutrición de Skills
```bash
# Lee automáticamente todas las skills disponibles en .agent/skills/
```
**Skills Críticas Verificadas:**
- ✅ **Sovereign Backend Engineer**: Multi-tenancy, JIT logic, Alembic migrations, BFF service
- ✅ **Nexus UI Architect**: Scroll Isolation, Mobile-First, DKG (Design Knowledge Graph)
- ✅ **DB Schema Surgeon**: Evolución segura de esquemas, JSONB clínico
- ✅ **Spec Architect**: Generación y validación de `.spec.md`
- ✅ **Deep Researcher**: Validación en documentación oficial antes de implementar

**Recordatorio Arquitectónico:**
> Toda skill debe respetar:
> - **Soberanía de Datos**: Filtrado explícito `WHERE tenant_id = $x` en TODAS las queries.
> - **Aislamiento de Scroll**: Contenedor principal `h-screen overflow-hidden`, área de contenido `flex-1 min-h-0 overflow-y-auto`.

---

### **Fase 2: Análisis y Especificación (SSOT Generation)**

**Objetivo:** Transformar requerimientos vagos en especificaciones técnicas rigurosas.

#### Paso 2.1: Validación de 3 Pilares
```bash
/advisor
```
**Análisis Obligatorio:**
- **Ciencia**: ¿Es técnicamente posible con el stack actual?
- **Mercado**: ¿Resuelve un pain point real del usuario dental?
- **Comunidad**: ¿Hay precedentes/patrones documentados?

**Salida:** Score de viabilidad (0-100). Si < 60, **STOP** y ejecutar `/clarify`.

#### Paso 2.2: Generación de SSOT
```bash
/specify
```
**El Advisor alimenta directamente al Spec Architect.**

**Estructura del `.spec.md`:**
1. **Contexto y Objetivos**: ¿Qué problema resuelve?
2. **Requerimientos Técnicos**: Backend, Frontend, UI/UX
3. **Criterios de Aceptación (Gherkin)**: Scenarios con Given/When/Then
4. **Esquema de Datos**: Tablas, columnas, tipos, constraints
5. **Riesgos y Mitigación**: Latencia, tokens expirados, race conditions

**Recordatorio Arquitectónico:**
> El `.spec.md` debe incluir:
> - **Checkpoint de Soberanía**: "Validar que el `tenant_id` se extraiga de JWT y no de parámetro de URL."
> - **Checkpoint de UI**: "Aplicar patrón de Scroll Isolation: `overflow-hidden` en contenedor padre, `min-h-0` en área de contenido."

#### Paso 2.3: Ronda de Clarificación (Opcional)
```bash
/clarify
```
Si el Advisor detecta ambigüedades o el spec tiene lagunas de lógica, el agente debe ejecutar una ronda de preguntas técnicas antes de proceder.

---

### **Fase 3: Planificación y Gatekeeper**

**Objetivo:** Diseñar la arquitectura técnica y validar la confianza de ejecución.

#### Paso 3.1: Generación del Plan Técnico
```bash
/plan
```
**Entrada:** `.spec.md` validado  
**Salida:** `implementation_plan.md`

**Secciones del Plan:**
1. **Goal Description**: Resumen del problema
2. **User Review Required**: Breaking changes, decisiones críticas
3. **Proposed Changes**: Agrupados por componente (Backend, Frontend, DB)
4. **Verification Plan**: Tests automatizados y verificación manual

**Recordatorio Arquitectónico:**
> En la sección "Proposed Changes", SIEMPRE incluir:
> - **Backend**: "Agregar filtro `WHERE tenant_id = $tenant_id` en la query SQL."
> - **Frontend**: "Aplicar Scroll Isolation en `Layout.tsx` con clases `h-screen overflow-hidden` y `flex-1 min-h-0 overflow-y-auto`."

#### Paso 3.2: Technical Gate (Umbral de Confianza)
```bash
/gate
```
**Evaluación de Confianza Técnica (0-100%):**
- **Spec Completeness**: ¿Todos los acceptance criteria son verificables?
- **Architecture Alignment**: ¿Respeta Soberanía y Scroll Isolation?
- **Skill Coverage**: ¿Tenemos las skills necesarias?
- **Risk Score**: ¿Los riesgos están mitigados?

**Decisión:**
- **Confianza ≥ 90%**: Proceder a `/implement` automáticamente.
- **70% ≤ Confianza < 90%**: Solicitar revisión del plan al usuario.
- **Confianza < 70%**: **STOP** y ejecutar `/clarify` o `/review`.

---

### **Fase 4: Implementación Disciplinada**

**Objetivo:** Escribir código siguiendo el plan aprobado con checkpoints de calidad.

#### Paso 4.1: Ejecución del Plan
```bash
/implement
```
**Modo de Ejecución:**
- Lee `implementation_plan.md`
- Ejecuta cambios en el orden especificado (dependencies first)
- Marca items en `task.md` como `[/]` (in-progress) y `[x]` (completed)

**Checkpoints Obligatorios Durante Implementación:**
1. **Antes de modificar queries SQL**: Verificar presencia de `tenant_id`
2. **Antes de editar Layout/UI**: Verificar que se preserva Scroll Isolation
3. **Antes de crear endpoints**: Validar que el contexto tenant viene del JWT

**Regla de Oro:**
> Si durante la implementación se detecta que el plan es incompleto o tiene errores, retroceder a Fase 3 (PLANNING) y actualizar `implementation_plan.md`. **NO** improvisar código sin actualizar el plan.

#### Paso 4.2: Desglose en Tasks (Opcional para Planes Masivos)
```bash
/tasks
```
Si la complejidad es alta (>10 archivos modificados), descomponer el plan en tickets individuales.

---

### **Fase 5: Validación y Corrección Autónoma**

**Objetivo:** Verificar que el código funciona y cumple con la especificación.

#### Paso 5.1: Auto-Verificación
```bash
/verify
```
**Ciclo de Verificación:**
1. Ejecutar tests automatizados (pytest, vitest)
2. Si hay fallos, intentar auto-corrección
3. Repetir hasta que los tests pasen o se alcance el límite de intentos (3x)

**Salida:**
- ✅ **Tests Passing**: Proceder a `/audit`
- ⚠️ **Tests Failing**: Retroceder a EXECUTION y corregir

#### Paso 5.2: Auditoría de Drift
```bash
/audit
```
**Comparativa:** `.spec.md` (SSOT) vs. Código Implementado

**Detecta:**
- ¿Se implementaron todos los Criterios de Aceptación?
- ¿Se respetaron los Esquemas de Datos?
- ¿Hay lógica extra no pedida? (Spec Drift)

**Salida:**
- ✅ **Match Total**: Proceder a `/review`
- ⚠️ **Drift Detectado**: Crear task de corrección inmediata

#### Paso 5.3: Revisión de Calidad
```bash
/review
```
**Perspectivas analizadas:**
1. **Seguridad**: ¿Hay vulnerabilidades? ¿Se valida input del usuario?
2. **Performance**: ¿Queries optimizadas? ¿Índices necesarios?
3. **Clean Code**: ¿Nombres descriptivos? ¿Funciones cortas?

---

### **Fase 6: Finalización y Registro**

**Objetivo:** Sincronizar con GitHub, documentar resultados y limpiar entorno.

#### Paso 6.1: Sync con GitHub
```bash
/push
```
- Crea repositorio privado si no existe
- Ejecuta `git add .`, `git commit`, `git push`
- Genera mensaje de commit descriptivo basado en `walkthrough.md`

#### Paso 6.2: Cierre del Sprint
```bash
/finish
```
**Acciones:**
1. Generar `walkthrough.md` con screenshots/recordings de pruebas
2. Archivar logs de la sesión
3. Actualizar memoria global del proyecto
4. Limpiar archivos temporales

---

## 🛡️ Blindajes Arquitectónicos (Non-Negotiable)

### 1. Soberanía de Datos (Multi-tenancy)

**Backend:**
```sql
-- ✅ CORRECTO
SELECT * FROM appointments WHERE tenant_id = $tenant_id AND professional_id = $prof_id;

-- ❌ INCORRECTO (Fuga de datos cross-tenant)
SELECT * FROM appointments WHERE professional_id = $prof_id;
```

**Validación de Contexto:**
```python
# ✅ CORRECTO: tenant_id desde JWT validado
tenant_id = await db.pool.fetchval("SELECT tenant_id FROM users WHERE id = $user_id")

# ❌ INCORRECTO: tenant_id desde parámetro de URL (manipulable)
tenant_id = request.query_params.get('tenant_id')
```

### 2. Aislamiento de Scroll (UI/UX)

**Layout.tsx (o contenedor principal):**
```tsx
{/* ✅ CORRECTO: Scroll Isolation Pattern */}
<div className="h-screen overflow-hidden flex flex-col">  {/* Contenedor padre */}
  <header className="h-16">Topbar</header>
  <div className="flex-1 min-h-0 overflow-y-auto">  {/* Área de contenido */}
    {children}
  </div>
</div>

{/* ❌ INCORRECTO: Body scroll + contenidos largos = Overlap */}
<div className="min-h-screen">
  {children}  {/* Scrolleará el body completo */}
</div>
```

### 3. Migraciones DB con Alembic

**orchestrator_service/alembic/versions/:**
```python
# ✅ CORRECTO: Migración Alembic versionada
def upgrade():
    op.add_column('professionals', sa.Column('working_hours', sa.JSON(), server_default='{}'))

def downgrade():
    op.drop_column('professionals', 'working_hours')

# ❌ INCORRECTO: SQL directo fuera de Alembic
# await db.pool.execute("ALTER TABLE professionals ADD COLUMN working_hours JSONB")
```

---

## 📊 Informe de Pre-Vuelo (Pre-Flight Report)

Antes de ejecutar el motor completo, el agente debe generar un informe con:

1. **Skills Cargadas**: Lista de capacidades disponibles
2. **Contexto del Proyecto**: Arquitectura actual, tech stack
3. **Riesgos Identificados**: Latencia, tokens, migraciones
4. **Confidence Score Estimado**: Predicción de viabilidad (0-100%)
5. **Dependencias Externas**: APIs, credentials, permisos

**Ejemplo:**
```markdown
## ✈️ Pre-Flight Report: Feature "Intelligent Agenda 2.0"

**Skills Activas:** Sovereign Backend, Nexus UI, DB Surgeon, Spec Architect  
**Riesgos:** Latencia GCal API (mitigado con async), Token expirado (captura de excepciones)  
**Confidence Score:** 95% (Alta viabilidad)  
**Bloqueos:** Ninguno detectado  
**Recomendación:** ✅ PROCEDER con `/autonomy`
```

---

## 🔄 Protocolo de Fusión No Destructiva

Cuando se actualicen workflows existentes (`AGENTS.md`, `docs/CONTEXTO_AGENTE_IA.md`, o cualquier workflow en `.agent/workflows/`):

1. **NUNCA eliminar** secciones existentes
2. **Expandir** añadiendo nueva información al final
3. **Marcar** nuevas capacidades con `[NUEVO]` si es relevante
4. **Preservar** el formato y estructura original

---

## 📞 Invocación del Motor

Para ejecutar el motor completo de forma autónoma:

```bash
# Opción 1: Invocación explícita
/autonomy

# Opción 2: Encadenar comandos (el agente decide cuándo detenerse)
/advisor /specify /plan /gate /implement /verify /audit
```

**El motor se detiene automáticamente si:**
- Confidence Score < 70%
- Audit detecta Drift crítico
- Tests fallan 3 veces consecutivas
- Usuario interrumpe manualmente

---

*Motor de Autonomía SDD v2.0 © 2026 — Powered by Antigravity | ClinicForge (Dra. María Laura Delgado)*
