# Spec: dentition-tabs

**Change:** odontogram-v2-complete
**Spec ID:** SPEC-DT
**Tipo:** Frontend
**Prioridad:** P1
**Dependencia:** `data-model-evolution` (formato v3.0 con `permanent.teeth` y `deciduous.teeth`)
**Estado:** Borrador
**Fecha:** 2026-04-02

---

## 1. Resumen

El odontograma actual de ClinicForge renderiza exclusivamente la denticion permanente (32 piezas FDI 11-48). Esta spec introduce un sistema de **tabs de denticion** que permite al clinico alternar entre la vista Permanente y la vista Temporal (decidua, 20 piezas FDI 51-85), con datos independientes por denticion y persistencia del tab activo en el formato v3.0 del odontograma.

El cambio refactoriza `Odontogram.tsx` en un orquestador liviano y extrae dos nuevos componentes: `OdontogramTabs.tsx` (la barra de tabs) y `DentitionChart.tsx` (el renderizador generico de cuadrantos que sirve tanto para permanente como temporal).

---

## 2. Requisitos funcionales

### REQ-DT-01 — Tabs de seleccion de denticion
El odontograma DEBE mostrar dos tabs encima del chart: **"Permanente"** (izquierda) y **"Temporal"** (derecha). El tab activo por defecto es "Permanente".

### REQ-DT-02 — Layout de denticion temporal
El tab "Temporal" DEBE renderizar 20 piezas deciduas distribuidas en 4 cuadrantes:
- Superior derecho: `[55, 54, 53, 52, 51]` (5 piezas, orden derecha a izquierda)
- Superior izquierdo: `[61, 62, 63, 64, 65]` (5 piezas, orden izquierda a derecha)
- Inferior derecho: `[85, 84, 83, 82, 81]` (5 piezas, orden derecha a izquierda)
- Inferior izquierdo: `[71, 72, 73, 74, 75]` (5 piezas, orden izquierda a derecha)

### REQ-DT-03 — Independencia de datos por denticion
Los estados de las piezas de la denticion permanente y temporal son completamente independientes. Modificar una pieza en "Temporal" NO afecta los datos de "Permanente" y viceversa.

### REQ-DT-04 — Persistencia del tab activo
El tab que el usuario tiene activo al momento de guardar se persiste en el campo `active_dentition` del formato v3.0: `"permanent"` o `"deciduous"`. Al recargar el odontograma, el tab guardado se restaura automáticamente.

### REQ-DT-05 — Formato FDI para piezas temporales
Las piezas temporales DEBEN mostrar su label FDI formateado con punto (ej: pieza 51 → "5.1", pieza 85 → "8.5"). La funcion `fdiLabel(id)` existente es válida para ambas denticiones.

### REQ-DT-06 — Animacion de transicion entre tabs
Al cambiar de tab DEBE haber una transicion de slide horizontal suave. El tab nuevo entra desde la direccion del tab seleccionado (de derecha si se activa "Temporal", de izquierda si se vuelve a "Permanente").

### REQ-DT-07 — Compatibilidad con datos existentes (migracion on-read)
Si `initialData` contiene un array plano `teeth` (formato v2.0, solo permanente), el componente DEBE interpretar esos datos como la denticion permanente y mostrar la denticion temporal con todas las piezas en estado "healthy".

### REQ-DT-08 — Odontograma vacio
Si no hay `initialData`, ambas denticiones DEBEN inicializarse con todas las piezas en estado `"healthy"`.

### REQ-DT-09 — Indicador de contenido en tab no activo
Si la denticion no activa tiene al menos una pieza con estado diferente de "healthy", el tab correspondiente DEBE mostrar un indicador visual (punto azul) que notifica al usuario que hay datos en esa vista.

### REQ-DT-10 — Modo readOnly
En `readOnly={true}`, los tabs son visibles y navegables (el clinico puede revisar ambas denticiones) pero no se puede modificar ninguna pieza.

### REQ-DT-11 — Touch-friendly
Los tabs DEBEN tener una altura minima de 44px en mobile para cumplir el estandar de toque accesible (WCAG 2.5.5). El ancho minimo de cada tab es de 120px.

