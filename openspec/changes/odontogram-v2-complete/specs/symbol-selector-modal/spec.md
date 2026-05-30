# Spec: symbol-selector-modal

**Change:** odontogram-v2-complete
**Spec ID:** SPEC-SM
**Tipo:** Frontend
**Prioridad:** P1
**Dependencia:** `surface-selection` (la superficie ya debe estar seleccionada antes de abrir este modal)
**Estado:** Borrador
**Fecha:** 2026-04-02

---

## 1. Resumen

El odontograma v1 de ClinicForge usa botones inline para seleccionar entre 10 estados posibles. Con el catalogo expandido v2 (~40 estados en 2 categorias), ese modelo no escala. Esta spec define el componente `SymbolSelectorModal` — el primer paso del flujo de edicion de superficies — que reemplaza los botones inline por un modal/drawer organizado, buscable y con soporte para preseleccion del estado actual.

El modal se presenta como **bottom sheet en mobile** (desliza desde abajo) y como **modal centrado en desktop** (fade-in con overlay). Su responsabilidad es única: presentar el catalogo de estados y dejar que el usuario elija uno. Al confirmar, delega el control al siguiente paso (`StateConditionModal`) pasando el `stateId` seleccionado.

El catalogo se divide en dos categorias visuales: **Preexistente** (estados clinicos preexistentes) y **Lesion** (patologias y condiciones activas). Cada item muestra icono, nombre y badge de categoria. La busqueda en tiempo real filtra por nombre de estado dentro del catalogo visible.

---

## 2. Requisitos funcionales

### REQ-SM-01 — Apertura del modal al seleccionar superficie
Cuando el usuario hace click en una superficie de una pieza dental (y el modo no es `readOnly`), el sistema DEBE abrir `SymbolSelectorModal` pasando el `toothId`, `surfaceName` y el estado actual de esa superficie (si existe) como `currentState`.

### REQ-SM-02 — Layout responsive: bottom sheet / modal centrado
En viewports menores a 768px (mobile) el componente DEBE renderizarse como un **bottom sheet** que ocupa el 85% del alto de la pantalla y el 100% del ancho, con bordes superiores redondeados (`rounded-t-2xl`). En viewports mayores o iguales a 768px (desktop) DEBE renderizarse como un **modal centrado** con `max-w-lg w-full` y `rounded-2xl`.

### REQ-SM-03 — Overlay con cierre al hacer click
El modal DEBE estar precedido por un overlay semi-transparente (`bg-black/60`). Al hacer click en el overlay (fuera del panel) se cierra el modal sin aplicar cambios (equivalente al boton X).

### REQ-SM-04 — Barra de busqueda
El modal DEBE incluir un campo de texto con placeholder `"Buscar símbolo..."` que filtra los estados visibles en tiempo real (sin debounce necesario, la lista es pequeña). La busqueda es case-insensitive y accentuation-insensitive. Si ningun estado coincide, muestra el mensaje `"Sin resultados para '{query}'"` centrado en el area de la grilla.

### REQ-SM-05 — Seccion "Preexistente"
Los estados de la categoria `"preexistente"` DEBEN aparecer antes de los de la categoria `"lesion"`. La seccion tiene un header con el texto `"PREEXISTENTE"` y un separador horizontal. El header solo es visible si la seccion tiene al menos un item (considerando el filtro de busqueda activo).

### REQ-SM-06 — Seccion "Lesion"
Los estados de la categoria `"lesion"` DEBEN aparecer despues de los de la categoria `"preexistente"`, con su propio header `"LESION"` y separador. El header solo es visible si la seccion tiene al menos un item con el filtro activo.

### REQ-SM-07 — Grilla de 2 columnas
Dentro de cada seccion, los estados se presentan en una grilla de 2 columnas (`grid grid-cols-2 gap-2`). Cada item es una tarjeta clickeable que ocupa el 100% del ancho de su celda.

### REQ-SM-08 — Estructura de cada item
Cada tarjeta de estado DEBE mostrar (de arriba a abajo):
1. El simbolo/icono del estado (proveniente del campo `icon` o `symbol` del catalogo, renderizado como texto o SVG inline de 24px)
2. El nombre del estado (`text-sm font-medium text-white`)
3. Un badge de categoria: `"PREEXISTENTE"` con clases `bg-blue-500/20 text-blue-400 text-xs px-2 py-0.5 rounded-full` o `"LESION"` con `bg-red-500/20 text-red-400 text-xs px-2 py-0.5 rounded-full`

