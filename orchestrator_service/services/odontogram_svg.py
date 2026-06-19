"""
Odontogram SVG generator — server-side rendering for PDF/print output.

Mirrors the React ToothSVG component using the same circular geometry:
center circle (occlusal) + 4 outer ring segments divided by diagonal cross.
Adapted for white-background print output with high-contrast colors.
"""

import json
from typing import Optional

# ---------------------------------------------------------------------------
# FDI quadrant definitions
# ---------------------------------------------------------------------------
UPPER_RIGHT = [18, 17, 16, 15, 14, 13, 12, 11]
UPPER_LEFT  = [21, 22, 23, 24, 25, 26, 27, 28]
LOWER_RIGHT = [48, 47, 46, 45, 44, 43, 42, 41]
LOWER_LEFT  = [31, 32, 33, 34, 35, 36, 37, 38]
ALL_PERMANENT = UPPER_RIGHT + UPPER_LEFT + LOWER_RIGHT + LOWER_LEFT

# ---------------------------------------------------------------------------
# SVG surface paths — same geometry as React ToothSVG.tsx
# ViewBox 0 0 40 40, center (20,20), outer R=18, inner r=7
# Diagonal cross at 45 degrees
# ---------------------------------------------------------------------------
SURFACE_PATHS = {
    "occlusal":   "M 20,13 A 7,7 0 1,0 20,27 A 7,7 0 1,0 20,13 Z",
    "vestibular": "M 7.3,7.3 A 18,18 0 0,1 32.7,7.3 L 25,15 A 7,7 0 0,0 15,15 Z",
    "distal":     "M 32.7,7.3 A 18,18 0 0,1 32.7,32.7 L 25,25 A 7,7 0 0,0 25,15 Z",
    "lingual":    "M 32.7,32.7 A 18,18 0 0,1 7.3,32.7 L 15,25 A 7,7 0 0,0 25,25 Z",
    "mesial":     "M 7.3,32.7 A 18,18 0 0,1 7.3,7.3 L 15,15 A 7,7 0 0,0 15,25 Z",
}

SURFACE_KEYS = ["occlusal", "vestibular", "lingual", "mesial", "distal"]


def _get_surface_path(tooth_id: int, surface_name: str) -> str:
    """DLD-73: Return the correct SVG path, swapping mesial/distal for Q1/Q4.

    Mesial always points toward the midline. The base paths have mesial=LEFT.
    For Q1 (11-18) and Q4 (41-48), the midline is to the RIGHT, so we swap.
    """
    quadrant = tooth_id // 10
    # Q1/Q4 = permanent right side, Q5/Q8 = deciduous right side (same anatomy)
    if quadrant in (1, 4, 5, 8) and surface_name in ("mesial", "distal"):
        swapped = "distal" if surface_name == "mesial" else "mesial"
        return SURFACE_PATHS[swapped]
    return SURFACE_PATHS[surface_name]

