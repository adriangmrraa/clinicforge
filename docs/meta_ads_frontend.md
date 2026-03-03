# Integración Meta Ads — Documentación Frontend

> Fecha: 2026-02-16 | Versión: 1.1 | Specs: 13, 14

---

## 1. Componentes Nuevos

### 1.1. `MarketingPerformanceCard.tsx` (Spec 09)

**Ubicación**: `frontend_react/src/components/MarketingPerformanceCard.tsx`
**Integrado en**: `DashboardView.tsx`

**Funcionalidad**:
- Muestra KPIs generales: Inversión, Retorno (Revenue), CPA (Costo por Adquisición).
- Dos pestañas (**Campaigns** / **Creatives**):
    - **Campaigns**: Rendimiento agrupado por campaña Meta.
    - **Creatives**: Rendimiento granular por anuncio (Master Ad List).
- Filtro de periodo integrado (sincronizado con Dashboard).
- Soporte para rango "Lifetime" (Máximo historial).
- Consume `GET /admin/marketing/stats`.

**Estados**:
| Estado | Render |
|--------|--------|
| Loading | Spinner con `Loader2` |
| Error / Sin datos | Mensaje "Sin datos de campañas" |
| OK | KPIs grid (3 columnas) + tabla de campañas |

**Interfaces**:
```typescript
interface CampaignStat {
    campaign_name: string;
    ad_id: string;
    ad_headline: string;
    leads: number;
    appointments: number;
    conversion_rate: number;
}

interface MarketingSummary {
    total_leads: number;
    total_appointments: number;
    overall_conversion_rate: number;
}
```

---

### 1.2. `AdContextCard.tsx` (Spec 10)

**Ubicación**: `frontend_react/src/components/AdContextCard.tsx`
**Integrado en**: `ChatsView.tsx`

**Funcionalidad**:
- Muestra el contexto del anuncio (headline, body) al inicio de un chat
- Solo se renderiza si el paciente tiene `acquisition_source !== 'ORGANIC'` y `meta_ad_headline` presente

**Props**:
```typescript
interface AdContextCardProps {
    headline?: string;    // Título del anuncio
    body?: string;        // Cuerpo del anuncio
    sourceUrl?: string;   // URL del anuncio (no se usa aún)
}
```

**Condición de render** (en `ChatsView.tsx`):
```tsx
{selectedSession && patientContext?.patient?.acquisition_source &&
  patientContext.patient.acquisition_source !== 'ORGANIC' &&
  patientContext.patient.meta_ad_headline && (
    <AdContextCard
      headline={patientContext.patient.meta_ad_headline}
      body={patientContext.patient.meta_ad_body}
    />
  )}

---

### 1.3. `MetaTokenBanner.tsx` [NEW]

**Ubicación**: `frontend_react/src/components/MetaTokenBanner.tsx`
**Integrado en**: `Layout.tsx`

**Funcionalidad**:
- Muestra una alerta global si la conexión con Meta vence en < 7 días.
- Botón "Reconectar" que redirige al Hub con el flag `?autoConnect=true`.
- Consume `GET /admin/meta/status`.

---

### 1.4. `MetaConnectionWizard.tsx` [NEW]

**Ubicación**: `frontend_react/src/components/MetaConnectionWizard.tsx`
**Integrado en**: `MarketingHubView.tsx`

**Funcionalidad**:
- Guía al usuario en la selección de la Ad Account y Portfolio después de conectar Meta.
- Soporta búsqueda de cuentas tanto propias como de clientes ("Client Accounts").
- Persiste la selección vía `POST /admin/marketing/meta/connect`.
```

---

## 2. Archivos Modificados

### 2.1. `PatientDetail.tsx` (Spec 08)

**Cambios**:
- Interfaz `Patient` extendida con:
  ```typescript
  acquisition_source?: string;
  meta_ad_id?: string;
  meta_ad_headline?: string;
  meta_campaign_id?: string;
  ```
- Badge "Meta Ads" con icono `Megaphone` cuando `acquisition_source === 'META_ADS'`
- Tooltip con `meta_ad_headline` y `meta_campaign_id`

