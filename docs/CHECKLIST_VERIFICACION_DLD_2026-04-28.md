# Checklist de Verificación — Tickets DLD (28/04/2026)

Guía paso a paso para verificar que los 8 tickets resueltos en esta iteración funcionan correctamente en el entorno desplegado.

---

## DLD-49 — Race condition en reserva de turnos

**Qué se arregló:** El agente confirmaba un turno y luego se contradecía diciendo que no estaba disponible.

### Pruebas

1. **Flujo normal de booking (happy path)**
   - Escribirle al bot por WhatsApp: "Hola, quiero sacar un turno"
   - Elegir un tratamiento (ej: "evaluación")
   - El bot debe ofrecer 2 opciones de horario
   - Elegir una opción (ej: "el primero")
   - El bot debe pedir nombre y DNI (si no los tiene)
   - El bot debe confirmar el turno sin contradecirse
   - Verificar que el turno aparezca en la agenda del CRM

2. **Verificar que no pide permiso innecesario**
   - Decir "quiero un turno para evaluación"
   - El bot NO debe preguntar "¿Querés que te busque turno?" — debe buscar directamente
   - Después de elegir un horario, NO debe preguntar "¿Te agendo?" — debe avanzar directo

3. **Verificar que no da vueltas**
   - Después de elegir un slot, el bot NO debe volver a ofrecer opciones
   - NO debe preguntar "¿Seguimos con el turno?" ni variaciones
   - La selección del paciente ES la confirmación — una sola vez basta

4. **Test de concurrencia (opcional, requiere 2 teléfonos)**
   - Desde teléfono A: pedir turno, elegir un horario
   - Desde teléfono B: pedir turno para el mismo día/profesional
   - El teléfono B NO debe ver el slot que A ya reservó
   - Si ambos eligen el mismo slot, solo uno debe quedar confirmado

### Qué buscar si falla
- Redis: verificar que el servicio está corriendo y accesible
- Logs del orchestrator: buscar `Soft-lock conflict` o `Soft-lock TTL refreshed`
- Verificar que `SLOT_LOCK_TTL_SECONDS = 300` en main.py

---

## DLD-48 + DLD-50 + DLD-51 — Agente conversacional limpio

**Qué se arregló:** El agente mandaba mensajes demasiado largos, preguntaba "¿Dónde nos conociste?" y mostraba info irrelevante.

### Pruebas

1. **Verificar que NO aparece "Consultando con Dr/a."**
   - Pedir un turno, esperar las opciones de horario
   - El mensaje de disponibilidad NO debe incluir "Consultando con Dr/a. Laura Delgado"
   - Solo debe mostrar las opciones de horario con fecha y hora

2. **Verificar que NO aparece la duración**
   - En el mensaje de opciones de horario, NO debe aparecer "⏱️ Duración: 45 min"
   - La duración solo debe mencionarse si el paciente la pregunta explícitamente

3. **Verificar que NO pregunta "¿Cómo nos conociste?"**
   - Completar un booking completo hasta la confirmación
   - Después de confirmar, el bot NO debe preguntar "¿Cómo nos conociste?" (a menos que sea un paciente completamente nuevo sin nombre registrado)
   - Para pacientes conocidos/recurrentes: NUNCA debe aparecer esta pregunta

4. **Verificar cierre limpio**
   - Después de confirmar un turno, el bot NO debe mandar un mensaje de relleno tipo "Cualquier duda que tengas antes de la consulta, escribime por acá. Te esperamos!"
   - El cierre debe ser breve: datos del turno + seña (si aplica) + anamnesis (si aplica)

5. **Verificar longitud de mensajes**
   - Los mensajes del bot deben ser cortos (2-3 líneas máximo por burbuja)
   - El flujo post-booking NO debe ser una cascada de 6 mensajes separados

### Qué buscar si falla
- Buscar en main.py: no debe existir "Consultando con Dr/a." en check_availability
- Buscar "6 BLOQUES" en main.py — no debe existir (ahora es "5 BLOQUES")
- Buscar "POST-CONFIRMACIÓN — CÓMO NOS CONOCISTE" — no debe existir

---

## DLD-52 — Botón "Registrar pago" en Presupuestos

**Qué se arregló:** El botón no ejecutaba la carga del pago.

### Pruebas

1. **Pago en plan aprobado (happy path)**
   - Ir a Presupuestos → seleccionar un presupuesto con status "Aprobado"
   - Hacer clic en "Registrar pago"
   - Completar monto (ej: $50.000), método (transferencia), fecha
   - Hacer clic en "Registrar pago" en el modal
   - El pago debe registrarse y reflejarse en el saldo

2. **Plan en borrador (debe estar deshabilitado)**
   - Seleccionar un presupuesto en status "Borrador"
   - El botón "Registrar pago" debe estar deshabilitado (gris, no clickeable)

3. **Plan completado (debe estar deshabilitado)**
   - Seleccionar un presupuesto en status "Completado"
   - El botón debe estar deshabilitado

4. **Error visible**
   - Si ocurre un error al registrar (ej: monto inválido), el mensaje de error debe aparecer DENTRO del modal, no detrás de él
   - El modal debe permanecer abierto para corregir y reintentar

