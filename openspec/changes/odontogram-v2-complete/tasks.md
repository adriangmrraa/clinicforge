# Tasks — odontogram-v2-complete

> Generado: 2026-04-02
> Change: Odontograma V2 Completo (dentición dual, 42 estados, superficies por pieza, PDF con decidua)

---

## Fase 1: Foundation — BLOQUEANTE

> Todas las tareas de fases posteriores dependen de esta fase. No comenzar Fase 2 hasta que 1.8 pase.

---

- [x] **Task 1.1: Crear shared/odontogram_utils.py** — Módulo de utilidades compartidas para parseo y construcción de datos de odontograma `(L)`
  - Files: `shared/odontogram_utils.py`
  - Spec: `specs/data-model-evolution/spec.md`
  - Depends on: —
  - AC:
    - `normalize_to_v3(raw)` acepta dicts con formato v1, v2 o v3 y siempre devuelve estructura v3.0 válida
    - `build_default_permanent()` retorna 32 piezas FDI 11–48 en estado "sano"
    - `build_default_deciduous()` retorna 20 piezas FDI 51–85 en estado "sano"

---

- [x] **Task 1.2: Crear modelos Pydantic v3.0 en shared/odontogram_utils.py** — Definir los tipos de datos canónicos del odontograma v3.0 `(M)`
  - Files: `shared/odontogram_utils.py`
  - Spec: `specs/data-model-evolution/spec.md`
  - Depends on: Task 1.1
  - AC:
    - Modelos `SurfaceState`, `ToothSurfacesV3`, `ToothDataV3`, `DentitionData`, `OdontogramV3` definidos con Pydantic
    - `LEGACY_STATE_MAP` cubre los 10 estados v2 mapeados a sus equivalentes v3 (ids string)
    - Todos los modelos son importables desde `shared.odontogram_utils`

---

- [x] **Task 1.3: Actualizar shared/models_dental.py** — Actualizar aliases de compatibilidad y referencias a los modelos v3 `(S)`
  - Files: `shared/models_dental.py`
  - Spec: `specs/data-model-evolution/spec.md`
  - Depends on: Task 1.2
  - AC:
    - `ToothSurface`, `ToothData`, `OdontogramV3` re-exportados desde `odontogram_utils`
    - No hay imports rotos en archivos que ya usaban `models_dental`
    - Aliases backward-compat presentes para nombres v2

---

- [x] **Task 1.4: Crear migración Alembic 017** — Migración no-destructiva que documenta el formato v3.0 y agrega índice GIN opcional `(M)`
  - Files: `orchestrator_service/alembic/versions/017_odontogram_v3_format.py`
  - Spec: `specs/data-model-evolution/spec.md`
  - Depends on: Task 1.2
  - AC:
    - La migración aplica sin errores contra la DB actual (`alembic upgrade head`)
    - `downgrade()` revierte sin pérdida de datos
    - El índice GIN sobre `odontogram_data` se crea solo si no existe (idempotente)

---

- [x] **Task 1.5: Crear catálogo de estados Python** — Definir los 42 estados clínicos con metadatos completos `(M)`
  - Files: `shared/odontogram_states.py`
  - Spec: `specs/state-catalog/spec.md`
  - Depends on: Task 1.2
  - AC:
    - 42 estados definidos (25 preexistente + 17 lesión), cada uno con `id`, `category`, `label_key`, `default_color`, `symbol`, `print_color`
    - `get_state_by_id(id)` retorna el estado o `None`
    - `get_states_by_category(category)` retorna lista filtrada
    - `normalize_legacy_state_id(old_id)` mapea ids v2 a ids v3 sin excepción

---

- [x] **Task 1.6: Crear catálogo de estados TypeScript** — Espejo exacto del catálogo Python en TypeScript `(M)`
  - Files: `frontend_react/src/constants/odontogramStates.ts`
  - Spec: `specs/state-catalog/spec.md`
  - Depends on: Task 1.5
  - AC:
    - Interfaces `OdontogramState` y `StateCategory` tipadas correctamente
    - Los 42 estados tienen los mismos `id`, `default_color` y `symbol` que el catálogo Python
    - `getStateById()`, `getStatesByCategory()`, `searchStates(query)` exportados y funcionales

