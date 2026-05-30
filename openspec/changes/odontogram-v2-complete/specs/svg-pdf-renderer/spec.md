# Spec: svg-pdf-renderer

**Change:** odontogram-v2-complete
**Spec ID:** SPEC-SPR
**Tipo:** Backend (Python)
**Prioridad:** P1
**Estado:** Borrador
**Fecha:** 2026-04-02
**Dependencias:** `state-catalog` (colores de impresión), `data-model-evolution` (formato v3.0), `dentition-tabs` (layout de piezas temporales)

---

## 1. Resumen

El renderizador SVG server-side (`orchestrator_service/services/odontogram_svg.py`) genera el odontograma embebido en los documentos clínicos PDF. Actualmente soporta 32 piezas permanentes con 10 estados y color único por diente. Esta spec extiende el renderizador para soportar:

1. **Coloreo por superficie individual** — cada una de las 5 superficies SVG de un diente se colorea con su propio estado del catálogo expandido (~40 estados).
2. **Sección de dentición temporal** — si el paciente tiene piezas temporales (FDI 51-85) con estado no-sano, se renderiza una segunda sección "Dentición Temporal" debajo de la permanente.
3. **Catálogo `PRINT_FILLS` expandido** — colores de alta legibilidad en papel blanco para los ~40 estados definidos en `state-catalog`.
4. **Leyenda dinámica** — solo muestra los estados que efectivamente aparecen en el odontograma del paciente.
5. **Resumen ampliado** — desglosado por dentición y por categoría (Preexistente vs. Lesión).
6. **Tabla de detalle con condición** — la columna "Condición" muestra Bueno/Malo/Indefinido junto a cada estado.
7. **Colores personalizados** — si una superficie tiene `color` HEX custom, ese color se usa en lugar del `printColor` por defecto del catálogo.
8. **Parser v3.0** — `normalize_odontogram_data` acepta el nuevo formato con secciones `permanent` / `deciduous`.
9. **Retrocompatibilidad** — datos v2.0 (solo dentición permanente, sin superficies) se renderizan idénticamente al comportamiento actual.
10. **Template HTML y servicio de registros digitales** actualizados para reflejar ambas secciones.

El renderizador sigue siendo 100% self-contained SVG (sin CSS externo, sin fuentes remotas) para garantizar fidelidad en cualquier renderer PDF (WeasyPrint, wkhtmltopdf, Puppeteer).

---

## 2. Requisitos Funcionales

### REQ-SPR-01 — Coloreo independiente por superficie
Cada path SVG dentro de un diente DEBE aplicar `fill` y `stroke` individuales según el estado de esa superficie. El modelo de datos v3.0 define `surfaces.buccal`, `.distal`, `.lingual`, `.mesial`, `.occlusal` con `state`, `condition` y `color` propios. El SVG DEBE reflejar este modelo con fidelidad.

### REQ-SPR-02 — Superficie sin estado propio hereda el estado global del diente
Si `surfaces[superficie]` es `null` o el campo `surfaces` está vacío (`{}`), esa superficie DEBE renderizarse con el `printColor` del `state` global del diente (`tooth.state`). Esto garantiza retrocompatibilidad con piezas que no tienen estados por superficie.

### REQ-SPR-03 — Líneas divisorias entre superficies más prominentes
Las 4 líneas `<line>` que dividen las superficies del diente (`stroke-width: 0.6` actual) DEBEN aumentar a `stroke-width: 0.8` para diferenciar superficies con colores distintos.

### REQ-SPR-04 — Overlay de símbolos whole-tooth
Para los estados que afectan el diente completo (`ausente`, `indicacion_extraccion`) el overlay visual (X roja, guión) DEBE seguir renderizándose sobre todas las superficies, independientemente de los colores individuales por superficie.

### REQ-SPR-05 — Sección de dentición temporal condicional
Si al menos una pieza de la dentición temporal tiene estado diferente de `"healthy"`, el SVG DEBE incluir una segunda sección de chart precedida de la cabecera **"Dentición Temporal"**. Si todas las piezas temporales son sanas (o no hay datos temporales), la sección se omite completamente.

### REQ-SPR-06 — Layout de dentición temporal
La sección temporal DEBE respetar el orden FDI de 4 cuadrantes con 5 piezas cada uno:
- Superior derecho: `[55, 54, 53, 52, 51]`
- Superior izquierdo: `[61, 62, 63, 64, 65]`
- Inferior derecho: `[85, 84, 83, 82, 81]`
- Inferior izquierdo: `[71, 72, 73, 74, 75]`

