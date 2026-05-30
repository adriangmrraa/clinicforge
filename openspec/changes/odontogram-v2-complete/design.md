# Diseno Tecnico: odontogram-v2-complete

**Cambio:** Odontograma v2 Completo — Denticion dual, superficies individuales, catalogo expandido
**Fecha:** 2026-04-02
**Estado:** Design
**Autor:** SDD Design Agent

---

## 1. Resumen de Arquitectura

### Diagrama de alto nivel

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           FRONTEND (React 18)                          │
│                                                                        │
│  Odontogram.tsx (Orquestador)                                          │
│  ├── OdontogramTabs.tsx          ← Tabs Permanente/Temporal            │
│  ├── DentitionChart.tsx          ← Renderer generico de cuadrantes     │
│  │   └── ToothSVG.tsx            ← Pieza individual con 5 superficies  │
│  │       └── SurfacePath.tsx     ← Superficie SVG clickeable           │
│  ├── SymbolSelectorModal.tsx     ← Selector de estados (~42)           │
│  ├── StateConditionModal.tsx     ← Condicion + color picker            │
│  ├── OdontogramLegend.tsx        ← Leyenda dinamica                    │
│  └── MobileToothZoom.tsx         ← Panel zoom para mobile              │
│                                                                        │
│  Shared:                                                               │
│  ├── constants/odontogramStates.ts  ← Catalogo TS (42 estados)        │
│  └── components/odontogram/catalog.ts ← Re-export + utilidades        │
└────────────────────┬───────────────────────────────────────────────────┘
                     │ PUT/GET /admin/patients/{id}/records/{id}/odontogram
                     ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                       BFF (Express :3000)                              │
└────────────────────┬───────────────────────────────────────────────────┘
                     ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                    ORCHESTRATOR (FastAPI :8000)                         │
│                                                                        │
│  admin_routes.py                                                       │
│  ├── PUT /admin/patients/{id}/records/{id}/odontogram  → acepta v2+v3 │
│  └── GET /admin/patients/{id}/records/{id}/odontogram  → retorna v3   │
│                                                                        │
│  shared/odontogram_utils.py     ← Parser unificado v1→v2→v3           │
│  shared/odontogram_states.py    ← Catalogo Python (42 estados)        │
│  shared/models_dental.py        ← Pydantic: SurfaceState, ToothDataV3 │
│                                                                        │
│  services/odontogram_svg.py     ← SVG renderer (PDF) per-surface      │
│  services/nova_tools.py         ← ver_odontograma, modificar_odontog. │
│  templates/odontogram_art.html  ← Template HTML con seccion temporal   │
│  services/digital_records_service.py ← Pasa v3.0 al renderer          │
│                                                                        │
│  alembic/versions/017_odontogram_v3_format.py  ← GIN index            │
└────────────────────┬───────────────────────────────────────────────────┘
                     ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  PostgreSQL — clinical_records.odontogram_data (JSONB v3.0)            │
│  GIN index: idx_clinical_records_odontogram_gin                        │
└─────────────────────────────────────────────────────────────────────────┘
```

### Principios de diseno

1. **Parser unico, multiples consumidores:** Un solo modulo `shared/odontogram_utils.py` normaliza cualquier version de datos a v3.0. Lo consumen: `admin_routes.py`, `odontogram_svg.py`, `nova_tools.py`.
2. **Catalogo duplicado controlado:** Python y TypeScript mantienen catalogos espejo. No hay mecanismo de sincronizacion automatica — se garantiza por disciplina de commit (mismo PR modifica ambos).
3. **Migracion on-read:** No hay migracion SQL batch. Los datos se upgraden en memoria al leerlos y se persisten en v3.0 al siguiente write.
4. **Estado vive en el orquestador:** `Odontogram.tsx` es la unica fuente de verdad del estado React. Los sub-componentes son presentacionales con callbacks.
5. **Retrocompatibilidad total:** El sistema acepta datos v1, v2, v3 en lectura y siempre escribe v3.

---

## 2. Modelo de Datos

### 2.1. Formato JSONB v3.0 — Estructura completa

```jsonc
{
  "version": "3.0",                           // Literal, siempre "3.0" al guardar
  "last_updated": "2026-04-02T15:30:00Z",     // ISO-8601 UTC
  "active_dentition": "permanent",             // "permanent" | "deciduous"

  "permanent": {
    "teeth": [
      {
        "id": 18,                              // FDI entero (11-48)
        "state": "healthy",                    // Estado global (retrocompat + resumen)
        "surfaces": {
          "occlusal": {
            "state": "caries",                 // String del catalogo (~42 valores)
            "condition": "malo",               // "bueno" | "malo" | "indefinido" | null
            "color": "#ef4444"                 // HEX #rrggbb o null (usa default)
          },
          "mesial":   { "state": "healthy", "condition": null, "color": null },
          "distal":   { "state": "restauracion_resina", "condition": "bueno", "color": "#3b82f6" },
          "buccal":   { "state": "healthy", "condition": null, "color": null },
          "lingual":  { "state": "healthy", "condition": null, "color": null }
        },
        "notes": "Caries incipiente, observacion"
      }
      // ... 32 dientes en orden: 18→11, 21→28, 48→41, 31→38
    ]
  },

  "deciduous": {
    "teeth": [
      {
        "id": 55,                              // FDI decidua: 55-51, 61-65, 85-81, 71-75
        "state": "healthy",
        "surfaces": {
          "occlusal": { "state": "healthy", "condition": null, "color": null },
          "mesial":   { "state": "healthy", "condition": null, "color": null },
          "distal":   { "state": "healthy", "condition": null, "color": null },
          "buccal":   { "state": "healthy", "condition": null, "color": null },
          "lingual":  { "state": "healthy", "condition": null, "color": null }
        },
        "notes": ""
      }
      // ... 20 dientes
    ]
  }
}
```

### 2.2. Orden FDI de almacenamiento

**Denticion permanente (32 piezas):**

| Cuadrante | FDIs en orden | Etiqueta |
|-----------|---------------|----------|
| Q1 Superior Derecho | 18, 17, 16, 15, 14, 13, 12, 11 | Terceros molares → incisivo central |
| Q2 Superior Izquierdo | 21, 22, 23, 24, 25, 26, 27, 28 | Incisivo central → tercer molar |
| Q4 Inferior Derecho | 48, 47, 46, 45, 44, 43, 42, 41 | Terceros molares → incisivo central |
| Q3 Inferior Izquierdo | 31, 32, 33, 34, 35, 36, 37, 38 | Incisivo central → tercer molar |

**Denticion decidua/temporal (20 piezas):**

| Cuadrante | FDIs en orden | Etiqueta |
|-----------|---------------|----------|
| Q5 Superior Derecho | 55, 54, 53, 52, 51 | 2do molar → incisivo central |
| Q6 Superior Izquierdo | 61, 62, 63, 64, 65 | Incisivo central → 2do molar |
| Q8 Inferior Derecho | 85, 84, 83, 82, 81 | 2do molar → incisivo central |
| Q7 Inferior Izquierdo | 71, 72, 73, 74, 75 | Incisivo central → 2do molar |

### 2.3. Superficie individual — SurfaceState

| Campo | Tipo | Valores | Default | Descripcion |
|-------|------|---------|---------|-------------|
| `state` | `string` | Cualquier ID del catalogo de 42 estados | `"healthy"` | Estado clinico de la superficie |
| `condition` | `string \| null` | `"bueno"`, `"malo"`, `"indefinido"`, `null` | `null` | Evaluacion clinica del estado |
| `color` | `string \| null` | HEX `#rrggbb` o `null` | `null` | Color custom. Si null, usa `defaultColor` del catalogo |

**Regla de color:** `surface.color ?? CATALOG[surface.state].defaultColor`

### 2.4. Superficies validas — Mapeo SVG ↔ Anatomico

| Key datos | Path SVG | Anatomico | Label i18n |
|-----------|----------|-----------|------------|
| `occlusal` | Centro (circle cx=20 cy=20 r=7) | Oclusal / Incisal | `odontogram.surfaces.occlusal` |
| `mesial` | `left` | Mesial (hacia linea media) | `odontogram.surfaces.mesial` |
| `distal` | `right` | Distal (alejada linea media) | `odontogram.surfaces.distal` |
| `buccal` | `top` | Vestibular / Bucal | `odontogram.surfaces.buccal` |
| `lingual` | `bottom` | Palatino / Lingual | `odontogram.surfaces.lingual` |

### 2.5. Modelos Pydantic — `shared/models_dental.py`

Se agregan los siguientes modelos SIN modificar los existentes (backward compat de API):

