# Spec General: Odontograma v2 Completo

**Cambio:** `odontogram-v2-complete`
**Fecha:** 2026-04-02
**Estado:** Spec
**Tipo:** Full-stack (Backend + Frontend + AI + PDF)
**Prioridad:** P0 (cambio estructural)

---

## 1. Resumen Ejecutivo

El odontograma actual (v2.0) soporta 32 piezas permanentes con 10 estados globales por diente. Las superficies se renderizan visualmente pero NO son clickeables individualmente: todo el diente comparte un unico estado.

La v2 Completa introduce **tres pilares fundamentales**:

| Pilar | Estado Actual | Estado Objetivo |
|-------|--------------|----------------|
| **Denticion** | Solo permanente (32 piezas FDI 11-48) | Dual: Permanente (32) + Temporal/Decidua (20 piezas FDI 51-85) con tabs |
| **Superficies** | 5 areas SVG renderizadas, pero con estado unico por diente | Cada superficie clickeable independiente con su propio estado, condicion y color |
| **Catalogo** | 10 estados basicos (`ToothStatus` enum) | ~40 estados (24 preexistentes + 16 lesiones) con condicion (Bueno/Malo/Indefinido) y color HEX |

Todo con **retrocompatibilidad total**: datos existentes en formato v1 (legacy dict) y v2.0 (teeth array) se auto-convierten a v3.0 sin migracion destructiva.

---

## 2. Specs Individuales y Dependencias

### 2.1 Tabla de specs

| # | Spec | Tipo | Prioridad | Depende de | Entregable principal |
|---|------|------|-----------|------------|---------------------|
| 1 | `data-model-evolution` | Backend | P0 | Ninguna | Formato JSONB v3.0, parser retrocompatible, Pydantic DTOs, Alembic 017 |
| 2 | `state-catalog` | Full-stack | P1 | 1 | Registro central de ~40 estados (Python + TypeScript), categorias, colores default |
| 3 | `dentition-tabs` | Frontend | P1 | 1 | Tabs Permanente/Temporal, layout de 20 dientes deciduos |
| 4 | `surface-selection` | Frontend | P1 | 1 | Superficies clickeables independientes, highlight individual, estado por superficie |
| 5 | `i18n-expansion` | Frontend | P2 | 2, 4 | ~100 claves nuevas por idioma (es/en/fr): estados, superficies, condiciones, UI |
| 6 | `symbol-selector-modal` | Frontend | P2 | 2 | Modal/drawer con grilla de estados, buscador, badges de categoria |
| 7 | `state-condition-color` | Frontend | P2 | 2 | Modal secundario: condicion (Bueno/Malo/Indefinido) + color picker HEX |
| 8 | `nova-tools-update` | Backend | P2 | 1, 2 | `ver_odontograma` y `modificar_odontograma` con denticion dual y estados v3.0 |
| 9 | `svg-pdf-renderer` | Backend | P2 | 1, 2 | SVG server-side con colores por superficie, seccion temporal, leyenda dinamica |

### 2.2 Grafo de dependencias

```
data-model-evolution (1) ──┬──> state-catalog (2) ──┬──> symbol-selector-modal (6)
                           |                        |
                           |                        ├──> state-condition-color (7)
                           |                        |
                           |                        ├──> i18n-expansion (5) <── surface-selection (4)
                           |                        |
                           |                        ├──> nova-tools-update (8)
                           |                        |
                           |                        └──> svg-pdf-renderer (9)
                           |
                           ├──> dentition-tabs (3)
                           |
                           └──> surface-selection (4) ──> i18n-expansion (5)
```

**Regla critica:** `data-model-evolution` es el unico bloqueante P0. Todo depende de el. `state-catalog` es el segundo nodo central del que dependen 5 specs.

### 2.3 Fases de implementacion

| Fase | Specs | Que entrega | Criterio de cierre |
|------|-------|------------|-------------------|
| **Fase 1 — Fundacion** | `data-model-evolution` + `state-catalog` | Formato v3.0 operativo, parser retrocompatible, catalogo de 40 estados | PUT/GET endpoints aceptan v3.0; datos v1/v2 se leen correctamente |
| **Fase 2 — Core UI** | `dentition-tabs` + `surface-selection` + `i18n-expansion` | Tabs Permanente/Temporal, superficies clickeables, traducciones | Usuario puede cambiar entre denticiones y seleccionar superficies individuales |
| **Fase 3 — UX Completa** | `symbol-selector-modal` + `state-condition-color` | Modales de seleccion con buscador, condicion y color | Flujo completo: superficie -> estado -> condicion -> color -> guardar |
| **Fase 4 — Ecosistema** | `nova-tools-update` + `svg-pdf-renderer` | IA reporta/modifica por superficie; PDF refleja colores individuales | Nova lee ambas denticiones; PDF muestra colores por superficie |