El tamaño de pieza es idéntico al permanente (38px). El ancho total de la fila es menor (5 piezas por cuadrante vs. 8), centrado dentro del mismo `SVG_WIDTH` (730px).

### REQ-SPR-07 — PRINT_FILLS expandido a ~40 estados
El dict `PRINT_FILLS` DEBE cubrir todos los IDs del catálogo definido en `state-catalog`. Los colores DEBEN ser los `printColor` definidos en esa spec (alta legibilidad sobre fondo blanco). Los estados legacy (`healthy`, `caries`, etc.) se mapean a sus equivalentes v2 manteniendo los colores actuales donde corresponda.

### REQ-SPR-08 — Colores personalizados por superficie
Si `surface.color` tiene un valor HEX (ej: `"#ff5733"`), el renderizador DEBE usar ese color directamente como `stroke` y `{hex}33` como `fill` (hex con 20% de opacidad), ignorando el `printColor` del catálogo para esa superficie. El símbolo del estado sigue usando el color del catálogo para mantenerse legible.

### REQ-SPR-09 — Leyenda dinámica
La leyenda DEBE mostrar únicamente los estados que están presentes en el odontograma renderizado (dentición permanente + temporal). Los estados `"healthy"` siempre se omiten de la leyenda. El orden de aparición en la leyenda es el definido en `STATE_ORDER` del catálogo.

### REQ-SPR-10 — Resumen desglosado
El bloque "RESUMEN" DEBE mostrar:
1. Total de piezas afectadas en dentición permanente: `N/32`
2. Total de piezas afectadas en dentición temporal (solo si hay sección temporal): `N/20`
3. Conteo por categoría: `Preexistente: N | Lesión: N`
4. Lista detallada de piezas (FDI + estado + condición) — solo piezas no sanas

### REQ-SPR-11 — Columna Condición en tabla de detalle
Cada fila de la lista de piezas afectadas DEBE incluir la condición de la superficie más relevante. Regla de prioridad: si el diente tiene una superficie con condición explícita, usar la primera encontrada en orden `occlusal → buccal → lingual → mesial → distal`. Si ninguna superficie tiene condición, usar la condición del diente global. Si no hay condición en ningún nivel, mostrar `—`.

Las condiciones se renderizan con texto de color:
- `bueno` → `#16a34a` (verde)
- `malo` → `#dc2626` (rojo)
- `indefinido` → `#9ca3af` (gris)

### REQ-SPR-12 — Parser v3.0 en `normalize_odontogram_data`
La función DEBE detectar el campo `"version": "3.0"` y extraer:
- `permanent.teeth` → lista de piezas permanentes
- `deciduous.teeth` → lista de piezas temporales
- `active_dentition` → se preserva en el dict normalizado

Si `version` es `"2.0"` o no existe, el comportamiento actual se mantiene intacto (retrocompatibilidad).

La función DEBE retornar un dict con clave `"format_version": "3.0"` y las secciones `"permanent"` y `"deciduous"` separadas.

### REQ-SPR-13 — Template HTML: sección temporal condicional
El template `odontogram_art.html` DEBE incluir un bloque condicional que renderice la sección "Dentición Temporal" si el contexto incluye `deciduous_svg` (string no vacío). La tabla de detalle DEBE mostrar la columna Condición y agrupar las piezas por dentición.

### REQ-SPR-14 — Servicio de registros digitales: pasar v3.0 correctamente
`gather_patient_data()` en `digital_records_service.py` DEBE pasar el dato completo v3.0 a `render_odontogram_svg()`. La función DEBE recibir el dict normalizado separado en permanente/temporal y ejecutar dos renders independientes: uno para cada sección. El contexto HTML resultante expone `odontogram_svg` (permanente) y `deciduous_svg` (temporal, vacío string si no aplica).

### REQ-SPR-15 — Retrocompatibilidad v2.0
Datos en formato v2.0 (dict plano `{teeth: [...]}` con estados de la lista original de 10) DEBEN renderizarse produciendo un SVG visualmente idéntico al actual. No se agrega sección temporal. La leyenda muestra solo los 10 estados originales si son los únicos presentes.

---

## 3. Detalle Técnico

### 3.1. Estructura del módulo refactorizado

