# Nova Dental Assistant — JIRA Tickets

**Proyecto**: CLINIC (ClinicForge)
**Fecha**: 2026-03-26
**Total**: 5 Epics, 30 Stories, 105 Story Points

---

## EPIC 0: Nova Onboarding Flow
**Key**: CLINIC-NOVA-ONBOARD
**Descripcion**: Flujo de onboarding guiado para nuevas clinicas. Nova guia al CEO/admin paso a paso en la configuracion inicial: profesionales, horarios, tratamientos, WhatsApp, Google Calendar, FAQs, datos bancarios, precio consulta. 8 pasos con tracking de progreso.
**Prioridad**: Highest
**Labels**: nova, onboarding, fase-0
**Story Points total**: 13

---

### Story 0.1: Crear endpoint GET /admin/nova/onboarding-status
**Tipo**: Story
**Prioridad**: Highest
**Story Points**: 3
**Descripcion**:
Retorna estado de onboarding de la sede actual. 8 checks booleanos:
1. has_professionals — professionals activos
2. has_working_hours — profesionales con horarios
3. has_treatment_types — tratamientos activos
4. has_whatsapp — credenciales ycloud
5. has_google_calendar — google_oauth_tokens
6. has_faqs — clinic_faqs >= 3
7. has_bank_details — tenant.bank_cbu o bank_alias
8. has_consultation_price — tenant.consultation_price not null

Response: { completed_steps, total_steps, next_step, is_complete, steps: [{name, completed, label}] }

**Acceptance Criteria**:
- [ ] Retorna 8 checks correctos
- [ ] next_step indica el primer paso incompleto
- [ ] is_complete=true cuando los 8 estan OK
- [ ] tenant_id isolation

**Subtasks**:
- [ ] Implementar endpoint en nova_routes.py
- [ ] 8 queries SQL de verificacion
- [ ] Tests unitarios

---

### Story 0.2: Crear endpoint POST /admin/nova/onboarding/complete-step
**Tipo**: Story
**Prioridad**: High
**Story Points**: 5
**Descripcion**:
Endpoint que permite completar un paso de onboarding con datos. Body: { step, data }.
Cada paso valida y guarda la config:
- "professionals": crear profesional con datos minimos
- "working_hours": configurar horarios del profesional
- "treatment_types": crear tipos de tratamiento
- "whatsapp": validar y guardar credenciales ycloud
- "google_calendar": redirigir a flow OAuth
- "faqs": crear FAQs iniciales
- "bank_details": guardar CBU/alias en tenant
- "consultation_price": guardar precio en tenant

Retorna onboarding-status actualizado.

**Acceptance Criteria**:
- [ ] Cada paso guarda datos correctamente
- [ ] Retorna status actualizado
- [ ] Validaciones por paso (nombre requerido, etc.)
- [ ] Solo CEO puede ejecutar

**Subtasks**:
- [ ] Implementar handler por cada uno de los 8 pasos
- [ ] Validaciones de datos por paso
- [ ] Retornar onboarding-status actualizado
- [ ] Tests unitarios

---

### Story 0.3: Frontend — Onboarding card en Nova widget
**Tipo**: Story
**Prioridad**: High
**Story Points**: 3
**Descripcion**:
Card en tab Chat que muestra progreso de onboarding cuando is_complete=false:
- Barra de progreso (X/8)
- Lista de pasos con checkmarks (completados) y circulos vacios (pendientes)
- Boton "Continuar configuracion" que inicia chat guiado para el siguiente paso
- Cuando todos completos, card desaparece y muestra mensaje de celebracion
- Solo visible si onboarding incompleto

**Acceptance Criteria**:
- [ ] Card muestra progreso correcto
- [ ] "Continuar" inicia conversacion guiada
- [ ] Card desaparece al completar onboarding
- [ ] Mensaje de celebracion al completar

**Subtasks**:
- [ ] Implementar OnboardingCard component
- [ ] Conectar con GET /admin/nova/onboarding-status
- [ ] Implementar flow de chat guiado por paso
- [ ] Implementar estado de celebracion

---

### Story 0.4: Nova tool onboarding_status + system prompt onboarding
**Tipo**: Story
**Prioridad**: Medium
**Story Points**: 2
**Descripcion**:
- Tool `onboarding_status` para que Nova pueda consultar el estado por voz/chat
- System prompt incluye reglas de onboarding: detectar sede nueva, sugerir pasos faltantes, guiar configuracion
- Nova dice proactivamente: "Veo que la sede {nombre} todavia no tiene {paso} configurado. Queres que te ayude?"

**Acceptance Criteria**:
- [ ] Tool retorna estado de onboarding
- [ ] Nova menciona proactivamente pasos faltantes
- [ ] Guia paso a paso funciona por chat

**Subtasks**:
- [ ] Implementar tool onboarding_status
- [ ] Actualizar system prompt con reglas de onboarding

---

## EPIC 1: Nova Backend — Routes + WS + Tools
**Key**: CLINIC-NOVA-BE
**Descripcion**: Backend completo de Nova: endpoints REST, WebSocket handler para voz bidireccional con OpenAI Realtime, y 20 tools de function calling adaptadas al dominio dental.
**Prioridad**: Highest
**Labels**: nova, backend, fase-1
**Story Points total**: 42

