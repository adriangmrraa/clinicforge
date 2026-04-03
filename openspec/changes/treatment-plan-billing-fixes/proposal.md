# Proposal: Treatment Plan Billing — Fixes & Stabilization

**Change**: treatment-plan-billing-fixes
**Parent**: treatment-plan-billing
**Status**: Draft
**Date**: 2026-04-03

---

## Intent

Corregir los 32 desfasajes encontrados por SDD-VERIFY entre las specs y la implementación del sistema de presupuesto y facturación. Sin estos fixes, el sistema tiene crasheos en runtime, errores de tipo en DB, inconsistencias de datos, y gaps de UX.

## Problem Statement

La implementación fue realizada por múltiples agentes en sesiones separadas, lo que introdujo:
- **8 bugs CRITICAL** que causan crashes, errores de DB, o pérdida de datos
- **12 issues HIGH** que rompen funcionalidad esperada o violan la spec
- **12 issues MEDIUM** de consistencia, naming, y UX

El sistema NO puede ir a producción sin resolver al menos los CRITICAL y HIGH.

## Scope

### In Scope
- Fix de los 8 CRITICAL (runtime crashes, DB type errors, missing logic)
- Fix de los 12 HIGH (migration types, response shapes, missing features)
- Fix de los 12 MEDIUM (naming, status codes, i18n, timezone)

### Out of Scope
- Nuevas features
- Refactoring de código no relacionado
- Tests E2E (se cubren con tests unitarios de los fixes)

## Approach

3 fases ordenadas por severidad:
1. **FASE CRITICAL**: 8 fixes que previenen crashes y corrupción de datos
2. **FASE HIGH**: 12 fixes funcionales y de migración
3. **FASE MEDIUM**: 12 fixes de consistencia y polish

## Risks

| Risk | Mitigation |
|------|------------|
| Migration 018 ya aplicada en algún entorno | Crear migration 019 correctiva (ALTER, no DROP+CREATE) |
| Cambios en schemas Pydantic rompen requests existentes | Backward compatible: hacer campos Optional, no remover |
| Nova tools modificados rompen flujo de voz | Additive changes only, no remover parámetros |

## Success Criteria

- 0 CRITICAL findings en re-verificación
- 0 HIGH findings en re-verificación
- Todos los tests existentes siguen pasando (88 tests)
- Nuevos tests cubren cada fix CRITICAL