# ---------------------------------------------------------------------------
# Print colors — high contrast for white background (42 states)
# Falls back to healthy for unknown states.
# ---------------------------------------------------------------------------
PRINT_FILLS = {
    "healthy":               {"fill": "#f3f4f6", "stroke": "#6b7280"},
    # Preexistente
    "implante":              {"fill": "#bfdbfe", "stroke": "#1d4ed8"},
    "radiografia":           {"fill": "#fde68a", "stroke": "#b45309"},
    "restauracion_resina":   {"fill": "#fde68a", "stroke": "#b45309"},
    "restauracion_amalgama": {"fill": "#9ca3af", "stroke": "#374151"},
    "restauracion_temporal": {"fill": "#fef08a", "stroke": "#a16207"},
    "sellador_fisuras":      {"fill": "#fef08a", "stroke": "#a16207"},
    "carilla":               {"fill": "#ddd6fe", "stroke": "#6d28d9"},
    "puente":                {"fill": "#bfdbfe", "stroke": "#1d4ed8"},
    "corona_porcelana":      {"fill": "#93c5fd", "stroke": "#1e3a8a"},
    "corona_resina":         {"fill": "#fbcfe8", "stroke": "#be185d"},
    "corona_metalceramica":  {"fill": "#fcd34d", "stroke": "#92400e"},
    "corona_temporal":       {"fill": "#fcd34d", "stroke": "#92400e"},
    "incrustacion":          {"fill": "#fde68a", "stroke": "#b45309"},
    "onlay":                 {"fill": "#fde68a", "stroke": "#a16207"},
    "poste":                 {"fill": "#fed7aa", "stroke": "#9a3412"},
    "perno":                 {"fill": "#9ca3af", "stroke": "#404040"},
    "fibras_ribbond":        {"fill": "#ddd6fe", "stroke": "#6d28d9"},
    "tratamiento_conducto":  {"fill": "#fed7aa", "stroke": "#9a3412"},
    "protesis_removible":    {"fill": "#bfdbfe", "stroke": "#1d4ed8"},
    "diente_erupcion":       {"fill": "#fed7aa", "stroke": "#9a3412"},
    "diente_no_erupcionado": {"fill": "#fed7aa", "stroke": "#9a3412"},
    "ausente":               {"fill": "#d1d5db", "stroke": "#4b5563"},
    "otra_preexistencia":    {"fill": "#fed7aa", "stroke": "#9a3412"},
    "treatment_planned":     {"fill": "#fef08a", "stroke": "#a16207"},
    # Lesion
    "mancha_blanca":         {"fill": "#fef3c7", "stroke": "#b45309"},
    "surco_profundo":        {"fill": "#fed7aa", "stroke": "#9a3412"},
    "caries":                {"fill": "#fca5a5", "stroke": "#991b1b"},
    "caries_penetrante":     {"fill": "#f87171", "stroke": "#7f1d1d"},
    "necrosis_pulpar":       {"fill": "#9ca3af", "stroke": "#111827"},
    "proceso_apical":        {"fill": "#fca5a5", "stroke": "#991b1b"},
    "fistula":               {"fill": "#fdba74", "stroke": "#9a3412"},
    "indicacion_extraccion": {"fill": "#fca5a5", "stroke": "#991b1b"},
    "abrasion":              {"fill": "#fef08a", "stroke": "#854d0e"},
    "abfraccion":            {"fill": "#fef08a", "stroke": "#854d0e"},
    "atricion":              {"fill": "#fef08a", "stroke": "#854d0e"},
    "erosion":               {"fill": "#fed7aa", "stroke": "#9a3412"},
    "fractura_horizontal":   {"fill": "#fca5a5", "stroke": "#991b1b"},
    "fractura_vertical":     {"fill": "#fca5a5", "stroke": "#991b1b"},
    "movilidad":             {"fill": "#fbcfe8", "stroke": "#be185d"},
    "hipomineralizacion_mih":{"fill": "#fef08a", "stroke": "#854d0e"},
    "otra_lesion":           {"fill": "#fed7aa", "stroke": "#9a3412"},
    # Legacy aliases
    "restoration":       {"fill": "#fde68a", "stroke": "#b45309"},
    "root_canal":        {"fill": "#fed7aa", "stroke": "#9a3412"},
    "crown":             {"fill": "#93c5fd", "stroke": "#1e3a8a"},
    "implant":           {"fill": "#bfdbfe", "stroke": "#1d4ed8"},
    "prosthesis":        {"fill": "#bfdbfe", "stroke": "#1d4ed8"},
    "extraction":        {"fill": "#f3f4f6", "stroke": "#9ca3af"},
    "missing":           {"fill": "#f3f4f6", "stroke": "#9ca3af"},
}

STATE_LABELS = {
    "healthy": "Sano", "caries": "Caries", "restauracion_resina": "Rest. resina",
    "restauracion_amalgama": "Rest. amalgama", "restauracion_temporal": "Rest. temporal",
    "sellador_fisuras": "Sellador", "carilla": "Carilla", "puente": "Puente",
    "corona_porcelana": "Corona porc.", "corona_resina": "Corona resina",
    "corona_metalceramica": "Corona M-C", "corona_temporal": "Corona temp.",
    "incrustacion": "Incrustación", "onlay": "Onlay", "poste": "Poste", "perno": "Perno",
    "fibras_ribbond": "Fibras Ribbond", "tratamiento_conducto": "Conducto",
    "implante": "Implante", "radiografia": "Radiografía",
    "protesis_removible": "Prótesis rem.", "diente_erupcion": "En erupción",
    "diente_no_erupcionado": "No erupcionado", "ausente": "Ausente",
    "otra_preexistencia": "Otra preex.", "treatment_planned": "Planificado",
    "mancha_blanca": "Mancha blanca", "surco_profundo": "Surco prof.",
    "caries_penetrante": "Caries penet.", "necrosis_pulpar": "Necrosis",
    "proceso_apical": "Proc. apical", "fistula": "Fístula",
    "indicacion_extraccion": "Ind. extracción", "abrasion": "Abrasión",
    "abfraccion": "Abfracción", "atricion": "Atrición", "erosion": "Erosión",
    "fractura_horizontal": "Fract. horiz.", "fractura_vertical": "Fract. vert.",
    "movilidad": "Movilidad", "hipomineralizacion_mih": "MIH", "otra_lesion": "Otra lesión",
    # Legacy
    "restoration": "Restauración", "root_canal": "Conducto", "crown": "Corona",
    "implant": "Implante", "prosthesis": "Prótesis", "extraction": "Extracción", "missing": "Ausente",
}

