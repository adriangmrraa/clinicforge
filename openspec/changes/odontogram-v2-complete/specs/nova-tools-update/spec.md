# Spec: nova-tools-update

**Cambio:** odontogram-v2-complete
**Spec ID:** nova-tools-update
**Tipo:** Backend
**Prioridad:** P2
**Estado:** Draft
**Fecha:** 2026-04-02
**Dependencias:** `data-model-evolution`, `state-catalog`

---

## 1. Resumen

Las herramientas de Nova `ver_odontograma` y `modificar_odontograma` deben actualizarse para soportar el nuevo formato v3.0 del odontograma. Los cambios cubren cuatro ejes: (1) soporte de dentición temporal (FDI 51-85) con el nuevo parámetro `denticion`; (2) catálogo expandido de ~40 estados reemplazando los 10 actuales; (3) lectura y escritura del formato v3.0 con la estructura `permanent/deciduous`; (4) salida textual enriquecida que reporta estado, condición y color por cada superficie individual.

El objetivo es que Nova pueda ser el asistente de voz fiel al estado real del odontograma v3, sin que el profesional tenga que abrir la UI para consultar o editar hallazgos.

---

## 2. Requisitos Funcionales

### 2.1. Dentición temporal

**REQ-NT-001** — El parámetro `denticion` debe ser aceptado en ambos tools (`ver_odontograma` y `modificar_odontograma`). Es opcional con default `"permanente"`. Los valores válidos son `"permanente"` y `"temporal"`.

**REQ-NT-002** — Al llamar `ver_odontograma(patient_id, denticion="temporal")`, el output debe mostrar exclusivamente las piezas deciduas (FDI 51-85) organizadas en sus cuadrantes temporales (Q5-Q8 de la notación FDI).

**REQ-NT-003** — Al llamar `modificar_odontograma(patient_id, piezas=[...], denticion="temporal")`, los cambios deben escribirse en la sección `deciduous.teeth` del JSONB, sin tocar `permanent.teeth`.

**REQ-NT-004** — Si se pasa un FDI permanente (11-48) con `denticion="temporal"`, o un FDI temporal (51-85) con `denticion="permanente"`, la herramienta debe devolver un error claro indicando la inconsistencia antes de escribir nada.

**REQ-NT-005** — Si no existe sección `deciduous` en el odontograma almacenado (datos v2.0 o v3.0 solo con permanente), Nova debe construirla en memoria con los 20 dientes temporales en estado `"healthy"` antes de aplicar cambios, y persistirla como parte del v3.0.

### 2.2. Catálogo expandido de estados

**REQ-NT-006** — `_VALID_STATES` debe incluir los ~40 estados del catálogo expandido (24 Preexistentes + 16 Lesiones). Los 10 estados actuales deben mantenerse por retrocompatibilidad.

**REQ-NT-007** — `_STATUS_ES` debe contener las etiquetas en español de los ~40 estados. El mapeo debe ser exhaustivo; no debe caer en el fallback de mostrar el key en inglés para ningún estado del catálogo.

**REQ-NT-008** — El tool schema de `modificar_odontograma` debe exponer el enum completo de ~40 estados en `piezas[].estado` para que el LLM de OpenAI pueda seleccionar el valor correcto desde el prompt del usuario.

**REQ-NT-009** — La validación de `estado` en `_modificar_odontograma` debe rechazar cualquier valor fuera del catálogo expandido y retornar el listado completo de estados válidos como ayuda.

### 2.3. Expansión del modelo de superficies

**REQ-NT-010** — El schema de `piezas[].superficies` en `modificar_odontograma` debe pasar de string simple (`"healthy"/"caries"/"treated"`) a objetos con tres campos opcionales: `estado` (enum de ~40 estados), `condicion` (`"bueno"/"malo"/"indefinido"`), `color` (string HEX).

**REQ-NT-011** — Los tres campos de superficie son individualmente opcionales. Nova puede enviar solo `estado`, solo `condicion`, solo `color`, o cualquier combinación. Los campos no enviados no se sobreescriben (merge parcial).

**REQ-NT-012** — Al persistir las superficies, el formato escrito en JSONB debe ser el objeto `{state, condition, color}` de v3.0, no el string plano de v2.0. Si la superficie tenía formato string legacy (v2.0), se migra in-memory al leer antes de aplicar cambios.

### 2.4. Lectura y escritura del formato v3.0

**REQ-NT-013** — `_parse_odontogram_data` debe ser reemplazado (o extendido) por una función `_parse_odontogram_v3(odata, denticion)` que:
  - Detecta la versión del JSONB (`version` key o estructura)
  - Si v3.0: extrae `permanent.teeth` o `deciduous.teeth` según `denticion`
  - Si v2.0 (`teeth` array plano): lo trata como `permanent.teeth`, migra superficies string → objeto
  - Si legacy dict: lo convierte al formato array y lo trata como `permanent.teeth`
  - Retorna siempre una lista de `ToothData`-compatible dicts

