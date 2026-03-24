# SPEC: Smart Booking Flow v2 — Flujo de agendamiento inteligente

**Fecha:** 2026-03-23
**Estado:** Clarificado
**Prioridad:** Alta
**Contexto:** Pruebas reales revelaron 6 problemas críticos + 4 adicionales en el flujo de agendamiento del agente IA.

---

## Clarificaciones (resueltas 2026-03-23)

### C1 — Slots insuficientes: completar con días siguientes
**Pregunta:** ¿Qué pasa cuando hay 1 o 2 slots libres en el día pedido?
**Respuesta:** **Opción C** — Mostrar los slots del día pedido + completar hasta 3 opciones buscando automáticamente en días siguientes. Ejemplo: si hoy solo hay 16:30, mostrar: `1) Hoy 16:30  2) Mañana 09:30  3) Mañana 15:00`.

### C2 — Horario libre fuera de las 3 opciones: modo flexible
**Pregunta:** ¿El paciente puede pedir un horario que no está en las 3 opciones?
**Respuesta:** **Sí, modo flexible.** Si pide otro horario, el agente llama `check_availability` para verificar si ese slot específico está libre. Si está libre → bookear. Si está ocupado → decir honestamente que está ocupado y ofrecer el slot libre más cercano. El agente NUNCA sobre-agenda; siempre busca el horario más óptimo que realmente esté disponible.

### C3 — Soft lock de 30 segundos para reserva temporal
**Pregunta:** ¿Cómo evitar que otro paciente tome el slot mientras se recolectan datos?
**Respuesta:** **Opción B con 30 segundos.** Implementar soft lock en Redis al momento que el paciente confirma un slot. TTL de 30 segundos (no 3 minutos, para evitar bloquear slots que nadie va a usar). Si el booking no se completa en 30s, el lock expira y el slot vuelve a estar disponible. `check_availability` debe respetar los soft locks activos.

### C4 — Almuerzo: documentar para configuración posterior
**Pregunta:** ¿La clínica tiene pausa de almuerzo configurada en `working_hours`?
**Respuesta:** Pendiente de verificación. Se elimina el filtro hardcodeado pero se documenta que la pausa de almuerzo debe configurarse en `working_hours` del tenant (slots separados). El usuario configurará esto posteriormente desde el panel admin.

### C5 — Buffer: problema real es restart del servidor
**Pregunta:** ¿El problema de mensajes separados es por TTL o por otro factor?
**Respuesta:** Los logs confirmaron que `msgs=1` (solo 1 de 3 mensajes capturado) Y hay un **restart del servidor** en los logs (`CancelledError` + shutdown del JobScheduler). El buffer task en memoria (`_delayed_process_buffer_task`) muere con el restart, y los mensajes que quedaban en Redis no se re-procesan al reiniciar. **Solución ampliada:** además de ajustar TTL, implementar recovery de buffers huérfanos al startup del servicio.

---

## Problemas detectados

### P1 — Rangos abiertos en vez de slots concretos
**Síntoma:** El agente dice "tenemos disponibilidad de 13:00 a 17:30" y pregunta "¿a qué hora te gustaría?". El paciente elige libremente y puede caer en un horario ocupado.
**Causa raíz:** `check_availability` (main.py:721-754) genera hasta 50 slots de 30min pero `slots_to_ranges()` (main.py:408-440) los colapsa en rangos continuos. El agente recibe "de 13:00 a 17:30" sin saber qué slots dentro del rango están ocupados.
**Impacto:** En la prueba 2, Martín pidió las 13:00, 13:30, 14:00, 15:00 — todos rechazados por `book_appointment`. Frustración total.

### P2 — El agente pide datos ANTES de confirmar el slot exacto
**Síntoma:** El agente pide nombre y DNI, después intenta bookear, falla, y vuelve a pedir los mismos datos.
**Causa raíz:** El system prompt (PASO 5 antes de PASO 6) fuerza a recolectar admisión antes de confirmar disponibilidad. Cuando `book_appointment` falla, el LLM pierde contexto de los datos ya dados.
**Impacto:** En la prueba 2, Martín dio nombre y DNI 3 veces.

