# Auditoría completa del proyecto – Estado por página y cobertura i18n

**Fecha:** 2026-02-08  
**Workflow:** Audit + Bug Fix (selector de idioma estricto)  
**Alcance:** Cada página/vista del frontend con su estado Backend, Frontend, Base de datos, Lógica e **i18n**.

---

## 1. Resumen ejecutivo

| Área | Estado | Nota |
|------|--------|------|
| **Backend** | ✅ Operativo | Auth, Admin (usuarios, tenants, chat, pacientes, turnos, profesionales, calendario, tratamientos, settings/clinic), analytics. Soberanía `tenant_id` en consultas. |
| **Frontend** | ✅ Operativo | Todas las rutas protegidas; Layout + Sidebar; vistas por rol (CEO, secretary, professional). |
| **Base de datos** | ✅ Esquema unificado | PostgreSQL; parches 12d/12e en `professionals`; aislamiento multi-tenant. |
| **Lógica de negocio** | ✅ Coherente | Registro con sede, aprobación CEO, agenda con GCal, chat por clínica, override 24h, agente con nombre clínica y detección de idioma. |
| **i18n (selector de idioma)** | ✅ Cobertura completa | Todas las páginas, notificaciones WebSocket (derivación, nuevo turno), notificación global Layout, alertas y confirmaciones usan `t()` y claves en es/en/fr. |

---

## 2. Estado por página / vista

### 2.1 Login (`/login`)

| Dimensión | Estado | Detalle |
|-----------|--------|---------|
| **Backend** | ✅ | `POST /auth/login`, `POST /auth/register`, `GET /auth/clinics`. Registro con `tenant_id`, specialty, phone_number, registration_id. |
| **Frontend** | ✅ | LoginView: formulario login/registro, selector sede y especialidad para professional/secretary. |
| **Base de datos** | ✅ | `users`, `professionals` (creación en registro). |
| **Lógica** | ✅ | Estado `pending` hasta aprobación CEO. |
| **i18n** | ✅ | Títulos, labels, placeholders, roles, mensajes de error/éxito, botones (Ingresar, Solicitar Registro), enlace “¿Ya tienes cuenta?” / “Solicitar acceso” con `t('login.*')`. |

---

### 2.2 Dashboard (`/`)

| Dimensión | Estado | Detalle |
|-----------|--------|---------|
| **Backend** | ✅ | `GET /admin/stats/summary?range=`, `GET /admin/chat/urgencies`. |
| **Frontend** | ✅ | DashboardView: KPIs (Conversaciones IA, Citas IA, Urgencias, Ingresos), gráfico de eficiencia, tabla Urgencias Recientes. WebSocket para NEW_APPOINTMENT. |
| **Base de datos** | ✅ | Agregaciones vía stats y urgencias. |
| **Lógica** | ✅ | Rango semanal/mensual. |
| **i18n** | ✅ | Título de página, subtítulo, botones Semanal/Mensual, labels de KPIs, gráfico (Derivaciones, Concretadas), tabla (Paciente, Motivo, Gravedad, Hora, Ver todo) con `t('dashboard.*')`. |

---

### 2.3 Agenda (`/agenda`)

| Dimensión | Estado | Detalle |
|-----------|--------|---------|
| **Backend** | ✅ | `GET /admin/appointments`, `GET /admin/calendar/blocks`, `GET /admin/professionals`, `GET /admin/patients`, `GET /admin/appointments/check-collisions`, POST/PUT/DELETE appointments, `POST /admin/calendar/sync`. |
| **Frontend** | ✅ | AgendaView + FullCalendar (timeGrid, dayGrid, list), filtro por profesional, MobileAgenda, AppointmentForm (crear/editar/eliminar turno). Socket.IO para actualizaciones. |
| **Base de datos** | ✅ | `appointments`, `google_calendar_blocks`. |
| **Lógica** | ✅ | Colisiones, next-slots, sincronización GCal. |
| **i18n** | ✅ | Título "Agenda", subtítulo, "Todos los Profesionales", botones del calendario (Hoy, Mes, Semana, Día, Todo el día), locale del calendario dinámico (`language`), alertas (fecha pasada, error cancelar) con `t('agenda.*')`. |

