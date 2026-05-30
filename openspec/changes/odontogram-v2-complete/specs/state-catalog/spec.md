# Spec: state-catalog

**Change:** odontogram-v2-complete
**Spec ID:** SC
**Tipo:** Full-stack (shared)
**Prioridad:** P1
**Estado:** Borrador
**Fecha:** 2026-04-02
**Dependencia:** `data-model-evolution`

---

## 1. Resumen

El odontograma v1 de ClinicForge define 10 estados como constantes dispersas en el componente React (`STATE_FILLS`, `STATE_BTN`, `TOOTH_STATES`). La v2 requiere ~40 estados organizados en dos categorías clínicas (Preexistente y Lesión), con colores, símbolos y claves i18n. Este spec define el **catálogo central de estados** como una fuente única de verdad (single source of truth) compartida entre frontend TypeScript y backend Python. Ambos artefactos deben mantenerse en sincronía: mismos IDs, mismos colores por defecto, mismos símbolos.

El catálogo también define la tabla de retrocompatibilidad que mapea los 10 estados del sistema v1 a sus equivalentes en el nuevo catálogo, garantizando que ningún dato clínico existente quede huérfano.

---

## 2. Requisitos Funcionales

### REQ-SC-001 — Definición del catálogo TypeScript

El archivo `frontend_react/src/constants/odontogramStates.ts` DEBE exportar:
- El array `ODONTOGRAM_STATES: OdontogramState[]` con las 41 entradas completas (24 preexistentes + 17 lesiones).
- El tipo `OdontogramState` con todos los campos requeridos.
- Los tipos union `OdontogramCategory`, `OdontogramStateId`.
- Funciones de utilidad: `getStateById(id)`, `getStatesByCategory(category)`.
- El mapa de retrocompatibilidad `LEGACY_STATE_MAP` para migración in-memory de datos v1/v2.

### REQ-SC-002 — Definición del catálogo Python

El archivo `shared/odontogram_states.py` DEBE exportar:
- El dataclass `OdontogramStateEntry` con los mismos campos que la interfaz TypeScript (adaptados a PEP-8).
- La lista `ODONTOGRAM_STATES: list[OdontogramStateEntry]` con las 41 entradas idénticas.
- El dict `ODONTOGRAM_STATES_BY_ID: dict[str, OdontogramStateEntry]` para lookup O(1).
- La función `get_state(id: str) -> OdontogramStateEntry | None`.
- El dict `LEGACY_STATE_MAP: dict[str, str]` para migración in-memory.

### REQ-SC-003 — Sincronía entre artefactos

Los IDs, colores HEX y símbolos en `odontogramStates.ts` y `odontogram_states.py` DEBEN ser idénticos. Cualquier adición, modificación o eliminación de un estado DEBE aplicarse a ambos archivos en el mismo commit.

### REQ-SC-004 — Categorías y orden

Los estados DEBEN estar organizados primero por categoría (`preexistente` → `lesion`) y dentro de cada categoría en el orden definido en esta spec (orden clínico lógico). El orden importa para la renderización del modal de selección.

### REQ-SC-005 — Colores para impresión PDF

Cada estado DEBE tener colores diferenciados para renderizado en pantalla (`defaultColor`) y para impresión en PDF (`printColor`). En pantalla: colores vibrantes sobre fondo oscuro. En PDF: colores de alto contraste sobre fondo blanco (stroke más oscuro, fill semitransparente o diferente).

### REQ-SC-006 — Retrocompatibilidad con 10 estados v1

El mapa `LEGACY_STATE_MAP` DEBE cubrir los siguientes mapeos:

| Estado v1 | Estado v2 | Notas |
|-----------|-----------|-------|
| `healthy` | `healthy` | Sin cambio |
| `caries` | `caries` | Sin cambio |
| `restoration` | `restauracion_resina` | Asume resina por defecto |
| `root_canal` | `tratamiento_conducto` | Sin cambio semántico |
| `crown` | `corona_porcelana` | Asume porcelana por defecto |
| `implant` | `implante` | Sin cambio |
| `prosthesis` | `protesis_removible` | Sin cambio semántico |
| `extraction` | `indicacion_extraccion` | Mapeo más preciso |
| `missing` | `ausente` | Sin cambio semántico |
| `treatment_planned` | `treatment_planned` | Se agrega al catálogo v2 como estado especial |

### REQ-SC-007 — Estado especial `treatment_planned`

El estado `treatment_planned` NO aparecía en las tablas de la propuesta pero existe en el sistema v1. DEBE agregarse al catálogo v2 dentro de la categoría `preexistente` con color `#f59e0b` (ámbar) y símbolo `Tp`. Esto garantiza que los datos existentes con este estado no pierdan su representación visual.