---

### Story 1.1: Crear nova_routes.py con endpoint GET /admin/nova/context
**Tipo**: Story
**Prioridad**: Highest
**Story Points**: 3
**Descripcion**:
Endpoint que retorna contexto de Nova para la pagina actual del dashboard. Solo SQL, $0.
- Recibe `page` (string) y `patient_id` (optional int)
- Ejecuta 9 checks estaticos (turnos sin confirmar, huecos agenda, recordatorios, facturacion pendiente, cancelaciones, pacientes sin anamnesis, FAQ insuficientes, etc.)
- Retorna: checks[], health_score, stats{}, greeting contextual
- Greeting dinamico segun pagina (agenda, pacientes, chats, dashboard, etc.)
- Greeting basado en score (<50, 50-80, >80)
- Requiere `verify_admin_token`
- Filtrar por `tenant_id` del usuario autenticado

**Acceptance Criteria**:
- [ ] GET /admin/nova/context?page=agenda retorna checks + greeting + stats
- [ ] Greeting correcto por pagina
- [ ] tenant_id isolation
- [ ] Roles respetados (profesional no ve facturacion global)

**Subtasks**:
- [ ] Crear `orchestrator_service/routes/nova_routes.py` con router prefix `/admin/nova`
- [ ] Implementar 9 queries SQL de health checks
- [ ] Implementar logica de greeting por pagina + score
- [ ] Registrar router en `main.py`
- [ ] Tests unitarios

---

### Story 1.2: Crear endpoint GET /admin/nova/health-check con score ponderado
**Tipo**: Story
**Prioridad**: High
**Story Points**: 3
**Descripcion**:
Health-check completo con score 0-100 ponderado. 13 checks (8 operativos + 5 configuracion).
- Score: 50 puntos config (profesionales, horarios, tratamientos, WhatsApp, GCal, FAQ) + 50 puntos operativo (turnos semana, sin confirmar, pagos, recordatorios, derivaciones)
- Retorna: score, checks[] con type/icon/message/action/weight, completed[], top_priority, stats{}
- Solo tenants del usuario autenticado

**Acceptance Criteria**:
- [ ] Score sube cuando se resuelven checks
- [ ] checks[] ordenados por peso descendente
- [ ] completed[] lista items OK
- [ ] top_priority = primer check de mayor peso

**Subtasks**:
- [ ] Implementar 8 checks operativos con queries SQL
- [ ] Implementar 5 checks de configuracion
- [ ] Implementar calculo de score ponderado
- [ ] Tests unitarios

---

### Story 1.3: Crear endpoint POST /admin/nova/session (sesion OpenAI Realtime)
**Tipo**: Story
**Prioridad**: Highest
**Story Points**: 5
**Descripcion**:
Crea sesion para el widget de voz. Recibe page + context_summary + patient_id opcional.
- Resolver OPENAI_API_KEY
- Construir system prompt dental con contexto + tools + pagina + paciente
- Generar session_id (uuid4)
- Guardar config en Redis (TTL 360s)
- Rate limiting: max 1 sesion simultanea por usuario, max 5 min, max 50 tool calls

**Acceptance Criteria**:
- [ ] POST /admin/nova/session retorna session_id valido
- [ ] Config guardada en Redis con TTL 360s
- [ ] System prompt incluye contexto de pagina y paciente
- [ ] Rate limiting funciona (no 2 sesiones simultaneas)

**Subtasks**:
- [ ] Implementar endpoint POST /admin/nova/session
- [ ] Construir system prompt dental dinamico
- [ ] Guardar sesion en Redis con TTL
- [ ] Implementar rate limiting por usuario
- [ ] Tests unitarios

---

### Story 1.4: Implementar WebSocket handler /public/nova/realtime-ws/{session_id}
**Tipo**: Story
**Prioridad**: Highest
**Story Points**: 8
**Descripcion**:
Bridge WebSocket entre browser y OpenAI Realtime API. El handler:
1. Valida session_id en Redis
2. Abre WS a OpenAI Realtime (`wss://api.openai.com/v1/realtime`)
3. Envia session.update con system prompt + tools + VAD config
4. Forward bidireccional: browser audio → OpenAI, OpenAI audio → browser
5. Maneja eventos: response.audio.delta, response.audio.done, transcript, speech_started, function_call
6. Ejecuta tools cuando OpenAI lo pide → retorna resultado

VAD config dental: threshold=0.5, prefix_padding=800ms, silence_duration=5000ms

**Acceptance Criteria**:
- [ ] WS connection exitosa con session_id valido
- [ ] Audio bidireccional funciona (PCM16 24kHz)
- [ ] Transcripciones se envian al browser
- [ ] nova_audio_done se envia cuando OpenAI termina de hablar
- [ ] user_speech_started se envia para barge-in
- [ ] Session se cierra limpiamente al desconectar