---

- [x] **Task 1.7: Actualizar endpoints admin_routes.py** — PUT y GET de odontograma aceptan y retornan v3.0 `(M)`
  - Files: `orchestrator_service/admin_routes.py`
  - Spec: `specs/data-model-evolution/spec.md`
  - Depends on: Task 1.1, Task 1.2
  - AC:
    - `GET /admin/patients/{id}/records/{id}/odontogram` auto-convierte datos v2.0 a v3.0 usando `normalize_to_v3`
    - `PUT` acepta payload v3.0 y lo persiste correctamente
    - El parseo inline previo es reemplazado por `import` desde `shared.odontogram_utils`

---

- [x] **Task 1.8: Cablear parsers en código existente** — Reemplazar parsers duplicados en odontogram_svg.py y nova_tools.py `(S)`
  - Files: `orchestrator_service/odontogram_svg.py`, `orchestrator_service/services/nova_tools.py`
  - Spec: `specs/data-model-evolution/spec.md`
  - Depends on: Task 1.1
  - AC:
    - `normalize_odontogram_data` en `odontogram_svg.py` reemplazado por `from shared.odontogram_utils import normalize_to_v3`
    - `_parse_odontogram_data` en `nova_tools.py` reemplazado por la misma importación
    - Ambos archivos siguen funcionando con datos v2.0 existentes

---

- [x] **Task 1.9: Tests Fase 1** — Suite de tests para toda la capa de datos `(L)`
  - Files: `tests/test_odontogram_utils.py`, `tests/test_odontogram_states.py`, `tests/test_odontogram_endpoints.py`
  - Spec: `specs/data-model-evolution/spec.md`, `specs/state-catalog/spec.md`
  - Depends on: Task 1.1 – Task 1.8
  - AC:
    - `normalize_to_v3` probado con input v1, v2 y v3 (casos nominales y edge cases)
    - `build_default_permanent()` y `build_default_deciduous()` verifican cantidad de piezas y FDI correcto
    - Endpoints PUT/GET probados con payload v2.0 y v3.0 (integración con DB de test)

---

## Fase 2: Core UI

> Requiere Fase 1 completa. Tareas 2.1–2.7 pueden paralelizarse entre sí; 2.8 es independiente.

---

- [x] **Task 2.1: Descomponer Odontogram.tsx** — Extraer subcomponentes para aliviar el archivo principal `(M)`
  - Files: `frontend_react/src/components/odontogram/ToothSVG.tsx`, `frontend_react/src/components/odontogram/OdontogramLegend.tsx`, `frontend_react/src/components/odontogram/Odontogram.tsx`
  - Spec: `specs/dentition-tabs/spec.md`
  - Depends on: Task 1.6
  - AC:
    - `ToothSVG` extraído a su propio archivo con misma API de props
    - `OdontogramLegend` extraído a su propio archivo
    - `Odontogram.tsx` actúa como orquestador; no hay regresión visual

---

- [x] **Task 2.2: Crear SurfacePath.tsx** — Componente SVG para superficie individual clickeable `(M)`
  - Files: `frontend_react/src/components/odontogram/SurfacePath.tsx`
  - Spec: `specs/surface-selection/spec.md`
  - Depends on: Task 1.6
  - AC:
    - Props tipadas: `pathD`, `surfaceName`, `state`, `condition`, `color`, `isSelected`, `onClick`
    - Color resuelto con prioridad: color custom → `default_color` del estado → color sano
    - Hover aplica `scale(1.05)`, selected aplica `stroke-width: 2` con glow CSS

---

