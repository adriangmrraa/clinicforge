"""
Odontogram SVG generator — server-side rendering for PDF/print output.

Replicates the React Odontogram component (Odontogram.tsx) using pure SVG,
adapted for white-background print output with high-contrast colors.
No external CSS, no animations, fully self-contained SVG string.
"""

import json
from typing import Optional

# ---------------------------------------------------------------------------
# FDI quadrant definitions (same order as React)
# ---------------------------------------------------------------------------
UPPER_RIGHT = [18, 17, 16, 15, 14, 13, 12, 11]
UPPER_LEFT  = [21, 22, 23, 24, 25, 26, 27, 28]
LOWER_RIGHT = [48, 47, 46, 45, 44, 43, 42, 41]
LOWER_LEFT  = [31, 32, 33, 34, 35, 36, 37, 38]

ALL_TEETH = UPPER_RIGHT + UPPER_LEFT + LOWER_RIGHT + LOWER_LEFT

# ---------------------------------------------------------------------------
# SVG surface paths — exact same as React SURFACE_PATHS
# ViewBox 0 0 40 40
# ---------------------------------------------------------------------------
SURFACE_PATHS = {
    "top":    "M20,2 A18,18 0 0,1 38,20 L27,20 A7,7 0 0,0 20,13 Z",
    "right":  "M38,20 A18,18 0 0,1 20,38 L20,27 A7,7 0 0,0 27,20 Z",
    "bottom": "M20,38 A18,18 0 0,1 2,20 L13,20 A7,7 0 0,0 20,27 Z",
    "left":   "M2,20 A18,18 0 0,1 20,2 L20,13 A7,7 0 0,0 13,20 Z",
}

# ---------------------------------------------------------------------------
# Print-adapted color scheme — white background, solid fills, high contrast
# ---------------------------------------------------------------------------
PRINT_FILLS = {
    "healthy":           {"fill": "#f0f0f0", "stroke": "#999999"},
    "caries":            {"fill": "#fecaca", "stroke": "#dc2626"},
    "restoration":       {"fill": "#bfdbfe", "stroke": "#2563eb"},
    "root_canal":        {"fill": "#fed7aa", "stroke": "#ea580c"},
    "crown":             {"fill": "#ddd6fe", "stroke": "#7c3aed"},
    "implant":           {"fill": "#c7d2fe", "stroke": "#4f46e5"},
    "prosthesis":        {"fill": "#99f6e4", "stroke": "#0d9488"},
    "extraction":        {"fill": "#f5f5f5", "stroke": "#adb5bd"},
    "missing":           {"fill": "#fafafa", "stroke": "#ced4da"},
    "treatment_planned": {"fill": "#fef08a", "stroke": "#ca8a04"},
}

# ---------------------------------------------------------------------------
# State symbols and labels (same as React STATE_SYMBOLS)
# ---------------------------------------------------------------------------
STATE_SYMBOLS = {
    "healthy":           "○",
    "caries":            "C",
    "restoration":       "R",
    "root_canal":        "Tc",
    "crown":             "Co",
    "implant":           "Im",
    "prosthesis":        "Pr",
    "extraction":        "✕",
    "missing":           "—",
    "treatment_planned": "P",
}

STATE_LABELS = {
    "healthy":           "Sano",
    "caries":            "Caries",
    "restoration":       "Restauración",
    "root_canal":        "Conducto",
    "crown":             "Corona",
    "implant":           "Implante",
    "prosthesis":        "Prótesis",
    "extraction":        "Extracción",
    "missing":           "Ausente",
    "treatment_planned": "Plan de tratamiento",
}

# State render order for the legend
STATE_ORDER = [
    "healthy", "caries", "restoration", "root_canal", "crown",
    "implant", "prosthesis", "extraction", "missing", "treatment_planned",
]

# ---------------------------------------------------------------------------
# Layout constants
# ---------------------------------------------------------------------------
TOOTH_SIZE   = 38    # px — rendered size of each tooth SVG
TOOTH_GAP    = 2     # px — gap between teeth
DIVIDER_W    = 8     # px — width of the jaw midline divider column
LABEL_H      = 14    # px — height reserved for FDI number label above/below tooth
JAW_SEP_H    = 10    # px — height of the horizontal jaw separator line
LEGEND_ITEM_W = 120  # px — width allocated per legend item
LEGEND_COLS   = 5    # items per legend row

SVG_WIDTH    = 730   # total SVG width — fits A4 with 1cm margins
SVG_PADDING  = 14    # left/right padding