---

## 3. Modelo de Datos v3.0

### 3.1 Estructura JSONB

El campo `clinical_records.odontogram_data` (PostgreSQL JSONB) evoluciona de un array plano de dientes a una estructura con denticion dual y superficies detalladas:

```jsonc
{
  "version": "3.0",
  "last_updated": "2026-04-02T10:30:00Z",
  "active_dentition": "permanent",   // "permanent" | "deciduous"

  "permanent": {
    "teeth": [
      {
        "id": 18,                       // FDI: 11-48 (32 piezas)
        "state": "healthy",             // estado global (retrocompatibilidad)
        "surfaces": {
          "occlusal": { "state": "caries", "condition": "malo", "color": "#ef4444" },
          "mesial":   { "state": "healthy", "condition": null, "color": null },
          "distal":   { "state": "restauracion_resina", "condition": "bueno", "color": "#3b82f6" },
          "buccal":   { "state": "healthy", "condition": null, "color": null },
          "lingual":  { "state": "healthy", "condition": null, "color": null }
        },
        "notes": ""
      }
      // ... 32 dientes
    ]
  },

  "deciduous": {
    "teeth": [
      {
        "id": 51,                       // FDI: 51-85 (20 piezas)
        "state": "healthy",
        "surfaces": { /* misma estructura */ },
        "notes": ""
      }
      // ... 20 dientes
    ]
  }
}
```

### 3.2 Superficie individual

Cada superficie tiene tres campos:

| Campo | Tipo | Valores | Default |
|-------|------|---------|---------|
| `state` | `string` | Cualquiera del catalogo de ~40 estados | `"healthy"` |
| `condition` | `string \| null` | `"bueno"`, `"malo"`, `"indefinido"`, `null` | `null` |
| `color` | `string \| null` | HEX (`"#ef4444"`) o `null` (usa color default del estado) | `null` |

**Regla de color:** Si `color` es `null`, se usa el `default_color` del estado segun el catalogo. Si el usuario lo overridea, se guarda el HEX custom.

### 3.3 Superficies validas

| Nombre | Posicion SVG | Mapping anatomico |
|--------|-------------|-------------------|
| `occlusal` | Centro (circulo) | Superficie de mordida / incisal en anteriores |
| `mesial` | Izquierda (path `left`) | Hacia la linea media |
| `distal` | Derecha (path `right`) | Alejada de la linea media |
| `buccal` | Arriba (path `top`) | Vestibular / labial |
| `lingual` | Abajo (path `bottom`) | Palatino (superior) / lingual (inferior) |

### 3.4 Piezas FDI

**Permanentes (32):**

| Cuadrante | Piezas | Posicion |
|-----------|--------|----------|
| Superior derecho | 18, 17, 16, 15, 14, 13, 12, 11 | Fila superior, bloque izquierdo |
| Superior izquierdo | 21, 22, 23, 24, 25, 26, 27, 28 | Fila superior, bloque derecho |
| Inferior derecho | 48, 47, 46, 45, 44, 43, 42, 41 | Fila inferior, bloque izquierdo |
| Inferior izquierdo | 31, 32, 33, 34, 35, 36, 37, 38 | Fila inferior, bloque derecho |

**Deciduos/Temporales (20):**

| Cuadrante | Piezas | Posicion |
|-----------|--------|----------|
| Superior derecho | 55, 54, 53, 52, 51 | Fila superior, bloque izquierdo |
| Superior izquierdo | 61, 62, 63, 64, 65 | Fila superior, bloque derecho |
| Inferior derecho | 85, 84, 83, 82, 81 | Fila inferior, bloque izquierdo |
| Inferior izquierdo | 71, 72, 73, 74, 75 | Fila inferior, bloque derecho |

---

## 4. Catalogo de Estados

### 4.1 Preexistentes (24 estados)

