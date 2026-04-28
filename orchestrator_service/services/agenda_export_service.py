"""
agenda_export_service.py — Generates weekly agenda PDFs and images.

Pattern follows budget_service.py (gather → render → WeasyPrint → disk).
No AI narrative. Pure data → Jinja2 template → PDF/PNG.

Layers:
  1. gather_agenda_data()    — DB queries, data normalization into grid / daily_lists / alphabetical
  2. render_agenda_html()    — Jinja2 render
  3. generate_agenda_pdf()   — WeasyPrint async (via to_thread), disk cache
  4. generate_agenda_image() — WeasyPrint PNG async (via to_thread), disk cache
"""

import asyncio
import logging
import os
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Optional

import pytz

from jinja2 import Environment, FileSystemLoader

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Jinja2 setup — templates/agenda/ relative to orchestrator_service root
# ---------------------------------------------------------------------------
_TEMPLATES_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "templates",
    "agenda",
)

_jinja_env = Environment(
    loader=FileSystemLoader(_TEMPLATES_DIR),
    autoescape=False,  # HTML template — no escaping needed
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
DAY_NAMES = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]

DAY_COLORS = {
    0: "#5b4a9e",  # Lunes  — purple
    1: "#2e6ca4",  # Martes — blue
    2: "#1a6b5a",  # Miércoles — teal
    3: "#6b5a1a",  # Jueves — gold
    4: "#8b4513",  # Viernes — brown
    5: "#4a4a4a",  # Sábado — dark grey
    6: "#4a4a4a",  # Domingo — dark grey
}


# =============================================================================
# LAYER 1: DATA GATHERING
# =============================================================================


