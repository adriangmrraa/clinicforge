# Spec: data-model-evolution

**Change:** odontogram-v2-complete
**Spec ID:** data-model-evolution
**Tipo:** Backend (P0 — bloqueante para todo el change)
**Fecha:** 2026-04-02
**Estado:** Draft

---

## 1. Resumen

Este spec define la evolución del modelo de datos del odontograma de ClinicForge desde el formato v2.0 actual hacia el formato v3.0, que introduce dentición dual (permanente + decidua), superficies con estado/condición/color independiente por cara, y un catálogo expandido de ~40 estados clínicos. El cambio es **no destructivo**: la columna JSONB `odontogram_data` en `clinical_records` no se altera estructuralmente; la migración de datos ocurre **en lectura** (on-read), y al guardar siempre se escribe en formato v3.0.

El problema central que resuelve este spec es la existencia de **dos parsers divergentes** (`normalize_odontogram_data` en `odontogram_svg.py` y `_parse_odontogram_data` en `nova_tools.py`) que manejan los mismos datos con lógica no coordinada, más modelos Pydantic (`ToothSurface`, `ToothData`) que aceptan solo 3 estados de superficie, incompatibles con el catálogo de ~40 estados requerido. La consolidación en un parser único y la actualización de los modelos es la fundación técnica de la que depende todo el resto del change.

---

## 2. Requisitos funcionales

### 2.1 Formato v3.0

**REQ-DM-001** — El sistema DEBE soportar un nuevo formato JSONB v3.0 para `odontogram_data` con la siguiente estructura raíz: `version`, `last_updated`, `active_dentition`, `permanent`, `deciduous`.

**REQ-DM-002** — El campo `active_dentition` DEBE ser de tipo `"permanent" | "deciduous"` y representa qué dentición estaba activa cuando el usuario guardó el registro.

**REQ-DM-003** — El campo `permanent` DEBE contener un objeto con clave `teeth`: array de 32 objetos diente con FDI 11–48 en orden estándar.

**REQ-DM-004** — El campo `deciduous` DEBE contener un objeto con clave `teeth`: array de 20 objetos diente con FDI 51–85 en orden estándar (ver §3.4 para numeración exacta).

**REQ-DM-005** — Cada objeto diente DEBE tener los campos: `id` (entero FDI), `state` (string — estado global para retrocompatibilidad), `surfaces` (objeto con 5 claves), `notes` (string, puede ser vacío).

**REQ-DM-006** — Cada superficie en `surfaces` DEBE tener la estructura `SurfaceState`: `state` (string del catálogo), `condition` (`"bueno" | "malo" | "indefinido" | null`), `color` (string HEX `#rrggbb` o `null`).

**REQ-DM-007** — Las 5 claves válidas de `surfaces` son: `occlusal`, `mesial`, `distal`, `buccal`, `lingual`. Cualquier otra clave DEBE ser ignorada al parsear.

### 2.2 Retrocompatibilidad

**REQ-DM-010** — El sistema DEBE parsear datos v1 (legacy dict `{"18": "caries"}`) convirtiéndolos a v3.0 en memoria, sin escritura destructiva.

**REQ-DM-011** — El sistema DEBE parsear datos v1 con formato alternativo (`{"18": {"status": "caries"}}`) con el mismo resultado que REQ-DM-010.

**REQ-DM-012** — El sistema DEBE parsear datos v2.0 (`{"teeth": [...], "version": "2.0"}`) interpretando el array plano de dientes como `permanent.teeth`, con `deciduous.teeth` inicializado vacío (dentición completa de 20 dientes sanos).

**REQ-DM-013** — En datos v2.0, las superficies existentes con formato antiguo (e.g. `{"occlusal": "caries"}` como string plano) DEBEN migrarse a `SurfaceState` con `state` = valor original, `condition = null`, `color = null`.

**REQ-DM-014** — Al guardar, independientemente del formato de entrada, SIEMPRE se DEBE escribir en formato v3.0.

**REQ-DM-015** — Una request de PUT con payload en formato v2.0 DEBE ser aceptada por la API y guardada en v3.0 (backward compat para clientes viejos).

### 2.3 Parser unificado

**REQ-DM-020** — DEBE existir un único módulo compartido `shared/odontogram_utils.py` que exporte la función `parse_odontogram_data(raw) -> OdontogramV3`.

**REQ-DM-021** — Tanto `orchestrator_service/services/odontogram_svg.py` como `orchestrator_service/services/nova_tools.py` DEBEN importar y usar `parse_odontogram_data` desde `shared/odontogram_utils.py`. Las funciones locales `normalize_odontogram_data` y `_parse_odontogram_data` DEBEN ser eliminadas o deprecadas como thin wrappers.