### REQ-DT-12 — Estado guardado refleja denticion activa
El boton "Guardar" guarda AMBAS denticiones simultaneamente en formato v3.0. El campo `active_dentition` refleja el tab que esta activo al momento de presionar guardar.

---

## 3. Detalle tecnico

### 3.1. Arquitectura de componentes

```
Odontogram.tsx (orquestador)
  ├── OdontogramTabs.tsx            — Tab bar: "Permanente" / "Temporal"
  └── DentitionChart.tsx            — Renderiza N dientes en layout de cuadrantes
      └── ToothSVG (existente)      — SVG individual por pieza
```

**Principio:** `DentitionChart` es completamente agnóstico a la denticion. Recibe un array de `QuadrantConfig` y renderiza las filas sin saber si son piezas 11-48 o 51-85.

### 3.2. Componente `OdontogramTabs.tsx`

```typescript
// Ubicacion: frontend_react/src/components/odontogram/OdontogramTabs.tsx

type DentitionType = 'permanent' | 'deciduous';

interface OdontogramTabsProps {
  active: DentitionType;
  onChange: (dentition: DentitionType) => void;
  hasDataPermanent: boolean;    // para mostrar el indicador de contenido
  hasDataDeciduous: boolean;
  readOnly?: boolean;
}
```

**Estado interno:** ninguno — componente completamente controlado por el padre.

**Rendering:** Dos botones `<button>` con `role="tab"` y `aria-selected`. El indicador de contenido es un `<span>` de 6px con `bg-blue-400` y `rounded-full`.

### 3.3. Componente `DentitionChart.tsx`

```typescript
// Ubicacion: frontend_react/src/components/odontogram/DentitionChart.tsx

interface QuadrantConfig {
  ids: number[];
  position: 'upper-right' | 'upper-left' | 'lower-right' | 'lower-left';
  numbersBelow: boolean;  // superior = false, inferior = true
}

interface DentitionChartProps {
  quadrants: QuadrantConfig[];
  teeth: ToothState[];
  selectedTooth: number | null;
  changedTeeth: Set<number>;
  readOnly: boolean;
  onToothClick: (toothId: number) => void;
}
```

**Rendering:** El componente arma el layout de cuadrantes genericamente. Divide el array de quadrants en dos filas (upper, lower) y aplica el separador vertical y el separador de mandibula de la misma forma que el codigo actual.

**Extraido de:** la funcion `renderTeethRow` actual mas el layout del `<div>` de cuadrantes en `Odontogram.tsx` (lineas 282-416).

### 3.4. Modificaciones en `Odontogram.tsx`

**Estado nuevo:**
```typescript
const [activeDentition, setActiveDentition] = useState<'permanent' | 'deciduous'>(
  initialData?.active_dentition ?? 'permanent'
);
const [permanentTeeth, setPermanentTeeth] = useState<ToothState[]>([]);
const [deciduousTeeth, setDecidousTeeth] = useState<ToothState[]>([]);
```

**Inicializacion (useEffect con `initialData`):**
```typescript
// v3.0
if (initialData?.version === '3.0') {
  setPermanentTeeth(initialData.permanent.teeth);
  setDecidousTeeth(initialData.deciduous.teeth);
  setActiveDentition(initialData.active_dentition ?? 'permanent');
}
// v2.0 migration (array plano)
else if (initialData?.teeth) {
  setPermanentTeeth(initialData.teeth);
  setDecidousTeeth(ALL_DECIDUOUS.map(id => ({ id, state: 'healthy', surfaces: {}, notes: '' })));
}
// Sin datos
else {
  setPermanentTeeth(ALL_PERMANENT.map(id => ({ id, state: 'healthy', surfaces: {}, notes: '' })));
  setDecidousTeeth(ALL_DECIDUOUS.map(id => ({ id, state: 'healthy', surfaces: {}, notes: '' })));
}
```

