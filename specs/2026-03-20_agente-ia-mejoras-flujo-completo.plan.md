# Plan de Implementación — Mejoras Integrales del Agente de IA
> Spec: `2026-03-20_agente-ia-mejoras-flujo-completo.spec.md`
> Fecha: 2026-03-20

## Estrategia de ejecución

Se implementa en **5 fases**, cada una desplegable y testeable de forma independiente. Cada fase se commitea por separado.

---

## FASE 1: Base de datos + Modelos (prerequisito de todo lo demás)

### Paso 1.1 — Migración Alembic: consultation_price en tenants + anamnesis_token en patients
- **Archivo:** `orchestrator_service/alembic/versions/xxxx_add_consultation_price_anamnesis_token.py`
- **Cambios:**
  - `ALTER TABLE tenants ADD COLUMN consultation_price DECIMAL(12,2) DEFAULT NULL`
  - `ALTER TABLE patients ADD COLUMN anamnesis_token UUID DEFAULT NULL`
  - `CREATE UNIQUE INDEX idx_patients_anamnesis_token ON patients(anamnesis_token) WHERE anamnesis_token IS NOT NULL`
- **Downgrade:** DROP COLUMN ambos
- **Verificación:** `alembic upgrade head` sin errores

### Paso 1.2 — Actualizar models.py
- **Archivo:** `orchestrator_service/models.py`
- **Cambios:**
  - Tenant: agregar `consultation_price = Column(DECIMAL(12,2), nullable=True)`
  - Patient: agregar `anamnesis_token = Column(UUID(as_uuid=True), nullable=True, unique=True)`

### Paso 1.3 — Variable de entorno FRONTEND_URL
- **Archivo:** `.env.production.example`
- **Cambio:** Agregar `FRONTEND_URL=https://app.dralauradelgado.com`
- En el código se lee con `os.getenv("FRONTEND_URL", "http://localhost:4173")`

**Commit:** `feat: add consultation_price, anamnesis_token, FRONTEND_URL`

---

## FASE 2: Working Hours extendido + UI de configuración de sedes

### Paso 2.1 — Backend: Extender PUT /admin/tenants para soportar working_hours con location por día
- **Archivo:** `orchestrator_service/admin_routes.py`
- **Cambio:** El endpoint `PUT /admin/tenants/{tenant_id}` ya acepta `working_hours` JSONB. Validar que la estructura acepte los nuevos campos (`location`, `address`, `maps_url` por día). Agregar `consultation_price` al update.
- **Verificación:** PUT con working_hours que incluya location → devuelve OK → SELECT confirma persistencia

### Paso 2.2 — Backend: Extender GET /admin/tenants para devolver consultation_price
- **Archivo:** `orchestrator_service/admin_routes.py`
- **Cambio:** Agregar `consultation_price` al SELECT del GET /admin/tenants y GET/PUT individual

### Paso 2.3 — Frontend: UI de configuración de sede con working_hours extendido
- **Archivo:** `frontend_react/src/views/` o `components/` (componente de config de sede)
- **Cambio:** En la UI de edición de sede/clínica, agregar por cada día:
  - Campos existentes: enabled, slots (start/end)
  - Campos nuevos: location (nombre sede), address (dirección), maps_url (link Google Maps)
  - Campo nuevo global: consultation_price (valor de la consulta)
- **Verificación:** Editar sede → guardar → recargar → valores persisten

### Paso 2.4 — Frontend: UI de configuración de profesional con working_hours extendido
- **Archivo:** `frontend_react/src/` (componente de edición de profesional)
- **Cambio:** Mismo patrón que sede: por cada día, campos opcionales de location/address/maps_url
- Si están vacíos → heredan del tenant (indicar visualmente "Hereda de sede")

**Commit:** `feat: multi-sede working_hours with location per day + consultation_price UI`

---

## FASE 3: Contexto del paciente + System Prompt completo

### Paso 3.1 — buffer_task.py: Extender patient_context
- **Archivo:** `orchestrator_service/services/buffer_task.py`
- **Cambios en la sección de patient_context (líneas 100-171):**
  - Agregar query para detectar si es lead nuevo (no existe en patients)
  - Agregar query para detectar turnos pasados vs futuros
  - Agregar check de anamnesis_completed (medical_history tiene datos)
  - Resolver sede del día actual desde tenant.working_hours
  - Leer `consultation_price` del tenant
  - Pasar todo al system prompt como parámetros nuevos