**REQ-DM-022** — El módulo compartido DEBE exportar las funciones auxiliares `build_default_permanent_teeth() -> list[dict]` (32 dientes) y `build_default_deciduous_teeth() -> list[dict]` (20 dientes), ambas retornando dientes con todos sus campos en estado `healthy` y superficies con `SurfaceState` defaults.

**REQ-DM-023** — `parse_odontogram_data` DEBE ser una función pura (sin efectos secundarios, sin I/O) que opere solo sobre datos en memoria.

**REQ-DM-024** — `parse_odontogram_data` DEBE manejar como entrada: `None`, `str` (JSON serializado), `dict` (cualquier versión), y valores inesperados — en todos los casos retornando un `OdontogramV3` válido sin lanzar excepciones.

### 2.4 Modelos Pydantic

**REQ-DM-030** — El modelo `SurfaceState` DEBE ser definido en `shared/models_dental.py` con los campos: `state: str` (string libre, validado contra catálogo en runtime no en tipo), `condition: Optional[Literal["bueno", "malo", "indefinido"]] = None`, `color: Optional[str] = None` (regex HEX o null).

**REQ-DM-031** — El modelo `ToothSurface` DEBE ser actualizado para usar `SurfaceState` en cada una de las 5 superficies, todas con valor por defecto `SurfaceState(state="healthy")`.

**REQ-DM-032** — El modelo `ToothData` DEBE mantener los campos existentes (`number`, `tooth_type`, `status`, `surfaces`, `color_code`, `notes`, `treatment_date`) y agregar: `id: Optional[int]` (alias FDI — para mapeo con formato v3), `dentition: Optional[DentitionType] = "permanent"`.

**REQ-DM-033** — El tipo `DentitionType` DEBE ser definido como `Literal["permanent", "deciduous"]`.

**REQ-DM-034** — El modelo `DentitionData` DEBE ser definido con campo `teeth: List[ToothDataV3]` donde `ToothDataV3` es la representación exacta de un diente en formato v3.0.

**REQ-DM-035** — El modelo `OdontogramV3` DEBE ser definido con campos: `version: Literal["3.0"] = "3.0"`, `last_updated: str`, `active_dentition: DentitionType = "permanent"`, `permanent: DentitionData`, `deciduous: DentitionData`.

**REQ-DM-036** — Los modelos existentes `ToothSurface` y `ToothData` DEBEN mantener compatibilidad de API (no breaking changes públicos) — se pueden extender pero no remover campos existentes.

### 2.5 Endpoints API

**REQ-DM-040** — El endpoint `PUT /admin/patients/{patient_id}/records/{record_id}/odontogram` DEBE aceptar payload en formato v3.0. También DEBE aceptar v2.0 (retrocompatibilidad) y convertirlo internamente antes de guardar.

**REQ-DM-041** — El endpoint `GET /admin/patients/{patient_id}/records/{record_id}` (y equivalentes que retornen `odontogram_data`) DEBE retornar el campo `odontogram_data` siempre en formato v3.0, upgradeando on-read si el dato almacenado es v1 o v2.

**REQ-DM-042** — Los endpoints DEBEN retornar un campo `odontogram_version: "3.0"` en la respuesta para que el cliente pueda detectar el formato recibido sin inspeccionar el JSONB.

**REQ-DM-043** — El endpoint de odontograma DEBE tener validación de `patient_id` y `tenant_id` extraídos del JWT — NUNCA de query params (Sovereignty Protocol).

### 2.6 Migración Alembic 017

**REQ-DM-050** — DEBE existir una migración Alembic `017_odontogram_v3_format.py` con funciones `upgrade()` y `downgrade()` completas.

**REQ-DM-051** — La migración DEBE ser **no destructiva**: no altera el tipo de la columna `odontogram_data` (ya es JSONB) ni elimina datos existentes.

**REQ-DM-052** — La función `upgrade()` DEBE agregar un índice GIN sobre `clinical_records.odontogram_data` si no existe: `CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_clinical_records_odontogram_gin ON clinical_records USING GIN (odontogram_data)`.

**REQ-DM-053** — La función `downgrade()` DEBE eliminar el índice GIN creado en upgrade.

**REQ-DM-054** — La migración DEBE incluir en su docstring la descripción completa del formato v3.0, los rangos FDI de permanente y decidua, y la política de retrocompatibilidad.

---

## 3. Modelo de datos

### 3.1 JSON Schema — formato v3.0 completo