**Cuadrantes para denticion temporal:**
```typescript
const DECIDUOUS_UPPER_RIGHT: number[] = [55, 54, 53, 52, 51];
const DECIDUOUS_UPPER_LEFT:  number[] = [61, 62, 63, 64, 65];
const DECIDUOUS_LOWER_RIGHT: number[] = [85, 84, 83, 82, 81];
const DECIDUOUS_LOWER_LEFT:  number[] = [71, 72, 73, 74, 75];
const ALL_DECIDUOUS = [...DECIDUOUS_UPPER_RIGHT, ...DECIDUOUS_UPPER_LEFT,
                       ...DECIDUOUS_LOWER_RIGHT, ...DECIDUOUS_LOWER_LEFT];
```

**Serialización al guardar:**
```typescript
const odontogramData = {
  version: '3.0',
  last_updated: new Date().toISOString(),
  active_dentition: activeDentition,
  permanent: { teeth: permanentTeeth },
  deciduous: { teeth: deciduousTeeth },
};
```

**Seleccion de datos activos:** Las funciones `handleToothClick`, `handleStateChange`, y `handleReset` operan sobre el setter del estado activo (`activeDentition === 'permanent' ? setPermanentTeeth : setDecidousTeeth`).

### 3.5. Logica `hasData` para indicador de tab

```typescript
const hasDataPermanent = permanentTeeth.some(t => t.state !== 'healthy');
const hasDataDeciduous = deciduousTeeth.some(t => t.state !== 'healthy');
```

### 3.6. Animacion de transicion

Se usa `overflow-hidden` en el contenedor del chart y una clase de `transform/translate` que cambia segun la direccion del tab. Implementado con `useState<'left'|'right'|null>(null)` para la direccion de la transicion.

```css
/* En el <style> del componente — ya existe ese bloque */
@keyframes slideInFromRight {
  from { transform: translateX(100%); opacity: 0; }
  to   { transform: translateX(0);    opacity: 1; }
}
@keyframes slideInFromLeft {
  from { transform: translateX(-100%); opacity: 0; }
  to   { transform: translateX(0);     opacity: 1; }
}
```

La animacion se aplica por 300ms, luego se limpia el estado de animacion.

### 3.7. Estilos de los tabs

Siguiendo la paleta dark mode del proyecto:

| Estado | Clases Tailwind |
|--------|-----------------|
| Tab inactivo | `bg-white/[0.04] border-white/[0.08] text-white/50 hover:bg-white/[0.07]` |
| Tab activo | `bg-white/[0.12] border-white/[0.18] text-white` |
| Tab activo — borde inferior | `border-b-2 border-b-blue-500` |
| Contenedor tabs | `flex gap-1 p-1 bg-white/[0.03] rounded-xl border border-white/[0.06]` |

Ambos tabs tienen `font-semibold text-sm`, `px-5 py-3`, `rounded-lg`, y `transition-all duration-200`.

---

## 4. Escenarios

### Escenario 1 — Tab Temporal muestra 20 piezas en layout correcto
**Dado** que el usuario está en el odontograma de un paciente
**Y** está en el tab "Permanente" (default)
**Cuando** hace click en el tab "Temporal"
**Entonces** el chart cambia con una animacion slide-right y muestra exactamente 20 piezas
**Y** la fila superior tiene [55, 54, 53, 52, 51] | [61, 62, 63, 64, 65]
**Y** la fila inferior tiene [85, 84, 83, 82, 81] | [71, 72, 73, 74, 75]
**Y** todas las piezas están en estado "healthy" (odontograma nuevo)

### Escenario 2 — Labels FDI correctos en denticion temporal
**Dado** que el usuario está en el tab "Temporal"
**Cuando** observa la pieza con ID 51
**Entonces** el label que aparece sobre/debajo de la pieza es "5.1"
**Y** la pieza con ID 65 muestra "6.5"
**Y** la pieza con ID 85 muestra "8.5"

### Escenario 3 — Independencia de datos entre denticiones
**Dado** que el usuario está en el tab "Permanente"
**Y** marca la pieza 11 como "caries"
**Cuando** cambia al tab "Temporal"
**Entonces** ninguna pieza temporal tiene el estado "caries"
**Cuando** vuelve al tab "Permanente"
**Entonces** la pieza 11 sigue en estado "caries"