```python
from typing import Optional, Literal, List
from pydantic import BaseModel, validator
import re

DentitionType = Literal["permanent", "deciduous"]

class SurfaceState(BaseModel):
    """Estado de una superficie individual de un diente (v3.0)."""
    state: str = "healthy"
    condition: Optional[Literal["bueno", "malo", "indefinido"]] = None
    color: Optional[str] = None

    @validator("color")
    def validate_hex_color(cls, v):
        if v is not None and not re.match(r'^#[0-9a-fA-F]{6}$', v):
            raise ValueError(f"color debe ser HEX #rrggbb, recibido: {v}")
        return v

    @classmethod
    def healthy(cls) -> "SurfaceState":
        return cls(state="healthy", condition=None, color=None)


class ToothSurfacesV3(BaseModel):
    """Las 5 superficies de un diente con estado independiente."""
    occlusal: SurfaceState = SurfaceState.healthy()
    mesial: SurfaceState = SurfaceState.healthy()
    distal: SurfaceState = SurfaceState.healthy()
    buccal: SurfaceState = SurfaceState.healthy()
    lingual: SurfaceState = SurfaceState.healthy()


class ToothDataV3(BaseModel):
    """Un diente en formato v3.0 del odontograma."""
    id: int                          # FDI number
    state: str = "healthy"           # Estado global (retrocompat)
    surfaces: ToothSurfacesV3 = ToothSurfacesV3()
    notes: str = ""


class DentitionData(BaseModel):
    """Una denticion completa (permanente o decidua)."""
    teeth: List[ToothDataV3]


class OdontogramV3(BaseModel):
    """Formato v3.0 del odontograma completo."""
    version: Literal["3.0"] = "3.0"
    last_updated: str = ""
    active_dentition: DentitionType = "permanent"
    permanent: DentitionData
    deciduous: DentitionData
```

**Decision:** Los modelos existentes `ToothSurface` y `ToothData` NO se modifican. Los nuevos modelos v3 coexisten. El parser unificado opera sobre dicts y retorna un `OdontogramV3`, que luego se serializa a dict para guardar en JSONB.

### 2.6. Parser unificado — `shared/odontogram_utils.py`

Archivo nuevo. Funcion pura, sin I/O, sin efectos secundarios.

```python
# shared/odontogram_utils.py

from shared.odontogram_states import LEGACY_STATE_MAP, ODONTOGRAM_STATES_BY_ID

def parse_odontogram_data(raw: Any) -> dict:
    """
    Normaliza cualquier formato de odontograma a v3.0.
    Acepta: None, str (JSON), dict (v1/v2/v3), valores invalidos.
    Retorna siempre un dict v3.0 valido sin lanzar excepciones.
    """

def build_default_permanent_teeth() -> list[dict]:
    """32 dientes permanentes (FDI 11-48) todos en estado healthy."""

def build_default_deciduous_teeth() -> list[dict]:
    """20 dientes deciduos (FDI 51-85) todos en estado healthy."""

def _migrate_v1_to_v3(data: dict) -> dict:
    """Legacy dict {"18": "caries"} o {"18": {"status": "caries"}} → v3.0"""

def _migrate_v2_to_v3(data: dict) -> dict:
    """v2.0 {"version": "2.0", "teeth": [...]} → v3.0"""

def _migrate_surface_string_to_object(surface_val) -> dict:
    """String plano "caries" → {"state": "caries", "condition": null, "color": null}"""

def _resolve_legacy_state(state: str) -> str:
    """Mapea estados v1 a sus equivalentes v2 via LEGACY_STATE_MAP."""

def compute_global_state(surfaces: dict) -> str:
    """
    Heuristica: si todas las superficies no-null tienen el mismo state → ese state.
    Si hay mezcla → "healthy" (estado real se lee por superficie).
    """
```

**Cadena de parseo:**

```
raw input
  │
  ├── None / invalido → v3.0 con todos healthy
  │
  ├── str → json.loads → dict → continuar
  │
  ├── dict sin "version" ni "teeth" (v1 legacy)
  │   → _migrate_v1_to_v3 → v3.0
  │
  ├── dict con "teeth" y sin "permanent" (v2.0)
  │   → _migrate_v2_to_v3 → v3.0
  │
  └── dict con "version": "3.0" (v3.0)
      → validar estructura → retornar (upgrade surfaces si necesario)
```

**Consumidores:**
- `admin_routes.py` — GET endpoint llama `parse_odontogram_data()` antes de retornar
- `admin_routes.py` — PUT endpoint llama `parse_odontogram_data()` para normalizar input antes de guardar
- `odontogram_svg.py` — `normalize_odontogram_data()` se convierte en thin wrapper de `parse_odontogram_data()`
- `nova_tools.py` — `_parse_odontogram_data()` se convierte en thin wrapper de `parse_odontogram_data()`

---

## 3. Catalogo de Estados

### 3.1. Estructura del catalogo

El catalogo define 42 estados: 25 preexistentes + 17 lesiones.

**Interfaz TypeScript:**

```typescript
// frontend_react/src/constants/odontogramStates.ts

export type OdontogramCategory = 'preexistente' | 'lesion';

export interface PrintColor {
  fill: string;    // HEX para relleno en PDF (fondo blanco)
  stroke: string;  // HEX para borde en PDF
}

export interface OdontogramState {
  id: string;                   // snake_case, unico global
  category: OdontogramCategory;
  labelKey: string;             // "odontogram.states.{id}" (i18n)
  defaultColor: string;         // HEX para pantalla (fondo oscuro)
  symbol: string;               // 1-3 chars, unico dentro de su categoria
  printColor: PrintColor;       // colores para PDF
}
```

**Dataclass Python:**

```python
# shared/odontogram_states.py

@dataclass(frozen=True)
class OdontogramStateEntry:
    id: str
    category: str            # "preexistente" | "lesion"
    label_key: str           # "odontogram.states.{id}"
    default_color: str       # HEX pantalla
    symbol: str
    print_fill: str          # HEX fill PDF
    print_stroke: str        # HEX stroke PDF
```

### 3.2. Catalogo completo (42 estados)

**Preexistentes (25):**

| # | ID | Label ES | Symbol | Color Pantalla | Print Fill | Print Stroke |
|---|-----|----------|--------|---------------|------------|--------------|
| 1 | `healthy` | Sano | `○` | `#f0f0f0` | `#f5f5f5` | `#9ca3af` |
| 2 | `implante` | Implante | `Im` | `#6366f1` | `#e0e7ff` | `#4338ca` |
| 3 | `radiografia` | Radiografia | `Rx` | `#f59e0b` | `#fef3c7` | `#d97706` |
| 4 | `restauracion_resina` | Restauracion resina | `Rr` | `#3b82f6` | `#dbeafe` | `#1d4ed8` |
| 5 | `restauracion_amalgama` | Restauracion amalgama | `Ra` | `#6b7280` | `#e5e7eb` | `#374151` |
| 6 | `restauracion_temporal` | Restauracion temporal | `Rt` | `#a78bfa` | `#ede9fe` | `#7c3aed` |
| 7 | `sellador_fisuras` | Sellador de fisuras | `Sf` | `#10b981` | `#d1fae5` | `#065f46` |
| 8 | `carilla` | Carilla | `Ca` | `#ec4899` | `#fce7f3` | `#be185d` |
| 9 | `puente` | Puente | `Pu` | `#8b5cf6` | `#ede9fe` | `#6d28d9` |
| 10 | `corona_porcelana` | Corona porcelana | `Cp` | `#d946ef` | `#fae8ff` | `#a21caf` |
| 11 | `corona_resina` | Corona resina | `Cr` | `#a855f7` | `#f3e8ff` | `#7e22ce` |
| 12 | `corona_metalceramica` | Corona metalceramica | `Cm` | `#7c3aed` | `#ede9fe` | `#5b21b6` |
| 13 | `corona_temporal` | Corona temporal | `Ct` | `#d946ef` | `#f5f3ff` | `#9333ea` |
| 14 | `incrustacion` | Incrustacion | `In` | `#14b8a6` | `#fdf2f8` | `#db2777` |
| 15 | `onlay` | Onlay | `On` | `#0d9488` | `#fdf4ff` | `#c026d3` |
| 16 | `poste` | Poste | `Po` | `#f97316` | `#ffedd5` | `#c2410c` |
| 17 | `perno` | Perno | `Pe` | `#ea580c` | `#fed7aa` | `#9a3412` |
| 18 | `fibras_ribbond` | Fibras Ribbond | `FR` | `#84cc16` | `#ecfccb` | `#4d7c0f` |
| 19 | `tratamiento_conducto` | Tratamiento de conducto | `Tc` | `#f97316` | `#fed7aa` | `#ea580c` |
| 20 | `protesis_removible` | Protesis removible | `Pr` | `#14b8a6` | `#99f6e4` | `#0d9488` |
| 21 | `diente_erupcion` | Diente en erupcion | `Ep` | `#22c55e` | `#dcfce7` | `#16a34a` |
| 22 | `diente_no_erupcionado` | Diente no erupcionado | `NE` | `#a3a3a3` | `#e5e5e5` | `#737373` |
| 23 | `ausente` | Ausente | `--` | `#d4d4d4` | `#fafafa` | `#ced4da` |
| 24 | `otra_preexistencia` | Otra preexistencia | `OP` | `#78716c` | `#e7e5e4` | `#57534e` |
| 25 | `treatment_planned` | Plan de tratamiento | `Tp` | `#f59e0b` | `#fef08a` | `#ca8a04` |