```
odontogram_svg.py
├── Constantes (SURFACE_PATHS, LAYOUT, etc.)
├── PRINT_FILLS          # dict expandido a ~40 estados
├── STATE_SYMBOLS        # dict expandido
├── STATE_LABELS         # dict expandido
├── STATE_CATEGORIES     # dict: state_id -> 'preexistente' | 'lesion'
├── STATE_ORDER          # lista ordenada de todos los estados
├── normalize_odontogram_data(raw)    # v2 + v3 parser
├── _fdi_label(tooth_id)
├── _resolve_surface_fill(surface_data, tooth_state)
├── _fills(state, custom_color=None)
├── _render_tooth_group(...)          # refactorizado para per-surface
├── _render_row(...)                  # sin cambios de interfaz
├── _render_legend(states_present, ...)  # dinámica
├── _render_summary(...)              # ampliado
├── _render_chart_section(teeth_map, quadrants, title, ...)  # nuevo
├── render_odontogram_svg(odontogram_data)   # orquestador
```

### 3.2. PRINT_FILLS expandido

El dict `PRINT_FILLS` pasa de 10 a ~42 entradas. Cada clave corresponde a un `id` del catálogo de estados. Las entradas legacy (v1) se mantienen como alias apuntando a los valores del catálogo v2 para no romper datos existentes durante la transición.

```python
PRINT_FILLS = {
    # ── Healthy ────────────────────────────────────────────────────────────
    "healthy":                    {"fill": "#f5f5f5", "stroke": "#9ca3af"},

    # ── Preexistentes ──────────────────────────────────────────────────────
    "implante":                   {"fill": "#e0e7ff", "stroke": "#4338ca"},
    "radiografia":                {"fill": "#fef3c7", "stroke": "#d97706"},
    "restauracion_resina":        {"fill": "#dbeafe", "stroke": "#1d4ed8"},
    "restauracion_amalgama":      {"fill": "#e5e7eb", "stroke": "#374151"},
    "restauracion_temporal":      {"fill": "#ede9fe", "stroke": "#7c3aed"},
    "sellador_fisuras":           {"fill": "#d1fae5", "stroke": "#065f46"},
    "carilla":                    {"fill": "#fce7f3", "stroke": "#be185d"},
    "puente":                     {"fill": "#ede9fe", "stroke": "#6d28d9"},
    "corona_porcelana":           {"fill": "#fae8ff", "stroke": "#a21caf"},
    "corona_resina":              {"fill": "#f3e8ff", "stroke": "#7e22ce"},
    "corona_metalceramica":       {"fill": "#ede9fe", "stroke": "#5b21b6"},
    "corona_temporal":            {"fill": "#f5f3ff", "stroke": "#9333ea"},
    "incrustacion":               {"fill": "#fdf2f8", "stroke": "#db2777"},
    "onlay":                      {"fill": "#fdf4ff", "stroke": "#c026d3"},
    "poste":                      {"fill": "#f1f5f9", "stroke": "#475569"},
    "perno":                      {"fill": "#f8fafc", "stroke": "#334155"},
    "fibras_ribbond":             {"fill": "#fafaf9", "stroke": "#44403c"},
    "tratamiento_conducto":       {"fill": "#fff7ed", "stroke": "#c2410c"},
    "protesis_removible":         {"fill": "#f0fdf4", "stroke": "#166534"},
    "protesis_fija":              {"fill": "#ecfdf5", "stroke": "#065f46"},
    "ortodoncia":                 {"fill": "#eff6ff", "stroke": "#1d4ed8"},
    "ausente":                    {"fill": "#fafafa", "stroke": "#ced4da"},
    "indicacion_extraccion":      {"fill": "#f5f5f5", "stroke": "#adb5bd"},
    "treatment_planned":          {"fill": "#fef9c3", "stroke": "#ca8a04"},

    # ── Lesiones ───────────────────────────────────────────────────────────
    "caries":                     {"fill": "#fee2e2", "stroke": "#dc2626"},
    "caries_penetrante":          {"fill": "#fecaca", "stroke": "#b91c1c"},
    "caries_incipiente":          {"fill": "#fef2f2", "stroke": "#ef4444"},
    "caries_recurrente":          {"fill": "#ffe4e6", "stroke": "#e11d48"},
    "fractura":                   {"fill": "#fef3c7", "stroke": "#b45309"},
    "erosion":                    {"fill": "#fff7ed", "stroke": "#ea580c"},
    "abrasion":                   {"fill": "#fffbeb", "stroke": "#d97706"},
    "atricion":                   {"fill": "#fef9c3", "stroke": "#ca8a04"},
    "abfraccion":                 {"fill": "#fef08a", "stroke": "#a16207"},
    "hipoplasia":                 {"fill": "#e0f2fe", "stroke": "#0369a1"},
    "fluorosis":                  {"fill": "#f0fdf4", "stroke": "#15803d"},
    "mancha_blanca":              {"fill": "#f8fafc", "stroke": "#64748b"},
    "caries_radicular":           {"fill": "#fecaca", "stroke": "#991b1b"},
    "reabsorcion":                {"fill": "#fce7f3", "stroke": "#9d174d"},
    "necrosis":                   {"fill": "#1f2937", "stroke": "#111827"},  # negro para PDF
    "pulpitis":                   {"fill": "#fee2e2", "stroke": "#b91c1c"},
    "absceso":                    {"fill": "#ffe4e6", "stroke": "#9f1239"},

    # ── Aliases legacy (v1 → v2 mapping, compatibilidad con datos existentes) ──
    "restoration":    {"fill": "#dbeafe", "stroke": "#1d4ed8"},  # → restauracion_resina
    "root_canal":     {"fill": "#fff7ed", "stroke": "#c2410c"},  # → tratamiento_conducto
    "crown":          {"fill": "#fae8ff", "stroke": "#a21caf"},  # → corona_porcelana
    "implant":        {"fill": "#e0e7ff", "stroke": "#4338ca"},  # → implante
    "prosthesis":     {"fill": "#f0fdf4", "stroke": "#166534"},  # → protesis_removible
    "extraction":     {"fill": "#f5f5f5", "stroke": "#adb5bd"},  # → indicacion_extraccion
    "missing":        {"fill": "#fafafa", "stroke": "#ced4da"},  # → ausente
}
```