```jsonc
{
  "version": "3.0",                           // String literal — siempre "3.0" al guardar
  "last_updated": "2026-04-02T15:30:00Z",     // ISO-8601 UTC, actualizado en cada save
  "active_dentition": "permanent",             // "permanent" | "deciduous"

  "permanent": {
    "teeth": [
      {
        "id": 18,                              // Número FDI entero (11-48 para permanente)
        "state": "healthy",                    // Estado global — para retrocompat y resumen rápido
        "surfaces": {
          "occlusal": {
            "state": "caries",                 // String del catálogo (~40 valores válidos)
            "condition": "malo",               // "bueno" | "malo" | "indefinido" | null
            "color": "#ef4444"                 // HEX string o null (usa default del estado si null)
          },
          "mesial":  { "state": "healthy", "condition": null, "color": null },
          "distal":  { "state": "restauracion_resina", "condition": "bueno", "color": "#3b82f6" },
          "buccal":  { "state": "healthy", "condition": null, "color": null },
          "lingual": { "state": "healthy", "condition": null, "color": null }
        },
        "notes": "Caries incipiente, observación"
      }
      // ... 32 dientes FDI 18→11, 21→28, 48→41, 31→38
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

### 3.2 Orden de dientes — dentición permanente (32 piezas)

Los dientes se almacenan en el array en el siguiente orden estándar (igual al frontend y al SVG renderer):

| Cuadrante | FDIs en orden |
|-----------|---------------|
| Superior Derecho (Q1) | 18, 17, 16, 15, 14, 13, 12, 11 |
| Superior Izquierdo (Q2) | 21, 22, 23, 24, 25, 26, 27, 28 |
| Inferior Derecho (Q4) | 48, 47, 46, 45, 44, 43, 42, 41 |
| Inferior Izquierdo (Q3) | 31, 32, 33, 34, 35, 36, 37, 38 |

### 3.3 Orden de dientes — dentición decidua/temporal (20 piezas)

| Cuadrante | FDIs en orden |
|-----------|---------------|
| Superior Derecho (Q5) | 55, 54, 53, 52, 51 |
| Superior Izquierdo (Q6) | 61, 62, 63, 64, 65 |
| Inferior Derecho (Q8) | 85, 84, 83, 82, 81 |
| Inferior Izquierdo (Q7) | 71, 72, 73, 74, 75 |

### 3.4 Modelos Pydantic — `shared/models_dental.py`

```python
from typing import Optional, Literal, List
from pydantic import BaseModel, Field, validator
import re

DentitionType = Literal["permanent", "deciduous"]

class SurfaceState(BaseModel):
    """Estado de una superficie individual de un diente (v3.0)."""
    state: str = "healthy"
    condition: Optional[Literal["bueno", "malo", "indefinido"]] = None
    color: Optional[str] = None  # HEX #rrggbb o None

    @validator("color")
    def validate_hex_color(cls, v):
        if v is not None and not re.match(r'^#[0-9a-fA-F]{6}$', v):
            raise ValueError(f"color debe ser HEX #rrggbb, recibido: {v}")
        return v

    @classmethod
    def healthy(cls) -> "SurfaceState":
        return cls(state="healthy", condition=None, color=None)


class ToothSurface(BaseModel):
    """Las 5 superficies de un diente, cada una con SurfaceState (v3.0)."""
    occlusal: SurfaceState = Field(default_factory=SurfaceState.healthy)
    mesial:   SurfaceState = Field(default_factory=SurfaceState.healthy)
    distal:   SurfaceState = Field(default_factory=SurfaceState.healthy)
    buccal:   SurfaceState = Field(default_factory=SurfaceState.healthy)
    lingual:  SurfaceState = Field(default_factory=SurfaceState.healthy)


class ToothDataV3(BaseModel):
    """Representación de un diente en formato v3.0 (usado en OdontogramV3)."""
    id: int = Field(..., description="Número FDI del diente")
    state: str = "healthy"             # estado global para resumen rápido
    surfaces: ToothSurface = Field(default_factory=ToothSurface)
    notes: str = ""


class DentitionData(BaseModel):
    """Una dentición completa (permanente o decidua)."""
    teeth: List[ToothDataV3] = Field(default_factory=list)


class OdontogramV3(BaseModel):
    """Formato canónico v3.0 del odontograma. Se escribe siempre en este formato."""
    version: Literal["3.0"] = "3.0"
    last_updated: str = ""             # ISO-8601 UTC
    active_dentition: DentitionType = "permanent"
    permanent: DentitionData = Field(default_factory=DentitionData)
    deciduous: DentitionData = Field(default_factory=DentitionData)

    def to_db_dict(self) -> dict:
        """Serializa a dict listo para guardarse en JSONB."""
        return self.dict()


# --- Modelos legacy: se mantienen para backward compat con código existente ---