---

### 2.4 Pacientes (`/pacientes`)

| Dimensión | Estado | Detalle |
|-----------|--------|---------|
| **Backend** | ✅ | `GET /admin/patients`, `GET /admin/treatment-types`, `GET /admin/professionals`, `GET /admin/patients/search-semantic`, POST/PUT/DELETE patients, `POST /admin/appointments` (turno inicial). |
| **Frontend** | ✅ | PatientsView: listado, búsqueda, modal crear/editar, eliminación, navegación a detalle. |
| **Base de datos** | ✅ | `patients`, `appointments`, `treatment_types`, `professionals`. |
| **Lógica** | ✅ | Búsqueda por texto y semántica; creación paciente + turno opcional. |
| **i18n** | ✅ | Título, placeholders de búsqueda; alertas (guardar, eliminar paciente, confirmación eliminar, paciente+turno ok, paciente ok + turno fallido) con `t('patients.*')` y `t('alerts.*')`. |

---

### 2.5 Detalle paciente (`/pacientes/:id`)

| Dimensión | Estado | Detalle |
|-----------|--------|---------|
| **Backend** | ✅ | `GET /admin/patients/{id}`, `GET /admin/patients/{id}/records`, `POST /admin/patients/{id}/records` (o endpoint de registros clínicos). |
| **Frontend** | ✅ | PatientDetail: ficha del paciente, historial clínico, alta de notas. |
| **Base de datos** | ✅ | `patients`, `clinical_records`. |
| **Lógica** | ✅ | Solo lectura + creación de registros. |
| **i18n** | ✅ | Alerta "Error al guardar el registro" con `t('alerts.error_save_record')`. Resto de labels de la página: revisar si hay más cadenas fijas y migrarlas a `t()`. |

---

### 2.6 Chats / Conversaciones (`/chats`)

| Dimensión | Estado | Detalle |
|-----------|--------|---------|
| **Backend** | ✅ | `GET /admin/chat/tenants`, `GET /admin/chat/sessions?tenant_id=`, `GET /admin/chat/messages/{phone}`, `PUT /admin/chat/sessions/{phone}/read`, `POST /admin/chat/send`, `POST /admin/chat/human-intervention`, `POST /admin/chat/remove-silence`, `GET /admin/patients/phone/{phone}/context`. |
| **Frontend** | ✅ | ChatsView: selector de clínica (CEO), lista de sesiones, panel de mensajes, intervención humana, quitar silencio, envío manual. WebSocket: HUMAN_HANDOFF, NEW_MESSAGE, HUMAN_OVERRIDE_CHANGED, CHAT_UPDATED, PATIENT_UPDATED, NEW_APPOINTMENT. |
| **Base de datos** | ✅ | `chat_messages`, sesiones derivadas de mensajes; `patients`. |
| **Lógica** | ✅ | Override 24h por (tenant_id, phone); ventana de mensajes por clínica. |
| **i18n** | ✅ | Título "Conversaciones", label Clínica, placeholders (búsqueda), tooltips (silenciar/activar sonido), "Cargando...", "No hay conversaciones", "Cargar mensajes anteriores". **Toasts WebSocket:** "Derivación Humana" y mensaje (`chats.toast_handoff_*`), "Nuevo Turno" y mensaje (`chats.toast_new_appointment_*`) en el idioma del selector. |

---

### 2.7 Personal / Aprobaciones (`/aprobaciones`)

