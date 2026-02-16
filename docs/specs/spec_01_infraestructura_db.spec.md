# Spec 01: Infraestructura de Datos Meta Ads

## 1. Contexto y Objetivos
**Objetivo:** Preparar la base de datos y los modelos del backend para persistir la información de atribución de marketing proveniente de Meta Ads.
**Problema:** Actualmente no existe lugar donde guardar `campaign_id`, `ad_id` o el contenido del anuncio que trajo al paciente.

## 2. Requerimientos Técnicos

### Backend (Base de Datos)
- **Tabla:** `patients`
- **Nuevas Columnas (Idempotentes):**
  - `acquisition_source` (`VARCHAR`, Default: 'ORGANIC')
  - `meta_campaign_id` (`VARCHAR`, Nullable)
  - `meta_ad_id` (`VARCHAR`, Nullable)
  - `meta_ad_headline` (`TEXT`, Nullable)
  - `meta_ad_body` (`TEXT`, Nullable)
- **Migración:** Debe usar `DO $$` block para ser idempotente (verificar existencia antes de agregar).

### Backend (ORM)
- **Archivo:** `orchestrator_service/db/models_dental.py`
- **Modelo:** `Patient`
- **Acción:** Mapear las nuevas columnas en SQLAlchemy.

## 3. Criterios de Aceptación (Gherkin)

```gherkin
Scenario: Ejecución de migración en base de datos existente
  Given la tabla 'patients' ya tiene datos
  When se ejecuta el script de migración '01_meta_ads_columns.sql'
  Then la tabla 'patients' tiene la columna 'acquisition_source' con default 'ORGANIC'
  And la columna 'meta_ad_id' existe y permite NULLs
  And no se perdieron datos de pacientes existentes

Scenario: Persistencia de modelo actualizado
  Given un objeto Patient con acquisition_source='META_ADS'
  When se guarda en la base de datos
  Then el valor se persiste correctamente sin errores de esquema
```

## 4. Esquema de Datos

```sql
ALTER TABLE patients
ADD COLUMN IF NOT EXISTS acquisition_source VARCHAR DEFAULT 'ORGANIC',
ADD COLUMN IF NOT EXISTS meta_campaign_id VARCHAR,
ADD COLUMN IF NOT EXISTS meta_ad_id VARCHAR,
ADD COLUMN IF NOT EXISTS meta_ad_headline TEXT,
ADD COLUMN IF NOT EXISTS meta_ad_body TEXT;
```

## 5. Riesgos y Mitigación
- **Riesgo:** Bloqueo de tabla en producción si `patients` es muy grande.
- **Mitigación:** La operación `ADD COLUMN` en Postgres moderno es rápida. Realizar en ventana de mantenimiento si es crítico.

## 6. Compliance SDD v2.0
- **Soberanía:** Estas columnas son propias del tenant. Al navegar `patients` siempre filtrar por `tenant_id`.