class ToothSurface_v2(BaseModel):
    """[DEPRECATED v3.0] Estado de superficie — 3 estados solamente. Usar SurfaceState."""
    occlusal: Optional[Literal["healthy", "caries", "treated"]] = "healthy"
    mesial:   Optional[Literal["healthy", "caries", "treated"]] = "healthy"
    distal:   Optional[Literal["healthy", "caries", "treated"]] = "healthy"
    buccal:   Optional[Literal["healthy", "caries", "treated"]] = "healthy"
    lingual:  Optional[Literal["healthy", "caries", "treated"]] = "healthy"


class ToothData(BaseModel):
    """Datos de un diente — extendido para v3.0 con campos opcionales nuevos."""
    number: int = Field(..., description="Número FDI del diente")
    id: Optional[int] = None           # alias de number para compatibilidad v3
    tooth_type: Optional[Literal["incisor", "canine", "premolar", "molar"]] = None
    status: str = "healthy"            # ampliado a string libre (no Literal restringido)
    surfaces: Optional[ToothSurface] = None
    color_code: Optional[str] = None
    notes: Optional[str] = None
    treatment_date: Optional[str] = None
    dentition: Optional[DentitionType] = "permanent"
```

### 3.5 Catálogo de estados (referencia para validación)

El catálogo completo se define en `shared/odontogram_states.py` (spec `state-catalog`). A efectos de este spec, el campo `state` en `SurfaceState` y `ToothDataV3.state` acepta **string libre** — la validación contra el catálogo ocurre en la capa de presentación, no en el modelo de datos. Esto permite evolucionar el catálogo sin migrations de schema.

Estados actuales conocidos (no exhaustivo — referencia para tests y parsers):

```python
# Preexistentes (~24)
PREEXISTENTE_STATES = [
    "healthy", "implante", "radiografia", "restauracion_resina",
    "restauracion_amalgama", "restauracion_temporal", "sellador_fisuras",
    "carilla", "puente", "corona_porcelana", "corona_resina",
    "corona_metalceramica", "corona_temporal", "incrustacion", "onlay",
    "poste", "perno", "fibras_ribbond", "tratamiento_conducto",
    "protesis_removible", "diente_erupcion", "diente_no_erupcionado",
    "ausente", "otra_preexistencia",
]

# Lesión (~16)
LESION_STATES = [
    "caries", "mancha_blanca", "surco_profundo", "caries_penetrante",
    "necrosis_pulpar", "proceso_apical", "fistula", "indicacion_extraccion",
    "abrasion", "abfraccion", "atricion", "erosion", "fractura_horizontal",
    "fractura_vertical", "movilidad", "hipomineralizacion_mih", "otra_lesion",
]

# Estados legacy v2 (se mapean en el parser para retrocompatibilidad):
LEGACY_STATE_MAP = {
    "treated":          "restauracion_resina",
    "restoration":      "restauracion_resina",
    "root_canal":       "tratamiento_conducto",
    "crown":            "corona_porcelana",
    "implant":          "implante",
    "prosthesis":       "protesis_removible",
    "extraction":       "indicacion_extraccion",
    "missing":          "ausente",
    "treatment_planned": "otra_preexistencia",
    # "healthy" y "caries" no necesitan mapeo — son iguales en v3
}
```

### 3.6 Parser unificado — `shared/odontogram_utils.py`

```python
"""
shared/odontogram_utils.py
Parser canónico para odontogram_data. ÚNICA fuente de verdad.
Importado por: odontogram_svg.py, nova_tools.py, admin_routes.py.
"""
import json
from datetime import datetime, timezone
from typing import Union
from shared.models_dental import OdontogramV3, DentitionData, ToothDataV3, ToothSurface, SurfaceState

# FDI order constants (mirrors frontend and odontogram_svg.py)
PERMANENT_FDI_ORDER = [
    18, 17, 16, 15, 14, 13, 12, 11,   # Q1 upper right
    21, 22, 23, 24, 25, 26, 27, 28,   # Q2 upper left
    48, 47, 46, 45, 44, 43, 42, 41,   # Q4 lower right
    31, 32, 33, 34, 35, 36, 37, 38,   # Q3 lower left
]

DECIDUOUS_FDI_ORDER = [
    55, 54, 53, 52, 51,   # Q5 upper right
    61, 62, 63, 64, 65,   # Q6 upper left
    85, 84, 83, 82, 81,   # Q8 lower right
    71, 72, 73, 74, 75,   # Q7 lower left
]


def build_default_permanent_teeth() -> list[dict]:
    """32 dientes permanentes, todos sanos, superficies inicializadas."""
    return [_make_tooth(fdi) for fdi in PERMANENT_FDI_ORDER]


def build_default_deciduous_teeth() -> list[dict]:
    """20 dientes deciduos, todos sanos, superficies inicializadas."""
    return [_make_tooth(fdi) for fdi in DECIDUOUS_FDI_ORDER]