**Subtasks**:
- [ ] Crear handler WS en main.py
- [ ] Implementar bridge bidireccional OpenAI ↔ Browser
- [ ] Implementar forwarding de eventos (audio.delta, audio.done, transcript, speech_started, response.done)
- [ ] Implementar ejecucion de tools en function_call_arguments.done
- [ ] Agregar `websockets` a requirements.txt
- [ ] Configurar VAD dental (threshold 0.5, silence 5000ms)
- [ ] Tests de conexion y cleanup

---

### Story 1.5: Implementar 6 tools de Pacientes
**Tipo**: Story
**Prioridad**: High
**Story Points**: 5
**Descripcion**:
Tools para OpenAI Realtime function calling:
1. `buscar_paciente(query)` — busca por nombre, apellido, DNI o telefono (ILIKE, LIMIT 5)
2. `ver_paciente(patient_id)` — ficha completa: datos, historial, proximos turnos, obra social
3. `registrar_paciente(first_name, last_name, phone, dni?, insurance?)` — crea paciente nuevo
4. `actualizar_paciente(patient_id, field, value)` — actualiza campo especifico
5. `historial_clinico(patient_id)` — registros clinicos, diagnosticos, odontograma. **Solo profesional/CEO**
6. `registrar_nota_clinica(patient_id, diagnosis, treatment_notes?, tooth_number?, tooth_status?, surface?)` — agrega nota clinica. **Solo profesional**

Todas validan tenant_id. Tools 5 y 6 validan rol.

**Acceptance Criteria**:
- [ ] Cada tool retorna JSON correcto
- [ ] buscar_paciente funciona con nombre, DNI y telefono
- [ ] historial_clinico rechaza secretarias
- [ ] registrar_nota_clinica acepta odontograma (pieza + superficie)
- [ ] Tenant isolation en todas las queries

**Subtasks**:
- [ ] Implementar buscar_paciente
- [ ] Implementar ver_paciente
- [ ] Implementar registrar_paciente
- [ ] Implementar actualizar_paciente
- [ ] Implementar historial_clinico (con check de rol)
- [ ] Implementar registrar_nota_clinica (con check de rol + odontograma)

---

### Story 1.6: Implementar 6 tools de Turnos
**Tipo**: Story
**Prioridad**: High
**Story Points**: 5
**Descripcion**:
Tools de gestion de turnos:
1. `ver_agenda(date?, professional_id?)` — turnos del dia con horario, paciente, tipo, estado
2. `proximo_paciente()` — siguiente turno del dia para el profesional actual
3. `verificar_disponibilidad(date, treatment_type?, professional_id?)` — reusar logica existente de check_availability/gcal_service
4. `agendar_turno(patient_id, date, time, treatment_type, professional_id?, notes?)` — crear turno + emitir Socket.IO NEW_APPOINTMENT
5. `cancelar_turno(appointment_id, reason?)` — cancelar + emitir APPOINTMENT_UPDATED
6. `confirmar_turnos(appointment_ids?)` — confirmar uno o todos los pendientes del dia

**Acceptance Criteria**:
- [ ] ver_agenda retorna turnos ordenados por hora
- [ ] proximo_paciente retorna solo el siguiente (no pasados)
- [ ] agendar_turno emite evento Socket.IO
- [ ] confirmar_turnos sin IDs confirma todos los del dia
- [ ] Tenant isolation

**Subtasks**:
- [ ] Implementar ver_agenda
- [ ] Implementar proximo_paciente
- [ ] Implementar verificar_disponibilidad (reusar gcal_service)
- [ ] Implementar agendar_turno + Socket.IO emit
- [ ] Implementar cancelar_turno + Socket.IO emit
- [ ] Implementar confirmar_turnos (batch)

---

### Story 1.7: Implementar 3 tools de Tratamientos/Facturacion + 3 Analytics/Config + 2 Navegacion
**Tipo**: Story
**Prioridad**: Medium
**Story Points**: 5
**Descripcion**:
**Tratamientos/Facturacion (3)**:
1. `listar_tratamientos(category?)` — tipos de tratamiento con precios y duracion
2. `registrar_pago(appointment_id, amount, method, notes?)` — registrar pago. **Solo CEO/secretaria**
3. `facturacion_pendiente()` — turnos completados sin pago

**Analytics/Config (3)**:
4. `resumen_semana()` — turnos, cancelaciones, pacientes nuevos, facturacion. **Solo CEO**
5. `rendimiento_profesional(professional_id, period)` — metricas de profesional. **Solo CEO**
6. `actualizar_faq(question, answer)` — agregar/actualizar FAQ de la clinica

**Navegacion (2)**:
7. `ir_a_pagina(page)` — navegar a pagina del dashboard (retorna evento para frontend)
8. `ir_a_paciente(patient_id)` — abrir ficha de paciente

**Acceptance Criteria**:
- [ ] registrar_pago rechaza profesionales (solo CEO/secretary)
- [ ] resumen_semana solo accesible por CEO
- [ ] actualizar_faq crea o actualiza FAQ existente
- [ ] ir_a_pagina retorna evento de navegacion al frontend