### REQ-SC-008 — Símbolo único por estado

Dentro de la categoría `lesion`, el estado `caries_penetrante` tiene símbolo `Cp*` en la propuesta. Dado que el asterisco puede causar problemas en rendering SVG, el símbolo se redefine como `CP` (mayúsculas) para distinguirlo de `corona_porcelana` (símbolo `Cp`). Esta distinción DEBE mantenerse en ambos artefactos.

### REQ-SC-009 — Tipo de dentición no es responsabilidad del catálogo

El catálogo NO distingue entre estados válidos para dentición permanente vs. temporal. Todos los estados son aplicables a ambas denticiones. La restricción clínica (si aplica) es responsabilidad de la UI, no del catálogo.

---

## 3. Detalle Técnico

### 3.1. Interfaz TypeScript

```typescript
// frontend_react/src/constants/odontogramStates.ts

export type OdontogramCategory = 'preexistente' | 'lesion';

export interface PrintColor {
  fill: string;    // HEX — color de relleno para PDF (fondo blanco)
  stroke: string;  // HEX — color de borde para PDF
}

export interface OdontogramState {
  id: string;                  // snake_case, único
  category: OdontogramCategory;
  labelKey: string;            // "odontogram.states.{id}"
  defaultColor: string;        // HEX — color pantalla (fondo oscuro)
  symbol: string;              // 1-3 chars, único dentro de la categoría
  printColor: PrintColor;      // colores para PDF
}

export type OdontogramStateId = typeof ODONTOGRAM_STATES[number]['id'];
```

### 3.2. Catálogo completo TypeScript — Categoría PREEXISTENTE (24 + 1 especial = 25 items)

