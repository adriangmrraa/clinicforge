# Informe de Auditoría – Selector de idioma (i18n)

**Criterio:** Todo el UI (modales, tablas, botones, etiquetas, mensajes de estado, toasts) debe respetar el idioma seleccionado. **Excepción:** el contenido de los mensajes de chat se muestra en el idioma en que llegaron (sin traducir).

---

## Match (ya cumple)

- **Navegación (Sidebar, Layout):** títulos y menús usan `t()`.
- **Configuración (Settings):** selector de idioma y textos de la página usan `t()`.
- **Login / Registro:** claves en `login.*` utilizadas.
- **Tratamientos (TreatmentsView):** en su mayoría traducido (subtítulo, botones, duraciones recomendadas, categorías, formulario de edición, tarjetas de servicio).
- **Perfil (ProfileView):** registrado en, nombre, apellido, guardar cambios.
- **Clinics (ClinicsView):** modal y listado usan `t()` (crear/editar clínica, proveedor de calendario, desde).
- **Pacientes (PatientsView):** subtítulo, botón nuevo paciente, búsqueda, modal nuevo/editar, tabla (DNI/Obra Social, Salud, Fecha Alta, Acciones), labels del formulario.
- **Conversaciones (ChatsView):** panel de contexto clínico (Contexto Clínico, Estado del Bot, IA activa, PACIENTE, CONTACTO / SIN TURNOS, etc.) ya usa `t()`. El contenido de los mensajes de chat **no** se traduce (correcto).

---

## Drift (no respeta el selector de idioma)

### 1. TreatmentsView.tsx
| Ubicación | Texto actual | Acción |
|-----------|--------------|--------|
| Label formulario creación | "Nombre" | Usar `t('treatments.name')` |
| Placeholder código | "ej: limpieza_profunda" | Añadir `treatments.placeholder_code` y usar `t()` |
| title botones | "Editar", "Eliminar" | Usar `t('common.edit')`, `t('common.delete')` |
| Empty state | "No hay tratamientos definidos" | Añadir `treatments.no_treatments_defined` |
| Empty state | "Comienza configurando tu primer servicio..." | Añadir `treatments.empty_hint` |
| Botón empty | "Configurar Primer Servicio" | Añadir `treatments.setup_first_service` |

### 2. ProfileView.tsx
| Ubicación | Texto actual | Acción |
|-----------|--------------|--------|
| Placeholders | "Tu nombre", "Tu apellido" | Añadir `profile.placeholder_first_name`, `placeholder_last_name` |
| Párrafo Google Calendar | "Importante: Para que el asistente IA..." | Añadir `profile.calendar_help` |
| Label | "Google Calendar ID" | Añadir `profile.calendar_id_label` |
| Placeholder | "ejemplo@gmail.com o xxxx@group..." | Añadir `profile.calendar_id_placeholder` |

### 3. ChatsView.tsx (solo UI, no mensajes)
| Ubicación | Texto actual | Acción |
|-----------|--------------|--------|
| Toast error | "Error de Conexión", "No se pudieron cargar las conversaciones..." | Usar claves `chats.error_connection_title`, `chats.error_connection_message` |
| title botón | "Ver ficha clínica" | Añadir `chats.view_clinical_chart` |
| Botones modo | "Activar IA", "Manual" | Añadir `chats.activate_ai`, `chats.manual` |
| Mensaje 24h | "Ventana de 24hs cerrada: No puedes enviar..." | Añadir `chats.window_24h_closed` |
| Badge | "Derivación automática" | Añadir `chats.auto_handoff` |
| Título panel | "Perfil del Paciente" | Añadir `chats.patient_profile_title` |

### 4. PatientsView.tsx
| Ubicación | Texto actual | Acción |
|-----------|--------------|--------|
| Estado carga | "Cargando pacientes..." | Añadir `patients.loading` y usar `t()` |
| title botones | "Ver Ficha", "Editar", "Eliminar" | Usar `patients.view_chart` + `common.edit` / `common.delete` |
| Badges card | "Teléfono", "Obra Social" | Usar `common.phone` o `patients.phone_label`, y `patients.obra_social` (ya existe) |

### 5. UserApprovalView.tsx
| Ubicación | Texto actual | Acción |
|-----------|--------------|--------|
| Días semana | "Miércoles", "Sábado" | Añadir `approvals.day_wednesday`, `approvals.day_saturday` (o `common.days.*`) |
| Especialidades | "Odontología General", "Cirugía Oral", etc. | Añadir `approvals.specialty_*` y mapear |
| setError | "No se pudieron cargar los usuarios..." | Añadir `approvals.error_load_users` |
| Labels/placeholders | Teléfono, Matrícula, Especialidad, Seleccionar... | Usar claves existentes o añadir |
| "Cargando datos de sedes...", "Cargando métricas...", "Sin datos en este período." | Varios | Añadir `approvals.loading_clinics`, `approvals.loading_metrics`, `approvals.no_data_period` |
| Métricas | "Pacientes únicos (mes)", "Turnos totales", "Tasa de finalización", "Retención", "Turnos completados", "Cancelaciones", "Ingresos estimados" | Añadir bloque `approvals.metrics.*` |
| Texto vinculación | "Aún no está vinculado a ninguna sede..." | Añadir `approvals.not_linked_hint` |
| "Completa la información del staff médico." | Subtítulo | Añadir `approvals.complete_staff_info` |
| "Datos Principales", "Contacto & Estado", "Sede / Clínica", "Nombre completo", "Matrícula", "E-mail", "Teléfono", "Activo", "Intervalos para el bot...", "Quitar", "Suspendido", "Editar perfil y horarios" | Formulario y badges | Añadir claves y usar `t()` |

