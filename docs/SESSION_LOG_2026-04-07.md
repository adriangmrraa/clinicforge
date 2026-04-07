# Session Log — 07/04/2026

> Resumen de la sesión de trabajo con Claude Code sobre ClinicForge.
> Documenta análisis, decisiones, fixes hechos, fixes pendientes y conclusiones.

---

## 1. Auditoría de producción

### Veredicto
**NO APTO para producción** sin correcciones previas. Base sólida pero faltan fundamentos operacionales.

### ✅ Lo que está bien
- Arquitectura microservicios + Docker Compose con healthchecks
- 30+ migraciones Alembic con baseline reproducible
- JWT con `tenant_id` embebido, CORS dinámico, middleware de seguridad
- CI con tests + lint + build
- Frontend TypeScript estricto, sin `dangerouslySetInnerHTML`, DOMPurify

### 🔴 Bloqueadores críticos
1. **Dependencias obsoletas**: `langchain==0.1.0` y `langchain-community==0.0.13` están deprecadas.
2. **JWT multi-secret fallback** (`my_routes.py:56-79`): intenta varias claves con HS256/384/512, reduce entropía.
3. **Sin backups documentados** para Postgres ni volúmenes (inaceptable para datos clínicos).
4. **Observabilidad opcional**: Sentry solo se activa si `SENTRY_DSN` está set; debe ser obligatorio en prod.
5. **Tests sin cobertura medida**: 22 tests existen pero sin `pytest-cov`. Faltan tests de aislamiento multi-tenant.

### 🟡 Riesgos medios
- CSP con `unsafe-inline` (`core/security_middleware.py:45-46`)
- Rate limiting con IP remota sin `X-Forwarded-For`
- Bare `except:` que silencian errores
- Log sanitizer no redacta PII de pacientes (riesgo legal HIPAA/GDPR/Ley 25.326)
- 7 TODOs pendientes (incluyendo verificación CEO en dashboard auth)

### Checklist mínimo antes de producción
1. ⬜ Actualizar LangChain → 0.2.x + `langchain-openai`
2. ⬜ Resolver `pip audit` / `npm audit`
3. ⬜ Eliminar JWT multi-secret fallback
4. ⬜ Hacer `SENTRY_DSN` obligatorio en startup
5. ⬜ Script de backup automático Postgres + restore probado
6. ⬜ Tests de aislamiento multi-tenant en CI
7. ⬜ `pytest-cov` con umbral mínimo 70%
8. ⬜ Sanitizar PII de pacientes en logs
9. ⬜ Reemplazar `unsafe-inline` en CSP por nonces
10. ⬜ APM o métricas Prometheus + alertas
11. ⬜ Configurar `X-Forwarded-For` en rate limiter
12. ⬜ Runbook de incidentes y rollback

---

## 2. Bugs encontrados y arreglados en esta sesión

### 2.1 Beta "Analizar Conversaciones con IA" rota

**Síntoma:** Error visible en el modal de profesional:
> Unsupported parameter: 'max_tokens' is not supported with this model. Use 'max_completion_tokens' instead.

**Causa:** `admin_routes.py:7127` usaba `max_tokens=500` en una llamada a OpenAI con modelo configurable. Cuando el tenant configuró GPT-5 Mini, el modelo rechazó el parámetro legacy.

**Fix:** intentar primero `max_completion_tokens`, caer a `max_tokens` con try/except si el modelo es legacy.

**Commit:** `ad0d7c5` — `fix(analytics): corrige insights beta y métricas de profesionales`

### 2.2 Métricas de profesional con datos engañosos

**Síntomas (modal de staff, vista de profesional):**
- "Turnos completados: 2 (finalización 0%)" → contradictorio. Mostraba `total_appointments` con la etiqueta de "completados".
- "Ingresos estimados: $0" → cálculo de revenue solo miraba `billing_amount` y `treatment_types.base_price`, ignorando los precios de consulta de profesional/tenant.