### Escenario 4 — Indicador de contenido en tab no activo
**Dado** que el usuario está en el tab "Temporal"
**Y** marca la pieza 51 como "restoration"
**Cuando** cambia al tab "Permanente"
**Entonces** el tab "Temporal" muestra el indicador de punto azul (hay datos)
**Y** el tab "Permanente" NO muestra indicador (si no tiene cambios)

### Escenario 5 — Guardado persiste ambas denticiones y tab activo
**Dado** que el usuario modifico la pieza 11 en "Permanente" y la pieza 51 en "Temporal"
**Y** está actualmente en el tab "Temporal"
**Cuando** presiona "Guardar"
**Entonces** la peticion PUT contiene version "3.0"
**Y** `permanent.teeth` incluye la pieza 11 con su estado modificado
**Y** `deciduous.teeth` incluye la pieza 51 con su estado modificado
**Y** `active_dentition` es "deciduous"

### Escenario 6 — Migracion on-read de datos v2.0
**Dado** que el `initialData` del paciente tiene formato v2.0 `{ "teeth": [...32 dientes...], "version": "2.0" }`
**Cuando** se monta el componente `Odontogram`
**Entonces** el tab "Permanente" muestra los 32 dientes con sus estados originales
**Y** el tab "Temporal" muestra 20 piezas todas en estado "healthy"
**Y** el indicador de contenido en el tab "Temporal" NO aparece

### Escenario 7 — readOnly permite cambiar tabs
**Dado** que el componente tiene `readOnly={true}`
**Y** el clinico está en el tab "Permanente"
**Cuando** hace click en el tab "Temporal"
**Entonces** puede ver el chart de denticion temporal
**Pero** no puede hacer click en ninguna pieza (cursor-default)

### Escenario 8 — Volver al tab Permanente tiene animacion inversa
**Dado** que el usuario está en el tab "Temporal"
**Cuando** hace click en el tab "Permanente"
**Entonces** el chart hace slide-left (entra desde la izquierda)

### Escenario 9 — Reset limpia solo la denticion activa
**Dado** que el usuario modificó piezas en ambas denticiones
**Y** está en el tab "Temporal"
**Cuando** hace click en "Reiniciar"
**Entonces** se confirma la accion con el modal de confirmacion (o se resetea directamente si no hay modal)
**Y** SOLO la denticion temporal vuelve a "healthy"
**Y** la denticion permanente mantiene sus modificaciones

### Escenario 10 — Mobile: tabs son touch-friendly
**Dado** que el usuario está en un dispositivo con pantalla de 375px (iPhone SE)
**Cuando** inspeccionamos los tabs
**Entonces** cada tab tiene una altura minima de 44px
**Y** el ancho de cada tab permite un toque cómodo (min 120px o 50% del contenedor)

---

## 5. Criterios de aceptacion

| ID | Criterio | Verificacion |
|----|----------|--------------|
| CA-DT-01 | El tab "Permanente" muestra exactamente 32 piezas en layout FDI 11-48 | Visual + test de conteo de nodos SVG |
| CA-DT-02 | El tab "Temporal" muestra exactamente 20 piezas en layout FDI 51-85 | Visual + test de conteo de nodos SVG |
| CA-DT-03 | Los labels FDI de piezas temporales usan formato `X.Y` (ej: "5.1", "8.5") | Snapshot test |
| CA-DT-04 | La transicion entre tabs tiene animacion slide horizontal visible (300ms) | Inspeccion visual |
| CA-DT-05 | Modificar pieza en un tab no altera los datos del otro tab | Test unitario de estado |
| CA-DT-06 | Guardar con tab "Temporal" activo produce JSON v3.0 con `active_dentition: "deciduous"` | Test de payload de API |
| CA-DT-07 | `initialData` v2.0 se carga correctamente como denticion permanente | Test de migracion on-read |
| CA-DT-08 | El tab no activo muestra indicador azul cuando tiene datos modificados | Test de renderizado condicional |
| CA-DT-09 | En `readOnly`, ambos tabs son navegables pero las piezas no responden a click | Test de evento |
| CA-DT-10 | Los tabs tienen altura >= 44px en viewport de 375px | Inspeccion CSS / test de layout |
| CA-DT-11 | El componente `DentitionChart` es reutilizable para ambas denticiones sin condicion `if` interna | Revision de codigo |
| CA-DT-12 | No hay regreson en la denticion permanente (layout, estados, animaciones existentes) | Test de regresion E2E |