| ID | Label (es) | Color Default | Simbolo |
|----|-----------|---------------|---------|
| `healthy` | Sano | `#e0e0e0` | `O` |
| `implante` | Implante | `#6366f1` | `Im` |
| `radiografia` | Radiografia | `#8b5cf6` | `Rx` |
| `restauracion_resina` | Restauracion resina | `#3b82f6` | `RR` |
| `restauracion_amalgama` | Restauracion amalgama | `#64748b` | `RA` |
| `restauracion_temporal` | Restauracion temporal | `#f59e0b` | `RT` |
| `sellador_fisuras` | Sellador de fisuras | `#06b6d4` | `SF` |
| `carilla` | Carilla | `#ec4899` | `Ca` |
| `puente` | Puente | `#8b5cf6` | `Pu` |
| `corona_porcelana` | Corona porcelana | `#a855f7` | `CP` |
| `corona_resina` | Corona resina | `#c084fc` | `CR` |
| `corona_metalceramica` | Corona metalceramica | `#7c3aed` | `CM` |
| `corona_temporal` | Corona temporal | `#d946ef` | `CT` |
| `incrustacion` | Incrustacion | `#14b8a6` | `In` |
| `onlay` | Onlay | `#0d9488` | `On` |
| `poste` | Poste | `#f97316` | `Po` |
| `perno` | Perno | `#ea580c` | `Pe` |
| `fibras_ribbond` | Fibras Ribbond | `#84cc16` | `FR` |
| `tratamiento_conducto` | Tratamiento de conducto | `#f97316` | `Tc` |
| `protesis_removible` | Protesis removible | `#14b8a6` | `Pr` |
| `diente_erupcion` | Diente en erupcion | `#22c55e` | `Ep` |
| `diente_no_erupcionado` | Diente no erupcionado | `#a3a3a3` | `NE` |
| `ausente` | Ausente | `#d4d4d4` | `--` |
| `otra_preexistencia` | Otra preexistencia | `#78716c` | `OP` |

### 4.2 Lesiones (16 estados)

| ID | Label (es) | Color Default | Simbolo |
|----|-----------|---------------|---------|
| `mancha_blanca` | Mancha blanca | `#fef3c7` | `MB` |
| `surco_profundo` | Surco profundo | `#fbbf24` | `SP` |
| `caries` | Caries | `#ef4444` | `C` |
| `caries_penetrante` | Caries penetrante | `#b91c1c` | `CP` |
| `necrosis_pulpar` | Necrosis pulpar | `#1e1e1e` | `NP` |
| `proceso_apical` | Proceso apical | `#dc2626` | `PA` |
| `fistula` | Fistula | `#f87171` | `Fi` |
| `indicacion_extraccion` | Indicacion extraccion | `#991b1b` | `IE` |
| `abrasion` | Abrasion | `#d97706` | `Ab` |
| `abfraccion` | Abfraccion | `#b45309` | `Af` |
| `atricion` | Atricion | `#92400e` | `At` |
| `erosion` | Erosion | `#a16207` | `Er` |
| `fractura_horizontal` | Fractura horizontal | `#7f1d1d` | `FH` |
| `fractura_vertical` | Fractura vertical | `#881337` | `FV` |
| `movilidad` | Movilidad | `#e11d48` | `Mv` |
| `hipomineralizacion_mih` | Hipomineralizacion MIH | `#fde68a` | `MIH` |
| `otra_lesion` | Otra lesion | `#9ca3af` | `OL` |

### 4.3 Condiciones

| Valor | Significado | Color indicador |
|-------|------------|----------------|
| `bueno` | Estado funcional, sin intervencion necesaria | Verde `#22c55e` |
| `malo` | Requiere atencion o reemplazo | Rojo `#ef4444` |
| `indefinido` | Pendiente de evaluacion | Amarillo `#eab308` |
| `null` | No aplica (ej. `healthy`, `ausente`) | Sin indicador |

---

## 5. Ciclo de Vida de los Datos (Data Flow v3.0)

### 5.1 Lectura

```
1. PatientDetail.tsx → GET /admin/patients/{id}/records
2. Backend lee clinical_records.odontogram_data (JSONB)
3. normalize_odontogram_data() detecta version:
   - v1 (legacy dict {tooth_id: state}) → parse a v3.0
   - v2.0 ({teeth: [...]})              → parse a v3.0
   - v3.0 ({version: "3.0", ...})       → uso directo
4. Respuesta JSON al frontend con formato v3.0
5. Odontogram.tsx parsea y renderiza segun active_dentition
```

### 5.2 Escritura