```typescript
export const ODONTOGRAM_STATES: OdontogramState[] = [
  // ─── PREEXISTENTE ────────────────────────────────────────────────────────
  {
    id: 'healthy',
    category: 'preexistente',
    labelKey: 'odontogram.states.healthy',
    defaultColor: '#f0f0f0',
    symbol: '○',
    printColor: { fill: '#f5f5f5', stroke: '#9ca3af' },
  },
  {
    id: 'implante',
    category: 'preexistente',
    labelKey: 'odontogram.states.implante',
    defaultColor: '#6366f1',
    symbol: 'Im',
    printColor: { fill: '#e0e7ff', stroke: '#4338ca' },
  },
  {
    id: 'radiografia',
    category: 'preexistente',
    labelKey: 'odontogram.states.radiografia',
    defaultColor: '#f59e0b',
    symbol: 'Rx',
    printColor: { fill: '#fef3c7', stroke: '#d97706' },
  },
  {
    id: 'restauracion_resina',
    category: 'preexistente',
    labelKey: 'odontogram.states.restauracion_resina',
    defaultColor: '#3b82f6',
    symbol: 'Rr',
    printColor: { fill: '#dbeafe', stroke: '#1d4ed8' },
  },
  {
    id: 'restauracion_amalgama',
    category: 'preexistente',
    labelKey: 'odontogram.states.restauracion_amalgama',
    defaultColor: '#6b7280',
    symbol: 'Ra',
    printColor: { fill: '#e5e7eb', stroke: '#374151' },
  },
  {
    id: 'restauracion_temporal',
    category: 'preexistente',
    labelKey: 'odontogram.states.restauracion_temporal',
    defaultColor: '#a78bfa',
    symbol: 'Rt',
    printColor: { fill: '#ede9fe', stroke: '#7c3aed' },
  },
  {
    id: 'sellador_fisuras',
    category: 'preexistente',
    labelKey: 'odontogram.states.sellador_fisuras',
    defaultColor: '#10b981',
    symbol: 'Sf',
    printColor: { fill: '#d1fae5', stroke: '#065f46' },
  },
  {
    id: 'carilla',
    category: 'preexistente',
    labelKey: 'odontogram.states.carilla',
    defaultColor: '#ec4899',
    symbol: 'Ca',
    printColor: { fill: '#fce7f3', stroke: '#be185d' },
  },
  {
    id: 'puente',
    category: 'preexistente',
    labelKey: 'odontogram.states.puente',
    defaultColor: '#8b5cf6',
    symbol: 'Pu',
    printColor: { fill: '#ede9fe', stroke: '#6d28d9' },
  },
  {
    id: 'corona_porcelana',
    category: 'preexistente',
    labelKey: 'odontogram.states.corona_porcelana',
    defaultColor: '#d946ef',
    symbol: 'Cp',
    printColor: { fill: '#fae8ff', stroke: '#a21caf' },
  },
  {
    id: 'corona_resina',
    category: 'preexistente',
    labelKey: 'odontogram.states.corona_resina',
    defaultColor: '#a855f7',
    symbol: 'Cr',
    printColor: { fill: '#f3e8ff', stroke: '#7e22ce' },
  },
  {
    id: 'corona_metalceramica',
    category: 'preexistente',
    labelKey: 'odontogram.states.corona_metalceramica',
    defaultColor: '#7c3aed',
    symbol: 'Cm',
    printColor: { fill: '#ede9fe', stroke: '#5b21b6' },
  },
  {
    id: 'corona_temporal',
    category: 'preexistente',
    labelKey: 'odontogram.states.corona_temporal',
    defaultColor: '#c084fc',
    symbol: 'Ct',
    printColor: { fill: '#f5f3ff', stroke: '#9333ea' },
  },
  {
    id: 'incrustacion',
    category: 'preexistente',
    labelKey: 'odontogram.states.incrustacion',
    defaultColor: '#f472b6',
    symbol: 'In',
    printColor: { fill: '#fdf2f8', stroke: '#db2777' },
  },
  {
    id: 'onlay',
    category: 'preexistente',
    labelKey: 'odontogram.states.onlay',
    defaultColor: '#e879f9',
    symbol: 'On',
    printColor: { fill: '#fdf4ff', stroke: '#c026d3' },
  },
  {
    id: 'poste',
    category: 'preexistente',
    labelKey: 'odontogram.states.poste',
    defaultColor: '#94a3b8',
    symbol: 'Po',
    printColor: { fill: '#f1f5f9', stroke: '#475569' },
  },
  {
    id: 'perno',
    category: 'preexistente',
    labelKey: 'odontogram.states.perno',
    defaultColor: '#64748b',
    symbol: 'Pe',
    printColor: { fill: '#f8fafc', stroke: '#334155' },
  },
  {
    id: 'fibras_ribbond',
    category: 'preexistente',
    labelKey: 'odontogram.states.fibras_ribbond',
    defaultColor: '#78716c',
    symbol: 'Fr',
    printColor: { fill: '#fafaf9', stroke: '#44403c' },
  },
  {
    id: 'tratamiento_conducto',
    category: 'preexistente',
    labelKey: 'odontogram.states.tratamiento_conducto',
    defaultColor: '#f97316',
    symbol: 'Tc',
    printColor: { fill: '#fff7ed', stroke: '#c2410c' },
  },
  {
    id: 'protesis_removible',
    category: 'preexistente',
    labelKey: 'odontogram.states.protesis_removible',
    defaultColor: '#14b8a6',
    symbol: 'Pr',
    printColor: { fill: '#f0fdfa', stroke: '#0f766e' },
  },
  {
    id: 'diente_erupcion',
    category: 'preexistente',
    labelKey: 'odontogram.states.diente_erupcion',
    defaultColor: '#fbbf24',
    symbol: 'De',
    printColor: { fill: '#fffbeb', stroke: '#b45309' },
  },
  {
    id: 'diente_no_erupcionado',
    category: 'preexistente',
    labelKey: 'odontogram.states.diente_no_erupcionado',
    defaultColor: '#d97706',
    symbol: 'Dn',
    printColor: { fill: '#fef3c7', stroke: '#92400e' },
  },
  {
    id: 'ausente',
    category: 'preexistente',
    labelKey: 'odontogram.states.ausente',
    defaultColor: '#374151',
    symbol: '—',
    printColor: { fill: '#d1d5db', stroke: '#111827' },
  },
  {
    id: 'treatment_planned',
    category: 'preexistente',
    labelKey: 'odontogram.states.treatment_planned',
    defaultColor: '#f59e0b',
    symbol: 'Tp',
    printColor: { fill: '#fef3c7', stroke: '#d97706' },
  },
  {
    id: 'otra_preexistencia',
    category: 'preexistente',
    labelKey: 'odontogram.states.otra_preexistencia',
    defaultColor: '#9ca3af',
    symbol: 'Op',
    printColor: { fill: '#f9fafb', stroke: '#6b7280' },
  },

  // ─── LESIÓN ──────────────────────────────────────────────────────────────
  {
    id: 'mancha_blanca',
    category: 'lesion',
    labelKey: 'odontogram.states.mancha_blanca',
    defaultColor: '#e5e7eb',
    symbol: 'Mb',
    printColor: { fill: '#f9fafb', stroke: '#6b7280' },
  },
  {
    id: 'surco_profundo',
    category: 'lesion',
    labelKey: 'odontogram.states.surco_profundo',
    defaultColor: '#fca5a5',
    symbol: 'Sp',
    printColor: { fill: '#fef2f2', stroke: '#dc2626' },
  },
  {
    id: 'caries',
    category: 'lesion',
    labelKey: 'odontogram.states.caries',
    defaultColor: '#ef4444',
    symbol: 'C',
    printColor: { fill: '#fee2e2', stroke: '#b91c1c' },
  },
  {
    id: 'caries_penetrante',
    category: 'lesion',
    labelKey: 'odontogram.states.caries_penetrante',
    defaultColor: '#dc2626',
    symbol: 'CP',
    printColor: { fill: '#fee2e2', stroke: '#7f1d1d' },
  },
  {
    id: 'necrosis_pulpar',
    category: 'lesion',
    labelKey: 'odontogram.states.necrosis_pulpar',
    defaultColor: '#991b1b',
    symbol: 'Np',
    printColor: { fill: '#fef2f2', stroke: '#450a0a' },
  },
  {
    id: 'proceso_apical',
    category: 'lesion',
    labelKey: 'odontogram.states.proceso_apical',
    defaultColor: '#b91c1c',
    symbol: 'Pa',
    printColor: { fill: '#fef2f2', stroke: '#7f1d1d' },
  },
  {
    id: 'fistula',
    category: 'lesion',
    labelKey: 'odontogram.states.fistula',
    defaultColor: '#f87171',
    symbol: 'Fi',
    printColor: { fill: '#fef2f2', stroke: '#ef4444' },
  },
  {
    id: 'indicacion_extraccion',
    category: 'lesion',
    labelKey: 'odontogram.states.indicacion_extraccion',
    defaultColor: '#7f1d1d',
    symbol: 'Ie',
    printColor: { fill: '#fee2e2', stroke: '#450a0a' },
  },
  {
    id: 'abrasion',
    category: 'lesion',
    labelKey: 'odontogram.states.abrasion',
    defaultColor: '#fb923c',
    symbol: 'Ab',
    printColor: { fill: '#fff7ed', stroke: '#c2410c' },
  },
  {
    id: 'abfraccion',
    category: 'lesion',
    labelKey: 'odontogram.states.abfraccion',
    defaultColor: '#f97316',
    symbol: 'Af',
    printColor: { fill: '#fff7ed', stroke: '#9a3412' },
  },
  {
    id: 'atricion',
    category: 'lesion',
    labelKey: 'odontogram.states.atricion',
    defaultColor: '#ea580c',
    symbol: 'At',
    printColor: { fill: '#fff7ed', stroke: '#7c2d12' },
  },
  {
    id: 'erosion',
    category: 'lesion',
    labelKey: 'odontogram.states.erosion',
    defaultColor: '#c2410c',
    symbol: 'Er',
    printColor: { fill: '#fff7ed', stroke: '#7c2d12' },
  },
  {
    id: 'fractura_horizontal',
    category: 'lesion',
    labelKey: 'odontogram.states.fractura_horizontal',
    defaultColor: '#92400e',
    symbol: 'Fh',
    printColor: { fill: '#fef3c7', stroke: '#78350f' },
  },
  {
    id: 'fractura_vertical',
    category: 'lesion',
    labelKey: 'odontogram.states.fractura_vertical',
    defaultColor: '#78350f',
    symbol: 'Fv',
    printColor: { fill: '#fef3c7', stroke: '#451a03' },
  },
  {
    id: 'movilidad',
    category: 'lesion',
    labelKey: 'odontogram.states.movilidad',
    defaultColor: '#eab308',
    symbol: 'Mo',
    printColor: { fill: '#fefce8', stroke: '#854d0e' },
  },
  {
    id: 'hipomineralizacion_mih',
    category: 'lesion',
    labelKey: 'odontogram.states.hipomineralizacion_mih',
    defaultColor: '#ca8a04',
    symbol: 'MIH',
    printColor: { fill: '#fefce8', stroke: '#713f12' },
  },
  {
    id: 'otra_lesion',
    category: 'lesion',
    labelKey: 'odontogram.states.otra_lesion',
    defaultColor: '#f87171',
    symbol: 'Ol',
    printColor: { fill: '#fef2f2', stroke: '#dc2626' },
  },
];
```