**REQ-NT-014** — `_get_latest_odontogram` debe aceptar el parámetro `denticion` y delegarlo a `_parse_odontogram_v3`. Firma resultante: `_get_latest_odontogram(patient_id, tenant_id, denticion="permanente") → (record_id, full_odata_dict, teeth_array)`. Retorna el JSONB completo además del array de dientes, para que `_modificar_odontograma` pueda actualizar solo la sección correcta y re-persistir el JSONB íntegro.

**REQ-NT-015** — Al escribir, `_modificar_odontograma` debe construir el JSONB v3.0 completo con ambas secciones (`permanent` y `deciduous`) aunque solo modifique una. La sección no modificada se preserva intacta desde el JSONB leído previamente.

**REQ-NT-016** — El campo `version` del JSONB escrito debe ser siempre `"3.0"`. El campo `active_dentition` debe reflejar la última dentición modificada por Nova.

### 2.5. Output de ver_odontograma

**REQ-NT-017** — El header del output de `ver_odontograma` debe indicar el tipo de dentición consultada: `"Odontograma PERMANENTE de {nombre}"` o `"Odontograma TEMPORAL de {nombre}"`.

**REQ-NT-018** — Para cada pieza con hallazgos, las superficies afectadas (estado != "healthy") deben mostrarse con su estado en español, condición (si existe) y color (si existe). Formato por superficie: `oclusal=caries [malo, #ef4444]`.

**REQ-NT-019** — Si una pieza tiene estado global distinto de `"healthy"` pero ninguna superficie afectada, se muestra solo el estado global. Si tiene superficies afectadas, ambas se muestran (estado global + superficies).

**REQ-NT-020** — El resumen final debe indicar cuántas piezas sanas quedan del total correspondiente: 32 para permanente, 20 para temporal.

**REQ-NT-021** — Los nombres de cuadrante en la salida deben reflejar la dentición: para temporal, los cuadrantes son Q5 (superior derecho), Q6 (superior izquierdo), Q7 (inferior izquierdo), Q8 (inferior derecho) conforme a la notación FDI.

### 2.6. Validaciones FDI

**REQ-NT-022** — `_VALID_FDI_PERMANENTE` = set de los 32 dientes permanentes (11-18, 21-28, 31-38, 41-48).

**REQ-NT-023** — `_VALID_FDI_DECIDUA` = set de los 20 dientes temporales (51-55, 61-65, 71-75, 81-85).

**REQ-NT-024** — La validación en `_modificar_odontograma` debe usar el conjunto correcto según `denticion`. El mensaje de error debe especificar el rango FDI válido para la dentición indicada.

**REQ-NT-025** — `_FDI_NAMES_DECIDUOUS` debe incluir los 20 nombres en español de los dientes temporales, conforme al diccionario entregado en el briefing.

### 2.7. Retrocompatibilidad

**REQ-NT-026** — Los odontogramas existentes en formato v2.0 deben ser legibles y modificables sin pérdida de datos. El parser debe migrarlos in-memory a v3.0 antes de operar.

**REQ-NT-027** — Los datos v1 legacy (dict `{"37": {"status": "caries"}}`) deben seguir siendo parseables, tratados como `permanent.teeth`.

**REQ-NT-028** — Si el JSONB almacenado no tiene sección `deciduous` y se consulta con `denticion="temporal"`, Nova responde "Sin datos de dentición temporal registrados" (no error, no crash).

---

## 3. Detalle Técnico

### 3.1. Constantes actualizadas

#### `_FDI_NAMES` (permanente — sin cambios)

```python
_FDI_NAMES = {
    18: "3er molar sup-der", 17: "2do molar sup-der", 16: "1er molar sup-der",
    15: "2do premolar sup-der", 14: "1er premolar sup-der", 13: "canino sup-der",
    12: "incisivo lateral sup-der", 11: "incisivo central sup-der",
    21: "incisivo central sup-izq", 22: "incisivo lateral sup-izq",
    23: "canino sup-izq", 24: "1er premolar sup-izq", 25: "2do premolar sup-izq",
    26: "1er molar sup-izq", 27: "2do molar sup-izq", 28: "3er molar sup-izq",
    38: "3er molar inf-izq", 37: "2do molar inf-izq", 36: "1er molar inf-izq",
    35: "2do premolar inf-izq", 34: "1er premolar inf-izq", 33: "canino inf-izq",
    32: "incisivo lateral inf-izq", 31: "incisivo central inf-izq",
    41: "incisivo central inf-der", 42: "incisivo lateral inf-der",
    43: "canino inf-der", 44: "1er premolar inf-der", 45: "2do premolar inf-der",
    46: "1er molar inf-der", 47: "2do molar inf-der", 48: "3er molar inf-der",
}
```

#### `_FDI_NAMES_DECIDUOUS` (nuevo)

