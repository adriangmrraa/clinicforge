# Spec: state-condition-color

**Change:** odontogram-v2-complete
**Spec ID:** SPEC-SCC
**Tipo:** Frontend
**Prioridad:** P1
**Dependencia:** `symbol-selector-modal` (se abre cuando `SymbolSelectorModal` llama a `onSelect(stateId)`)
**Estado:** Borrador
**Fecha:** 2026-04-02

---

## 1. Resumen

`StateConditionModal` es el segundo paso del flujo de edicion de superficies. Se abre inmediatamente despues de que el usuario elige un estado desde `SymbolSelectorModal`. Su responsabilidad es capturar dos datos adicionales: la **condicion clinica** del estado (Bueno / Malo / Indefinido) y el **color** con el que se visualizara esa superficie en el odontograma.

Al confirmar con "Aplicar", el modal llama a `onApply(condition, color)` y el orquestador (`Odontogram.tsx`) escribe el triplete `{ state, condition, color }` en la superficie correspondiente. Al hacer click en "Volver", el usuario regresa a `SymbolSelectorModal` sin perder la seleccion anterior.

El diseno del modal sigue el sistema dark de ClinicForge con acento `cyan` para los elementos activos e interactivos, tomando como referencia el screenshot de SmileConnect donde los botones de condicion tienen un borde cyan al estar seleccionados y el boton "Aplicar" es de fondo teal/cyan.

---

## 2. Requisitos funcionales

### REQ-SCC-01 — Apertura desde SymbolSelectorModal
`StateConditionModal` DEBE abrirse cuando `SymbolSelectorModal` resuelve su seleccion (el usuario hace click en "Siguiente"). Los datos que recibe son: `stateId` (el estado elegido), `stateName` (nombre legible del estado), y `defaultColor` (del catalogo). Ambos modales NO deben estar visibles simultaneamente: `SymbolSelectorModal` se cierra (o queda oculto sin desmontar) mientras `StateConditionModal` esta abierto.

### REQ-SCC-02 — Selector de condicion: 3 opciones exclusivas
El modal DEBE mostrar 3 botones de condicion en una fila horizontal:
- **Bueno**: icono checkmark (`<Check size={18} />`), texto "Bueno"
- **Malo**: icono X (`<X size={18} />`), texto "Malo"
- **Indefinido**: icono interrogacion (`<HelpCircle size={18} />`), texto "Indefinido"

Solo una condicion puede estar seleccionada a la vez. La seleccion inicial es `"indefinido"` si `currentCondition` no fue provisto.

### REQ-SCC-03 — Feedback visual de condicion seleccionada
El boton de condicion seleccionado DEBE destacarse con borde cyan y fondo cyan suave (`border-cyan-400 bg-cyan-400/10 text-cyan-300`). Los botones no seleccionados tienen estilo neutro (`bg-white/[0.04] border-white/[0.08] text-white/50`). La transicion entre estados es `transition-colors duration-150`.

### REQ-SCC-04 — Color actual como swatch circular
El modal DEBE mostrar el color seleccionado actualmente como un circulo de 48px (`w-12 h-12 rounded-full`). Al abrir, el color inicial es `currentColor` si fue provisto, o `defaultColor` del catalogo si no lo fue. El swatch se actualiza en tiempo real al cambiar el color.

### REQ-SCC-05 — Display del codigo HEX
Junto al swatch DEBE mostrarse el codigo HEX del color actual (ej: `#ef4444`). El codigo es editable directamente como un input de texto: si el usuario escribe un HEX valido (formato `#RRGGBB` o `#RGB`), el swatch se actualiza. Si el valor es invalido, el input muestra borde rojo pero NO se actualiza el swatch hasta que el HEX sea valido.

### REQ-SCC-06 — Color picker nativo al hacer click en el swatch
Al hacer click en el swatch (o en el icono de paleta junto al HEX), se abre el picker de color nativo del navegador (input `type="color"` oculto, disparado por click). El valor del picker nativo se refleja inmediatamente en el swatch y en el input HEX.

### REQ-SCC-07 — Paleta de colores predefinidos
Debajo del swatch y el HEX, el modal DEBE mostrar una fila de **10 swatches de colores predefinidos** (quick-select). Al hacer click en uno, el color se aplica inmediatamente al swatch principal y al input HEX. Los colores predefinidos son:

