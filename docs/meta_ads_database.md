# Integración Meta Ads — Documentación Database

> Fecha: 2026-02-16 | Versión: 1.1 | Specs: 13, 14

---

## 1. Migración (Parche 19)

**Ubicación**: `orchestrator_service/db.py` (líneas ~433-454)
**Tipo**: Idempotente (safe para re-ejecución)

### SQL Ejecutado

```sql
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public'
        AND table_name = 'patients'
        AND column_name = 'acquisition_source'
    ) THEN
        ALTER TABLE patients ADD COLUMN acquisition_source VARCHAR(50) DEFAULT 'ORGANIC';
    END IF;

    IF NOT EXISTS (...column_name = 'meta_campaign_id') THEN
        ALTER TABLE patients ADD COLUMN meta_campaign_id VARCHAR(255);
    END IF;

    IF NOT EXISTS (...column_name = 'meta_ad_id') THEN
        ALTER TABLE patients ADD COLUMN meta_ad_id VARCHAR(255);
    END IF;

    IF NOT EXISTS (...column_name = 'meta_ad_headline') THEN
        ALTER TABLE patients ADD COLUMN meta_ad_headline TEXT;
    END IF;

    IF NOT EXISTS (...column_name = 'meta_ad_body') THEN
        ALTER TABLE patients ADD COLUMN meta_ad_body TEXT;
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_patients_acquisition_source ON patients(acquisition_source);

-- Parche 20: Soporte de Identidad Multi-plataforma (JSONB)
ALTER TABLE patients ADD COLUMN IF NOT EXISTS external_ids JSONB DEFAULT '{}';
CREATE INDEX IF NOT EXISTS idx_patients_external_ids ON patients USING GIN (external_ids);

-- Parche 21: Motor de Automatización & Expiración Meta
CREATE TABLE IF NOT EXISTS automation_logs (
    id SERIAL PRIMARY KEY,
    tenant_id INTEGER REFERENCES tenants(id),
    patient_id INTEGER REFERENCES patients(id),
    task_type VARCHAR(50), -- 'handoff_alert', 'appointment_reminder'
    status VARCHAR(20), -- 'sent', 'failed'
    details JSONB,
    created_at TIMESTAMP DEFAULT NOW()
);

ALTER TABLE tenants ADD COLUMN IF NOT EXISTS timezone VARCHAR(50) DEFAULT 'America/Argentina/Buenos_Aires';
```

---

## 2. Esquema de Columnas Nuevas

| Columna | Tipo | Default | Nullable | Fuente | Descripción |
|---------|------|---------|----------|--------|-------------|
| `acquisition_source` | `VARCHAR(50)` | `'ORGANIC'` | No | Webhook referral (Spec 03) | Fuente de adquisición: `ORGANIC`, `META_ADS`, etc. |
| `meta_campaign_id` | `VARCHAR(255)` | `NULL` | Sí | Graph API enrichment (Spec 05) | Nombre de la campaña (enriquecido por background task) |
| `meta_ad_id` | `VARCHAR(255)` | `NULL` | Sí | Webhook referral (Spec 03) | ID del anuncio de Meta (ej. `23857123456`) |
| `meta_ad_headline` | `TEXT` | `NULL` | Sí | Webhook referral (Spec 03) | Título del anuncio (ej. "¿Dolor de muelas?") |
| `meta_ad_body` | `TEXT` | `NULL` | Sí | Webhook referral (Spec 03) | Cuerpo/descripción del anuncio |

---

## 2.1. Central de Credenciales (`credentials`) [MODIFIED]

A partir de la Misión 3, la tabla `credentials` centraliza los activos de Meta por `tenant_id`:

| Name | Valor | Descripción |
|------|-------|-------------|
| `META_ADS_TOKEN` | `String (Encrypted)` | Long-Lived Token de Meta. |
| `META_AD_ACCOUNT_ID` | `String` | ID de la cuenta de anuncios seleccionada en el Wizard. |
| `META_TOKEN_EXPIRES_AT` | `ISO Date String` | Fecha de expiración del token (usada para el Banner global). |
| `META_TOKEN_STATUS` | `'ACTIVE' \| 'EXPIRED'` | Estado de salud de la conexión. |


---

## 3. Índices

| Índice | Tabla | Columna(s) | Tipo |
|--------|-------|------------|------|
| `idx_patients_acquisition_source` | `patients` | `acquisition_source` | B-tree |

**Justificación**: El filtro `WHERE acquisition_source = 'META_ADS'` se usa en el endpoint de marketing stats (`GET /admin/marketing/stats`), que agrupa por campaña.