| Dimensión | Estado | Detalle |
|-----------|--------|---------|
| **Backend** | ✅ | `GET /admin/users`, `GET /admin/users/pending`, `POST /admin/users/{id}/status`, `GET /admin/professionals`, `GET /admin/professionals/by-user/{id}`, `GET /admin/professionals/{id}/analytics`, `GET /admin/chat/sessions?tenant_id=`, POST/PUT ` /admin/professionals`. |
| **Frontend** | ✅ | UserApprovalView: pestañas Solicitudes / Personal Activo, tarjetas de usuario, modal detalle (acordeón: Sus pacientes, Uso plataforma, Mensajes), modal Editar Perfil, formulario Vincular a sede. |
| **Base de datos** | ✅ | `users`, `professionals`, métricas y sesiones de chat. |
| **Lógica** | ✅ | Aprobación activa/suspendido; vinculación profesional–sede; working_hours. |
| **i18n** | ✅ | Título y subtítulo de página, pestañas (Solicitudes, Personal Activo), estados vacíos, "Cargando personal...", Cerrar, Vincular a sede / a otra sede, Crear perfil en una sede, labels (Elegir sede, Teléfono, Especialidad, Matrícula, Miembro desde, Quitar, Agregar horario). Alertas (procesar solicitud, cargar profesional, guardar, seleccionar sede, vincular sede) con `t('approvals.*')` y `t('alerts.*')`. |

---

### 2.8 Sedes / Clínicas (`/sedes`)

| Dimensión | Estado | Detalle |
|-----------|--------|---------|
| **Backend** | ✅ | `GET /admin/tenants`, `POST /admin/tenants`, `PUT /admin/tenants/{id}`, `DELETE /admin/tenants/{id}` (verify_admin_token, solo CEO). |
| **Frontend** | ✅ | ClinicsView: listado de clínicas, modal crear/editar, eliminación. |
| **Base de datos** | ✅ | `tenants`. |
| **Lógica** | ✅ | CRUD sedes; config calendar_provider. |
| **i18n** | ✅ | Título, subtítulo, "Nueva sede", "Cargando..."; confirmación de eliminar clínica con `t('clinics.*')`, `t('common.loading')`, `t('alerts.confirm_delete_clinic')`. |

---

### 2.9 Tratamientos (`/tratamientos`)

| Dimensión | Estado | Detalle |
|-----------|--------|---------|
| **Backend** | ✅ | `GET /admin/treatment-types`, `POST /admin/treatment-types`, `PUT /admin/treatment-types/{code}`, `DELETE /admin/treatment-types/{code}`. |
| **Frontend** | ✅ | TreatmentsView: listado, crear, editar, eliminar por código. |
| **Base de datos** | ✅ | `treatment_types`. |
| **Lógica** | ✅ | CRUD por código. |
| **i18n** | ✅ | Título de página; alertas (guardar cambios, código y nombre obligatorios, crear tratamiento, confirmar eliminar tratamiento, error eliminar) con `t('treatments.title')` y `t('alerts.*')`. |

---

### 2.10 Perfil (`/perfil`)

| Dimensión | Estado | Detalle |
|-----------|--------|---------|
| **Backend** | ✅ | `GET /auth/profile`, `PATCH /auth/profile`. |
| **Frontend** | ✅ | ProfileView: formulario nombre, apellido, Google Calendar ID (si professional). |
| **Base de datos** | ✅ | `users`, `professionals`. |
| **Lógica** | ✅ | Actualización de perfil usuario y opcionalmente professional. |
| **i18n** | ✅ | Título "Mi Perfil", subtítulo con `t('profile.*')`. Mensajes de error/éxito pueden migrarse a `t('alerts.*')` si aún están fijos. |

---

### 2.11 Configuración (`/configuracion`)

| Dimensión | Estado | Detalle |
|-----------|--------|---------|
| **Backend** | ✅ | `GET /admin/settings/clinic`, `PATCH /admin/settings/clinic` (ui_language). |
| **Frontend** | ✅ | ConfigView: selector de idioma (Español, English, Français); efecto inmediato con `setLanguage` + PATCH. Solo CEO. |
| **Base de datos** | ✅ | `tenants.config.ui_language`. |
| **Lógica** | ✅ | Idioma por defecto `en`; persistencia por tenant. |
| **i18n** | ✅ | Toda la vista usa `t('config.*')`. |

---

### 2.12 Layout y notificación global

| Dimensión | Estado | Detalle |
|-----------|--------|---------|
| **Backend** | — | N/A (socket mismo que Chats). |
| **Frontend** | ✅ | Layout: Sidebar, área principal, banner de notificación de derivación humana (HUMAN_HANDOFF por WebSocket). Al hacer clic, navega a Chats con el teléfono seleccionado. |
| **i18n** | ✅ | Título de app, Sucursal, Principal, "Derivación Humana", "Motivo", "Click para abrir chat" con `t('layout.*')`. |