- [x] **Task 2.3: Actualizar ToothSVG para renderizado por superficie** — Reemplazar paths uniformes con 5 SurfacePath individuales `(M)`
  - Files: `frontend_react/src/components/odontogram/ToothSVG.tsx`
  - Spec: `specs/surface-selection/spec.md`
  - Depends on: Task 2.1, Task 2.2
  - AC:
    - Cada una de las 5 superficies (oclusal, vestibular, lingual, mesial, distal) usa `SurfacePath`
    - Primer clic selecciona pieza, segundo clic selecciona superficie
    - Animaciones `toothPop` y anillo de selección se mantienen intactas

---

- [x] **Task 2.4: Crear DentitionChart.tsx** — Componente reutilizable para renderizar N piezas en layout de cuadrantes `(L)`
  - Files: `frontend_react/src/components/odontogram/DentitionChart.tsx`
  - Spec: `specs/dentition-tabs/spec.md`
  - Depends on: Task 2.3
  - AC:
    - Acepta `teeth[]`, `quadrantsConfig`, `onToothClick`, `onSurfaceClick`, `selectedTooth`, `selectedSurface`
    - Configuración de cuadrantes para permanente (4×8) y decidua (4×5) incluida
    - Divisor de línea media y separador de arcos visibles

---

- [x] **Task 2.5: Crear OdontogramTabs.tsx** — Tabs de navegación entre dentición permanente y temporal `(S)`
  - Files: `frontend_react/src/components/odontogram/OdontogramTabs.tsx`
  - Spec: `specs/dentition-tabs/spec.md`
  - Depends on: Task 2.1
  - AC:
    - Dos tabs: "Permanente" / "Temporal" con estilos dark (`bg-white/[0.04]` inactivo, `bg-white/[0.12]` activo)
    - Transición animada al cambiar tab
    - Prop `hasDecidData` muestra punto indicador en tab Temporal cuando hay datos

---

- [x] **Task 2.6: Cablear tabs en Odontogram.tsx** — Integrar OdontogramTabs y DentitionChart con estado dual `(M)`
  - Files: `frontend_react/src/components/odontogram/Odontogram.tsx`
  - Spec: `specs/dentition-tabs/spec.md`
  - Depends on: Task 2.4, Task 2.5
  - AC:
    - Estado `activeDentition` maneja qué array de piezas se pasa a `DentitionChart`
    - Cambio de tab no pierde cambios no guardados en la otra dentición
    - Al guardar, `active_dentition` se persiste en el payload v3.0

---

- [x] **Task 2.7: Crear MobileToothZoom.tsx** — Panel flotante de zoom para selección de superficie en móvil `(M)`
  - Files: `frontend_react/src/components/odontogram/MobileToothZoom.tsx`
  - Spec: `specs/surface-selection/spec.md`
  - Depends on: Task 2.3
  - AC:
    - Solo visible en viewports < 768px cuando hay una pieza seleccionada
    - Posicionado mediante `getBoundingClientRect` de la pieza seleccionada
    - Las 5 superficies son claramente clickeables en tamaño 2–3x; se cierra con clic externo

---

- [x] **Task 2.8: Agregar claves i18n** — Internacionalizar todos los nuevos textos del odontograma `(M)`
  - Files: `frontend_react/src/locales/es.json`, `frontend_react/src/locales/en.json`, `frontend_react/src/locales/fr.json`
  - Spec: `specs/i18n-expansion/spec.md`
  - Depends on: Task 1.5 (para lista de estados)
  - AC:
    - ~75 claves nuevas agregadas en los 3 archivos (42 estados + categorías + condiciones + superficies + tabs + labels de modal)
    - Terminología clínica correcta en inglés y francés (no traducciones literales)
    - Odontogram.tsx y subcomponentes usan `t('key')` para todos los textos nuevos

---