### Paso 3.2 — build_system_prompt: Reescribir greeting + triage + objeciones + conversión + sede + anamnesis
- **Archivo:** `orchestrator_service/main.py` (función `build_system_prompt`)
- **Nuevos parámetros:**
  - `patient_status: str` — "new_lead" | "patient_no_appointment" | "patient_with_appointment"
  - `consultation_price: float | None`
  - `sede_info: dict | None` — {location, address, maps_url} del día actual
- **Cambios en el prompt:**

  **A) GREETING (reemplazar sección IDENTIDAD Y TONO):**
  ```
  MENSAJE INICIAL OBLIGATORIO (primera interacción):
  "Hola 😊
  Soy la asistente virtual del {clinic_name}.
  La Dra. se especializa en rehabilitación oral con implantes, prótesis y cirugía guiada."

  + SI patient_status == "new_lead": "¿En qué tipo de consulta estás interesado?"
  + SI patient_status == "patient_no_appointment": "¿En qué podemos ayudarte hoy?"
  + SI patient_status == "patient_with_appointment": Comentario sobre turno próximo + sede + hora
  ```

  **B) TRIAGE DE IMPLANTES (nueva sección):**
  ```
  Si el paciente menciona implantes, prótesis, o relacionados → ENVIAR opciones con emojis:
  🦷 Perdí un diente
  🦷🦷 Perdí varios dientes
  🔄 Uso prótesis removible
  🔧 Necesito cambiar una prótesis
  😣 Tengo una prótesis que se mueve
  🤔 No estoy seguro

  Luego profundizar: "¿Hace cuánto tiempo tenés este problema?"
  Luego posicionamiento: mensaje sobre Dra. Laura Delgado + especialidades
  ```

  **C) MANEJO DE OBJECIONES (nueva sección):**
  - Precio: guión con consultation_price dinámico
  - Miedo: guión empático con tecnología moderna

  **D) CONVERSIÓN (nueva sección):**
  - "¿Querés que coordinemos una consulta de evaluación con la Dra. Laura Delgado?"
  - Opciones NO visibles

  **E) MULTI-SEDE (nueva sección):**
  - Info de sedes disponibles inyectada desde working_hours
  - Regla: la sede se determina por el día, no por elección del paciente

  **F) CONFIRMACIÓN (modificar PASO 7):**
  - Incluir sede (nombre + dirección + maps) en confirmación
  - Agregar link de anamnesis

  **G) ANAMNESIS (eliminar PASOS 8-9, agregar nuevo paso):**
  - Eliminar PASO 8 (cuestionario) y PASO 9 (guardar anamnesis)
  - Nuevo paso: enviar link de formulario público
  - "Para ahorrar tiempo en tu consulta podés completar tu ficha médica aquí: {link}"
  - "Cuando termines avisame para corroborar los datos"

### Paso 3.3 — main.py: Modificar check_availability para devolver sede del día
- **Archivo:** `orchestrator_service/main.py`
- **Cambio:** Al devolver disponibilidad, incluir nombre de sede + dirección del día consultado
- **Resolución:** tenant.working_hours[day].location → fallback tenant.address

### Paso 3.4 — main.py: Modificar book_appointment para sede + anamnesis_token
- **Archivo:** `orchestrator_service/main.py`
- **Cambios:**
  - Generar `anamnesis_token` UUID al confirmar turno (si el paciente no tiene uno)
  - Guardar token en patients
  - Resolver sede del día del turno
  - Incluir en confirmación: sede + dirección + maps + link anamnesis
  - Formato: `{FRONTEND_URL}/anamnesis/{tenant_id}/{token}`

### Paso 3.5 — main.py: Nueva tool get_patient_anamnesis
- **Archivo:** `orchestrator_service/main.py`
- **Cambio:** Tool que lee medical_history del paciente actual (por phone + tenant_id)
- **Uso:** Cuando el paciente dice "ya completé el formulario", el agente llama esta tool para verificar y confirmar los datos

