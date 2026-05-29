# Design: DLD-85 — Agent Option Confusion (Day number vs Option number)

## ADR-1: Dos líneas de defensa (Prompt + Código)

**Contexto:** El bug tiene dos causas raíz actuando en serie: (1) el LLM a veces pasa el texto del paciente como `date_time` en vez de `slot_index`, y (2) el fallback regex `r"(?:opci[oó]n\s*)?(\d)"` captura CUALQUIER dígito sin distinguir contexto.

**Decisión:** Atacar ambas. No es "o prompt o código" — es prompt **Y** código. Si el LLM aprende a pasar slot_index, el bug nunca llega al fallback. Si igual no lo hace, el fallback lo resuelve bien.

## ADR-2: Función dedicada `_match_option_number()` en el fallback

**Contexto:** El matching actual está inline en `book_appointment` (líneas 3240-3264), dentro de un bucle que itera `_offered` slots y aplica regex sin contexto.

**Decisión:** Extraer a función `_match_option_number(patient_text, offered_slots) -> Optional[int]` con esta jerarquía:

```
1. DÍA DE SEMANA (R1): si el texto contiene día de semana y SOLO 1 opción cae ese día
2. DÍA + NÚMERO (R2): si texto contiene día "N" y el day-of-month de UNA opción coincide
3. ORDINAL (R3): "el primero", "segundo", "opción N", o número SOLO sin contexto de fecha
4. HORA (R4): "el de las 10", match por hora exacta
5. NULL → parse_datetime fallback
```

El cambio clave: **antes de tocar el regex de opción numérica**, preguntar "esto tiene día de semana?" y resolver por día primero.

## ADR-3: NO reemplazar secciones enteras del prompt

**Contexto:** El design anterior proponía reemplazar `=== REGLA DE RESOLUCIÓN DE SLOT ===` entera. Eso pisa la regla existente.

**Decisión:** No pisar nada. Solo **agregar casos al final de cada sección**, manteniendo el texto original intacto.

## Diagrama de Flujo del Fallback

```
date_time del LLM (ej: "martes dos")
       │
       ▼
┌─────────────────────────────────┐
│  _match_option_number()         │
│                                 │
│  ¿Texto contiene día semana?    │
│  ├─ SI: matchear por día (R1)   │
│  │   └─ 1 match → return idx    │
│  │   └─ 2 matches → ver nº día  │
│  │       └─ 1 match → return    │
│  │       └─ 0 match → seguir    │
│  │                              │
│  ├─ ¿Texto ordinal/opción N?    │
│  │   └─ SI → match regex +      │
│  │       validar índice (R3)     │
│  │                              │
│  ├─ ¿Texto con hora? (R4)       │
│  │   └─ SI → match por hora     │
│  │                              │
│  └─ Sin match → return None     │
└──────────┬──────────────────────┘
           ▼
┌─────────────────────────────────┐
│  parse_datetime(date_time)       │
│  (fallback final)                │
└─────────────────────────────────┘
```

## Cambios Específicos en Código

### 1. `_match_option_number()` — NUEVA (antes de book_appointment, ~línea 2950)

