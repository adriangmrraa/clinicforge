# Análisis de Rama-German vs Main — ClinicForge

**Fecha de análisis:** 2026-03-17
**Rama analizada:** `origin/Rama-German`
**Rama de referencia:** `main` (commit `fae14a9`)
**Punto de divergencia:** commit `add0bc4` — *fix(sender): fetch bot_phone_number from tenants table instead of credentials*

---

## 1. Resumen ejecutivo

La rama `Rama-German` introduce Alembic como framework de migraciones de base de datos, junto con modelos SQLAlchemy completos para el ORM. El trabajo técnico de Alembic está bien implementado, pero la rama se quedó **40+ commits atrás de main** y le faltan tablas y columnas que se agregaron posteriormente en main con migraciones SQL directas. Además, German se fue de scope agregando un sistema de autenticación, un servicio BFF, y security middleware que no formaban parte de la tarea original.

---

## 2. Contexto de divergencia

| Dato | Valor |
|------|-------|
| Merge-base | `add0bc4` |
| Commits en Rama-German (propios) | 4 + 2 merges |
| Commits en main que German NO tiene | ~40+ |
| Archivos modificados por German | 18 (980 líneas añadidas, 71 eliminadas) |

### Commits de German

```
dfd2b72 chore: Add .gitattributes, service start script, remove temp demo files
d816a2b Merge branch 'main' into Rama-German
dcfd700 feat: Implement core authentication, user registration, and security middleware
bf878ea feat: Initialize BFF service with CORS, health check, and a proxy
1af3ac7 Merge branch 'main'
4b62a2d feat: add initial database models, Alembic migration setup, and core config
```

### Commits en main que German no tiene (muestra)

```
fae14a9 fix: dashboard metrics 500 (jinja2 missing) y Recharts width warning
a501feb feat: configuración dinámica de clínica, FAQs y system prompt optimizado
9341829 Fix DASHBOARD STATUS687779
575846b feat: Autenticación automática CEO con sesiones
539a152 feat: Sistema agente mejorado v2.0 con dashboard CEO completo
f3ecee9 fix(agenda): vistas Año/3 Años, overlay de carga y fetch por vista
0978c4f feat: implemented annual/3-year agenda filters, real-time anamnesis sync
084d622 feat: book_appointment fix, anamnesis flow, patient isolation
... (+30 commits más)
```

---

## 3. Análisis del trabajo de Alembic

### 3.1 Archivos de infraestructura creados

| Archivo | Propósito | Estado |
|---------|-----------|--------|
| `orchestrator_service/alembic.ini` | Configuración de Alembic | Correcto |
| `orchestrator_service/alembic/env.py` | Script de entorno para migraciones | Correcto |
| `orchestrator_service/alembic/script.py.mako` | Template de migraciones | Correcto |
| `orchestrator_service/alembic/README` | Documentación básica | OK |
| `orchestrator_service/models.py` | 18 modelos SQLAlchemy (432 líneas) | Incompleto vs main |
| `orchestrator_service/start.sh` | Script de arranque con `alembic upgrade head` | Correcto |
| `orchestrator_service/requirements.txt` | Agregó `alembic` y `psycopg2-binary` | Correcto |
| `docs/migraciones_y_roadmap_alembic.md` | Roadmap de migraciones en 5 fases | Buena documentación |

### 3.2 Lo que hizo bien

1. **env.py inteligente**: Convierte `postgresql+asyncpg://` a `postgresql://` sincrónico para que Alembic funcione. Este es el problema principal que hay que resolver al usar Alembic con FastAPI + asyncpg, y lo resolvió correctamente:
   ```python
   dsn.replace("postgresql+asyncpg://", "postgresql://")
   ```

2. **start.sh con fail-fast**: El script ejecuta `alembic upgrade head` antes de levantar uvicorn, con `set -e` para detener el deploy si la migración falla. Usa `exec` para manejar PID 1 correctamente en Docker.

3. **Migración baseline vacía**: La primera migración `83ffa6090043_initial_baseline.py` es un `pass` en upgrade/downgrade. Esto es el patrón correcto para marcar el estado inicial del schema sin modificar nada.

4. **Modelos con constraints**: Los 18 modelos tienen `CheckConstraint`, `UniqueConstraint`, `Index` y `ForeignKey` correctamente definidos, con server_default para timestamps.

5. **pool.NullPool**: Usa NullPool en env.py, que es lo correcto para scripts de migración de corta duración.

6. **Autogenerate**: Importa `Base.metadata` en env.py, habilitando `alembic revision --autogenerate`.

### 3.3 Problemas encontrados

#### Severidad ALTA

- **`op.drop_constraint(None, 'credentials', type_='foreignkey')` en downgrade de la migración sync**: Pasar `None` como nombre de constraint es frágil y puede fallar si hay múltiples FKs en la tabla. Debería usar el nombre explícito del constraint.