### P3 — Triage no detecta "se me cayó un diente"
**Síntoma:** El agente respondió "no presenta signos de urgencia dental" cuando el paciente dijo "se me cayó un diente, se me partió, es urgente".
**Causa raíz doble:**
1. El system prompt (línea 2371) dice: "Solo llamar a `triage_urgency` si el paciente describe **dolor, inflamación, sangrado o accidente**". "Se me cayó un diente" no matchea esos 4 triggers → el agente probablemente NO invocó la tool.
2. Aun si la invocara, los keywords del criterio 6 son `"prótesis se cayó"`, `"diente roto"`, `"corona se despegó"`. Falta `"se me cayó un diente"`, `"se me partió un diente"`, `"perdí un diente"`, `"se me salió"`.

### P4 — Mensajes separados rápidos → respuestas individuales
**Síntoma:** El paciente manda "Se me cayó un diente es urgente" y 1 segundo después "Se me partió". El agente responde a cada uno por separado.
**Causa raíz:** El buffer en `relay.py` usa TTL de 10 segundos, pero el debounce loop chequea `ttl(timer_key)` y si el primer mensaje ya disparó el procesamiento antes de que llegue el segundo, se procesan como conversaciones separadas. Con mensajes que llegan con <2s de diferencia esto no debería pasar, pero el comportamiento observado sugiere que hay un race condition o el TTL se resolvió antes.
**Nota:** Necesita investigación adicional del timing real en producción.

### P5 — Flujo poco directo: demasiados round-trips
**Síntoma:** "Hola, quiero un turno" → saludo → "¿qué tratamiento?" → responde → "¿es para vos?" → responde → check_availability → "¿a qué hora?" → elige → pide nombre → pide DNI → booking. Mínimo 6-8 mensajes ida y vuelta.
**Causa raíz:** El system prompt (PASOS 1-8) es secuencial estricto: cada paso es un turno de conversación separado. No hay instrucción para combinar pasos cuando el paciente ya proveyó información.

### P6 — Repite preguntas de datos ya proporcionados
**Síntoma:** El agente pidió nombre, DNI y confirmación "¿es para vos?" múltiples veces en la misma conversación.
**Causa raíz:** La regla ANTI-REPETICIÓN (línea 2261) existe pero es genérica. No hay instrucción explícita de que si el paciente ya dio nombre/DNI y se cambia horario o día, NO debe volver a pedirlos. Además, en conversaciones largas, el LLM pierde tracking de datos ya recolectados.

---

## Problemas adicionales encontrados en el análisis de código

### P7 — Almuerzo hardcodeado: se saltan slots de 13:00-14:00
**Causa:** `generate_free_slots` (main.py:372-374) tiene un filtro hardcodeado:
```python
if current.hour >= 13 and current.hour < 14 and not time_preference:
    continue  # Saltar almuerzo
```
Esto elimina los slots de 13:00-13:30 del resultado, pero `book_appointment` SÍ permite bookear a esas horas si no hay conflicto. Inconsistencia entre lo que `check_availability` reporta como disponible y lo que `book_appointment` acepta.
**Impacto:** En la prueba 1, Lucas agendó a las 13:15 exitosamente (vía `book_appointment`), pero `check_availability` probablemente no mostró ese rango porque el filtro de almuerzo lo oculta. Esto depende de si el paciente usó `time_preference='tarde'` (que bypasea el filtro) o no.

### P8 — Intervalo de 30min fijo no respeta duraciones menores
**Causa:** `generate_free_slots` itera en intervalos de 30 minutos (`interval_minutes=30` en main.py:403). Si un tratamiento dura 15 o 20 minutos, los slots se generan cada 30min igualmente, desperdiciando capacidad. Un turno de 15min a las 13:15 bloquea el slot de 13:00 completo en el busy_map.
**Impacto:** Menor capacidad efectiva de agenda para tratamientos cortos.

### P9 — `check_availability` no indica QUÉ slots están ocupados dentro del rango
**Causa:** `slots_to_ranges()` colapsa slots libres contiguos. Si hay un "hueco" de 30min ocupado dentro de un rango de 4 horas, el rango se divide. Pero si el hueco es exactamente al inicio o final, el rango se acorta sin indicar por qué. El agente no tiene visibilidad de los slots específicos ocupados.

### P10 — System prompt no instruye sobre re-intento inteligente
**Causa:** Cuando `book_appointment` falla con "No hay disponibilidad a las HH:MM", el system prompt (línea 2353) dice "corregí el parámetro y reintentá", pero no le dice que llame `check_availability` de nuevo para obtener slots actualizados. El agente queda adivinando horarios.

---

## Soluciones propuestas

### S1 — Ofertar 2-3 slots concretos en vez de rangos (P1, P9)