def _make_tooth(fdi: int) -> dict:
    return {
        "id": fdi,
        "state": "healthy",
        "surfaces": {
            "occlusal": {"state": "healthy", "condition": None, "color": None},
            "mesial":   {"state": "healthy", "condition": None, "color": None},
            "distal":   {"state": "healthy", "condition": None, "color": None},
            "buccal":   {"state": "healthy", "condition": None, "color": None},
            "lingual":  {"state": "healthy", "condition": None, "color": None},
        },
        "notes": "",
    }


def parse_odontogram_data(raw: Union[str, dict, None]) -> OdontogramV3:
    """
    Parser canónico. Acepta cualquier formato histórico de odontogram_data y
    retorna siempre un OdontogramV3 válido. Nunca lanza excepciones.

    Cadena de detección:
      None              → OdontogramV3 vacío (permanente + decidua sanos)
      str               → json.loads → reintenta como dict
      dict v3.0         → uso directo (version == "3.0")
      dict v2.0         → teeth array plano → permanent.teeth, decidua por defecto
      dict legacy       → {"18": "caries"} o {"18": {"status": "..."}} → migración
      cualquier otro    → OdontogramV3 vacío (falla silenciosa)
    """
    ...


def odontogram_v3_to_dict(odata: OdontogramV3) -> dict:
    """Serializa OdontogramV3 a dict plano para guardar en JSONB."""
    d = odata.dict()
    d["last_updated"] = datetime.now(timezone.utc).isoformat()
    return d
```

---

## 4. Escenarios

### Escenario 1 — Parsear dato v1 (legacy dict de strings)

```
DADO: odontogram_data = '{"18": "caries", "21": "healthy"}'
CUANDO: parse_odontogram_data(raw) es llamado
ENTONCES:
  - result.version == "3.0"
  - result.active_dentition == "permanent"
  - pieza 18 en permanent.teeth tiene state == "caries"
  - pieza 21 en permanent.teeth tiene state == "healthy"
  - las 30 piezas restantes tienen state == "healthy" con todas las superficies sanas
  - deciduous.teeth tiene 20 dientes todos sanos
  - NO se lanza ninguna excepción
```

### Escenario 2 — Parsear dato v1 (legacy dict de objetos)

```
DADO: odontogram_data = {"37": {"status": "root_canal"}, "11": {"state": "crown", "notes": "Corona porcelana"}}
CUANDO: parse_odontogram_data(raw) es llamado
ENTONCES:
  - pieza 37 tiene state == "tratamiento_conducto"  (mapping legacy → v3)
  - pieza 11 tiene state == "corona_porcelana"       (mapping legacy → v3)
  - pieza 11 tiene notes == "Corona porcelana"
  - superficies de 37 y 11: todas "healthy", condition null, color null
  - deciduous.teeth tiene 20 dientes sanos
```

### Escenario 3 — Parsear dato v2.0 con teeth array plano

```
DADO: odontogram_data = {
  "teeth": [
    {"id": 16, "state": "extraction", "surfaces": {}, "notes": ""},
    {"id": 36, "state": "caries", "surfaces": {"occlusal": "caries"}, "notes": ""},
  ],
  "version": "2.0",
  "last_updated": "2025-10-01T10:00:00Z"
}
CUANDO: parse_odontogram_data(raw) es llamado
ENTONCES:
  - result.permanent.teeth contiene TODAS las 32 piezas (las 30 restantes con state healthy)
  - pieza 16 tiene state == "indicacion_extraccion"  (mapping "extraction" → v3)
  - pieza 36 tiene state == "caries"
  - pieza 36.surfaces.occlusal == SurfaceState(state="caries", condition=None, color=None)
    (migración de superficie string plano → SurfaceState)
  - result.deciduous.teeth tiene 20 dientes sanos
  - result.active_dentition == "permanent"
```

### Escenario 4 — Parsear dato v3.0 completo

```
DADO: odontogram_data = {
  "version": "3.0",
  "last_updated": "2026-04-01T09:00:00Z",
  "active_dentition": "deciduous",
  "permanent": {"teeth": [{"id": 18, "state": "healthy", "surfaces": {...}, "notes": ""}]},
  "deciduous": {"teeth": [{"id": 55, "state": "caries", "surfaces": {...}, "notes": "Lesión"}]}
}
CUANDO: parse_odontogram_data(raw) es llamado
ENTONCES:
  - result.version == "3.0"
  - result.active_dentition == "deciduous"
  - pieza 55 en deciduous.teeth tiene state == "caries" y notes == "Lesión"
  - permanent.teeth se retorna tal cual (no se sobreescribe)