```python
_FDI_NAMES_DECIDUOUS = {
    55: "2do molar temporal sup-der", 54: "1er molar temporal sup-der",
    53: "canino temporal sup-der", 52: "incisivo lateral temporal sup-der",
    51: "incisivo central temporal sup-der",
    61: "incisivo central temporal sup-izq", 62: "incisivo lateral temporal sup-izq",
    63: "canino temporal sup-izq", 64: "1er molar temporal sup-izq",
    65: "2do molar temporal sup-izq",
    71: "incisivo central temporal inf-izq", 72: "incisivo lateral temporal inf-izq",
    73: "canino temporal inf-izq", 74: "1er molar temporal inf-izq",
    75: "2do molar temporal inf-izq",
    81: "incisivo central temporal inf-der", 82: "incisivo lateral temporal inf-der",
    83: "canino temporal inf-der", 84: "1er molar temporal inf-der",
    85: "2do molar temporal inf-der",
}
```

#### `_VALID_FDI_PERMANENTE` y `_VALID_FDI_DECIDUA` (reemplazan `_VALID_FDI`)

```python
_VALID_FDI_PERMANENTE = set(_FDI_NAMES.keys())      # {11..18, 21..28, 31..38, 41..48}
_VALID_FDI_DECIDUA    = set(_FDI_NAMES_DECIDUOUS.keys())  # {51..55, 61..65, 71..75, 81..85}
_VALID_FDI            = _VALID_FDI_PERMANENTE | _VALID_FDI_DECIDUA  # mantener para compat
```

#### `_STATUS_ES` expandido (~40 estados)

```python
_STATUS_ES = {
    # ── PREEXISTENTE (24) ──
    "healthy":                 "sano",
    "implant":                 "implante",
    "radiografia":             "radiografía",
    "restauracion_resina":     "restauración resina",
    "restauracion_amalgama":   "restauración amalgama",
    "restauracion_temporal":   "restauración temporal",
    "sellador_fisuras":        "sellador de fisuras",
    "carilla":                 "carilla",
    "puente":                  "puente",
    "corona_porcelana":        "corona porcelana",
    "corona_resina":           "corona resina",
    "corona_metalceramica":    "corona metalcerámica",
    "corona_temporal":         "corona temporal",
    "incrustacion":            "incrustación",
    "onlay":                   "onlay",
    "poste":                   "poste",
    "perno":                   "perno",
    "fibras_ribbond":          "fibras ribbond",
    "root_canal":              "tratamiento de conducto",
    "protesis_removible":      "prótesis removible",
    "diente_erupcion":         "diente en erupción",
    "diente_no_erupcionado":   "diente no erupcionado",
    "missing":                 "ausente",
    "otra_preexistencia":      "otra preexistencia",
    # ── LESIÓN (16) ──
    "mancha_blanca":           "mancha blanca",
    "surco_profundo":          "surco profundo",
    "caries":                  "caries",
    "caries_penetrante":       "caries penetrante",
    "necrosis_pulpar":         "necrosis pulpar",
    "proceso_apical":          "proceso apical",
    "fistula":                 "fístula",
    "indicacion_extraccion":   "indicación de extracción",
    "abrasion":                "abrasión",
    "abfraccion":              "abfracción",
    "atricion":                "atricción",
    "erosion":                 "erosión",
    "fractura_horizontal":     "fractura horizontal",
    "fractura_vertical":       "fractura vertical",
    "movilidad":               "movilidad",
    "hipomineralizacion_mih":  "hipomineralización MIH",
    "otra_lesion":             "otra lesión",
    # ── RETROCOMPATIBILIDAD (alias de los 10 originales) ──
    "restoration":             "restauración",
    "extraction":              "extracción",
    "treatment_planned":       "planificado",
    "crown":                   "corona",
    "prosthesis":              "prótesis",
}
```

#### `_VALID_STATES` (derivado del mapa expandido)

```python
_VALID_STATES = set(_STATUS_ES.keys())
```

#### `_ALL_TEETH_DECIDUOUS` (nuevo)

```python
_ALL_TEETH_DECIDUOUS = [
    55, 54, 53, 52, 51,  # Q5 — superior derecho
    61, 62, 63, 64, 65,  # Q6 — superior izquierdo
    75, 74, 73, 72, 71,  # Q7 — inferior izquierdo (de derecha a izquierda en el chart)
    81, 82, 83, 84, 85,  # Q8 — inferior derecho
]
```

#### `_CONDITION_ES` (nuevo)

```python
_CONDITION_ES = {
    "bueno":     "bueno",
    "malo":      "malo",
    "indefinido": "indefinido",
}
_VALID_CONDITIONS = set(_CONDITION_ES.keys())
```

---

### 3.2. Funciones actualizadas

#### `_build_default_teeth_deciduous()` (nuevo)

```python
def _build_default_teeth_deciduous() -> list:
    """Build a full 20-tooth array for deciduous dentition (all healthy)."""
    return [{"id": t, "state": "healthy", "surfaces": {}, "notes": ""} for t in _ALL_TEETH_DECIDUOUS]
```

#### `_parse_surface_v3(surface_val)` (nuevo helper)

Normaliza el valor de una superficie a formato v3.0:

```python
def _parse_surface_v3(surface_val) -> dict:
    """
    Normaliza surface_val al formato v3.0: {state, condition, color}.
    - Si es string (v2.0): {"state": val, "condition": None, "color": None}
    - Si es dict: merge con defaults, asegurando las 3 keys
    - Si es None/falsy: {"state": "healthy", "condition": None, "color": None}
    """
    if isinstance(surface_val, str):
        return {"state": surface_val, "condition": None, "color": None}
    if isinstance(surface_val, dict):
        return {
            "state":     surface_val.get("state", "healthy"),
            "condition": surface_val.get("condition"),
            "color":     surface_val.get("color"),
        }
    return {"state": "healthy", "condition": None, "color": None}
```

#### `_parse_odontogram_v3(odata, denticion)` (reemplaza `_parse_odontogram_data`)

```python
def _parse_odontogram_v3(odata, denticion: str = "permanente") -> tuple[list, dict]:
    """
    Parse odontogram_data from DB.
    Returns: (teeth_array, full_odata_dict)

    - teeth_array: list of teeth for the requested denticion
    - full_odata_dict: full v3.0 dict (both sections) for safe re-writing

    Handles:
      - v3.0: {"version": "3.0", "permanent": {"teeth": [...]}, "deciduous": {"teeth": [...]}}
      - v2.0: {"version": "2.0", "teeth": [...]}  → treated as permanent.teeth
      - legacy dict: {"37": {"status": "caries"}, ...}  → treated as permanent.teeth
      - None / invalid → all healthy defaults
    """
    if isinstance(odata, str):
        try:
            odata = json.loads(odata)
        except Exception:
            odata = {}

    if not isinstance(odata, dict):
        odata = {}

    version = odata.get("version", "unknown")

    # ── V3.0 — native format ──────────────────────────────────────────────────
    if version == "3.0":
        full = odata  # already correct
        if denticion == "temporal":
            teeth = full.get("deciduous", {}).get("teeth") or []
            if not teeth:
                return [], full   # vacío — REQ-NT-028
        else:
            teeth = full.get("permanent", {}).get("teeth") or _build_default_teeth()
        return teeth, full

    # ── V2.0 — flat teeth array → treat as permanent ─────────────────────────
    if "teeth" in odata and isinstance(odata["teeth"], list):
        perm_teeth = odata["teeth"]
        full = {
            "version": "3.0",
            "last_updated": odata.get("last_updated"),
            "active_dentition": "permanent",
            "permanent": {"teeth": perm_teeth},
            "deciduous": {"teeth": _build_default_teeth_deciduous()},
        }
        if denticion == "temporal":
            return [], full  # sin datos temporales en v2.0
        return perm_teeth, full

    # ── Legacy dict ───────────────────────────────────────────────────────────
    if odata:
        perm_teeth = _build_default_teeth()
        for tooth_key, tooth_data in odata.items():
            try:
                num = int(tooth_key)
            except ValueError:
                continue
            if not isinstance(tooth_data, dict):
                continue
            status = tooth_data.get("status", tooth_data.get("state", "healthy"))
            for i, t in enumerate(perm_teeth):
                if t["id"] == num:
                    perm_teeth[i]["state"] = status
                    if "surfaces" in tooth_data:
                        perm_teeth[i]["surfaces"] = tooth_data["surfaces"]
                    if "notes" in tooth_data:
                        perm_teeth[i]["notes"] = tooth_data["notes"]
                    break
        full = {
            "version": "3.0",
            "last_updated": None,
            "active_dentition": "permanent",
            "permanent": {"teeth": perm_teeth},
            "deciduous": {"teeth": _build_default_teeth_deciduous()},
        }
        if denticion == "temporal":
            return [], full
        return perm_teeth, full

    # ── Empty / null ──────────────────────────────────────────────────────────
    full = {
        "version": "3.0",
        "last_updated": None,
        "active_dentition": "permanent",
        "permanent": {"teeth": _build_default_teeth()},
        "deciduous": {"teeth": _build_default_teeth_deciduous()},
    }
    if denticion == "temporal":
        return _build_default_teeth_deciduous(), full
    return _build_default_teeth(), full
```

#### `_get_latest_odontogram` (firma actualizada)

```python
async def _get_latest_odontogram(
    patient_id: int, tenant_id: int, denticion: str = "permanente"
) -> tuple[uuid.UUID | None, list, dict]:
    """
    Returns (record_id, teeth_array, full_odata_dict).

    - record_id: None si no existe registro clínico
    - teeth_array: dientes de la dentición pedida
    - full_odata_dict: JSONB completo v3.0 (ambas secciones) para re-escritura segura
    """
    row = await db.pool.fetchrow(
        """
        SELECT id, odontogram_data
        FROM clinical_records
        WHERE patient_id = $1 AND tenant_id = $2
        ORDER BY record_date DESC, created_at DESC
        LIMIT 1
        """,
        patient_id, tenant_id,
    )
    if not row:
        teeth, full = _parse_odontogram_v3(None, denticion)
        return None, teeth, full

    teeth, full = _parse_odontogram_v3(row["odontogram_data"], denticion)
    return row["id"], teeth, full
```

#### `_ver_odontograma` (firma y lógica actualizada)