```
1. Usuario abre tab Permanente o Temporal
2. Click en superficie de un diente → highlight azul animado
3. Se abre SymbolSelectorModal → elige estado del catalogo
4. Se abre StateConditionModal → elige condicion + color (opcional)
5. Click "Aplicar" → actualiza estado local de la superficie
6. Click "Guardar" (boton principal) → PUT /admin/patients/{id}/records/{id}/odontogram
7. Backend valida y guarda como v3.0 en JSONB
8. Emite WebSocket ODONTOGRAM_UPDATED → otros clientes actualizan
```

### 5.3 Pipeline PDF (Digital Records)

```
1. digital_records_service.py → gather_patient_data()
2. Lee clinical_records.odontogram_data
3. normalize_odontogram_data() → v3.0
4. render_odontogram_svg() genera SVG con:
   - Seccion permanente (32 dientes, colores por superficie)
   - Seccion decidua (20 dientes, si tiene datos)
   - Leyenda dinamica (solo estados presentes)
5. SVG embebido en odontogram_art.html template
6. WeasyPrint → PDF
7. Disponible en tab "Documentos Digitales"
```

### 5.4 Nova AI

```
1. Profesional pide a Nova: "que tiene el paciente en la pieza 36?"
2. Nova llama ver_odontograma(pieza=36)
3. Tool lee clinical_records → normalize a v3.0
4. Responde con estado por superficie:
   "Pieza 3.6 (Permanente):
    - Oclusal: Caries (malo) #ef4444
    - Mesial: Sano
    - Distal: Restauracion resina (bueno)
    - Vestibular: Sano
    - Lingual: Sano"
```

---

## 6. Retrocompatibilidad

### 6.1 Matriz de conversion

| Input | Deteccion | Conversion |
|-------|-----------|-----------|
| `null` / vacio | `raw is None` | v3.0 con 32 dientes `healthy`, deciduos vacios |
| v1 (legacy dict `{"18": "caries"}`) | Todas las keys son digitos | Cada entry → `permanent.teeth[].state`, surfaces = 5x `healthy` |
| v2.0 (`{"teeth": [...], "format_version": "2.0"}`) | Tiene `teeth` como lista | `teeth` → `permanent.teeth`, superficies mapeadas si existen |
| v3.0 (`{"version": "3.0", ...}`) | Tiene `version: "3.0"` | Uso directo |
| v3.0 sin `deciduous` | `version: "3.0"` pero sin key `deciduous` | Se inicializa `deciduous.teeth` con 20 dientes `healthy` |
| Cliente viejo envia v2.0 | PUT recibe sin `version` | Auto-upgrade a v3.0, se guarda v3.0 |

### 6.2 Parser chain

```python
def normalize_odontogram_data(raw) -> dict:
    """
    Cadena de parseo: detecta version -> convierte -> retorna v3.0.
    SIEMPRE retorna formato v3.0 valido.
    NUNCA modifica la DB en lectura (conversion in-memory).
    Al guardar, SIEMPRE se persiste v3.0.
    """
```

### 6.3 Invariantes

1. **Lectura no-destructiva:** La conversion v1/v2 → v3.0 ocurre en memoria. El dato original en PostgreSQL no se toca hasta el proximo `PUT`.
2. **Escritura siempre v3.0:** Cualquier guardado escribe formato v3.0, sin importar que formato leyo.
3. **Sin datos perdidos:** Si v2.0 tenia `surfaces.buccal = "caries"`, en v3.0 se mapea a `surfaces.buccal.state = "caries"`.
4. **Estado global preservado:** `tooth.state` se mantiene para retrocompatibilidad con lecturas que no entienden superficies.

---

## 7. Puntos de Integracion Criticos

### 7.1 Digital Records (Tab "Documentos Digitales")

| Archivo | Rol | Cambio requerido |
|---------|-----|-----------------|
| `orchestrator_service/services/digital_records_service.py` | Recopila datos del paciente | `gather_patient_data()` debe pasar v3.0 al renderer |
| `orchestrator_service/services/odontogram_svg.py` | Genera SVG server-side | Refactoring completo: colores por superficie, seccion temporal |
| `orchestrator_service/templates/digital_records/odontogram_art.html` | Template HTML para embeber SVG | Ajustar si cambia la estructura del SVG insertado |

**Pipeline afectado:**
```
gather_patient_data() → render_odontogram_svg(v3.0) → odontogram_art.html → WeasyPrint → PDF
```