```

### Escenario 5 — Guardar odontograma v3.0

```
DADO: Un request PUT /admin/patients/5/records/99/odontogram con payload v3.0 válido
CUANDO: El endpoint recibe y procesa el request
ENTONCES:
  - Se llama parse_odontogram_data con el payload recibido
  - Se actualiza last_updated con timestamp UTC actual
  - Se persiste en DB como JSON v3.0 completo
  - La respuesta incluye odontogram_version: "3.0"
  - Se emite evento WebSocket ODONTOGRAM_UPDATED con el nuevo estado
```

### Escenario 6 — Guardar odontograma en formato v2.0 (backward compat)

```
DADO: Un request PUT con payload {"teeth": [...], "version": "2.0"} (cliente viejo)
CUANDO: El endpoint recibe y procesa el request
ENTONCES:
  - El parser convierte automáticamente a v3.0
  - Se guarda en DB como v3.0 (NO como v2.0)
  - El cliente recibe HTTP 200 con odontogram_version: "3.0"
  - No se retorna error 422 (backward compat garantizada)
```

### Escenario 7 — Leer odontograma con dato legacy en DB

```
DADO: DB tiene odontogram_data = '{"18": "caries"}' (dato v1 sin migrar)
CUANDO: GET /admin/patients/5/records/99 es llamado
ENTONCES:
  - El endpoint retorna el campo odontogram_data en formato v3.0 completo
  - pieza 18 tiene state == "caries"
  - deciduous.teeth tiene 20 dientes sanos
  - La DB NO es modificada por esta lectura (on-read migration es en memoria solamente)
```

### Escenario 8 — Dato corrupto o nulo en DB

```
DADO: odontogram_data = null  O  odontogram_data = "invalid json{"
CUANDO: parse_odontogram_data(raw) es llamado
ENTONCES:
  - Se retorna OdontogramV3 con permanent y deciduous con dientes todos sanos
  - NO se lanza excepción
  - El error se registra en logs con nivel WARNING con el valor que causó el fallo
```

### Escenario 9 — Migración Alembic 017 en DB limpia (upgrade)

```
DADO: DB sin índice GIN en clinical_records.odontogram_data
CUANDO: alembic upgrade head es ejecutado
ENTONCES:
  - Se crea el índice idx_clinical_records_odontogram_gin
  - No se modifican filas existentes en clinical_records
  - El schema de la columna odontogram_data no cambia (sigue siendo JSONB)
  - alembic version = 017
```

### Escenario 10 — Migración Alembic 017 en DB con índice ya existente

```
DADO: DB ya tiene el índice GIN (por cualquier motivo previo)
CUANDO: alembic upgrade head es ejecutado
ENTONCES:
  - El IF NOT EXISTS previene error
  - La migración completa sin error
```

### Escenario 11 — Superficie con color HEX inválido

```
DADO: Payload con surfaces.occlusal.color = "rojo" (no HEX)
CUANDO: El endpoint valida con SurfaceState
ENTONCES:
  - Pydantic lanza ValidationError
  - El endpoint retorna HTTP 422 con mensaje descriptivo
  - No se escribe en DB
```

### Escenario 12 — Pieza FDI fuera de rango permanente

```
DADO: Payload con permanent.teeth incluyendo pieza con id = 99 (no es FDI válido)
CUANDO: parse_odontogram_data procesa el dato
ENTONCES:
  - La pieza 99 es ignorada (no se incluye en el OdontogramV3 resultante)
  - Las 32 piezas estándar se inicializan con sus defaults
  - Se registra WARNING en logs con "FDI desconocido: 99"
```

---

## 5. Criterios de aceptación

### Formato y modelos

- [ ] **AC-DM-01** — `OdontogramV3`, `DentitionData`, `ToothDataV3`, `SurfaceState`, `ToothSurface` (actualizado), `DentitionType` definidos en `shared/models_dental.py`
- [ ] **AC-DM-02** — `SurfaceState.color` valida HEX via `@validator` — acepta `#3b82f6`, rechaza `"azul"` y `"3b82f6"` (sin #)
- [ ] **AC-DM-03** — `OdontogramV3.to_db_dict()` serializa correctamente a dict plano (no Pydantic objects anidados)
- [ ] **AC-DM-04** — `LEGACY_STATE_MAP` aplicado en parser: `"extraction"` → `"indicacion_extraccion"`, `"root_canal"` → `"tratamiento_conducto"`, `"crown"` → `"corona_porcelana"`, `"treated"` → `"restauracion_resina"`

### Parser unificado

