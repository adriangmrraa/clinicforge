# Diagnóstico Técnico: Misión 1 - Meta Ads (Cierre de Brecha)

## 1. Análisis de Estado Actual (Gap Analysis)

| Componente | Estado | Detalle Técnico |
| :--- | :--- | :--- |
| **Atribución de Leads** | ✅ Funcional | El `chat_endpoint` captura el objeto `referral` y lo guarda en la tabla `patients`. |
| **Enriquecimiento (Ads API)** | ✅ Funcional | `enrich_patient_attribution` asíncrono descarga nombres de campaña/anuncio vía Graph API. |
| **Métricas de Conversión** | ⚠️ Parcial | El endpoint `/admin/marketing/stats` cruza leads con citas, pero **no tiene datos de gasto (Spend)**. |
| **Cálculo de ROI** | ❌ Faltante | No hay integración con la API de *Ads Insights* para obtener el costo por lead/ad. |
| **Settings / Templates UI** | ❌ Mock | `MetaTemplatesView.tsx` es estático. No permite gestionar ni enviar plantillas HSM. |

## 2. Plan de Acción (Misión 1)

### Paso 1: Backend - Marketing Insights & ROI
- **MetaAdsClient**: Implementar `get_ads_insights(time_range)` para obtener el gasto publicitario de Meta.
- **Analytics logic**: Modificar `/admin/marketing/stats` para cruzar:
    - (Ingreso Estimado) - (Gasto Meta Ads) = **ROI Real**.
- **Templates API**: Crear `GET /admin/marketing/templates` (proxy a YCloud) para listar plantillas aprobadas.

### Paso 2: Frontend - UI Funcional
- **MetaTemplatesView**: 
    1. Reemplazar el mock por una tabla dinámica de plantillas.
    2. Botón "Sincronizar con Meta" para refrescar el catálogo.
- **MarketingPerformanceCard**: Añadir campos de "Gasto Total" y "ROI" al componente del Dashboard.

---

# /specify: Misión 2 - Motor de Automatización YCloud (HSM) v1.1

## 1. Objetivo
Automatizar el ciclo de vida del paciente (Lead -> Cita -> Feedback) mediante el envío proactivo de plantillas HSM (High Security Messages) de WhatsApp, superando la restricción de las 24 horas.

## 2. Esquema de Datos (Evolución)

### Tabla `tenants` [MODIFICACIÓN]
- `timezone`: VARCHAR(50) DEFAULT 'America/Argentina/Buenos_Aires'. (Permite selector en UI para el CEO).

### Tabla `automation_logs` [NUEVA]
- `id`: UUID.
- `tenant_id`: INT (FK).
- `patient_id`: INT (FK).
- `appointment_id`: INT (FK, opcional).
- `type`: VARCHAR ("REMAINDER_24H", "FEEDBACK_45M", "LEAD_RECOVERY").
- `status`: VARCHAR ("pending", "sent", "failed", "delivered", "read").
- `error_message`: TEXT (Para registrar fallos de YCloud/Meta).
- `template_name`: VARCHAR.
- `sent_at`: TIMESTAMP.

### Tabla `appointments` [MODIFICACIÓN]
- `feedback_sent`: BOOLEAN (Default FALSE).

## 3. Lógica de Negocio (Triggers)

### A. Confirmación Pre-Turno (24h)
- **Filtro**: `appointments` con `status = 'confirmed'`, `appointment_datetime` entre T-24h y T-25h (ajustado por el `timezone` del tenant).
- **Acción**: Enviar plantilla `confirmacion_cita_24h`.

### B. Feedback Post-Consulta (45m)
- **Filtro**: `appointments` con `status = 'completed'`, `updated_at` hace ~45 min, `feedback_sent = FALSE`.
- **Persistencia**: Aunque se agende un nuevo turno para el futuro, este trigger debe dispararse basándose en el turno marcado como `completed`.

### C. Seguimiento de Leads (Recuperación)
- **Filtro**: `patients` que contactaron vía Meta Ads, sin turnos agendados, sin actividad reciente.

## 4. Orquestación y Resiliencia
- **Manejo de Errores**: Si YCloud devuelve un error de rate-limit (429), reintentar con backoff. Si es error de plantilla inexistente, marcar como `failed` y alertar en logs de auditoría.
- **Transparencia**: El sistema debe registrar cada paso en `automation_logs` para que sea visible en la UI.

## 5. UI de Automatización (Transparencia Total)
- Una vista que explique el flujo "Detrás de escena":
    1. Listado de plantillas aprobadas.
    2. Historial de envíos con estados en tiempo real (Enviado -> Entregado -> Leído).
    3. Métricas estratégicas: Tasa de conversión de leads recuperados y tasa de respuesta de feedback.