```python
async def _ver_odontograma(args: Dict, tenant_id: int, user_role: str) -> str:
    """Shows the full current odontogram for a patient (v3.0 format)."""
    if user_role not in ("ceo", "professional"):
        return _role_error("ver_odontograma", ["ceo", "professional"])

    pid = args.get("patient_id")
    denticion = args.get("denticion", "permanente").lower()

    if denticion not in ("permanente", "temporal"):
        return "El parámetro 'denticion' debe ser 'permanente' o 'temporal'."
    if not pid:
        return "Necesito el ID del paciente."

    patient = await db.pool.fetchrow(
        "SELECT first_name, last_name FROM patients WHERE id = $1 AND tenant_id = $2",
        int(pid), tenant_id,
    )
    if not patient:
        return "No encontré a ese paciente."

    record_id, teeth, _ = await _get_latest_odontogram(int(pid), tenant_id, denticion)
    name = f"{patient['first_name']} {patient['last_name'] or ''}".strip()

    # REQ-NT-028: sin datos de dentición temporal
    if denticion == "temporal" and not teeth:
        return f"Odontograma TEMPORAL de {name}: sin datos de dentición temporal registrados."

    modified = [t for t in teeth if t.get("state", "healthy") != "healthy"]

    label = "PERMANENTE" if denticion == "permanente" else "TEMPORAL"
    total = 32 if denticion == "permanente" else 20

    if not modified:
        return f"Odontograma {label} de {name}: todas las {total} piezas están sanas."

    lines = [f"Odontograma {label} de {name} ({len(modified)} pieza(s) con hallazgos):\n"]

    # Cuadrantes: permanente → 1,2,3,4 | temporal → 5,6,7,8
    if denticion == "permanente":
        quad_range = {1: [], 2: [], 3: [], 4: []}
        q_names = {
            1: "Superior Derecho (Q1)",
            2: "Superior Izquierdo (Q2)",
            3: "Inferior Izquierdo (Q3)",
            4: "Inferior Derecho (Q4)",
        }
        fdi_names_map = _FDI_NAMES
    else:
        quad_range = {5: [], 6: [], 7: [], 8: []}
        q_names = {
            5: "Superior Derecho Temporal (Q5)",
            6: "Superior Izquierdo Temporal (Q6)",
            7: "Inferior Izquierdo Temporal (Q7)",
            8: "Inferior Derecho Temporal (Q8)",
        }
        fdi_names_map = _FDI_NAMES_DECIDUOUS

    for t in teeth:
        state = t.get("state", "healthy")
        if state == "healthy":
            continue
        num = t.get("id", 0)
        q = num // 10
        if q not in quad_range:
            continue

        status_es = _STATUS_ES.get(state, state)
        fdi_name = fdi_names_map.get(num, f"pieza {num}")
        detail = f"  Pieza {num} ({fdi_name}): {status_es}"

        # Surfaces — formato v3.0
        surfaces = t.get("surfaces", {})
        if surfaces and isinstance(surfaces, dict):
            affected_parts = []
            for s_name, s_val in surfaces.items():
                sv = _parse_surface_v3(s_val)
                s_state = sv.get("state", "healthy")
                if s_state and s_state != "healthy":
                    s_label = _STATUS_ES.get(s_state, s_state)
                    extras = []
                    if sv.get("condition"):
                        extras.append(sv["condition"])
                    if sv.get("color"):
                        extras.append(sv["color"])
                    suffix = f" [{', '.join(extras)}]" if extras else ""
                    affected_parts.append(f"{s_name}={s_label}{suffix}")
            if affected_parts:
                detail += f" | Superficies: {', '.join(affected_parts)}"

        notes = t.get("notes", "")
        if notes:
            detail += f" — {notes}"

        quad_range[q].append(detail)

    for q in sorted(quad_range.keys()):
        if quad_range[q]:
            lines.append(f"{q_names[q]}:")
            lines.extend(quad_range[q])
            lines.append("")

    lines.append(f"Las {total - len(modified)} piezas restantes están sanas.")
    return "\n".join(lines)
```

#### `_modificar_odontograma` (lógica actualizada)

Cambios clave respecto a la versión actual:

1. Extrae `denticion = args.get("denticion", "permanente")` y valida contra `("permanente", "temporal")`.
2. Selecciona `_VALID_FDI_PERMANENTE` o `_VALID_FDI_DECIDUA` para validar FDI según dentición.
3. Detecta inconsistencia FDI/dentición (REQ-NT-004) antes de escribir.
4. Llama `_get_latest_odontogram(pid, tenant_id, denticion)` para obtener `(record_id, teeth_array, full_odata)`.
5. Al iterar piezas, aplica superficies con merge objeto-a-objeto (REQ-NT-011):
   ```python
   surfaces_input = pieza.get("superficies", {})
   if surfaces_input and isinstance(surfaces_input, dict):
       existing_surfaces = current_teeth[i].get("surfaces", {})
       if not isinstance(existing_surfaces, dict):
           existing_surfaces = {}
       for s_name, s_val in surfaces_input.items():
           en_name = surface_map.get(s_name.lower(), s_name.lower())
           existing_sv = _parse_surface_v3(existing_surfaces.get(en_name))
           # Merge parcial: solo sobreescribir campos enviados
           if isinstance(s_val, dict):
               if "estado" in s_val:
                   existing_sv["state"] = s_val["estado"]
               if "condicion" in s_val:
                   existing_sv["condition"] = s_val["condicion"]
               if "color" in s_val:
                   existing_sv["color"] = s_val["color"]
           elif isinstance(s_val, str):
               existing_sv["state"] = s_val
           existing_surfaces[en_name] = existing_sv
       current_teeth[i]["surfaces"] = existing_surfaces
   ```