### 3.3. Funciones de utilidad TypeScript

```typescript
// Lookup O(1) por ID
export const ODONTOGRAM_STATES_BY_ID = Object.fromEntries(
  ODONTOGRAM_STATES.map((s) => [s.id, s])
) as Record<string, OdontogramState>;

// Helper — nunca lanza, retorna undefined si el ID no existe
export function getStateById(id: string): OdontogramState | undefined {
  return ODONTOGRAM_STATES_BY_ID[id];
}

// Helper — retorna solo los estados de una categoría
export function getStatesByCategory(
  category: OdontogramCategory
): OdontogramState[] {
  return ODONTOGRAM_STATES.filter((s) => s.category === category);
}

// Mapa de retrocompatibilidad v1 → v2
export const LEGACY_STATE_MAP: Record<string, string> = {
  healthy:          'healthy',
  caries:           'caries',
  restoration:      'restauracion_resina',
  root_canal:       'tratamiento_conducto',
  crown:            'corona_porcelana',
  implant:          'implante',
  prosthesis:       'protesis_removible',
  extraction:       'indicacion_extraccion',
  missing:          'ausente',
  treatment_planned: 'treatment_planned',
};

// Normaliza un ID v1 a su equivalente v2; retorna el mismo ID si ya es v2
export function normalizeLegacyStateId(id: string): string {
  return LEGACY_STATE_MAP[id] ?? id;
}
```