### 3.3. `_resolve_surface_fill(surface_data, tooth_state)`

```python
def _resolve_surface_fill(
    surface_data: dict | None,
    tooth_state: str,
    custom_color: str | None = None,
) -> dict:
    """
    Resuelve fill/stroke para UNA superficie.

    Prioridad:
    1. Si surface_data.color (HEX custom): fill = hex + "33", stroke = hex
    2. Si surface_data.state existente: usar PRINT_FILLS[surface_data.state]
    3. Fallback: usar PRINT_FILLS[tooth_state] (estado global del diente)
    4. Fallback final: PRINT_FILLS["healthy"]
    """
    if surface_data and surface_data.get("color"):
        hex_color = surface_data["color"]
        return {"fill": f"{hex_color}33", "stroke": hex_color}

    if surface_data and surface_data.get("state"):
        state = surface_data["state"]
    else:
        state = tooth_state

    return PRINT_FILLS.get(state, PRINT_FILLS["healthy"])
```

### 3.4. `_render_tooth_group` refactorizado

La firma se mantiene igual externamente para no romper `_render_row`. Se agrega el parámetro interno `surfaces_data`:

```python
def _render_tooth_group(
    tooth_id: int,
    state: str,
    tx: float,
    ty: float,
    numbers_below: bool,
    surfaces_data: dict | None = None,   # NUEVO: dict {surface_key: {state, condition, color}}
) -> str:
```

**Cambios internos:**

1. **Por cada path de superficie** (`top`/`right`/`bottom`/`left`): llamar a `_resolve_surface_fill(surfaces_data.get(surface_key), state)` donde el mapeo de surface key es:
   - `top` → `buccal`
   - `right` → `distal`
   - `bottom` → `lingual`
   - `left` → `mesial`

2. **Círculo oclusal**: `_resolve_surface_fill(surfaces_data.get("occlusal"), state)`

3. **Líneas divisorias**: `stroke-width` de `0.6` → `0.8` cuando hay colores de superficie diferentes entre sí (detectable comparando los fills de las 5 superficies).

4. **Overlays whole-tooth** (`ausente`, `indicacion_extraccion`, `extraction`, `missing`): se renderizan basándose en el `state` global del diente (no en superficies individuales), para no perder visibilidad del overlay cuando solo algunas superficies tienen ese estado.

5. **Colección de estados presentes**: cada llamada a `_render_tooth_group` retorna opcionalmente el set de estados encontrados para construcción de la leyenda dinámica (ver sección 3.6).

### 3.5. `_render_chart_section` (nueva función)

Encapsula el rendering de un bloque completo de chart (título + 2 filas de maxilares + separador):

```python
def _render_chart_section(
    teeth_map: dict,           # {tooth_id: {"state": str, "surfaces": dict}}
    upper_left_ids: list,      # cuadrante superior izquierdo en orden de render
    upper_right_ids: list,
    lower_left_ids: list,
    lower_right_ids: list,
    section_title: str,        # "Dentición Permanente" | "Dentición Temporal"
    y_offset: float,
    jaw_x: float,
    jaw_w: float,
) -> tuple[str, float, set]:   # (svg_parts_str, height_used, states_present_set)
```

