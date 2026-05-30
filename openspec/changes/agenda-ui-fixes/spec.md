# SDD Spec: Retoques y Mejoras UI Agenda

**Change**: `agenda-ui-fixes`
**Ticket**: DLD-34
**Status**: DRAFT
**Date**: 2026-04-22
**Author**: SDD Orchestrator

---

## 1. Requirements

| ID | Requisito | Prioridad |
|----|-----------|-----------|
| REQ-1 | Los textos de hora y nombre del paciente en la vista Mes son legibles en desktop (≥768px) sin necesidad de zoom | MUST |
| REQ-2 | En viewport <768px la vista Mes no tiene cambios visuales (sigue usando `MobileAgenda`) | MUST |
| REQ-3 | La vista Semana no presenta gap ni hueco visual entre el toolbar y la grilla de horarios | MUST |
| REQ-4 | La vista Día no presenta regresión visual respecto al estado actual | MUST |
| REQ-5 | La vista Lista no presenta regresión visual respecto al estado actual | MUST |
| REQ-6 | Los cambios no alteran lógica de negocio, endpoints, ni schema de base de datos | MUST |

---

## 2. Scenarios

### SC-1 — Vista Mes en desktop 1920×1080
- **Dado** que el usuario tiene la agenda en vista Mes en un monitor 1920×1080
- **Cuando** hay turnos cargados en el mes
- **Entonces** la hora del turno y el nombre del paciente son legibles sin hacer zoom (tamaño ≥ `text-xs` / 12px en la tarjeta)

### SC-2 — Vista Mes en tablet 768px
- **Dado** que el usuario tiene la agenda en vista Mes en un viewport de exactamente 768px de ancho
- **Cuando** hay turnos cargados en el mes
- **Entonces** los textos son proporcionales al tamaño del cell y no generan overflow ni truncamiento incorrecto

### SC-3 — Vista Mes en mobile <768px
- **Dado** que el usuario tiene la agenda en un viewport <768px
- **Cuando** navega a la vista Mes
- **Entonces** se renderiza `MobileAgenda` (no `AppointmentCard`) y el comportamiento visual es idéntico al estado previo al cambio

### SC-4 — Vista Semana sin gap superior
- **Dado** que el usuario tiene la agenda en vista Semana
- **Cuando** hace scroll hacia arriba hasta el tope de la grilla
- **Entonces** el header sticky y la grilla de horarios están alineados sin gap visible entre ellos

### SC-5 — Vista Día sin regresión
- **Dado** que el usuario tiene la agenda en vista Día
- **Cuando** navega entre días y hace scroll
- **Entonces** el layout visual es idéntico al estado previo al cambio (sin gaps ni textos alterados)

### SC-6 — Vista Lista sin regresión
- **Dado** que el usuario tiene la agenda en vista Lista
- **Cuando** hay turnos listados
- **Entonces** el layout visual es idéntico al estado previo al cambio

---

## 3. Technical Changes

### 3.1 `frontend_react/src/components/AppointmentCard.tsx`

Bloque `isMonthView` — cambios de clases Tailwind:

| Elemento | Clase actual | Clase nueva |
|----------|-------------|------------|
| Texto hora del turno | `text-[10px]` | `text-[10px] md:text-xs` |
| Texto nombre del paciente | `text-[10px]` | `text-[10px] md:text-xs` |
| Contenedor interno (padding vertical) | `py-0.5` | `py-0.5 md:py-1` |

Reglas de aplicación:
- Solo aplica al bloque condicional `isMonthView === true`
- Los bloques `isWeekView` e `isDayView` de `AppointmentCard` no se tocan
- No se agrega ninguna lógica JS/TS nueva — solo cambio de clases Tailwind
- No se agrega ningún `breakpoints` import ni helper — Tailwind maneja el responsive por CSS puro

### 3.2 `frontend_react/src/views/AgendaView.tsx`

Bloque de estilos CSS (el componente ya contiene un bloque `<style>` o equivalente para las customizaciones de FullCalendar):

**Regla 1 — Eliminar border-spacing:**
```
.fc-scrollgrid {
  border-spacing: 0 !important;
}
```

**Regla 2 — Ajuste de padding toolbar (condicional):**
Solo agregar si tras la regla 1 persiste el gap visual:
```
.fc-toolbar {
  padding-top: 4px !important;
  padding-bottom: 4px !important;
}
```

Criterio para activar regla 2: si en QA manual vista Semana aún muestra gap ≥1px entre toolbar y grilla con solo la regla 1 aplicada.

**Reglas de alcance:**
- No modificar `--fc-toolbar-height` (afecta todos los viewports)
- No agregar media queries específicas para este fix (el `border-spacing: 0` es correcto para todos los viewports)
- No tocar el CSS de vista Día ni Lista (la fix aplica globalmente via `.fc-scrollgrid` y es inerte en esas vistas si no generan gap)

---

## 4. Non-Functional Requirements

- **Rendimiento**: Sin impacto. Cambios son CSS puro sin JS adicional.
- **Accesibilidad**: La mejora de legibilidad de texto es aditiva respecto a accesibilidad.
- **Internacionalización**: Sin impacto. No se agregan ni modifican textos visibles.
- **Multi-tenancy**: Sin impacto. Los cambios aplican a todos los tenants por igual (corrección visual universal).

---

## 5. Out of Scope

- Rediseño completo de vista Semana estilo Google Calendar (cambio futuro, requiere análisis propio)
- Cambios en `MobileAgenda` (componente separado, fuera de este ticket)
- Cualquier cambio en `orchestrator_service/`, `bff_service/`, o `whatsapp_service/`
- Cambios en migraciones Alembic o modelos SQLAlchemy
- Modificaciones a la lógica de renderizado de `FullCalendar` (plugins, views, event handlers)
- Cambios de color, iconografía, o paleta del design system (el dark mode palette no cambia)
