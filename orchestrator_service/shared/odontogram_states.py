"""
shared/odontogram_states.py — Catálogo de estados del odontograma

Define los 42 estados clínicos organizados en 2 categorías:
- PREEXISTENTE (25 estados): condiciones previas del diente
- LESIÓN (17 estados): patologías activas

Cada estado tiene: id, category, label_key (i18n), default_color,
symbol, print_fill, print_stroke.

Espejo del catálogo TypeScript: frontend_react/src/constants/odontogramStates.ts
Ambos archivos DEBEN mantenerse sincronizados.
"""

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class OdontogramStateEntry:
    """Entrada del catálogo de estados odontológicos."""
    id: str
    category: str            # "preexistente" | "lesion"
    label_key: str           # "odontogram.states.{id}"
    default_color: str       # HEX para pantalla (fondo oscuro)
    symbol: str              # 1-3 chars
    print_fill: str          # HEX fill para PDF (fondo blanco)
    print_stroke: str        # HEX stroke para PDF


# ============================================================
# CATÁLOGO COMPLETO — 42 ESTADOS
# ============================================================

ODONTOGRAM_STATES: list[OdontogramStateEntry] = [
    # ── PREEXISTENTE (25) ──
    OdontogramStateEntry("healthy", "preexistente", "odontogram.states.healthy", "#f0f0f0", "○", "#f5f5f5", "#9ca3af"),
    OdontogramStateEntry("implante", "preexistente", "odontogram.states.implante", "#6366f1", "Im", "#e0e7ff", "#4338ca"),
    OdontogramStateEntry("radiografia", "preexistente", "odontogram.states.radiografia", "#f59e0b", "Rx", "#fef3c7", "#d97706"),
    OdontogramStateEntry("restauracion_resina", "preexistente", "odontogram.states.restauracion_resina", "#3b82f6", "Rr", "#dbeafe", "#1d4ed8"),
    OdontogramStateEntry("restauracion_amalgama", "preexistente", "odontogram.states.restauracion_amalgama", "#6b7280", "Ra", "#e5e7eb", "#374151"),
    OdontogramStateEntry("restauracion_temporal", "preexistente", "odontogram.states.restauracion_temporal", "#a78bfa", "Rt", "#ede9fe", "#7c3aed"),
    OdontogramStateEntry("sellador_fisuras", "preexistente", "odontogram.states.sellador_fisuras", "#10b981", "Sf", "#d1fae5", "#065f46"),
    OdontogramStateEntry("carilla", "preexistente", "odontogram.states.carilla", "#ec4899", "Ca", "#fce7f3", "#be185d"),
    OdontogramStateEntry("puente", "preexistente", "odontogram.states.puente", "#8b5cf6", "Pu", "#ede9fe", "#6d28d9"),
    OdontogramStateEntry("corona_porcelana", "preexistente", "odontogram.states.corona_porcelana", "#d946ef", "Cp", "#fae8ff", "#a21caf"),
    OdontogramStateEntry("corona_resina", "preexistente", "odontogram.states.corona_resina", "#a855f7", "Cr", "#f3e8ff", "#7e22ce"),
    OdontogramStateEntry("corona_metalceramica", "preexistente", "odontogram.states.corona_metalceramica", "#7c3aed", "Cm", "#ede9fe", "#5b21b6"),
    OdontogramStateEntry("corona_temporal", "preexistente", "odontogram.states.corona_temporal", "#d946ef", "Ct", "#f5f3ff", "#9333ea"),
    OdontogramStateEntry("incrustacion", "preexistente", "odontogram.states.incrustacion", "#14b8a6", "In", "#ccfbf1", "#0f766e"),
    OdontogramStateEntry("onlay", "preexistente", "odontogram.states.onlay", "#0d9488", "On", "#99f6e4", "#115e59"),
    OdontogramStateEntry("poste", "preexistente", "odontogram.states.poste", "#f97316", "Po", "#ffedd5", "#c2410c"),
    OdontogramStateEntry("perno", "preexistente", "odontogram.states.perno", "#ea580c", "Pe", "#fed7aa", "#9a3412"),
    OdontogramStateEntry("fibras_ribbond", "preexistente", "odontogram.states.fibras_ribbond", "#84cc16", "FR", "#ecfccb", "#4d7c0f"),
    OdontogramStateEntry("tratamiento_conducto", "preexistente", "odontogram.states.tratamiento_conducto", "#f97316", "Tc", "#fed7aa", "#ea580c"),
    OdontogramStateEntry("protesis_removible", "preexistente", "odontogram.states.protesis_removible", "#14b8a6", "Pr", "#99f6e4", "#0d9488"),
    OdontogramStateEntry("diente_erupcion", "preexistente", "odontogram.states.diente_erupcion", "#22c55e", "Ep", "#dcfce7", "#16a34a"),
    OdontogramStateEntry("diente_no_erupcionado", "preexistente", "odontogram.states.diente_no_erupcionado", "#a3a3a3", "NE", "#e5e5e5", "#737373"),
    OdontogramStateEntry("ausente", "preexistente", "odontogram.states.ausente", "#d4d4d4", "--", "#fafafa", "#ced4da"),
    OdontogramStateEntry("otra_preexistencia", "preexistente", "odontogram.states.otra_preexistencia", "#78716c", "OP", "#e7e5e4", "#57534e"),
    OdontogramStateEntry("treatment_planned", "preexistente", "odontogram.states.treatment_planned", "#f59e0b", "Tp", "#fef08a", "#ca8a04"),

    # ── LESIÓN (17) ──
    OdontogramStateEntry("mancha_blanca", "lesion", "odontogram.states.mancha_blanca", "#fef3c7", "MB", "#fffbeb", "#d97706"),
    OdontogramStateEntry("surco_profundo", "lesion", "odontogram.states.surco_profundo", "#fbbf24", "SP", "#fef9c3", "#a16207"),
    OdontogramStateEntry("caries", "lesion", "odontogram.states.caries", "#ef4444", "C", "#fecaca", "#dc2626"),
    OdontogramStateEntry("caries_penetrante", "lesion", "odontogram.states.caries_penetrante", "#b91c1c", "CP", "#fca5a5", "#991b1b"),
    OdontogramStateEntry("necrosis_pulpar", "lesion", "odontogram.states.necrosis_pulpar", "#1f2937", "Np", "#d1d5db", "#111827"),
    OdontogramStateEntry("proceso_apical", "lesion", "odontogram.states.proceso_apical", "#dc2626", "PA", "#fecaca", "#b91c1c"),
    OdontogramStateEntry("fistula", "lesion", "odontogram.states.fistula", "#f97316", "Fi", "#fed7aa", "#c2410c"),
    OdontogramStateEntry("indicacion_extraccion", "lesion", "odontogram.states.indicacion_extraccion", "#ef4444", "Ex", "#f5f5f5", "#adb5bd"),
    OdontogramStateEntry("abrasion", "lesion", "odontogram.states.abrasion", "#fb923c", "Ab", "#ffedd5", "#ea580c"),
    OdontogramStateEntry("abfraccion", "lesion", "odontogram.states.abfraccion", "#fcd34d", "Af", "#fef9c3", "#ca8a04"),
    OdontogramStateEntry("atricion", "lesion", "odontogram.states.atricion", "#f59e0b", "At", "#fef3c7", "#b45309"),
    OdontogramStateEntry("erosion", "lesion", "odontogram.states.erosion", "#fdba74", "Er", "#ffedd5", "#c2410c"),
    OdontogramStateEntry("fractura_horizontal", "lesion", "odontogram.states.fractura_horizontal", "#ef4444", "Fh", "#fecaca", "#b91c1c"),
    OdontogramStateEntry("fractura_vertical", "lesion", "odontogram.states.fractura_vertical", "#dc2626", "Fv", "#fca5a5", "#991b1b"),
    OdontogramStateEntry("movilidad", "lesion", "odontogram.states.movilidad", "#fb7185", "Mo", "#fecdd3", "#e11d48"),
    OdontogramStateEntry("hipomineralizacion_mih", "lesion", "odontogram.states.hipomineralizacion_mih", "#fbbf24", "MH", "#fef9c3", "#a16207"),
    OdontogramStateEntry("otra_lesion", "lesion", "odontogram.states.otra_lesion", "#78716c", "Ol", "#e7e5e4", "#57534e"),
]