# ---------------------------------------------------------------------------
# Layout
# ---------------------------------------------------------------------------
TOOTH_SIZE = 38
TOOTH_GAP  = 2
DIVIDER_W  = 8
LABEL_H    = 14
JAW_SEP_H  = 10
SVG_WIDTH  = 730
SVG_PADDING = 14


def _fdi_label(tooth_id: int) -> str:
    return f"{tooth_id // 10}.{tooth_id % 10}"


def _fills(state: str, custom_color: str = None) -> dict:
    if custom_color:
        return {"fill": f"{custom_color}33", "stroke": custom_color}
    return PRINT_FILLS.get(state, PRINT_FILLS["healthy"])


def _surface_state(surface_data) -> dict:
    """Extract state + optional custom color from v3 surface format.
    Returns {"state": str, "color": str | None}."""
    if isinstance(surface_data, dict):
        return {"state": surface_data.get("state", "healthy"), "color": surface_data.get("color")}
    if isinstance(surface_data, str):
        return {"state": surface_data, "color": None}
    return {"state": "healthy", "color": None}


def _render_tooth_group(tooth_id: int, tooth_data: dict, tx: float, ty: float,
                         numbers_below: bool) -> str:
    """Render a single tooth with per-surface colors."""
    state = tooth_data.get("state", "healthy")
    surfaces = tooth_data.get("surfaces", {})
    fills = _fills(state)
    is_absent = state in ("missing", "ausente", "extraction", "indicacion_extraccion")

    label = _fdi_label(tooth_id)
    tooth_y = ty + (0 if not numbers_below else LABEL_H)
    label_y = ty + (LABEL_H - 2) if not numbers_below else (ty + LABEL_H + TOOTH_SIZE + 10)
    scale = TOOTH_SIZE / 40.0

    parts = []

    # FDI number label
    parts.append(
        f'<text x="{tx + TOOTH_SIZE / 2:.1f}" y="{label_y:.1f}" '
        f'text-anchor="middle" font-family="Arial,sans-serif" '
        f'font-size="9" font-weight="bold" fill="#555555">{label}</text>'
    )

    parts.append(f'<g transform="translate({tx:.1f},{tooth_y:.1f}) scale({scale:.4f})">')

    # Render each surface with its own color
    for sk in SURFACE_KEYS:
        sd = _surface_state(surfaces.get(sk, {})) if surfaces else {"state": state, "color": None}
        s_state = sd["state"]
        s_color = sd.get("color")
        sf = _fills(s_state, s_color)
        opacity = "0.35" if is_absent else "0.9"
        parts.append(
            f'  <path d="{_get_surface_path(tooth_id, sk)}" fill="{sf["fill"]}" stroke="{sf["stroke"]}" '
            f'stroke-width="1" opacity="{opacity}"/>'
        )

    # Structural dividers (diagonal cross + inner circle)
    div_color = "#cccccc"
    div_op = "0.3" if is_absent else "0.6"
    for x1, y1, x2, y2 in [(7.3,7.3,15,15),(32.7,7.3,25,15),(32.7,32.7,25,25),(7.3,32.7,15,25)]:
        parts.append(f'  <line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{div_color}" stroke-width="0.7" opacity="{div_op}"/>')
    parts.append(f'  <circle cx="20" cy="20" r="7" fill="none" stroke="{div_color}" stroke-width="0.6" opacity="{div_op}"/>')
    parts.append(f'  <circle cx="20" cy="20" r="18" fill="none" stroke="#bbbbbb" stroke-width="0.4"/>')

    # Extraction X
    if state in ("extraction", "indicacion_extraccion"):
        parts.append('  <line x1="6" y1="6" x2="34" y2="34" stroke="#dc2626" stroke-width="2" stroke-linecap="round"/>')
        parts.append('  <line x1="34" y1="6" x2="6" y2="34" stroke="#dc2626" stroke-width="2" stroke-linecap="round"/>')

    # Missing dash
    if state in ("missing", "ausente"):
        parts.append('  <line x1="10" y1="20" x2="30" y2="20" stroke="#999999" stroke-width="2.5" stroke-linecap="round"/>')

    parts.append("</g>")
    return "\n".join(parts)


