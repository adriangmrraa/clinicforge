# Propuesta: odontogram-v2-complete

**Cambio:** Odontograma v2 Completo — Denticion dual, superficies individuales, catalogo expandido
**Fecha:** 2026-04-02
**Estado:** Propuesta
**Autor:** SDD Orchestrator

---

## 1. Intension (Intent)

El odontograma actual de ClinicForge (v1) soporta 32 piezas permanentes con 10 estados basicos y un modelo de interaccion donde las 5 superficies del diente se renderizan pero NO son clickeables individualmente. La Dra. Laura Delgado requiere una evolucion mayor para alcanzar paridad funcional con sistemas de referencia (SmileConnect) y cubrir las necesidades reales de un consultorio odontologico profesional.

La v2 introduce tres pilares fundamentales: (1) **denticion dual** — permanente (32 piezas FDI 11-48) y temporal/decidua (20 piezas FDI 51-85) con tabs de seleccion; (2) **superficies independientes** — cada una de las 5 areas SVG por diente es clickeable y puede tener su propio estado; (3) **catalogo expandido** — ~40 estados organizados en dos categorias (Preexistente y Lesion) con condicion (Bueno/Malo/Indefinido) y color personalizable por superficie. Todo esto con retrocompatibilidad total: los datos existentes siguen funcionando sin migracion destructiva.

---

## 2. Alcance (Scope)

### EN ALCANCE

| Area | Detalle |
|------|---------|
| **Frontend — Odontogram.tsx** | Refactorizar completamente el componente: tabs Permanente/Temporal, superficies clickeables, integracion con selector de simbolos |
| **Frontend — SymbolSelectorModal** | Nuevo componente: modal/drawer con buscador, grilla 2 columnas, badges de categoria, multi-select |
| **Frontend — StateConditionModal** | Nuevo componente: modal secundario con selector Estado (Bueno/Malo/Indefinido) + picker de color HEX |
| **Backend — Modelo de datos** | Evolucion de `ToothSurface` y `ToothData` en `shared/models_dental.py` para soportar ~40 estados, condicion, color, y tipo de denticion |
| **Backend — Migracion Alembic** | Nueva migracion 017 para evolucionar `clinical_records.odontogram_data` (retrocompatible con JSONB existente) |
| **Backend — API endpoints** | Adaptar PUT/GET `/admin/patients/{id}/records/{id}/odontogram` para nuevo formato v3 |
| **Nova Tools** | Actualizar `ver_odontograma` y `modificar_odontograma` para soportar denticion temporal y nuevos estados |
| **SVG PDF Renderer** | Extender `odontogram_svg.py` para renderizar denticion temporal, ~40 estados, y colores custom |
| **i18n** | Agregar ~80+ claves de traduccion (40 estados * 2 idiomas extra + UI elements) en es/en/fr |
| **WebSocket** | El evento `ODONTOGRAM_UPDATED` ya existe; solo necesita propagarse correctamente con el nuevo formato |

### FUERA DE ALCANCE

| Exclusion | Razon |
|-----------|-------|
| Historial de versiones del odontograma | Se abordara en un change separado (`document-versioning`) |
| Integracion con imagenes radiograficas superpuestas | Feature futura, no solicitada en screenshots de referencia |
| Exportacion directa a formatos de obras sociales (ART) | El PDF renderer existente ya cubre esto; solo se extiende |
| Impresion directa desde el navegador | Ya funciona con el SVG PDF renderer actual |
| Cambios en el modelo de `clinical_records` (columnas SQL) | La data vive en JSONB `odontogram_data`, no se agregan columnas |
| Odontograma mixto (mostrar permanente + temporal simultaneamente) | Solo tabs, no visualizacion simultanea |

---

## 3. Enfoque Tecnico (Approach)

### 3.1. Estructura de datos v3

El formato JSONB de `odontogram_data` evoluciona de v2.0 a v3.0 con retrocompatibilidad total:

