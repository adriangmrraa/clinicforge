# Proposal: Mejora de contraste de colores en el odontograma

## Intent

Algunos tratamientos del odontograma usan colores que no se diferencian del fondo oscuro de la UI, haciendo que el profesional no pueda identificar visualmente qué tratamientos están registrados. Específicamente, `restauracion_amalgama` (gris #6b7280), `otra_preexistencia`/`otra_lesion` (gris cálido #78716c) y `necrosis_pulpar` (casi negro #1f2937) son invisibles o prácticamente indistinguibles sobre el fondo oscuro (#0d1117).

## Scope

### In Scope
- Revisión de la paleta completa de 42 estados del odontograma identificando los que no cumplen contraste mínimo
- Cambio de `defaultColor` en los estados problemáticos (frontend TypeScript + shared Python)
- Sincronización de colores en `PRINT_FILLS` del renderizador SVG para PDF si aplica
- Validación visual post-cambio

### Out of Scope
- Cambios en el sistema de `buildStateFills()` (opacidades) — solo colores base
- Agregar campo de color a `treatment_types` en la BD (no existe relación con odontograma)
- Modificar el flujo de `StateConditionModal` (color picker por superficie)
- Agregar tests automáticos de contraste

## Approach

### Análisis de contraste realizado
Contra fondo `#0d1117` (rgb 13, 17, 23):

| Estado | Color Actual | Contraste stroke | Problema |
|--------|-------------|-----------------|----------|
| restauracion_amalgama | `#6b7280` gris | ~4.0:1 (borderline) | fill 12% = invisible |
| otra_preexistencia | `#78716c` gris cálido | ~3.5:1 (insuficiente) | fill 12% = invisible |
| otra_lesion | `#78716c` gris cálido | ~3.5:1 (insuficiente) | fill 12% = invisible |
| necrosis_pulpar | `#1f2937` casi negro | ~1.2:1 (invisible) | fill y stroke = invisibles |
| diente_no_erupcionado | `#a3a3a3` gris claro | ~5.5:1 (aceptable) | borderline, probablemente ok |

### Cambios propuestos

| Estado | Color Actual | Nuevo Color | Rationale |
|--------|-------------|-------------|-----------|
| restauracion_amalgama | `#6b7280` | `#0891b2` (cyan-600) | Metálico visible, distinto de resina (azul) |
| necrosis_pulpar | `#1f2937` | `#831843` (pink-900) | Serio/oscuro pero visible |
| otra_preexistencia | `#78716c` | `#a16207` (amber-700) | Catch-all cálido y visible |
| otra_lesion | `#78716c` | `#be185d` (pink-700) | Distinto de preexistencia, tono lesión |

### Archivos a modificar
1. `frontend_react/src/constants/odontogramStates.ts` → `defaultColor` en 4 estados
2. `shared/odontogram_states.py` → `default_color` en 4 estados (espejo)
3. `orchestrator_service/services/odontogram_svg.py` → `PRINT_FILLS` correspondientes

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `frontend_react/src/constants/odontogramStates.ts` | Modified | `defaultColor` de 4 estados |
| `shared/odontogram_states.py` | Modified | `default_color` de 4 estados (espejo) |
| `orchestrator_service/services/odontogram_svg.py` | Modified | `PRINT_FILLS` sync si aplica |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Los nuevos colores no satisfacen al usuario clínicamente | Med | Proponer colores con significado semántico, dejar que el usuario apruebe |
| Dientes pintados con color nuevo se confunden con otro estado | Bajo | Verificar que el nuevo color no esté ya usado |
| El print PDF se ve distinto | Bajo | `PRINT_FILLS` tiene colores independientes para fondo blanco |

## Rollback Plan

Revertir los cambios en los 3 archivos. Los colores anteriores están documentados en esta proposal y en el diff de git.

## Dependencies

Ninguna — los colores son hardcodeados, no hay migraciones de BD ni cambios de esquema.

## Success Criteria

- [ ] Cada estado problemático tiene un `defaultColor` con contraste ≥ 4.5:1 contra `#0d1117`
- [ ] Los 4 estados modificados se ven claramente distintos entre sí y del fondo
- [ ] El catálogo TypeScript y Python están sincronizados
- [ ] El legend del odontograma muestra los nuevos colores correctamente
- [ ] Print PDF mantiene su paleta de colores para fondo blanco
