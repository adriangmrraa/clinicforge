# Spec: Telegram UX Improvements

## S1: QUICK_ACTIONS Buttons Cleanup

### Requirements
- Remove `reply_markup=QUICK_ACTIONS` from `_process_and_respond()` — Nova responses must NOT include buttons
- Remove `reply_markup=QUICK_ACTIONS` from `_handle_callback()` — callback responses must NOT include buttons
- Keep `reply_markup=QUICK_ACTIONS` ONLY in `_handle_start()` — the `/start` welcome message
- No other behavioral changes

### Scenarios
```
DADO que el usuario envía /start
CUANDO Nova responde con el mensaje de bienvenida
ENTONCES muestra los 4 botones (Agenda, Pendientes, Resumen, Ayuda)

DADO que el usuario envía un mensaje de texto cualquiera
CUANDO Nova responde
ENTONCES la respuesta NO tiene botones — solo texto

DADO que el usuario presiona un botón de QUICK_ACTIONS
CUANDO Nova responde con el resultado
ENTONCES la respuesta NO tiene botones — solo texto
```

---

## S2: enviar_pdf_telegram Tool

### Requirements
- Nueva tool `enviar_pdf_telegram` en NOVA_TOOLS_SCHEMA (formato flat Realtime)
- Parámetros: `patient_id` (optional int), `record_id` (optional string), `tipo_documento` (optional enum: clinical_report, post_surgery, odontogram_art, authorization_request)
- Si `record_id`: buscar ese registro específico en `patient_digital_records`
- Si `patient_id` + `tipo_documento`: buscar el más reciente de ese tipo
- Si `patient_id` solo: buscar el más reciente de cualquier tipo
- Si no existe `pdf_path` o el archivo no existe: generar PDF con `generate_pdf(html_content, output_path)`
- Retornar: `[PDF_ATTACHMENT:{pdf_path}|{title}.pdf]\n{mensaje_confirmación}`
- Si no se encuentra ningún registro: retornar error descriptivo
- Todos los queries filtran por `tenant_id`

### Scenarios
```
DADO que el CEO dice "mandame el informe clínico de García"
CUANDO Nova ejecuta buscar_paciente → enviar_pdf_telegram(patient_id=31, tipo_documento="clinical_report")
ENTONCES la tool busca el registro más reciente tipo clinical_report para patient_id=31
Y genera PDF si no existe
Y retorna "[PDF_ATTACHMENT:/app/uploads/.../abc.pdf|Informe Clínico — García.pdf]\nTe envío el informe clínico."

DADO que el CEO dice "mandame la última ficha de Gamarra"
CUANDO Nova ejecuta enviar_pdf_telegram(patient_id=5)
ENTONCES busca el registro más reciente de cualquier tipo
Y retorna el marcador PDF + confirmación

DADO que no existe ningún registro digital para el paciente
CUANDO se ejecuta enviar_pdf_telegram
ENTONCES retorna "No se encontró ninguna ficha digital para este paciente. ¿Querés que la genere?"

DADO que el PDF no existe en disco pero html_content sí existe
CUANDO se ejecuta enviar_pdf_telegram
ENTONCES genera el PDF con WeasyPrint
Y actualiza pdf_path en la DB
Y retorna el marcador
```

---

## S3: generar_reporte_personalizado Tool

### Requirements
- Nueva tool `generar_reporte_personalizado` en NOVA_TOOLS_SCHEMA
- Parámetros:
  - `titulo` (required string): título del reporte (ej: "Comparativa Abril vs Diciembre 2025")
  - `contenido` (required string): contenido HTML/texto del reporte que Nova escribió basándose en datos recopilados
  - `subtitulo` (optional string): subtítulo o descripción
- La tool:
  1. Carga datos del tenant (clinic_name, logo via `resolve_logo_data_uri`)
  2. Renderiza `custom_report.html` con Jinja2 pasando titulo, subtitulo, contenido, datos del tenant
  3. Genera PDF con WeasyPrint en directorio temporal
  4. Retorna `[PDF_ATTACHMENT:{pdf_path}|{titulo}.pdf]\n{confirmación}`
- El contenido que Nova pasa puede incluir HTML básico: `<h2>`, `<p>`, `<table>`, `<ul>`, `<b>`, `<i>`
- El template hereda de `base.html` (logo, estilos A4, tipografía profesional)
- Los PDFs custom se guardan en `/tmp/nova_reports/` (no en patient_digital_records — no son fichas de pacientes)

