# Spec 05: Caché y Enriquecimiento Asíncrono

## 1. Contexto y Objetivos
**Objetivo:** Optimizar el consumo de la API de Meta y evitar latencia en el chat del usuario.
**Problema:** Consultar la Graph API en tiempo real por cada mensaje bloquearía la respuesta de la IA.

## 2. Requerimientos Técnicos

### Backend (Redis Caché)
- **Clave:** `meta:ad:{ad_id}`
- **Valor:** JSON `{ "campaign_name": "...", "ad_name": "..." }`
- **TTL:** 48 horas (los nombres de campañas no cambian frecuente).

### Backend (Background Task)
- **Archivo:** `orchestrator_service/services/tasks.py`
- **Función:** `enrich_patient_attribution(patient_id: int, ad_id: str, tenant_id: str)`
- **Flujo:**
  1. Verificar Redis. Si hit, usar datos.
  2. Si miss, llamar `MetaAdsClient`.
  3. Guardar en Redis.
  4. Actualizar `patients` con nombres de campaña/anuncio.
  5. Ejecutar como `BackgroundTask` de FastAPI post-respuesta.

## 3. Criterios de Aceptación (Gherkin)

```gherkin
Scenario: Enriquecimiento con caché vacío
  Given caché Redis vacío
  When se ejecuta la tarea de enriquecimiento
  Then se llama a la API de Meta y se guarda en Redis
  And se actualiza la tabla 'patients'

Scenario: Enriquecimiento con caché lleno
  Given Redis tiene datos para ad_id '123'
  When se ejecuta la tarea
  Then NO se llama a la API de Meta
  And se utiliza el valor de caché
```

## 4. Esquema de Datos

No aplica cambios de esquema persistence, solo Redis k-v.

## 5. Riesgos y Mitigación
- **Riesgo:** Falla de tarea asíncrona.
- **Mitigación:** Logs de error específicos. Degradación grácil (mostrar ID si no hay nombre).

## 6. Compliance SDD v2.0
- **Soberanía:** Updates siempre filtrados por tenant.