TODOS los cambios al modelo de datos y renderizado DEBEN reflejarse en esta pipeline. Un cambio en v3.0 que no se propague al SVG renderer genera PDFs incorrectos.

### 7.2 WebSocket

El evento `ODONTOGRAM_UPDATED` ya existe y sigue funcionando. El payload ahora es mas grande (contiene ambas denticiones) pero la estructura del evento no cambia:

```python
await sio.emit("ODONTOGRAM_UPDATED", {
    "patient_id": patient_id,
    "record_id": record_id,
    "odontogram_data": data_v3   # ahora incluye permanent + deciduous
}, room=f"tenant_{tenant_id}")
```

No se requiere nuevo evento ni cambio de protocolo.

### 7.3 Nova AI Tools

| Tool | Cambio |
|------|--------|
| `ver_odontograma` | Nuevo parametro `denticion` (permanent/deciduous). Reporta estado por superficie. Valida FDI 51-85 para deciduos. |
| `modificar_odontograma` | Nuevo parametro `denticion`. Acepta `superficie` (opcional). Reconoce los ~40 estados. Valida FDI segun denticion. |

**Regla de validacion FDI:**
- Permanentes: 11-18, 21-28, 31-38, 41-48
- Deciduos: 51-55, 61-65, 71-75, 81-85

### 7.4 Endpoints API

| Endpoint | Metodo | Cambio |
|----------|--------|--------|
| `GET /admin/patients/{id}/records` | GET | Sin cambio. Retorna `odontogram_data` como JSONB (ahora v3.0 o legacy). |
| `PUT /admin/patients/{id}/records/{id}/odontogram` | PUT | Acepta v2.0 o v3.0. Normaliza a v3.0 antes de guardar. |

El endpoint PUT ya acepta JSONB libre. La validacion se hace en el parser, no en el schema del endpoint.

---

## 8. Arquitectura de Componentes Frontend

### 8.1 Estructura de archivos (despues del cambio)

```
frontend_react/src/components/
  Odontogram.tsx                          # Componente principal (refactorizado)
  odontogram/
    OdontogramTabs.tsx                    # Tabs Permanente / Temporal
    DentitionChart.tsx                    # Renderiza 32 o 20 dientes segun tab activo
    ToothSVG.tsx                          # Pieza individual (extraido de Odontogram.tsx)
    SurfacePath.tsx                       # Superficie clickeable individual (nuevo)
    SymbolSelectorModal.tsx               # Modal selector de estados (nuevo)
    StateConditionModal.tsx               # Modal condicion + color (nuevo)
    OdontogramLegend.tsx                  # Leyenda dinamica (refactorizado)
  constants/
    odontogramStates.ts                   # Catalogo de estados TypeScript
```

### 8.2 Flujo de componentes

```
Odontogram.tsx
  |
  ├── OdontogramTabs.tsx ──── [Permanente] [Temporal]
  |                                 |
  ├── DentitionChart.tsx ─── renderiza 32 o 20 dientes
  |     |
  |     └── ToothSVG.tsx ─── pieza individual
  |           |
  |           └── SurfacePath.tsx ─── area SVG clickeable
  |                    |
  |                    └── onClick → abre SymbolSelectorModal
  |
  ├── SymbolSelectorModal.tsx ─── grilla de estados con buscador
  |     |
  |     └── onSelect → abre StateConditionModal
  |
  ├── StateConditionModal.tsx ─── Bueno/Malo/Indefinido + color picker
  |     |
  |     └── onApply → actualiza superficie en state local
  |
  └── OdontogramLegend.tsx ─── leyenda de estados presentes
```

### 8.3 Estado local (React)

```typescript
interface OdontogramState {
  version: "3.0";
  active_dentition: "permanent" | "deciduous";
  permanent: { teeth: ToothV3[] };
  deciduous: { teeth: ToothV3[] };
}

interface ToothV3 {
  id: number;
  state: string;          // estado global (retrocompat)
  surfaces: Record<SurfaceName, SurfaceData>;
  notes: string;
}

interface SurfaceData {
  state: string;           // ID del catalogo
  condition: "bueno" | "malo" | "indefinido" | null;
  color: string | null;    // HEX override o null para default
}

type SurfaceName = "occlusal" | "mesial" | "distal" | "buccal" | "lingual";
```

---

## 9. Catalogo Compartido (Frontend + Backend)

El catalogo de estados se define en DOS archivos espejo:

### 9.1 Backend: `shared/odontogram_states.py`