6. Construye el JSONB v3.0 actualizando solo la sección correcta en `full_odata`:
   ```python
   section_key = "deciduous" if denticion == "temporal" else "permanent"
   full_odata[section_key]["teeth"] = current_teeth
   full_odata["version"] = "3.0"
   full_odata["last_updated"] = _dt.now().isoformat()
   full_odata["active_dentition"] = "deciduous" if denticion == "temporal" else "permanent"
   ```
7. Persiste `full_odata` (JSONB completo, no solo la sección).
8. `_FDI_NAMES.get` usa `_FDI_NAMES_DECIDUOUS` si `denticion == "temporal"` para el resumen.

---

### 3.3. Schemas de tools actualizados

#### `ver_odontograma` (schema JSON)

```python
{
    "type": "function",
    "name": "ver_odontograma",
    "description": (
        "Muestra el estado actual COMPLETO del odontograma de un paciente. "
        "Llamá SIEMPRE esta tool antes de modificar el odontograma. "
        "Muestra cada pieza con su estado global, superficies afectadas (con condición y color), "
        "organizado por cuadrante. Soporta dentición permanente (32 piezas FDI 11-48) "
        "y temporal/decidua (20 piezas FDI 51-85)."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "patient_id": {
                "type": "integer",
                "description": "ID del paciente"
            },
            "denticion": {
                "type": "string",
                "enum": ["permanente", "temporal"],
                "description": (
                    "Tipo de dentición a consultar. "
                    "'permanente' = adulto (FDI 11-48, default). "
                    "'temporal' = dentición de leche/decidua (FDI 51-85, niños)."
                ),
            },
        },
        "required": ["patient_id"],
    },
}
```

#### `modificar_odontograma` (schema JSON)

La descripción debe actualizarse para mencionar FDI 51-85 y el nuevo catálogo. El cuerpo de `piezas.items`:

```python
{
    "type": "object",
    "properties": {
        "numero": {
            "type": "integer",
            "description": (
                "Número FDI de la pieza. "
                "Permanente: 11-18 (sup-der), 21-28 (sup-izq), 31-38 (inf-izq), 41-48 (inf-der). "
                "Temporal: 51-55 (sup-der), 61-65 (sup-izq), 71-75 (inf-izq), 81-85 (inf-der). "
                "Siempre como entero sin punto."
            )
        },
        "estado": {
            "type": "string",
            "enum": [
                # Preexistente
                "healthy", "implant", "radiografia", "restauracion_resina",
                "restauracion_amalgama", "restauracion_temporal", "sellador_fisuras",
                "carilla", "puente", "corona_porcelana", "corona_resina",
                "corona_metalceramica", "corona_temporal", "incrustacion", "onlay",
                "poste", "perno", "fibras_ribbond", "root_canal", "protesis_removible",
                "diente_erupcion", "diente_no_erupcionado", "missing", "otra_preexistencia",
                # Lesión
                "mancha_blanca", "surco_profundo", "caries", "caries_penetrante",
                "necrosis_pulpar", "proceso_apical", "fistula", "indicacion_extraccion",
                "abrasion", "abfraccion", "atricion", "erosion", "fractura_horizontal",
                "fractura_vertical", "movilidad", "hipomineralizacion_mih", "otra_lesion",
                # Retrocompat
                "restoration", "extraction", "treatment_planned", "crown", "prosthesis",
            ],
            "description": "Estado global de la pieza. Ver catálogo completo."
        },
        "superficies": {
            "type": "object",
            "description": (
                "Superficies a modificar (opcional). Solo pasar las que cambian. "
                "Cada superficie acepta estado, condicion y/o color de forma independiente."
            ),
            "properties": {
                "oclusal":  _superficie_schema(),
                "mesial":   _superficie_schema(),
                "distal":   _superficie_schema(),
                "bucal":    _superficie_schema(),
                "lingual":  _superficie_schema(),
            },
        },
        "notas": {
            "type": "string",
            "description": "Nota clínica para esta pieza (opcional)"
        },
    },
    "required": ["numero", "estado"],
}
```

Donde `_superficie_schema()` es un helper que retorna:

```python
def _superficie_schema() -> dict:
    return {
        "type": "object",
        "description": "Estado individual de esta superficie",
        "properties": {
            "estado": {
                "type": "string",
                "enum": [/* misma lista de ~40 estados */],
                "description": "Estado de la superficie"
            },
            "condicion": {
                "type": "string",
                "enum": ["bueno", "malo", "indefinido"],
                "description": "Condición clínica de la superficie"
            },
            "color": {
                "type": "string",
                "description": "Color HEX para visualización (ej: '#ef4444')"
            },
        },
    }
```

