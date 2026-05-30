# Spec: surface-selection

**Change:** odontogram-v2-complete
**Spec ID:** SPEC-SS
**Tipo:** Frontend
**Prioridad:** P1
**Dependencia:** `data-model-evolution` (formato v3.0 con superficies por pieza), `dentition-tabs` (arquitectura de componentes)
**Estado:** Borrador
**Fecha:** 2026-04-02

---

## 1. Resumen

El odontograma actual renderiza las 5 superficies SVG de cada pieza (vestibular, distal, lingual, mesial, oclusal) como decoracion visual — todas comparten el mismo estado del diente y ninguna es clickeable individualmente. Esta spec hace que **cada superficie sea un target de click independiente** con su propio estado, color y logica de seleccion.

La interaccion tiene dos niveles: (1) click en una pieza la selecciona globalmente; (2) click en una superficie dentro de la pieza seleccionada la resalta e inicia el flujo de asignacion de estado para esa superficie especifica. Esto permite, por ejemplo, marcar "caries" solo en la superficie oclusal de la pieza 36 mientras el resto permanece "healthy".

Se extrae el nuevo componente `SurfacePath.tsx` para encapsular la logica de una superficie SVG individual clickeable.

---

## 2. Requisitos funcionales

### REQ-SS-01 — Superficies independientes por diente
Cada pieza dental DEBE tener 5 superficies independientes: `buccal` (top), `distal` (right), `lingual` (bottom), `mesial` (left), `occlusal` (center). Cada superficie puede tener un estado diferente del catalogo.

### REQ-SS-02 — Interaccion de dos niveles
El flujo de seleccion DEBE seguir exactamente este orden:
- **Nivel 1 (seleccion de pieza):** Click en cualquier parte de una pieza no seleccionada → la pieza se selecciona (anillo azul animado). Las superficies aun no son clickeables.
- **Nivel 2 (seleccion de superficie):** Dentro de la pieza seleccionada → click en una superficie especifica → esa superficie se resalta y se abre el selector de estado.

### REQ-SS-03 — Superficie hover en pieza seleccionada
Cuando una pieza esta seleccionada, las 5 superficies DEBEN mostrar estado hover visual al pasar el cursor sobre ellas (escala 1.05 en el path SVG, duracion 200ms) para indicar que son clickeables.

### REQ-SS-04 — Resaltado de superficie seleccionada
La superficie seleccionada (despues del click nivel 2) DEBE diferenciarse visualmente mediante:
- `stroke-width` aumentado de 1 a 2.5
- Un glow sutil del color del estado actual de esa superficie (`drop-shadow` de 4px)
- Una animacion de pulse suave en el stroke (keyframe `surfacePulse`)

### REQ-SS-05 — Colores independientes por superficie
Cada superficie DEBE renderizarse con el color de su propio estado. Si la superficie tiene `state: "healthy"`, usa los colores de `STATE_FILLS.healthy`. Si tiene `state: "caries"`, usa `STATE_FILLS.caries`. El color del estado de la pieza completa (`tooth.state`) ya no determina el color de la visualizacion — son los estados de superficie quienes mandan.

### REQ-SS-06 — Estado global del diente como fallback
Si una superficie no tiene estado propio (`surface.state` es null o undefined), DEBE heredar visualmente el estado global de la pieza (`tooth.state`). Esto garantiza retrocompatibilidad con piezas que no tienen estados por superficie.

### REQ-SS-07 — Coherencia visual cuando todas las superficies son iguales
Si las 5 superficies de un diente tienen el mismo estado, el diente DEBE verse visualmente igual que el diente actual (color uniforme). No hay diferencia perceptible con el comportamiento pre-v2.

### REQ-SS-08 — Animacion de cambio de estado por superficie
Cuando se aplica un nuevo estado a una superficie especifica, DEBE ejecutarse la animacion `toothPop` (ya existente) sobre ESA SUPERFICIE, no sobre el diente completo. El resto de las superficies no se animan.