```typescript
export const DENTAL_COLOR_PRESETS = [
  '#22c55e',  // verde (sano)
  '#3b82f6',  // azul (resina)
  '#ef4444',  // rojo (caries activa)
  '#f97316',  // naranja (caries inicial)
  '#f59e0b',  // ambar (corona)
  '#8b5cf6',  // violeta (implante)
  '#06b6d4',  // cyan (sellante)
  '#6b7280',  // gris (amalgama)
  '#1f2937',  // negro oscuro (necrosis)
  '#f1f5f9',  // blanco grisaceo (mancha blanca)
];
```

### REQ-SCC-08 — Nombre del estado en el header
El header del modal DEBE mostrar el nombre del estado que se esta configurando (proveniente de `stateName`). Esto da contexto al usuario sobre qué esta coloreando/condicionando. Ejemplo: `"Configurar: Caries"`.

### REQ-SCC-09 — Boton "Aplicar"
En la parte inferior del modal DEBE haber un boton `"Aplicar"` con clases `bg-cyan-500 hover:bg-cyan-400 text-white font-semibold`. Este boton siempre esta habilitado (siempre hay una condicion seleccionada por defecto y un color valido). Al hacer click llama a `onApply(condition, color)` y luego cierra el modal con `onClose()`.

### REQ-SCC-10 — Boton "Volver"
Al lado izquierdo del boton "Aplicar" DEBE haber un boton `"← Volver"` con clases `bg-white/[0.06] text-white/70 hover:bg-white/[0.10]`. Al hacer click llama a `onBack()` sin modificar ningun estado de superficie. `Odontogram.tsx` usa `onBack` para volver a mostrar `SymbolSelectorModal` con la seleccion previa intacta.

### REQ-SCC-11 — Modal centrado en todos los viewports
A diferencia de `SymbolSelectorModal` que es bottom sheet en mobile, `StateConditionModal` se presenta siempre como un **modal centrado** (no bottom sheet) tanto en mobile como en desktop. Esto es intencional: es un paso secundario con pocos controles que no necesita tanto espacio vertical. `max-w-sm w-full` en mobile, `max-w-md` en desktop.

### REQ-SCC-12 — Boton X para cerrar sin cambios
El header DEBE incluir un boton `X` que llama a `onClose()` sin llamar a `onApply()`. Esto cancela el flujo de edicion completo (no vuelve al selector de simbolos, cierra todo).

### REQ-SCC-13 — Preseleccion de condicion y color
Si `currentCondition` fue provisto (la superficie ya tenia una condicion previa), ese boton aparece seleccionado al abrir. Si `currentColor` fue provisto, ese color aparece en el swatch y en el input HEX al abrir. Esto permite editar una superficie ya configurada sin tener que reseleccionar todo desde cero.

### REQ-SCC-14 — Animacion de entrada
El modal entra con `opacity-0 scale-95 → opacity-100 scale-100` en 300ms, igual que el modal centrado en desktop de `SymbolSelectorModal`. El overlay es el mismo (`bg-black/60 fixed inset-0 z-50`). La salida es el inverso, completada antes del desmontaje.

### REQ-SCC-15 — Accesibilidad basica
El modal DEBE tener `role="dialog"` y `aria-modal="true"`. El `aria-label` del dialog debe ser `"Configurar condición y color del estado"`. Los 3 botones de condicion deben tener `role="radio"` y `aria-checked={isSelected}`. El boton X `aria-label="Cerrar"`.

---

## 3. Detalle tecnico

### 3.1. Estructura de componentes

```
StateConditionModal.tsx
  ├── Overlay (div con bg-black/60)
  └── Panel (modal centrado, siempre)
       ├── Header
       │     ├── "Configurar: {stateName}"
       │     └── Boton X
       ├── Body (scrolleable si fuera necesario, aunque raro)
       │     ├── ConditionSelector
       │     │     ├── BotonBueno
       │     │     ├── BotonMalo
       │     │     └── BotonIndefinido
       │     ├── ColorSection
       │     │     ├── ColorSwatch (48px, clickeable)
       │     │     ├── HexInput (texto, editable)
       │     │     └── PaletaPresets (10 swatches)
       │     └── (input[type="color"] oculto, referenciado por ref)
       └── Footer
             ├── Boton "← Volver"
             └── Boton "Aplicar"
```

**Ubicacion:** `frontend_react/src/components/odontogram/StateConditionModal.tsx`

### 3.2. Props interface