Esta función reemplaza el código inline del render actual y permite llamarla dos veces: una para permanente y otra para temporal.

Para la dentición temporal, el ancho de fila es diferente (5 piezas × 38px + 4 × 2px = 198px por cuadrante, más el divider de 8px = 404px total), por lo que la función recalcula `jaw_w` internamente basándose en `len(upper_left_ids)`.

### 3.6. `_render_legend` dinámica

```python
def _render_legend(
    x: float,
    y: float,
    available_width: float,
    states_present: set,     # NUEVO: solo renderizar estos estados
) -> tuple[str, float]:
```

- Filtra `STATE_ORDER` para incluir solo los estados en `states_present`.
- Los estados `"healthy"` siempre se excluyen de la leyenda.
- Si `states_present` está vacío → retorna una línea de texto "Sin hallazgos registrados".
- El número de columnas de la leyenda se ajusta dinámicamente: si hay ≤ 5 estados, 5 columnas; si hay 6-10 estados, 5 columnas (2 filas); si hay > 10 estados, 5 columnas (N filas). `LEGEND_COLS = 5` se mantiene.

### 3.7. `_render_summary` ampliado

```python
def _render_summary(
    x: float,
    y: float,
    permanent_teeth_map: dict,
    deciduous_teeth_map: dict | None,
) -> tuple[str, float]:
```

**Bloque de salida:**

```
RESUMEN
───────────────────────────────────────────
Dentición Permanente: N/32 piezas afectadas
  Preexistente: N piezas
  Lesión: N piezas

Dentición Temporal: N/20 piezas afectadas     ← Solo si hay datos temporales
  Preexistente: N piezas
  Lesión: N piezas

Piezas afectadas:
  1.6  —  Caries (Oclusal)      [Malo]
  2.1  —  Corona porcelana      [Bueno]
  5.5  —  Caries incipiente     [—]
  ...
```

La columna de condición se muestra con el color apropiado (texto SVG con `fill` de color verde/rojo/gris).

La categoría de un estado se determina consultando `STATE_CATEGORIES[state_id]`. Para los aliases legacy, la categoría es la del estado destino.

### 3.8. `normalize_odontogram_data` v3.0

```python
def normalize_odontogram_data(raw) -> dict:
    """
    Retorna:
    {
        "format_version": "2.0" | "3.0",
        "teeth": [...],                    # solo para v2.0 (retrocompat)
        "permanent": {"teeth": [...]},     # solo para v3.0
        "deciduous": {"teeth": [...]},     # solo para v3.0
        "active_dentition": "permanent" | "deciduous",
        "affected_count": int,
    }
    """
```

**Lógica de detección de versión:**

1. Si `raw.get("version") == "3.0"` → parsear `permanent.teeth` y `deciduous.teeth`.
2. Si `raw.get("teeth")` es lista → v2.0, rellenar `permanent.teeth` con esa lista, `deciduous.teeth = []`.
3. Si es dict de keys numéricas → legacy, migrar a v2.0 (comportamiento actual).
4. Si None o inválido → estructura vacía v2.0.

**Construcción del `teeth_map` para render:**

```python
def _build_teeth_map(teeth_list: list) -> dict:
    """
    {tooth_id (int): {"state": str, "surfaces": dict[str, dict]}}
    """
    teeth_map = {}
    for t in teeth_list:
        tid = int(t.get("id"))
        teeth_map[tid] = {
            "state": t.get("state", "healthy"),
            "surfaces": t.get("surfaces", {}),
        }
    return teeth_map
```

### 3.9. Actualización del template HTML

**Archivo:** `orchestrator_service/templates/digital_records/odontogram_art.html`

Cambios:
1. Renombrar `odontogram_svg` → el template recibe `permanent_svg` y opcionalmente `deciduous_svg`.
2. Agregar bloque condicional Jinja2:
   ```html
   {{ permanent_svg | safe }}
   {% if deciduous_svg %}
   <div class="section-break"></div>
   {{ deciduous_svg | safe }}
   {% endif %}
   ```
3. La tabla de detalle de piezas afectadas (HTML, no SVG) DEBE incluir una columna "Condición" con colores semánticos.
4. La tabla DEBE agrupar las filas en dos secciones: "Dentición Permanente" y "Dentición Temporal" si aplica.