- [x] **Task 2.9: Tests Fase 2** — Tests de componentes UI core `(L)`
  - Files: `frontend_react/src/components/odontogram/__tests__/`
  - Spec: `specs/dentition-tabs/spec.md`, `specs/surface-selection/spec.md`
  - Depends on: Task 2.1 – Task 2.8
  - AC:
    - Cambio de tab renderiza el array de piezas correcto (permanente vs decidua)
    - Clic en superficie selecciona la superficie correcta (no la pieza entera)
    - Color por superficie se resuelve según prioridad (custom > estado > sano)
    - Panel de zoom aparece en viewport 375px al seleccionar pieza

---

## Fase 3: Modales de Selección

> Requiere Task 2.6 y Task 2.8. Tareas 3.1 y 3.2 pueden implementarse en paralelo.

---

- [x] **Task 3.1: Crear SymbolSelectorModal.tsx** — Modal de búsqueda y selección de estado clínico `(L)`
  - Files: `frontend_react/src/components/odontogram/SymbolSelectorModal.tsx`
  - Spec: `specs/symbol-selector-modal/spec.md`
  - Depends on: Task 1.6, Task 2.8
  - AC:
    - Bottom sheet en móvil (slide-up), modal centrado en desktop (fade-in)
    - Barra de búsqueda con normalización de acentos funcional
    - Grid 2 columnas con badges de categoría (azul preexistente, rojo lesión) y secciones con header
    - Botón "Siguiente" habilitado solo cuando hay estado seleccionado

---

- [x] **Task 3.2: Crear StateConditionModal.tsx** — Modal de condición clínica y color personalizado `(M)`
  - Files: `frontend_react/src/components/odontogram/StateConditionModal.tsx`
  - Spec: `specs/state-condition-color/spec.md`
  - Depends on: Task 1.6, Task 2.8
  - AC:
    - 3 botones de condición: Bueno (verde), Malo (cyan), Indefinido (gris)
    - Color picker: swatch de preview + input HEX + 10 presets dentales
    - Botón "← Volver" navega al modal de símbolo (no cierra el flujo)

---

- [x] **Task 3.3: Cablear modales en Odontogram.tsx** — Integrar el flujo completo de selección de estado `(M)`
  - Files: `frontend_react/src/components/odontogram/Odontogram.tsx`
  - Spec: `specs/symbol-selector-modal/spec.md`, `specs/state-condition-color/spec.md`
  - Depends on: Task 3.1, Task 3.2
  - AC:
    - Flujo: clic en superficie → `SymbolSelectorModal` → "Siguiente" → `StateConditionModal` → "Aplicar" → superficie actualizada
    - Estado pendiente (`pendingState`) se descarta si se cierra sin aplicar
    - `Escape` cierra el modal activo; animación de cierre visible

---

- [x] **Task 3.4: Actualizar OdontogramLegend.tsx** — Leyenda dinámica con solo los estados presentes `(S)`
  - Files: `frontend_react/src/components/odontogram/OdontogramLegend.tsx`
  - Spec: `specs/state-catalog/spec.md`
  - Depends on: Task 2.1, Task 3.3
  - AC:
    - Solo muestra estados que aparecen en el odontograma actual (permanente o decidua según tab activa)
    - Agrupa por categoría (preexistente / lesión)
    - Responsive: wraps correctamente en mobile sin overflow horizontal

---

- [x] **Task 3.5: Tests Fase 3** — Tests de flujo de modales `(L)`
  - Files: `frontend_react/src/components/odontogram/__tests__/`
  - Spec: `specs/symbol-selector-modal/spec.md`, `specs/state-condition-color/spec.md`
  - Depends on: Task 3.1 – Task 3.4
  - AC:
    - Clic en superficie abre `SymbolSelectorModal`
    - Búsqueda con tilde y sin tilde retorna el mismo resultado ("caries" == "cariés")
    - Flujo completo superficie → símbolo → condición → aplicar actualiza el estado de la superficie en el array
    - "← Volver" desde `StateConditionModal` regresa a `SymbolSelectorModal` sin cerrar

---

## Fase 4: Backend Ecosystem

> Requiere Fase 1 completa. Tareas 4.1–4.3 (Nova) y 4.4–4.6 (SVG/PDF) pueden correr en paralelo.