---

## 4. Flujo de Escritura

```
┌─────────────────────────────────────────────────────────────┐
│ Paso 1: Atribución Inicial (Spec 03) — Síncrono            │
│ main.py → UPDATE patients                                   │
│   SET acquisition_source = 'META_ADS',                      │
│       meta_ad_id = '23857...',                              │
│       meta_ad_headline = '¿Dolor de muelas?',              │
│       meta_ad_body = 'Agenda tu turno...'                   │
│   WHERE id = $5 AND tenant_id = $6                          │
│   (Solo si acquisition_source IS NULL o = 'ORGANIC')        │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│ Paso 2: Enriquecimiento (Spec 05) — Background Task        │
│ tasks.py → UPDATE patients                                  │
│   SET meta_campaign_id = 'Campaña Blanqueamiento 2026'      │
│   WHERE id = $2 AND tenant_id = $3                          │
│   (Usando COALESCE: no sobrescribe si ya existe)            │
│   (NO toca meta_ad_headline ni meta_ad_body)                │
└─────────────────────────────────────────────────────────────┘
```

> **Nota importante**: El enrichment (Paso 2) SOLO actualiza `meta_campaign_id` con el nombre legible de la campaña obtenido de la Graph API. Los campos `meta_ad_headline` y `meta_ad_body` son sacrosantos — vienen del webhook y representan el contenido real del anuncio que vio el paciente.

---

## 5. Queries de Lectura

### Marketing Stats (Spec 07)
```sql
SELECT 
    COALESCE(p.meta_campaign_id, 'Sin Campaña') AS campaign_name,
    COALESCE(p.meta_ad_id, 'Unknown') AS ad_id,
    COALESCE(p.meta_ad_headline, '') AS ad_headline,
    COUNT(*) AS leads,
    COUNT(a.id) AS appointments,
    CASE WHEN COUNT(*) > 0 
         THEN ROUND(COUNT(a.id)::numeric / COUNT(*)::numeric, 2) 
         ELSE 0 END AS conversion_rate
FROM patients p
LEFT JOIN appointments a 
    ON a.patient_id = p.id 
    AND a.tenant_id = p.tenant_id
    AND a.status IN ('scheduled', 'confirmed', 'completed')
WHERE p.tenant_id = $1
  AND p.acquisition_source = 'META_ADS'
GROUP BY p.meta_campaign_id, p.meta_ad_id, p.meta_ad_headline
ORDER BY leads DESC
```

### Patient Context (Mejorado)
```sql
SELECT id, first_name, last_name, phone_number, status,
       urgency_level, urgency_reason, preferred_schedule,
       acquisition_source, meta_ad_id, meta_ad_headline, meta_ad_body
FROM patients 
WHERE tenant_id = $1 AND (phone_number = $2 OR phone_number = $3)
  AND status != 'deleted'
```

---

## 6. Consideraciones de Producción

### Idempotencia
- ✅ Usa `IF NOT EXISTS` para cada columna
- ✅ Usa `CREATE INDEX IF NOT EXISTS`
- ✅ Se puede re-ejecutar sin errores

### Rollback
Si necesitas revertir la migración (no hay Parche automático):
```sql
-- ⚠️ CUIDADO: Esto borra datos
ALTER TABLE patients DROP COLUMN IF EXISTS acquisition_source;
ALTER TABLE patients DROP COLUMN IF EXISTS meta_campaign_id;
ALTER TABLE patients DROP COLUMN IF EXISTS meta_ad_id;
ALTER TABLE patients DROP COLUMN IF EXISTS meta_ad_headline;
ALTER TABLE patients DROP COLUMN IF EXISTS meta_ad_body;
DROP INDEX IF EXISTS idx_patients_acquisition_source;
```

### Performance
- Las nuevas columnas son `VARCHAR`/`TEXT` nullable — impacto mínimo en tablas existentes
- El índice `idx_patients_acquisition_source` optimiza el filtro de `marketing/stats`
- Si la tabla `patients` crece mucho (>100K filas), considerar índice parcial:
  ```sql
  CREATE INDEX idx_patients_meta_ads ON patients(meta_campaign_id) 
  WHERE acquisition_source = 'META_ADS';
  ```

---

## 7. Google Ads Database Integration (NUEVO - Marzo 2026)

### 7.1. Migración (Parche 21)
**Ubicación**: `orchestrator_service/migrations/patch_021_google_ads_integration.sql`
**Tipo**: Idempotente (CREATE TABLE IF NOT EXISTS)