### REQ-SM-09 — Estado de seleccion en grilla
Al hacer click en un item, este se marca como seleccionado visualmente (`ring-2 ring-blue-500 bg-blue-500/10`). Solo se puede tener un item seleccionado a la vez. Si `currentState` fue provisto como prop, ese item aparece pre-seleccionado al abrir el modal.

### REQ-SM-10 — Boton "Siguiente"
En la parte inferior del panel (fuera del area de scroll) DEBE haber un boton `"Siguiente →"` con clases `bg-white text-[#0a0e1a] font-semibold`. Este boton esta **deshabilitado** (`opacity-40 cursor-not-allowed`) si no hay ningun estado seleccionado. Al hacer click, llama a `onSelect(selectedStateId)` y cierra el modal.

### REQ-SM-11 — Boton de cierre X
En la esquina superior derecha del header del panel DEBE haber un boton `X` (`lucide-react` `<X size={20} />`). Al hacer click llama a `onClose()` sin aplicar cambios.

### REQ-SM-12 — Header contextual
El header del modal DEBE mostrar el contexto de lo que se está editando: `"Superficie: {surfaceName}"` si `surfaceName` fue provisto, o `"Pieza {toothId}"` como fallback. Usar la funcion de traduccion `t()` para las etiquetas estaticas.

### REQ-SM-13 — Scroll interno
El area de la grilla (con las dos secciones) DEBE ser scrolleable verticalmente (`overflow-y-auto`) sin que el header (con titulo y busqueda) ni el footer (con el boton "Siguiente") hagan scroll.

### REQ-SM-14 — Animacion de entrada/salida
**Mobile (bottom sheet):** entra con `translate-y-full → translate-y-0` en 300ms (`transition-transform duration-300 ease-out`). Sale con el inverso.
**Desktop (modal):** entra con `opacity-0 scale-95 → opacity-100 scale-100` en 300ms (`transition-all duration-300 ease-out`). Sale con el inverso.
La animacion de salida se completa antes de desmontar el componente (usar estado `isClosing` con `setTimeout(onClose, 300)` al iniciar el cierre).

### REQ-SM-15 — Accesibilidad basica
El modal DEBE tener `role="dialog"` y `aria-modal="true"`. El boton X DEBE tener `aria-label="Cerrar selector de simbolos"`. Al abrir, el foco DEBE moverse al campo de busqueda.

### REQ-SM-16 — Estado vacio inicial
Si `currentState` es `undefined` o `null`, ningun item aparece pre-seleccionado y el boton "Siguiente" inicia deshabilitado.

---

## 3. Detalle tecnico

### 3.1. Estructura de componentes

```
SymbolSelectorModal.tsx
  ├── Overlay (div con bg-black/60)
  └── Panel (bottom sheet | modal)
       ├── Header
       │     ├── Texto contextual (superficie/pieza)
       │     └── Boton X
       ├── Barra de busqueda (input)
       ├── Grilla scrolleable
       │     ├── SeccionPreexistente
       │     │     ├── Header "PREEXISTENTE"
       │     │     └── grid: StateCard[] (filtrados)
       │     └── SeccionLesion
       │           ├── Header "LESION"
       │           └── grid: StateCard[] (filtrados)
       └── Footer
             └── Boton "Siguiente →"
```

**Ubicacion:** `frontend_react/src/components/odontogram/SymbolSelectorModal.tsx`

### 3.2. Props interface

```typescript
interface SymbolSelectorModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSelect: (stateId: string) => void;  // llamado cuando el usuario confirma con "Siguiente"
  currentState?: string;                // pre-selecciona el estado actual de la superficie
  toothId: number;                      // para mostrar contexto en el header
  surfaceName?: string;                 // nombre de la superficie siendo editada (ej: "Oclusal")
}
```

### 3.3. Estado interno

```typescript
const [query, setQuery]               = useState('');
const [selected, setSelected]         = useState<string | null>(currentState ?? null);
const [isClosing, setIsClosing]       = useState(false);
const searchInputRef                  = useRef<HTMLInputElement>(null);
```