- [ ] **AC-DM-05** — `shared/odontogram_utils.py` existe y exporta `parse_odontogram_data`, `build_default_permanent_teeth`, `build_default_deciduous_teeth`
- [ ] **AC-DM-06** — `odontogram_svg.py` importa `parse_odontogram_data` desde `shared.odontogram_utils` — `normalize_odontogram_data` usa el parser compartido internamente
- [ ] **AC-DM-07** — `nova_tools.py` importa `parse_odontogram_data` desde `shared.odontogram_utils` — `_parse_odontogram_data` usa el parser compartido internamente
- [ ] **AC-DM-08** — `parse_odontogram_data(None)` retorna `OdontogramV3` con 32 permanentes + 20 deciduos sanos, sin excepción
- [ ] **AC-DM-09** — `parse_odontogram_data("json corrupto")` retorna `OdontogramV3` vacío, sin excepción
- [ ] **AC-DM-10** — `build_default_permanent_teeth()` retorna exactamente 32 items con FDI en orden `[18, 17, ..., 11, 21, ..., 28, 48, ..., 41, 31, ..., 38]`
- [ ] **AC-DM-11** — `build_default_deciduous_teeth()` retorna exactamente 20 items con FDI en orden `[55, 54, 53, 52, 51, 61, 62, 63, 64, 65, 85, 84, 83, 82, 81, 71, 72, 73, 74, 75]`

### Retrocompatibilidad

- [ ] **AC-DM-12** — Parse de v1 `{"18": "caries"}` → `permanent.teeth[pieza 18].state == "caries"`, decidua con 20 sanos
- [ ] **AC-DM-13** — Parse de v1 `{"37": {"status": "root_canal"}}` → `permanent.teeth[pieza 37].state == "tratamiento_conducto"`
- [ ] **AC-DM-14** — Parse de v2.0 `{"teeth": [...], "version": "2.0"}` → `permanent.teeth` completo (32 piezas), `deciduous.teeth` con 20 sanos
- [ ] **AC-DM-15** — Superficie v2 string plano `{"occlusal": "caries"}` → migra a `SurfaceState(state="caries", condition=None, color=None)`
- [ ] **AC-DM-16** — PUT con payload v2.0 retorna HTTP 200 y guarda en DB como v3.0

### API endpoints

- [ ] **AC-DM-17** — GET de registro con odontograma v1 en DB retorna `odontogram_data` en formato v3.0 (upgrade on-read)
- [ ] **AC-DM-18** — PUT con payload v3.0 válido persiste correctamente y retorna `odontogram_version: "3.0"`
- [ ] **AC-DM-19** — PUT con `surfaces.buccal.color = "rojo"` retorna HTTP 422 con mensaje de validación
- [ ] **AC-DM-20** — `tenant_id` extraído del JWT en endpoints de odontograma, nunca de query params

### Migración Alembic

- [ ] **AC-DM-21** — `alembic upgrade head` desde 016 hasta 017 completa sin error
- [ ] **AC-DM-22** — `alembic downgrade -1` desde 017 hasta 016 completa sin error
- [ ] **AC-DM-23** — Índice `idx_clinical_records_odontogram_gin` existe en DB tras upgrade
- [ ] **AC-DM-24** — `IF NOT EXISTS` en CREATE INDEX previene error en upgrade si el índice ya existe
- [ ] **AC-DM-25** — Datos existentes en `clinical_records` no son alterados por la migración

### Tests

- [ ] **AC-DM-26** — Tests en `tests/test_odontogram_parser.py` cubren los 12 escenarios de este spec
- [ ] **AC-DM-27** — Tests de escenarios 1, 2, 3, 4, 8, 11, 12 son tests unitarios puros (sin DB)
- [ ] **AC-DM-28** — Tests de escenarios 5, 6, 7 usan `AsyncMock` / fixture de DB de test
- [ ] **AC-DM-29** — Coverage de `shared/odontogram_utils.py` >= 90% verificado con `pytest --cov`

---

## 6. Archivos afectados