### REQ-SS-09 — Lineas divisorias entre superficies
Las 4 lineas `<line>` que dividen las superficies del diente DEBEN hacerse mas visibles cuando la pieza esta seleccionada:
- Pieza no seleccionada: `opacity: 0.25`, `stroke-width: 0.6` (igual que ahora)
- Pieza seleccionada: `opacity: 0.6`, `stroke-width: 0.8`

### REQ-SS-10 — Indicador de superficie activa en el selector de estado
Cuando una superficie esta seleccionada, el selector de estado (panel de estados o modal) DEBE mostrar un indicador de que superficie se esta editando (ej: "Superficie: Oclusal · Pieza 3.6").

### REQ-SS-11 — Deseleccion de superficie al cambiar pieza
Si el usuario hace click en otra pieza mientras hay una superficie seleccionada, la seleccion de superficie DEBE limpiarse. La nueva pieza pasa a Nivel 1 (pieza seleccionada, superficie no seleccionada aun).

### REQ-SS-12 — Mobile: zoom interactivo en pieza seleccionada
En viewports menores a 768px (`< md` en Tailwind), al seleccionar una pieza DEBE aparecer un panel flotante que muestra la pieza ampliada (2.5x-3x), con las 5 superficies claramente diferenciadas y sus labels. El usuario hace tap en la superficie dentro del panel y el panel se cierra al aplicar el estado. El panel aparece cerca de la pieza seleccionada (posicionado con `getBoundingClientRect()`).

### REQ-SS-13 — Superficie oclusal (circulo central)
La superficie oclusal es el circulo central (`cx=20, cy=20, r=7`). DEBE ser un elemento `<circle>` con el mismo sistema de click, hover, y glow que los paths de las superficies externas.

### REQ-SS-14 — Modo readOnly
En `readOnly={true}`, las superficies muestran sus colores pero no responden a ningun evento de click ni muestran hover. El cursor es `cursor-default`.

### REQ-SS-15 — Propagacion de eventos SVG
Los eventos `onClick` en los elementos SVG de superficie DEBEN llamar a `event.stopPropagation()` para no activar el `onClick` del SVG padre (que cambia la seleccion de pieza).

---

## 3. Detalle tecnico

### 3.1. Mapa de superficies

| Path SVG | Nombre anatomico | Key en datos |
|----------|-----------------|--------------|
| `top` (vestibular/buccal) | Vestibular / Bucal | `buccal` |
| `right` (distal) | Distal | `distal` |
| `bottom` (lingual/palatino) | Lingual / Palatino | `lingual` |
| `left` (mesial) | Mesial | `mesial` |
| `center` (oclusal/incisal) | Oclusal / Incisal | `occlusal` |

### 3.2. Estructura de datos de superficie (v3.0)

```typescript
// Desde data-model-evolution
interface SurfaceState {
  state: ToothStatus;       // del catalogo expandido
  condition: 'bueno' | 'malo' | 'indefinido' | null;
  color: string | null;     // HEX custom o null (usa default_color del catalogo)
}

interface ToothSurfaces {
  buccal:   SurfaceState | null;
  distal:   SurfaceState | null;
  lingual:  SurfaceState | null;
  mesial:   SurfaceState | null;
  occlusal: SurfaceState | null;
}

interface ToothState {
  id: number;
  state: ToothStatus;        // estado global (fallback y retrocompat)
  surfaces: ToothSurfaces;
  notes?: string;
}
```

### 3.3. Componente `SurfacePath.tsx`

```typescript
// Ubicacion: frontend_react/src/components/odontogram/SurfacePath.tsx

type SurfaceKey = 'buccal' | 'distal' | 'lingual' | 'mesial' | 'occlusal';

interface SurfacePathProps {
  surfaceKey: SurfaceKey;
  path?: string;              // para los 4 paths externos; undefined para oclusal (usa <circle>)
  surfaceState: SurfaceState | null;
  fallbackToothState: ToothStatus;
  isToothSelected: boolean;
  isSurfaceSelected: boolean;
  isAbsent: boolean;          // para pieza extraction/missing → opacity 0.35
  readOnly: boolean;
  onClick: (e: React.MouseEvent, surface: SurfaceKey) => void;
  onMouseEnter?: () => void;
  onMouseLeave?: () => void;
  justChanged: boolean;       // trigger animacion toothPop
}
```