El parámetro `denticion` se agrega al nivel de `modificar_odontograma`:

```python
"denticion": {
    "type": "string",
    "enum": ["permanente", "temporal"],
    "description": (
        "Tipo de dentición a modificar. "
        "'permanente' = adulto (FDI 11-48, default). "
        "'temporal' = dentición de leche (FDI 51-85)."
    ),
},
```

---

## 4. Escenarios

### Escenario 1: Consulta de dentición temporal (primer acceso)

```gherkin
Dado que un paciente pediátrico tiene odontograma en formato v2.0 (solo permanente)
Cuando Nova llama ver_odontograma(patient_id=42, denticion="temporal")
Entonces el parser detecta v2.0
Y construye sección deciduous con 20 dientes sanos en memoria
Y retorna "Odontograma TEMPORAL de [nombre]: sin datos de dentición temporal registrados."
Y NO crea ni modifica ningún registro clínico
```

### Escenario 2: Modificación de diente temporal con nuevo estado

```gherkin
Dado que un paciente tiene odontograma v3.0 con secciones permanent y deciduous
Cuando Nova llama modificar_odontograma(
    patient_id=42,
    piezas=[{"numero": 74, "estado": "caries"}],
    denticion="temporal"
)
Entonces el parser extrae deciduous.teeth
Y actualiza pieza 74 con estado "caries"
Y escribe el JSONB completo con version="3.0", permanent intacto, deciduous actualizado
Y el resumen dice "Pieza 74 (1er molar temporal inf-izq) → caries"
```

### Escenario 3: Modificación con superficies en v3.0

```gherkin
Dado que un paciente tiene pieza 16 con estado healthy y sin superficies
Cuando Nova llama modificar_odontograma con:
    piezas=[{
        "numero": 16,
        "estado": "restauracion_resina",
        "superficies": {
            "oclusal": {"estado": "restauracion_resina", "condicion": "bueno", "color": "#3b82f6"},
            "mesial":  {"estado": "caries", "condicion": "malo"}
        }
    }]
Entonces pieza 16 queda con estado="restauracion_resina"
Y superficie oclusal = {state: "restauracion_resina", condition: "bueno", color: "#3b82f6"}
Y superficie mesial = {state: "caries", condition: "malo", color: null}
Y las otras 3 superficies permanecen sin cambios
```

### Escenario 4: Merge parcial de superficies

```gherkin
Dado que pieza 36 tiene superficie "oclusal": {state: "caries", condition: "malo", color: "#ef4444"}
Cuando Nova llama modificar_odontograma con:
    piezas=[{"numero": 36, "estado": "root_canal",
             "superficies": {"oclusal": {"condicion": "bueno"}}}]
Entonces estado global pasa a "root_canal"
Y superficie oclusal queda {state: "caries", condition: "bueno", color: "#ef4444"}
  -- solo se actualizó condicion, state y color se preservaron
```

### Escenario 5: FDI inconsistente con dentición

```gherkin
Dado que Nova intenta modificar pieza 74 (temporal) con denticion="permanente"
Cuando _modificar_odontograma valida las piezas
Entonces retorna error: "Pieza 74: número FDI inválido para dentición permanente. Rango válido: 11-48."
Y no escribe nada en la base de datos
```

### Escenario 6: Retrocompatibilidad con v2.0

```gherkin
Dado que clinical_records.odontogram_data contiene formato v2.0:
    {"version": "2.0", "teeth": [{id: 16, state: "caries", surfaces: {}, notes: ""}], ...}
Cuando Nova llama ver_odontograma(patient_id=X, denticion="permanente")
Entonces el parser detecta v2.0 por presencia de "teeth" array plano
Y migra in-memory a v3.0 tratando teeth como permanent.teeth
Y muestra correctamente "Pieza 16 (1er molar sup-der): caries"
Y NO modifica el registro en DB (solo lectura)
```

### Escenario 7: Retrocompatibilidad con datos legacy dict

```gherkin
Dado que odontogram_data contiene formato legacy:
    {"37": {"status": "caries"}, "46": {"status": "crown"}}
Cuando Nova llama ver_odontograma(patient_id=X, denticion="permanente")
Entonces el parser migra el dict al array de 32 dientes
Y pieza 37 aparece como "caries" y pieza 46 como "corona"
Y las 30 piezas restantes aparecen como sanas
```

### Escenario 8: ver_odontograma con superficies en nuevo formato

```gherkin
Dado que pieza 16 tiene:
    state: "restauracion_resina"
    surfaces:
      occlusal: {state: "restauracion_resina", condition: "bueno", color: "#3b82f6"}
      mesial:   {state: "caries", condition: "malo", color: null}
Cuando Nova llama ver_odontograma(patient_id=X)
Entonces el output incluye:
    "Pieza 16 (1er molar sup-der): restauración resina | Superficies: occlusal=restauración resina [bueno, #3b82f6], mesial=caries [malo]"
```

### Escenario 9: Consulta simultánea de ambas denticiones