| Archivo | Tipo de cambio | Descripción |
|---------|----------------|-------------|
| `shared/models_dental.py` | Modificación | Agregar `SurfaceState`, `ToothDataV3`, `DentitionData`, `OdontogramV3`, `DentitionType`. Actualizar `ToothSurface` para usar `SurfaceState`. Extender `ToothData` con `id` y `dentition`. Mantener backward compat. |
| `shared/odontogram_utils.py` | Creación nueva | Módulo nuevo. Parser unificado `parse_odontogram_data()`, helpers `build_default_permanent_teeth()` y `build_default_deciduous_teeth()`, `odontogram_v3_to_dict()`, constantes `PERMANENT_FDI_ORDER`, `DECIDUOUS_FDI_ORDER`, `LEGACY_STATE_MAP`. |
| `orchestrator_service/services/odontogram_svg.py` | Modificación | `normalize_odontogram_data()` refactorizada para usar `parse_odontogram_data` del módulo compartido. Import agregado. La función mantiene la misma firma pública (`normalize_odontogram_data(raw) -> dict`) para no romper callers. |
| `orchestrator_service/services/nova_tools.py` | Modificación | `_parse_odontogram_data()` refactorizada para usar `parse_odontogram_data` del módulo compartido. `_build_default_teeth()` puede permanecer como wrapper de `build_default_permanent_teeth()`. Import agregado. |
| `orchestrator_service/admin_routes.py` | Modificación | Endpoint `PUT /admin/patients/{patient_id}/records/{record_id}/odontogram` acepta v3.0 y v2.0. Endpoint GET hace upgrade on-read via `parse_odontogram_data`. Agrega campo `odontogram_version` en respuesta. |
| `orchestrator_service/alembic/versions/017_odontogram_v3_format.py` | Creación nueva | Migración no destructiva. `upgrade()`: crea índice GIN IF NOT EXISTS. `downgrade()`: elimina el índice. Docstring con descripción del formato v3.0. |
| `tests/test_odontogram_parser.py` | Creación nueva | Tests unitarios para `parse_odontogram_data` y helpers. Cubre los 12 escenarios definidos en §4. |

### Archivos NO afectados en este spec

Los siguientes archivos son afectados por otros specs del change y NO deben modificarse aquí:

- `frontend_react/src/components/Odontogram.tsx` — spec `surface-selection` y `dentition-tabs`
- `orchestrator_service/services/nova_tools.py` (tools H2 schema/lógica) — spec `nova-tools-update`
- `orchestrator_service/services/odontogram_svg.py` (renderizado multi-color, dentición temporal) — spec `svg-pdf-renderer`
- `frontend_react/src/locales/*.json` — spec `i18n-expansion`

---

## 7. Dependencias

### Este spec BLOQUEA (dependencias downstream)

| Spec | Razón |
|------|-------|
| `dentition-tabs` | Necesita `OdontogramV3` con `permanent`/`deciduous` para persistir tabs |
| `surface-selection` | Necesita `SurfaceState` con `state/condition/color` por superficie |
| `state-catalog` | El catálogo define los valores válidos de `SurfaceState.state` |
| `nova-tools-update` | Nova tools necesitan `parse_odontogram_data` y `OdontogramV3` para leer/escribir |
| `svg-pdf-renderer` | El renderer necesita `parse_odontogram_data` y acceso a los colores por superficie |
| `i18n-expansion` | Las claves i18n de superficies/condiciones dependen de los nombres definidos aquí |

### Este spec REQUIERE (dependencias upstream)

Ninguna — este spec es la base del change. No tiene precondiciones técnicas excepto que la migración 016 exista en Alembic (ya existe en el codebase actual).

### Relación con otros changes

| Change | Relación |
|--------|----------|
| `document-versioning` | Independiente. Si se implementa, el historial de versiones de odontograma usará `OdontogramV3` como snapshot. Este spec no lo bloquea ni lo requiere. |
| `odontogram-svg-pdf-vector` | Ya implementado. Este spec reutiliza `odontogram_svg.py` existente y lo extiende internamente (sin breaking changes). |
| `pytest-cov-coverage-tool` | Deseable tener coverage configurado antes de escribir `test_odontogram_parser.py`, pero no bloqueante. |

---

## Notas de implementación

### Sobre la firma pública de `normalize_odontogram_data`

La función `normalize_odontogram_data` en `odontogram_svg.py` actualmente retorna `{"teeth": list, "affected_count": int, "format_version": "2.0"}`. En este spec, internamente usará `parse_odontogram_data`, pero su **firma pública no cambia** — para no romper el caller en `render_odontogram_svg`. El spec `svg-pdf-renderer` se encargará de actualizar esa firma para manejar v3.0 completo.

### Sobre `_parse_odontogram_data` en `nova_tools.py`

Actualmente retorna `list` (solo el array de dientes). Al refactorizar, puede mantenerse como un wrapper que llama a `parse_odontogram_data` y extrae `permanent.teeth` para mantener compatibilidad con `_get_latest_odontogram`. El spec `nova-tools-update` es el responsable de actualizar los callers para manejar la estructura v3 completa.

### Estrategia para `active_dentition` en v2 → v3

Al migrar un dato v2.0 (que no tiene dentición explícita), `active_dentition` se setea en `"permanent"` por defecto. No existe heurística para inferir si la intención original era decidua.

### Índice GIN y `CONCURRENTLY`

La migración usa `CREATE INDEX CONCURRENTLY` para evitar locks de escritura en producción. Alembic no soporta CONCURRENTLY dentro de una transacción explícita — la migración DEBE usar `op.execute()` directamente y NO usar `with op.get_context().autocommit_block():` para este statement específico. Verificar comportamiento en la versión de Alembic del proyecto antes de implementar.