### 3.4. Dataclass Python y catálogo espejo

```python
# shared/odontogram_states.py
from dataclasses import dataclass
from typing import Literal, Optional

OdontogramCategory = Literal['preexistente', 'lesion']

@dataclass(frozen=True)
class PrintColor:
    fill: str    # HEX — para PDF fondo blanco
    stroke: str  # HEX — borde en PDF

@dataclass(frozen=True)
class OdontogramStateEntry:
    id: str
    category: OdontogramCategory
    label_key: str               # "odontogram.states.{id}"
    default_color: str           # HEX pantalla
    symbol: str                  # 1-3 chars
    print_color: PrintColor

# Lista completa — mismo orden que el catálogo TypeScript
ODONTOGRAM_STATES: list[OdontogramStateEntry] = [
    # ─── PREEXISTENTE ────────────────────────────────────────────────────
    OdontogramStateEntry('healthy',               'preexistente', 'odontogram.states.healthy',               '#f0f0f0', '○',   PrintColor('#f5f5f5', '#9ca3af')),
    OdontogramStateEntry('implante',              'preexistente', 'odontogram.states.implante',              '#6366f1', 'Im',  PrintColor('#e0e7ff', '#4338ca')),
    OdontogramStateEntry('radiografia',           'preexistente', 'odontogram.states.radiografia',           '#f59e0b', 'Rx',  PrintColor('#fef3c7', '#d97706')),
    OdontogramStateEntry('restauracion_resina',   'preexistente', 'odontogram.states.restauracion_resina',   '#3b82f6', 'Rr',  PrintColor('#dbeafe', '#1d4ed8')),
    OdontogramStateEntry('restauracion_amalgama', 'preexistente', 'odontogram.states.restauracion_amalgama', '#6b7280', 'Ra',  PrintColor('#e5e7eb', '#374151')),
    OdontogramStateEntry('restauracion_temporal', 'preexistente', 'odontogram.states.restauracion_temporal', '#a78bfa', 'Rt',  PrintColor('#ede9fe', '#7c3aed')),
    OdontogramStateEntry('sellador_fisuras',      'preexistente', 'odontogram.states.sellador_fisuras',      '#10b981', 'Sf',  PrintColor('#d1fae5', '#065f46')),
    OdontogramStateEntry('carilla',               'preexistente', 'odontogram.states.carilla',               '#ec4899', 'Ca',  PrintColor('#fce7f3', '#be185d')),
    OdontogramStateEntry('puente',                'preexistente', 'odontogram.states.puente',                '#8b5cf6', 'Pu',  PrintColor('#ede9fe', '#6d28d9')),
    OdontogramStateEntry('corona_porcelana',      'preexistente', 'odontogram.states.corona_porcelana',      '#d946ef', 'Cp',  PrintColor('#fae8ff', '#a21caf')),
    OdontogramStateEntry('corona_resina',         'preexistente', 'odontogram.states.corona_resina',         '#a855f7', 'Cr',  PrintColor('#f3e8ff', '#7e22ce')),
    OdontogramStateEntry('corona_metalceramica',  'preexistente', 'odontogram.states.corona_metalceramica',  '#7c3aed', 'Cm',  PrintColor('#ede9fe', '#5b21b6')),
    OdontogramStateEntry('corona_temporal',       'preexistente', 'odontogram.states.corona_temporal',       '#c084fc', 'Ct',  PrintColor('#f5f3ff', '#9333ea')),
    OdontogramStateEntry('incrustacion',          'preexistente', 'odontogram.states.incrustacion',          '#f472b6', 'In',  PrintColor('#fdf2f8', '#db2777')),
    OdontogramStateEntry('onlay',                 'preexistente', 'odontogram.states.onlay',                 '#e879f9', 'On',  PrintColor('#fdf4ff', '#c026d3')),
    OdontogramStateEntry('poste',                 'preexistente', 'odontogram.states.poste',                 '#94a3b8', 'Po',  PrintColor('#f1f5f9', '#475569')),
    OdontogramStateEntry('perno',                 'preexistente', 'odontogram.states.perno',                 '#64748b', 'Pe',  PrintColor('#f8fafc', '#334155')),
    OdontogramStateEntry('fibras_ribbond',        'preexistente', 'odontogram.states.fibras_ribbond',        '#78716c', 'Fr',  PrintColor('#fafaf9', '#44403c')),
    OdontogramStateEntry('tratamiento_conducto',  'preexistente', 'odontogram.states.tratamiento_conducto',  '#f97316', 'Tc',  PrintColor('#fff7ed', '#c2410c')),
    OdontogramStateEntry('protesis_removible',    'preexistente', 'odontogram.states.protesis_removible',    '#14b8a6', 'Pr',  PrintColor('#f0fdfa', '#0f766e')),
    OdontogramStateEntry('diente_erupcion',       'preexistente', 'odontogram.states.diente_erupcion',       '#fbbf24', 'De',  PrintColor('#fffbeb', '#b45309')),
    OdontogramStateEntry('diente_no_erupcionado', 'preexistente', 'odontogram.states.diente_no_erupcionado', '#d97706', 'Dn',  PrintColor('#fef3c7', '#92400e')),
    OdontogramStateEntry('ausente',               'preexistente', 'odontogram.states.ausente',               '#374151', '—',   PrintColor('#d1d5db', '#111827')),
    OdontogramStateEntry('treatment_planned',     'preexistente', 'odontogram.states.treatment_planned',     '#f59e0b', 'Tp',  PrintColor('#fef3c7', '#d97706')),
    OdontogramStateEntry('otra_preexistencia',    'preexistente', 'odontogram.states.otra_preexistencia',    '#9ca3af', 'Op',  PrintColor('#f9fafb', '#6b7280')),

    # ─── LESIÓN ──────────────────────────────────────────────────────────
    OdontogramStateEntry('mancha_blanca',          'lesion', 'odontogram.states.mancha_blanca',          '#e5e7eb', 'Mb',  PrintColor('#f9fafb', '#6b7280')),
    OdontogramStateEntry('surco_profundo',         'lesion', 'odontogram.states.surco_profundo',         '#fca5a5', 'Sp',  PrintColor('#fef2f2', '#dc2626')),
    OdontogramStateEntry('caries',                 'lesion', 'odontogram.states.caries',                 '#ef4444', 'C',   PrintColor('#fee2e2', '#b91c1c')),
    OdontogramStateEntry('caries_penetrante',      'lesion', 'odontogram.states.caries_penetrante',      '#dc2626', 'CP',  PrintColor('#fee2e2', '#7f1d1d')),
    OdontogramStateEntry('necrosis_pulpar',        'lesion', 'odontogram.states.necrosis_pulpar',        '#991b1b', 'Np',  PrintColor('#fef2f2', '#450a0a')),
    OdontogramStateEntry('proceso_apical',         'lesion', 'odontogram.states.proceso_apical',         '#b91c1c', 'Pa',  PrintColor('#fef2f2', '#7f1d1d')),
    OdontogramStateEntry('fistula',                'lesion', 'odontogram.states.fistula',                '#f87171', 'Fi',  PrintColor('#fef2f2', '#ef4444')),
    OdontogramStateEntry('indicacion_extraccion',  'lesion', 'odontogram.states.indicacion_extraccion',  '#7f1d1d', 'Ie',  PrintColor('#fee2e2', '#450a0a')),
    OdontogramStateEntry('abrasion',               'lesion', 'odontogram.states.abrasion',               '#fb923c', 'Ab',  PrintColor('#fff7ed', '#c2410c')),
    OdontogramStateEntry('abfraccion',             'lesion', 'odontogram.states.abfraccion',              '#f97316', 'Af',  PrintColor('#fff7ed', '#9a3412')),
    OdontogramStateEntry('atricion',               'lesion', 'odontogram.states.atricion',               '#ea580c', 'At',  PrintColor('#fff7ed', '#7c2d12')),
    OdontogramStateEntry('erosion',                'lesion', 'odontogram.states.erosion',                '#c2410c', 'Er',  PrintColor('#fff7ed', '#7c2d12')),
    OdontogramStateEntry('fractura_horizontal',    'lesion', 'odontogram.states.fractura_horizontal',    '#92400e', 'Fh',  PrintColor('#fef3c7', '#78350f')),
    OdontogramStateEntry('fractura_vertical',      'lesion', 'odontogram.states.fractura_vertical',      '#78350f', 'Fv',  PrintColor('#fef3c7', '#451a03')),
    OdontogramStateEntry('movilidad',              'lesion', 'odontogram.states.movilidad',              '#eab308', 'Mo',  PrintColor('#fefce8', '#854d0e')),
    OdontogramStateEntry('hipomineralizacion_mih', 'lesion', 'odontogram.states.hipomineralizacion_mih', '#ca8a04', 'MIH', PrintColor('#fefce8', '#713f12')),
    OdontogramStateEntry('otra_lesion',            'lesion', 'odontogram.states.otra_lesion',            '#f87171', 'Ol',  PrintColor('#fef2f2', '#dc2626')),
]

# Índice para lookup O(1)
ODONTOGRAM_STATES_BY_ID: dict[str, OdontogramStateEntry] = {
    s.id: s for s in ODONTOGRAM_STATES
}

def get_state(state_id: str) -> Optional[OdontogramStateEntry]:
    """Retorna el estado por ID, o None si no existe."""
    return ODONTOGRAM_STATES_BY_ID.get(state_id)

# Mapa de retrocompatibilidad v1 → v2
LEGACY_STATE_MAP: dict[str, str] = {
    'healthy':          'healthy',
    'caries':           'caries',
    'restoration':      'restauracion_resina',
    'root_canal':       'tratamiento_conducto',
    'crown':            'corona_porcelana',
    'implant':          'implante',
    'prosthesis':       'protesis_removible',
    'extraction':       'indicacion_extraccion',
    'missing':          'ausente',
    'treatment_planned': 'treatment_planned',
}

def normalize_legacy_state_id(state_id: str) -> str:
    """Convierte un ID v1 a su equivalente v2. Retorna el mismo ID si ya es v2."""
    return LEGACY_STATE_MAP.get(state_id, state_id)
```