**Compatibilidad:** Si el contexto solo recibe `odontogram_svg` (llamadas legacy al template), el template DEBE seguir funcionando con un `{% if odontogram_svg %}` que sea el fallback.

### 3.10. Actualización de `digital_records_service.py`

En `gather_patient_data()`:
1. El dato de odontograma se normaliza con `normalize_odontogram_data()`.
2. Si `format_version == "3.0"`:
   - Renderizar `permanent_svg = render_chart_section(permanent_teeth_map, ...)`
   - Renderizar `deciduous_svg = render_chart_section(deciduous_teeth_map, ...)` solo si hay piezas temporales con estado no-sano.
3. Si `format_version == "2.0"`:
   - Renderizar `permanent_svg = render_odontogram_svg(data)` (comportamiento actual)
   - `deciduous_svg = ""`

En `assemble_html()`:
1. Pasar ambas variables `permanent_svg` y `deciduous_svg` al contexto del template.
2. Para retrocompatibilidad, también pasar `odontogram_svg = permanent_svg`.

### 3.11. Verificación del endpoint

El endpoint `POST /patients/{patient_id}/digital-records/generate` en `orchestrator_service/routes/digital_records.py` recibe el `patient_id` y delega a `digital_records_service`. No se requieren cambios en la firma del endpoint, solo verificar que el `odontogram_data` que se pasa a `gather_patient_data` es el raw JSONB sin deserialización previa (el servicio lo deserializa internamente con `normalize_odontogram_data`).

---

## 4. Escenarios

### Escenario 1 — Datos v2.0, sin superficies (retrocompatibilidad)
**Dado** que un paciente tiene `odontogram_data` en formato v2.0:
```json
{"teeth": [{"id": 36, "state": "caries", "surfaces": {}, "notes": ""}], "affected_count": 1, "format_version": "2.0"}
```
**Cuando** se genera el PDF del registro digital
**Entonces** el SVG muestra todas las superficies de la pieza 36 con el color de "caries" (rojo homogéneo)
**Y** NO se renderiza sección "Dentición Temporal"
**Y** la leyenda muestra solo el estado "caries"
**Y** el resumen dice "Dentición Permanente: 1/32 piezas afectadas"

### Escenario 2 — Datos v3.0, superficies mixtas en pieza permanente
**Dado** que la pieza 36 tiene:
```json
{
  "id": 36,
  "state": "healthy",
  "surfaces": {
    "occlusal": {"state": "caries", "condition": "malo", "color": null},
    "buccal":   {"state": "restauracion_resina", "condition": "bueno", "color": null},
    "distal":   null,
    "lingual":  null,
    "mesial":   null
  }
}
```
**Cuando** se renderiza el SVG
**Entonces** el círculo oclusal tiene fill `#fee2e2` y stroke `#dc2626` (color de caries)
**Y** el path superior (buccal) tiene fill `#dbeafe` y stroke `#1d4ed8` (color de restauracion_resina)
**Y** los paths distal, lingual, mesial heredan el estado global del diente ("healthy") y se renderizan en gris
**Y** las líneas divisorias tienen `stroke-width: 0.8` (superficies distintas detectadas)
**Y** la leyenda incluye "Caries" y "Restauración (Resina)" pero NO "Sano"

### Escenario 3 — Datos v3.0, dentición temporal presente
**Dado** que el paciente tiene formato v3.0 con:
- `permanent.teeth`: 32 piezas (2 con caries)
- `deciduous.teeth`: 20 piezas (3 con estados no-sanos: caries, sellador_fisuras)
**Cuando** se genera el SVG
**Entonces** la sección superior muestra el chart permanente con header "Dentición Permanente"
**Y** debajo aparece una segunda sección con header "Dentición Temporal"
**Y** la sección temporal muestra 4 filas de 5 piezas cada una (layout FDI 5x)
**Y** las 17 piezas temporales sanas se renderizan en gris
**Y** las 3 piezas temporales afectadas se renderizan con sus colores correctos
**Y** la leyenda es única y consolidada (union de estados de ambas secciones)
**Y** el resumen muestra ambos conteos separados

### Escenario 4 — Datos v3.0, dentición temporal toda sana
**Dado** que `deciduous.teeth` contiene 20 piezas todas con `state: "healthy"` y `surfaces: {}`
**Cuando** se genera el SVG
**Entonces** NO se renderiza la sección "Dentición Temporal"
**Y** el SVG es visualmente idéntico al de un dato v2.0 equivalente