**Logica de color:**
```typescript
function resolveSurfaceFill(
  surfaceState: SurfaceState | null,
  fallback: ToothStatus
): { fill: string; stroke: string; glow: string } {
  const effectiveState = surfaceState?.state ?? fallback;
  const fills = STATE_FILLS[effectiveState] ?? STATE_FILLS.healthy;
  // Si tiene color custom en surfaceState.color, sobreescribe el fill
  if (surfaceState?.color) {
    const hex = surfaceState.color;
    return {
      fill: `${hex}1F`,      // hex + 12% opacidad
      stroke: hex,
      glow: `drop-shadow(0 0 4px ${hex}4D)`,
    };
  }
  return fills;
}
```

**Rendering del `<path>` (superficies buccal/distal/lingual/mesial):**
```tsx
<path
  d={path}
  fill={resolved.fill}
  stroke={resolved.stroke}
  strokeWidth={isSurfaceSelected ? 2.5 : 1}
  opacity={isAbsent ? 0.35 : 0.9}
  style={{
    filter: isSurfaceSelected ? resolved.glow : undefined,
    cursor: (readOnly || !isToothSelected) ? 'default' : 'pointer',
    transition: 'all 200ms ease-out',
    transform: (isToothSelected && !readOnly) ? 'scale(1)' : undefined,
  }}
  className={`
    transition-all duration-200
    ${justChanged ? 'animate-[toothPop_0.4s_ease-out]' : ''}
    ${(isToothSelected && !readOnly) ? 'hover:scale-[1.05]' : ''}
    ${isSurfaceSelected ? 'animate-[surfacePulse_2s_ease-in-out_infinite]' : ''}
  `}
  onClick={!readOnly ? (e) => { e.stopPropagation(); onClick(e, surfaceKey); } : undefined}
/>
```

**Rendering del `<circle>` (oclusal):**
Mismo patron pero con `cx=20 cy=20 r=7` y sin `d` prop.

### 3.4. Estado de seleccion de superficie en `Odontogram.tsx`

**Estado nuevo:**
```typescript
const [selectedSurface, setSelectedSurface] = useState<SurfaceKey | null>(null);
const [changedSurfaces, setChangedSurfaces] = useState<Map<number, Set<SurfaceKey>>>(new Map());
```

**Handler de click en superficie:**
```typescript
const handleSurfaceClick = (toothId: number, surface: SurfaceKey) => {
  if (readOnly) return;
  if (selectedTooth !== toothId) {
    // Nivel 1: seleccionar pieza primero
    setSelectedTooth(toothId);
    setSelectedSurface(null);
    return;
  }
  // Nivel 2: seleccionar superficie
  setSelectedSurface(surface);
  // Abrir modal de seleccion de estado (SymbolSelectorModal) — cubierto por spec symbol-selector-modal
  setModalOpen(true);
};
```

**Handler de click en pieza (nivel 1 — click en el SVG completo, no en superficie):**
```typescript
const handleToothClick = (toothId: number) => {
  if (readOnly) return;
  if (selectedTooth === toothId) {
    // Ya estaba seleccionada: no hace nada (el usuario debe clickear superficie)
    return;
  }
  setSelectedTooth(toothId);
  setSelectedSurface(null);  // limpiar superficie al cambiar pieza
};
```