Al montar (`useEffect` con `[isOpen]`): si `isOpen === true`, enfoca `searchInputRef.current` y hace scroll al top del area de la grilla.

### 3.4. Origen del catalogo

```typescript
// frontend_react/src/components/odontogram/catalog.ts  (nuevo archivo)
export interface DentalStateEntry {
  id: string;           // ej: "caries", "restauracion_resina"
  name: string;         // ej: "Caries", "Restauracion Resina"
  category: 'preexistente' | 'lesion';
  icon: string;         // emoji o codigo de simbolo (ej: "⬛", "🔵")
  defaultColor: string; // color HEX por defecto (ej: "#ef4444")
}

export const DENTAL_CATALOG: DentalStateEntry[] = [
  // ~20 estados Preexistente
  { id: 'healthy',              name: 'Sano',                    category: 'preexistente', icon: '○',  defaultColor: '#22c55e' },
  { id: 'restauracion_resina',  name: 'Restauración Resina',     category: 'preexistente', icon: '◼',  defaultColor: '#3b82f6' },
  { id: 'restauracion_amalgama',name: 'Restauración Amalgama',   category: 'preexistente', icon: '◆',  defaultColor: '#6b7280' },
  { id: 'corona',               name: 'Corona',                  category: 'preexistente', icon: '♛',  defaultColor: '#f59e0b' },
  { id: 'implante',             name: 'Implante',                category: 'preexistente', icon: '⟂',  defaultColor: '#8b5cf6' },
  { id: 'sellante',             name: 'Sellante',                category: 'preexistente', icon: '▣',  defaultColor: '#06b6d4' },
  { id: 'protesis_parcial',     name: 'Prótesis Parcial',        category: 'preexistente', icon: '⌂',  defaultColor: '#d97706' },
  { id: 'protesis_total',       name: 'Prótesis Total',          category: 'preexistente', icon: '⌬',  defaultColor: '#b45309' },
  { id: 'perno',                name: 'Perno',                   category: 'preexistente', icon: '⊕',  defaultColor: '#7c3aed' },
  { id: 'carilla',              name: 'Carilla',                 category: 'preexistente', icon: '▷',  defaultColor: '#0ea5e9' },
  { id: 'puente',               name: 'Puente',                  category: 'preexistente', icon: '⌘',  defaultColor: '#ca8a04' },
  { id: 'endodoncia',           name: 'Endodoncia (RCT)',        category: 'preexistente', icon: '⊗',  defaultColor: '#dc2626' },
  { id: 'extraido',             name: 'Extraído / Ausente',      category: 'preexistente', icon: '✗',  defaultColor: '#374151' },
  { id: 'erupcion_parcial',     name: 'Erupción Parcial',        category: 'preexistente', icon: '↑',  defaultColor: '#84cc16' },
  { id: 'diente_retenido',      name: 'Diente Retenido',        category: 'preexistente', icon: '↓',  defaultColor: '#64748b' },
  { id: 'diastema',             name: 'Diastema',                category: 'preexistente', icon: '↔',  defaultColor: '#94a3b8' },
  { id: 'giroversion',          name: 'Giroversión',             category: 'preexistente', icon: '↻',  defaultColor: '#a78bfa' },
  { id: 'supernumerario',       name: 'Supernumerario',          category: 'preexistente', icon: '+',  defaultColor: '#f97316' },
  // ~20 estados Lesion
  { id: 'caries',               name: 'Caries',                  category: 'lesion',       icon: '●',  defaultColor: '#ef4444' },
  { id: 'caries_inicial',       name: 'Caries Inicial',          category: 'lesion',       icon: '◉',  defaultColor: '#f97316' },
  { id: 'caries_secundaria',    name: 'Caries Secundaria',       category: 'lesion',       icon: '◎',  defaultColor: '#dc2626' },
  { id: 'fractura',             name: 'Fractura',                category: 'lesion',       icon: '⚡',  defaultColor: '#fbbf24' },
  { id: 'fisura',               name: 'Fisura',                  category: 'lesion',       icon: '╱',  defaultColor: '#f59e0b' },
  { id: 'abrasion',             name: 'Abrasión',                category: 'lesion',       icon: '≈',  defaultColor: '#fb923c' },
  { id: 'erosion',              name: 'Erosión',                 category: 'lesion',       icon: '∿',  defaultColor: '#fdba74' },
  { id: 'abfraccion',           name: 'Abfracción',              category: 'lesion',       icon: '⌒',  defaultColor: '#fcd34d' },
  { id: 'recesion_gingival',    name: 'Recesión Gingival',       category: 'lesion',       icon: '↡',  defaultColor: '#f43f5e' },
  { id: 'bolsa_periodontal',    name: 'Bolsa Periodontal',       category: 'lesion',       icon: '⩔',  defaultColor: '#e11d48' },
  { id: 'movilidad',            name: 'Movilidad',               category: 'lesion',       icon: '〜',  defaultColor: '#fb7185' },
  { id: 'hiperestesia',         name: 'Hiperestesia',            category: 'lesion',       icon: '⚠',  defaultColor: '#fbbf24' },
  { id: 'impactacion_alimento', name: 'Impactación Alimento',    category: 'lesion',       icon: '∨',  defaultColor: '#a3e635' },
  { id: 'necrosis',             name: 'Necrosis Pulpar',         category: 'lesion',       icon: '☠',  defaultColor: '#1f2937' },
  { id: 'inflamacion',          name: 'Inflamación Periapical',  category: 'lesion',       icon: '⊛',  defaultColor: '#dc2626' },
  { id: 'mancha_blanca',        name: 'Mancha Blanca',           category: 'lesion',       icon: '◌',  defaultColor: '#f1f5f9' },
  { id: 'tincion',              name: 'Tinción',                 category: 'lesion',       icon: '▪',  defaultColor: '#78350f' },
];
```

