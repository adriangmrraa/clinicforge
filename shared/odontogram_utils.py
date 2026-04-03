"""
shared/odontogram_utils.py — Parser unificado de odontograma v3.0

Módulo compartido que normaliza cualquier versión de datos de odontograma
(v1 legacy dict, v2.0 teeth array, v3.0 dual dentition) al formato v3.0.

Consumidores:
- orchestrator_service/admin_routes.py (GET/PUT endpoints)
- orchestrator_service/services/odontogram_svg.py (PDF renderer)
- orchestrator_service/services/nova_tools.py (AI voice tools)

Principio: función pura, sin I/O, sin efectos secundarios.
NUNCA lanza excepciones — siempre retorna un v3.0 válido.
"""

import json
import re
from datetime import datetime
from typing import Any, List, Literal, Optional

from pydantic import BaseModel, validator


# ---------------------------------------------------------------------------
# Tipos base
# ---------------------------------------------------------------------------

DentitionType = Literal["permanent", "deciduous"]
DentalCondition = Literal["bueno", "malo", "indefinido"]


# ---------------------------------------------------------------------------
# Modelos Pydantic v3.0
# ---------------------------------------------------------------------------

class SurfaceState(BaseModel):
    """Estado de una superficie individual."""

    state: str = "healthy"
    condition: Optional[DentalCondition] = None
    color: Optional[str] = None

    @validator("color")
    def validate_hex_color(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and not re.match(r"^#[0-9a-fA-F]{6}$", v):
            raise ValueError(f"color debe ser HEX #rrggbb, recibido: {v}")
        return v

    @classmethod
    def healthy(cls) -> "SurfaceState":
        """Retorna una superficie en estado sano (factory helper)."""
        return cls(state="healthy", condition=None, color=None)


class ToothSurfacesV3(BaseModel):
    """Las 5 superficies de un diente en formato v3.0."""

    occlusal: SurfaceState = SurfaceState.healthy()
    mesial: SurfaceState = SurfaceState.healthy()
    distal: SurfaceState = SurfaceState.healthy()
    buccal: SurfaceState = SurfaceState.healthy()
    lingual: SurfaceState = SurfaceState.healthy()


class ToothDataV3(BaseModel):
    """Representación de un diente en formato v3.0."""

    id: int
    state: str = "healthy"
    surfaces: ToothSurfacesV3 = ToothSurfacesV3()
    notes: str = ""


class DentitionData(BaseModel):
    """Una dentición completa (permanente o decidua)."""

    teeth: List[ToothDataV3]


class OdontogramV3(BaseModel):
    """Formato canónico v3.0 del odontograma de ClinicForge."""

    version: Literal["3.0"] = "3.0"
    last_updated: str = ""
    active_dentition: DentitionType = "permanent"
    permanent: DentitionData
    deciduous: DentitionData


# ---------------------------------------------------------------------------
# Constantes FDI
# ---------------------------------------------------------------------------

# Dientes permanentes (32) en orden de visualización por cuadrante
PERMANENT_UPPER_RIGHT: List[int] = [18, 17, 16, 15, 14, 13, 12, 11]
PERMANENT_UPPER_LEFT: List[int]  = [21, 22, 23, 24, 25, 26, 27, 28]
PERMANENT_LOWER_RIGHT: List[int] = [48, 47, 46, 45, 44, 43, 42, 41]
PERMANENT_LOWER_LEFT: List[int]  = [31, 32, 33, 34, 35, 36, 37, 38]

ALL_PERMANENT_FDI: List[int] = (
    PERMANENT_UPPER_RIGHT
    + PERMANENT_UPPER_LEFT
    + PERMANENT_LOWER_RIGHT
    + PERMANENT_LOWER_LEFT
)

# Dientes deciduos (20) en orden de visualización por cuadrante
DECIDUOUS_UPPER_RIGHT: List[int] = [55, 54, 53, 52, 51]
DECIDUOUS_UPPER_LEFT: List[int]  = [61, 62, 63, 64, 65]
DECIDUOUS_LOWER_RIGHT: List[int] = [85, 84, 83, 82, 81]
DECIDUOUS_LOWER_LEFT: List[int]  = [71, 72, 73, 74, 75]

ALL_DECIDUOUS_FDI: List[int] = (
    DECIDUOUS_UPPER_RIGHT
    + DECIDUOUS_UPPER_LEFT
    + DECIDUOUS_LOWER_RIGHT
    + DECIDUOUS_LOWER_LEFT
)

VALID_PERMANENT_FDI: frozenset = frozenset(ALL_PERMANENT_FDI)
VALID_DECIDUOUS_FDI: frozenset = frozenset(ALL_DECIDUOUS_FDI)
VALID_ALL_FDI: frozenset = VALID_PERMANENT_FDI | VALID_DECIDUOUS_FDI

# Claves válidas de superficies (orden canónico)
SURFACE_KEYS: List[str] = ["occlusal", "mesial", "distal", "buccal", "lingual"]


# ---------------------------------------------------------------------------
# Mapa de estados legacy → v3
# ---------------------------------------------------------------------------

LEGACY_STATE_MAP: dict = {
    # v2 states (nombres usados en React/DB actual)
    "healthy":           "healthy",
    "caries":            "caries",
    "restoration":       "restauracion_resina",
    "root_canal":        "tratamiento_conducto",
    "crown":             "corona_porcelana",
    "implant":           "implante",
    "prosthesis":        "protesis_removible",
    "extraction":        "indicacion_extraccion",
    "missing":           "ausente",
    "treatment_planned": "treatment_planned",
    # Aliases alternativos encontrados en datos históricos
    "treated":           "restauracion_resina",
    "crowned":           "corona_porcelana",
    "extracted":         "indicacion_extraccion",
}


# ---------------------------------------------------------------------------
# Funciones auxiliares (prefijo _ = uso interno)
# ---------------------------------------------------------------------------

def _resolve_legacy_state(state: str) -> str:
    """Mapea un ID de estado v1/v2 al ID canónico del catálogo v3."""
    return LEGACY_STATE_MAP.get(state, state)


def _build_healthy_tooth(fdi: int) -> dict:
    """Construye un diente sano con todas sus superficies inicializadas."""
    return {
        "id": fdi,
        "state": "healthy",
        "surfaces": {
            sk: {"state": "healthy", "condition": None, "color": None}
            for sk in SURFACE_KEYS
        },
        "notes": "",
    }


def _build_default_v3() -> dict:
    """
    Construye un odontograma v3.0 vacío con todos los dientes sanos.

    Retorna un dict plano (no Pydantic) para facilitar la serialización JSON
    y la mutación posterior antes de retornar al caller.
    """
    return {
        "version": "3.0",
        "last_updated": datetime.utcnow().isoformat(),
        "active_dentition": "permanent",
        "permanent": {"teeth": build_default_permanent_teeth()},
        "deciduous": {"teeth": build_default_deciduous_teeth()},
    }


def _migrate_surface_to_v3(surface_val: Any) -> dict:
    """
    Convierte un valor de superficie de cualquier formato a SurfaceState dict.

    Acepta:
    - dict con clave "state" (ya es v3 o v2 con estructura parcial)
    - str (estado plano legacy, e.g. "caries")
    - cualquier otro valor → retorna superficie sana
    """
    if isinstance(surface_val, dict) and "state" in surface_val:
        return {
            "state": _resolve_legacy_state(surface_val.get("state", "healthy")),
            "condition": surface_val.get("condition"),
            "color": surface_val.get("color"),
        }
    if isinstance(surface_val, str):
        return {
            "state": _resolve_legacy_state(surface_val),
            "condition": None,
            "color": None,
        }
    return {"state": "healthy", "condition": None, "color": None}


def _migrate_v1_to_v3(data: dict) -> dict:
    """
    Migra formato v1 legacy al formato v3.0.

    v1 acepta dos variantes:
    - Simple:  {"18": "caries"}
    - Extendido: {"18": {"status": "caries", "surfaces": {...}}}

    Solo procesa dientes permanentes (los IDs decimales de decidua son
    ambiguos en v1, ya que el formato no tenía noción de dentición dual).
    """
    v3 = _build_default_v3()
    teeth_map = {t["id"]: t for t in v3["permanent"]["teeth"]}

    for key, value in data.items():
        try:
            fdi = int(key)
        except (ValueError, TypeError):
            continue

        if fdi not in VALID_PERMANENT_FDI:
            continue

        if isinstance(value, str):
            # Variante simple: {"18": "caries"}
            state = _resolve_legacy_state(value)
            teeth_map[fdi]["state"] = state
            for sk in SURFACE_KEYS:
                teeth_map[fdi]["surfaces"][sk] = {
                    "state": state,
                    "condition": None,
                    "color": None,
                }

        elif isinstance(value, dict):
            # Variante extendida: {"18": {"status": "caries", "surfaces": {...}}}
            raw_state = value.get("status", value.get("state", "healthy"))
            state = _resolve_legacy_state(raw_state)
            teeth_map[fdi]["state"] = state

            surfaces = value.get("surfaces", {})
            for sk in SURFACE_KEYS:
                if isinstance(surfaces, dict) and sk in surfaces:
                    teeth_map[fdi]["surfaces"][sk] = _migrate_surface_to_v3(surfaces[sk])
                else:
                    teeth_map[fdi]["surfaces"][sk] = {
                        "state": state,
                        "condition": None,
                        "color": None,
                    }

            if value.get("notes"):
                teeth_map[fdi]["notes"] = value["notes"]

    return v3


def _migrate_v2_to_v3(data: dict) -> dict:
    """
    Migra formato v2.0 al formato v3.0.

    v2.0: {"version": "2.0", "teeth": [{id, state, surfaces, notes}]}

    El array `teeth` de v2 se interpreta como `permanent.teeth`.
    `deciduous.teeth` queda inicializado con los 20 dientes sanos.
    """
    v3 = _build_default_v3()
    teeth_map = {t["id"]: t for t in v3["permanent"]["teeth"]}

    v2_teeth = data.get("teeth", [])
    if not isinstance(v2_teeth, list):
        return v3

    for v2_tooth in v2_teeth:
        if not isinstance(v2_tooth, dict):
            continue

        fdi = v2_tooth.get("id")
        if fdi is None or fdi not in VALID_PERMANENT_FDI:
            continue

        state = _resolve_legacy_state(v2_tooth.get("state", "healthy"))
        teeth_map[fdi]["state"] = state
        teeth_map[fdi]["notes"] = v2_tooth.get("notes", "")

        v2_surfaces = v2_tooth.get("surfaces", {})
        if isinstance(v2_surfaces, dict):
            for sk in SURFACE_KEYS:
                if sk in v2_surfaces:
                    teeth_map[fdi]["surfaces"][sk] = _migrate_surface_to_v3(
                        v2_surfaces[sk]
                    )
                else:
                    # Superficie no especificada → hereda el estado global del diente
                    teeth_map[fdi]["surfaces"][sk] = {
                        "state": state,
                        "condition": None,
                        "color": None,
                    }
        else:
            # Sin dato de superficies → todas heredan el estado global
            for sk in SURFACE_KEYS:
                teeth_map[fdi]["surfaces"][sk] = {
                    "state": state,
                    "condition": None,
                    "color": None,
                }

    if data.get("last_updated"):
        v3["last_updated"] = data["last_updated"]

    return v3


def _normalize_v3_inplace(raw: dict) -> dict:
    """
    Valida y completa un dict que ya declara version="3.0".

    Construye primero el default completo y luego sobreescribe con los valores
    presentes en el input, para garantizar que siempre se retorne un v3
    estructuralmente completo aunque el input tenga campos faltantes.
    """
    result = _build_default_v3()
    result["active_dentition"] = raw.get("active_dentition", "permanent")
    result["last_updated"] = raw.get("last_updated", result["last_updated"])

    # Procesar dentición permanente
    if "permanent" in raw and isinstance(raw["permanent"], dict):
        raw_perm_teeth = raw["permanent"].get("teeth", [])
        if isinstance(raw_perm_teeth, list):
            perm_map = {t["id"]: t for t in result["permanent"]["teeth"]}
            for tooth in raw_perm_teeth:
                if not isinstance(tooth, dict):
                    continue
                fdi = tooth.get("id")
                if fdi not in perm_map:
                    continue
                perm_map[fdi]["state"] = tooth.get("state", "healthy")
                perm_map[fdi]["notes"] = tooth.get("notes", "")
                if isinstance(tooth.get("surfaces"), dict):
                    for sk in SURFACE_KEYS:
                        if sk in tooth["surfaces"]:
                            perm_map[fdi]["surfaces"][sk] = _migrate_surface_to_v3(
                                tooth["surfaces"][sk]
                            )

    # Procesar dentición decidua
    if "deciduous" in raw and isinstance(raw["deciduous"], dict):
        raw_dec_teeth = raw["deciduous"].get("teeth", [])
        if isinstance(raw_dec_teeth, list):
            dec_map = {t["id"]: t for t in result["deciduous"]["teeth"]}
            for tooth in raw_dec_teeth:
                if not isinstance(tooth, dict):
                    continue
                fdi = tooth.get("id")
                if fdi not in dec_map:
                    continue
                dec_map[fdi]["state"] = tooth.get("state", "healthy")
                dec_map[fdi]["notes"] = tooth.get("notes", "")
                if isinstance(tooth.get("surfaces"), dict):
                    for sk in SURFACE_KEYS:
                        if sk in tooth["surfaces"]:
                            dec_map[fdi]["surfaces"][sk] = _migrate_surface_to_v3(
                                tooth["surfaces"][sk]
                            )

    return result


# ---------------------------------------------------------------------------
# API pública del módulo
# ---------------------------------------------------------------------------

def build_default_permanent_teeth() -> list:
    """
    Retorna la lista de 32 dientes permanentes en estado sano.

    FDI order: 18-11 (cuad 1), 21-28 (cuad 2), 48-41 (cuad 3), 31-38 (cuad 4).
    """
    return [_build_healthy_tooth(fdi) for fdi in ALL_PERMANENT_FDI]


def build_default_deciduous_teeth() -> list:
    """
    Retorna la lista de 20 dientes deciduos en estado sano.

    FDI order: 55-51 (cuad 5), 61-65 (cuad 6), 85-81 (cuad 8), 71-75 (cuad 7).
    """
    return [_build_healthy_tooth(fdi) for fdi in ALL_DECIDUOUS_FDI]


def normalize_to_v3(raw: Any) -> dict:
    """
    Punto de entrada principal. Normaliza CUALQUIER formato de odontograma a v3.0.

    Acepta:
    - None           → odontograma vacío con 52 dientes sanos
    - str            → JSON deserializado y luego procesado
    - dict v1 legacy → {"18": "caries"} o {"18": {"status": "caries"}}
    - dict v2.0      → {"version": "2.0", "teeth": [...]}
    - dict v3.0      → validado y completado con defaults si hay campos faltantes
    - cualquier otro → odontograma vacío (no lanza excepción)

    Retorna:
        dict (no Pydantic) listo para serialización JSON. Siempre válido.

    Nota: Esta función es una alias para `parse_odontogram_data` — se mantienen
    ambos nombres para compatibilidad con consumidores existentes.
    """
    # Caso trivial: sin datos
    if raw is None:
        return _build_default_v3()

    # Deserializar JSON string
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return _build_default_v3()

    # Solo procesamos dicts a partir de acá
    if not isinstance(raw, dict):
        return _build_default_v3()

    # Detectar versión y delegar al migrador correspondiente

    if raw.get("version") == "3.0" and "permanent" in raw and "deciduous" in raw:
        # Ya es v3.0 — validar y completar campos faltantes
        return _normalize_v3_inplace(raw)

    if "teeth" in raw and isinstance(raw.get("teeth"), list):
        # Array plano de dientes → formato v2.0
        return _migrate_v2_to_v3(raw)

    if any(isinstance(key, str) and key.isdigit() for key in raw.keys()):
        # Claves numéricas como strings → formato v1 legacy
        return _migrate_v1_to_v3(raw)

    # Formato desconocido — retornar default silenciosamente
    return _build_default_v3()


# Alias para compatibilidad con REQ-DM-020 (nombre en spec)
parse_odontogram_data = normalize_to_v3


def compute_global_state(surfaces: dict) -> str:
    """
    Calcula el estado global de un diente a partir de sus superficies.

    Heurística:
    - Si todas las superficies no-sanas tienen el mismo estado → retorna ese estado.
    - Si hay estados mixtos → retorna "healthy" (el detalle está en las superficies).
    - Si todas son sanas → retorna "healthy".

    Args:
        surfaces: dict con las 5 claves SURFACE_KEYS → SurfaceState dict

    Returns:
        str con el ID de estado predominante.
    """
    non_healthy_states: set = set()

    for sk in SURFACE_KEYS:
        s = surfaces.get(sk, {})
        if isinstance(s, dict):
            st = s.get("state", "healthy")
            if st != "healthy":
                non_healthy_states.add(st)

    if len(non_healthy_states) == 1:
        return non_healthy_states.pop()

    # Mixed o todo sano → "healthy" (el caller debe leer superficies para detalle)
    return "healthy"