```typescript
type DentalCondition = 'bueno' | 'malo' | 'indefinido';

interface StateConditionModalProps {
  isOpen: boolean;
  onClose: () => void;
  onApply: (condition: DentalCondition, color: string) => void;
  onBack: () => void;
  stateId: string;         // ej: "caries" — para acceder al catalogo si se necesita
  stateName: string;       // ej: "Caries" — para mostrar en el header
  defaultColor: string;    // del catalogo, color inicial si no hay currentColor
  currentCondition?: DentalCondition;
  currentColor?: string;
}
```

### 3.3. Estado interno

```typescript
const [condition, setCondition] = useState<DentalCondition>(
  currentCondition ?? 'indefinido'
);
const [color, setColor]         = useState<string>(
  currentColor ?? defaultColor
);
const [hexInput, setHexInput]   = useState<string>(
  currentColor ?? defaultColor
);
const [hexError, setHexError]   = useState<boolean>(false);
const [isClosing, setIsClosing] = useState<boolean>(false);
const colorPickerRef            = useRef<HTMLInputElement>(null);
```

**Sincronizacion `color` / `hexInput`:**
- Cuando cambia el picker nativo o un preset → actualiza `color` Y `hexInput`
- Cuando el usuario edita `hexInput` directamente:
  - Siempre actualiza `hexInput` (para que el campo sea controlado y muestre lo que escribe)
  - Si el valor es HEX valido (`/^#([0-9A-Fa-f]{3}|[0-9A-Fa-f]{6})$/`), actualiza `color` y limpia `hexError`
  - Si no es valido, activa `hexError` pero NO toca `color`

### 3.4. Pseudo-wireframe

```
┌──────────────────────────────────┐
│  Configurar: Caries         [X]  │  ← header
├──────────────────────────────────┤
│                                  │
│  Condición                       │
│  ┌────────┐ ┌────────┐ ┌──────┐  │
│  │ ✓ Bueno│ │ ✗ Malo │ │ ? I… │  │  ← 3 botones, row
│  └────────┘ └────────┘ └──────┘  │
│             ↑ seleccionado       │
│             (borde + fondo cyan) │
│                                  │
│  Color                           │
│  ┌──┐  #ef4444             [🎨]  │  ← swatch 48px + hex input
│  └──┘                            │
│                                  │
│  ○ ○ ○ ○ ○ ○ ○ ○ ○ ○            │  ← 10 color presets (20px circles)
│                                  │
├──────────────────────────────────┤
│  [← Volver]    [     Aplicar  ]  │  ← footer
└──────────────────────────────────┘
```

### 3.5. Implementacion del ColorSection

```tsx
// Swatch clickeable que dispara el picker nativo
<div
  className="w-12 h-12 rounded-full cursor-pointer ring-2 ring-white/10 hover:ring-white/30 transition-all"
  style={{ backgroundColor: color }}
  onClick={() => colorPickerRef.current?.click()}
/>

{/* HEX input */}
<input
  type="text"
  value={hexInput}
  onChange={e => handleHexChange(e.target.value)}
  maxLength={7}
  className={cn(
    'bg-white/[0.04] border rounded-lg px-3 py-2 text-sm font-mono text-white w-28',
    hexError ? 'border-red-500' : 'border-white/[0.08]'
  )}
/>

{/* Picker nativo oculto */}
<input
  ref={colorPickerRef}
  type="color"
  value={color}
  onChange={e => handlePickerChange(e.target.value)}
  className="sr-only"
/>

{/* Presets */}
<div className="flex gap-2 flex-wrap mt-3">
  {DENTAL_COLOR_PRESETS.map(preset => (
    <button
      key={preset}
      className={cn(
        'w-5 h-5 rounded-full transition-transform hover:scale-110',
        color === preset ? 'ring-2 ring-white ring-offset-1 ring-offset-[#0d1117]' : ''
      )}
      style={{ backgroundColor: preset }}
      onClick={() => handlePresetClick(preset)}
      aria-label={`Color ${preset}`}
    />
  ))}
</div>
```

### 3.6. Logica de aplicacion y cierre

```typescript
const handleApply = () => {
  onApply(condition, color);
  handleClose(); // animacion de salida + onClose()
};

const handleBack = () => {
  onBack(); // no cierra, el padre maneja la transicion de vuelta a SymbolSelectorModal
};

const handleClose = () => {
  setIsClosing(true);
  setTimeout(() => {
    setIsClosing(false);
    onClose();
  }, 300);
};
```

