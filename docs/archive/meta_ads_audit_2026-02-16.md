# Auditoría Pre-Despliegue — Integración Meta Ads

> Fecha: 2026-02-16 | Auditor: Antigravity AI | Resultado: ✅ APROBADO (con 2 bugs corregidos)

---

## 🔍 Resumen de Auditoría

Se auditaron **17 archivos** entre backend, frontend y base de datos.
Se encontraron **2 bugs** que fueron corregidos antes de este reporte.

---

## 🐛 Bugs Encontrados y Corregidos

### BUG-001: Enrichment sobrescribía headline/body (CRÍTICO)

| Campo | Valor |
|-------|-------|
| **Archivo** | `orchestrator_service/services/tasks.py` (línea 119-124) |
| **Severidad** | 🔴 Crítica — corrupción de datos |
| **Descripción** | El UPDATE del enrichment mapeaba `ad_name` → `meta_ad_headline` y `adset_name` → `meta_ad_body`, sobrescribiendo los datos reales del anuncio (capturados del webhook referral) con nombres display de la Graph API |
| **Impacto** | El headline real "¿Dolor de muelas?" se reemplazaba por el nombre del ad "Ad #3847 - Blanqueamiento" |
| **Fix** | Reducido el enrichment a SOLO actualizar `meta_campaign_id`. Los campos `meta_ad_headline` y `meta_ad_body` ya no se tocan |

### BUG-002: Atribución sin tenant_id en WHERE (MEDIO)

| Campo | Valor |
|-------|-------|
| **Archivo** | `orchestrator_service/main.py` (línea 1556) |
| **Severidad** | 🟡 Media — violación de soberanía |
| **Descripción** | El UPDATE de atribución usaba `WHERE id = $5` sin incluir `AND tenant_id = $6` |
| **Impacto** | En teoría, IDs de paciente son únicos globalmente. Pero viola el principio de defensa en profundidad |
| **Fix** | Agregado `AND tenant_id = $6` al WHERE |

---

## ✅ Checklist de Soberanía (tenant_id)

| Query | Archivo | tenant_id en WHERE |
|-------|---------|-------------------|
| Atribución UPDATE | `main.py:1556` | ✅ (post-fix) |
| Enrichment UPDATE | `tasks.py:117` | ✅ |
| Marketing Stats SELECT | `admin_routes.py:2776` | ✅ |
| Patient Context SELECT | `admin_routes.py:196` | ✅ |
| Health Check endpoint | `admin_routes.py:2816` | ✅ (protegido JWT) |
| Triage UPDATE | `main.py:852` | ⚠️ Preexistente (solo `WHERE id = $3`) |

> **Nota**: El UPDATE de triage (`main.py:852`) es un bug preexistente, no introducido en esta integración. Se recomienda corregir en un pass futuro.

---

## ✅ Checklist de Migración DB

| Verificación | Resultado |
|-------------|-----------|
| Columnas con `IF NOT EXISTS` | ✅ |
| Índice con `IF NOT EXISTS` | ✅ |
| Default `'ORGANIC'` para `acquisition_source` | ✅ |
| Columnas NULL-safe (nullable) | ✅ |
| Idempotente (re-ejecutable sin error) | ✅ |

---

## ✅ Checklist Frontend

| Verificación | Resultado |
|-------------|-----------|
| `MarketingPerformanceCard` maneja loading/error | ✅ |
| `AdContextCard` null-safe (retorna null si no hay datos) | ✅ |
| PatientDetail badge solo muestra si `acquisition_source === 'META_ADS'` | ✅ |
| No hay imports rotos o componentes sin exportar | ✅ |
| Overflow controlado en lista de campañas (`max-h-40`) | ✅ |

---

## ✅ Checklist de Seguridad

| Verificación | Resultado |
|-------------|-----------|
| `META_ADS_TOKEN` no aparece en logs | ✅ (log_sanitizer) |
| `access_token` en URLs sanitizado | ✅ (regex pattern) |
| Health check protegido con JWT | ✅ |
| Marketing stats protegido con JWT + roles (ceo, secretary) | ✅ |

---

## 📋 Archivos Auditados

### Nuevos (5)
- `orchestrator_service/core/log_sanitizer.py` ✅
- `orchestrator_service/scripts/check_meta_health.py` ✅
- `orchestrator_service/scripts/__init__.py` ✅
- `frontend_react/src/components/MarketingPerformanceCard.tsx` ✅
- `frontend_react/src/components/AdContextCard.tsx` ✅

### Modificados (8)
- `orchestrator_service/main.py` ✅ (bug-002 corregido)
- `orchestrator_service/admin_routes.py` ✅
- `orchestrator_service/db.py` ✅
- `orchestrator_service/services/tasks.py` ✅ (bug-001 corregido)
- `orchestrator_service/services/meta_ads_service.py` ✅
- `frontend_react/src/views/PatientDetail.tsx` ✅
- `frontend_react/src/views/DashboardView.tsx` ✅
- `frontend_react/src/views/ChatsView.tsx` ✅

---

## 🚀 Recomendaciones para Despliegue

1. **Variables de entorno**: Asegurar que `META_ADS_TOKEN` esté configurada en el servidor (o dejar vacía para degradación grácil)
2. **Redis**: Si Redis no está disponible, el enrichment funciona pero sin cache
3. **Migración DB**: Se ejecuta automáticamente al iniciar el orchestrator (Parche 19 en db.py)
4. **Lint errors**: Todos los errores Pyre2 son falsos positivos (paquetes Docker-only)
5. **Bug preexistente**: Considerar corregir el `WHERE` de triage (`main.py:852`) en el próximo sprint

---

## 📊 Documentación Generada

| Documento | Path |
|-----------|------|
| Backend | `docs/meta_ads_backend.md` |
| Frontend | `docs/meta_ads_frontend.md` |
| Database | `docs/meta_ads_database.md` |
| Auditoría (este doc) | `docs/meta_ads_audit_2026-02-16.md` |