**Fixes aplicados:**
1. `analytics_service.py`: cadena de fallback de revenue ampliada a `billing_amount → treatment_types.base_price → professionals.consultation_price → tenants.consultation_price`. Aplicado en `get_all_professionals_analytics` y `get_professional_summary`.
2. Backend ahora expone `completed_appointments` además de `total_appointments`.
3. `UserApprovalView.tsx:693`: muestra `completados / totales (finalización X%)` en lugar de etiquetar el total como completados.

**Commit:** `ad0d7c5` (mismo commit que 2.1)

### 2.3 Memoria de pacientes rota con GPT-5 Mini

**Contexto:** El operador (Dra. Laura Delgado) tenía configurado GPT-5 Mini como modelo de "Memoria de pacientes" desde la UI de Tokens & Métricas. Esto rompía silenciosamente la extracción de memorias en cada conversación (logueado solo como warning).

**Análisis ampliado:** Se buscaron todos los `max_tokens` en el código y se identificó que `patient_memory.py` era una bomba de tiempo equivalente al bug 2.1. Otros sitios (`vision_service.py`, `telegram_bot.py`) tenían modelos hardcodeados a gpt-4o así que no estaban afectados. `nova_daily_analysis.py` ya tenía su propio fallback.

**Solución (con SDD):**
Spec en `openspec/changes/openai-param-compat/`:
- `proposal.md`, `spec.md`, `tasks.md`

Implementación:
1. Nuevo helper `core/openai_compat.py`:
   - `is_modern_openai_model(model)` — detecta `gpt-5*`, `o1*`, `o3*`, `o4*`
   - `build_openai_chat_kwargs(model, max_tokens, temperature, **extra)` — devuelve dict de kwargs correcto según familia. Modelos modernos reciben `max_completion_tokens` y solo conservan `temperature` cuando es exactamente `1`.
2. `services/patient_memory.py`:
   - `extract_and_store_memories` y `compact_memories` usan el helper.
   - `compact_memories` ahora respeta `MODEL_PATIENT_MEMORY` (antes hardcodeado a gpt-4o-mini, bug latente).
3. `tests/test_openai_compat.py` con 8 tests cubriendo legacy, modern, temperature handling y extras reservados.

**Commit:** `95bd9a0` — `fix(memory): soporte gpt-5/o-series en patient_memory vía openai_compat`

---

## 3. Bugs identificados pero NO arreglados

### 3.1 Dashboard de tokens y métricas
Verificado que `/admin/stats/summary` (endpoint del Dashboard principal) **no llama a OpenAI**, solo agrega datos de DB. No afectado por el bug de `max_tokens`.

### 3.2 TORA — Conversación de prueba con "Juan Román Riquelme"
Sesión de testing reveló 9 bugs. Todos documentados en archivos separados:

- **`docs/TORA_STATE_MACHINE_LOCK_TASK.md`** — bugs críticos #1, #4, #5, #9 (state machine sin lock).
- **`docs/TORA_COSMETIC_BUGS_TASK.md`** — bugs #2, #3, #6, #7, #8 (cosméticos y UX).

#### Resumen ejecutivo de los 9 bugs

| # | Bug | Severidad | Causa raíz |
|---|-----|-----------|------------|
| 1 | Fecha invertida `12/05 → 05/12` | 🔴 crítico | State machine + parser sin `dayfirst` |
| 2 | `[INTERNAL_PRICE:7000000]` filtrado al usuario | 🟠 medio | Falta capa de saneamiento |
| 3 | Precio "$7.000.000" para blanqueamiento | 🟠 medio | Probable data entry o centavos |
| 4 | Loop tras "Agéndame el del 12 de mayo" | 🔴 crítico | State machine sin lock |
| 5 | "Sin turnos" después de bookear | 🔴 crítico | State machine (booking nunca persistió) |
| 6 | Feriado 17/08 ofrecido como disponible | 🟡 bajo | `check_availability` no consulta `holiday_service` |
| 7 | "Por la tarde" no filtra slots | 🟡 bajo | Falta entidad `time_of_day` en parser |
| 8 | Saludo completo repetido | 🟡 bajo | Sin flag `greeted_at` en contexto |
| 9 | Doble respuesta de slots | 🟡 bajo | Race condition del buffer |

#### Causa raíz dominante: state machine sin lock