```python
def _match_option_number(patient_text: str, offered_slots: list) -> Optional[int]:
    """
    Resuelve qué opción eligió el paciente según el texto.
    
    Jerarquía (first match wins):
    R1 - Día de semana: si texto contiene día y solo 1 opción cae ese día
    R2 - Día + número de día: día + "N" donde el nro del mes coincide
    R3 - Ordinal: "primero","segundo","opción N", o número SIN contexto fecha
    R4 - Hora: "el de las 10", hora exacta matchea
    
    Returns: 0-based index o None
    """
    text = patient_text.lower().strip()
    if not text or not offered_slots:
        return None
    
    days_es = {"lunes":0, "martes":1, "miércoles":2, "miercoles":2,
               "jueves":3, "viernes":4, "sábado":5, "sabado":5, "domingo":6}
    
    # R1 - Día de semana
    mentioned_days = [d for d in days_es if d in text]
    if mentioned_days:
        day_num = days_es[mentioned_days[0]]
        matching = [(i, s) for i, s in enumerate(offered_slots)
                    if s.get("date") and date.fromisoformat(s["date"]).weekday() == day_num]
        if len(matching) == 1:
            return matching[0][0]  # inequívoco
    
    # R2 - Día de semana + número de día
    if mentioned_days:
        day_num = days_es[mentioned_days[0]]
        day_match = re.search(r'(?:del?\s+)?(\d{1,2})\s*(?:de\s+\w+)?(?:\s|$|,|\.)', text)
        if day_match:
            target_day = int(day_match.group(1))
            matching = [(i, s) for i, s in enumerate(offered_slots)
                        if s.get("date")
                        and date.fromisoformat(s["date"]).weekday() == day_num
                        and date.fromisoformat(s["date"]).day == target_day]
            if len(matching) == 1:
                return matching[0][0]
    
    # R3 - Ordinal / opción N (SOLO cuando NO hay día de semana en el texto)
    ordinal_map = {"primero":0, "primer":0, "primera":0, "segundo":1, "segunda":1,
                   "tercero":2, "tercer":2, "tercera":2}
    for word, idx in ordinal_map.items():
        if word in text and idx < len(offered_slots):
            return idx
    
    opt_match = re.search(r'(?:opci[oó]n|option)\s*(\d+)', text)
    if opt_match:
        idx = int(opt_match.group(1)) - 1
        if 0 <= idx < len(offered_slots):
            return idx
    
    # Número solo (sin contexto de fecha, sin día de semana)
    if not mentioned_days and not re.search(r'\b(de|del|enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|octubre|noviembre|diciembre)\b', text):
        num_match = re.fullmatch(r'\s*(\d+)\s*', text)
        if num_match:
            idx = int(num_match.group(1)) - 1
            if 0 <= idx < len(offered_slots):
                return idx
    
    # R4 - Hora
    time_match = re.search(r'(?:las?\s+)?(\d{1,2})\s*(?:[:h](\d{2}))?(?:\s*hs?)?', text)
    if time_match:
        target_h = int(time_match.group(1))
        target_m = int(time_match.group(2)) if time_match.group(2) else 0
        for i, s in enumerate(offered_slots):
            st = s.get("time", "")
            if ":" in st:
                h, m = st.split(":")
                if int(h) == target_h and int(m) == target_m:
                    return i
    
    # Periodo (mañana/tarde) como desempate
    for i, s in enumerate(offered_slots):
        st = s.get("time", "")
        if ":" in st:
            h = int(st.split(":")[0])
            if "tarde" in text and h >= 12:
                return i
            if "mañana" in text and h < 12 and "tarde" not in text:
                return i
    
    return None
```

### 2. En `book_appointment` — reemplazar el bloque de fallback (líneas 3196-3266)

```python
# Reemplazar TODO el bloque de "Fallback: if no interpreted_date..."
# que va desde línea 3196 hasta línea 3266, con:
if apt_datetime is None:
    try:
        from services.conversation_state import get_state
        _conv_state = await get_state(tenant_id, chat_phone)
        _offered = _conv_state.get("last_offered_slots", [])
        if _offered and date_time:
            logger.info(f"📅 BOOK SLOT MATCH: attempting resolution | text={date_time!r} | offered={_offered}")
            _matched_idx = _match_option_number(date_time, _offered)
            if _matched_idx is not None:
                s = _offered[_matched_idx]
                base_date = date.fromisoformat(s["date"])
                h, m = int(s["time"].split(":")[0]), int(s["time"].split(":")[1])
                apt_datetime = datetime.combine(base_date, datetime.min.time()).replace(
                    hour=h, minute=m, second=0, microsecond=0, tzinfo=get_active_tz()
                )
                logger.info(f"📅 BOOK SLOT MATCH: rule=resolved | idx={_matched_idx} | slot={s['date']} {s['time']}")
            else:
                logger.info(f"📅 BOOK SLOT MATCH: no rule matched | text={date_time!r} | falling to parse_datetime")
    except Exception as _slot_err:
        logger.warning(f"📅 BOOK: slot match fallback failed: {_slot_err}")
```

### 3. En system prompt — SOLO agregar CASOS a las 3 secciones existentes