**Cambio en `check_availability`** (main.py:750-757):

En vez de convertir slots a rangos con `slots_to_ranges()`, seleccionar 3 opciones representativas:

```
Algoritmo de selección:
1. Filtrar slots que ya pasaron (si es hoy)
2. De los slots libres, clasificar en:
   - MAÑANA: slots con hora < 13:00
   - TARDE: slots con hora >= 13:00
3. Seleccionar hasta 3 opciones:
   - Opción A: Primer slot disponible de MAÑANA (si hay)
   - Opción B: Primer slot disponible de TARDE (si hay)
   - Opción C: Slot "comodín" — elegir uno diferente (ej: a mitad de la tarde, o el último disponible)
   Si solo hay mañana o solo tarde, dar hasta 3 de ese bloque espaciados.
4. Formatear como:
   "Tengo estos horarios para {date}: 1) 09:30  2) 14:00  3) 16:30. Cuál te queda mejor? Si preferís otro horario, decime."
```

**Nuevo output de `check_availability`:**
```
Para {date_query} ({duration} min), te propongo estas opciones:
1) {slot_a} — {sede_a}
2) {slot_b} — {sede_b}
3) {slot_c} — {sede_c}
Si preferís otro horario, decime y verifico si está disponible.
Total de huecos libres hoy: {total_count}.
```

**Algoritmo `pick_representative_slots()`:**
```
Input: all_free_slots (list[str]), target_date, tenant_working_hours
Output: list[dict] con hasta 3 slots {time, date, sede}

1. Clasificar slots del día pedido en MAÑANA (<13:00) y TARDE (>=13:00)
2. Seleccionar:
   - Opción A: primer slot de MAÑANA (si hay)
   - Opción B: primer slot de TARDE (si hay)
   - Opción C: slot a mitad de la tarde o último disponible (espaciado)
3. Si hay < 3 opciones del día pedido:
   - Buscar días siguientes (máx 7 días adelante) hasta completar 3
   - Para cada día extra: resolver sede según working_hours del tenant
4. Cada opción incluye: hora, fecha, sede del día correspondiente
```

**Si el paciente pide un horario fuera de las opciones** (C2 — modo flexible):
- El agente llama `check_availability` con el horario/día específico pedido
- Si el slot está libre → proceder a booking
- Si está ocupado → informar honestamente y ofrecer el slot libre más cercano
- NUNCA sobre-agendar: solo bookear horarios verdaderamente disponibles

**Cambio en system prompt** (PASO 4):
```
PASO 4: CONSULTAR DISPONIBILIDAD - 'check_availability' UNA vez.
La tool devuelve 2-3 opciones concretas con horario, fecha y sede.
Presentá las opciones al paciente tal cual.
Si el paciente elige una opción → pasar a PASO 4b.
Si el paciente pide otro horario → volver a llamar check_availability para verificar ese horario.
  - Si está libre → pasar a PASO 4b con ese horario.
  - Si está ocupado → decir honestamente que está ocupado y ofrecer el más cercano disponible.
Si NINGUNA opción funciona → ofrecer otro día o profesional.
```

**Archivos a modificar:**
- `orchestrator_service/main.py` — función `check_availability` (líneas 750-757), nueva función `pick_representative_slots()`
- `orchestrator_service/main.py` — system prompt PASO 4 (línea 2317)

---

### S2 — Reordenar flujo: confirmar slot ANTES de pedir datos (P2, P6)

**Cambio en system prompt** — Reordenar PASOS 4, 5, 6:

```
FLUJO DE AGENDAMIENTO (ORDEN ESTRICTO):
PASO 1: SALUDO
PASO 2: DEFINIR SERVICIO
PASO 2b: PARA QUIÉN ES EL TURNO
PASO 3: PROFESIONAL ASIGNADO
PASO 4: CONSULTAR DISPONIBILIDAD (2-3 opciones)
PASO 4b: PACIENTE ELIGE OPCIÓN ← NUEVO: el paciente confirma slot
PASO 5: DATOS DE ADMISIÓN (solo si paciente nuevo Y slot confirmado)
PASO 6: AGENDAR con book_appointment
PASO 7: CONFIRMACIÓN
PASO 8: FICHA MÉDICA

REGLA DE NO-REPETICIÓN DE DATOS (CRÍTICO):
Si el paciente ya dio nombre, apellido o DNI en esta conversación,
NUNCA volver a pedirlos aunque cambie el horario, día o tratamiento.
Reutilizá los datos que ya tenés del historial de chat.
```