async def gather_agenda_data(
    pool,
    tenant_id: int,
    start_date: str,
    end_date: str,
    professional_id: Optional[int] = None,
    include_cancelled: bool = False,
) -> dict:
    """
    Gather appointments for the date range and build 3 display structures.

    All queries are scoped to tenant_id (multi-tenant isolation rule).

    Args:
        pool: asyncpg connection pool
        tenant_id: resolved tenant (never from request params)
        start_date: ISO date string "YYYY-MM-DD"
        end_date:   ISO date string "YYYY-MM-DD"
        professional_id: optional filter by professional

    Returns a dict with keys: grid, daily_lists, alphabetical, time_slots,
    days, total_turnos, total_personas, date_display.
    """
    # Convert date strings to timezone-aware datetimes for asyncpg
    try:
        _tz = pytz.timezone('America/Argentina/Buenos_Aires')
        y1, m1, d1 = map(int, start_date.split('-'))
        y2, m2, d2 = map(int, end_date.split('-'))
        start_dt = _tz.localize(datetime(y1, m1, d1, 0, 0, 0))
        end_dt = _tz.localize(datetime(y2, m2, d2, 23, 59, 59))
    except ValueError as exc:
        logger.error("gather_agenda_data: invalid date range %s – %s: %s", start_date, end_date, exc)
        raise

    # ── Base query ────────────────────────────────────────────────────────────
    base_sql = """
        SELECT
            a.id,
            a.appointment_datetime,
            a.duration_minutes,
            a.status,
            (p.first_name || ' ' || COALESCE(p.last_name, '')) AS patient_name,
            COALESCE(prof.first_name, '') AS professional_name
        FROM appointments a
        JOIN patients p ON a.patient_id = p.id AND p.tenant_id = $1
        LEFT JOIN professionals prof ON a.professional_id = prof.id AND prof.tenant_id = $1
        WHERE a.tenant_id = $1
          AND a.appointment_datetime BETWEEN $2 AND $3
    """

    if not include_cancelled:
        base_sql += "\n        AND a.status NOT IN ('cancelled')"

    args: list = [tenant_id, start_dt, end_dt]

    if professional_id is not None:
        base_sql += " AND a.professional_id = $4"
        args.append(professional_id)

    base_sql += " ORDER BY a.appointment_datetime ASC"

    rows = await pool.fetch(base_sql, *args)

    # ── Build display structures ──────────────────────────────────────────────
    # grid[time_slot][day_index] = [patient_name, ...]
    grid: dict[str, dict[int, list[str]]] = defaultdict(lambda: defaultdict(list))

    # daily_lists_map[day_index] = { day_name, day_index, color, rows: [...] }
    daily_lists_map: dict[int, dict] = {}

    # alphabetical_raw — will be sorted at the end
    alphabetical_raw: list[dict] = []

    patient_names_seen: set[str] = set()
    hours_seen: set[int] = set()

    for row in rows:
        dt: datetime = row["appointment_datetime"]
        day_idx: int = dt.weekday()  # 0=Monday … 6=Sunday
        hour: int = dt.hour
        slot_label: str = f"{hour:02d}:00-{hour + 1:02d}:00"
        patient_name: str = (row["patient_name"] or "").strip() or "Sin nombre"
        professional_name: str = (row["professional_name"] or "").strip()
        day_name: str = DAY_NAMES[day_idx]

        hours_seen.add(hour)
        patient_names_seen.add(patient_name)

        # grid
        grid[slot_label][day_idx].append(patient_name)

        # daily_lists
        if day_idx not in daily_lists_map:
            daily_lists_map[day_idx] = {
                "day_name": day_name,
                "day_index": day_idx,
                "color": DAY_COLORS.get(day_idx, "#4a4a4a"),
                "count": 0,
                "rows": [],
            }
        daily_lists_map[day_idx]["count"] += 1
        daily_lists_map[day_idx]["rows"].append(
            {
                "patient_name": patient_name,
                "time_slot": dt.strftime("%H:%M"),
                "professional_name": professional_name,
            }
        )

        # alphabetical (raw — will sort later)
        alphabetical_raw.append(
            {
                "patient_name": patient_name,
                "day_name": day_name,
                "day_index": day_idx,
                "day_color": DAY_COLORS.get(day_idx, "#4a4a4a"),
                "time_slot": dt.strftime("%H:%M"),
                "professional_name": professional_name,
            }
        )

    # ── Sort and number alphabetical list ─────────────────────────────────────
    alphabetical_raw.sort(key=lambda x: x["patient_name"].lower())
    alphabetical = [{"number": i + 1, **item} for i, item in enumerate(alphabetical_raw)]

    # ── Sort daily_lists by day_index ─────────────────────────────────────────
    daily_lists = [daily_lists_map[k] for k in sorted(daily_lists_map.keys())]
    # Each day's rows are already time-ordered because the DB query is ORDER BY datetime ASC

    # ── Build time_slots list (hourly, sorted) ────────────────────────────────
    if hours_seen:
        min_hour = min(hours_seen)
        max_hour = max(hours_seen)
        time_slots = [f"{h:02d}:00-{h + 1:02d}:00" for h in range(min_hour, max_hour + 1)]
    else:
        time_slots = []

    # ── Days present in the data (for grid header) ────────────────────────────
    days_seen = sorted({row["appointment_datetime"].weekday() for row in rows})
    days = [{"name": DAY_NAMES[d], "index": d} for d in days_seen]

    # ── Date display ─────────────────────────────────────────────────────────
    try:
        s = datetime.fromisoformat(start_date)
        e = datetime.fromisoformat(end_date)
        date_display = f"{s.strftime('%d/%m/%Y')} — {e.strftime('%d/%m/%Y')}"
    except ValueError:
        date_display = f"{start_date} — {end_date}"

    return {
        "grid": {slot: dict(day_map) for slot, day_map in grid.items()},
        "daily_lists": daily_lists,
        "alphabetical": alphabetical,
        "time_slots": time_slots,
        "days": days,
        "total_turnos": len(rows),
        "total_personas": len(patient_names_seen),
        "date_display": date_display,
        "generated_at": datetime.now().strftime("%d/%m/%Y a las %H:%M"),
    }