```jsonc
{
  "version": "3.0",
  "last_updated": "2026-04-02T10:30:00Z",
  "active_dentition": "permanent", // "permanent" | "deciduous"
  "permanent": {
    "teeth": [
      {
        "id": 18,
        "state": "healthy",          // estado global del diente (para retrocompatibilidad)
        "surfaces": {
          "occlusal":  { "state": "caries", "condition": "malo", "color": "#ef4444" },
          "mesial":    { "state": "healthy", "condition": null, "color": null },
          "distal":    { "state": "restauracion_resina", "condition": "bueno", "color": "#3b82f6" },
          "buccal":    { "state": "healthy", "condition": null, "color": null },
          "lingual":   { "state": "healthy", "condition": null, "color": null }
        },
        "notes": ""
      }
      // ... 32 dientes
    ]
  },
  "deciduous": {
    "teeth": [
      {
        "id": 51,
        "state": "healthy",
        "surfaces": { /* misma estructura */ },
        "notes": ""
      }
      // ... 20 dientes
    ]
  }
}
```

**Retrocompatibilidad:** El parser (`normalize_odontogram_data` en `odontogram_svg.py` y `_parse_odontogram_data` en `nova_tools.py`) detecta la version:
- **v2.0** (`teeth` array plano) → se interpreta como `permanent.teeth`, surfaces se migran in-memory
- **v3.0** (nueva estructura) → uso directo
- **Legacy** (dict `{tooth_id: state}`) → ya migrado a v2.0, se cascadea a v3.0

### 3.2. Catalogo de estados

Se define un registro central de estados en un archivo compartido (`shared/odontogram_states.py` o constante en el componente React + espejo backend):

```
PREEXISTENTE (24 items):
  implante, radiografia, restauracion_resina, restauracion_amalgama,
  restauracion_temporal, sellador_fisuras, carilla, puente,
  corona_porcelana, corona_resina, corona_metalceramica, corona_temporal,
  incrustacion, onlay, poste, perno, fibras_ribbond,
  tratamiento_conducto, protesis_removible, diente_erupcion,
  diente_no_erupcionado, ausente, otra_preexistencia, healthy

LESION (16 items):
  mancha_blanca, surco_profundo, caries, caries_penetrante,
  necrosis_pulpar, proceso_apical, fistula, indicacion_extraccion,
  abrasion, abfraccion, atricion, erosion, fractura_horizontal,
  fractura_vertical, movilidad, hipomineralizacion_mih, otra_lesion
```

Cada estado tiene: `id`, `category` (preexistente|lesion), `label_key` (i18n), `default_color`, `icon_symbol`.

### 3.3. Flujo de interaccion UI

1. **Tab selection** — El usuario elige "Permanente" o "Temporal" con tabs animados sobre el chart
2. **Tooth click** — Selecciona la pieza (borde azul animado, igual que ahora)
3. **Surface click** — Click en una de las 5 areas SVG de la pieza seleccionada (highlight individual)
4. **Symbol Selector Modal** — Se abre con la lista completa de estados, buscador, y badges de categoria
5. **State Condition Modal** — Tras elegir estado, modal secundario con: Estado (Bueno/Malo/Indefinido) + Color picker
6. **Aplicar** — Se guarda la superficie con su estado, condicion y color; visual feedback inmediato

### 3.4. Migracion de datos

No se requiere migracion SQL destructiva. La migracion Alembic 017:
- Solo documenta el nuevo formato v3.0 en un comentario
- Opcionalmente agrega un indice GIN sobre `odontogram_data` si no existe (para queries futuras)
- La migracion real de datos es **on-read**: los parsers convierten v2.0 → v3.0 en memoria al leer
- Al guardar, siempre se escribe en formato v3.0

### 3.5. Arquitectura de componentes (Frontend)