**Agregar regla explícita:**
```
CAMBIO DE HORARIO/DÍA: Si el paciente cambia de opinión sobre horario o día
DESPUÉS de haber dado sus datos, volver SOLO a PASO 4 (consultar disponibilidad).
NO repetir PASOS 2, 2b, 3 ni 5.
```

**Soft Lock de 30 segundos (C3):**

Cuando el paciente confirma un slot (PASO 4b), crear un lock temporal en Redis:
```
Key:   slot_lock:{tenant_id}:{professional_id}:{date}:{time}
Value: {conversation_id}
TTL:   30 segundos
```

Comportamiento:
- `check_availability` al generar slots libres: filtrar slots que tengan un soft lock activo de OTRO conversation_id (el mismo paciente puede ver su propio lock).
- `book_appointment` al verificar disponibilidad: ignorar soft locks (la verificación real es contra `appointments` table).
- Si el booking se completa → el lock ya no importa (el appointment existe).
- Si el booking no se completa en 30s → el lock expira automáticamente y el slot vuelve a estar disponible.
- Si otro paciente pregunta por ese slot durante el lock → "Ese horario está siendo reservado en este momento. Te ofrezco estas alternativas: ..."

**Implementación técnica:**
```python
# En check_availability, al generar slots:
async def is_slot_locked(tenant_id, prof_id, date_str, time_str, my_conv_id):
    key = f"slot_lock:{tenant_id}:{prof_id}:{date_str}:{time_str}"
    lock_conv = await redis.get(key)
    return lock_conv and lock_conv.decode() != my_conv_id

# Al confirmar slot (nuevo endpoint o en buffer_task):
async def lock_slot(tenant_id, prof_id, date_str, time_str, conv_id):
    key = f"slot_lock:{tenant_id}:{prof_id}:{date_str}:{time_str}"
    await redis.setex(key, 30, conv_id)
```

**Trigger del lock:** El agente no puede llamar Redis directamente. Dos opciones:
- **Opción A:** Nueva tool `confirm_slot` que el agente llama cuando el paciente elige un horario. La tool crea el lock y devuelve confirmación.
- **Opción B:** `book_appointment` crea el lock automáticamente al inicio de su ejecución, antes de pedir datos faltantes.

Se implementa **Opción A** — nueva tool `confirm_slot` que el agente llama en PASO 4b.

**Archivos a modificar:**
- `orchestrator_service/main.py` — system prompt, sección FLUJO DE AGENDAMIENTO (líneas 2295-2340)
- `orchestrator_service/main.py` — nueva tool `confirm_slot`
- `orchestrator_service/main.py` — `check_availability` debe filtrar slots con lock activo de otros

---

### S3 — Ampliar triggers y keywords de triage (P3)

**3a. Ampliar triggers del system prompt** (línea 2371):

Cambiar:
```
TRIAJE Y URGENCIAS: Solo llamar a 'triage_urgency' si el paciente describe
dolor, inflamación, sangrado o accidente.
```
Por:
```
TRIAJE Y URGENCIAS: Llamar a 'triage_urgency' si el paciente describe CUALQUIERA de:
dolor, inflamación, sangrado, accidente, traumatismo, rotura, pérdida de diente/pieza,
fiebre, "se me cayó", "se me rompió", "se me partió", "se me salió", "urgente",
"emergencia", "no puedo comer", "no puedo hablar".
NO por consultas de rutina (limpieza, blanqueamiento, control).
```

**3b. Ampliar keywords en `triage_urgency`** (main.py:1236-1237):

Agregar al criterio 6 (emergency_criteria):
```python
# 6. Pérdida/rotura de pieza dental o prótesis
['prótesis se cayó', 'corona se despegó', 'puente roto', 'fractura diente',
 'no puedo comer', 'no puedo hablar', 'diente roto', 'corona rota', 'puente despegado',
 # Nuevos keywords:
 'se me cayó un diente', 'se me cayó el diente', 'se cayó un diente',
 'se me partió', 'se me partió un diente', 'diente partido',
 'se me rompió un diente', 'se me rompió el diente',
 'se me salió un diente', 'se me salió el diente', 'se salió un diente',
 'perdí un diente', 'se me perdió un diente',
 'se me quebró', 'diente quebrado',
 'se me aflojó un diente', 'diente flojo', 'diente suelto',
 'se me movió un diente']
```