def _render_row(ids: list, teeth_map: dict, row_x: float, row_y: float,
                numbers_below: bool) -> str:
    parts = []
    cx = row_x
    for tid in ids:
        td = teeth_map.get(tid, {"state": "healthy", "surfaces": {}})
        parts.append(_render_tooth_group(tid, td, cx, row_y, numbers_below))
        cx += TOOTH_SIZE + TOOTH_GAP
    return "\n".join(parts)


def _row_width(n: int) -> float:
    return n * TOOTH_SIZE + (n - 1) * TOOTH_GAP


def _render_legend(x: float, y: float, available_width: float, used_states: set) -> tuple:
    """Render legend only for states actually used."""
    items = [s for s in used_states if s != "healthy" and s in STATE_LABELS]
    if not items:
        return "", 0

    cols = min(5, len(items))
    col_w = available_width / cols
    row_h = 20
    parts = []

    for i, state in enumerate(items):
        col = i % cols
        row = i // cols
        lx = x + col * col_w
        ly = y + row * row_h
        sf = _fills(state)
        label = STATE_LABELS.get(state, state)

        parts.append(f'<circle cx="{lx + 7:.1f}" cy="{ly + 7:.1f}" r="5" fill="{sf["fill"]}" stroke="{sf["stroke"]}" stroke-width="1"/>')
        parts.append(f'<text x="{lx + 16:.1f}" y="{ly + 11:.1f}" font-family="Arial,sans-serif" font-size="9" fill="#333333">{label}</text>')

    total_rows = (len(items) + cols - 1) // cols
    return "\n".join(parts), total_rows * row_h + 4


def normalize_odontogram_data(raw) -> dict:
    """Normalize any odontogram format to v3."""
    from shared.odontogram_utils import normalize_to_v3
    return normalize_to_v3(raw)