### 3.5. Resumen cuantitativo del catálogo

| Categoría | Cantidad | Rango en el array |
|-----------|----------|-------------------|
| Preexistente | 25 (24 de la propuesta + `treatment_planned`) | índices 0–24 |
| Lesión | 17 | índices 25–41 |
| **Total** | **42** | — |

> Nota: El recuento de 42 vs. los "~40" de la propuesta se debe a la inclusión de `treatment_planned` (REQ-SC-007) para garantizar retrocompatibilidad con datos existentes.

---

## 4. Escenarios

### Escenario SC-01 — Lookup de estado existente (TypeScript)

```gherkin
Given el catálogo ODONTOGRAM_STATES está importado
When llamo getStateById('implante')
Then retorna el objeto con id='implante', category='preexistente',
     symbol='Im', defaultColor='#6366f1'
```

### Escenario SC-02 — Lookup de estado inexistente (TypeScript)

```gherkin
Given el catálogo ODONTOGRAM_STATES está importado
When llamo getStateById('estado_que_no_existe')
Then retorna undefined (no lanza excepción)
```

### Escenario SC-03 — Filtrado por categoría

```gherkin
Given el catálogo ODONTOGRAM_STATES está importado
When llamo getStatesByCategory('lesion')
Then retorna exactamente 17 elementos
And todos tienen category='lesion'
And el primer elemento tiene id='mancha_blanca'
And el último elemento tiene id='otra_lesion'
```