### 3.5. Logica de filtrado

```typescript
const normalizeStr = (s: string) =>
  s.toLowerCase().normalize('NFD').replace(/\p{Diacritic}/gu, '');

const filtered = useMemo(() => {
  const q = normalizeStr(query.trim());
  if (!q) return DENTAL_CATALOG;
  return DENTAL_CATALOG.filter(e => normalizeStr(e.name).includes(q));
}, [query]);

const preexistentes = filtered.filter(e => e.category === 'preexistente');
const lesiones      = filtered.filter(e => e.category === 'lesion');
```

### 3.6. Logica de cierre con animacion

```typescript
const handleClose = () => {
  setIsClosing(true);
  setTimeout(() => {
    setIsClosing(false);
    onClose();
  }, 300);
};

const handleNext = () => {
  if (!selected) return;
  onSelect(selected);
  handleClose();
};
```

### 3.7. Pseudo-wireframe (mobile — bottom sheet)

```
┌─────────────────────────────────────┐
│  Superficie: Oclusal        [X]     │  ← header fijo
├─────────────────────────────────────┤
│  [🔍 Buscar símbolo...           ]  │  ← searchbar fijo
├─────────────────────────────────────┤
│  PREEXISTENTE ────────────────────  │
│  ┌──────────────┐ ┌──────────────┐  │
│  │  ○  Sano     │ │  ◼  Resina   │  │  ← grid 2 cols
│  │ [PREEX.]     │ │ [PREEX.]     │  │
│  └──────────────┘ └──────────────┘  │
│  ┌──────────────┐ ┌──────────────┐  │
│  │  ♛  Corona   │ │  ⊗  Endodoc  │  │
│  │ [PREEX.]     │ │ [PREEX.]     │  │
│  └──────────────┘ └──────────────┘  │
│  ...                                │  ← scroll
│  LESION ──────────────────────────  │
│  ┌──────────────┐ ┌──────────────┐  │
│  │  ●  Caries   │ │  ⚡ Fractura  │  │
│  │  [LESION]    │ │  [LESION]    │  │  ← ring azul si seleccionado
│  └──────────────┘ └──────────────┘  │
│  ...                                │
├─────────────────────────────────────┤
│  [        Siguiente →         ]     │  ← footer fijo, disabled si !selected
└─────────────────────────────────────┘
```

### 3.8. Clases Tailwind clave