---

## 6. Archivos afectados

| Archivo | Cambio |
|---------|--------|
| `frontend_react/src/components/Odontogram.tsx` | Refactoring mayor: nuevo estado (`activeDentition`, `permanentTeeth`, `deciduousTeeth`), inicializacion v2→v3, serialización v3.0, delegacion de render a `DentitionChart` |
| `frontend_react/src/components/odontogram/OdontogramTabs.tsx` | **NUEVO** — Tab bar controlado, indicadores de contenido |
| `frontend_react/src/components/odontogram/DentitionChart.tsx` | **NUEVO** — Renderer generico de cuadrantes, extrae `renderTeethRow` + layout de cuadrantes |
| `frontend_react/src/locales/es.json` | Agregar claves: `odontogram.tab_permanent`, `odontogram.tab_deciduous` |
| `frontend_react/src/locales/en.json` | Idem en ingles |
| `frontend_react/src/locales/fr.json` | Idem en frances |

**Archivos NO afectados por esta spec:**
- `orchestrator_service/admin_routes.py` — ya soporta JSONB libre; esta spec solo cambia el payload
- `orchestrator_service/services/odontogram_svg.py` — lo cubre `svg-pdf-renderer`
- `orchestrator_service/services/nova_tools.py` — lo cubre `nova-tools-update`

---

## 7. Dependencias

### Dependencias previas (deben estar completas antes de implementar esta spec)

| Spec | Razon |
|------|-------|
| `data-model-evolution` | Define el formato v3.0 `{ permanent: { teeth: [] }, deciduous: { teeth: [] }, active_dentition }` que esta spec consume al leer y escribir |

### Specs que dependen de esta (deben implementarse despues)

| Spec | Razon |
|------|-------|
| `surface-selection` | Necesita `DentitionChart` y la arquitectura de componentes establecida aqui para integrar `SurfacePath` |
| `symbol-selector-modal` | Necesita saber que tab esta activo para guardar el estado en la denticion correcta |
| `svg-pdf-renderer` | Necesita conocer la estructura de `permanent.teeth` y `deciduous.teeth` para renderizar dos secciones en el PDF |

### Dependencias tecnicas (librerias/APIs)

| Dependencia | Version requerida | Uso |
|-------------|-------------------|-----|
| React | 18.x (ya instalado) | `useState`, `useEffect`, `useRef` |
| Tailwind CSS | 3.x (ya instalado) | Clases de estilos |
| `useTranslation` | Context propio del proyecto | Labels de tabs con i18n |

---

## Notas de implementacion

1. **Crear directorio `/odontogram/`**: Todos los sub-componentes del odontograma van en `frontend_react/src/components/odontogram/`. El archivo `Odontogram.tsx` sigue en `components/` como punto de entrada principal (para no romper imports existentes).

2. **No duplicar `ToothSVG`**: El componente `ToothSVG` existente NO se mueve ni se duplica. `DentitionChart` lo importa directamente desde su nueva ubicacion si se mueve, o desde el archivo actual si no se mueve.

3. **`ALL_PERMANENT` y `ALL_DECIDUOUS`**: Extraer las constantes de cuadrantes a un archivo `odontogram/constants.ts` para que `DentitionChart`, `Odontogram.tsx` y los tests las importen desde un unico lugar.

4. **Indicador de contenido**: El indicador de "hay datos" se calcula en `Odontogram.tsx` (orquestador) porque tiene acceso a ambos arrays de teeth, y se pasa como props a `OdontogramTabs`.

5. **Animacion de transicion — implementacion minimalista**: Para evitar complejidad con framer-motion (no esta en el proyecto), usar un enfoque basado en `key` prop que fuerza el remontado del `DentitionChart` con una clase CSS de animacion:
   ```tsx
   <div key={activeDentition} className={`animate-[${slideDirection}_0.3s_ease-out]`}>
     <DentitionChart ... />
   </div>
   ```