**Aplicar estado a superficie:**
```typescript
const applyStateToSurface = (
  toothId: number,
  surface: SurfaceKey,
  state: ToothStatus,
  condition: 'bueno' | 'malo' | 'indefinido' | null,
  color: string | null
) => {
  const setter = activeDentition === 'permanent' ? setPermanentTeeth : setDecidousTeeth;
  setter(prev => prev.map(tooth => {
    if (tooth.id !== toothId) return tooth;
    return {
      ...tooth,
      surfaces: {
        ...tooth.surfaces,
        [surface]: { state, condition, color },
      },
      // Actualizar state global: si todas las superficies tienen el mismo estado, sintetizar
      state: computeGlobalState({ ...tooth.surfaces, [surface]: { state, condition, color } }),
    };
  }));
  // Marcar superficie como recien-cambiada para la animacion
  setChangedSurfaces(prev => {
    const next = new Map(prev);
    const toothSurfaces = new Set(prev.get(toothId) ?? []);
    toothSurfaces.add(surface);
    next.set(toothId, toothSurfaces);
    return next;
  });
  setTimeout(() => {
    setChangedSurfaces(prev => {
      const next = new Map(prev);
      const toothSurfaces = new Set(prev.get(toothId) ?? []);
      toothSurfaces.delete(surface);
      if (toothSurfaces.size === 0) next.delete(toothId);
      else next.set(toothId, toothSurfaces);
      return next;
    });
  }, 500);
};
```

**`computeGlobalState`:** si todas las superficies tienen el mismo `state` → ese es el `tooth.state`. Si son mixtas → `"healthy"` como fallback (el estado "real" es por superficie). Este campo se mantiene por retrocompatibilidad con el renderer SVG y Nova.

### 3.5. Modificaciones en `ToothSVG`

`ToothSVG` recibe nuevos props y delega el rendering de cada path a `SurfacePath`:

```typescript
interface ToothSVGProps {
  // existentes:
  toothId: number;
  state: ToothStatus;
  isSelected: boolean;
  readOnly: boolean;
  onClick: () => void;
  justChanged: boolean;
  // nuevos:
  surfaces: ToothSurfaces;
  selectedSurface: SurfaceKey | null;
  changedSurfaces: Set<SurfaceKey>;
  onSurfaceClick: (surface: SurfaceKey) => void;
}
```

El SVG padre (`<svg>`) mantiene su `onClick` para Nivel 1 (seleccion de pieza). Los `<SurfacePath>` internos llaman `e.stopPropagation()` antes de propagar a `onSurfaceClick` para no disparar el click del SVG padre cuando ya se está en Nivel 2.

### 3.6. Panel de zoom mobile (`MobileToothZoom.tsx`)

```typescript
// Ubicacion: frontend_react/src/components/odontogram/MobileToothZoom.tsx

interface MobileToothZoomProps {
  toothId: number;
  surfaces: ToothSurfaces;
  toothState: ToothStatus;
  position: { top: number; left: number };  // calculado con getBoundingClientRect
  onSurfaceClick: (surface: SurfaceKey) => void;
  onClose: () => void;
}
```

**Rendering:** Un `<div>` `fixed` con `z-50`, background `bg-[#0d1117]/95`, `backdrop-blur-xl`, `border border-white/[0.12]`, `rounded-2xl`, `p-4`. Contiene:
1. Label de la pieza seleccionada ("Pieza 3.6")
2. Un `<svg>` de 120x120 (3x el original 40x40) con los 5 `SurfacePath` ampliados
3. Labels de cada superficie en el borde (textos: "V", "D", "L", "M", "O")
4. Boton "✕" para cerrar sin seleccionar

**Activacion:** Solo en `window.innerWidth < 768`. Se desmonta al seleccionar una superficie o al presionar cerrar.

**Posicionamiento:** Calcula si el panel cabe abajo o arriba del diente usando `getBoundingClientRect` + `window.innerHeight`.

### 3.7. Animaciones nuevas (agregar al `<style>` del componente)

```css
@keyframes surfacePulse {
  0%, 100% { stroke-width: 2.5; opacity: 0.9; }
  50%       { stroke-width: 3.0; opacity: 1.0; }
}

@keyframes surfacePop {
  0%   { transform: scale(1); }
  30%  { transform: scale(1.15); }
  60%  { transform: scale(0.97); }
  100% { transform: scale(1); }
}
```

`surfacePulse` se aplica al `<SurfacePath>` cuando `isSurfaceSelected=true`.
`surfacePop` reemplaza a `toothPop` cuando `justChanged=true` en `SurfacePath` (efecto en superficie individual, no en el SVG padre).

---

## 4. Escenarios