# ---------------------------------------------------------------------------
# Helper: FDI label string  (e.g. 18 → "1.8")
# ---------------------------------------------------------------------------
def _fdi_label(tooth_id: int) -> str:
    return f"{tooth_id // 10}.{tooth_id % 10}"


# ---------------------------------------------------------------------------
# Helper: safe state lookup
# ---------------------------------------------------------------------------
def _fills(state: str) -> dict:
    return PRINT_FILLS.get(state, PRINT_FILLS["healthy"])


# ---------------------------------------------------------------------------
# Render a single tooth as SVG <g> elements (no outer <svg> tag).
# tx, ty = top-left corner of the tooth bounding box in the parent coordinate system.
# numbers_below = True for lower jaw (label goes below), False for upper (label above).
# ---------------------------------------------------------------------------
def _render_tooth_group(tooth_id: int, state: str, tx: float, ty: float,
                         numbers_below: bool) -> str:
    fills = _fills(state)
    fill   = fills["fill"]
    stroke = fills["stroke"]

    is_absent  = state in ("missing", "extraction")
    surface_op = "0.35" if is_absent else "0.9"
    line_op    = "0.20" if is_absent else "0.4"

    label = _fdi_label(tooth_id)

    # y-coordinate of the tooth SVG square (inside the bounding box)
    tooth_y = ty + (0 if not numbers_below else LABEL_H)
    label_y = ty + (LABEL_H - 2) if not numbers_below else (ty + LABEL_H + TOOTH_SIZE + 10)

    # Scale factor: we want TOOTH_SIZE px but the viewBox is 40x40
    scale = TOOTH_SIZE / 40.0

    parts = []

    # FDI label
    parts.append(
        f'<text x="{tx + TOOTH_SIZE / 2:.1f}" y="{label_y:.1f}" '
        f'text-anchor="middle" font-family="Arial, sans-serif" '
        f'font-size="9" font-weight="bold" fill="#555555">{label}</text>'
    )

    # Tooth group — transform: translate + scale to fit TOOTH_SIZE
    parts.append(
        f'<g transform="translate({tx:.1f},{tooth_y:.1f}) scale({scale:.4f})">'
    )

    # 4 surface paths
    for surface, path_d in SURFACE_PATHS.items():
        parts.append(
            f'  <path d="{path_d}" fill="{fill}" stroke="{stroke}" '
            f'stroke-width="1" opacity="{surface_op}"/>'
        )

    # Center circle (occlusal)
    parts.append(
        f'  <circle cx="20" cy="20" r="7" fill="{fill}" stroke="{stroke}" '
        f'stroke-width="1" opacity="{surface_op}"/>'
    )

    # Cross connector lines (same as React)
    for x1, y1, x2, y2 in [
        (20, 2,  20, 13),
        (20, 27, 20, 38),
        (2,  20, 13, 20),
        (27, 20, 38, 20),
    ]:
        parts.append(
            f'  <line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" '
            f'stroke="{stroke}" stroke-width="0.6" opacity="{line_op}"/>'
        )

    # Extraction X overlay
    if state == "extraction":
        parts.append(
            '  <line x1="6" y1="6" x2="34" y2="34" stroke="#dc2626" '
            'stroke-width="2" stroke-linecap="round"/>'
        )
        parts.append(
            '  <line x1="34" y1="6" x2="6" y2="34" stroke="#dc2626" '
            'stroke-width="2" stroke-linecap="round"/>'
        )

    # Missing dash
    if state == "missing":
        parts.append(
            '  <line x1="10" y1="20" x2="30" y2="20" stroke="#999999" '
            'stroke-width="2.5" stroke-linecap="round"/>'
        )

    parts.append("</g>")

    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Render a row of tooth IDs.
# Returns (svg_string, row_width_px).
# row_x, row_y = top-left corner in parent coordinate system.
# numbers_below: True for lower jaw.
# ---------------------------------------------------------------------------
def _render_row(ids: list, teeth_map: dict, row_x: float, row_y: float,
                numbers_below: bool) -> str:
    parts = []
    cursor_x = row_x
    for tooth_id in ids:
        state = teeth_map.get(tooth_id, "healthy")
        parts.append(
            _render_tooth_group(tooth_id, state, cursor_x, row_y, numbers_below)
        )
        cursor_x += TOOTH_SIZE + TOOTH_GAP
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Row pixel width (8 teeth + gaps)
# ---------------------------------------------------------------------------
def _row_width(n: int) -> float:
    return n * TOOTH_SIZE + (n - 1) * TOOTH_GAP