Los bugs 1, 4, 5 y 9 son síntomas del mismo problema: **el LLM (gpt-4o-mini) re-llama `check_availability` cuando recibe una confirmación del usuario**, en lugar de avanzar a `confirm_slot` → `book_appointment`.

Esto pasa porque:
- El system prompt no impone reglas duras de transición de estados.
- No hay un "slot lock" en Redis que persista los slots vivos del último turno.
- `gpt-4o-mini` con muchos tools disponibles tiende a re-ejecutar tools de búsqueda.

**Decisión del owner (acordada en sesión):** el problema #1 es el system prompt sin reglas de transición de estados. Es mucho más que un problema de buffer. Atacar primero con prompt hardening (camino A) y slot lock en Redis (camino B). FSM completa (camino C) solo si A+B no alcanzan.

---

## 4. Decisiones arquitectónicas tomadas

### 4.1 Helper de compatibilidad OpenAI (implementado)
Centralizar el manejo de diferencias entre familias de modelos OpenAI en un único helper `core/openai_compat.py`. Cualquier nuevo servicio que llame a OpenAI debe usar este helper para evitar reintroducir el bug de `max_tokens`.

**Follow-up pendiente:** migrar `nova_daily_analysis.py`, `digital_records_service.py` y `attachment_summary.py` al helper (hoy cada uno tiene su propia variante).

### 4.2 SDD (Spec-Driven Development) como práctica
Para cambios no triviales, crear primero el spec en `openspec/changes/<nombre>/` con `proposal.md`, `spec.md`, `tasks.md` antes de tocar código. Aplicado en esta sesión para `openai-param-compat`.

### 4.3 TORA: prompt hardening + slot lock en Redis
Para los bugs críticos del state machine, la decisión es atacar con A+B combinados:
- **A.** Reglas explícitas de transición en el system prompt + few-shot examples del flujo correcto.
- **B.** Slot lock en Redis (`tora:slots:{tenant}:{phone}`, TTL 10 min) que `confirm_slot` valida antes de bookear.

NO se va a refactorizar a una FSM explícita (camino C) hasta confirmar que A+B no alcanzan.

---

## 5. Tareas pendientes priorizadas

### Esta semana (urgente)
1. ⬜ TORA bug #2 — Strip `[INTERNAL_PRICE]` (5 min)
2. ⬜ TORA bug #3 — Verificar precio en DB y arreglar escala (10 min)
3. ⬜ TORA bugs #1, #4, #5, #9 — State machine lock (camino A: prompt hardening, primero)

### Próximo sprint
4. ⬜ TORA bugs #6 (feriados), #7 (tarde/mañana), #8 (saludo único)
5. ⬜ State machine slot lock en Redis (camino B)
6. ⬜ Tests E2E del flujo de booking
7. ⬜ Migrar `nova_daily_analysis.py`, `digital_records_service.py`, `attachment_summary.py` al helper `openai_compat`

### Backlog (pre-producción)
- Todo el checklist de la sección 1 (LangChain, backups, Sentry obligatorio, cobertura, etc.)

---

## 6. Commits de esta sesión

| Commit | Descripción |
|--------|-------------|
| `ad0d7c5` | `fix(analytics): corrige insights beta y métricas de profesionales` |
| `95bd9a0` | `fix(memory): soporte gpt-5/o-series en patient_memory vía openai_compat` |
| _(este)_ | `docs: tareas pendientes TORA + session log` |

Branch: `claude/add-claude-documentation-FXTv9`

---

## 7. Notas para retomar desde Engram

- **Lo más importante de esta sesión:** entender que TORA tiene un problema de control de flujo conversacional, no de tools rotos. El state machine es el bug #1 a resolver.
- **Lo que ya está blindado:** todo el camino de OpenAI con modelos modernos. Nunca más debería romperse silenciosamente cuando alguien cambie el modelo desde la UI.
- **Lo que sigue siendo deuda:** los 12 puntos del checklist de producción. Ninguno se atacó en esta sesión.
- **Decisión filosófica del owner:** SDD para cambios no triviales, parches rápidos para bugs cosméticos.