### Escenario 1 — Click en pieza no seleccionada → Nivel 1
**Dado** que no hay ninguna pieza seleccionada
**Cuando** el clinico hace click en la pieza 36
**Entonces** la pieza 36 se selecciona (anillo azul animado, escala 1.15)
**Y** el selector de estado muestra "Pieza 3.6" en el header
**Y** NO se abre ningun modal de superficie
**Y** las superficies de la pieza 36 muestran hover al pasar el cursor

### Escenario 2 — Click en superficie → Nivel 2
**Dado** que la pieza 36 ya esta seleccionada (Nivel 1)
**Cuando** el clinico hace click sobre la superficie superior (vestibular/buccal)
**Entonces** esa superficie se resalta (stroke-width 2.5, glow del color actual)
**Y** el header indica "Superficie: Vestibular · Pieza 3.6"
**Y** se abre el modal de seleccion de estado (SymbolSelectorModal)

### Escenario 3 — Aplicar estado a superficie individual
**Dado** que la superficie vestibular de la pieza 36 esta seleccionada (Nivel 2)
**Y** el modal de estados esta abierto
**Cuando** el clinico selecciona "caries" y confirma
**Entonces** SOLO la superficie vestibular de la pieza 36 pasa a color rojo
**Y** las demas superficies de la pieza 36 permanecen en su estado anterior
**Y** se ejecuta la animacion `surfacePop` solo en la superficie vestibular
**Y** el modal se cierra

### Escenario 4 — Colores independientes por superficie en el mismo diente
**Dado** que la pieza 36 tiene:
  - Vestibular: caries (rojo)
  - Oclusal: restoration (azul)
  - Resto: healthy (gris)
**Cuando** se renderiza el SVG de la pieza 36
**Entonces** el path superior (vestibular) es rojo
**Y** el circulo central (oclusal) es azul
**Y** los otros 3 paths son grises (healthy)

### Escenario 5 — Fallback a estado global del diente
**Dado** que una pieza importada de datos v2.0 tiene `state: "crown"` y `surfaces: {}`
**Cuando** se renderiza esa pieza
**Entonces** las 5 superficies se muestran con el color de "crown" (violeta)
**Y** la pieza se ve identica al comportamiento de la v1

### Escenario 6 — Cambiar pieza limpia superficie seleccionada
**Dado** que la superficie oclusal de la pieza 36 esta seleccionada (Nivel 2)
**Cuando** el clinico hace click en la pieza 11
**Entonces** la seleccion de superficie de la pieza 36 se limpia
**Y** la pieza 11 pasa a Nivel 1 (seleccionada, sin superficie activa)
**Y** el anillo azul se mueve a la pieza 11

### Escenario 7 — stopPropagation en superficie seleccionada
**Dado** que la pieza 36 esta seleccionada (Nivel 1) y el clinico hace click en la superficie vestibular
**Cuando** el evento se procesa
**Entonces** `handleSurfaceClick` se ejecuta
**Y** `handleToothClick` (el handler del SVG padre) NO se ejecuta por segunda vez

### Escenario 8 — Lineas divisorias mas visibles al seleccionar pieza
**Dado** que ninguna pieza esta seleccionada
**Cuando** el clinico selecciona la pieza 36
**Entonces** las 4 lineas divisorias dentro de la pieza 36 pasan de opacity 0.25 a 0.6

### Escenario 9 — Mobile: panel de zoom al seleccionar pieza
**Dado** que el viewport es 375px de ancho (iPhone SE)
**Y** el clinico hace tap en la pieza 36 (Nivel 1)
**Entonces** aparece un panel flotante `MobileToothZoom` cerca de la pieza
**Y** el panel muestra la pieza amplificada a 3x
**Y** los labels de superficie son legibles ("V", "D", "L", "M", "O")
**Cuando** el clinico toca la superficie "Oclusal" en el panel
**Entonces** el panel se cierra
**Y** se activa el Nivel 2 con la superficie oclusal seleccionada
**Y** se abre el SymbolSelectorModal