# ---------------------------------------------------------------------------
# Render legend row
# ---------------------------------------------------------------------------
def _render_legend(x: float, y: float, available_width: float) -> tuple[str, float]:
    """Returns (svg_string, height_used)."""
    parts = []
    col_w = available_width / LEGEND_COLS
    row_h = 22
    cx_off = 8   # circle center offset from left of column
    tx_off = 20  # text left edge offset

    for i, state in enumerate(STATE_ORDER):
        col = i % LEGEND_COLS
        row = i // LEGEND_COLS
        lx = x + col * col_w
        ly = y + row * row_h

        fills = _fills(state)
        label = STATE_LABELS[state]
        sym   = STATE_SYMBOLS[state]

        # Colored circle
        parts.append(
            f'<circle cx="{lx + cx_off:.1f}" cy="{ly + 8:.1f}" r="6" '
            f'fill="{fills["fill"]}" stroke="{fills["stroke"]}" stroke-width="1"/>'
        )
        # Symbol inside circle
        parts.append(
            f'<text x="{lx + cx_off:.1f}" y="{ly + 12:.1f}" '
            f'text-anchor="middle" font-family="Arial, sans-serif" '
            f'font-size="7" font-weight="bold" fill="{fills["stroke"]}">{sym}</text>'
        )
        # Label
        parts.append(
            f'<text x="{lx + tx_off:.1f}" y="{ly + 12:.1f}" '
            f'font-family="Arial, sans-serif" font-size="10" fill="#333333">{label}</text>'
        )

    total_rows = (len(STATE_ORDER) + LEGEND_COLS - 1) // LEGEND_COLS
    height_used = total_rows * row_h + 4
    return "\n".join(parts), height_used


# ---------------------------------------------------------------------------
# Data normalizer (standalone — mirrors task 1.1)
# ---------------------------------------------------------------------------
def normalize_odontogram_data(raw) -> dict:
    """
    Accepts None, JSON string, legacy dict {tooth_id: state_str},
    or v2 dict {teeth: [...], ...}.
    Always returns {"teeth": [...], "affected_count": int, "format_version": "2.0"}.
    """
    if raw is None:
        return {"teeth": [], "affected_count": 0, "format_version": "2.0"}

    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except Exception:
            return {"teeth": [], "affected_count": 0, "format_version": "2.0"}

    if not isinstance(raw, dict):
        return {"teeth": [], "affected_count": 0, "format_version": "2.0"}

    # v2 format: {"teeth": [...]}
    if "teeth" in raw and isinstance(raw["teeth"], list):
        teeth = raw["teeth"]
        affected = sum(
            1 for t in teeth if t.get("state", "healthy") != "healthy"
        )
        return {"teeth": teeth, "affected_count": affected, "format_version": "2.0"}

    # Legacy format: {"18": "caries", "21": {"status": "crown"}, ...}
    if raw and all(str(k).isdigit() for k in raw.keys()):
        teeth = []
        for k, v in raw.items():
            if isinstance(v, str):
                state = v
            elif isinstance(v, dict):
                state = v.get("status", v.get("state", "healthy"))
            else:
                state = "healthy"
            teeth.append({"id": int(k), "state": state, "surfaces": {}, "notes": ""})
        affected = sum(1 for t in teeth if t.get("state", "healthy") != "healthy")
        return {"teeth": teeth, "affected_count": affected, "format_version": "2.0"}

    return {"teeth": [], "affected_count": 0, "format_version": "2.0"}


