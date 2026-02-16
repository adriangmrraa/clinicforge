# Integración Meta Ads — Documentación Frontend

> Fecha: 2026-02-16 | Versión: 1.0 | Specs: 08, 09, 10

---

## 1. Componentes Nuevos

### 1.1. `MarketingPerformanceCard.tsx` (Spec 09)

**Ubicación**: `frontend_react/src/components/MarketingPerformanceCard.tsx`
**Integrado en**: `DashboardView.tsx`

**Funcionalidad**:
- Muestra KPIs de campañas Meta Ads: Leads, Citas, Tasa de Conversión
- Lista de hasta 5 campañas con detalle de leads y citas
- Consume `GET /admin/marketing/stats`

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

- **Colores**: Se usan paletas suaves (blue-50, blue-100, blue-600) para el branding de Meta Ads
- **Responsive**: Grid de KPIs usa `grid-cols-3` que se adapta al contenedor padre
- **Overflow**: Lista de campañas tiene `max-h-40 overflow-y-auto` para evitar overflow
- **Truncado**: Textos largos usan `truncate` y `line-clamp-2` con `title` tooltip nativo