**Lesiones (17):**

| # | ID | Label ES | Symbol | Color Pantalla | Print Fill | Print Stroke |
|---|-----|----------|--------|---------------|------------|--------------|
| 26 | `mancha_blanca` | Mancha blanca | `MB` | `#fef3c7` | `#fffbeb` | `#d97706` |
| 27 | `surco_profundo` | Surco profundo | `SP` | `#fbbf24` | `#fef9c3` | `#a16207` |
| 28 | `caries` | Caries | `C` | `#ef4444` | `#fecaca` | `#dc2626` |
| 29 | `caries_penetrante` | Caries penetrante | `CP` | `#b91c1c` | `#fca5a5` | `#991b1b` |
| 30 | `necrosis_pulpar` | Necrosis pulpar | `Np` | `#1f2937` | `#d1d5db` | `#111827` |
| 31 | `proceso_apical` | Proceso apical | `PA` | `#dc2626` | `#fecaca` | `#b91c1c` |
| 32 | `fistula` | Fistula | `Fi` | `#f97316` | `#fed7aa` | `#c2410c` |
| 33 | `indicacion_extraccion` | Indicacion de extraccion | `Ex` | `#ef4444` | `#f5f5f5` | `#adb5bd` |
| 34 | `abrasion` | Abrasion | `Ab` | `#fb923c` | `#ffedd5` | `#ea580c` |
| 35 | `abfraccion` | Abfraccion | `Af` | `#fcd34d` | `#fef9c3` | `#ca8a04` |
| 36 | `atricion` | Atricion | `At` | `#f59e0b` | `#fef3c7` | `#b45309` |
| 37 | `erosion` | Erosion | `Er` | `#fdba74` | `#ffedd5` | `#c2410c` |
| 38 | `fractura_horizontal` | Fractura horizontal | `Fh` | `#ef4444` | `#fecaca` | `#b91c1c` |
| 39 | `fractura_vertical` | Fractura vertical | `Fv` | `#dc2626` | `#fca5a5` | `#991b1b` |
| 40 | `movilidad` | Movilidad | `Mo` | `#fb7185` | `#fecdd3` | `#e11d48` |
| 41 | `hipomineralizacion_mih` | Hipomineralizacion MIH | `MH` | `#fbbf24` | `#fef9c3` | `#a16207` |
| 42 | `otra_lesion` | Otra lesion | `OL` | `#78716c` | `#e7e5e4` | `#57534e` |

### 3.3. Mapa de retrocompatibilidad — LEGACY_STATE_MAP

```python
LEGACY_STATE_MAP = {
    # v1 state ID          → v2 state ID
    "healthy":              "healthy",
    "caries":               "caries",
    "restoration":          "restauracion_resina",
    "root_canal":           "tratamiento_conducto",
    "crown":                "corona_porcelana",
    "implant":              "implante",
    "prosthesis":           "protesis_removible",
    "extraction":           "indicacion_extraccion",
    "missing":              "ausente",
    "treatment_planned":    "treatment_planned",
    # Surface legacy states
    "treated":              "restauracion_resina",
}
```

### 3.4. Funciones de lookup

**TypeScript:**
```typescript
export function getStateById(id: string): OdontogramState | undefined;
export function getStatesByCategory(cat: OdontogramCategory): OdontogramState[];
export function resolveColor(stateId: string, customColor?: string | null): string;
// resolveColor retorna customColor si existe, o defaultColor del catalogo
```

**Python:**
```python
def get_state(id: str) -> OdontogramStateEntry | None:
    return ODONTOGRAM_STATES_BY_ID.get(id)

def resolve_print_color(state_id: str, custom_color: str | None = None) -> dict:
    """Retorna {"fill": ..., "stroke": ...} para rendering PDF."""
    if custom_color:
        return {"fill": f"{custom_color}33", "stroke": custom_color}
    entry = get_state(state_id)
    if entry:
        return {"fill": entry.print_fill, "stroke": entry.print_stroke}
    return PRINT_FILLS["healthy"]
```

### 3.5. Generacion de STATE_FILLS para React

Los colores de pantalla del catalogo se transforman en el formato `{fill, stroke, glow}` que el componente React espera:

```typescript
export function buildStateFills(): Record<string, { fill: string; stroke: string; glow: string }> {
  const fills: Record<string, { fill: string; stroke: string; glow: string }> = {};
  for (const state of ODONTOGRAM_STATES) {
    const hex = state.defaultColor;
    if (state.id === 'healthy') {
      fills[state.id] = {
        fill: 'rgba(255,255,255,0.06)',
        stroke: 'rgba(255,255,255,0.20)',
        glow: '',
      };
    } else {
      fills[state.id] = {
        fill: `${hex}1F`,           // hex + 12% opacidad
        stroke: hex,
        glow: `drop-shadow(0 0 4px ${hex}4D)`,
      };
    }
  }
  return fills;
}

export const STATE_FILLS = buildStateFills();
```

---

## 4. Arquitectura de Componentes React

### 4.1. Arbol de componentes

```
frontend_react/src/components/
├── Odontogram.tsx                          ← Punto de entrada (no se mueve)
└── odontogram/                             ← NUEVO directorio
    ├── OdontogramTabs.tsx                  ← Tab bar
    ├── DentitionChart.tsx                  ← Renderer de cuadrantes
    ├── ToothSVG.tsx                        ← Pieza individual (extraido)
    ├── SurfacePath.tsx                     ← Superficie clickeable
    ├── SymbolSelectorModal.tsx             ← Selector de estados
    ├── StateConditionModal.tsx             ← Condicion + color
    ├── OdontogramLegend.tsx                ← Leyenda dinamica
    ├── MobileToothZoom.tsx                 ← Zoom para mobile
    ├── constants.ts                        ← Cuadrantes, paths SVG, keys
    └── types.ts                            ← Interfaces compartidas
```

### 4.2. Interfaces compartidas — `odontogram/types.ts`

```typescript
export type DentitionType = 'permanent' | 'deciduous';
export type SurfaceKey = 'buccal' | 'distal' | 'lingual' | 'mesial' | 'occlusal';
export type DentalCondition = 'bueno' | 'malo' | 'indefinido';

export interface SurfaceState {
  state: string;
  condition: DentalCondition | null;
  color: string | null;
}

export interface ToothSurfaces {
  buccal: SurfaceState;
  distal: SurfaceState;
  lingual: SurfaceState;
  mesial: SurfaceState;
  occlusal: SurfaceState;
}

export interface ToothState {
  id: number;
  state: string;
  surfaces: ToothSurfaces;
  notes: string;
}

export interface QuadrantConfig {
  ids: number[];
  position: 'upper-right' | 'upper-left' | 'lower-right' | 'lower-left';
  numbersBelow: boolean;
}

export interface OdontogramV3Data {
  version: '3.0';
  last_updated: string;
  active_dentition: DentitionType;
  permanent: { teeth: ToothState[] };
  deciduous: { teeth: ToothState[] };
}
```

### 4.3. Estado del orquestador — `Odontogram.tsx`

```typescript
// ── Estado de datos ──
const [activeDentition, setActiveDentition] = useState<DentitionType>('permanent');
const [permanentTeeth, setPermanentTeeth]   = useState<ToothState[]>([]);
const [deciduousTeeth, setDecidousTeeth]    = useState<ToothState[]>([]);

// ── Estado de seleccion ──
const [selectedTooth, setSelectedTooth]       = useState<number | null>(null);
const [selectedSurface, setSelectedSurface]   = useState<SurfaceKey | null>(null);

// ── Estado de animacion ──
const [changedTeeth, setChangedTeeth]         = useState<Set<number>>(new Set());
const [changedSurfaces, setChangedSurfaces]   = useState<Map<number, Set<SurfaceKey>>>(new Map());

// ── Estado de modales ──
const [symbolModalOpen, setSymbolModalOpen]         = useState(false);
const [conditionModalOpen, setConditionModalOpen]    = useState(false);
const [pendingStateId, setPendingStateId]            = useState<string | null>(null);
const [pendingStateName, setPendingStateName]        = useState('');
const [pendingDefaultColor, setPendingDefaultColor]  = useState('#ffffff');

// ── Estado de guardado ──
const [saving, setSaving]         = useState(false);
const [hasChanges, setHasChanges] = useState(false);
```