**Importante:** `onBack` NO llama a `handleClose`. La animacion de salida de `StateConditionModal` y la re-apertura de `SymbolSelectorModal` la orquesta el componente padre `Odontogram.tsx` respondiendo al evento `onBack`.

### 3.7. Flujo en el orquestador (Odontogram.tsx)

```typescript
// Estado del flujo de seleccion de simbolo
const [symbolModalOpen, setSymbolModalOpen]         = useState(false);
const [conditionModalOpen, setConditionModalOpen]   = useState(false);
const [pendingStateId, setPendingStateId]           = useState<string | null>(null);
const [pendingStateName, setPendingStateName]       = useState<string>('');
const [pendingDefaultColor, setPendingDefaultColor] = useState<string>('#ffffff');
const [editingSurface, setEditingSurface]           = useState<{
  toothId: number;
  surfaceName: string;
} | null>(null);

// Al hacer click en una superficie
const handleSurfaceClick = (toothId: number, surfaceName: string) => {
  setEditingSurface({ toothId, surfaceName });
  setSymbolModalOpen(true);
};

// SymbolSelectorModal.onSelect
const handleSymbolSelect = (stateId: string) => {
  const entry = DENTAL_CATALOG.find(e => e.id === stateId)!;
  setPendingStateId(stateId);
  setPendingStateName(entry.name);
  setPendingDefaultColor(entry.defaultColor);
  setSymbolModalOpen(false);
  setConditionModalOpen(true);
};

// StateConditionModal.onApply
const handleConditionApply = (condition: DentalCondition, color: string) => {
  if (!editingSurface || !pendingStateId) return;
  applySurfaceState(editingSurface.toothId, editingSurface.surfaceName, {
    state: pendingStateId,
    condition,
    color,
  });
  setConditionModalOpen(false);
  setEditingSurface(null);
};

// StateConditionModal.onBack
const handleConditionBack = () => {
  setConditionModalOpen(false);
  setSymbolModalOpen(true); // reabre SymbolSelectorModal con currentState intacto
};
```

### 3.8. Clases Tailwind clave

| Elemento | Clases |
|----------|--------|
| Overlay | `fixed inset-0 z-50 bg-black/60 flex items-center justify-center p-4` |
| Panel | `bg-[#0d1117] rounded-2xl w-full max-w-sm md:max-w-md flex flex-col shadow-2xl` |
| Header | `flex items-center justify-between p-4 border-b border-white/[0.06]` |
| Header titulo | `text-sm font-semibold text-white` |
| Body | `p-5 space-y-5` |
| Section label | `text-xs font-bold text-white/40 tracking-widest uppercase mb-2` |
| Condition button fila | `grid grid-cols-3 gap-2` |
| Condition button no seleccionado | `flex flex-col items-center gap-1 py-3 rounded-xl bg-white/[0.04] border border-white/[0.08] text-white/50 hover:bg-white/[0.08] transition-colors cursor-pointer` |
| Condition button seleccionado | `flex flex-col items-center gap-1 py-3 rounded-xl border border-cyan-400 bg-cyan-400/10 text-cyan-300` |
| Color row | `flex items-center gap-3` |
| Hex input | `bg-white/[0.04] border border-white/[0.08] rounded-lg px-3 py-2 text-sm font-mono text-white w-28 outline-none focus:border-cyan-500/50` |
| Hex input error | `border-red-500` |
| Footer | `flex gap-3 p-4 border-t border-white/[0.06]` |
| Boton Volver | `flex-1 bg-white/[0.06] text-white/70 font-medium py-3 rounded-xl hover:bg-white/[0.10] transition-colors` |
| Boton Aplicar | `flex-2 bg-cyan-500 hover:bg-cyan-400 text-white font-semibold py-3 rounded-xl transition-colors` |

---

## 4. Escenarios

### Escenario 1 — Flujo completo: editar una superficie nueva
**Dado** que el usuario hizo click en la superficie "Oclusal" de la pieza 26 (sin estado previo)
**Y** selecciono "Caries" en `SymbolSelectorModal` y presiono "Siguiente"
**Cuando** `StateConditionModal` se abre
**Entonces** el header muestra `"Configurar: Caries"`
**Y** el boton "Indefinido" esta seleccionado por defecto
**Y** el swatch y el HEX muestran el `defaultColor` de "Caries" del catalogo (`#ef4444`)
**Cuando** el usuario selecciona "Malo"
**Y** hace click en el preset de color naranja (`#f97316`)
**Y** presiona "Aplicar"
**Entonces** se llama a `onApply('malo', '#f97316')`
**Y** la superficie "Oclusal" de la pieza 26 queda con `{ state: 'caries', condition: 'malo', color: '#f97316' }`
**Y** el modal se cierra con animacion

