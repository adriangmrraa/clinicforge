# Especificación Técnica: Mission 3 - Meta Marketing Hub & ROI Forge

Esta especificación detalla la implementación de un panel centralizado para gestionar campañas de Meta Ads, auditar métricas de rendimiento y configurar la atribución de leads directamente desde Dentalogic.

## 1. Objetivos
- **Visibilidad Total**: Dashboard para visualizar campañas, ad sets y anuncios con métricas de Meta (Spend, Clicks, CTR, ROI).
- **Conectividad Simplificada**: Implementar "Meta Login" para que el CEO pueda conectar su cuenta publicitaria sin configurar variables de entorno manuales.
- **Acceso Directo**: Integrar "Plantillas HSM" y "Marketing Hub" en el Sidebar principal.
- **Atribución Inteligente**: Cruce automático entre mensajes entrantes de WhatsApp y metadatos de campaña para calcular el ROI real por anuncio.

## 2. Requerimientos de UI (Frontend)

### 2.1 Navigation (Sidebar)
- Nuevo item: **Marketing Hub** (Icono: `Megaphone` o `BarChart3`).
- Nuevo item: **Plantillas HSM** (Icono: `MessageSquare` o `ClockCheck`).

### 2.2 Marketing Hub Dashboard
- **Vista de Cuentas**: Lista de Ad Accounts vinculadas.
- **Vista de Campañas**: Tabla con:
    - Nombre del Anuncio / Campaña.
    - Estado (Active, Paused).
    - Métricas de Meta: Inversión, Clicks, CPC.
    - Métricas de Dentalogic: Leads generados, Citas agendadas.
    - **KPI Estrella**: ROI Real (Revenue / Spend).
- **Botón "Conectar cuenta de Meta"**: Lanza el popup de OAuth.

### 2.3 HSM Templates View
- Mover a la barra lateral (Sidebar) para acceso global.
- Permitir previsualización de plantillas aprobadas.

## 3. Requerimientos Técnicos (Backend)

### 3.1 Meta OAuth Flow (Token Exchange)
El sistema implementará el flujo de canje de 3 niveles para asegurar persistencia:
1. **Fase 1 (Frontend)**: El CEO inicia sesión y obtiene un `Short-Lived User Token` (validez: 2h).
2. **Fase 2 (Backend Exchange)**: 
    - El backend envía el token a `GET /oauth/access_token` con el `META_APP_SECRET`.
    - Resultado: `Long-Lived User Token` (validez: 60 días).
3. **Fase 3 (Permanent Retrieval)**:
    - Se consulta `GET /me/accounts` usando el token de 60 días.
    - Resultado: `Permanent Page Access Tokens` para los activos (Páginas/WhatsApp). No expiran.
4. **Ad Account Management**:
    - Para métricas de Ads, se usará el `Long-Lived User Token` (60 días). El sistema notificará al CEO 7 días antes de la expiración para una re-conexión rápida de un solo clic.

### 3.2 Credential Storage Strategy
- Los tokens permanentes (Páginas/WA) se guardarán en `credentials` con `category='meta_page'`.
- El User Token (Marketing API) se guardará con `category='meta_user_long'`.

### 3.2 Attribution Engine
- El webhook de WhatsApp (YCloud) debe extraer el `referral` object.
- Guardar `meta_ad_id`, `meta_campaign_id` y `meta_adset_id` en el registro del paciente/lead.
- Reportar eventos de conversión (Cita agendada, Tratamiento pagado) de vuelta a Meta CAPI (opcional/fase 2).

## 4. Esquema de Datos (Adiciones)
- **Table `credentials`**: Extender tipos para `META_USER_ACCESS_TOKEN`, `META_BUSINESS_ID`, `META_SELECTED_AD_ACCOUNT`.
- **Table `automation_logs`**: Ya implementada, se usará para reportar estados de entrega de HSM.

## 5. Diseño de Componentes
- `MetaMarketingHub.tsx`: Vista principal de campañas.
- `MetaConnectPopup.tsx`: Modal para el flujo de autenticación.
- `CampaignMetricTable.tsx`: Tabla granular de rendimiento.

## 7. Clarificaciones y Reglas de Negocio
- **Relación 1:1**: Cada clínica (`tenant`) solo puede tener una única `Ad Account` vinculada.
- **Acceso Restringido**: Las vistas de **Marketing Hub** y **Plantillas HSM** son exclusivas para el rol `CEO`.
- **Atribución Inmortal**: Los datos de origen (`meta_ad_id`, etc.) en el paciente deben ser persistentes y no sobrescribirse, permitiendo ver el embudo completo desde Lead hasta Paciente.
- **Ventana Temporal**: El dashboard cargará por defecto los últimos **30 días**.
- **Consolidación de Interfaz**: Se eliminará la pestaña de "Meta Ads" de la sección de Configuración para centralizar tanto la conexión (OAuth) como la visualización en el nuevo **Marketing Hub**.

## 8. Criterios de Aceptación Actualizados
- [x] El CEO puede conectar su cuenta de Meta via popup.
- [x] El Sidebar muestra los logos de Marketing y Plantillas (Solo para CEO).
- [ ] Filtrado por Clínica en el Dashboard de Marketing.
- [ ] Visualización del funnel: Lead proveniente de Ads -> Paciente con tratamiento.