```gherkin
Dado que un paciente tiene hallazgos en dentición permanente Y temporal
Cuando Nova llama ver_odontograma(patient_id=X, denticion="permanente")
Entonces solo muestra las 32 piezas permanentes con sus hallazgos
Y cuando Nova llama ver_odontograma(patient_id=X, denticion="temporal")
Entonces solo muestra las 20 piezas temporales con sus hallazgos
```

### Escenario 10: Creación de registro clínico nuevo para dentición temporal

```gherkin
Dado que un paciente no tiene ningún clinical_record
Cuando Nova llama modificar_odontograma(patient_id=X, piezas=[...], denticion="temporal")
Entonces se crea un nuevo clinical_record con odontogram_data v3.0
Y la sección permanent tiene 32 dientes sanos
Y la sección deciduous tiene la pieza modificada + 19 dientes sanos
```

---

## 5. Criterios de Aceptación

**CA-NT-01** — `ver_odontograma` con `denticion="temporal"` retorna piezas FDI 51-85 organizadas en Q5-Q8 con nombres correctos en español (ej: "1er molar temporal inf-izq" para pieza 74).

**CA-NT-02** — `modificar_odontograma` con `denticion="temporal"` y pieza 74 escribe en `deciduous.teeth` sin modificar `permanent.teeth`. Verificable directamente en el JSONB de la DB.

**CA-NT-03** — Los ~40 estados del catálogo expandido son aceptados por `_VALID_STATES`. Un estado como `"restauracion_resina"` no es rechazado por la validación. Los 10 estados originales siguen siendo válidos.

**CA-NT-04** — `_STATUS_ES` cubre el 100% de los estados en `_VALID_STATES`. No debe existir ningún estado en `_VALID_STATES` sin traducción al español.

**CA-NT-05** — El merge parcial de superficies funciona: enviar solo `condicion` no sobreescribe `state` ni `color` de la superficie existente.

**CA-NT-06** — Datos en formato v2.0 son legibles sin error ni pérdida de información. Los tests con fixtures v2.0 pasan sin modificar el fixture.

**CA-NT-07** — Datos legacy dict son legibles sin error. Los tests con fixtures legacy pasan.

**CA-NT-08** — Inconsistencia FDI/dentición devuelve error antes de cualquier escritura en DB (ninguna query `UPDATE` ejecutada).

**CA-NT-09** — La salida de `ver_odontograma` incluye estado, condición y color de cada superficie afectada, en el formato `superficie=estado [condicion, color]`.

**CA-NT-10** — El schema JSON de los tools es válido según la especificación de OpenAI Realtime API (estructura plana `{type, name, description, parameters}`). Los 20 enums de `estado` en `piezas[].superficies[*].estado` son idénticos a los de `piezas[].estado`.

**CA-NT-11** — El JSONB escrito siempre tiene `version: "3.0"` y `active_dentition` refleja la dentición modificada.

**CA-NT-12** — `ver_odontograma` sin `denticion` funciona igual que antes (comportamiento por defecto = permanente). No hay regresiones.

---

## 6. Archivos Afectados

| Archivo | Tipo de cambio | Descripción |
|---------|---------------|-------------|
| `orchestrator_service/services/nova_tools.py` | Modificación | Constantes, helpers, tool definitions, `_ver_odontograma`, `_modificar_odontograma`, `_get_latest_odontogram`, `_parse_odontogram_v3` |

Solo un archivo afectado. Todos los cambios están contenidos en la sección H2 del archivo, con el bloque de constantes (~línea 3610) y las funciones (~línea 3640-3910).

---

## 7. Dependencias

### 7.1. Dependencias entrantes (deben estar completas antes de implementar esta spec)

| Spec | Qué provee | Por qué es bloqueante |
|------|-----------|----------------------|
| `data-model-evolution` | Formato v3.0 del JSONB (`permanent`/`deciduous`, `ToothSurface` con `state/condition/color`) | Los parsers de esta spec asumen la estructura v3.0 definida en esa spec |
| `state-catalog` | Catálogo completo de ~40 estados (`shared/odontogram_states.py`) | `_STATUS_ES` y `_VALID_STATES` deben ser un subconjunto consistente con ese catálogo |

### 7.2. Dependencias salientes (esta spec desbloquea)

Ninguna. `nova-tools-update` es una hoja en el grafo de dependencias: no hay specs que la requieran para comenzar.

### 7.3. Dependencias de runtime

| Dependencia | Versión | Uso |
|-------------|---------|-----|
| `asyncpg` | existente | Queries a `clinical_records` |
| `json` (stdlib) | — | Parse/serialización del JSONB |
| `uuid` (stdlib) | — | Generación de `record_id` para nuevos registros |
| Tabla `clinical_records` | Schema existente | `odontogram_data` es JSONB — sin cambios de schema |

### 7.4. NO requiere

- Migración Alembic (el JSONB evoluciona in-place).
- Cambios en otros servicios (BFF, WhatsApp, frontend).
- Nuevas dependencias Python.
- Cambios en `admin_routes.py` (los endpoints REST de odontograma son responsabilidad de `data-model-evolution`).