### Escenario 2 — Preseleccion al editar superficie existente
**Dado** que la superficie "Mesial" de la pieza 14 tiene `{ state: 'restauracion_resina', condition: 'bueno', color: '#3b82f6' }`
**Cuando** el usuario hace click en esa superficie y llega a `StateConditionModal` con `currentCondition="bueno"` y `currentColor="#3b82f6"`
**Entonces** el boton "Bueno" esta seleccionado visualmente
**Y** el swatch muestra un circulo azul (`#3b82f6`)
**Y** el input HEX muestra `"#3b82f6"`

### Escenario 3 — Edicion del HEX directamente
**Dado** que `StateConditionModal` esta abierto con color `#ef4444`
**Cuando** el usuario borra el campo HEX y escribe `#22c55e`
**Entonces** el swatch se actualiza al color verde en tiempo real
**Y** ningun borde de error aparece
**Cuando** el usuario escribe un HEX invalido como `#zzzzzz`
**Entonces** el input muestra borde rojo (`border-red-500`)
**Y** el swatch NO cambia (sigue mostrando el ultimo color valido)

### Escenario 4 — Picker nativo abre al hacer click en el swatch
**Dado** que `StateConditionModal` esta abierto
**Cuando** el usuario hace click en el swatch circular
**Entonces** se dispara el click en el `<input type="color">` oculto
**Y** el navegador abre el selector de color nativo del SO
**Cuando** el usuario elige un color en el picker nativo
**Entonces** el swatch y el HEX se actualizan inmediatamente con el color elegido

### Escenario 5 — Preset de color actualiza swatch y HEX
**Dado** que el modal esta abierto con color `#ef4444`
**Cuando** el usuario hace click en el preset `#8b5cf6` (violeta)
**Entonces** el swatch grande muestra el circulo violeta
**Y** el input HEX muestra `"#8b5cf6"`
**Y** el preset violeta tiene el anillo de seleccion (`ring-2 ring-white`)
**Y** el preset rojo anterior ya no tiene el anillo

### Escenario 6 — Volver al selector de simbolos
**Dado** que el usuario llego a `StateConditionModal` despues de elegir "Restauracion Resina"
**Cuando** hace click en "← Volver"
**Entonces** se llama a `onBack()` sin llamar a `onApply()`
**Y** `Odontogram.tsx` cierra `StateConditionModal` y reabre `SymbolSelectorModal`
**Y** en `SymbolSelectorModal`, "Restauracion Resina" sigue seleccionada (preseleccion intacta)
**Y** la superficie del diente no tiene ningun cambio

### Escenario 7 — Cerrar con X cancela el flujo completo
**Dado** que el usuario esta en `StateConditionModal` con "Malo" seleccionado y color cambiado
**Cuando** hace click en el boton X
**Entonces** se llama a `onClose()` sin llamar a `onApply()`
**Y** ambos modales (SymbolSelector y StateCondition) quedan cerrados
**Y** la superficie del diente NO tiene cambios

### Escenario 8 — "Aplicar" siempre esta habilitado
**Dado** que `StateConditionModal` se abre por primera vez (condicion "Indefinido", color default)
**Entonces** el boton "Aplicar" esta habilitado inmediatamente (sin necesidad de interaccion previa)
**Cuando** el usuario hace click en "Aplicar" sin cambiar nada
**Entonces** se llama a `onApply('indefinido', defaultColor)`

### Escenario 9 — Animacion de entrada
**Dado** que `StateConditionModal` va a abrirse (isOpen cambia a true)
**Entonces** el panel entra con fade-in y scale de 95% a 100% en 300ms
**Y** el overlay aparece simultaneamente con fade-in
**Cuando** el usuario presiona Aplicar o X
**Entonces** el panel sale con fade-out y scale inverso en 300ms
**Y** el desmontaje ocurre DESPUES de que la animacion termina