| Elemento | Clases |
|----------|--------|
| Overlay | `fixed inset-0 z-50 bg-black/60` |
| Panel mobile | `fixed bottom-0 left-0 right-0 z-50 bg-[#0d1117] rounded-t-2xl max-h-[85vh] flex flex-col` |
| Panel desktop | `fixed inset-0 z-50 flex items-center justify-center p-4` > `bg-[#0d1117] rounded-2xl w-full max-w-lg max-h-[85vh] flex flex-col` |
| Header | `flex items-center justify-between p-4 border-b border-white/[0.06]` |
| SearchInput | `w-full bg-white/[0.04] border border-white/[0.08] text-white placeholder:text-white/30 rounded-lg px-3 py-2 text-sm outline-none focus:border-blue-500/50` |
| Grid area | `flex-1 overflow-y-auto p-4 space-y-4` |
| Section header | `text-xs font-bold text-white/40 tracking-widest mb-2` |
| StateCard no seleccionada | `bg-white/[0.04] border border-white/[0.08] rounded-xl p-3 cursor-pointer hover:bg-white/[0.08] transition-colors` |
| StateCard seleccionada | `bg-blue-500/10 border border-blue-500 ring-2 ring-blue-500/30 rounded-xl p-3 cursor-pointer` |
| Badge Preexistente | `bg-blue-500/20 text-blue-400 text-xs px-2 py-0.5 rounded-full` |
| Badge Lesion | `bg-red-500/20 text-red-400 text-xs px-2 py-0.5 rounded-full` |
| Footer | `p-4 border-t border-white/[0.06]` |
| Boton Siguiente activo | `w-full bg-white text-[#0a0e1a] font-semibold py-3 rounded-xl transition-opacity` |
| Boton Siguiente disabled | `w-full bg-white/20 text-white/30 font-semibold py-3 rounded-xl cursor-not-allowed` |

---

## 4. Escenarios

### Escenario 1 — Apertura con preseleccion del estado actual
**Dado** que la superficie oclusal de la pieza 21 tiene estado `"caries"`
**Cuando** el usuario hace click en esa superficie
**Entonces** `SymbolSelectorModal` se abre
**Y** el item "Caries" aparece con el anillo azul de seleccion
**Y** el boton "Siguiente" esta habilitado

### Escenario 2 — Busqueda filtra estados en tiempo real
**Dado** que el modal esta abierto mostrando los ~40 estados
**Cuando** el usuario escribe "corona" en el campo de busqueda
**Entonces** la grilla muestra solo los items que contienen "corona" (case-insensitive, accentuation-insensitive)
**Y** los headers de seccion que quedaron sin items son ocultados

### Escenario 3 — Busqueda sin resultados
**Dado** que el modal esta abierto
**Cuando** el usuario escribe "xyzabc" en el campo de busqueda
**Entonces** la grilla muestra el mensaje `"Sin resultados para 'xyzabc'"` centrado
**Y** no hay items ni headers de seccion visibles

### Escenario 4 — Seleccion de un estado y avance al siguiente paso
**Dado** que el modal esta abierto con ninguna seleccion previa
**Y** el boton "Siguiente" esta deshabilitado
**Cuando** el usuario hace click en la tarjeta "Restauracion Resina"
**Entonces** esa tarjeta se marca con el anillo azul
**Y** el boton "Siguiente" se habilita
**Cuando** el usuario hace click en "Siguiente"
**Entonces** se llama a `onSelect("restauracion_resina")`
**Y** el modal inicia la animacion de cierre

### Escenario 5 — Solo se puede seleccionar un estado a la vez
**Dado** que el modal esta abierto
**Cuando** el usuario hace click en "Caries"
**Entonces** "Caries" queda seleccionada
**Cuando** el usuario hace click en "Fractura"
**Entonces** "Fractura" queda seleccionada
**Y** "Caries" ya no tiene el estado de seleccionado (el anillo desaparece)

### Escenario 6 — Cierre sin cambios por overlay o boton X
**Dado** que el modal esta abierto
**Y** el usuario habia seleccionado "Caries"
**Cuando** el usuario hace click en el overlay o en el boton X
**Entonces** se llama a `onClose()` sin llamar a `onSelect()`
**Y** la superficie del diente no cambia de estado

### Escenario 7 — Animacion bottom sheet en mobile
**Dado** que el usuario esta en un viewport de 375px de ancho
**Cuando** el modal se abre
**Entonces** el panel sube desde la parte inferior con una transicion de 300ms
**Cuando** el usuario cierra el modal
**Entonces** el panel baja hacia la parte inferior con una transicion de 300ms
**Y** el desmontaje del componente ocurre despues de que la animacion termina