### 2.2. `DashboardView.tsx` (Spec 09)

**Cambios**:
- Import de `MarketingPerformanceCard`
- Renderizado entre los gráficos de actividad y la tabla de urgencias

### 2.3. `ChatsView.tsx` (Spec 10)

**Cambios**:
- Interfaz `PatientContext` extendida con campo `patient` que incluye Meta Ads fields
- Import de `AdContextCard`
- Render condicional antes del listado de mensajes

### 2.4. `axios.ts` & `AuthContext.tsx` [MODIFIED]

**Cambios Críticos**:
- **`AuthContext.tsx`**: Persiste el `tenant_id` en `localStorage` tras el login exitoso.
- **`axios.ts`**: Interceptor de request que agrega el header `X-Tenant-ID` usando el valor de `localStorage`. Esto es vital para que el backend resuelva las credenciales correctas de Meta.

---

## 3. Dependencias de Iconos

Todos los iconos usados provienen de `lucide-react`:
- `Megaphone` — Badge Meta Ads y cards
- `TrendingUp` — KPI de conversión
- `Users` — KPI de leads
- `CalendarCheck` — KPI de citas
- `Loader2` — Spinner de carga
- `ExternalLink` — Link al anuncio original

---

## 4. API Endpoints Consumidos

| Componente | Endpoint | Método |
|-----------|----------|--------|
| `MarketingPerformanceCard` | `/admin/marketing/stats` | GET |
| `AdContextCard` (vía `ChatsView`) | `/admin/patients/phone/{phone}/context` | GET |
| `PatientDetail` (existente) | `/admin/patients/{id}` | GET |

---

## 5. Notas de Diseño

- **Colores**: Se usan paletas suaves (blue-50, blue-100, blue-600) para el branding de Meta Ads.
- **Responsive (Stacking Pattern)**: 
    - En Desktop (MD+): Grillas laterales y tablas densas.
    - En Mobile (< MD): Las tablas se transforman en "Cards Stacking", donde cada fila es una card con labels claros para facilitar la lectura táctil.
- **i18n Universal**: Todas las llaves del Marketing Hub (`total_investment`, `leads`, `roi`, etc.) están localizadas en `es.json` y `en.json`.
- **Truncado**: Textos largos usan `truncate` y `line-clamp-2` con `title` tooltip nativo.

---

## 6. Patrones de UI Multi-canal (Fase 14)

Se implementó un sistema de "Contexto Visual Inmersivo" para diferenciar los canales de origen.

### 6.1. Identidad por Platform Config
La función `getPlatformConfig(channel)` en `ChatsView.tsx` mapea:

| Canal | Color Primario | Icono | Badge |
|-------|----------------|-------|-------|
| **WhatsApp** | Green-600 | `MessageCircle` | Verde / WA |
| **Instagram** | Pink-600 | `Instagram` | Violeta / IG |
| **Facebook** | Blue-600 | `Facebook` | Azul / FB |

### 6.2. Elementos de Acento
- **Borde Lateral**: El chat seleccionado adquiere un borde lateral de `4px` con el color de la plataforma.
- **Burbujas de Respuesta**: El fondo de los mensajes del asistente (`role="assistant"`) cambia al color de la plataforma.
- **Inputs dinámicos**: El foco del campo de texto y el botón "Enviar" se tiñen con el color del canal activo.
- **Avatares Reales**: Priorización de `customer_avatar` de Meta sobre las iniciales genéricas.

---

## 7. Protocolo de Conexión (OAuth Popup)

### 7.1. Flujo de Ventana Emergente
1. El usuario hace clic en "Conectar con Meta".
2. Se abre un popup a `/admin/meta/auth` (Backend).
3. Tras la autorización en Facebook, Meta redirecciona al callback del Backend.
4. El Backend cierra el popup mediante una página HTML que emite un evento `postMessage` al `window.opener`.
5. El Frontend captura el mensaje y refresca el estado de conexión.