- **Modelos desactualizados**: Los modelos no reflejan el schema actual de main. Le faltan 9+ tablas y múltiples columnas (ver sección 4).

#### Severidad MEDIA

- **Conversión `preferred_time` de TIME a DateTime**: El `postgresql_using` cast `(COALESCE(preferred_date, CURRENT_DATE) + preferred_time)::timestamp with time zone` es riesgoso en producción con datos existentes. Puede generar valores incorrectos si `preferred_date` es NULL.

- **Sin `relationship()` en los modelos**: Los modelos definen `ForeignKey` pero no `relationship()`. Esto significa que el ORM no puede hacer lazy loading ni eager loading de relaciones. Se pierde la principal ventaja de usar SQLAlchemy como ORM.

- **`test_column` en users**: Dejó una columna de prueba (`test_column`) en la tabla users y la limpia en la migración sync. Esto indica que hizo testing directamente en la base de datos en lugar de usar un entorno de prueba aislado.

#### Severidad BAJA

- Ambos drivers presentes: `asyncpg` (para la app) y `psycopg2-binary` (para Alembic). Es aceptable pero agrega una dependencia extra.
- Comentarios removidos en columnas de `patients` (birth_date, email, city, first_touch_source) sin razón aparente.

---

## 4. Tablas y migraciones faltantes

### 4.1 Tablas que existen en main pero NO en los modelos de German

| Tabla | Migración en main | Función |
|-------|-------------------|---------|
| `google_oauth_tokens` | `patch_021_google_ads_integration.sql` | Tokens OAuth 2.0 para Google Ads/Login |
| `google_ads_accounts` | `patch_021_google_ads_integration.sql` | Cuentas de clientes Google Ads |
| `google_ads_metrics_cache` | `patch_021_google_ads_integration.sql` | Cache de métricas de campañas |
| `patient_attribution_history` | `patch_020_last_touch_attribution.sql` | Historial completo de atribución multi-touch |
| `daily_analytics_metrics` | `007_analytics_metrics.sql` | Métricas agregadas del dashboard CEO |
| `google_calendar_blocks` | `dentalogic_schema.sql` (base) | Bloques de calendario Google |
| `calendar_sync_log` | `dentalogic_schema.sql` (base) | Log de sincronización de calendario |
| `accounting_transactions` | `dentalogic_schema.sql` (base) | Transacciones contables |
| `daily_cash_flow` | `dentalogic_schema.sql` (base) | Reporte de caja diaria |

### 4.2 Columnas faltantes en tablas existentes

| Tabla | Columnas faltantes | Migración en main |
|-------|-------------------|-------------------|
| `patients` | `last_touch_source`, `last_touch_ad_id`, `last_touch_ad_name`, `last_touch_campaign_id`, `last_touch_campaign_name`, `last_touch_timestamp` | `patch_020_last_touch_attribution.sql` |
| `patients` | `city` | `patch_022_patient_admission_fields.sql` |
| `chat_conversations` | `last_read_at` | `v15_add_last_read_at.sql` |
| `chat_conversations` | `last_derivhumano_at` | `v16_fix_missing_column_derivhumano.sql` |

### 4.3 Vista faltante

| Vista | Migración en main | Función |
|-------|-------------------|---------|
| `patient_attribution_complete` | `patch_020_last_touch_attribution.sql` | Vista unificada de atribución first-touch + last-touch |

### 4.4 Función faltante

| Función | Ubicación en main | Función |
|---------|-------------------|---------|
| `get_treatment_duration()` | `dentalogic_schema.sql` | Retorna duración de tratamiento según urgencia |

### 4.5 Tablas que German tiene EXTRA (no en el schema SQL de main)

| Modelo | Descripción | Nota |
|--------|-------------|------|
| `PatientDocument` | Documentos/imágenes de pacientes | No existe en schema SQL de main |
| `ChannelConfig` | Configuración de canales de comunicación | No existe en main |
| `AutomationLog` | Log de automatizaciones | No existe en main |

Estas tablas extra podrían ser útiles a futuro, pero no están en producción actualmente.

---

## 5. Trabajo fuera de scope

German agregó funcionalidad que no le fue solicitada:

| Feature | Archivos | Observación |
|---------|----------|-------------|
| Sistema de autenticación JWT | `auth_routes.py` (320 líneas) | Main ya tiene su propio sistema de auth con sesiones CEO |
| BFF Service (TypeScript) | `bff_service/src/index.ts` | Proxy/gateway innecesario actualmente |
| Security Middleware | `core/security_middleware.py` | Headers de seguridad (HSTS, CSP, X-Frame-Options) |
| `.gitattributes` | `.gitattributes` | Normalización de line endings |

El sistema de auth de German (JWT + HttpOnly cookies) **entra en conflicto** con el sistema de autenticación que ya se implementó en main (sesiones CEO con dashboard).

---

## 6. Cómo proceder

### Opción A: Cherry-pick de infraestructura Alembic (RECOMENDADA)