### 6. AppointmentForm.tsx
| Ubicación | Texto actual | Acción |
|-----------|--------------|--------|
| Pestañas placeholder | "Historial Médico disponible próximamente", "Módulo de Facturación disponible próximamente" | Añadir `agenda.medical_history_coming`, `agenda.billing_coming` |

### 7. PatientDetail.tsx
| Ubicación | Texto actual | Acción |
|-----------|--------------|--------|
| Títulos y labels | "Historia Clínica Digital", "Antecedentes Críticos", "Paciente", "Antecedentes Médicos", "Condiciones Críticas:", "Línea de Tiempo Clínica", "No hay registros clínicos aún", "Motivo de consulta", "Diagnóstico", "Plan de tratamiento", "Notas", "Nueva Evolución Clínica", "Consulta Inicial", "Evolución", "Procedimiento", "Receta", "Signos Vitales", "Presión Arterial", "Frecuencia Cardíaca" | Añadir bloque `patient_detail.*` y usar `t()` en toda la vista |
| Placeholders | "Ej: Dolor de muela...", "120/80", "72" | Incluir en `patient_detail.*` |

### 8. ProfessionalsView.tsx
| Ubicación | Texto actual | Acción |
|-----------|--------------|--------|
| Días y especialidades | Igual que UserApprovalView | Reutilizar o duplicar claves |
| "Gestión del staff médico y disponibilidad", "Médicos Activos", "Cargando equipo médico...", "Comienza agregando el primer miembro..." | Subtítulos y estados | Añadir `professionals.*` |
| Modal | "Editar Perfil Médico", "Nuevo Miembro del Equipo", "Seleccionar clínica...", "Vincular este profesional...", "Guardar Cambios", "Firmar Alta Médica" | Añadir claves y usar `t()` |

### 9. Otros componentes/vistas
| Archivo | Texto | Acción |
|---------|--------|--------|
| MobileAgenda.tsx | "No hay turnos para este día" | Añadir `agenda.no_appointments_today` |
| ProtectedRoute.tsx | "Verificando sesión..." | Añadir `common.verifying_session` |
| Dashboard.tsx | "Tasa de Éxito" | Añadir clave en dashboard/agenda |
| ProfessionalAnalyticsView.tsx | "Analytics Estratégico", "Visión de alto nivel...", "Tasa Retención", "Retención" | Añadir `analytics.*` |
| LoginView.tsx | "Teléfono" (label), especialidades | Usar `login.phone`, traducir opciones de especialidad |
| ClinicsView.tsx | setSuccess/setError: "Clínica actualizada correctamente", "Clínica creada correctamente", "Error al guardar la clínica" | Añadir `clinics.toast_updated`, `clinics.toast_created`, `clinics.toast_error` |
| Credentials.tsx, Tools.tsx, Stores.tsx, Setup.tsx | Varios labels y títulos en español | Si son vistas activas del producto, añadir namespaces y traducir |

---

## Resumen

- **Match:** Navegación, Config, Login, Tratamientos (mayoría), Perfil (básico), Clinics, Pacientes (mayoría), Chats (panel contexto). Contenido de mensajes de chat correctamente sin traducir.
- **Drift:** ~60+ cadenas en 12+ archivos que siguen en español/inglés fijo. Prioridad: TreatmentsView (empty + labels), ProfileView (Google Calendar), ChatsView (toasts y botones UI), PatientsView (loading + titles), UserApprovalView (formulario y métricas), AppointmentForm (placeholders pestañas), PatientDetail (toda la vista), ProfessionalsView, MobileAgenda, ProtectedRoute, toasts de ClinicsView.

---

## Acción correctiva sugerida

1. ~~Añadir las claves faltantes~~ **Hecho en última pasada:** `approvals` (días, especialidades, formulario, métricas, not_linked_hint, edit profile, suspended, reactivate), `patient_detail` (completo), `clinics` (toast_updated/created/error), `chats` (handoff_banner, remove_silence, manual_mode_active), `dashboard` (panel_title, last_sync, never, active_tenants, success_rate, etc.).
2. ~~Reemplazar en cada archivo~~ **Hecho:** UserApprovalView, PatientDetail, ClinicsView (toasts), ChatsView (banners), Dashboard.
3. Verificación: cambiar idioma a English y recorrer todas las vistas; confirmar que no quede texto en español.
4. Pendiente opcional: ProfessionalsView (subtítulo, modal Editar Perfil, Firmar Alta Médica), ProfessionalAnalyticsView, LoginView (label Teléfono, especialidades), vistas admin (Credentials, Tools, Stores, Setup).