### Escenario 10 — Responsive: modal centrado en mobile
**Dado** que el usuario esta en un viewport de 375px
**Cuando** `StateConditionModal` se abre
**Entonces** el modal aparece centrado (NO es bottom sheet) con `max-w-sm w-full`
**Y** los 3 botones de condicion caben en una fila dentro del modal
**Y** la paleta de 10 colores preset hace wrap si no caben en una fila

---

## 5. Criterios de aceptacion

| ID | Criterio | Verificacion |
|----|----------|--------------|
| CA-SCC-01 | El modal muestra el nombre del estado en el header (`"Configurar: {stateName}"`) | Test de renderizado con props |
| CA-SCC-02 | Los 3 botones de condicion (Bueno/Malo/Indefinido) se muestran en una fila horizontal | Inspeccion visual + test de layout |
| CA-SCC-03 | Al abrir sin `currentCondition`, el boton "Indefinido" esta seleccionado | Test de estado inicial |
| CA-SCC-04 | Al abrir con `currentCondition="bueno"`, el boton "Bueno" esta seleccionado | Test de prop |
| CA-SCC-05 | Solo un boton de condicion puede estar seleccionado a la vez | Test de interaccion |
| CA-SCC-06 | El boton seleccionado tiene borde y fondo cyan (`border-cyan-400 bg-cyan-400/10`) | Test de clases CSS |
| CA-SCC-07 | El swatch muestra `defaultColor` si no hay `currentColor`, o `currentColor` si fue provisto | Test de prop |
| CA-SCC-08 | Editar el HEX con un valor valido actualiza el swatch en tiempo real | Test de input change |
| CA-SCC-09 | Editar el HEX con un valor invalido muestra borde rojo y NO actualiza el swatch | Test de validacion |
| CA-SCC-10 | Click en el swatch abre el color picker nativo | Test de `colorPickerRef.click()` |
| CA-SCC-11 | Cambiar color en el picker nativo actualiza swatch y HEX | Test de evento onChange del input color |
| CA-SCC-12 | Click en un preset actualiza swatch, HEX y marca el preset con anillo | Test de interaccion |
| CA-SCC-13 | El boton "Aplicar" llama a `onApply(condition, color)` con los valores actuales | Test de callback |
| CA-SCC-14 | El boton "Aplicar" esta siempre habilitado (nunca disabled) | Test de atributo |
| CA-SCC-15 | El boton "← Volver" llama a `onBack()` sin llamar a `onApply()` | Test de callback |
| CA-SCC-16 | El boton X llama a `onClose()` sin llamar a `onApply()` | Test de callback |
| CA-SCC-17 | La animacion de entrada/salida (300ms fade+scale) se completa antes del desmontaje | Test de timing |
| CA-SCC-18 | En mobile (375px), el modal es centrado (no bottom sheet) con `max-w-sm` | Test de viewport |
| CA-SCC-19 | La paleta de 10 presets muestra todos los colores definidos en `DENTAL_COLOR_PRESETS` | Test de renderizado |
| CA-SCC-20 | Al hacer click en Volver, `SymbolSelectorModal` reabre con el estado previamente seleccionado | Test de integracion |

---

## 6. Archivos afectados

| Archivo | Cambio |
|---------|--------|
| `frontend_react/src/components/odontogram/StateConditionModal.tsx` | **NUEVO** — Componente principal de esta spec |
| `frontend_react/src/components/odontogram/catalog.ts` | Agregar la constante `DENTAL_COLOR_PRESETS: string[]` (10 colores) al archivo creado por `symbol-selector-modal` |
| `frontend_react/src/components/Odontogram.tsx` | Modificado: importa `StateConditionModal`; agrega estados `conditionModalOpen`, `pendingStateId`, `pendingStateName`, `pendingDefaultColor`; implementa `handleSymbolSelect`, `handleConditionApply`, `handleConditionBack` segun el patron del orquestador descrito en §3.7 |
| `frontend_react/src/locales/es.json` | Agregar claves: `odontogram.condition_modal.title_prefix`, `odontogram.condition_modal.condition_label`, `odontogram.condition_modal.color_label`, `odontogram.condition_modal.condition_bueno`, `odontogram.condition_modal.condition_malo`, `odontogram.condition_modal.condition_indefinido`, `odontogram.condition_modal.apply_button`, `odontogram.condition_modal.back_button`, `odontogram.condition_modal.close_aria` |
| `frontend_react/src/locales/en.json` | Idem en ingles |
| `frontend_react/src/locales/fr.json` | Idem en frances |