Esta opción toma solo el valor real del trabajo de German y lo aplica sobre main actual:

1. **Cherry-pick selectivo** — Extraer de Rama-German solo los archivos de infraestructura:
   - `orchestrator_service/alembic.ini`
   - `orchestrator_service/alembic/env.py`
   - `orchestrator_service/alembic/script.py.mako`
   - `orchestrator_service/start.sh`
   - Dependencias en `requirements.txt` (`alembic`, `psycopg2-binary`)

2. **Crear `models.py` completo** — Escribir un models.py nuevo que refleje las 26 tablas actuales de main (no las 18 de German).

3. **Generar baseline** — Crear una migración vacía como baseline:
   ```bash
   alembic revision -m "baseline_main_schema"
   ```

4. **Stamp en producción** — Marcar la DB de producción con la versión actual:
   ```bash
   alembic stamp head
   ```

5. **A partir de ahora**, toda nueva migración se crea con:
   ```bash
   alembic revision --autogenerate -m "descripcion del cambio"
   ```

### Opción B: Rebase de Rama-German sobre main

1. German hace `git rebase main` en su rama
2. Resuelve conflictos (habrá muchos, especialmente en `admin_routes.py`, `main.py`, `docker-compose.yml`)
3. Actualiza `models.py` con las 9+ tablas faltantes
4. Corre `alembic revision --autogenerate -m "sync with main"` para generar migración delta
5. Testea contra DB limpia y contra DB con schema de producción

**No se recomienda** porque:
- 40+ commits de diferencia generarán conflictos masivos
- El auth system de German conflictúa con el de main
- Es más trabajo que empezar con la infraestructura limpia

### Opción C: Merge directo (NO RECOMENDADA)

Un merge directo sería destructivo. Las dos ramas divergieron demasiado y tienen implementaciones conflictivas (auth, admin_routes, docker-compose).

---

## 7. Calificación del trabajo de German

| Aspecto | Nota | Justificación |
|---------|------|---------------|
| Conocimiento de Alembic | **8/10** | Setup correcto, env.py con manejo de asyncpg, estructura profesional |
| Modelos SQLAlchemy | **7/10** | Completos para su momento, buenos constraints e indexes, faltan relationships |
| Calidad de migraciones | **6/10** | Baseline correcta, sync tiene problemas (None constraint, test_column) |
| Documentación | **8/10** | El roadmap de migraciones es detallado y bien estructurado |
| Scope management | **5/10** | Se fue de scope: auth, BFF, security middleware no eran la tarea |
| Sincronización con equipo | **4/10** | No mantuvo su rama actualizada, 40+ commits atrás |
| Prácticas de desarrollo | **6/10** | test_column en producción, debug endpoints públicos |

### Nota global: 6.5/10

**Resumen**: Buen trabajo técnico en la implementación de Alembic, con una documentación sólida. El principal problema es que se fue de scope agregando features no solicitadas (auth, BFF, security middleware) y no coordinó con los cambios que se iban haciendo en main. El trabajo de infraestructura Alembic es rescatable y debería usarse como base.

---

## 8. Archivos de referencia en Rama-German

### Alembic Core
- `orchestrator_service/alembic.ini`
- `orchestrator_service/alembic/env.py`
- `orchestrator_service/alembic/script.py.mako`
- `orchestrator_service/alembic/versions/83ffa6090043_initial_baseline.py`
- `orchestrator_service/alembic/versions/820dbf12532d_sync_point_with_patients_and_treatments.py`

### Modelos y Auth
- `orchestrator_service/models.py` (432 líneas, 18 clases)
- `orchestrator_service/auth_routes.py` (320 líneas)
- `orchestrator_service/core/security_middleware.py` (72 líneas)

### Configuración y Deploy
- `orchestrator_service/start.sh`
- `orchestrator_service/requirements.txt`
- `orchestrator_service/Dockerfile`
- `docker-compose.yml`
- `docs/migraciones_y_roadmap_alembic.md`

---

## 9. Migraciones actuales en main (referencia)

| Archivo | Qué hace |
|---------|----------|
| `dentalogic_schema.sql` | Schema completo base (26 tablas) |
| `patch_017_meta_ads_attribution.sql` | Atribución Meta Ads en patients |
| `patch_019_meta_form_leads.sql` | Tabla de leads de Meta Forms |
| `patch_020_last_touch_attribution.sql` | Last-touch attribution + historial |
| `patch_021_google_ads_integration.sql` | Google Ads OAuth + métricas |
| `patch_022_patient_admission_fields.sql` | Campo city en patients |
| `v15_add_last_read_at.sql` | last_read_at en chat_conversations |
| `v16_fix_missing_column_derivhumano.sql` | last_derivhumano_at en chat_conversations |
| `007_analytics_metrics.sql` | daily_analytics_metrics para dashboard |

Todas estas migraciones deben estar representadas en el `models.py` final de Alembic para que `--autogenerate` funcione correctamente.