**Commit:** `feat: differentiated greeting, implant triage, objection handling, multi-sede, anamnesis link`

---

## FASE 4: Página pública de anamnesis

### Paso 4.1 — Backend: Endpoints públicos de anamnesis
- **Archivo:** `orchestrator_service/admin_routes.py` (o nuevo archivo `public_routes.py`)
- **Endpoints:**
  - `GET /public/anamnesis/{tenant_id}/{token}` — Sin auth. Devuelve nombre del paciente + nombre clínica + datos de anamnesis existentes (si hay)
  - `POST /public/anamnesis/{tenant_id}/{token}` — Sin auth. Guarda medical_history JSONB. Emite Socket.IO `PATIENT_UPDATED`
- **Validación:** token debe existir en patients con ese tenant_id
- **Rate limit:** Considerar límite básico para evitar abuso

### Paso 4.2 — BFF: Proxy para ruta pública
- **Archivo:** `bff_service/index.js`
- **Cambio:** Agregar proxy para `/public/*` → orchestrator (sin auth headers)

### Paso 4.3 — Frontend: AnamnesisPublicView.tsx
- **Archivo:** `frontend_react/src/views/AnamnesisPublicView.tsx` (NUEVO)
- **Diseño:**
  - Mobile-first, sin sidebar, sin header de la app
  - Logo de la clínica arriba + "Ficha médica — {clinic_name}"
  - Secciones con checkboxes/radio buttons:
    - Enfermedades de base (checklist: diabetes, hipertensión, cardiopatía, problemas de coagulación, hepatitis, HIV, osteoporosis, tiroides, epilepsia, asma, otro + campo libre)
    - Medicación habitual (texto libre)
    - Alergias (checklist: penicilina, amoxicilina, latex, anestesia local, AINES/ibuprofeno, aspirina, otro + campo libre)
    - Cirugías previas (texto libre)
    - Fumador (sí/no + cantidad)
    - Embarazo/Lactancia (sí/no/no aplica)
    - Experiencias negativas en odontología (texto libre)
    - Miedos dentales (checklist: agujas, dolor, ruido del torno, asfixia/ahogo, sangre, anestesia, otro + campo libre)
  - Botón "Enviar ficha médica"
  - Pantalla de éxito: "Gracias! Tu ficha fue guardada. Podés avisarle al asistente por WhatsApp."
- **Validación:** Si token inválido → pantalla de error amigable
- **i18n:** Solo español por ahora (es formulario para pacientes argentinos)

### Paso 4.4 — Frontend: Ruta en App.tsx
- **Archivo:** `frontend_react/src/App.tsx`
- **Cambio:** Agregar ruta pública fuera del layout autenticado:
  ```tsx
  <Route path="/anamnesis/:tenantId/:token" element={<AnamnesisPublicView />} />
  ```
- NO agregar al sidebar/navegación

**Commit:** `feat: public anamnesis form page (mobile-optimized checklist)`

---

## FASE 5: Testing + deploy

### Paso 5.1 — Test end-to-end del flujo
- Enviar "Hola" desde número no registrado → verificar greeting de lead
- Enviar "Hola" desde número registrado con turno → verificar greeting con turno + sede
- Enviar "quiero implantes" → verificar triage con emojis
- Preguntar precio → verificar respuesta con consultation_price
- Agendar turno Miércoles → verificar sede Córdoba en confirmación
- Agendar turno Martes → verificar sede Salta en confirmación
- Verificar link de anamnesis en confirmación
- Abrir link → completar formulario → verificar datos guardados
- Decirle al agente "ya completé" → verificar que lee los datos

### Paso 5.2 — Commit final + push
- Push de todas las fases a main
- Deploy en EasyPanel

---

## Orden de dependencias

```
FASE 1 (DB) ──→ FASE 2 (Working Hours UI) ──→ FASE 3 (System Prompt + Tools)
                                                        ↓
                                              FASE 4 (Página Anamnesis)
                                                        ↓
                                              FASE 5 (Test + Deploy)
```

FASE 1 es prerequisito de todo. FASE 2 y 3 pueden avanzar en paralelo parcialmente. FASE 4 depende de FASE 1 (anamnesis_token) y FASE 3 (tool de generación de link). FASE 5 es final.