```
Odontogram.tsx (refactored)
  ├── OdontogramTabs.tsx          — Permanente / Temporal tabs
  ├── DentitionChart.tsx          — Renderiza 32 o 20 dientes segun tab
  │   └── ToothSVG.tsx            — Pieza individual (ya existe, se extiende)
  │       └── SurfacePath.tsx     — Superficie clickeable individual (nuevo)
  ├── SymbolSelectorModal.tsx     — Modal de seleccion de estados (nuevo)
  ├── StateConditionModal.tsx     — Modal de condicion + color (nuevo)
  └── OdontogramLegend.tsx        — Leyenda expandida (refactored)
```

### 3.6. Estrategia de renderizado SVG (PDF)

El `odontogram_svg.py` se extiende para:
- Renderizar dos paginas/secciones: Permanente y Temporal (si tiene datos)
- Cada diente muestra colores por superficie (no color uniforme)
- La leyenda se expande para mostrar los estados usados (no los 40, solo los presentes)
- Se mantiene el esquema de colores para impresion (fondo blanco, alto contraste)

---

## 4. Riesgos

| # | Riesgo | Probabilidad | Impacto | Mitigacion |
|---|--------|-------------|---------|------------|
| R1 | **Retrocompatibilidad rota** — Datos existentes en v2.0 dejan de renderizar | Media | Critico | Parser con deteccion de version automatica + tests exhaustivos con data v1/v2/v3 |
| R2 | **Performance SVG con 40 estados** — El componente React se vuelve lento con muchos re-renders | Baja | Alto | Memoizacion agresiva (`React.memo`, `useMemo`), separacion de concerns por superficie |
| R3 | **UX sobrecarga** — 40 estados confunden al usuario, latencia percibida al abrir modales | Media | Alto | Buscador con fuzzy search en el modal, estados frecuentes arriba, animaciones de transicion |
| R4 | **Complejidad del PDF renderer** — Renderizar colores por superficie en SVG estatico es mas complejo | Media | Medio | Prototipar primero la pieza SVG individual con multi-color antes de escalar a 52 dientes |
| R5 | **Nova tools desactualizados** — Si no se actualizan, la IA da informacion incompleta | Baja | Alto | Incluir actualizacion de Nova tools como spec dedicada, no como afterthought |
| R6 | **Denticion temporal olvidada en parsers** — Se testea solo permanente, temporal tiene bugs | Media | Medio | Tests dedicados para decidua: 20 dientes, FDI 51-85, edge cases |
| R7 | **Mobile UX degradada** — Las superficies individuales son muy pequenas en movil | Alta | Medio | Zoom interactivo en la pieza seleccionada, o modal de superficie ampliada para mobile |

---

## 5. Desglose de Specs

Cada spec es una unidad logica de trabajo con sus propios criterios de aceptacion y puede implementarse y testearse independientemente (respetando el orden de dependencias).

### Grafo de dependencias

```
data-model-evolution ──────────┬──> dentition-tabs
                               ├──> surface-selection
                               ├──> state-catalog
                               ├──> nova-tools-update
                               └──> svg-pdf-renderer

state-catalog ─────────────────┬──> state-condition-color
                               └──> symbol-selector-modal

surface-selection + state-catalog ──> i18n-expansion

dentition-tabs + surface-selection + state-catalog +
state-condition-color + symbol-selector-modal ──> INTEGRATION (implícita)
```

---

### Spec 1: `data-model-evolution`
**Tipo:** Backend
**Prioridad:** P0 (bloqueante para todo lo demas)
**Descripcion:** Evolucionar el modelo de datos JSONB de odontograma de v2.0 a v3.0. Actualizar Pydantic DTOs en `shared/models_dental.py`. Crear migracion Alembic 017. Implementar parser retrocompatible que lee v1/v2/v3 y siempre escribe v3. Actualizar endpoints PUT/GET de odontograma en `admin_routes.py`.
**Archivos afectados:**
- `shared/models_dental.py` — `ToothSurface`, `ToothData`, nuevos modelos
- `orchestrator_service/admin_routes.py` — endpoints de odontograma
- `orchestrator_service/alembic/versions/017_*.py` — nueva migracion
- `orchestrator_service/services/odontogram_svg.py` — `normalize_odontogram_data`