### Escenario 10 — Mobile: panel no aparece en desktop
**Dado** que el viewport es 1280px de ancho
**Cuando** el clinico selecciona la pieza 36
**Entonces** NO aparece el panel `MobileToothZoom`
**Y** el clinico puede clickear directamente en las superficies del SVG

### Escenario 11 — readOnly no permite click en superficie
**Dado** que el componente tiene `readOnly={true}`
**Y** la pieza 36 tiene caries en la superficie vestibular
**Cuando** el clinico hace click o tap sobre la superficie vestibular
**Entonces** no ocurre ninguna accion
**Y** no se abre ningun modal
**Y** la pieza muestra sus colores correctamente (solo lectura visual)

### Escenario 12 — Animacion surfacePop solo en superficie modificada
**Dado** que la pieza 36 tiene oclusal en "healthy"
**Cuando** el clinico cambia oclusal a "caries"
**Entonces** solo el circulo central (oclusal) ejecuta la animacion `surfacePop` (350ms)
**Y** los paths externos (vestibular, mesial, distal, lingual) NO se animan

---

## 5. Criterios de aceptacion

| ID | Criterio | Verificacion |
|----|----------|--------------|
| CA-SS-01 | Cada una de las 5 superficies responde a click independiente | Test de evento por superficie |
| CA-SS-02 | Click en pieza no seleccionada → Nivel 1 (no abre modal) | Test de flujo de interaccion |
| CA-SS-03 | Click en superficie de pieza seleccionada → Nivel 2 (abre selector) | Test de flujo de interaccion |
| CA-SS-04 | Cada superficie renderiza con el color de su estado propio | Snapshot test / inspeccion visual |
| CA-SS-05 | Superficie sin estado propio hereda el estado global de la pieza | Test de retrocompatibilidad |
| CA-SS-06 | `event.stopPropagation()` previene doble-disparo del SVG padre | Test de propagacion de eventos |
| CA-SS-07 | `isSurfaceSelected=true` aplica `stroke-width: 2.5` y `surfacePulse` | Inspeccion de atributos SVG |
| CA-SS-08 | Animacion `surfacePop` se ejecuta SOLO en la superficie modificada | Inspeccion visual + test de clases |
| CA-SS-09 | Cambiar pieza limpia la superficie seleccionada del estado | Test de estado interno |
| CA-SS-10 | En mobile (< 768px), aparece `MobileToothZoom` al seleccionar pieza | Test de responsive con jsdom resize |
| CA-SS-11 | Panel `MobileToothZoom` cierra al seleccionar superficie o presionar ✕ | Test de ciclo de vida del componente |
| CA-SS-12 | En `readOnly`, superficie no responde a click ni muestra hover cursor | Test de evento + inspeccion CSS |
| CA-SS-13 | Lineas divisorias son mas opacas cuando la pieza esta seleccionada | Inspeccion visual de atributo `opacity` |
| CA-SS-14 | 5 dientes con estados mixtos por superficie se renderizan sin degradacion de performance | Profiling React DevTools (< 16ms por render) |
| CA-SS-15 | No hay regreson en piezas con estado global unificado (se ven igual que antes) | Test de regresion E2E |

---

## 6. Archivos afectados

| Archivo | Cambio |
|---------|--------|
| `frontend_react/src/components/Odontogram.tsx` | Nuevo estado (`selectedSurface`, `changedSurfaces`), `handleSurfaceClick`, `applyStateToSurface`, `computeGlobalState`, pasar nuevos props a `ToothSVG` |
| `frontend_react/src/components/odontogram/SurfacePath.tsx` | **NUEVO** — Superficie SVG clickeable con hover, selection highlight, animacion individual, `stopPropagation` |
| `frontend_react/src/components/odontogram/MobileToothZoom.tsx` | **NUEVO** — Panel flotante para mobile con pieza amplificada 3x |
| `frontend_react/src/components/odontogram/constants.ts` | **NUEVO** (compartido con `dentition-tabs`) — `SURFACE_PATHS`, `SURFACE_KEYS`, `SURFACE_LABELS` |
| `frontend_react/src/locales/es.json` | Agregar claves de superficies: `odontogram.surfaces.buccal`, `.distal`, `.lingual`, `.mesial`, `.occlusal`, `odontogram.selecting_surface` |
| `frontend_react/src/locales/en.json` | Idem en ingles |
| `frontend_react/src/locales/fr.json` | Idem en frances |