---

- [x] **Task 4.1: Actualizar schemas de herramientas Nova** — Extender `ver_odontograma` y `modificar_odontograma` con soporte v3.0 `(M)`
  - Files: `orchestrator_service/services/nova_tools.py`
  - Spec: `specs/nova-tools-update/spec.md`
  - Depends on: Task 1.5
  - AC:
    - Parámetro `denticion` ("permanente" | "temporal") agregado a ambas herramientas
    - `_VALID_STATES` expandido con los 42 ids de estados v3
    - `_FDI_NAMES_DECIDUOUS` definido con los 20 dientes FDI 51–85

---

- [x] **Task 4.2: Actualizar implementación ver_odontograma** — Lectura de datos v3.0 por dentición `(M)`
  - Files: `orchestrator_service/services/nova_tools.py`
  - Spec: `specs/nova-tools-update/spec.md`
  - Depends on: Task 4.1, Task 1.1
  - AC:
    - Lee desde la sección `permanente` o `decidua` según parámetro
    - Reporta estado + condición por superficie en la respuesta texto
    - Piezas de dentición decidua organizadas por cuadrantes Q5–Q8 en el output

---

- [x] **Task 4.3: Actualizar implementación modificar_odontograma** — Escritura parcial en formato v3.0 `(M)`
  - Files: `orchestrator_service/services/nova_tools.py`
  - Spec: `specs/nova-tools-update/spec.md`
  - Depends on: Task 4.1, Task 1.1
  - AC:
    - Escribe en la sección de dentición correcta (permanente o decidua)
    - Merge parcial: solo sobreescribe campos explícitamente pasados en `{state, condition, color}`
    - Valida que el FDI pertenece al rango de la dentición indicada; emite `ODONTOGRAM_UPDATED` con payload v3.0 completo

---

- [x] **Task 4.4: Actualizar renderer odontogram_svg.py** — Renderizado por superficie con 42 estados y sección decidua `(XL)`
  - Files: `orchestrator_service/odontogram_svg.py`
  - Spec: `specs/svg-pdf-renderer/spec.md`
  - Depends on: Task 1.5, Task 1.8
  - AC:
    - `_render_tooth_group()` usa colores por superficie (custom → estado → sano)
    - `PRINT_FILLS` cubre los 42 estados con colores de impresión
    - `_render_chart_section()` es reutilizable para permanente y decidua
    - Sección decidua se incluye condicionalmente (solo si hay datos en `decidua`)

---

- [x] **Task 4.5: Actualizar template HTML odontogram_art.html** — Template con sección decidua y tabla expandida `(M)`
  - Files: `orchestrator_service/templates/odontogram_art.html` (o path equivalente)
  - Spec: `specs/svg-pdf-renderer/spec.md`
  - Depends on: Task 4.4
  - AC:
    - Bloque condicional para sección decidua (Jinja2 `{% if has_deciduous %}`)
    - Tabla de detalle incluye columna "Condición" además de "Estado"
    - Las piezas afectadas muestran desglose por superficie

---

- [x] **Task 4.6: Actualizar digital_records_service.py** — Integrar v3.0 en la generación de expediente digital `(M)`
  - Files: `orchestrator_service/services/digital_records_service.py`
  - Spec: `specs/svg-pdf-renderer/spec.md`
  - Depends on: Task 4.4, Task 4.5
  - AC:
    - `gather_patient_data()` pasa la estructura v3.0 completa al renderer
    - `render_odontogram_svg()` recibe y maneja `OdontogramV3` correctamente
    - La generación PDF end-to-end no lanza excepción con datos v2.0 ni v3.0

---