### Escenario 8 — Animacion fade/scale en desktop
**Dado** que el usuario esta en un viewport de 1280px de ancho
**Cuando** el modal se abre
**Entonces** el panel aparece con fade-in y leve scale-up (de 95% a 100%) en 300ms
**Y** el modal esta centrado en la pantalla con overlay oscuro

### Escenario 9 — Foco en searchbar al abrir
**Dado** que el modal se abre (cualquier contexto)
**Cuando** el componente termina de montar
**Entonces** el cursor queda posicionado en el campo de busqueda `"Buscar símbolo..."`
**Y** el usuario puede escribir de inmediato sin hacer click adicional

### Escenario 10 — Contexto en el header
**Dado** que el modal se abre para la superficie "Mesial" de la pieza 15
**Entonces** el header del modal muestra `"Superficie: Mesial"`
**Dado** que el modal se abre sin `surfaceName` (solo con `toothId: 36`)
**Entonces** el header muestra `"Pieza 36"`

### Escenario 11 — readOnly no abre el modal
**Dado** que el odontograma esta en modo `readOnly={true}`
**Cuando** el usuario hace click en cualquier superficie
**Entonces** `SymbolSelectorModal` NO se abre
**Y** el cursor sobre las superficies es `cursor-default` (no pointer)

---

## 5. Criterios de aceptacion

| ID | Criterio | Verificacion |
|----|----------|--------------|
| CA-SM-01 | En mobile (< 768px) el modal se presenta como bottom sheet ocupando 85vh | Test de clases CSS / viewport test |
| CA-SM-02 | En desktop (>= 768px) el modal se presenta centrado como `max-w-lg` | Test de clases CSS / viewport test |
| CA-SM-03 | El catalogo muestra las 2 secciones ("PREEXISTENTE" y "LESION") con sus respectivos headers | Test de renderizado |
| CA-SM-04 | La busqueda filtra por nombre, es case-insensitive y accentuation-insensitive | Test unitario de `normalizeStr` + test de render |
| CA-SM-05 | Si la busqueda no arroja resultados, se muestra el mensaje de "Sin resultados" | Test de renderizado con query sin match |
| CA-SM-06 | Si `currentState` es provisto, ese item aparece pre-seleccionado al abrir | Test de prop / snapshot |
| CA-SM-07 | El boton "Siguiente" esta deshabilitado si no hay seleccion | Test de atributo `disabled` / `aria-disabled` |
| CA-SM-08 | Al seleccionar un estado y hacer click en "Siguiente", se llama a `onSelect(stateId)` | Test de callback |
| CA-SM-09 | Solo es posible tener un item seleccionado a la vez | Test de estado |
| CA-SM-10 | Click en overlay o en X llama a `onClose()` sin llamar `onSelect()` | Test de callback |
| CA-SM-11 | La animacion de cierre (300ms) se completa ANTES de desmontar el componente | Test de timing / `setTimeout` |
| CA-SM-12 | El foco pasa al campo de busqueda al abrir el modal | Test de focus |
| CA-SM-13 | En `readOnly`, el modal no se abre al hacer click en la superficie | Test de integración |
| CA-SM-14 | Los badges de categoria tienen el color correcto (azul para preexistente, rojo para lesion) | Test de clases |
| CA-SM-15 | El header muestra "Superficie: {nombre}" si `surfaceName` es provisto, "Pieza {id}" como fallback | Test de renderizado condicional |

---

## 6. Archivos afectados

| Archivo | Cambio |
|---------|--------|
| `frontend_react/src/components/odontogram/SymbolSelectorModal.tsx` | **NUEVO** — Componente principal de esta spec |
| `frontend_react/src/components/odontogram/catalog.ts` | **NUEVO** — `DENTAL_CATALOG: DentalStateEntry[]` con ~40 entradas, exportado para uso en modal, StateConditionModal, y SVG renderer |
| `frontend_react/src/components/Odontogram.tsx` | Modificado: importa `SymbolSelectorModal`, maneja estado `symbolModalOpen`, `selectedSurface`, `currentSurfaceState`; pasa props al modal; conecta `onSelect` con apertura de `StateConditionModal` |
| `frontend_react/src/locales/es.json` | Agregar claves: `odontogram.symbol_selector.title`, `odontogram.symbol_selector.search_placeholder`, `odontogram.symbol_selector.next_button`, `odontogram.symbol_selector.no_results`, `odontogram.symbol_selector.section_preexistente`, `odontogram.symbol_selector.section_lesion`, `odontogram.symbol_selector.close_aria` |
| `frontend_react/src/locales/en.json` | Idem en ingles |
| `frontend_react/src/locales/fr.json` | Idem en frances |