### 7.2. Tablas Nuevas

#### 7.2.1. `google_oauth_tokens`
```sql
CREATE TABLE IF NOT EXISTS google_oauth_tokens (
    id SERIAL PRIMARY KEY,
    tenant_id INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    platform VARCHAR(50) NOT NULL DEFAULT 'ads',  -- 'ads' or 'login'
    access_token TEXT NOT NULL,
    refresh_token TEXT,
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
    scopes TEXT[],
    email VARCHAR(255),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(tenant_id, platform)
);
```
**Propósito**: Almacena tokens OAuth 2.0 de Google para cada tenant
**Índices**: `idx_google_oauth_tokens_tenant`, `idx_google_oauth_tokens_expires`

#### 7.2.2. `google_ads_accounts`
```sql
CREATE TABLE IF NOT EXISTS google_ads_accounts (
    id SERIAL PRIMARY KEY,
    tenant_id INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    customer_id VARCHAR(50) NOT NULL,  -- Google Ads Customer ID
    descriptive_name VARCHAR(255),
    currency_code VARCHAR(10),
    time_zone VARCHAR(50),
    manager BOOLEAN DEFAULT FALSE,
    test_account BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(tenant_id, customer_id)
);
```
**Propósito**: Cuentas de Google Ads accesibles por cada tenant
**Índices**: `idx_google_ads_accounts_tenant`

#### 7.2.3. `google_ads_metrics_cache`
```sql
CREATE TABLE IF NOT EXISTS google_ads_metrics_cache (
    id SERIAL PRIMARY KEY,
    tenant_id INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    customer_id VARCHAR(50) NOT NULL,
    campaign_id VARCHAR(50) NOT NULL,
    campaign_name VARCHAR(255),
    date DATE NOT NULL,
    impressions BIGINT DEFAULT 0,
    clicks BIGINT DEFAULT 0,
    cost_micros BIGINT DEFAULT 0,  -- Micros (divide by 1,000,000 for currency)
    conversions DOUBLE PRECISION DEFAULT 0,
    conversions_value DOUBLE PRECISION DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(tenant_id, customer_id, campaign_id, date)
);
```
**Propósito**: Cache de métricas de Google Ads para performance
**Índices**: `idx_google_ads_metrics_cache_tenant_date`, `idx_google_ads_metrics_cache_campaign`

### 7.3. Credenciales Google
```sql
-- Añadir credenciales Google a la tabla credentials
INSERT INTO credentials (tenant_id, name, value, category, updated_at)
SELECT DISTINCT tenant_id, 'GOOGLE_CLIENT_ID', '', 'google', NOW()
FROM tenants
WHERE NOT EXISTS (...)
ON CONFLICT DO NOTHING;

-- Repetir para: GOOGLE_CLIENT_SECRET, GOOGLE_DEVELOPER_TOKEN, 
-- GOOGLE_REDIRECT_URI, GOOGLE_LOGIN_REDIRECT_URI

-- Credencial global (tenant_id = 0)
INSERT INTO credentials (tenant_id, name, value, category, updated_at)
VALUES (0, 'GOOGLE_ADS_API_VERSION', 'v16', 'google', NOW())
ON CONFLICT DO UPDATE SET value = EXCLUDED.value;
```

### 7.4. Comparación Meta Ads vs Google Ads Database
| Aspecto | Meta Ads | Google Ads |
|---------|----------|------------|
| **Token Storage** | `credentials` table | `google_oauth_tokens` table |
| **Campaign Data** | `meta_ads_campaigns` | `google_ads_metrics_cache` |
| **Account Info** | Meta API on-demand | `google_ads_accounts` table |
| **Lead Attribution** | `patients` columns | Campaign-level (no patient link) |
| **Data Freshness** | Real-time API | Cached (hourly/daily) |
| **Multi-tenant** | Tenant_id en queries | Tenant_id en todas las tablas |

### 7.5. Performance Considerations
1. **Cache Strategy**: Google Ads metrics se cachean para reducir API calls
2. **Token Refresh**: Auto-refresh implementado (check cada 5 minutos)
3. **Index Optimization**: Índices en tenant_id + date para queries rápidas
4. **Data Retention**: Considerar cleanup de cache viejo (>90 días)

### 7.6. Migration Execution
```bash
# Ejecutar migración
python3 run_google_migration.py run

# Verificar estado
python3 run_google_migration.py status
```

**Documentación completa**: Ver [google_ads_integration.md](google_ads_integration.md)