- [x] **Task 4.7: Tests Fase 4** — Tests del backend ecosystem `(XL)`
  - Files: `tests/test_nova_odontogram.py`, `tests/test_odontogram_svg.py`, `tests/test_digital_records.py`
  - Spec: `specs/nova-tools-update/spec.md`, `specs/svg-pdf-renderer/spec.md`
  - Depends on: Task 4.1 – Task 4.6
  - AC:
    - `ver_odontograma` con `denticion="temporal"` retorna piezas Q5–Q8
    - `modificar_odontograma` con superficie parcial no sobreescribe campos no pasados
    - SVG renderer genera SVG válido con datos v2.0 (backward compat) y v3.0
    - PDF generado incluye sección decidua cuando `decidua` tiene datos; la omite cuando está vacía

---

## Fase 5: Integración y Polish

> Requiere todas las fases anteriores.

---

- [x] **Task 5.1: Test de integración end-to-end** — Flujo completo desde UI hasta DB, Nova y PDF `(XL)`
  - Files: `tests/test_e2e_odontogram.py`
  - Spec: `specs/general/spec.md`
  - Depends on: Todas las tareas anteriores
  - AC:
    - Flujo completo funcional: abrir paciente → seleccionar tab → clic pieza → clic superficie → seleccionar estado → condición/color → guardar → dato en DB con formato v3.0
    - WebSocket `ODONTOGRAM_UPDATED` emitido después del guardado
    - Nova puede leer el odontograma guardado; PDF generado con el dato correcto

---

- [x] **Task 5.2: Testing mobile** — Verificación en viewport 375px `(M)`
  - Files: Playwright/Cypress config o test manual checklist
  - Spec: `specs/surface-selection/spec.md`
  - Depends on: Task 2.7, Task 3.1, Task 3.2
  - AC:
    - Panel `MobileToothZoom` aparece y es completamente operable con touch en 375px
    - `SymbolSelectorModal` en bottom sheet es scrolleable sin desbordar
    - Tabs son accesibles y tienen área de toque ≥ 44px

---

- [x] **Task 5.3: Verificación de backward compatibility** — Garantizar que odontogramas v2.0 existentes funcionan sin migración manual `(M)`
  - Files: Scripts de prueba, fixture data
  - Spec: `specs/data-model-evolution/spec.md`
  - Depends on: Task 1.1, Task 1.7, Task 4.4, Task 4.6
  - AC:
    - Paciente con dato v2.0 en DB se renderiza correctamente en la UI (auto-upgrade en GET)
    - Modificar y guardar ese paciente persiste formato v3.0 en DB
    - Nova puede leer el dato v2.0 original sin error; PDF generado sin excepción

---

- [x] **Task 5.4: Auditoría de performance** — Verificar que el odontograma con 32 piezas × 5 superficies no degrada la UI `(M)`
  - Files: Profiling via React DevTools / Chrome Performance
  - Spec: `specs/general/spec.md`
  - Depends on: Task 2.6, Task 3.3
  - AC:
    - Tiempo de render inicial del odontograma permanente < 100ms en hardware de referencia
    - Ningún frame > 16ms durante animación de selección de pieza o apertura de modal
    - `SVG renderer` en Python completa en < 2s para un odontograma con 42 estados usados

---

## Resumen de Complejidad

| Task | Complejidad |
|------|-------------|
| 1.1 | L |
| 1.2 | M |
| 1.3 | S |
| 1.4 | M |
| 1.5 | M |
| 1.6 | M |
| 1.7 | M |
| 1.8 | S |
| 1.9 | L |
| 2.1 | M |
| 2.2 | M |
| 2.3 | M |
| 2.4 | L |
| 2.5 | S |
| 2.6 | M |
| 2.7 | M |
| 2.8 | M |
| 2.9 | L |
| 3.1 | L |
| 3.2 | M |
| 3.3 | M |
| 3.4 | S |
| 3.5 | L |
| 4.1 | M |
| 4.2 | M |
| 4.3 | M |
| 4.4 | XL |
| 4.5 | M |
| 4.6 | M |
| 4.7 | XL |
| 5.1 | XL |
| 5.2 | M |
| 5.3 | M |
| 5.4 | M |

**Total**: 34 tareas — 4 XL · 10 L · 16 M · 4 S