```python
ODONTOGRAM_STATES = {
    "caries": {
        "category": "lesion",
        "label_key": "odontogram.states.caries",
        "default_color": "#ef4444",
        "icon_symbol": "C",
    },
    # ... ~40 estados
}
```

Consumido por: `odontogram_svg.py`, `nova_tools.py`, `admin_routes.py` (validacion).

### 9.2 Frontend: `constants/odontogramStates.ts`

```typescript
export const ODONTOGRAM_STATES: Record<string, OdontogramStateEntry> = {
  caries: {
    category: "lesion",
    labelKey: "odontogram.states.caries",
    defaultColor: "#ef4444",
    iconSymbol: "C",
  },
  // ... ~40 estados
};
```

Consumido por: `Odontogram.tsx`, `SymbolSelectorModal.tsx`, `OdontogramLegend.tsx`.

**Regla de sincronizacion:** Ambos archivos DEBEN tener los mismos IDs y colores default. Cualquier adicion de estado se hace en ambos simultaneamente. El archivo Python es la fuente de verdad.

---

## 10. Migracion Alembic (017)

### Que hace

La migracion es **no-destructiva y minima**:

1. **NO** agrega columnas nuevas (los datos viven en JSONB `odontogram_data`).
2. **NO** modifica datos existentes (la conversion es on-read).
3. **Opcionalmente** agrega indice GIN sobre `odontogram_data` para queries futuras:
   ```sql
   CREATE INDEX IF NOT EXISTS idx_clinical_records_odontogram_gin
   ON clinical_records USING GIN (odontogram_data);
   ```
4. Documenta el formato v3.0 en el docstring de la migracion.

### Downgrade

```sql
DROP INDEX IF EXISTS idx_clinical_records_odontogram_gin;
```

No hay rollback de datos necesario: los datos v3.0 son compatibles con lecturas v2.0 (el campo `teeth` sigue existiendo dentro de `permanent.teeth` para parsers legacy).

---

## 11. Estrategia de Performance

### 11.1 React (Frontend)

| Tecnica | Donde | Por que |
|---------|-------|---------|
| `React.memo` | `ToothSVG`, `SurfacePath` | Solo re-renderiza si SU superficie cambia |
| `useMemo` | `DentitionChart` | Memoiza array de dientes filtrados |
| `useCallback` | Handlers de click | Evita re-renders en cascada |
| State granular | Superficie-level | Cambiar 1 superficie no re-renderiza las otras 4 del mismo diente |
| Lazy loading | `SymbolSelectorModal` | Solo carga cuando se abre (React.lazy) |

**Target:** < 16ms frame time con 32 dientes renderizados (60fps).

### 11.2 Mobile UX

| Problema | Solucion |
|----------|----------|
| Superficies muy pequenas en 375px | Zoom interactivo: al seleccionar diente, se muestra panel ampliado con las 5 superficies |
| Touch targets insuficientes | Superficie ampliada: minimo 44x44px en el panel de zoom |
| Scroll interference | `touch-action: manipulation` en el chart SVG |

### 11.3 SVG PDF (Backend)

| Tecnica | Donde |
|---------|-------|
| Leyenda dinamica | Solo estados presentes, no los 40 |
| Deciduos condicional | Solo renderiza seccion temporal si `deciduous.teeth` tiene datos no-healthy |
| Reutilizacion de paths | Los SVG paths se definen una vez y se referencian con `<use>` |

---

## 12. i18n (Internacionalizacion)

### 12.1 Claves nuevas estimadas

| Categoria | Cantidad | Ejemplo key |
|-----------|----------|-------------|
| Estados (~40) | 40 x 3 idiomas = 120 | `odontogram.states.caries` |
| Categorias (2) | 2 x 3 = 6 | `odontogram.categories.preexisting` |
| Condiciones (3) | 3 x 3 = 9 | `odontogram.conditions.good` |
| Superficies (5) | 5 x 3 = 15 | `odontogram.surfaces.occlusal` |
| UI labels (~10) | 10 x 3 = 30 | `odontogram.tabs.permanent`, `odontogram.search_placeholder` |
| **Total** | **~180 claves** (60 por idioma) | |

### 12.2 Archivos afectados

- `frontend_react/src/locales/es.json` — Fuente de verdad
- `frontend_react/src/locales/en.json`
- `frontend_react/src/locales/fr.json`

### 12.3 Namespace

Todas las claves bajo `odontogram.*`:

```json
{
  "odontogram": {
    "tabs": { "permanent": "Permanente", "deciduous": "Temporal" },
    "states": { "caries": "Caries", "implante": "Implante", ... },
    "categories": { "preexisting": "Preexistente", "lesion": "Lesion" },
    "conditions": { "good": "Bueno", "bad": "Malo", "undefined": "Indefinido" },
    "surfaces": { "occlusal": "Oclusal", "mesial": "Mesial", ... },
    "search_placeholder": "Buscar simbolo...",
    "apply": "Aplicar",
    "back": "Volver",
    "no_data": "Sin datos de odontograma registrados"
  }
}
```

---

## 13. Mitigacion de Riesgos

| # | Riesgo | Prob. | Impacto | Mitigacion | Spec responsable |
|---|--------|-------|---------|-----------|-----------------|
| R1 | Retrocompatibilidad rota — datos v1/v2 dejan de renderizar | Media | Critico | Parser chain con tests exhaustivos: fixtures v1, v2.0, v3.0, null, string JSONB | `data-model-evolution` |
| R2 | Performance React con 40 estados y superficies | Baja | Alto | `React.memo`, `useMemo`, re-render por superficie, no por diente completo | `surface-selection` |
| R3 | UX sobrecargada — 40 estados confunden al usuario | Media | Alto | Buscador fuzzy en modal, estados frecuentes primero, badges de categoria | `symbol-selector-modal` |
| R4 | PDF renderer — colores por superficie en SVG estatico | Media | Medio | Prototipar 1 diente multi-color antes de escalar a 52 | `svg-pdf-renderer` |
| R5 | Nova tools desactualizados post-cambio | Baja | Alto | Spec dedicada, no afterthought. Tests que validan lectura v3.0 | `nova-tools-update` |
| R6 | Denticion temporal olvidada en tests | Media | Medio | Tests dedicados: 20 dientes, FDI 51-85, edge cases deciduos | `data-model-evolution`, `dentition-tabs` |
| R7 | Mobile UX degradada — superficies muy chicas | Alta | Medio | Panel de zoom para pieza seleccionada, touch targets 44px min | `surface-selection` |
| R8 | Catalogos Python/TS desincronizados | Baja | Medio | CI check que compara IDs de ambos archivos, o generacion automatica | `state-catalog` |

---

## 14. Archivos Afectados (Mapa Completo)

### Backend

| Archivo | Tipo de cambio | Spec(s) |
|---------|---------------|---------|
| `shared/models_dental.py` | Modificar: nuevos Pydantic DTOs (v3.0) | 1 |
| `shared/odontogram_states.py` | **Nuevo:** catalogo Python de ~40 estados | 2 |
| `orchestrator_service/admin_routes.py` | Modificar: PUT/GET odontograma acepta v3.0 | 1 |
| `orchestrator_service/alembic/versions/017_*.py` | **Nuevo:** migracion (indice GIN opcional) | 1 |
| `orchestrator_service/services/odontogram_svg.py` | Refactoring mayor: superficies, temporal, leyenda | 9 |
| `orchestrator_service/services/nova_tools.py` | Modificar: tools H2, parser, schemas | 8 |
| `orchestrator_service/services/digital_records_service.py` | Verificar: pasa v3.0 correctamente al renderer | 9 |
| `orchestrator_service/templates/digital_records/odontogram_art.html` | Verificar: acepta SVG mas grande (temporal) | 9 |

### Frontend

| Archivo | Tipo de cambio | Spec(s) |
|---------|---------------|---------|
| `frontend_react/src/components/Odontogram.tsx` | Refactoring mayor: extraer componentes, tabs, superficies | 3, 4 |
| `frontend_react/src/components/odontogram/OdontogramTabs.tsx` | **Nuevo** | 3 |
| `frontend_react/src/components/odontogram/DentitionChart.tsx` | **Nuevo** | 3 |
| `frontend_react/src/components/odontogram/ToothSVG.tsx` | **Nuevo** (extraido de Odontogram.tsx) | 4 |
| `frontend_react/src/components/odontogram/SurfacePath.tsx` | **Nuevo** | 4 |
| `frontend_react/src/components/odontogram/SymbolSelectorModal.tsx` | **Nuevo** | 6 |
| `frontend_react/src/components/odontogram/StateConditionModal.tsx` | **Nuevo** | 7 |
| `frontend_react/src/components/odontogram/OdontogramLegend.tsx` | **Nuevo** (extraido + expandido) | 2, 5 |
| `frontend_react/src/constants/odontogramStates.ts` | **Nuevo** | 2 |
| `frontend_react/src/locales/es.json` | Modificar: ~60 claves nuevas | 5 |
| `frontend_react/src/locales/en.json` | Modificar: ~60 claves nuevas | 5 |
| `frontend_react/src/locales/fr.json` | Modificar: ~60 claves nuevas | 5 |