### 4.4. Props de cada componente

**`OdontogramTabs`:**
```typescript
interface OdontogramTabsProps {
  active: DentitionType;
  onChange: (dentition: DentitionType) => void;
  hasDataPermanent: boolean;
  hasDataDeciduous: boolean;
  readOnly?: boolean;
}
```

**`DentitionChart`:**
```typescript
interface DentitionChartProps {
  quadrants: QuadrantConfig[];
  teeth: ToothState[];
  selectedTooth: number | null;
  selectedSurface: SurfaceKey | null;
  changedTeeth: Set<number>;
  changedSurfaces: Map<number, Set<SurfaceKey>>;
  readOnly: boolean;
  onToothClick: (toothId: number) => void;
  onSurfaceClick: (toothId: number, surface: SurfaceKey) => void;
}
```

**`ToothSVG`:**
```typescript
interface ToothSVGProps {
  toothId: number;
  state: string;
  surfaces: ToothSurfaces;
  isSelected: boolean;
  selectedSurface: SurfaceKey | null;
  changedSurfaces: Set<SurfaceKey>;
  readOnly: boolean;
  justChanged: boolean;
  onClick: () => void;
  onSurfaceClick: (surface: SurfaceKey) => void;
}
```

**`SurfacePath`:**
```typescript
interface SurfacePathProps {
  surfaceKey: SurfaceKey;
  path?: string;             // undefined para occlusal (usa <circle>)
  surfaceState: SurfaceState;
  fallbackToothState: string;
  isToothSelected: boolean;
  isSurfaceSelected: boolean;
  isAbsent: boolean;
  readOnly: boolean;
  justChanged: boolean;
  onClick: (e: React.MouseEvent, surface: SurfaceKey) => void;
}
```

**`SymbolSelectorModal`:**
```typescript
interface SymbolSelectorModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSelect: (stateId: string) => void;
  currentState?: string;
  toothId: number;
  surfaceName?: string;
}
```

**`StateConditionModal`:**
```typescript
interface StateConditionModalProps {
  isOpen: boolean;
  onClose: () => void;
  onApply: (condition: DentalCondition, color: string) => void;
  onBack: () => void;
  stateId: string;
  stateName: string;
  defaultColor: string;
  currentCondition?: DentalCondition;
  currentColor?: string;
}
```

**`MobileToothZoom`:**
```typescript
interface MobileToothZoomProps {
  toothId: number;
  surfaces: ToothSurfaces;
  toothState: string;
  position: { top: number; left: number };
  onSurfaceClick: (surface: SurfaceKey) => void;
  onClose: () => void;
}
```

**`OdontogramLegend`:**
```typescript
interface OdontogramLegendProps {
  usedStates: Set<string>;   // solo los state IDs presentes en el chart
}
```

### 4.5. Flujo de datos

```
              Odontogram.tsx (estado)
              ┌──────────────┐
              │ permanentTeeth│──── teeth[] ───→ DentitionChart
              │ deciduousTeeth│                   └── ToothSVG × N
              │ activeDentition                       └── SurfacePath × 5
              │ selectedTooth │
              │ selectedSurface
              │ symbolModalOpen
              │ conditionModalOpen
              │ pendingState* │
              └───┬──────┬───┘
                  │      │
     callbacks ◄──┘      └──► modales controlados
     onToothClick              SymbolSelectorModal
     onSurfaceClick            StateConditionModal
     handleSymbolSelect
     handleConditionApply
     handleConditionBack
```

**Principio:** Los datos fluyen hacia abajo (props). Las acciones fluyen hacia arriba (callbacks). Solo `Odontogram.tsx` muta el estado.

---

## 5. Flujo de Interaccion

### 5.1. Flujo principal — Editar una superficie

```
PASO 1: Tab Selection
  Usuario clickea tab "Permanente" o "Temporal"
  → setActiveDentition(tipo)
  → DentitionChart recibe el array de teeth correspondiente
  → Animacion slide horizontal 300ms

PASO 2: Tooth Selection (Nivel 1)
  Usuario clickea en una pieza dental
  → handleToothClick(toothId)
  → setSelectedTooth(toothId), setSelectedSurface(null)
  → ToothSVG muestra anillo azul animado (scale 1.15)
  → Lineas divisorias se hacen mas visibles (opacity 0.6)
  → En mobile (<768px): aparece MobileToothZoom

PASO 3: Surface Selection (Nivel 2)
  Usuario clickea en una superficie dentro de la pieza seleccionada
  → SurfacePath llama e.stopPropagation() + onClick(surfaceKey)
  → handleSurfaceClick(toothId, surfaceKey)
  → setSelectedSurface(surfaceKey)
  → Surface resaltada (stroke-width 2.5, glow, surfacePulse animation)
  → setSymbolModalOpen(true)

PASO 4: Symbol Selection
  SymbolSelectorModal se abre
  → Muestra ~42 estados en grilla 2 columnas con busqueda
  → Usuario busca/selecciona un estado → click "Siguiente"
  → handleSymbolSelect(stateId)
  → setPendingStateId, setPendingStateName, setPendingDefaultColor
  → setSymbolModalOpen(false), setConditionModalOpen(true)

PASO 5: Condition + Color
  StateConditionModal se abre
  → Muestra 3 botones condicion (Bueno/Malo/Indefinido)
  → Muestra color swatch + HEX input + 10 presets
  → Default: condicion="indefinido", color=defaultColor del catalogo
  → Usuario configura → click "Aplicar"
  → handleConditionApply(condition, color)

PASO 6: Apply
  → applySurfaceState(toothId, surfaceKey, {state, condition, color})
  → Actualiza surfaces[surfaceKey] en el tooth del array activo
  → Recalcula tooth.state via computeGlobalState()
  → Marca superficie como changed (animacion surfacePop 350ms)
  → setConditionModalOpen(false)
  → setHasChanges(true)

PASO 7: Save
  Boton flotante "Guardar" (visible cuando hasChanges=true)
  → Serializa OdontogramV3Data
  → PUT /admin/patients/{id}/records/{id}/odontogram
  → WebSocket event ODONTOGRAM_UPDATED
  → setHasChanges(false), feedback visual (checkmark)
```

### 5.2. Flujo alternativo — Volver al selector de simbolos

```
En StateConditionModal, click "← Volver"
→ handleConditionBack()
→ setConditionModalOpen(false)
→ setSymbolModalOpen(true) con pendingStateId como currentState
→ El usuario puede re-seleccionar otro estado
```

### 5.3. Flujo alternativo — Cancelar

```
En cualquier modal, click X o overlay
→ onClose() → cierra ambos modales
→ La superficie no se modifica
→ selectedSurface se mantiene (puede re-abrir el flujo)
```

### 5.4. Flujo mobile

```
Viewport < 768px:
  Tooth click → MobileToothZoom aparece (3x, posicionado via getBoundingClientRect)
  → Usuario toca superficie en el panel ampliado
  → MobileToothZoom cierra
  → Nivel 2 se activa + SymbolSelectorModal se abre como bottom sheet (85vh)
  → StateConditionModal se abre centrado (max-w-sm)
```

### 5.5. Diagrama de estados de los modales

```
                 ┌───────────┐
     surface     │  CLOSED   │◄─── X / overlay en cualquier modal
     click       └─────┬─────┘
                       │
                       ▼
              ┌────────────────┐
              │ SYMBOL_MODAL   │
              │ (selecting)    │
              └───┬────────┬───┘
          onSelect│        │onClose
                  ▼        ▼
         ┌──────────────┐  CLOSED
         │CONDITION_MODAL│
         └──┬──────┬──┬──┘
    onApply │ onBack│  │onClose
            ▼      ▼  ▼
         CLOSED  SYMBOL_MODAL  CLOSED
```

---

## 6. Diseno de API

### 6.1. PUT — Actualizar odontograma

**Endpoint:** `PUT /admin/patients/{patient_id}/records/{record_id}/odontogram`

**Headers:** `Authorization: Bearer <JWT>`, `X-Admin-Token: <token>`

