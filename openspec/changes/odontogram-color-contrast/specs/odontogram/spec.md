# Spec Odontogram: Color Contrast Enhancement

**Change:** `odontogram-color-contrast`
**Date:** 2026-05-19
**Status:** Spec
**Target:** `frontend_react/src/constants/odontogramStates.ts`, `shared/odontogram_states.py`, `orchestrator_service/services/odontogram_svg.py`

---

## Purpose

The odontogram renders 42 clinical states on a dark-themed UI (background ~`#0d1117`). Some states use colors that lack sufficient contrast, making them invisible or hard to distinguish. This spec defines minimum contrast requirements and the specific color changes needed to ensure all states are clearly distinguishable from the background and from each other.

## Requirements

### R1: Minimum Contrast Ratio

Every state's `defaultColor` MUST have a WCAG contrast ratio of at least **3.0:1** (AA Large) against the dark background `#0d1117` when rendered as SVG stroke (100% opacity).

#### Scenario: Verify contrast for restauracion_amalgama

- GIVEN the odontogram state `restauracion_amalgama`
- WHEN its `defaultColor` is evaluated against background `#0d1117`
- THEN the contrast ratio MUST be ≥ 3.0:1

#### Scenario: Verify contrast for necrosis_pulpar

- GIVEN the odontogram state `necrosis_pulpar`
- WHEN its `defaultColor` is evaluated against background `#0d1117`
- THEN the contrast ratio MUST be ≥ 3.0:1

#### Scenario: Verify contrast for otra_preexistencia

- GIVEN the odontogram state `otra_preexistencia`
- WHEN its `defaultColor` is evaluated against background `#0d1117`
- THEN the contrast ratio MUST be ≥ 3.0:1

#### Scenario: Verify contrast for otra_lesion

- GIVEN the odontogram state `otra_lesion`
- WHEN its `defaultColor` is evaluated against background `#0d1117`
- THEN the contrast ratio MUST be ≥ 3.0:1

#### Scenario: Verify non-regression of existing colors

- GIVEN any of the remaining 38 odontogram states
- WHEN their `defaultColor` is evaluated against background `#0d1117`
- THEN the contrast ratio MUST remain ≥ 3.0:1 (no color SHOULD be degraded)

### R2: Color Distinctiveness

Each modified state's `defaultColor` MUST be visually distinct from all other states' colors on the dark background. No two states SHOULD share the same `defaultColor`.

#### Scenario: Amalgama distinct from resina

- GIVEN the odontogram states `restauracion_amalgama` and `restauracion_resina`
- WHEN both are rendered on dark background
- THEN they MUST be visually distinguishable from each other

#### Scenario: Lesion distinct from preexistente

- GIVEN the states `otra_lesion` and `otra_preexistencia`
- WHEN both are rendered on dark background
- THEN they MUST use different colors

### R3: Cross-Platform Synchronization

The `defaultColor` values in the TypeScript catalog and the Python catalog MUST be identical for all 42 states.

#### Scenario: TypeScript and Python catalogs match

- GIVEN `frontend_react/src/constants/odontogramStates.ts` and `shared/odontogram_states.py`
- WHEN comparing `defaultColor` (TS) and `default_color` (Python) for each state
- THEN they MUST be identical for all 42 states

### R4: Print Output Integrity

The print/SVG output (`odontogram_svg.py`) MUST continue using white-background-optimized colors (`PRINT_FILLS`). Changes to screen colors MUST NOT modify print colors unless they conflict.

#### Scenario: Print colors unchanged for modified states

- GIVEN a state whose `defaultColor` was modified (e.g., `restauracion_amalgama`)
- WHEN rendering the odontogram SVG for PDF
- THEN the print colors in `PRINT_FILLS` MUST remain the original white-background values

### R5: Legend Accuracy

The `OdontogramLegend` component MUST display the correct color for each used state after the color change.

#### Scenario: Legend shows updated color

- GIVEN an odontogram with `restauracion_amalgama` on at least one tooth
- WHEN the legend renders
- THEN the legend entry for `restauracion_amalgama` MUST use the new `defaultColor`

## Proposed Color Changes

| State | Current Color | New Color | Contrast (new vs bg) |
|-------|-------------|-----------|---------------------|
| `restauracion_amalgama` | `#6b7280` | `#0891b2` (cyan-600) | ~5.6:1 |
| `necrosis_pulpar` | `#1f2937` | `#831843` (pink-900) | ~4.0:1 |
| `otra_preexistencia` | `#78716c` | `#a16207` (amber-700) | ~4.8:1 |
| `otra_lesion` | `#78716c` | `#be185d` (pink-700) | ~4.5:1 |

**Note:** These proposed colors are tentative. The final palette MUST be approved by the product owner (Dra. Laura Delgado) before implementation.

## Implementation Notes

- Only `defaultColor` field changes in TS catalog. The `buildStateFills()` function automatically computes fill (12% opacity), stroke (100%), and glow from the new color.
- The SVG printer (`odontogram_svg.py`) has independent `PRINT_FILLS` for white-background output. Only update these if a modified screen color causes a visual conflict in print.
- `necrosis_pulpar` in print (white bg) uses `#d1d5db` fill / `#111827` stroke — these are fine and SHOULD NOT change.

## Testing Scenarios

### Manual QA

1. Open odontogram in PatientDetail for a patient with amalgama registrations
2. Verify the affected teeth show a visible cyan color distinct from resina (blue)
3. Verify legend shows correct new colors
4. Verify tabs (permanent/deciduous) both reflect changes
5. Generate a PDF digital record and verify print colors are unchanged

### Visual Diff

- Before/after screenshots of each modified state in context
- Verify no color bleeding or visual confusion with adjacent states