5. **Monto cero (debe estar deshabilitado)**
   - Abrir el modal de pago y dejar el monto en 0 o vacío
   - El botón de envío debe estar deshabilitado

### Qué buscar si falla
- Consola del navegador (F12): verificar que no hay errores JS
- Network tab: verificar que el POST a `/admin/treatment-plans/{id}/payments` se ejecuta
- Si el backend responde 422: verificar status del plan en la base de datos

---

## DLD-53 — Campo de descripción en Presupuestos

**Qué se arregló:** El campo de descripción era demasiado pequeño y cortaba el texto.

### Pruebas

1. **Campo expandido**
   - Ir a Presupuestos → agregar o editar un ítem
   - El campo "Descripción personalizada" debe ser un área de texto de 3 líneas (no una línea sola)
   - Debe permitir escribir textos largos sin cortarlos

2. **Texto completo se guarda**
   - Escribir una descripción larga (3-4 líneas)
   - Guardar el ítem
   - Reabrir → el texto debe aparecer completo, sin truncar

### Qué buscar si falla
- Inspeccionar elemento (F12): debe ser `<textarea>` no `<input type="text">`

---

## DLD-47 — Impresión de agenda sincronizada

**Qué se arregló:** La impresión no reflejaba los pacientes realmente cargados en la agenda.

### Pruebas

1. **Comparar pantalla vs PDF**
   - Ir a la Agenda en vista semanal
   - Contar cuántos turnos hay en cada día
   - Hacer clic en Descargar → Imprimir
   - El PDF debe mostrar EXACTAMENTE los mismos turnos que la pantalla
   - Los nombres de pacientes deben coincidir al 100%

2. **Turnos cancelados**
   - Si hay un turno cancelado visible en la agenda, debe aparecer también en el PDF
   - Antes del fix, los cancelados se omitían del PDF

3. **Verificar rango de fechas**
   - En vista semanal (ej: lunes a domingo), el PDF debe cubrir exactamente esos 7 días
   - NO debe incluir el lunes de la semana siguiente (era el bug del off-by-one)

4. **Verificar turnos de madrugada (si aplica)**
   - Si hay turnos agendados entre 00:00 y 03:00, deben aparecer en el día correcto del PDF
   - Antes del fix, el desfasaje de timezone podía asignarlos al día anterior

### Qué buscar si falla
- Network tab: verificar los parámetros `start_date` y `end_date` que se envían al endpoint
- `end_date` debe ser el domingo (último día visible), NO el lunes siguiente
- Verificar que `include_cancelled=true` se envía en la URL

---

## DLD-37 — Duplicación de diagnóstico eliminada

**Qué se arregló:** Al asignar una nota de diagnóstico, el texto se duplicaba N veces.

### Pruebas

1. **Crear nota de diagnóstico**
   - Ir a un paciente → Registros clínicos → Agregar nota
   - Escribir un diagnóstico (ej: "Caries en pieza 15")
   - Guardar
   - El diagnóstico debe aparecer UNA SOLA VEZ en el historial

2. **Doble clic / doble submit**
   - Intentar guardar la misma nota dos veces rápidamente (doble clic)
   - Debe aparecer solo UNA vez en la base de datos
   - No debe dar error visible

3. **Diagnósticos diferentes (deben coexistir)**
   - Agregar un segundo diagnóstico diferente para el mismo paciente (ej: "Gingivitis")
   - Ambos diagnósticos deben aparecer (uno cada uno)
   - La protección contra duplicados es por `(paciente + diagnóstico + día)`, no por paciente solo

4. **Via Nova (si aplica)**
   - Pedirle a Nova: "Registrá una nota clínica para [paciente]: diagnóstico X"
   - Pedirlo de nuevo con el mismo diagnóstico
   - Debe existir solo un registro

### Qué buscar si falla
- Verificar que la migración 059 se ejecutó: `SELECT indexname FROM pg_indexes WHERE tablename = 'clinical_records' AND indexname = 'uq_clinical_records_dedup';`
- Si no existe el índice, correr manualmente: `alembic upgrade head`
- Si hay duplicados previos, correr el SQL de dedup ANTES de la migración:
  ```sql
  DELETE FROM clinical_records a USING clinical_records b
  WHERE a.id > b.id
    AND a.tenant_id = b.tenant_id
    AND a.patient_id = b.patient_id
    AND a.diagnosis = b.diagnosis
    AND DATE(a.record_date) = DATE(b.record_date);
  ```

---

## Resumen rápido de verificación

| # | Ticket | Test mínimo | Tiempo estimado |
|---|--------|-------------|-----------------|
| 1 | DLD-49 | Booking completo por WhatsApp sin contradicciones | 3 min |
| 2 | DLD-48/50/51 | Booking completo, verificar mensajes cortos y sin preguntas de más | 3 min |
| 3 | DLD-52 | Registrar pago en plan aprobado | 1 min |
| 4 | DLD-53 | Verificar textarea en descripción de presupuesto | 30 seg |
| 5 | DLD-47 | Comparar agenda pantalla vs PDF impreso | 2 min |
| 6 | DLD-37 | Crear nota clínica, verificar que no se duplica | 1 min |

**Tiempo total estimado de verificación: ~10 minutos**