### Escenario SC-04 — Retrocompatibilidad: estado v1 → v2

```gherkin
Given el mapa LEGACY_STATE_MAP está importado
When llamo normalizeLegacyStateId('restoration')
Then retorna 'restauracion_resina'
```

```gherkin
When llamo normalizeLegacyStateId('crown')
Then retorna 'corona_porcelana'
```

```gherkin
When llamo normalizeLegacyStateId('restauracion_resina')
Then retorna 'restauracion_resina' (ID v2 pasa sin cambios)
```

### Escenario SC-05 — Sincronía TypeScript ↔ Python

```gherkin
Given el catálogo TypeScript y el catálogo Python están generados
When comparo los IDs de ODONTOGRAM_STATES en ambos archivos
Then los conjuntos son idénticos (mismo orden, mismos valores)
When comparo los defaultColor de cada ID en ambos archivos
Then todos los colores HEX son idénticos
When comparo los symbol de cada ID en ambos archivos
Then todos los símbolos son idénticos
```

### Escenario SC-06 — Lookup Python

```gherkin
Given el módulo shared.odontogram_states está importado
When llamo get_state('caries_penetrante')
Then retorna OdontogramStateEntry con symbol='CP', category='lesion'
When llamo get_state('estado_invalido')
Then retorna None (sin excepción)
```