### Escenario 5 — Odontograma vacío (sin datos)
**Dado** que `odontogram_data` es `None`
**Cuando** se llama a `render_odontogram_svg(None)`
**Entonces** el SVG muestra 32 piezas permanentes en estado "healthy"
**Y** la leyenda está vacía o muestra "Sin hallazgos registrados"
**Y** el resumen dice "Piezas afectadas: 0/32"

### Escenario 6 — Color personalizado en superficie
**Dado** que la superficie oclusal de la pieza 11 tiene `color: "#e67e22"`
**Cuando** se renderiza esa superficie
**Entonces** el fill del círculo oclusal es `"#e67e2233"` (color custom con 20% opacidad)
**Y** el stroke es `"#e67e22"` (color custom sólido)
**Y** el símbolo del estado en la leyenda sigue usando el color del catálogo (no el custom)

### Escenario 7 — Estado "ausente" con superficies mixtas
**Dado** que la pieza 21 tiene `state: "ausente"` y superficies con estados variados
**Cuando** se renderiza
**Entonces** el overlay de guión (missing dash) se renderiza sobre el diente completo
**Y** las superficies aún muestran sus colores individuales debajo del overlay
**Y** las superficies tienen `opacity: 0.35` (efecto de ausencia)

### Escenario 8 — Leyenda con muchos estados (> 10)
**Dado** que el odontograma tiene 15 estados distintos presentes
**Cuando** se calcula la leyenda dinámica
**Entonces** se renderizan 3 filas de 5 columnas (15 items)
**Y** el alto de la leyenda se calcula correctamente para que el SVG total no tenga cortes

### Escenario 9 — Condición en tabla de resumen
**Dado** que la pieza 36 tiene la superficie oclusal con `condition: "malo"`
**Cuando** se genera el bloque de resumen
**Entonces** la línea de la pieza 36 muestra `[Malo]` en color rojo (`fill="#dc2626"`)

### Escenario 10 — datos v3.0 con campo `permanent` ausente (datos corruptos)
**Dado** que `odontogram_data` tiene `version: "3.0"` pero le falta el campo `permanent`
**Cuando** `normalize_odontogram_data` procesa el dato
**Entonces** retorna una estructura v3.0 con `permanent.teeth = []` y `deciduous.teeth = []`
**Y** el render produce un SVG con 32 piezas sanas sin lanzar excepción

---

## 5. Criterios de Aceptación

| ID | Criterio | Verificación |
|----|----------|--------------|
| CA-SPR-01 | Diente con 5 superficies de estados distintos renderiza 5 colores distintos en el SVG | Inspeccion de atributos `fill`/`stroke` en SVG generado |
| CA-SPR-02 | Superficie sin dato propio hereda el color del `state` global del diente | Comparar output v2.0 con v3.0 equivalente |
| CA-SPR-03 | `ausente` e `indicacion_extraccion` muestran overlay (✕ o —) sobre las superficies | Buscar elemento `<line>` de overlay en SVG |
| CA-SPR-04 | Si hay piezas temporales no-sanas, el SVG incluye sección "Dentición Temporal" | `assert "Dentición Temporal" in svg` |
| CA-SPR-05 | Si todas las piezas temporales son sanas, NO se renderiza sección temporal | `assert "Dentición Temporal" not in svg` |
| CA-SPR-06 | Layout temporal: 5 piezas por cuadrante en orden FDI correcto | Verificar labels FDI en el SVG generado |
| CA-SPR-07 | `PRINT_FILLS` cubre los ~42 IDs del catálogo (sin KeyError en lookup normal) | Test unitario que itera todos los IDs del catálogo |
| CA-SPR-08 | Color personalizado HEX se aplica como fill semi-transparente y stroke sólido | Inspeccion de atributos con color custom |
| CA-SPR-09 | Leyenda dinámica no incluye estados ausentes del odontograma | Contar items de leyenda vs. estados presentes |
| CA-SPR-10 | Leyenda nunca incluye "Sano" / "healthy" | `assert "Sano" not in legend_svg` |
| CA-SPR-11 | Resumen muestra conteo separado por dentición cuando hay datos temporales | Verificar texto de resumen en SVG |
| CA-SPR-12 | Condición "malo" renderiza en color rojo, "bueno" en verde, sin condición en `—` | Inspeccion de atributo `fill` en texto de condición |
| CA-SPR-13 | `normalize_odontogram_data` con `version: "3.0"` retorna `permanent` y `deciduous` separados | Test unitario directo |
| CA-SPR-14 | `normalize_odontogram_data` con dato v2.0 retorna estructura compatible (retrocompat) | Test de regresión |
| CA-SPR-15 | `normalize_odontogram_data` con `None` retorna estructura vacía sin excepción | Test unitario |
| CA-SPR-16 | El template `odontogram_art.html` renderiza solo la sección temporal cuando `deciduous_svg` no es vacío | Test de renderización del template Jinja2 |
| CA-SPR-17 | La tabla HTML de detalle incluye columna "Condición" con colores semánticos | Inspección HTML del documento generado |
| CA-SPR-18 | El endpoint `POST /digital-records/generate` produce un PDF con ambas secciones cuando el paciente tiene datos temporales | Test de integración con datos v3.0 reales |
| CA-SPR-19 | SVG generado es válido (no contiene XML malformado) | `xml.etree.ElementTree.fromstring(svg)` sin excepción |
| CA-SPR-20 | Toda la lógica de renderizado es self-contained (sin CSS externo, sin fuentes remotas, sin imports de red) | Revisión manual del SVG generado |

