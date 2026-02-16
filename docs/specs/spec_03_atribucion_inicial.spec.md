# Spec 03: Atribución Inicial (Orchestrator)

## 1. Contexto y Objetivos
**Objetivo:** Vincular la información del anuncio (`referral_data`) con el paciente en el momento que llega el mensaje al Orchestrator.
**Problema:** La información llega al webhook pero debe persistirse en la entidad `Patient`.

## 2. Requerimientos Técnicos

### Backend (Orchestrator)
- **Endpoint:** `POST /chat` (o equivalente).
- **Lógica:**
  1. Recibir `referral_data` en el body del request.
  2. Buscar paciente por teléfono y `tenant_id`.
  3. Si `referral_data` existe:
     - Si `acquisition_source` es 'ORGANIC' o NULL:
       - Actualizar a 'META_ADS'.
       - Guardar `meta_campaign_id` (default provisional: `source_id`), `meta_ad_id` (`source_id`), `meta_ad_headline`, `meta_ad_body`.
     - Si ya tiene atribución, no sobreescribir el origen original (First Touch), pero actualizar metadatos de última interacción si es relevante (opcional).
  4. Pasar contexto del anuncio a la memoria de la sesión para la IA (ver Spec 06).

## 3. Criterios de Aceptación (Gherkin)

```gherkin
Scenario: Nuevo paciente desde anuncio
  Given un número de teléfono que no existe en DB
  And un request a /chat con 'referral_data'
  When se crea el paciente
  Then 'acquisition_source' es 'META_ADS'
  And 'meta_ad_id' coincide con el 'source_id' del referral

Scenario: Paciente existente orgánico interactúa con anuncio
  Given un paciente existente con acquisition_source='ORGANIC'
  And un request a /chat con 'referral_data'
  When se procesa el mensaje
  Then se actualiza 'acquisition_source' a 'META_ADS'
  And se guardan los datos del anuncio
```

## 4. Esquema de Datos

No aplica cambios de esquema DB, solo lógica de actualización.

## 5. Riesgos y Mitigación
- **Riesgo:** Sobreescritura de atribución valiosa.
- **Mitigación:** Prioridad a la primera fuente (First Touch).

## 6. Compliance SDD v2.0
- **Soberanía:** `UPDATE patients SET ... WHERE phone = $phone AND tenant_id = $tenant_id`.