**Archivos que se modifican en `ToothSVG` (inline o extraido):**
- Si `ToothSVG` permanece inline en `Odontogram.tsx`: se modifica esa seccion del archivo.
- Si se extrae a `frontend_react/src/components/odontogram/ToothSVG.tsx`: se crea ese archivo.

---

## 7. Dependencias

### Dependencias previas (deben estar completas antes de implementar esta spec)

| Spec | Razon |
|------|-------|
| `data-model-evolution` | Define `ToothSurfaces` con `SurfaceState` (state + condition + color) que `SurfacePath` lee para resolver su fill/stroke |
| `dentition-tabs` | Establece la arquitectura de componentes (`DentitionChart`, directorio `odontogram/`). `SurfacePath` se crea en ese directorio. `Odontogram.tsx` ya tiene el estado `activeDentition` que `applyStateToSurface` necesita para saber en que array guardar |

### Specs que dependen de esta (se implementan despues)

| Spec | Razon |
|------|-------|
| `symbol-selector-modal` | Necesita que `SurfacePath` dispare `onSurfaceClick` para abrirse. El modal recibe `surface` y `toothId` como contexto |
| `state-condition-color` | Modal secundario que se abre despues del `SymbolSelectorModal`. Llama `applyStateToSurface` con la condicion y el color |
| `svg-pdf-renderer` | Necesita renderizar superficies con colores individuales; depende del modelo de datos que esta spec escribe via `applyStateToSurface` |

### Dependencias tecnicas

| Dependencia | Version | Uso |
|-------------|---------|-----|
| React | 18.x | `useState`, `useRef`, `useEffect` (para posicionamiento del zoom panel) |
| Tailwind CSS | 3.x | Clases de layout del `MobileToothZoom` |
| SVG nativo | Browser | Paths y circle; no se requieren librerias externas |

---

## Notas de implementacion

1. **`stopPropagation` es critico:** Sin esto, un click en superficie en Nivel 2 tambien dispara el `onClick` del SVG padre y pasa al Nivel 1 de nuevo. Verificar en tests con `userEvent.click` de Testing Library.

2. **`transform-origin` en SVG paths:** Los browsers aplican `transform-origin: 50% 50%` por defecto en SVG, pero en algunos browsers esto se interpreta relativo al viewport, no al elemento. Para el hover `scale(1.05)` de cada superficie, usar `style={{ transformOrigin: 'center' }}` o `transform-box: fill-box` en CSS.

3. **`computeGlobalState` es una heuristica:** El estado global del diente se usa como fallback para Nova y el PDF renderer. La logica sugerida: si todas las superficies no-null tienen el mismo estado → ese estado; si hay mezcla → "healthy" (el estado real se lee por superficie). No es un campo critico, no debe romper el flujo si la heuristica es imperfecta.

4. **Mobile zoom — posicion:** Calcular `getBoundingClientRect` del elemento SVG en el `useEffect` al activarse. Si `top + 200 > window.innerHeight`, posicionar arriba del diente. Si `left + 160 > window.innerWidth`, alinear a la derecha.

5. **Orden de implementacion dentro de la spec:** Implementar primero sin `MobileToothZoom` (desktop funcional), agregar el zoom panel como ultimo paso. Facilita el testing incremental.

6. **`changedSurfaces` como `Map<number, Set<SurfaceKey>>`:** Permite marcar multiples superficies de multiples dientes como "recien cambiadas" simultaneamente sin colisiones. Limpiar con `setTimeout(500)` igual que `changedTeeth` existente.

7. **No eliminar `toothPop`:** La animacion `toothPop` existente en el SVG padre se mantiene para cuando se aplica un estado global al diente (feature de retrocompatibilidad). `surfacePop` es adicional para cambios por superficie.
