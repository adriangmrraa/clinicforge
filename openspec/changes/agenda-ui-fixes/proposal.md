# SDD Proposal: Retoques y Mejoras UI Agenda

**Change**: `agenda-ui-fixes`
**Ticket**: DLD-34
**Status**: PROPOSED
**Date**: 2026-04-22
**Author**: SDD Orchestrator

---

## 1. Intent

### Problem Statement

La vista de agenda presenta dos problemas visuales que degradan la experiencia en desktop:

**A. Vista Mes — textos ilegibles en desktop**: Los eventos renderizados por `AppointmentCard.tsx` usan `text-[10px]` fijo para la hora y el nombre del paciente en la variante `isMonthView`. No hay breakpoints responsive (`md:`, `lg:`), lo que hace el texto ilegible en pantallas grandes donde los cells del mes tienen espacio suficiente para mostrar más información.

**B. Vista Semana — gap/hueco visual superior**: El header sticky introducido en DLD-29 genera un gap visible entre el toolbar y la grilla de la semana. El origen es una combinación de `border-spacing` no nulo en `.fc-scrollgrid` (FullCalendar usa `border-collapse: separate` por defecto) y el padding del toolbar que desajusta el offset del header pegajoso.

### Why This Matters

- **Legibilidad**: En la vista mes de un desktop 1920×1080, los textos de `10px` son ilegibles sin zoom. El personal de la clínica consulta la agenda en monitores, no solo en mobile.
- **Profesionalismo visual**: El gap en la vista semana parece un bug de renderizado y rompe la consistencia visual del diseño dark.
- **Impacto de la fix**: Ambos problemas se resuelven con cambios CSS/Tailwind puntuales — sin lógica nueva, sin migraciones, sin endpoints.

---

## 2. Scope

### In Scope

| Area | Archivos | Qué cambia |
|------|----------|-----------|
| Textos vista Mes | `frontend_react/src/components/AppointmentCard.tsx` | Clases de tamaño de texto e inner padding con breakpoints responsive |
| Gap vista Semana | `frontend_react/src/views/AgendaView.tsx` (bloque CSS inline o clase global) | Forzar `border-spacing: 0` en `.fc-scrollgrid`; ajustar padding toolbar si necesario |

### Out of Scope

- Rediseño completo de la vista Semana estilo Google Calendar (cambio futuro independiente)
- Cambios en `MobileAgenda` (componente separado, ya funciona correctamente en mobile)
- Cualquier modificación a lógica de negocio, endpoints, o base de datos
- Cambios en otras vistas (Día, Lista) salvo que se detecte regresión al implementar

---

## 3. Approach

### Fix A — Textos responsivos en vista Mes

`AppointmentCard.tsx` en el bloque `isMonthView` usa clases Tailwind hardcodeadas sin breakpoints. El cambio es puramente aditivo: extender las clases existentes con variantes `md:` para que el texto escale en pantallas ≥768px. El componente mobile (`MobileAgenda`) no se toca porque es un componente separado.

La lógica es: `text-[10px]` queda para mobile (el breakpoint de `<768px` que ya usa la agenda), y `md:text-xs` activa en tablet/desktop donde el espacio del cell lo permite. El padding vertical del contenedor sigue la misma lógica.

### Fix B — Eliminar gap en vista Semana

FullCalendar genera un `<table>` con clase `.fc-scrollgrid` que usa `border-collapse: separate`. En algunos temas, el `border-spacing` por defecto no es `0`, lo que produce un gap visual de 1-2px entre rows. Con el header sticky de DLD-29, ese gap se amplifica visualmente porque el header se superpone al borde superior.

La corrección es agregar `.fc-scrollgrid { border-spacing: 0 !important }` en el bloque de estilos CSS de `AgendaView.tsx`. Si tras esa corrección persiste el desajuste de offset, se ajusta el padding del toolbar de `8px` a `4–6px` para compensar.

Este enfoque es preferible a modificar `--fc-toolbar-height` porque ese custom property afecta todos los viewports y puede generar nuevos desajustes en mobile.

---

## 4. Rollback Plan

### Risk Level: MÍNIMO

Ambos cambios son puramente visuales y CSS-bound. No hay cambios de lógica, schema, ni endpoints.

- **Rollback**: `git revert <commit>` — el servicio frontend no necesita reinicio de backend.
- **Feature flag**: No aplica. Los cambios son visualmente aditivos y no afectan mobile ni lógica de negocio.

---

## 5. Risks

| Riesgo | Severidad | Mitigación |
|--------|-----------|-----------|
| El cambio `md:text-xs` en vista Mes afecta móvil | BAJO | El breakpoint `md:` activa a partir de 768px. La agenda ya hace el corte mobile/desktop exactamente en ese punto con `MobileAgenda`. Sin riesgo de colisión. |
| `.fc-scrollgrid { border-spacing: 0 }` afecta vista Día/Lista | BAJO | FullCalendar aplica el mismo `.fc-scrollgrid` en todas las vistas de grilla. Verificar visualmente vista Día post-fix. El impacto esperado es neutro o positivo (misma fix aplica). |
| Ajuste de padding toolbar genera nuevo desajuste | BAJO | El ajuste de padding es condicional (solo si persiste el gap post `border-spacing: 0`). Se evalúa visualmente antes de committear. |
| Regresión en otros breakpoints de AppointmentCard | BAJO | El componente solo tiene el bloque `isMonthView` con clases de texto fijas. Los otros bloques (isWeekView, isDayView) no se tocan. |

---

## 6. Success Criteria

- [ ] En viewport 1920×1080, vista Mes: textos de hora y nombre de paciente legibles sin zoom
- [ ] En viewport 768px (tablet), vista Mes: textos proporcionados y sin overflow
- [ ] En viewport <768px: sin cambio visual (usa `MobileAgenda`, `AppointmentCard` no renderiza)
- [ ] Vista Semana: sin gap visual entre toolbar y grilla de horarios
- [ ] Vista Día: sin regresión visual
- [ ] Vista Lista: sin regresión visual
- [ ] Mobile en todas las vistas: sin regresión