# ---------------------------------------------------------------------------
# Main public function
# ---------------------------------------------------------------------------
def render_odontogram_svg(odontogram_data: Optional[dict]) -> str:
    """Generate a print-friendly SVG string for PDF/document output."""
    data = normalize_odontogram_data(odontogram_data)

    # Build lookup from v3 format: tooth_id → {state, surfaces, notes}
    teeth_map: dict = {}
    for dentition_key in ("permanent", "deciduous"):
        dentition = data.get(dentition_key, {})
        for t in dentition.get("teeth", []):
            tid = t.get("id")
            if tid is not None:
                teeth_map[int(tid)] = t

    # Fill missing permanent teeth with healthy
    for tid in ALL_PERMANENT:
        if tid not in teeth_map:
            teeth_map[tid] = {"state": "healthy", "surfaces": {}}

    # Collect used states
    used_states = set()
    for tid in ALL_PERMANENT:
        td = teeth_map.get(tid, {})
        st = td.get("state", "healthy")
        if st != "healthy":
            used_states.add(st)
        for sk in SURFACE_KEYS:
            ss = _surface_state(td.get("surfaces", {}).get(sk, {}))
            ssv = ss["state"] if isinstance(ss, dict) else ss
            if ssv != "healthy":
                used_states.add(ssv)

    is_empty = len(used_states) == 0

    # ---------------------------------------------------------------------------
    # Layout
    # ---------------------------------------------------------------------------
    row_h = LABEL_H + TOOTH_SIZE
    q_width = _row_width(8)
    jaw_w = q_width + DIVIDER_W + q_width
    jaw_x = (SVG_WIDTH - jaw_w) / 2

    y = SVG_PADDING
    title_y = y + 16; y += 30

    if is_empty:
        y += 18  # space for "no data" note

    y += 6  # gap between title and first row of teeth
    upper_row_y = y; y += row_h
    sep_y = y + 2; y += JAW_SEP_H
    lower_row_y = y; y += row_h

    # Legend
    y += 12; legend_title_y = y + 10; y += 18
    legend_svg, legend_h = _render_legend(jaw_x, y, jaw_w, used_states)
    y += legend_h

    # Summary
    y += 10; summary_title_y = y + 10; y += 18
    affected_teeth = [(tid, teeth_map[tid].get("state", "healthy")) for tid in ALL_PERMANENT if teeth_map.get(tid, {}).get("state", "healthy") != "healthy"]

    summary_lines = [(f"Piezas afectadas: {len(affected_teeth)}/32", False)]
    for tid, st in affected_teeth:
        summary_lines.append((f"  {_fdi_label(tid)}  —  {STATE_LABELS.get(st, st)}", True))

    line_h = 14
    y += len(summary_lines) * line_h + 4
    total_h = y + SVG_PADDING

    # ---------------------------------------------------------------------------
    # Build SVG
    # ---------------------------------------------------------------------------
    p = []
    p.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="100%" height="auto" viewBox="0 0 {SVG_WIDTH} {total_h}" style="max-width:{SVG_WIDTH}px; background:#ffffff;font-family:Arial,sans-serif;">')
    p.append(f'<rect width="100%" height="100%" fill="#ffffff"/>')

    # Title
    p.append(f'<text x="{SVG_WIDTH/2:.1f}" y="{title_y}" text-anchor="middle" font-size="14" font-weight="bold" fill="#111111">Odontograma FDI</text>')

    if is_empty:
        p.append(f'<text x="{SVG_WIDTH/2:.1f}" y="{title_y+16}" text-anchor="middle" font-size="10" fill="#999999" font-style="italic">Sin datos de odontograma registrados</text>')

    # Upper jaw
    ul_x = jaw_x
    ur_x = jaw_x + q_width + DIVIDER_W
    p.append(_render_row(UPPER_RIGHT, teeth_map, ul_x, upper_row_y, False))
    p.append(_render_row(UPPER_LEFT, teeth_map, ur_x, upper_row_y, False))

    # Midline
    div_x = jaw_x + q_width + DIVIDER_W / 2
    p.append(f'<line x1="{div_x:.1f}" y1="{upper_row_y+4}" x2="{div_x:.1f}" y2="{upper_row_y+row_h-4}" stroke="#cccccc" stroke-width="1" stroke-dasharray="3,2"/>')

    # Jaw separator
    p.append(f'<line x1="{jaw_x:.1f}" y1="{sep_y:.1f}" x2="{jaw_x+jaw_w:.1f}" y2="{sep_y:.1f}" stroke="#aaaaaa" stroke-width="2"/>')
    p.append(f'<text x="{jaw_x-4:.1f}" y="{sep_y+4:.1f}" text-anchor="end" font-size="8" fill="#888888">Superior</text>')
    p.append(f'<text x="{jaw_x-4:.1f}" y="{sep_y+14:.1f}" text-anchor="end" font-size="8" fill="#888888">Inferior</text>')

    # Lower jaw
    p.append(_render_row(LOWER_RIGHT, teeth_map, ul_x, lower_row_y, True))
    p.append(_render_row(LOWER_LEFT, teeth_map, ur_x, lower_row_y, True))
    p.append(f'<line x1="{div_x:.1f}" y1="{lower_row_y+4}" x2="{div_x:.1f}" y2="{lower_row_y+row_h-4}" stroke="#cccccc" stroke-width="1" stroke-dasharray="3,2"/>')

    # Legend
    if used_states:
        p.append(f'<text x="{jaw_x:.1f}" y="{legend_title_y}" font-size="10" font-weight="bold" fill="#444444" letter-spacing="1">REFERENCIAS</text>')
        p.append(f'<line x1="{jaw_x:.1f}" y1="{legend_title_y+3}" x2="{jaw_x+jaw_w:.1f}" y2="{legend_title_y+3}" stroke="#dddddd" stroke-width="1"/>')
        p.append(legend_svg)

    # Summary
    p.append(f'<text x="{jaw_x:.1f}" y="{summary_title_y}" font-size="10" font-weight="bold" fill="#444444" letter-spacing="1">RESUMEN</text>')
    p.append(f'<line x1="{jaw_x:.1f}" y1="{summary_title_y+3}" x2="{jaw_x+jaw_w:.1f}" y2="{summary_title_y+3}" stroke="#dddddd" stroke-width="1"/>')

    ly = summary_title_y + 18
    for text, is_detail in summary_lines:
        color = "#555555" if is_detail else "#222222"
        weight = "normal" if is_detail else "bold"
        size = "10" if is_detail else "11"
        p.append(f'<text x="{jaw_x + (16 if is_detail else 0):.1f}" y="{ly}" font-size="{size}" font-weight="{weight}" fill="{color}">{text}</text>')
        ly += line_h

    p.append("</svg>")
    return "\n".join(p)