**Body — formato v3.0 (nuevo):**
```json
{
  "odontogram_data": {
    "version": "3.0",
    "last_updated": "2026-04-02T15:30:00Z",
    "active_dentition": "permanent",
    "permanent": {
      "teeth": [
        {
          "id": 18,
          "state": "healthy",
          "surfaces": {
            "occlusal": { "state": "caries", "condition": "malo", "color": "#ef4444" },
            "mesial": { "state": "healthy", "condition": null, "color": null },
            "distal": { "state": "healthy", "condition": null, "color": null },
            "buccal": { "state": "healthy", "condition": null, "color": null },
            "lingual": { "state": "healthy", "condition": null, "color": null }
          },
          "notes": ""
        }
      ]
    },
    "deciduous": {
      "teeth": []
    }
  }
}
```

**Body — formato v2.0 (backward compat, sigue aceptado):**
```json
{
  "odontogram_data": {
    "version": "2.0",
    "teeth": [
      { "id": 18, "state": "caries", "surfaces": {}, "notes": "" }
    ]
  }
}
```

**Comportamiento del endpoint:**
1. Extrae `tenant_id` del JWT (Sovereignty Protocol)
2. Valida que el `clinical_record` pertenece al `patient_id` y `tenant_id`
3. Llama `parse_odontogram_data(odontogram_data)` para normalizar a v3.0
4. Persiste el resultado v3.0 en `clinical_records.odontogram_data`
5. Retorna `{"status": "ok", "odontogram_version": "3.0"}`

### 6.2. GET — Obtener odontograma

**Endpoint:** `GET /admin/patients/{patient_id}/records/{record_id}/odontogram`

**Respuesta — SIEMPRE v3.0:**
```json
{
  "odontogram_data": {
    "version": "3.0",
    "last_updated": "2026-04-02T15:30:00Z",
    "active_dentition": "permanent",
    "permanent": { "teeth": [...] },
    "deciduous": { "teeth": [...] }
  },
  "odontogram_version": "3.0"
}
```

**Comportamiento:**
1. Lee `odontogram_data` del registro
2. Si es v1 o v2 → `parse_odontogram_data()` lo convierte a v3.0 en memoria
3. Retorna v3.0 (NO escribe la conversion — eso lo hace el siguiente PUT)

### 6.3. Alembic 017

**Archivo:** `orchestrator_service/alembic/versions/017_odontogram_v3_format.py`

**upgrade():**
```python
def upgrade():
    """
    Odontograma v3.0 — denticion dual + superficies independientes.

    No altera la columna odontogram_data (ya es JSONB).
    Agrega indice GIN para queries futuras sobre estados.
    La migracion de datos es on-read: el parser convierte v1/v2 → v3 al leer.
    """
    op.execute("""
        CREATE INDEX CONCURRENTLY IF NOT EXISTS
        idx_clinical_records_odontogram_gin
        ON clinical_records USING GIN (odontogram_data)
    """)
```

**downgrade():**
```python
def downgrade():
    op.execute("DROP INDEX IF EXISTS idx_clinical_records_odontogram_gin")
```

**Nota:** La migracion es NO destructiva. Solo agrega un indice. Los datos existentes siguen funcionando sin tocar.

---

## 7. Diseno Nova Tools

### 7.1. `ver_odontograma` — Lectura

**Schema actualizado:**
```python
{
    "type": "function",
    "name": "ver_odontograma",
    "description": "Ver el odontograma de un paciente. Muestra piezas con hallazgos por superficie.",
    "parameters": {
        "type": "object",
        "properties": {
            "patient_id": {"type": "integer", "description": "ID del paciente"},
            "denticion": {
                "type": "string",
                "enum": ["permanente", "temporal"],
                "default": "permanente",
                "description": "Tipo de denticion a consultar"
            }
        },
        "required": ["patient_id"]
    }
}
```

**Logica interna:**
1. Lee `odontogram_data` del ultimo `clinical_record` del paciente
2. Llama `parse_odontogram_data()` (parser unificado)
3. Extrae `permanent.teeth` o `deciduous.teeth` segun `denticion`
4. Para cada pieza con hallazgos (state != "healthy" o superficies != healthy):
   - Muestra FDI + nombre anatomico + estado global
   - Lista superficies afectadas: `oclusal=caries [malo, #ef4444]`
5. Resumen: `N/32 piezas sanas` (permanente) o `N/20 piezas sanas` (temporal)

**Output ejemplo:**
```
Odontograma PERMANENTE de Juan Pérez:

Cuadrante Superior Derecho:
  Pieza 16 (1er molar sup-der):
    Estado: caries
    Superficies: oclusal=caries [malo] | distal=restauracion_resina [bueno, #3b82f6]

Cuadrante Inferior Izquierdo:
  Pieza 36 (1er molar inf-izq):
    Estado: restauracion_resina
    Superficies: oclusal=restauracion_resina [bueno]

Resumen: 30/32 piezas sanas | Preexistente: 1 | Lesión: 1
```

### 7.2. `modificar_odontograma` — Escritura

**Schema actualizado:**
```python
{
    "type": "function",
    "name": "modificar_odontograma",
    "description": "Modificar el odontograma. Soporta estados por superficie con condicion y color.",
    "parameters": {
        "type": "object",
        "properties": {
            "patient_id": {"type": "integer"},
            "piezas": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "pieza": {"type": "integer", "description": "Numero FDI"},
                        "estado": {"type": "string", "enum": [/* 42 estados */]},
                        "superficies": {
                            "type": "object",
                            "description": "Estados por superficie (parcial)",
                            "properties": {
                                "oclusal":    {"type": "object", "properties": {"estado": {"type": "string"}, "condicion": {"type": "string"}, "color": {"type": "string"}}},
                                "mesial":     {"$ref": "#oclusal"},
                                "distal":     {"$ref": "#oclusal"},
                                "vestibular": {"$ref": "#oclusal"},
                                "lingual":    {"$ref": "#oclusal"}
                            }
                        },
                        "notas": {"type": "string"}
                    },
                    "required": ["pieza"]
                }
            },
            "denticion": {
                "type": "string",
                "enum": ["permanente", "temporal"],
                "default": "permanente"
            },
            "diagnostico": {"type": "string"}
        },
        "required": ["patient_id", "piezas"]
    }
}
```

**Logica interna:**
1. Lee el odontograma actual → `parse_odontogram_data()` → v3.0
2. Valida que los FDIs corresponden a la denticion indicada
3. Para cada pieza en `piezas`:
   - Si tiene `estado`: actualiza `tooth.state` y todas las superficies al mismo estado
   - Si tiene `superficies`: merge parcial — solo sobreescribe las superficies enviadas
   - Si tiene `notas`: actualiza `tooth.notes`
4. Construye el JSONB v3.0 completo (ambas denticiones)
5. Persiste con `active_dentition` = la denticion modificada

**Validaciones FDI:**
```python
_VALID_FDI_PERMANENTE = {11,12,13,14,15,16,17,18,21,22,23,24,25,26,27,28,
                         31,32,33,34,35,36,37,38,41,42,43,44,45,46,47,48}
_VALID_FDI_DECIDUA    = {51,52,53,54,55,61,62,63,64,65,
                         71,72,73,74,75,81,82,83,84,85}
```

### 7.3. Mapeo de superficies Nova ↔ JSONB

Nova usa nombres en espanol → se mapean a claves JSONB:

```python
_SURFACE_MAP = {
    "oclusal":    "occlusal",
    "mesial":     "mesial",
    "distal":     "distal",
    "vestibular": "buccal",
    "lingual":    "lingual",
    "palatino":   "lingual",  # alias
}
```

---

## 8. Diseno SVG/PDF Renderer

### 8.1. Pipeline de rendering

```
odontogram_data (JSONB)
  │
  ▼
parse_odontogram_data()        ← Parser unificado
  │
  ├── permanent.teeth → render_chart_section("Denticion Permanente", ...)
  │                       └── render_tooth_group() × 32
  │                            └── render_surface_path() × 5  ← NUEVO: per-surface fill
  │
  └── deciduous.teeth → render_chart_section("Denticion Temporal", ...)  ← CONDICIONAL
                          └── render_tooth_group() × 20
                               └── render_surface_path() × 5
  │
  ├── render_legend(states_present)   ← DINAMICA: solo estados usados
  │
  └── render_summary(permanent, deciduous)  ← DESGLOSADO: por denticion + categoria
```

### 8.2. Funcion principal refactorizada