**Archivos NO afectados por esta spec:**
- `orchestrator_service/admin_routes.py` — el endpoint PUT de odontograma ya acepta JSONB libre; el nuevo formato `{ state, condition, color }` por superficie es compatible sin cambios de schema
- `orchestrator_service/models.py` — sin cambios; `odontogram_data` es JSONB
- `orchestrator_service/services/odontogram_svg.py` — lo cubre la spec `svg-pdf-renderer`

---

## 7. Dependencias

### Dependencias previas (deben estar completas antes de implementar esta spec)

| Spec | Razon |
|------|-------|
| `symbol-selector-modal` | `StateConditionModal` es el segundo paso del flujo iniciado por `SymbolSelectorModal`. Requiere que `catalog.ts` (con `DENTAL_CATALOG` y `DentalStateEntry`) ya exista, ya que accede a `defaultColor` del catalogo. Tambien requiere la interfaz de `onSelect(stateId)` definida alli. |
| `surface-selection` | El handler `onSurfaceClick` (que arranca el flujo de 2 pasos) vive en la arquitectura de superficies clickeables. `StateConditionModal` usa `editingSurface.toothId` y `editingSurface.surfaceName` que ese handler provee. |

### Specs que dependen de esta (deben implementarse despues)

| Spec | Razon |
|------|-------|
| `svg-pdf-renderer` | El renderer necesita leer el campo `condition` y `color` de cada superficie para renderizar variantes visuales (color custom en el SVG, leyenda de condicion). Esta spec define el formato final de esos campos. |
| `nova-tools-update` | Las herramientas `ver_odontograma` y `modificar_odontograma` de Nova necesitan representar la condicion (bueno/malo/indefinido) en su output textual. Esta spec define los valores validos del enum. |

### Dependencias tecnicas (librerias/APIs)

| Dependencia | Version requerida | Uso |
|-------------|-------------------|-----|
| React | 18.x | `useState`, `useRef`, `useEffect` |
| Tailwind CSS | 3.x | Todos los estilos, `cn()` para clases condicionales |
| `lucide-react` | instalado | Iconos `Check`, `X`, `HelpCircle`, `Palette` |
| `useTranslation` | Context propio | Labels con i18n |
| Browser API nativo | — | `<input type="color">` para el picker |

---

## Notas de implementacion

1. **`cn()` utility**: Importar desde `'../../../lib/utils'` (o donde este definida en el proyecto). Es necesaria para las clases condicionales de los botones de condicion y el HEX input con error.

2. **No instalar librerias de color picker**: El color picker nativo del navegador (`<input type="color">`) es suficiente y ya esta disponible en todos los navegadores modernos. No agregar `react-colorful` ni similares para este caso.

3. **El `<input type="color">` debe estar en el DOM**: Aunque tiene `className="sr-only"` (visualmente oculto), debe estar montado en el DOM para que `colorPickerRef.current.click()` funcione. No usar `display: none` ya que algunos navegadores bloquean el click programatico en elementos ocultos con `display: none`.

4. **Sincronizacion bidireccional color/hex**: La fuente de verdad es `color` (el estado). `hexInput` es un estado separado para permitir la edicion intermedia del texto sin disparar updates del swatch con cada tecla. La funcion `handleHexChange` actualiza `hexInput` siempre y `color` solo si el HEX es valido.

5. **`onBack` no tiene animacion propia en este componente**: `Odontogram.tsx` responde al `onBack` cerrando `StateConditionModal` (via `setConditionModalOpen(false)`) y abriendo `SymbolSelectorModal` (via `setSymbolModalOpen(true)`). Las animaciones de salida e entrada son manejadas por cada componente respectivamente basado en su prop `isOpen`.

6. **Testiabilidad**: El boton "Aplicar" `data-testid="condition-apply"`. Los botones de condicion `data-testid="condition-btn-bueno"`, `"condition-btn-malo"`, `"condition-btn-indefinido"`. El swatch `data-testid="color-swatch"`. El input HEX `data-testid="hex-input"`. Los presets `data-testid={`color-preset-${preset}`}`.

7. **Texto "Configurar:"**: Usar la clave i18n `odontogram.condition_modal.title_prefix` (valor: `"Configurar:"`) seguido del `stateName` que viene como prop. No concatenar directamente con template string para mantener compatibilidad con los 3 idiomas.