Agregar al criterio 4 (traumatismo):
```python
# 4. Traumatismo facial/bucal
[..., 'se me cayó', 'se me rompió', 'se me partió']  # formas genéricas
```

**Archivos a modificar:**
- `orchestrator_service/main.py` — `triage_urgency` keywords (líneas 1219-1238)
- `orchestrator_service/main.py` — system prompt trigger de triage (línea 2371)

---

### S4 — Buffer resiliente: recovery de mensajes huérfanos + sliding window (P4)

**Diagnóstico confirmado (C5):** Los logs muestran `msgs=1` (solo 1 de 3 mensajes) Y un restart del servidor (`CancelledError`). El task asyncio `_delayed_process_buffer_task` que esperaba el TTL murió con el restart. Los mensajes 2 y 3 quedaron en Redis sin ser procesados.

**Dos cambios necesarios:**

**4a. Recovery al startup** — Al iniciar el servicio, buscar buffers huérfanos en Redis:
```python
# En startup del orchestrator (main.py lifespan o start event)
async def recover_orphaned_buffers():
    """Busca keys buffer:* en Redis que no tengan un timer:* activo asociado."""
    cursor = 0
    while True:
        cursor, keys = await redis.scan(cursor, match="buffer:*", count=100)
        for buf_key in keys:
            # buf_key = "buffer:{tenant_id}:{external_user_id}"
            parts = buf_key.decode().split(":")
            tenant_id, ext_user = int(parts[1]), parts[2]
            timer_key = f"timer:{tenant_id}:{ext_user}"

            # Si no hay timer activo, este buffer está huérfano
            if not await redis.exists(timer_key):
                messages = await redis.lrange(buf_key, 0, -1)
                await redis.delete(buf_key)
                if messages:
                    logger.warning(f"♻️ Recovering orphaned buffer: {buf_key} ({len(messages)} msgs)")
                    # Re-encolar para procesamiento
                    asyncio.create_task(process_buffer_task(
                        tenant_id, conv_id, ext_user,
                        [m.decode() for m in messages], ...
                    ))
        if cursor == 0:
            break
```

**4b. Sliding window mínimo** — Ajustar timing en `relay.py`:
```python
BUFFER_TTL_SECONDS = 12          # de 10 a 12
MIN_REMAINING_TTL = 4            # nuevo: extender si quedan < 4s

# En enqueue_buffer_and_schedule_task():
current_ttl = await redis.ttl(timer_key)
if current_ttl > 0 and current_ttl < MIN_REMAINING_TTL:
    new_ttl = MIN_REMAINING_TTL
else:
    new_ttl = max(current_ttl, ttl)
await redis.setex(timer_key, new_ttl, "1")
```

**Archivos a modificar:**
- `orchestrator_service/services/relay.py` — constantes y lógica de TTL (líneas 27, 61-75)
- `orchestrator_service/main.py` — startup event, nueva función `recover_orphaned_buffers()`

---

### S5 — Flujo más directo: combinar pasos (P5)

**Cambio en system prompt** — Agregar regla de "fast track":

```
FAST TRACK (ATAJOS):
• Si el paciente dice tratamiento + "para mí" en el mismo mensaje
  (ej: "Quiero un blanqueamiento para mí") → saltá PASO 2b, ir directo a PASO 3/4.
• Si el paciente dice "quiero un turno" sin especificar tratamiento →
  preguntar tratamiento Y ofrecer lista corta de los más comunes en UN solo mensaje.
• Si el paciente dice tratamiento + día/hora → ejecutar check_availability
  directo sin preguntar "¿querés que busque disponibilidad?".
• NUNCA preguntes "¿querés que busque disponibilidad?" — siempre buscala directamente.
• Combiná preguntas cuando sea natural: "Genial! El turno es para vos? Y tenés preferencia de día?"
```

**Cambio en greeting para patient_no_appointment y patient_with_appointment:**

Para pacientes existentes que dicen "quiero un turno", el agente ya tiene nombre y DNI. El flujo debería ser:
```
1. ¿Qué tratamiento?
2. check_availability → 3 opciones
3. Paciente elige → book_appointment directo (sin pedir datos)
```

**Archivos a modificar:**
- `orchestrator_service/main.py` — system prompt, sección FLUJO DE AGENDAMIENTO y CTAs NATURALES (líneas 2295-2367)

---

### S6 — Re-intento inteligente post-fallo de booking (P10)