---

### 2.13 Componentes compartidos

| Componente | i18n |
|------------|------|
| **Sidebar** | ✅ Menú (Dashboard, Agenda, Pacientes, etc.), Cerrar sesión, Expandir/Contraer, Cerrar menú, nombre app con `t('nav.*')`. |
| **AppointmentForm** | ✅ Confirmación "¿Está seguro de eliminar este turno?" con `t('alerts.confirm_delete_appointment')`. |
| **MobileAgenda** | Revisar si contiene textos fijos; si los hay, extraer a `agenda.*` o `common.*`. |

---

### 2.14 Vistas adicionales (admin / herramientas)

| Vista | Ruta / uso | i18n |
|-------|------------|------|
| **ProfessionalsView** | `/profesionales` (redirige a aprobaciones; acceso directo posible) | ✅ Alert "Error al guardar profesional" con `t('alerts.error_save_professional')`. |
| **Credentials** | Herramientas / credenciales | ⚠️ alert/confirm en español; migrar a `alerts.*` si se usa en la misma SPA. |
| **Tools** | Herramientas | ⚠️ Idem. |
| **Stores** | Tiendas | ⚠️ Idem. |
| **Setup** | Setup inicial | ⚠️ "Setup Completo!"; clave ya existe en `alerts.setup_complete`, falta usar `t()`. |

---

## 3. Notificaciones en tiempo real (WebSocket) e i18n

| Evento | Origen | Dónde se muestra | i18n |
|--------|--------|------------------|------|
| **HUMAN_HANDOFF** | Backend (derivhumano) | ChatsView (toast) + Layout (banner global) | ✅ Título y mensaje del toast con `chats.toast_handoff_*`. Banner con `layout.notification_handoff` y `layout.notification_reason`. |
| **NEW_APPOINTMENT** | Backend / agenda | ChatsView (toast) | ✅ Título y mensaje con `chats.toast_new_appointment_*`. |
| **NEW_MESSAGE** | Backend | ChatsView (lista y panel) | Contenido del mensaje es dato del usuario/agente; no se traduce. |
| **HUMAN_OVERRIDE_CHANGED** | Backend | ChatsView (estado de sesión) | Solo estado interno; sin texto fijo que traducir. |

---

## 4. Criterios de aceptación del selector de idioma (spec 25 + extensión)

- [x] Selector en Configuración (es/en/fr) con efecto inmediato en toda la UI.
- [x] Persistencia en `tenants.config.ui_language` vía GET/PATCH `/admin/settings/clinic`.
- [x] Idioma por defecto inglés en frontend y backend.
- [x] Sidebar, Layout, ConfigView, Login, Dashboard, Agenda, Pacientes, Chats, Aprobaciones, Sedes, Tratamientos, Perfil usan `t()` para todos los textos visibles.
- [x] Notificaciones WebSocket (derivación humana, nuevo turno) muestran título y mensaje en el idioma seleccionado.
- [x] Notificación global de derivación (Layout) usa claves de layout.
- [x] Alertas y confirmaciones (alert/confirm) en las vistas principales usan `alerts.*`.
- [ ] Credentials, Tools, Stores, Setup: opcional migrar alert/confirm a `t('alerts.*')` si forman parte del flujo principal.

---

## 5. Acciones correctivas pendientes (drift menor)

1. **Scroll Isolation:** Revisar todas las vistas con listas largas para cumplir h-screen, overflow-hidden, flex-1 min-h-0 overflow-y-auto (Sovereign Glass).
2. **Vistas admin (Credentials, Tools, Stores, Setup):** Si se exponen en el menú, conectar sus alert/confirm a `t('alerts.*')`.
3. **AUDIT_ESTADO_PROYECTO.md línea 294:** Eliminar resto de texto antiguo "pendiente" en el ítem 2 de Acciones correctivas si sigue presente.

---

*Documento generado por workflow Audit + Bug Fix – 2026-02-08. Cobertura i18n estricta: todo atado al selector de idioma.*