---

## 15. Criterios de Aceptacion Globales

### Retrocompatibilidad
- [ ] Odontogramas v1 (legacy dict) se renderizan sin perdida de datos
- [ ] Odontogramas v2.0 (teeth array) se renderizan sin perdida de datos
- [ ] Al guardar un v2.0, se persiste como v3.0
- [ ] Clientes viejos que envien v2.0 por PUT no rompen

### Funcionalidad Core
- [ ] Tab Permanente muestra 32 dientes FDI 11-48
- [ ] Tab Temporal muestra 20 dientes FDI 51-85
- [ ] Las 5 superficies de cada diente son clickeables individualmente
- [ ] Los ~40 estados del catalogo son seleccionables por superficie
- [ ] Condicion (Bueno/Malo/Indefinido) se asigna por superficie
- [ ] Color HEX customizable por superficie con default del catalogo
- [ ] Guardar persiste v3.0 con superficies independientes

### Performance
- [ ] React frame time < 16ms con 32 dientes renderizados
- [ ] Modales se abren en < 200ms
- [ ] El SVG PDF renderer genera en < 2s para ambas denticiones

### Mobile
- [ ] Superficies accionables en pantallas >= 375px
- [ ] Panel de zoom para pieza seleccionada en mobile
- [ ] Touch targets minimo 44x44px en panel ampliado

### PDF / Digital Records
- [ ] PDF refleja colores por superficie (no color uniforme)
- [ ] Seccion temporal aparece en PDF si tiene datos no-healthy
- [ ] Leyenda dinamica muestra solo estados presentes

### Nova AI
- [ ] `ver_odontograma` reporta estado por superficie
- [ ] `modificar_odontograma` acepta superficie especifica
- [ ] Ambos tools soportan denticion temporal (FDI 51-85)
- [ ] Validacion correcta de rango FDI por denticion

### i18n
- [ ] Los ~40 estados traducidos en es/en/fr
- [ ] Labels de UI (tabs, modales, condiciones, superficies) traducidos
- [ ] Namespace `odontogram.*` sin conflictos

---

## 16. Metricas de Exito

| Metrica | Target | Como se mide |
|---------|--------|-------------|
| Retrocompatibilidad | 100% de v1/v2 renderizan sin error | Tests automaticos con fixtures |
| Catalogo completo | 40 estados disponibles y seleccionables | Verificacion manual + test de integracion |
| Denticion temporal | 20 dientes funcionales con tab | Test E2E |
| PDF por superficie | Colores individuales en SVG generado | Visual regression + test unitario |
| Nova accuracy | 100% lectura/escritura por superficie | Tests unitarios de tools |
| Mobile usability | Superficies accionables en 375px+ | Test manual en iPhone SE viewport |
| Performance | < 16ms frame time, 32 dientes | React Profiler |

---

## 17. Lo que NO cambia

Para claridad, estos elementos **no se modifican**:

- Estructura de la tabla `clinical_records` (no se agregan columnas SQL)
- Evento WebSocket `ODONTOGRAM_UPDATED` (misma estructura)
- Endpoint URLs (mismos paths)
- Autenticacion y `tenant_id` isolation
- Tab "Odontograma" en PatientDetail (sigue siendo la misma tab)
- Historial de versiones del odontograma (change separado: `document-versioning`)
- Odontograma mixto (no se muestra permanente + temporal simultaneamente)

---

## 18. Orden de Lectura Recomendado

Para un desarrollador que se incorpora al cambio:

1. **Esta spec** (general) — vision completa
2. `data-model-evolution` — entender el formato v3.0 y el parser
3. `state-catalog` — conocer los ~40 estados
4. `surface-selection` — como funcionan las superficies clickeables
5. `dentition-tabs` — como se agrega la denticion temporal
6. `symbol-selector-modal` + `state-condition-color` — los modales de UX
7. `i18n-expansion` — traducciones
8. `nova-tools-update` — impacto en IA
9. `svg-pdf-renderer` — impacto en PDFs