```python
def render_odontogram_svg(
    odontogram_data: Any,
    include_deciduous: bool = True
) -> dict:
    """
    Retorna:
    {
        "permanent_svg": str,     # SVG del chart permanente
        "deciduous_svg": str,     # SVG del chart temporal (vacio si no aplica)
        "legend_svg": str,        # SVG de leyenda
        "summary_html": str,      # HTML de resumen
    }
    """
    parsed = parse_odontogram_data(odontogram_data)
    # ...
```

### 8.3. Coloring per-surface

La funcion `_render_tooth_group` pasa de aplicar un color uniforme a renderizar cada path SVG con su propio color:

```python
def _render_tooth_group(tooth_data: dict, x: int, y: int) -> str:
    """Genera el SVG de un diente individual con colores por superficie."""
    surfaces = tooth_data.get("surfaces", {})
    global_state = tooth_data.get("state", "healthy")

    svg_parts = []
    for svg_key, data_key in SURFACE_SVG_MAP.items():
        surface_state = surfaces.get(data_key, {})
        effective_state = surface_state.get("state") or global_state
        custom_color = surface_state.get("color")
        fills = resolve_print_color(effective_state, custom_color)

        if svg_key == "center":
            svg_parts.append(f'<circle cx="{x+20}" cy="{y+20}" r="7" '
                           f'fill="{fills["fill"]}" stroke="{fills["stroke"]}" '
                           f'stroke-width="0.8"/>')
        else:
            svg_parts.append(f'<path d="{SURFACE_PATHS[svg_key]}" '
                           f'fill="{fills["fill"]}" stroke="{fills["stroke"]}" '
                           f'stroke-width="0.8" transform="translate({x},{y})"/>')

    # Overlay para whole-tooth states (ausente, extraccion)
    if effective_state in ("ausente", "indicacion_extraccion"):
        svg_parts.append(_render_whole_tooth_overlay(x, y, effective_state))

    return "\n".join(svg_parts)
```

**Mapeo SVG ↔ Datos:**
```python
SURFACE_SVG_MAP = {
    "top":    "buccal",
    "right":  "distal",
    "bottom": "lingual",
    "left":   "mesial",
    "center": "occlusal",
}
```

### 8.4. Seccion temporal condicional

```python
def _has_deciduous_data(deciduous_teeth: list) -> bool:
    """True si al menos una pieza temporal tiene estado != healthy."""
    return any(
        t.get("state", "healthy") != "healthy" or
        any(s.get("state", "healthy") != "healthy"
            for s in t.get("surfaces", {}).values()
            if isinstance(s, dict))
        for t in deciduous_teeth
    )
```

Si `_has_deciduous_data()` retorna `True`, se renderiza una segunda seccion con:
- Cabecera "Denticion Temporal" en negrita
- Layout de 4 cuadrantes con 5 piezas cada uno
- Mismo tamano de pieza (38px) centrado en el SVG_WIDTH

### 8.5. Leyenda dinamica

```python
def _render_legend(states_present: set[str]) -> str:
    """Genera leyenda SVG solo con los estados que aparecen."""
    # Filtrar: excluir "healthy", ordenar por STATE_ORDER
    visible = [s for s in STATE_ORDER if s in states_present and s != "healthy"]
    # Renderizar en filas de 4 columnas
    # Cada item: swatch de color + simbolo + label
```

### 8.6. Template HTML actualizado

`orchestrator_service/templates/digital_records/odontogram_art.html`:

```html
<!-- Denticion permanente (siempre) -->
<h3>Denticion Permanente</h3>
{{ permanent_svg | safe }}

<!-- Denticion temporal (condicional) -->
{% if deciduous_svg %}
<h3>Denticion Temporal</h3>
{{ deciduous_svg | safe }}
{% endif %}

<!-- Leyenda -->
{{ legend_svg | safe }}

<!-- Resumen con columna Condicion -->
{{ summary_html | safe }}
```

### 8.7. Integracion con digital_records_service.py

```python
# En gather_patient_data():
odontogram_result = render_odontogram_svg(
    odontogram_data=record.get("odontogram_data"),
    include_deciduous=True
)
context["permanent_svg"] = odontogram_result["permanent_svg"]
context["deciduous_svg"] = odontogram_result["deciduous_svg"]
context["legend_svg"] = odontogram_result["legend_svg"]
context["summary_html"] = odontogram_result["summary_html"]
```

---

## 9. Estrategia de Migracion

### 9.1. Cadena de parseo completa

```
                  ┌──────────────┐
                  │ raw input    │
                  └──────┬───────┘
                         │
                    ┌────▼────┐
                    │ None?   │──── Si → v3.0 default (todos healthy)
                    └────┬────┘
                         │ No
                    ┌────▼────┐
                    │ string? │──── Si → json.loads → dict
                    └────┬────┘
                         │ dict
                    ┌────▼───────────┐
                    │ has "version"  │
                    │ == "3.0"?      │──── Si → validar estructura, retornar
                    └────┬───────────┘
                         │ No
                    ┌────▼───────────┐
                    │ has "teeth"    │
                    │ (array)?       │──── Si → v2.0 → _migrate_v2_to_v3
                    └────┬───────────┘
                         │ No
                    ┌────▼───────────┐
                    │ dict con claves│
                    │ numericas?     │──── Si → v1 legacy → _migrate_v1_to_v3
                    └────┬───────────┘
                         │ No
                    ┌────▼───────────┐
                    │ Formato        │
                    │ desconocido    │──── v3.0 default (todos healthy, log warning)
                    └────────────────┘
```

### 9.2. Migracion v1 → v3

```python
def _migrate_v1_to_v3(data: dict) -> dict:
    """
    v1 legacy: {"18": "caries"} o {"18": {"status": "caries"}}
    """
    teeth = []
    for tooth_id_str, value in data.items():
        try:
            tooth_id = int(tooth_id_str)
        except (ValueError, TypeError):
            continue

        if isinstance(value, str):
            state = _resolve_legacy_state(value)
        elif isinstance(value, dict):
            state = _resolve_legacy_state(value.get("status", "healthy"))
        else:
            state = "healthy"

        # Todas las superficies heredan el estado global
        surface = {"state": state, "condition": None, "color": None}
        teeth.append({
            "id": tooth_id,
            "state": state,
            "surfaces": {
                "occlusal": surface.copy(),
                "mesial": surface.copy(),
                "distal": surface.copy(),
                "buccal": surface.copy(),
                "lingual": surface.copy(),
            },
            "notes": ""
        })

    # Completar piezas faltantes como healthy
    existing_ids = {t["id"] for t in teeth}
    for fdi in ALL_PERMANENT:
        if fdi not in existing_ids:
            teeth.append(_build_healthy_tooth(fdi))

    teeth.sort(key=lambda t: ALL_PERMANENT.index(t["id"]) if t["id"] in ALL_PERMANENT else 99)

    return _build_v3_envelope(teeth, build_default_deciduous_teeth())
```

### 9.3. Migracion v2 → v3

```python
def _migrate_v2_to_v3(data: dict) -> dict:
    """
    v2.0: {"version": "2.0", "teeth": [{id, state, surfaces, notes}]}
    surfaces puede ser {} o {"occlusal": "caries"} (string plano)
    """
    teeth = []
    for tooth in data.get("teeth", []):
        surfaces = {}
        raw_surfaces = tooth.get("surfaces", {})
        for key in ("occlusal", "mesial", "distal", "buccal", "lingual"):
            raw = raw_surfaces.get(key)
            if isinstance(raw, str):
                # v2 string format → v3 object
                surfaces[key] = {
                    "state": _resolve_legacy_state(raw),
                    "condition": None,
                    "color": None
                }
            elif isinstance(raw, dict) and "state" in raw:
                # Already v3-like
                surfaces[key] = raw
            else:
                # Missing → inherit global state
                surfaces[key] = {
                    "state": _resolve_legacy_state(tooth.get("state", "healthy")),
                    "condition": None,
                    "color": None
                }

        teeth.append({
            "id": tooth["id"],
            "state": _resolve_legacy_state(tooth.get("state", "healthy")),
            "surfaces": surfaces,
            "notes": tooth.get("notes", "")
        })

    return _build_v3_envelope(teeth, build_default_deciduous_teeth())
```

### 9.4. Edge cases

| Caso | Manejo |
|------|--------|
| `odontogram_data` es `None` | v3.0 default: 32 permanentes + 20 deciduos, todos healthy |
| `odontogram_data` es string JSON | `json.loads()` → continuar como dict |
| `odontogram_data` es string no-JSON | Log warning, retornar v3.0 default |
| v3.0 con `deciduous.teeth` vacio | Se completa con `build_default_deciduous_teeth()` |
| v3.0 con pieza sin `surfaces` key | Se inicializan 5 superficies healthy |
| Estado legacy no reconocido | `_resolve_legacy_state()` lo deja como esta (no se pierden datos) |
| FDI fuera de rango en teeth | Se ignora con log warning |