---

### Spec 2: `dentition-tabs`
**Tipo:** Frontend
**Prioridad:** P1
**Dependencia:** `data-model-evolution`
**Descripcion:** Agregar tabs "Permanente" / "Temporal" sobre el chart del odontograma. Tab Permanente muestra 32 dientes FDI 11-48 (layout actual). Tab Temporal muestra 20 dientes FDI 51-85 con layout: superior (55-51 + 61-65), inferior (85-81 + 71-75). El primer tab usado se convierte en default pero siempre se puede cambiar. Cada denticion tiene su propio array de datos independiente.
**Archivos afectados:**
- `frontend_react/src/components/Odontogram.tsx` — refactoring mayor
- Nuevo: `frontend_react/src/components/odontogram/OdontogramTabs.tsx`
- Nuevo: `frontend_react/src/components/odontogram/DentitionChart.tsx`

---

### Spec 3: `surface-selection`
**Tipo:** Frontend
**Prioridad:** P1
**Dependencia:** `data-model-evolution`
**Descripcion:** Hacer que las 5 areas SVG por diente (vestibular/top, mesial/left, distal/right, lingual/bottom, oclusal/center) sean INDEPENDIENTEMENTE clickeables. Cada superficie puede tener su propio estado del catalogo expandido. Feedback visual: la superficie seleccionada se resalta; cada superficie muestra su color de estado. El click en una superficie abre el selector de simbolos para ESA superficie.
**Archivos afectados:**
- `frontend_react/src/components/Odontogram.tsx` — refactoring de `ToothSVG`
- Nuevo: `frontend_react/src/components/odontogram/SurfacePath.tsx`

---

### Spec 4: `state-catalog`
**Tipo:** Full-stack (shared)
**Prioridad:** P1
**Dependencia:** `data-model-evolution`
**Descripcion:** Definir el catalogo completo de ~40 estados en dos categorias (Preexistente ~24, Lesion ~16). Cada estado tiene: `id` (snake_case), `category`, `label_key` (i18n), `default_color` (HEX), `icon_symbol`. El catalogo se define en un archivo compartido importable tanto por frontend como backend. Reemplaza el enum actual de 10 estados.
**Archivos afectados:**
- Nuevo: `shared/odontogram_states.py` — catalogo Python (backend + SVG renderer)
- Nuevo: `frontend_react/src/constants/odontogramStates.ts` — catalogo TypeScript (frontend)
- `frontend_react/src/components/Odontogram.tsx` — reemplazar `STATE_FILLS`, `STATE_BTN`, etc.

---

### Spec 5: `state-condition-color`
**Tipo:** Frontend
**Prioridad:** P2
**Dependencia:** `state-catalog`
**Descripcion:** Despues de seleccionar un estado para una superficie, mostrar un modal secundario con: (1) Selector de condicion: Bueno / Malo / Indefinido (3 botones); (2) Picker de color HEX (input + paleta predefinida); (3) Botones Aplicar / Volver. El color y condicion se guardan en la estructura de superficie del diente.
**Archivos afectados:**
- Nuevo: `frontend_react/src/components/odontogram/StateConditionModal.tsx`
- `frontend_react/src/components/Odontogram.tsx` — integracion del modal

---