#### Sección 1: `=== REGLA DE RESOLUCIÓN DE SLOT ===` (líneas 9919-9923)
Agregar DESPUÉS del texto existente (no reemplazar):
```
ADEMÁS, cuando el paciente dice DÍA + NÚMERO (ej: "martes dos", "martes 2 de junio"):
- El número ES EL DÍA DEL MES, no el número de opción. No confundir.
- Si solo UNA opción cae en ese día de semana → seleccionarla.
- Si AMBAS caen en el mismo día → el número de día desambigua cuál fecha.
  Ej: 1️⃣ Martes 02/06 / 2️⃣ Martes 16/06 → "martes dos" → día 2 → Opción 1

ADEMÁS, cuando el paciente dice "el primero", "el segundo", "el de las 10", "el de la tarde":
- "primero"/"segundo" → número de opción
- "el de las X" / "el de la mañana/tarde" → resolver por hora
```

#### Sección 2: `REGLA INQUEBRANTABLE DE SELECCIÓN` (líneas 10069-10073)
Agregar al final:
```
ADEMÁS, si el paciente dice el DÍA DE LA SEMANA (ej: "martes", "el jueves") → 
resolvé usando la REGLA DE RESOLUCIÓN DE SLOT (ver arriba). 
ADEMÁS, si el paciente dice DÍA + NÚMERO (ej: "martes dos") → 
NO confundir con número de opción. El número ES el día del mes.
```

#### Sección 3: `REGLA DE SELECCIÓN DE TURNO` (líneas 10090-10097)
Agregar al final del listado de guiones:
```
- Si el paciente dice DÍA DE SEMANA (ej: "martes") y solo UNA opción cae ese día → usá slot_index de ESA opción. No confundir con número de opción.
- Si el paciente dice DÍA + NÚMERO (ej: "martes dos") → usá slot_index de la opción cuyo día de mes coincide. El número es el día, no la opción.
- Si el paciente dice "el de las X", "el de la mañana", "el de la tarde" → match por hora, usá slot_index de la opción que coincide.
```

## Logging

Agregar al inicio de `_match_option_number`:
```python
logger.debug(f"_match_option_number: text={patient_text!r} offered={offered_slots}")
```

## Archivos Afectados

| Archivo | Cambio |
|---------|--------|
| `orchestrator_service/main.py: ~2940` | Insertar función `_match_option_number()` |
| `orchestrator_service/main.py: 3196-3266` | Reemplazar fallback inline con `_match_option_number()` |
| `orchestrator_service/main.py: 9923` | Agregar 2 bloques "ADEMÁS" a REGLA DE RESOLUCIÓN DE SLOT |
| `orchestrator_service/main.py: 10073` | Agregar "ADEMÁS" a REGLA INQUEBRANTABLE DE SELECCIÓN |
| `orchestrator_service/main.py: 10097` | Agregar 3 guiones a REGLA DE SELECCIÓN DE TURNO |

## Testing

```python
test_cases = [
    # (text, opt1_date, opt1_time, opt2_date, opt2_time, expected_idx)
    # R1 - Día de semana inequívoco
    ("martes",     "2026-06-02","10:00", "2026-06-16","15:00", 0),  # 1 opción martes
    ("el martes",  "2026-06-01","10:00", "2026-06-16","15:00", None), # 0 martes
    # R2 - Día + número
    ("martes dos", "2026-06-02","10:00", "2026-06-16","15:00", 0),  # día 2
    ("martes 16",  "2026-06-02","10:00", "2026-06-16","15:00", 1),  # día 16
    ("martes 2 de junio","2026-06-02","10:00","2026-06-16","15:00",0),
    # R3 - Ordinal
    ("el primero", "2026-06-02","10:00", "2026-06-16","15:00", 0),
    ("segundo",    "2026-06-02","10:00", "2026-06-16","15:00", 1),
    ("opción 2",   "2026-06-02","10:00", "2026-06-16","15:00", 1),
    ("1",          "2026-06-02","10:00", "2026-06-16","15:00", 0),
    ("2",          "2026-06-02","10:00", "2026-06-16","15:00", 1),
    # R4 - Hora
    ("el de las 10","2026-06-02","10:00","2026-06-16","15:00", 0),
    ("a las 3 de la tarde","2026-06-02","10:00","2026-06-16","15:00", 1),
    ("el de la mañana","2026-06-02","10:00","2026-06-16","15:00", 0),
]
```

## Rollback

Revertir el commit en `main.py`. Cambios localizados en ~5 lugares, diff fácil de reversar.