---

## 10. Performance

### 10.1. Optimizaciones React

**`React.memo` en componentes costosos:**
```typescript
// ToothSVG — solo re-renderiza si sus props cambian
export const ToothSVG = React.memo(function ToothSVG(props: ToothSVGProps) {
  // ...
});

// SurfacePath — solo re-renderiza si su surface state o selection cambia
export const SurfacePath = React.memo(function SurfacePath(props: SurfacePathProps) {
  // ...
});
```

**`useMemo` para datos derivados:**
```typescript
// Solo recalcular cuando cambia el array de teeth activo
const activeTeeth = useMemo(
  () => activeDentition === 'permanent' ? permanentTeeth : deciduousTeeth,
  [activeDentition, permanentTeeth, deciduousTeeth]
);

// Solo recalcular indicadores de contenido cuando cambian los arrays
const hasDataPermanent = useMemo(
  () => permanentTeeth.some(t => t.state !== 'healthy'),
  [permanentTeeth]
);

// Lookup O(1) para STATE_FILLS — calculado una vez
const STATE_FILLS = useMemo(() => buildStateFills(), []);
```

**Evitar re-renders en cascada:**
- `changedSurfaces` es un `Map<number, Set<SurfaceKey>>` — solo marca las superficies que realmente cambiaron
- `setChangedSurfaces` limpia despues de 500ms con `setTimeout` — no acumula referencias
- Cada `ToothSVG` recibe `changedSurfaces.get(toothId) ?? EMPTY_SET` — referencia estable si no cambio

**Patron de referencia estable:**
```typescript
const EMPTY_SET = new Set<SurfaceKey>();  // singleton, evita crear nuevo Set en cada render

// En DentitionChart:
<ToothSVG
  changedSurfaces={changedSurfaces.get(tooth.id) ?? EMPTY_SET}
  // ...
/>
```

### 10.2. Objetivo de performance

| Metrica | Target | Justificacion |
|---------|--------|---------------|
| Frame time al modificar 1 superficie | < 16ms | 60fps: solo 1 ToothSVG + 1 SurfacePath re-renderizan |
| Mount inicial de 32 dientes | < 50ms | 32 ToothSVG × 5 SurfacePath = 160 elementos SVG |
| Cambio de tab (32 → 20 dientes) | < 100ms | Desmonte + remonte + animacion |
| Apertura de SymbolSelectorModal | < 50ms | Lista de 42 items, busqueda sin debounce |
| SVG server-side render (PDF) | < 500ms | Sin interactividad, puro string building |

### 10.3. Optimizaciones SVG server-side

- Stateless: cada llamada a `render_odontogram_svg()` es independiente
- String concatenation con `join` (no f-strings repetidos)
- Pre-calcular `PRINT_FILLS` y `STATE_SYMBOLS` como diccionarios estáticos (lookup O(1))
- No usar templates Jinja para el SVG interno — solo para el wrapper HTML

---

## 11. Decisiones de Diseno (ADRs)

### ADR-001: Parser unico vs. parsers separados

**Contexto:** Existen dos parsers divergentes: `normalize_odontogram_data` (odontogram_svg.py) y `_parse_odontogram_data` (nova_tools.py). Ambos manejan los mismos datos con logica distinta.

**Decision:** Crear un modulo compartido `shared/odontogram_utils.py` con un parser unico. Los parsers existentes se convierten en thin wrappers que delegan al parser compartido.

**Consecuencias (+):** Eliminacion de bugs de divergencia. Un solo lugar para actualizar la logica de parseo. Tests unificados.

**Consecuencias (-):** Nuevo archivo shared que ambos servicios deben importar. Import path: `from shared.odontogram_utils import parse_odontogram_data`.

---

### ADR-002: Migracion on-read vs. batch SQL

**Contexto:** Migrar ~N registros de odontograma de v1/v2 a v3 en la base de datos.

**Decision:** Migracion on-read. No se ejecuta una migracion SQL batch. Los datos se convierten a v3.0 en memoria cuando se leen, y se persisten como v3.0 en el siguiente write.

**Consecuencias (+):** Zero-downtime. No hay riesgo de corrupcion de datos. Compatible con rollback. La migracion Alembic 017 es trivial (solo GIN index).

**Consecuencias (-):** Cada lectura de datos v1/v2 tiene overhead de conversion (despreciable: <1ms por registro). Los datos legacy permanecen en la DB hasta que el usuario guarde el odontograma.

---

### ADR-003: Catalogo duplicado Python/TypeScript

**Contexto:** El catalogo de estados debe estar disponible en frontend (React) y backend (FastAPI + SVG renderer).

**Decision:** Dos archivos espejo: `shared/odontogram_states.py` y `frontend_react/src/constants/odontogramStates.ts`. Sincronizacion por disciplina de commit.

**Alternativas descartadas:**
- Generar TS desde Python: agrega complejidad al build, rompe el flujo de desarrollo frontend
- Servir el catalogo via API: agrega latencia al mount del componente, dependency innecesaria
- JSON compartido importado por ambos: TypeScript no tiene tipado robusto sobre JSON importado

**Consecuencias:** Se agrega una nota en ambos archivos indicando que deben mantenerse sincronizados. CI podria agregar un check comparativo en el futuro.

---

### ADR-004: Estado global del diente como heuristica

**Contexto:** El campo `tooth.state` existia como unica fuente de verdad en v2. En v3, las superficies son la fuente de verdad.

**Decision:** `tooth.state` se mantiene como campo derivado (heuristica). Se calcula con `computeGlobalState()`: si todas las superficies tienen el mismo estado → ese es el global; si hay mezcla → `"healthy"`.

**Consecuencias:** Retrocompatibilidad para Nova (que puede preguntar el estado global), PDF renderer (que necesita un fallback), y datos legacy. El campo NO es autoridad — las superficies mandan.

---

### ADR-005: SymbolSelectorModal como bottom sheet en mobile

**Contexto:** El selector de ~42 estados necesita espacio vertical considerable.

**Decision:** Bottom sheet (85vh) en mobile, modal centrado en desktop. StateConditionModal siempre es modal centrado (pocos controles).

**Consecuencias:** Mejor UX mobile: el bottom sheet es un patron familiar (como Google Maps, WhatsApp). En desktop, el modal centrado permite ver el odontograma detras.

---

### ADR-006: No usar framer-motion

**Contexto:** Las animaciones del odontograma necesitan transiciones suaves (tabs, modales, superficies).

**Decision:** CSS keyframes + transition classes de Tailwind. No instalar framer-motion.

**Consecuencias (+):** Zero dependency adicional. El bundle no crece. Las animaciones son simples (translate, scale, opacity).

**Consecuencias (-):** Las animaciones de salida requieren el patron `isClosing` con `setTimeout` para completarse antes del desmontaje. Con framer-motion seria `AnimatePresence`, pero no justifica la dependencia.

---

### ADR-007: MobileToothZoom como componente separado

**Contexto:** Las superficies individuales son demasiado pequenas para touch en mobile (<768px).

**Decision:** Al seleccionar una pieza en mobile, aparece un panel flotante `MobileToothZoom` con la pieza ampliada a 3x. El usuario toca la superficie en el panel ampliado.

**Consecuencias:** UX mobile viable sin necesidad de zoom global (pinch-zoom rompe el scroll). Solo aparece en viewports <768px. Posicionamiento via `getBoundingClientRect()`.

---

### ADR-008: Color picker nativo del navegador

**Contexto:** StateConditionModal necesita un picker de color para personalizar el color de una superficie.

**Decision:** Usar `<input type="color">` nativo (oculto, disparado por click en el swatch). Complementar con 10 presets de colores dentales y un input HEX editable.

**Alternativas descartadas:**
- `react-colorful` / `react-color`: agregan dependencia, overkill para un picker secundario
- Paleta extendida custom: demasiado complejo, el picker nativo del SO ya es completo

**Consecuencias:** Funcionalidad completa sin dependencias. El picker nativo varia entre browsers pero es funcional en todos. El `<input type="color">` debe usar `className="sr-only"` (no `display:none`) para que `click()` funcione en todos los browsers.

---

## 12. Archivos a Crear/Modificar

### 12.1. Archivos NUEVOS