### Spec 6: `symbol-selector-modal`
**Tipo:** Frontend
**Prioridad:** P2
**Dependencia:** `state-catalog`
**Descripcion:** Modal/drawer con la lista completa de estados organizados por categoria. Incluye: barra de busqueda ("Buscar simbolo..."), layout grilla 2 columnas, cada item muestra icono + nombre + badge de categoria (azul para Preexistente, rojo para Lesion), scrollable, seleccion con checkbox para multi-select capability. Se abre al hacer click en una superficie o al querer cambiar el estado de un diente completo.
**Archivos afectados:**
- Nuevo: `frontend_react/src/components/odontogram/SymbolSelectorModal.tsx`
- `frontend_react/src/components/Odontogram.tsx` — integracion del modal

---

### Spec 7: `nova-tools-update`
**Tipo:** Backend
**Prioridad:** P2
**Dependencia:** `data-model-evolution`, `state-catalog`
**Descripcion:** Actualizar las herramientas de Nova `ver_odontograma` y `modificar_odontograma` para: (1) soportar parametro `denticion` (permanente/temporal); (2) reconocer los ~40 nuevos estados; (3) leer/escribir formato v3.0; (4) reportar estado por superficie en la salida textual; (5) manejar piezas temporales FDI 51-85. Actualizar la descripcion de los tools en el schema.
**Archivos afectados:**
- `orchestrator_service/services/nova_tools.py` — tools H2 + parser `_parse_odontogram_data`
- `orchestrator_service/services/nova_tools.py` — tool definitions (schema JSON)

---

### Spec 8: `svg-pdf-renderer`
**Tipo:** Backend
**Prioridad:** P2
**Dependencia:** `data-model-evolution`, `state-catalog`
**Descripcion:** Extender `odontogram_svg.py` para: (1) renderizar cada superficie con su color individual (no color uniforme por diente); (2) agregar seccion de denticion temporal si tiene datos (layout 20 dientes, 10+10); (3) expandir leyenda dinamica (solo muestra estados presentes en el chart); (4) soportar formato v3.0 en `normalize_odontogram_data`; (5) mantener retrocompatibilidad con v2.0.
**Archivos afectados:**
- `orchestrator_service/services/odontogram_svg.py` — refactoring completo del renderer

---

### Spec 9: `i18n-expansion`
**Tipo:** Frontend
**Prioridad:** P2
**Dependencia:** `state-catalog`, `surface-selection`
**Descripcion:** Agregar claves de traduccion para: (1) ~40 estados nuevos (es/en/fr); (2) categorias "Preexistente" y "Lesion"; (3) condiciones "Bueno", "Malo", "Indefinido"; (4) labels de UI: tabs, modal de selector, modal de condicion, buscador; (5) labels de superficies: "Oclusal", "Mesial", "Distal", "Vestibular", "Lingual". Estimado: ~100 claves nuevas por idioma.
**Archivos afectados:**
- `frontend_react/src/locales/es.json`
- `frontend_react/src/locales/en.json`
- `frontend_react/src/locales/fr.json`

---

## Orden de implementacion sugerido

| Fase | Specs | Justificacion |
|------|-------|---------------|
| **Fase 1** | `data-model-evolution` + `state-catalog` | Fundacion: sin esto, nada mas puede avanzar |
| **Fase 2** | `dentition-tabs` + `surface-selection` + `i18n-expansion` | Core UI: las interacciones principales |
| **Fase 3** | `symbol-selector-modal` + `state-condition-color` | UX completa: modales de seleccion |
| **Fase 4** | `nova-tools-update` + `svg-pdf-renderer` | Backend ecosystem: IA y exportacion |

---

## Metricas de exito

1. **Retrocompatibilidad**: Datos existentes de odontogramas v1/v2 se renderizan correctamente sin intervencion manual
2. **Paridad funcional**: Todas las 40 condiciones visibles en screenshots de SmileConnect estan disponibles
3. **Performance**: El componente React renderiza 32 dientes con superficies individuales sin lag perceptible (< 16ms frame time)
4. **Mobile**: Las superficies son accionables en pantallas >= 375px de ancho (iPhone SE como baseline)
5. **AI accuracy**: Nova puede reportar y modificar estados por superficie correctamente en el 100% de los casos