# ── Lookups O(1) ──

ODONTOGRAM_STATES_BY_ID: dict[str, OdontogramStateEntry] = {s.id: s for s in ODONTOGRAM_STATES}

PREEXISTENTE_STATES: list[OdontogramStateEntry] = [s for s in ODONTOGRAM_STATES if s.category == "preexistente"]
LESION_STATES: list[OdontogramStateEntry] = [s for s in ODONTOGRAM_STATES if s.category == "lesion"]

# Set of all valid state IDs for validation
VALID_STATE_IDS: set[str] = set(ODONTOGRAM_STATES_BY_ID.keys())


# ── Retrocompatibilidad ──

LEGACY_STATE_MAP: dict[str, str] = {
    "healthy": "healthy",
    "caries": "caries",
    "restoration": "restauracion_resina",
    "root_canal": "tratamiento_conducto",
    "crown": "corona_porcelana",
    "implant": "implante",
    "prosthesis": "protesis_removible",
    "extraction": "indicacion_extraccion",
    "missing": "ausente",
    "treatment_planned": "treatment_planned",
    "treated": "restauracion_resina",
    "crowned": "corona_porcelana",
    "extracted": "indicacion_extraccion",
}


# ── Funciones de lookup ──

def get_state_by_id(state_id: str) -> Optional[OdontogramStateEntry]:
    """Retorna el estado por ID o None si no existe."""
    return ODONTOGRAM_STATES_BY_ID.get(state_id)


def get_states_by_category(category: str) -> list[OdontogramStateEntry]:
    """Retorna estados filtrados por categoría."""
    return [s for s in ODONTOGRAM_STATES if s.category == category]


def normalize_legacy_state_id(old_id: str) -> str:
    """Mapea un ID de estado v1/v2 a su equivalente v3. Si no está en el mapa, retorna tal cual."""
    return LEGACY_STATE_MAP.get(old_id, old_id)


def is_valid_state(state_id: str) -> bool:
    """Verifica si un ID de estado es válido en el catálogo v3."""
    return state_id in VALID_STATE_IDS


def resolve_print_color(state_id: str, custom_color: Optional[str] = None) -> dict:
    """
    Retorna {"fill": ..., "stroke": ...} para rendering PDF.
    Si hay custom_color, genera fill semi-transparente desde ese color.
    """
    if custom_color:
        return {"fill": f"{custom_color}33", "stroke": custom_color}
    entry = ODONTOGRAM_STATES_BY_ID.get(state_id)
    if entry:
        return {"fill": entry.print_fill, "stroke": entry.print_stroke}
    # Fallback to healthy
    healthy = ODONTOGRAM_STATES_BY_ID["healthy"]
    return {"fill": healthy.print_fill, "stroke": healthy.print_stroke}