| Archivo | Descripcion | Spec |
|---------|-------------|------|
| `shared/odontogram_utils.py` | Parser unificado v1→v2→v3 + builders | data-model-evolution |
| `shared/odontogram_states.py` | Catalogo Python (42 estados + LEGACY_STATE_MAP) | state-catalog |
| `frontend_react/src/constants/odontogramStates.ts` | Catalogo TypeScript (42 estados + utilidades) | state-catalog |
| `frontend_react/src/components/odontogram/types.ts` | Interfaces compartidas | data-model-evolution |
| `frontend_react/src/components/odontogram/constants.ts` | Cuadrantes, paths SVG, keys | dentition-tabs |
| `frontend_react/src/components/odontogram/OdontogramTabs.tsx` | Tab bar Permanente/Temporal | dentition-tabs |
| `frontend_react/src/components/odontogram/DentitionChart.tsx` | Renderer generico cuadrantes | dentition-tabs |
| `frontend_react/src/components/odontogram/ToothSVG.tsx` | Pieza individual (extraido) | surface-selection |
| `frontend_react/src/components/odontogram/SurfacePath.tsx` | Superficie clickeable | surface-selection |
| `frontend_react/src/components/odontogram/SymbolSelectorModal.tsx` | Selector de estados | symbol-selector-modal |
| `frontend_react/src/components/odontogram/StateConditionModal.tsx` | Condicion + color | state-condition-color |
| `frontend_react/src/components/odontogram/OdontogramLegend.tsx` | Leyenda dinamica | state-catalog |
| `frontend_react/src/components/odontogram/MobileToothZoom.tsx` | Zoom mobile | surface-selection |
| `orchestrator_service/alembic/versions/017_odontogram_v3_format.py` | Migracion GIN index | data-model-evolution |

### 12.2. Archivos MODIFICADOS

| Archivo | Cambios | Spec |
|---------|---------|------|
| `shared/models_dental.py` | Agregar `SurfaceState`, `ToothSurfacesV3`, `ToothDataV3`, `DentitionData`, `OdontogramV3` (sin borrar existentes) | data-model-evolution |
| `frontend_react/src/components/Odontogram.tsx` | Refactoring mayor: estado dual denticion, handlers de superficie, orquestacion de modales, delegacion a sub-componentes | dentition-tabs, surface-selection, symbol-selector-modal, state-condition-color |
| `orchestrator_service/admin_routes.py` | PUT: normalizar input via parser antes de guardar. GET: retornar siempre v3.0. Agregar `odontogram_version` en response | data-model-evolution |
| `orchestrator_service/services/odontogram_svg.py` | Expandir PRINT_FILLS a 42 estados, per-surface coloring, seccion temporal, leyenda dinamica, resumen desglosado | svg-pdf-renderer |
| `orchestrator_service/services/nova_tools.py` | Actualizar `ver_odontograma` y `modificar_odontograma` con denticion, estados expandidos, superficies v3.0 | nova-tools-update |
| `orchestrator_service/templates/digital_records/odontogram_art.html` | Seccion temporal condicional, columna Condicion en tabla | svg-pdf-renderer |
| `orchestrator_service/services/digital_records_service.py` | Pasar v3.0 a renderer, contexto con `permanent_svg` + `deciduous_svg` | svg-pdf-renderer |
| `frontend_react/src/locales/es.json` | ~110 claves nuevas bajo `odontogram.*` | i18n-expansion |
| `frontend_react/src/locales/en.json` | ~110 claves nuevas bajo `odontogram.*` | i18n-expansion |
| `frontend_react/src/locales/fr.json` | ~110 claves nuevas bajo `odontogram.*` | i18n-expansion |

### 12.3. Archivos NO afectados

| Archivo | Razon |
|---------|-------|
| `orchestrator_service/models.py` | `odontogram_data` es JSONB libre — no requiere cambio de schema SQL |
| `orchestrator_service/main.py` | No tiene logica de odontograma directa |
| `bff_service/` | Es proxy transparente — no parsea el payload |
| `orchestrator_service/db.py` | Sin cambios en la conexion |

---

## Apendice A: Constantes de cuadrantes — `odontogram/constants.ts`

```typescript
// Permanentes
export const PERM_UPPER_RIGHT = [18, 17, 16, 15, 14, 13, 12, 11];
export const PERM_UPPER_LEFT  = [21, 22, 23, 24, 25, 26, 27, 28];
export const PERM_LOWER_RIGHT = [48, 47, 46, 45, 44, 43, 42, 41];
export const PERM_LOWER_LEFT  = [31, 32, 33, 34, 35, 36, 37, 38];
export const ALL_PERMANENT    = [...PERM_UPPER_RIGHT, ...PERM_UPPER_LEFT,
                                 ...PERM_LOWER_RIGHT, ...PERM_LOWER_LEFT];

// Deciduos
export const DEC_UPPER_RIGHT = [55, 54, 53, 52, 51];
export const DEC_UPPER_LEFT  = [61, 62, 63, 64, 65];
export const DEC_LOWER_RIGHT = [85, 84, 83, 82, 81];
export const DEC_LOWER_LEFT  = [71, 72, 73, 74, 75];
export const ALL_DECIDUOUS   = [...DEC_UPPER_RIGHT, ...DEC_UPPER_LEFT,
                                 ...DEC_LOWER_RIGHT, ...DEC_LOWER_LEFT];

// Quadrant configs
export const PERMANENT_QUADRANTS: QuadrantConfig[] = [
  { ids: PERM_UPPER_RIGHT, position: 'upper-right', numbersBelow: false },
  { ids: PERM_UPPER_LEFT,  position: 'upper-left',  numbersBelow: false },
  { ids: PERM_LOWER_RIGHT, position: 'lower-right', numbersBelow: true  },
  { ids: PERM_LOWER_LEFT,  position: 'lower-left',  numbersBelow: true  },
];

export const DECIDUOUS_QUADRANTS: QuadrantConfig[] = [
  { ids: DEC_UPPER_RIGHT, position: 'upper-right', numbersBelow: false },
  { ids: DEC_UPPER_LEFT,  position: 'upper-left',  numbersBelow: false },
  { ids: DEC_LOWER_RIGHT, position: 'lower-right', numbersBelow: true  },
  { ids: DEC_LOWER_LEFT,  position: 'lower-left',  numbersBelow: true  },
];

// SVG surface paths (ViewBox 0 0 40 40)
export const SURFACE_PATHS = {
  top:    'M20,2 A18,18 0 0,1 38,20 L27,20 A7,7 0 0,0 20,13 Z',
  right:  'M38,20 A18,18 0 0,1 20,38 L20,27 A7,7 0 0,0 27,20 Z',
  bottom: 'M20,38 A18,18 0 0,1 2,20 L13,20 A7,7 0 0,0 20,27 Z',
  left:   'M2,20 A18,18 0 0,1 20,2 L20,13 A7,7 0 0,0 13,20 Z',
};

export const SURFACE_KEYS: SurfaceKey[] = ['buccal', 'distal', 'lingual', 'mesial', 'occlusal'];

export const SVG_TO_DATA_MAP: Record<string, SurfaceKey> = {
  top:    'buccal',
  right:  'distal',
  bottom: 'lingual',
  left:   'mesial',
  center: 'occlusal',
};
```

---

## Apendice B: Colores preset para StateConditionModal

```typescript
export const DENTAL_COLOR_PRESETS = [
  '#22c55e',  // verde (sano)
  '#3b82f6',  // azul (resina)
  '#ef4444',  // rojo (caries activa)
  '#f97316',  // naranja (caries inicial)
  '#f59e0b',  // ambar (corona)
  '#8b5cf6',  // violeta (implante)
  '#06b6d4',  // cyan (sellante)
  '#6b7280',  // gris (amalgama)
  '#1f2937',  // negro oscuro (necrosis)
  '#f1f5f9',  // blanco grisaceo (mancha blanca)
];
```

---

## Apendice C: Animaciones CSS

```css
/* surfacePulse — superficie seleccionada */
@keyframes surfacePulse {
  0%, 100% { stroke-width: 2.5; opacity: 0.9; }
  50%       { stroke-width: 3.0; opacity: 1.0; }
}

/* surfacePop — superficie recien modificada */
@keyframes surfacePop {
  0%   { transform: scale(1); }
  30%  { transform: scale(1.15); }
  60%  { transform: scale(0.97); }
  100% { transform: scale(1); }
}

/* slideInFromRight — transicion de tabs */
@keyframes slideInFromRight {
  from { transform: translateX(100%); opacity: 0; }
  to   { transform: translateX(0);    opacity: 1; }
}

/* slideInFromLeft — transicion de tabs */
@keyframes slideInFromLeft {
  from { transform: translateX(-100%); opacity: 0; }
  to   { transform: translateX(0);     opacity: 1; }
}
```