**Archivos NO afectados por esta spec:**
- `orchestrator_service/admin_routes.py` — no cambia el API; el modal es puramente frontend
- `orchestrator_service/services/odontogram_svg.py` — usa `catalog.ts` indirectamente via el formato de datos, pero el renderer es Python
- `orchestrator_service/services/nova_tools.py` — los `stateId` del catalogo son los mismos que ya espera `modificar_odontograma`

---

## 7. Dependencias

### Dependencias previas (deben estar completas antes de implementar esta spec)

| Spec | Razon |
|------|-------|
| `surface-selection` | Esta spec REQUIERE que el sistema de superficies individuales clickeables ya exista en `Odontogram.tsx`. `SymbolSelectorModal` se abre desde el handler `onSurfaceClick(toothId, surfaceName)` que `surface-selection` define. |
| `dentition-tabs` | El componente `Odontogram.tsx` ya debe tener el estado `activeDentition` para que `onSelect` sepa en cual denticion escribir el nuevo estado de la superficie. |

### Specs que dependen de esta (deben implementarse despues)

| Spec | Razon |
|------|-------|
| `state-condition-color` | `SymbolSelectorModal` llama a `onSelect(stateId)` que disparara la apertura de `StateConditionModal`. Si esta spec no existe, `onSelect` no puede abrir el segundo paso. |
| `svg-pdf-renderer` | El renderer necesita el `DENTAL_CATALOG` (definido en `catalog.ts`) para conocer el `defaultColor` y el `icon` de cada estado al renderizar el SVG/PDF. |

### Dependencias tecnicas (librerias/APIs)

| Dependencia | Version requerida | Uso |
|-------------|-------------------|-----|
| React | 18.x | `useState`, `useEffect`, `useRef`, `useMemo` |
| Tailwind CSS | 3.x | Todas las clases de estilos (responsive breakpoints, dark palette) |
| `lucide-react` | instalado | Icono `X` (boton cierre) y `Search` (icono en el input) |
| `useTranslation` | Context propio | Labels de UI con i18n |

---

## Notas de implementacion

1. **`catalog.ts` es la fuente unica de verdad**: El mismo archivo se importa en `SymbolSelectorModal`, `StateConditionModal`, `Odontogram.tsx` (para resolver nombres de estados en tooltips), y eventualmente en el renderer Python (que lo tendra como un espejo en `models_dental.py`). No duplicar la data.

2. **`onSelect` NO cierra el modal directamente**: `onSelect(stateId)` es llamado por el padre (`Odontogram.tsx`), que a su vez abre `StateConditionModal` y puede cerrar `SymbolSelectorModal`. Esto le da al padre control total del flujo. La animacion de cierre del modal se inicia desde `handleNext`, pero el desmontaje definitivo lo controla el padre via `isOpen={false}`.

3. **Bottom sheet vs modal — no usar CSS media query puro**: Detectar el breakpoint con `useWindowSize()` (hook simple de `useState` + `useEffect`) para poder aplicar clases distintas al elemento raiz. No usar solo `sm:` de Tailwind porque la estructura del DOM (posicionamiento fixed) es diferente entre los dos layouts.

4. **Scroll al top al abrir**: Guardar una referencia al contenedor de la grilla (`gridRef`) y ejecutar `gridRef.current.scrollTop = 0` en el `useEffect` de apertura, para que si el modal fue cerrado con el scroll a la mitad, vuelva al top al reabrirse.

5. **Testiabilidad**: Todos los items de estado deben tener `data-testid={`state-card-${entry.id}`}`. El boton "Siguiente" debe tener `data-testid="symbol-selector-next"`. El input de busqueda `data-testid="symbol-selector-search"`.