# ---------------------------------------------------------------------------
# Main public function
# ---------------------------------------------------------------------------
def render_odontogram_svg(odontogram_data: Optional[dict]) -> str:
    """
    Generate a print-friendly SVG string replicating the React Odontogram component.

    Args:
        odontogram_data: Normalized odontogram dict (from normalize_odontogram_data)
                         or raw data in any supported format.

    Returns:
        Valid SVG string, starting with <svg and ending with </svg>.
    """
    # Normalize input
    data = normalize_odontogram_data(odontogram_data)
    teeth_list = data.get("teeth", [])
    affected_count = data.get("affected_count", 0)
    is_empty = len(teeth_list) == 0

    # Build lookup: tooth_id -> state
    if is_empty:
        # Render all 32 teeth as healthy
        teeth_map = {tid: "healthy" for tid in ALL_TEETH}
    else:
        teeth_map = {}
        for t in teeth_list:
            tid = t.get("id")
            state = t.get("state", "healthy")
            if tid is not None:
                teeth_map[int(tid)] = state
        # Fill missing teeth with healthy
        for tid in ALL_TEETH:
            if tid not in teeth_map:
                teeth_map[tid] = "healthy"

    # ---------------------------------------------------------------------------
    # Layout geometry
    # Upper jaw row height = label + tooth
    # Lower jaw row height = tooth + label
    # Each row bounding box: LABEL_H + TOOTH_SIZE
    # ---------------------------------------------------------------------------
    row_h = LABEL_H + TOOTH_SIZE   # 14 + 38 = 52 px per jaw half-row

    # Quadrant pixel widths
    q_width = _row_width(8)   # 8 teeth each quadrant: 8*38 + 7*2 = 318 px

    # Total jaw width = 2 quadrants + divider + gaps
    jaw_w = q_width + DIVIDER_W + q_width   # 318 + 8 + 318 = 644 px

    # Center the jaw within SVG_WIDTH
    jaw_x = (SVG_WIDTH - jaw_w) / 2

    # --- Y positions ---
    y_cursor = SVG_PADDING

    # Title
    title_y = y_cursor + 14
    y_cursor += 24   # title height

    # Upper jaw row (labels above, so row starts at y_cursor)
    upper_row_y = y_cursor
    y_cursor += row_h   # 52 px

    # Jaw separator
    sep_y = y_cursor + 2
    y_cursor += JAW_SEP_H

    # Lower jaw row (labels below)
    lower_row_y = y_cursor
    y_cursor += row_h

    # Legend section
    y_cursor += 12
    legend_title_y = y_cursor + 10
    y_cursor += 18

    legend_x = jaw_x
    legend_y = y_cursor
    legend_svg, legend_h = _render_legend(legend_x, legend_y, jaw_w)
    y_cursor += legend_h

    # Summary section
    y_cursor += 10
    summary_title_y = y_cursor + 10
    y_cursor += 18

    # Collect affected teeth for summary list
    affected_teeth = [
        (tid, teeth_map[tid])
        for tid in ALL_TEETH
        if teeth_map.get(tid, "healthy") != "healthy"
    ]

    summary_lines = []
    # "Piezas afectadas: N/32"
    summary_lines.append(
        (f"Piezas afectadas: {len(affected_teeth)}/32", False)
    )
    if affected_teeth:
        for tid, state in affected_teeth:
            label = STATE_LABELS.get(state, state)
            summary_lines.append((f"  {_fdi_label(tid)}  —  {label}", True))

    summary_line_h = 14
    summary_block_h = len(summary_lines) * summary_line_h + 4
    y_cursor += summary_block_h

    # Empty-state note
    empty_note_h = 20 if is_empty else 0
    y_cursor += empty_note_h

    total_h = y_cursor + SVG_PADDING

    # ---------------------------------------------------------------------------
    # Build SVG
    # ---------------------------------------------------------------------------
    parts = []

    # Root SVG element
    parts.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'width="{SVG_WIDTH}" height="{total_h}" '
        f'viewBox="0 0 {SVG_WIDTH} {total_h}" '
        f'style="background:#ffffff;font-family:Arial,sans-serif;">'
    )

    # White background rect (explicit for PDF renderers)
    parts.append(
        f'<rect width="{SVG_WIDTH}" height="{total_h}" fill="#ffffff"/>'
    )

    # ---------------------------------------------------------------------------
    # Title
    # ---------------------------------------------------------------------------
    parts.append(
        f'<text x="{SVG_WIDTH / 2:.1f}" y="{title_y}" '
        f'text-anchor="middle" font-family="Arial, sans-serif" '
        f'font-size="14" font-weight="bold" fill="#111111">Odontograma FDI</text>'
    )

    # Empty-state note (below title if no data)
    if is_empty:
        parts.append(
            f'<text x="{SVG_WIDTH / 2:.1f}" y="{title_y + 16}" '
            f'text-anchor="middle" font-family="Arial, sans-serif" '
            f'font-size="10" fill="#999999" font-style="italic">'
            f'Sin datos de odontograma registrados</text>'
        )

    # ---------------------------------------------------------------------------
    # Upper jaw
    # Upper-right quadrant (ids: 18..11) — left block
    # Upper-left quadrant  (ids: 21..28) — right block
    # Numbers above teeth (numbers_below=False)
    # ---------------------------------------------------------------------------
    upper_left_x  = jaw_x
    upper_right_x = jaw_x + q_width + DIVIDER_W   # after divider

    parts.append(
        _render_row(UPPER_RIGHT, teeth_map, upper_left_x,  upper_row_y, numbers_below=False)
    )
    parts.append(
        _render_row(UPPER_LEFT,  teeth_map, upper_right_x, upper_row_y, numbers_below=False)
    )

    # Midline vertical divider (upper jaw)
    div_x = jaw_x + q_width + DIVIDER_W / 2
    parts.append(
        f'<line x1="{div_x:.1f}" y1="{upper_row_y + 4}" '
        f'x2="{div_x:.1f}" y2="{upper_row_y + row_h - 4}" '
        f'stroke="#cccccc" stroke-width="1" stroke-dasharray="3,2"/>'
    )

    # ---------------------------------------------------------------------------
    # Horizontal jaw separator
    # ---------------------------------------------------------------------------
    sep_x1 = jaw_x
    sep_x2 = jaw_x + jaw_w
    parts.append(
        f'<line x1="{sep_x1:.1f}" y1="{sep_y:.1f}" '
        f'x2="{sep_x2:.1f}" y2="{sep_y:.1f}" '
        f'stroke="#aaaaaa" stroke-width="2"/>'
    )
    # Upper/lower labels at separator
    parts.append(
        f'<text x="{jaw_x - 4:.1f}" y="{sep_y + 4:.1f}" '
        f'text-anchor="end" font-family="Arial, sans-serif" '
        f'font-size="8" fill="#888888">Superior</text>'
    )
    parts.append(
        f'<text x="{jaw_x - 4:.1f}" y="{sep_y + 4 + 10:.1f}" '
        f'text-anchor="end" font-family="Arial, sans-serif" '
        f'font-size="8" fill="#888888">Inferior</text>'
    )

    # ---------------------------------------------------------------------------
    # Lower jaw
    # Lower-right quadrant (ids: 48..41) — left block
    # Lower-left quadrant  (ids: 31..38) — right block
    # Numbers below teeth (numbers_below=True)
    # ---------------------------------------------------------------------------
    lower_left_x  = jaw_x
    lower_right_x = jaw_x + q_width + DIVIDER_W

    parts.append(
        _render_row(LOWER_RIGHT, teeth_map, lower_left_x,  lower_row_y, numbers_below=True)
    )
    parts.append(
        _render_row(LOWER_LEFT,  teeth_map, lower_right_x, lower_row_y, numbers_below=True)
    )

    # Midline vertical divider (lower jaw)
    parts.append(
        f'<line x1="{div_x:.1f}" y1="{lower_row_y + 4}" '
        f'x2="{div_x:.1f}" y2="{lower_row_y + row_h - 4}" '
        f'stroke="#cccccc" stroke-width="1" stroke-dasharray="3,2"/>'
    )

    # ---------------------------------------------------------------------------
    # Legend section
    # ---------------------------------------------------------------------------
    parts.append(
        f'<text x="{legend_x:.1f}" y="{legend_title_y}" '
        f'font-family="Arial, sans-serif" font-size="10" font-weight="bold" '
        f'fill="#444444" letter-spacing="1">REFERENCIAS</text>'
    )
    parts.append(
        f'<line x1="{legend_x:.1f}" y1="{legend_title_y + 3}" '
        f'x2="{legend_x + jaw_w:.1f}" y2="{legend_title_y + 3}" '
        f'stroke="#dddddd" stroke-width="1"/>'
    )
    parts.append(legend_svg)

    # ---------------------------------------------------------------------------
    # Summary section
    # ---------------------------------------------------------------------------
    parts.append(
        f'<text x="{legend_x:.1f}" y="{summary_title_y}" '
        f'font-family="Arial, sans-serif" font-size="10" font-weight="bold" '
        f'fill="#444444" letter-spacing="1">RESUMEN</text>'
    )
    parts.append(
        f'<line x1="{legend_x:.1f}" y1="{summary_title_y + 3}" '
        f'x2="{legend_x + jaw_w:.1f}" y2="{summary_title_y + 3}" '
        f'stroke="#dddddd" stroke-width="1"/>'
    )

    line_y = summary_title_y + 18
    for text, is_detail in summary_lines:
        color = "#555555" if is_detail else "#222222"
        weight = "normal" if is_detail else "bold"
        size = "10" if is_detail else "11"
        parts.append(
            f'<text x="{legend_x + (16 if is_detail else 0):.1f}" y="{line_y}" '
            f'font-family="Arial, sans-serif" font-size="{size}" '
            f'font-weight="{weight}" fill="{color}">{text}</text>'
        )
        line_y += summary_line_h

    # Close SVG
    parts.append("</svg>")

    return "\n".join(parts)