### Scenarios
```
DADO que el CEO dice "cruzá datos de abril vs diciembre y haceme un PDF"
CUANDO Nova:
  1. Usa obtener_registros/consultar_datos para recopilar datos
  2. Analiza y escribe el contenido como HTML
  3. Llama generar_reporte_personalizado(titulo="Comparativa Abril vs Diciembre 2025", contenido="<h2>Turnos</h2><p>En abril...</p>...")
ENTONCES el tool genera un PDF branded con el análisis
Y retorna el marcador PDF para envío por Telegram

DADO que el CEO dice "haceme un resumen ejecutivo de la semana en PDF"
CUANDO Nova recopila datos con resumen_semana + resumen_financiero
Y escribe el análisis como HTML
Y llama generar_reporte_personalizado
ENTONCES genera PDF branded y lo envía

DADO que WeasyPrint no está disponible
CUANDO se intenta generar el PDF
ENTONCES retorna "No se pudo generar el PDF. WeasyPrint no está instalado."
```

---

## S4: PDF Attachment Detection in telegram_bot.py

### Requirements
- En `_process_and_respond()`, ANTES de enviar el texto al chat:
  1. Buscar el patrón `[PDF_ATTACHMENT:{path}|{filename}]` en `response_text`
  2. Si se encuentra: extraer path y filename
  3. Verificar que el archivo existe en disco
  4. Enviar el archivo con `update.effective_chat.send_document(document=open(path, 'rb'), filename=filename)`
  5. Stripear el marcador del texto antes de enviarlo y antes de guardarlo en el historial
- Si el archivo no existe: logear warning, no enviar documento, mantener el texto
- Si hay múltiples marcadores: enviar todos los PDFs
- El patrón debe ser regex: `\[PDF_ATTACHMENT:([^|]+)\|([^\]]+)\]`
- También aplicar en `_handle_callback` si algún día los callbacks generan PDFs

### Scenarios
```
DADO que un tool result contiene "[PDF_ATTACHMENT:/app/uploads/x.pdf|Informe.pdf]\nTe envío el informe."
CUANDO _process_and_respond procesa la respuesta
ENTONCES envía /app/uploads/x.pdf como documento con filename "Informe.pdf"
Y luego envía "Te envío el informe." como texto (sin el marcador)

DADO que el archivo en el marcador no existe
CUANDO _process_and_respond intenta enviarlo
ENTONCES logea warning
Y envía solo el texto (sin marcador)

DADO que el response_text no contiene ningún marcador
CUANDO _process_and_respond procesa normalmente
ENTONCES comportamiento idéntico al actual — sin cambios

DADO que el marcador aparece en el texto
CUANDO se guarda en el historial de Redis
ENTONCES el marcador está stripeado — solo se guarda el texto limpio
```

---

## S5: custom_report.html Template

### Requirements
- Nuevo archivo `orchestrator_service/templates/digital_records/custom_report.html`
- Extiende `base.html` (hereda logo, tipografía, estilos A4, header/footer)
- Variables Jinja2:
  - `data.clinic.name` — nombre de la clínica
  - `data.clinic.logo_url` — logo base64 data URI
  - `data.titulo` — título del reporte
  - `data.subtitulo` — subtítulo (opcional)
  - `data.contenido` — contenido HTML libre (lo que Nova escribió)
  - `data.fecha` — fecha de generación
- El contenido se renderiza con `{{ data.contenido | safe }}` (HTML directo de Nova)
- Estilos para tablas, listas y headers dentro del contenido libre
- Footer con fecha de generación y "Generado por Nova AI"

### Scenarios
```
DADO que se renderiza custom_report.html con titulo="Reporte Mensual" y contenido HTML
CUANDO WeasyPrint genera el PDF
ENTONCES el PDF tiene logo de la clínica en el header
Y título "Reporte Mensual" como H1
Y el contenido HTML renderizado con estilos profesionales
Y footer con fecha y "Generado por Nova AI"
```

---

## S6: System Prompt — Reportes y PDFs Proactivos

### Requirements

Agregar las siguientes instrucciones al system prompt de Nova en `nova_prompt.py`, tanto en la sección general como reforzada en MODO TELEGRAM.

#### Bloque: REPORTES Y DOCUMENTOS PDF

Agregar DESPUÉS del bloque de FICHAS DIGITALES existente en el prompt:

```
REPORTES PDF PERSONALIZADOS (tu diferencial analítico):
Tenés generar_reporte_personalizado para crear PDFs branded con CUALQUIER análisis que el CEO necesite.

FLUJO DE GENERACIÓN DE REPORTES:
1. RECOPILAR: Usá obtener_registros, consultar_datos, resumen_semana, resumen_financiero, etc. para juntar TODOS los datos necesarios
2. ANALIZAR: Cruzá, compará, calculá tendencias, identificá patrones
3. REDACTAR: Escribí el contenido como HTML profesional con tablas, bullets, secciones
4. GENERAR: Llamá generar_reporte_personalizado(titulo, contenido_html)
5. El PDF se envía automáticamente al chat

FORMATO DEL CONTENIDO HTML QUE ESCRIBÍS:
- <h2> para secciones principales
- <h3> para sub-secciones
- <table> con <thead>/<tbody> para datos comparativos (SIEMPRE con bordes y padding)
- <ul>/<li> para listas de hallazgos
- <b> para datos clave (montos, porcentajes, nombres)
- <p> para párrafos de análisis
- Incluir SIEMPRE: resumen ejecutivo al inicio, conclusiones al final
- Montos: $XX.XXX con punto de miles
- Fechas: DD/MM/YYYY
- Porcentajes: con 1 decimal (ej: 23.5%)

TIPOS DE REPORTES QUE PODÉS GENERAR:
"Comparame abril vs diciembre" → obtener_registros(appointments, abril) + obtener_registros(appointments, diciembre) → tabla comparativa turnos/facturación/cancelaciones/no-shows → generar_reporte_personalizado
"Informe de productividad de Laura" → rendimiento_profesional + appointments + billing → tabla detallada por semana/mes → generar_reporte_personalizado
"Reporte de deudores" → treatment_plans activos → payments → calcular saldos → tabla paciente|plan|debe|último pago → generar_reporte_personalizado
"Análisis de marketing" → meta_ad_insights + patients(acquisition_source) → ROI por campaña → generar_reporte_personalizado
"Resumen ejecutivo del mes" → resumen_semana + resumen_financiero + facturacion_pendiente + contar_registros → consolidar → generar_reporte_personalizado
"Pacientes inactivos" → patients sin appointments en 6+ meses → tabla con datos de contacto → generar_reporte_personalizado
"Proyección de ingresos" → appointments scheduled próximo mes + tarifas → estimar ingresos → generar_reporte_personalizado

PROACTIVIDAD EN REPORTES:
- Si el CEO pide un análisis complejo → OFRECÉ generar el PDF: "¿Querés que te lo arme como PDF con el logo de la clínica?"
- Si los datos son extensos (tabla 10+ filas) → SUGERÍ PDF en vez de texto largo: "Son muchos datos, ¿te lo mando como PDF?"
- Si el CEO dice "mandame", "pasame", "enviame" → generar PDF directamente, sin preguntar

ENVÍO DE FICHAS EXISTENTES:
"Mandame el informe de García" / "pasame la ficha" / "enviame el post-quirúrgico" → enviar_pdf_telegram
"Generá y mandame" → generar_ficha_digital → enviar_pdf_telegram (ENCADENAR)
NUNCA digas "no puedo enviar archivos". PODÉS y DEBÉS enviar PDFs por este chat.
```

#### Bloque MODO TELEGRAM — Refuerzo de reportes

Agregar al final del bloque `page=telegram → MODO TELEGRAM:` existente:

```
  REPORTES PDF:
  Cuando el CEO pide análisis/reportes → recopilar datos → generar_reporte_personalizado → PDF enviado al chat.
  Cuando pide "mandame la ficha/informe" → enviar_pdf_telegram.
  Si los datos son extensos → proponé PDF: "Son muchos datos, ¿te armo un PDF?"
  SIEMPRE ofrecé PDF cuando el análisis tiene tablas grandes o comparativas.
```

### Scenarios
```
DADO que el CEO dice "comparame los turnos de abril contra diciembre"
CUANDO Nova recopila datos de ambos meses
ENTONCES Nova analiza, redacta HTML con tablas comparativas
Y llama generar_reporte_personalizado automáticamente
Y el CEO recibe el PDF en el chat

DADO que el CEO dice "cuánto facturamos este mes"
CUANDO Nova responde con un resumen de 3 líneas
ENTONCES NO genera PDF — la respuesta es corta, texto es suficiente

DADO que el CEO dice "cuánto facturó cada profesional este mes detallado por semana"
CUANDO Nova recopila datos extensos (tabla 4 profesionales × 4 semanas)
ENTONCES Nova responde con un resumen breve en texto
Y OFRECE: "Son muchos datos, ¿te armo un PDF con el detalle completo?"

DADO que el CEO dice "mandame el informe clínico de García"
CUANDO Nova ejecuta buscar_paciente → enviar_pdf_telegram
ENTONCES el CEO recibe el PDF de la ficha clínica existente en el chat

DADO que el CEO dice "generame y mandame el post-quirúrgico de García"
CUANDO Nova ejecuta generar_ficha_digital → enviar_pdf_telegram
ENTONCES genera la ficha, crea el PDF, y lo envía al chat (encadenamiento)

DADO que el CEO dice "pasame un reporte de los deudores"
CUANDO Nova detecta "pasame" como instrucción de envío
ENTONCES genera el reporte directamente sin preguntar "¿querés PDF?"
Y envía el PDF branded al chat

DADO que el CEO pide algo que Nova ya respondió en texto pero dice "pasame eso en PDF"
CUANDO Nova tiene el contexto del historial
ENTONCES toma el contenido de su respuesta anterior
Y lo formatea como HTML profesional
Y genera el PDF con generar_reporte_personalizado
```