---

## 6. Archivos Afectados

| Archivo | Tipo de cambio | Descripción |
|---------|---------------|-------------|
| `orchestrator_service/services/odontogram_svg.py` | Refactor mayor | `PRINT_FILLS` expandido, `_resolve_surface_fill`, `_render_tooth_group` per-surface, `_render_chart_section`, `_render_legend` dinámica, `_render_summary` ampliado, `normalize_odontogram_data` v3.0 |
| `orchestrator_service/templates/digital_records/odontogram_art.html` | Modificación | Bloque condicional `deciduous_svg`, columna Condición en tabla, agrupación por dentición |
| `orchestrator_service/services/digital_records_service.py` | Modificación | `gather_patient_data()` pasa datos v3.0 correctamente; `assemble_html()` expone `permanent_svg`, `deciduous_svg`, `odontogram_svg` |
| `orchestrator_service/routes/digital_records.py` | Verificación | Confirmar que el dato raw JSONB llega sin deserializar al servicio |

---

## 7. Dependencias

### Dependencias previas (deben estar completas antes de implementar esta spec)

| Spec | Razón |
|------|-------|
| `state-catalog` | Define los IDs y `printColor` de todos los estados del catálogo expandido. `PRINT_FILLS` en esta spec está directamente derivado de los `printColor` de ese catálogo. Sin el catálogo aprobado, los colores de impresión podrían cambiar. |
| `data-model-evolution` | Define el formato v3.0 con `permanent.teeth`, `deciduous.teeth`, y la estructura de `surfaces[key].{state, condition, color}`. `normalize_odontogram_data` y `_build_teeth_map` consumen ese formato. |
| `dentition-tabs` | Define los IDs y orden FDI de los cuadrantes de dentición temporal (`DECIDUOUS_UPPER_RIGHT`, etc.). El layout del chart temporal de esta spec replica ese orden. |

### Specs que dependen de esta

| Spec | Razón |
|------|-------|
| Ninguna en este change | Esta es la spec de salida (PDF generation). La cadena termina aquí dentro del change. |

### Dependencias técnicas (Python / infraestructura)

| Dependencia | Versión | Uso en esta spec |
|-------------|---------|-----------------|
| Python | 3.11+ | Type hints `dict | None` (union operator) |
| Jinja2 | 3.x | Template `odontogram_art.html` (ya en uso) |
| xml.etree.ElementTree (stdlib) | — | Validación SVG en tests |
| pytest | 7+ | Tests unitarios de `normalize_odontogram_data` y renders |
| `shared/odontogram_states.py` | (nuevo en `state-catalog`) | Lookup de `STATE_CATEGORIES` y `printColor` para construcción de `PRINT_FILLS` |

### Constraints de diseño

1. **Sin dependencias externas en el SVG** — El output SVG no puede referenciar fuentes, imágenes o CSS externos. Todo color, layout y tipografía se especifica inline.
2. **Ancho fijo 730px** — `SVG_WIDTH = 730` se mantiene para compatibilidad con templates A4 existentes.
3. **Altura dinámica** — El SVG crece verticalmente según la cantidad de piezas afectadas, estados en la leyenda, y presencia de sección temporal. El cálculo de `total_h` debe ser preciso para evitar recortes.
4. **Thread safety** — Las funciones son stateless (no estado global mutable). Seguro para uso concurrente en Uvicorn async workers.
5. **No requiere migración Alembic** — Todo el trabajo es en la capa de rendering. Los datos en JSONB no se modifican estructuralmente por esta spec.