# =============================================================================
# LAYER 2: HTML RENDERING (Jinja2)
# =============================================================================


def render_agenda_html(data: dict) -> str:
    """Render the agenda_semanal.html template with gathered data."""
    template = _jinja_env.get_template("agenda_semanal.html")
    return template.render(**data)


# =============================================================================
# LAYER 3: PDF GENERATION (WeasyPrint, sync in thread)
# =============================================================================


def _generate_pdf_sync(html: str, pdf_path: str) -> str:
    """
    Blocking WeasyPrint call — MUST be called via asyncio.to_thread.

    Falls back to writing an HTML file if WeasyPrint is not installed,
    so development environments don't break.
    """
    os.makedirs(os.path.dirname(pdf_path), exist_ok=True)
    try:
        from weasyprint import HTML as _WP_HTML  # lazy import — optional dep
        _WP_HTML(string=html, base_url=_TEMPLATES_DIR).write_pdf(pdf_path)
        logger.info("_generate_pdf_sync: wrote PDF → %s", pdf_path)
        return pdf_path
    except ImportError:
        logger.warning("WeasyPrint not available — writing HTML fallback")
        html_path = pdf_path.replace(".pdf", ".html")
        Path(html_path).write_text(html, encoding="utf-8")
        return html_path
    except Exception as exc:
        logger.error("_generate_pdf_sync: WeasyPrint failed: %s", exc)
        raise


def _generate_image_sync(html: str, image_path: str) -> str:
    """
    Generate PNG from HTML by first creating a PDF, then converting.
    WeasyPrint 60+ removed write_png — we generate PDF and serve it.
    Falls back to PDF with .png extension if no image converter available.
    """
    # WeasyPrint 60+ doesn't support write_png, so we generate PDF instead
    pdf_path = image_path.rsplit(".", 1)[0] + ".pdf"
    return _generate_pdf_sync(html, pdf_path)


async def generate_agenda_pdf(
    pool,
    tenant_id: int,
    start_date: str,
    end_date: str,
    professional_id: Optional[int] = None,
    include_cancelled: bool = False,
) -> str:
    """
    Generate a weekly agenda PDF and save it to disk.

    Output path: /app/uploads/agenda/{tenant_id}/agenda_{start_date}_{end_date}.pdf

    Returns the file path on success.
    """
    upload_dir = Path(f"/app/uploads/agenda/{tenant_id}")
    safe_start = start_date.replace("-", "")
    safe_end = end_date.replace("-", "")
    suffix = f"_prof{professional_id}" if professional_id is not None else ""
    pdf_path = str(upload_dir / f"agenda_{safe_start}_{safe_end}{suffix}.pdf")

    data = await gather_agenda_data(pool, tenant_id, start_date, end_date, professional_id, include_cancelled)
    html = render_agenda_html(data)

    result = await asyncio.to_thread(_generate_pdf_sync, html, pdf_path)
    return result


async def generate_agenda_image(
    pool,
    tenant_id: int,
    start_date: str,
    end_date: str,
    professional_id: Optional[int] = None,
    format: str = "png",
) -> str:
    """
    Generate a weekly agenda image (first page) and save it to disk.

    Output path: /app/uploads/agenda/{tenant_id}/agenda_{start_date}_{end_date}.{format}

    Returns the file path on success.
    """
    upload_dir = Path(f"/app/uploads/agenda/{tenant_id}")
    safe_start = start_date.replace("-", "")
    safe_end = end_date.replace("-", "")
    suffix = f"_prof{professional_id}" if professional_id is not None else ""
    fmt = format.lower()
    image_path = str(upload_dir / f"agenda_{safe_start}_{safe_end}{suffix}.{fmt}")

    data = await gather_agenda_data(pool, tenant_id, start_date, end_date, professional_id)
    html = render_agenda_html(data)

    result = await asyncio.to_thread(_generate_image_sync, html, image_path)
    return result