**Subtasks**:
- [ ] Implementar listar_tratamientos
- [ ] Implementar registrar_pago (con check rol)
- [ ] Implementar facturacion_pendiente
- [ ] Implementar resumen_semana (con check rol CEO)
- [ ] Implementar rendimiento_profesional (con check rol CEO)
- [ ] Implementar actualizar_faq
- [ ] Implementar ir_a_pagina + ir_a_paciente (eventos navegacion)

---

### Story 1.8: Implementar 4 tools multi-sede (CEO)
**Tipo**: Story
**Prioridad**: High
**Story Points**: 5
**Descripcion**:
4 tools exclusivas para CEO multi-sede:
1. `resumen_sedes()` — consolidado de todas las sedes: turnos, pacientes, facturacion, score
2. `comparar_sedes(metric, period?)` — compara cancelaciones, nuevos pacientes, facturacion, ocupacion entre sedes
3. `switch_sede(clinic_name)` — cambia contexto activo a otra sede (busca ILIKE)
4. `onboarding_status(clinic_name?)` — estado de configuracion de sede

Todas validan role=ceo. resumen_sedes y comparar_sedes hacen queries cross-tenant.

**Acceptance Criteria**:
- [ ] resumen_sedes retorna datos de todas las sedes
- [ ] comparar_sedes ordena por metrica elegida
- [ ] switch_sede cambia contexto y lo persiste en sesion
- [ ] Solo CEO puede ejecutar

**Subtasks**:
- [ ] Implementar resumen_sedes (cross-tenant queries)
- [ ] Implementar comparar_sedes con metricas configurables
- [ ] Implementar switch_sede (ILIKE search + session update)
- [ ] Implementar onboarding_status
- [ ] Validar role=ceo en las 4 tools

---

### Story 1.9: Actualizar endpoints /context y /health-check para multi-sede CEO
**Tipo**: Story
**Prioridad**: High
**Story Points**: 3
**Descripcion**:
- GET /admin/nova/context: para CEO sin tenant_id especifico, retornar contexto consolidado + array sedes con score y top alert
- GET /admin/nova/health-check: para CEO, agregar consolidated_score (promedio) y per_sede array con score y checks por sede
- POST /admin/nova/session: incluir lista de sedes en system prompt para CEO

**Acceptance Criteria**:
- [ ] CEO ve consolidated_score + per_sede
- [ ] Staff ve single-tenant (sin cambios)
- [ ] Session prompt incluye sedes para CEO

**Subtasks**:
- [ ] Actualizar /context con logica CEO multi-sede
- [ ] Actualizar /health-check con consolidated_score + per_sede
- [ ] Actualizar /session con lista de sedes en prompt

---

## EPIC 2: Nova Frontend — Widget + Voz + Chat
**Key**: CLINIC-NOVA-FE
**Descripcion**: Widget flotante de Nova integrado en el Layout de ClinicForge. 3 tabs (Chat, Salud, Insights), voice pipeline completo con echo prevention, action routing, y contexto enriquecido por pagina.
**Prioridad**: Highest
**Labels**: nova, frontend, fase-2
**Story Points total**: 29

---

