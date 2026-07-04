# Plan diferido: candado determinista anti "agenda-solo" (BUG B)

> Estado: **DIFERIDO** el 2026-07-03. El subset seguro (A2/A3/B5/B6) ya está en PRUEBAS (`83c7d4c`).
> Este candado de código NO se subió porque la verificación adversarial (workflow `wf_92a9b29b-e25`, 7 agentes)
> probó que el diseño original **rompía TODOS los bookings**. Se implementa aparte, con TODOS los must-fix de abajo,
> y con su propia ronda de pruebas antes de promover.

## El bug (BUG B)
`gpt-5.4-mini` a veces calcula un slot con `check_availability`, NO se lo muestra al paciente, pide nombre+DNI y
llama `confirm_slot`+`book_appointment` → agenda un turno que el paciente **nunca vio ni eligió** (caso Lucas: martes
04/08). Los gates actuales (`SLOT_NOT_OFFERED` main.py:4348, estado `OFFERED_SLOTS`, `slot_offer` Redis) se satisfacen
con que la tool **haya devuelto** el slot, no con que el mensaje con las opciones **se haya emitido** al paciente.
Es intermitente (conv del 22:48 agendó BIEN: mostró y el paciente eligió "la 1").

## Diseño (sello de presentación) — la idea
- `slot_offer` (Redis) nace `presented=false`.
- `buffer_task` pone `presented=true` SOLO si el texto realmente enviado al paciente contiene DD/MM+HH:MM de los slots.
- `book_appointment` exige `presented=true`; si no, devuelve error **RECUPERABLE** `SLOT_NOT_SHOWN` ("re-presentá las 2 opciones"), NUNCA deriva.

## MUST-FIX obligatorios antes de aplicar (de la verificación adversarial)
1. **`datetime` NO está importado a nivel de módulo en buffer_task.py** (solo en ramas condicionales, línea ~930 y ~4050). El bloque del sello DEBE hacer `from datetime import datetime` adentro, o lanza NameError → el sello nunca se pone → book bloquea TODO. (CRÍTICO)
2. **Resolver `phone = current_customer_phone.get()` explícitamente** dentro del bloque del sello (no depender de la variable `phone` filtrada de un `if` ~90 líneas arriba).
3. **Scope a SoloEngine, o mover el sello a un punto post-send compartido.** El gate vive en `book_appointment` (tool compartida) pero el sello propuesto corre solo en el path del executor solo → tenants `ai_engine_mode='multi'` nunca sellan → **se les bloquea TODO booking**. (CRÍTICO)
4. **Quitar la salvedad `len(offered_slots)<=1`** → reabre el bug exacto (el martes 04/08 era 1 solo slot nunca mostrado). Para 1 opción también exigir `presented=true` (el sello la marca si está en el texto). Gatear la salvedad solo por `specific_time`/exact donde el paciente nombró la hora.
5. **Decrementar `booking_attempts` en `SLOT_NOT_SHOWN`** (espejar `UNAVAILABLE` en `_track_book_error` main.py:170), o correr el gate ANTES del incremento (4106). Si no: 3 falsos-bloqueos → `CONFIRM_REQUIRED` (4110) → **deriva a humano** (viola "nunca deriva").
6. **Sellar sobre el texto FINAL, justo antes del send** (después de STATE_GUARD/SLOT_LOCKED retries, del date-validator ~4149, del NET, y del ABORT-AND-RECOMPUTE ~4269). Sellar en ~3782 lee texto pre-retry/pre-postproceso y puede sellar un mensaje que después se descarta/blanquea → reabre BUG B.
7. **Manejar la re-búsqueda de honestidad ("¿algo antes?")**: cuando `check_availability` devuelve los MISMOS slots ya presentados y el prompt prohíbe re-listarlos, el sello no re-dispara → falso-bloqueo de un booking legítimo. Solución: aceptar un slot presente en `convstate.presented_slots` de CUALQUIER turno previo (no solo el último `slot_offer`), o no resetear `presented` si los slots devueltos son idénticos a los ya presentados.
8. **Normalizar los 5 lectores de `slot_offer`** en el MISMO commit (el shape pasa de lista a `{slots,presented}`): book Priority-0 (~4233/4239), book R1 gate (~4368), reschedule (~6307, fail-open), confirm_slot Priority-1 (~7801/7807), TTL-refresh (~8037). Los que indexan por int (`[_idx]`) rompen si reciben dict.
9. **Matcher tolerante** (o sellar contra el `resp` canónico de la tool, main.py:3555, que ya trae DD/MM zero-padded): aceptar `8/7`==`08/07`, `8 de julio`, `13 hs`/`a las 13`. El match literal contra la paráfrasis del LLM es frágil.
10. **Fuente de verdad ÚNICA = Redis `slot_offer.presented`** (se resetea por-llamada en check_availability 3599). Tratar `convstate.presented_slots` como solo auditoría; resetear en la rama `OFFERED_SLOTS` de `set_state`.

## BUG A — red determinista opcional pendiente
- Además de A2/A3 ya subidos: considerar **derivar `preferred_days` del `date_query`** server-side cuando el LLM lo omite (regex de días de semana), como red. OJO: cuidado con "menos el viernes"/"no puedo el viernes" (eso es exclude, no preferred) — no hacer derive naïve.
- **A1 (auto-advance respeta preferred_days)** quedó fuera: hoy `pick_representative_slots` (main.py:1705) ya bumpea el rango a 7 y filtra por complemento, así que con la ventana ancha (A2) suele alcanzar. Reevaluar si en pruebas "fin de mes + día" sigue fallando.

## DUDA ABIERTA a confirmar en DB de pruebas
- La memoria [[clinicforge-laura-config-ground-truth]] dice Elizabeth (id23) atiende **Vie 10-15**. Pero el log del 22:52 con `preferred_days='viernes'` devolvió **0 slots** para viernes. Confirmar si en la DB de pruebas el viernes de Elizabeth está enabled/con agenda, porque si NO atiende viernes, "los últimos viernes" es imposible para ortodoncia y el bot hizo bien en ofrecer mar/mié.