### 7.2. Redirección Post-Conexión
El Backend usa la variable de entorno `FRONTEND_URL` para construir la URL de retorno. En desarrollo debe ser `http://localhost:3000/`.

---

## 8. Integración con Google Ads (NUEVO - Marzo 2026)

### 8.1. MarketingHubView Actualizado
**Ubicación**: `frontend_react/src/views/MarketingHubView.tsx`
**Nueva funcionalidad**: Dashboard combinado con 3 tabs:
1. **Meta Ads** - Funcionalidad existente
2. **Google Ads** - Nueva integración completa
3. **Combinado** - Estadísticas unificadas de ambas plataformas

**Características**:
- ✅ **Tabs platform-specific** con iconos distintivos (Megaphone, Globe, BarChart3)
- ✅ **Banners de conexión dinámicos** por plataforma (colores diferentes)
- ✅ **Time range selector** sincronizado entre todas las tabs
- ✅ **Auto-refresh** de datos al cambiar entre plataformas

### 8.2. GoogleConnectionWizard
**Ubicación**: `frontend_react/src/components/integrations/GoogleConnectionWizard.tsx`
**Diseño**: Consistente con MetaConnectionWizard (mismo UX/UI)
**Flujo**: 4 steps:
1. **Welcome** - Beneficios y estado de configuración
2. **Configure** - Configuración manual (si es necesario)
3. **Authorize** - Ventana OAuth de Google
4. **Complete** - Confirmación de conexión exitosa

### 8.3. API Client para Google Ads
**Ubicación**: `frontend_react/src/api/google_ads.ts`
**Características**:
- ✅ **11 métodos API** bien tipados
- ✅ **Formateo de currency** (micros → ARS/USD)
- ✅ **Demo data fallback** cuando API no disponible
- ✅ **Error handling robusto** con mensajes amigables

### 8.4. Tipos TypeScript
**Ubicación**: `frontend_react/src/types/google_ads.ts`
**Cobertura**: 15+ interfaces para Google Ads API
- `GoogleCampaign`, `GoogleMetrics`, `GoogleCustomer`
- `GoogleConnectionStatus`, `CombinedStats`
- `MultiPlatformCampaign`, `PlatformStatus`

### 8.5. Traducciones
**Archivos actualizados**:
- `frontend_react/src/locales/es.json` - 150+ strings nuevos
- `frontend_react/src/locales/en.json` - 150+ strings nuevos
**Categorías**: wizard, métricas, errores, tablas, botones

### 8.6. Comparación UX Meta vs Google
| Aspecto | Meta Ads | Google Ads |
|---------|----------|------------|
| **Wizard Steps** | 3 steps | 4 steps |
| **OAuth Window** | Popup Meta | Popup Google |
| **Connection Banner** | Verde (Meta) | Azul (Google) |
| **Metrics Display** | Leads, Appointments, ROI | Impressions, Clicks, ROAS |
| **Demo Data** | Sí | Sí |
| **Manual Sync** | No | Sí (botón "Sincronizar") |

### 8.7. Flujo de Usuario Unificado
1. **Navegar** a Marketing Hub (`/marketing`)
2. **Seleccionar** tab "Google Ads" o "Meta Ads"
3. **Conectar** cuenta (wizard paso a paso)
4. **Ver métricas** en dashboard en tiempo real
5. **Comparar** plataformas en tab "Combinado"

### 8.8. Estados de Conexión
```typescript
type ConnectionStatus = {
  meta: {
    connected: boolean;
    has_token: boolean;
    has_account: boolean;
  };
  google: {
    connected: boolean;
    has_token: boolean;
    has_developer_token: boolean;
    email?: string;
  };
};
```

### 8.9. Recomendaciones de Implementación
1. **Meta Ads primero**: Conectar Meta Ads para leads de WhatsApp
2. **Google Ads después**: Conectar Google Ads para campañas de búsqueda
3. **Dashboard combinado**: Usar tab "Combinado" para análisis ROI cross-platform
4. **Demo mode**: Probar sin credenciales reales (datos de demostración)

**Documentación completa**: Ver [google_ads_integration.md](google_ads_integration.md)