**Cambio en system prompt** — Reemplazar la regla actual (línea 2353):

Actual:
```
NUNCA DAR POR PERDIDA UNA RESERVA: Si una tool devuelve ❌ o ⚠️, corregí el parámetro y reintentá.
```

Nuevo:
```
RE-INTENTO INTELIGENTE:
• Si book_appointment falla con "No hay disponibilidad a las HH:MM":
  1) Llamá check_availability DE NUEVO para ese día (la disponibilidad pudo cambiar).
  2) Presentá las nuevas opciones al paciente.
  3) NO adivinés horarios. NO iterés hora por hora.
• Si falla por datos incorrectos (DNI inválido, nombre vacío):
  Pedí solo el dato que falló, no todos de nuevo.
• Máximo 2 reintentos automáticos. Al 3er fallo → derivar a humano con derivhumano.
```

**Archivos a modificar:**
- `orchestrator_service/main.py` — system prompt (línea 2353)

---

### S7 — Eliminar filtro de almuerzo hardcodeado (P7)

**Cambio en `generate_free_slots`** (main.py:371-374):

Eliminar:
```python
# Saltar almuerzo (opcional)
if current.hour >= 13 and current.hour < 14 and not time_preference:
    current += timedelta(minutes=interval_minutes)
    continue
```

El almuerzo debería manejarse desde `working_hours` del tenant (configurando slots separados: 09:00-13:00 y 14:00-18:00). Si el tenant no tiene pausa de almuerzo configurada, no la forzamos.

**Archivos a modificar:**
- `orchestrator_service/main.py` — `generate_free_slots()` (líneas 371-374)

---

## Resumen de archivos a modificar

| Archivo | Cambios |
|---------|---------|
| `orchestrator_service/main.py` — `check_availability()` | S1: `pick_representative_slots()`, filtrar soft locks, completar con días siguientes |
| `orchestrator_service/main.py` — `generate_free_slots()` | S7: eliminar filtro almuerzo hardcodeado |
| `orchestrator_service/main.py` — `triage_urgency()` | S3b: ampliar keywords de emergencia |
| `orchestrator_service/main.py` — `build_system_prompt()` | S1, S2, S3a, S5, S6: reescribir flujo de agendamiento, triggers triage, fast track, reintento |
| `orchestrator_service/main.py` — nueva tool `confirm_slot` | S2: soft lock de 30s en Redis |
| `orchestrator_service/main.py` — startup event | S4: `recover_orphaned_buffers()` |
| `orchestrator_service/services/relay.py` | S4: TTL 12s + sliding window mínimo 4s |

---

## Orden de implementación recomendado

1. **S1 + S7** — Slots concretos + quitar almuerzo hardcodeado (resuelve P1, P7, P9 — el problema más visible)
2. **S2 + S6** — Reordenar flujo + soft lock 30s + reintento inteligente (resuelve P2, P6, P10)
3. **S3** — Triage ampliado (resuelve P3 — riesgo clínico)
4. **S5** — Fast track / flujo directo (resuelve P5 — UX)
5. **S4** — Buffer resiliente: recovery de huérfanos + sliding window (resuelve P4)

---

## Criterios de aceptación

- [ ] `check_availability` devuelve 2-3 opciones concretas con horario, fecha y sede
- [ ] Si el día pedido tiene < 3 slots, se completa con días siguientes (hasta 7 días)
- [ ] El paciente puede pedir un horario fuera de las opciones; el agente verifica honestamente si está libre
- [ ] Soft lock de 30s en Redis al confirmar slot; otros pacientes ven "horario siendo reservado"
- [ ] Nombre y DNI se piden UNA sola vez por conversación, DESPUÉS de confirmar slot
- [ ] "Se me cayó un diente" / "se me partió" / "perdí un diente" se clasifican como emergency
- [ ] El agente no repite datos ya recolectados al cambiar horario/día
- [ ] Slots de 13:00-13:30 aparecen si no hay pausa de almuerzo configurada en working_hours
- [ ] El agente no pregunta "¿querés que busque disponibilidad?" — la busca directamente
- [ ] Post-fallo de booking, el agente re-consulta `check_availability` en vez de adivinar
- [ ] Buffers huérfanos en Redis se recuperan automáticamente al reiniciar el servicio
- [ ] Sliding window de 4s mínimo garantiza que mensajes rápidos se agreguen
- [ ] Nueva tool `confirm_slot` disponible para el agente en PASO 4b