### Story 2.1: Crear NovaWidget.tsx — estructura base + boton flotante
**Tipo**: Story
**Prioridad**: Highest
**Story Points**: 3
**Descripcion**:
Componente flotante presente en toda la plataforma (excepto login, anamnesis, demo).
- Boton: fixed bottom-6 right-6, w-14 h-14, gradiente violet-600 → indigo-600
- Pulse 10s al cargar
- Badge rojo con numero de alertas criticas
- Click abre panel w-80 lg:w-[420px] h-[560px], dark theme bg-[#0f0f17]
- 3 tabs: Chat, Salud, Insights
- Header con score
- Exclusiones: /login, /anamnesis/*, /demo, /privacy, /terms

**Acceptance Criteria**:
- [ ] Widget visible en todas las paginas protegidas
- [ ] Widget NO visible en rutas publicas
- [ ] Click abre/cierra panel con animacion
- [ ] Badge muestra alertas criticas
- [ ] 3 tabs funcionales

**Subtasks**:
- [ ] Crear componente NovaWidget.tsx
- [ ] Implementar boton flotante con badge
- [ ] Implementar panel con 3 tabs
- [ ] Implementar logica de exclusion de rutas
- [ ] Integrar en Layout.tsx

---

### Story 2.2: Implementar Tab Chat — mensajes + input texto
**Tipo**: Story
**Prioridad**: Highest
**Story Points**: 3
**Descripcion**:
Tab de chat con:
- Quick Checks (top): 2 checks mas urgentes como cards clicables con colores por tipo (alert=rojo, warning=amber, suggestion=cyan, info=blue)
- Historial de mensajes: burbujas usuario (violet, derecha) y Nova (white/5, izquierda)
- Loading: "Nova pensando..." con animate-pulse
- Input texto: enviar con Enter, boton Send violet-600
- Envio por POST texto al WS (type: text_message)

**Acceptance Criteria**:
- [ ] Quick checks clicables navegan a pagina correcta
- [ ] Mensajes se muestran en burbujas con colores correctos
- [ ] Enter envia mensaje
- [ ] Loading state mientras Nova responde

**Subtasks**:
- [ ] Implementar Quick Checks cards
- [ ] Implementar historial de mensajes (burbujas)
- [ ] Implementar input de texto + envio
- [ ] Conectar con WS para envio/recepcion de texto

---

### Story 2.3: Implementar Tab Salud — score + checks + stats
**Tipo**: Story
**Prioridad**: High
**Story Points**: 3
**Descripcion**:
Tab que muestra health-check de la clinica:
- Score central (0-100) con barra de progreso y color por rango (verde >=80, amarillo 50-79, rojo <50)
- Lista de completados (checkmarks verdes)
- Cards pendientes ordenadas por peso, clicables → navegan a pagina
- Stats grid 2x2: turnos hoy, pacientes totales, pagos pendientes, cancelaciones hoy
- Datos de GET /admin/nova/health-check

**Acceptance Criteria**:
- [ ] Score muestra color correcto por rango
- [ ] Completados con checkmarks
- [ ] Pendientes clicables navegan correctamente
- [ ] Stats grid con datos reales

**Subtasks**:
- [ ] Implementar score central con barra de progreso
- [ ] Implementar lista de completados
- [ ] Implementar cards de pendientes con action routing
- [ ] Implementar stats grid
- [ ] Conectar con endpoint health-check

---

### Story 2.4: Implementar Tab Insights — daily analysis
**Tipo**: Story
**Prioridad**: Medium
**Story Points**: 3
**Descripcion**:
Tab que muestra el analisis diario generado por el cron:
- Estado vacio: "Sin datos de hoy" + explicacion
- Con datos: resumen, stats operativos (grid 4 cols), temas frecuentes (con cantidad), problemas detectados, cancelacion insights, sugerencias con boton "Aplicar sugerencia"
- "Aplicar sugerencia" llama POST /admin/nova/apply-suggestion → crea FAQ → muestra badge "Aplicada"
- Datos de GET /admin/nova/daily-analysis

**Acceptance Criteria**:
- [ ] Estado vacio muestra mensaje informativo
- [ ] Resumen + temas + problemas se muestran correctamente
- [ ] "Aplicar sugerencia" crea FAQ en DB
- [ ] Badge "Aplicada" aparece tras aplicar

**Subtasks**:
- [ ] Implementar estado vacio
- [ ] Implementar layout con resumen + stats + temas + problemas + sugerencias
- [ ] Implementar "Aplicar sugerencia" (POST + badge)
- [ ] Conectar con endpoint daily-analysis

---

### Story 2.5: Implementar Voice Pipeline — captura + playback + echo prevention
**Tipo**: Story
**Prioridad**: Highest
**Story Points**: 8
**Descripcion**:
Pipeline de voz completo:

**Captura (browser → server)**:
- getUserMedia → AudioContext nativo (48kHz) → ScriptProcessor 4096
- Resample 48→24kHz → Float32→PCM16 → enviar por WS como ArrayBuffer
- 3 gates en onaudioprocess: micPaused, novaPlaying, WS cerrado

**Playback (server → browser)**:
- Recibir ArrayBuffer PCM16 → Float32 → AudioContext 24kHz
- Cola secuencial con nextPlayTimeRef

**Echo prevention (3 capas)**:
1. Auto-mute mic al recibir audio de Nova
2. Auto-unmute cuando Nova termina (nova_audio_done + remainingMs + 300ms buffer)
3. Safety net en response_done (500ms delay)

**Barge-in**: user_speech_started → cancelPlayback() → cerrar AudioContext + reset cola

**Indicador UI**: idle → listening → processing → speaking → listening

**Cleanup**: cerrar WS, parar stream, desconectar processor, cerrar AudioContexts, reset refs

**Acceptance Criteria**:
- [ ] Hablar por mic → Nova responde por voz + texto
- [ ] Sin eco (3 capas funcionando)
- [ ] Sin superposicion de audio (cola secuencial)
- [ ] Barge-in funciona limpio
- [ ] Indicador de estado correcto en UI
- [ ] Cleanup al cerrar widget

**Subtasks**:
- [ ] Implementar captura de audio (mic → resample → PCM16 → WS)
- [ ] Implementar playback secuencial (cola con nextPlayTimeRef)
- [ ] Implementar echo prevention capa 1 (auto-mute)
- [ ] Implementar echo prevention capa 2 (auto-unmute con timing)
- [ ] Implementar echo prevention capa 3 (safety net)
- [ ] Implementar barge-in (cancelPlayback)
- [ ] Implementar indicador de estado en UI
- [ ] Implementar cleanup completo

---

### Story 2.6: Implementar Toast Notification al entrar
**Tipo**: Story
**Prioridad**: Medium
**Story Points**: 2
**Descripcion**:
Toast al entrar a la plataforma si hay alertas criticas:
- Posicion: fixed bottom-24 left-6
- Contenido: "Nova: {alerta mas critica}"
- Boton "Ver detalles" → abre widget
- Auto-dismiss: 8 segundos
- 1 vez por sesion (sessionStorage)
- Delay 2s para no bloquear carga

**Acceptance Criteria**:
- [ ] Toast aparece con alerta critica
- [ ] Solo 1 vez por sesion
- [ ] Auto-dismiss a 8s
- [ ] "Ver detalles" abre widget

**Subtasks**:
- [ ] Implementar componente Toast
- [ ] Logica de sessionStorage para mostrar 1 vez
- [ ] Conectar con health-check endpoint
- [ ] Click "Ver detalles" abre NovaWidget

---

### Story 2.7: Action Routing + Page Detection + Contexto enriquecido
**Tipo**: Story
**Prioridad**: High
**Story Points**: 2
**Descripcion**:
- **Action routing**: mapeo de acciones de checks a rutas (confirmar_turnos→/agenda, conectar_gcal→/configuracion, etc.)
- **Page detection**: detectar pagina actual por pathname (agenda, pacientes, chats, etc.)
- **Contexto enriquecido**: segun pagina enviar contexto extra al POST /admin/nova/session:
  - agenda: turnos del dia, proximo paciente
  - pacientes/:id: ficha del paciente seleccionado
  - chats: conversacion activa
  - analytics: metricas semana
  - configuracion: estado integraciones

**Acceptance Criteria**:
- [ ] Click en check navega a pagina correcta
- [ ] Pagina actual se detecta y envia al backend
- [ ] Contexto de paciente se incluye en /pacientes/:id

**Subtasks**:
- [ ] Implementar ACTION_ROUTES map
- [ ] Implementar page detection por pathname
- [ ] Implementar contexto enriquecido por pagina
- [ ] Extraer patient_id de URL cuando aplica

---

### Story 2.8: Configurar nginx proxy para WebSocket Nova
**Tipo**: Story
**Prioridad**: High
**Story Points**: 2
**Descripcion**:
Agregar bloque en nginx.conf del frontend para proxear WebSocket de Nova:
- Location: `/api/public/nova/`
- Proxy pass: `http://orchestrator:8000/public/nova/`
- Headers: Upgrade, Connection "upgrade", Host, X-Real-IP
- Timeouts: read 600s, send 600s

**Acceptance Criteria**:
- [ ] WS connection funciona a traves de nginx
- [ ] Sin timeout prematuro (600s)

**Subtasks**:
- [ ] Agregar bloque location en nginx.conf
- [ ] Testear conexion WS a traves del proxy

---

### Story 2.9: Sede selector dropdown en widget (CEO)
**Tipo**: Story
**Prioridad**: High
**Story Points**: 3
**Descripcion**:
Dropdown en header del widget para que CEO seleccione sede:
- Muestra sede actual con mini-score
- Lista todas las sedes con score
- Opcion "Ver todas las sedes" para vista consolidada
- Cambiar sede actualiza X-Tenant-ID en localStorage y recarga contexto Nova
- Solo visible si user.role === 'ceo'
- Staff: solo muestra nombre de clinica (sin dropdown)

**Acceptance Criteria**:
- [ ] Dropdown visible solo para CEO
- [ ] Cambiar sede recarga datos
- [ ] "Ver todas" muestra consolidado
- [ ] Staff no ve dropdown

**Subtasks**:
- [ ] Implementar SedeSelector component
- [ ] Logica de switch (localStorage + reload context)
- [ ] Vista consolidada multi-sede
- [ ] Ocultar para staff

---

## EPIC 3: Nova Health Check Clinico
**Key**: CLINIC-NOVA-HEALTH
**Descripcion**: Sistema de monitoreo proactivo con 13 health checks clinicos, score ponderado 0-100, greeting contextual por pagina, y toast de alertas. Solo SQL, $0.
**Prioridad**: High
**Labels**: nova, health, fase-3
**Story Points total**: 8

---

### Story 3.1: Implementar 8 checks operativos
**Tipo**: Story
**Prioridad**: High
**Story Points**: 3
**Descripcion**:
Checks que cambian cada dia:
1. Turnos sin confirmar hoy (alert, peso 10)
2. Huecos grandes en agenda manana >2h (suggestion, peso 5)
3. Recordatorios no enviados para manana (alert, peso 8)
4. Facturacion pendiente ultimos 30 dias (warning, peso 7)
5. Cancelaciones del dia (info, peso 3)
6. Pacientes nuevos sin anamnesis ultimos 7 dias (suggestion, peso 4)
7. Derivaciones a humano >3 en 24h (alert, peso 6)
8. Pacientes sin control hace 6+ meses (suggestion, peso 4)

**Acceptance Criteria**:
- [ ] Cada check retorna type, icon, message, action, weight
- [ ] Queries filtran por tenant_id
- [ ] Check 2 (huecos) compara working_hours vs turnos reales
- [ ] Check 7 detecta contenido de derivhumano en chat_messages

**Subtasks**:
- [ ] Implementar checks 1-4 (alta prioridad)
- [ ] Implementar checks 5-8 (media prioridad)
- [ ] Implementar deteccion de huecos comparando working_hours vs slots ocupados

---

### Story 3.2: Implementar 5 checks de configuracion
**Tipo**: Story
**Prioridad**: Medium
**Story Points**: 2
**Descripcion**:
Checks que cambian rara vez:
9. Profesionales sin horarios configurados (warning, peso 8)
10. Google Calendar no conectado (warning, peso 6)
11. WhatsApp no conectado (warning, peso 8)
12. FAQ insuficientes <3 (suggestion, peso 5)
13. Sin tipos de tratamiento activos (warning, peso 7)

**Acceptance Criteria**:
- [ ] Cada check retorna type, icon, message, action, weight
- [ ] Check 10 consulta google_oauth_tokens
- [ ] Check 11 consulta credentials WHERE category='ycloud'

**Subtasks**:
- [ ] Implementar checks 9-13
- [ ] Tests unitarios

---

### Story 3.3: Implementar calculo de score y greeting contextual
**Tipo**: Story
**Prioridad**: High
**Story Points**: 3
**Descripcion**:
**Score (0-100)**:
- Config (50 pts max): profesionales activos (10), horarios (10), tratamientos (10), WhatsApp (10), GCal (5), FAQ>=3 (5)
- Operativo (50 pts max): turnos semana (10), sin confirmar==0 (10), pagos OK (10), recordatorios>=80% (10), derivaciones<=3 (10)

**Greeting**:
- score <50: "La clinica necesita atencion. Lo mas urgente: {top_check}"
- score 50-80: "Va bien! Pero podes mejorar: {top_suggestion}"
- score >80: greeting por pagina (agenda, pacientes, chats, etc.)

**Acceptance Criteria**:
- [ ] Score correcto segun checks activos
- [ ] Greeting varia por score y pagina
- [ ] Score se incluye en response de /context y /health-check

**Subtasks**:
- [ ] Implementar funcion de calculo de score
- [ ] Implementar build_greeting(page, checks, score, stats)
- [ ] Integrar en endpoints /context y /health-check

---

## EPIC 4: Nova Daily Analysis + Insights
**Key**: CLINIC-NOVA-ANALYSIS
**Descripcion**: Cron cada 12h que analiza conversaciones + actividad operativa con GPT-4o-mini, genera insights accionables y sugerencias auto-aplicables. ~$0.003/clinica/ejecucion.
**Prioridad**: Medium
**Labels**: nova, analysis, ia, fase-4
**Story Points total**: 13

---

### Story 4.1: Crear cron job nova_daily_analysis
**Tipo**: Story
**Prioridad**: High
**Story Points**: 3
**Descripcion**:
Background loop que corre cada 12 horas:
1. Para cada tenant activo, recopilar:
   - Conversaciones ultimas 24h (chat_messages, truncar a 80 chars, max 100 msgs)
   - Stats operativos: turnos creados, completados, cancelados (con razones), no-shows, derivaciones, nuevos pacientes, facturacion
2. Compactar datos en prompt
3. Enviar a GPT-4o-mini con response_format json_object
4. Guardar resultado en Redis (key: nova_daily:{tenant_id}, TTL 48h)

**Acceptance Criteria**:
- [ ] Cron arranca al iniciar orchestrator (log: nova_daily_analysis_started)
- [ ] Redis tiene nova_daily:{tenant_id} despues de ejecucion
- [ ] Datos compactados no exceden ~2000 tokens input
- [ ] Costo por ejecucion ~$0.003

**Subtasks**:
- [ ] Crear `orchestrator_service/services/nova_daily_analysis.py`
- [ ] Implementar recopilacion de conversaciones (SQL + compactar)
- [ ] Implementar recopilacion de stats operativos (SQL)
- [ ] Implementar llamada a GPT-4o-mini con prompt de analisis
- [ ] Implementar cache en Redis (TTL 48h)
- [ ] Registrar cron en main.py (lifespan)

---

### Story 4.2: Crear endpoint GET /admin/nova/daily-analysis
**Tipo**: Story
**Prioridad**: Medium
**Story Points**: 2
**Descripcion**:
Lee el analisis diario de Redis y lo retorna al frontend.
- Si no hay datos: `{"available": false}`
- Si hay datos: `{"available": true, "analysis": {...}}`
- Analysis incluye: temas_frecuentes, problemas, temas_sin_cobertura, sugerencias, cancelacion_insights, satisfaccion_estimada, resumen, operational_stats, analyzed_at

**Acceptance Criteria**:
- [ ] Retorna available=false si no hay datos
- [ ] Retorna analysis completo si hay datos en Redis
- [ ] Filtrado por tenant_id

**Subtasks**:
- [ ] Implementar endpoint en nova_routes.py
- [ ] Leer de Redis y parsear JSON
- [ ] Manejar caso sin datos

---

### Story 4.3: Crear endpoint POST /admin/nova/apply-suggestion
**Tipo**: Story
**Prioridad**: Medium
**Story Points**: 2
**Descripcion**:
Permite aplicar sugerencias del daily analysis directamente:
- type="faq": busca FAQ existente por question (ILIKE), si existe actualiza, si no crea nueva
- type="prompt_rule": reservado para futuro (agregar reglas al system prompt)
- Requiere autenticacion

**Acceptance Criteria**:
- [ ] Crear FAQ nueva funciona
- [ ] Actualizar FAQ existente funciona (ILIKE match)
- [ ] Retorna status ok con accion realizada

**Subtasks**:
- [ ] Implementar endpoint en nova_routes.py
- [ ] Logica UPSERT para FAQs
- [ ] Tests unitarios

---

### Story 4.4: Disenar prompt de analisis para GPT-4o-mini
**Tipo**: Story
**Prioridad**: High
**Story Points**: 3
**Descripcion**:
Prompt que analiza actividad dental y retorna JSON estructurado:
- Input: conversaciones compactadas + datos operativos
- Output JSON: temas_frecuentes[], problemas[], temas_sin_cobertura[], sugerencias[], cancelacion_insights[], satisfaccion_estimada (1-10), resumen
- Sugerencias deben ser accionables: "Crear FAQ: pregunta → respuesta"
- Temperature: 0, max_tokens: 700
- No incluir datos de pacientes individuales (privacy)

**Acceptance Criteria**:
- [ ] Output es JSON valido
- [ ] Sugerencias son accionables (se pueden aplicar como FAQ)
- [ ] No incluye nombres de pacientes
- [ ] Tokens input ~1800, output ~500

**Subtasks**:
- [ ] Disenar y testear prompt
- [ ] Validar output JSON schema
- [ ] Verificar que no filtra datos de pacientes

---

### Story 4.5: Analisis consolidado cross-sede (CEO)
**Tipo**: Story
**Prioridad**: Medium
**Story Points**: 3
**Descripcion**:
El cron genera ademas un analisis consolidado comparando todas las sedes:
- Prompt GPT-4o-mini con stats de todas las sedes
- Genera: ranking de sedes, mejor/peor sede, comparativas, tendencia global, resumen CEO
- Cache en Redis key nova_daily:consolidated (TTL 48h)
- Endpoint GET /admin/nova/daily-analysis?consolidated=true

**Acceptance Criteria**:
- [ ] Ranking de sedes correcto
- [ ] Comparativas relevantes
- [ ] Redis tiene nova_daily:consolidated
- [ ] Endpoint retorna analisis consolidado

**Subtasks**:
- [ ] Implementar _analyze_consolidated()
- [ ] Disenar prompt de comparacion cross-sede
- [ ] Cache en Redis
- [ ] Actualizar endpoint con query param consolidated

---

## RESUMEN DE ESTIMACION

| Epic | Stories | Story Points | Prioridad |
|------|---------|-------------|-----------|
| **E0: Onboarding** | 4 | 13 | Highest |
| **E1: Backend** | 9 (+2) | 42 (+8) | Highest |
| **E2: Frontend** | 9 (+1) | 29 (+3) | Highest |
| **E3: Health Check** | 3 | 8 | High |
| **E4: Daily Analysis** | 5 (+1) | 13 (+3) | Medium |
| **TOTAL** | **30** | **105** | |

### Orden de ejecucion sugerido (dependencias)

```
Sprint 1: E0 (Stories 0.1-0.2) + E1 (Stories 1.1-1.4) → Onboarding backend + Nova core
Sprint 2: E0 (Stories 0.3-0.4) + E1 (Stories 1.5-1.7) → Onboarding UI + Tools
Sprint 3: E1 (Stories 1.8-1.9) + E3 (Stories 3.1-3.3) → Multi-sede tools + Health
Sprint 4: E2 (Stories 2.1-2.5) → Widget UI + Voice
Sprint 5: E2 (Stories 2.6-2.9) → Toast + Action routing + Sede selector
Sprint 6: E4 (Stories 4.1-4.5) → Daily analysis + Cross-sede insights
```

### Dependencias entre stories

- 1.4 (WS handler) depende de 1.3 (session)
- 1.5, 1.6, 1.7 (tools) dependen de 1.4 (WS handler)
- 2.1-2.4 (widget UI) dependen de 1.1, 1.2 (endpoints context/health)
- 2.5 (voice) depende de 1.4 (WS handler)
- 2.6 (toast) depende de 1.2 (health-check)
- 4.1 (cron) es independiente
- 4.2, 4.3 (endpoints) dependen de 4.1
- 4.4 (prompt) va en paralelo con 4.1
- 0.1 (onboarding status) blocks 0.3 (frontend card) and 0.4 (tool)
- 0.2 (complete step) blocks 0.3 (frontend interaction)
- 1.8 (multi-sede tools) depends on 1.4 (WS handler)
- 1.9 (multi-sede endpoints) blocks 2.9 (sede selector)
- 4.5 (consolidated analysis) depends on 4.1 (cron)

### Labels sugeridos

- `nova` — todo lo de Nova
- `backend` / `frontend` — por capa
- `fase-0` / `fase-1` / `fase-2` / `fase-3` / `fase-4` — por fase
- `voice` — todo lo de voz
- `health` — health checks
- `tools` — function calling tools
- `ia` — componentes que usan IA (GPT)
- `onboarding` — onboarding flow
- `multi-sede` — cross-tenant CEO features