### Escenario SC-07 — Estado `treatment_planned` accesible como v2

```gherkin
Given un registro de odontograma con surface.state = 'treatment_planned' (guardado en v1)
When el frontend llama getStateById('treatment_planned')
Then retorna el estado correctamente con symbol='Tp', defaultColor='#f59e0b'
And la superficie se renderiza con ese color sin errores visuales
```

### Escenario SC-08 — Total de estados por categoría

```gherkin
Given el catálogo ODONTOGRAM_STATES
When cuento los elementos con category='preexistente'
Then el resultado es 25
When cuento los elementos con category='lesion'
Then el resultado es 17
When cuento todos los elementos
Then el resultado es 42
```

---

## 5. Criterios de Aceptación

| ID | Criterio | Verificación |
|----|----------|-------------|
| CA-SC-01 | `odontogramStates.ts` exporta exactamente 42 entradas en `ODONTOGRAM_STATES` | `ODONTOGRAM_STATES.length === 42` en test unitario |
| CA-SC-02 | `odontogram_states.py` exporta exactamente 42 entradas en `ODONTOGRAM_STATES` | `len(ODONTOGRAM_STATES) == 42` en test unitario |
| CA-SC-03 | Todos los IDs son únicos en ambos catálogos | Set de IDs tiene el mismo tamaño que el array |
| CA-SC-04 | Todos los `symbol` son únicos dentro de cada categoría | Sin duplicados en sets por categoría |
| CA-SC-05 | Los IDs de TypeScript y Python son idénticos y en el mismo orden | Test de snapshot |
| CA-SC-06 | Los `defaultColor` de TypeScript y Python son idénticos para cada ID | Test de comparación campo a campo |
| CA-SC-07 | `getStateById('unknown')` retorna `undefined` sin lanzar | Test con ID inexistente |
| CA-SC-08 | `get_state('unknown')` retorna `None` sin lanzar | Test con ID inexistente |
| CA-SC-09 | Todos los IDs v1 del `LEGACY_STATE_MAP` resuelven a un ID v2 válido | `getStateById(normalizeLegacyStateId(legacyId))` no es undefined para cada entrada |
| CA-SC-10 | El campo `printColor` tiene fill y stroke distintos entre sí (alto contraste) | Ninguna entrada tiene `fill === stroke` |

---

## 6. Archivos Afectados

| Archivo | Acción | Descripción |
|---------|--------|-------------|
| `frontend_react/src/constants/odontogramStates.ts` | **CREAR** | Catálogo TypeScript — fuente de verdad frontend |
| `shared/odontogram_states.py` | **CREAR** | Catálogo Python — espejo del catálogo TypeScript |
| `frontend_react/src/components/Odontogram.tsx` | **MODIFICAR** | Reemplazar `STATE_FILLS`, `STATE_BTN`, `TOOTH_STATES` con importaciones del catálogo |
| `orchestrator_service/services/odontogram_svg.py` | **MODIFICAR** | Reemplazar colores hardcodeados con `ODONTOGRAM_STATES_BY_ID` de Python |
| `orchestrator_service/services/nova_tools.py` | **MODIFICAR** | Actualizar validación de estados en `modificar_odontograma` |
| `tests/test_odontogram_states.py` | **CREAR** | Tests de sincronía, unicidad de IDs y símbolos, retrocompatibilidad |

---

## 7. Dependencias

| Tipo | Dependencia | Detalle |
|------|-------------|---------|
| **Bloqueante** | `data-model-evolution` | Los nuevos IDs de estado se usan en los DTOs Pydantic de `models_dental.py`. Sin el modelo actualizado, los endpoints rechazan los nuevos IDs. |
| **Bloqueante inversa** | `state-condition-color` | Este spec debe estar completo para que `StateConditionModal` sepa qué estados mostrar. |
| **Bloqueante inversa** | `symbol-selector-modal` | El `SymbolSelectorModal` itera sobre `ODONTOGRAM_STATES` de este spec. |
| **Bloqueante inversa** | `i18n-expansion` | Las claves `labelKey` de este spec deben existir en los JSON de traducción. |
| **Bloqueante inversa** | `svg-pdf-renderer` | El renderer usa `ODONTOGRAM_STATES_BY_ID` de Python para mapear colores. |
| **Bloqueante inversa** | `nova-tools-update` | Nova valida los IDs de estado contra el catálogo Python. |
| **Sin dependencia** | `dentition-tabs` | Los tabs no necesitan el catálogo para funcionar; lo usan pero no lo requieren. |
