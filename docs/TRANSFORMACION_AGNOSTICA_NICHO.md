# Transformación agnóstica de nicho – De Dentalogic a plataforma reutilizable

**Propósito de este documento:** Sirve como **punto de partida para una nueva conversación con un agente de IA de código**. El flujo es: (1) el agente lee **docs/CONTEXTO_AGENTE_IA.md** y **docs/PROMPT_CONTEXTO_IA_COMPLETO.md** para entender el proyecto actual (Dentalogic); (2) luego lee **este documento** para entender el objetivo de transformación y los primeros pasos. No se aplican cambios al código en esta fase; solo se usa esta documentación para alinear al agente.

**Última actualización:** 2026-02-09

---

## 1. Objetivo de la transformación

- **Estado actual:** Repositorio **Dentalogic** (clínica dental multi-tenant, agente WhatsApp para turnos, triaje, derivación a humano, agenda, pacientes, profesionales, tratamientos).
- **Objetivo:** Dejar la **misma infraestructura y lógica de base** (multi-tenant, auth, API REST, frontend React, agente conversacional por WhatsApp, BD PostgreSQL, Redis, etc.) pero **agnóstica al nicho**, de forma que se pueda:
  - Reutilizar la base para **otro nicho** con otras páginas, otras tools del agente, otro system prompt y otro contrato de API (dominio distinto).
  - Ejemplo de segundo nicho: **CRM para vendedores y setters** de una empresa: cada vendedor/setter conecta su número de WhatsApp, usa plantillas aprobadas por Meta para prospectar, y el dueño/administrador ve toda la actividad y puede medir resultados (métricas por vendedor, conversaciones, etc.).

En resumen: **una base común (auth, tenants, chat, mensajería, métricas, UI shell) y “plugines” o configuraciones por nicho** (dominio dental vs dominio ventas/CRM), sin duplicar toda la infra.

---

## 2. Qué se mantiene (base reutilizable)

| Capa | Qué se mantiene |
|------|------------------|
| **Infra y despliegue** | Docker Compose, EasyPanel, PostgreSQL, Redis, estructura de servicios (orchestrator + whatsapp_service + frontend). |
| **Multi-tenancy** | Modelo tenant_id, aislamiento por sede/organización, reglas de soberanía. |
| **Auth y roles** | Login, registro, JWT, X-Admin-Token, roles (CEO/admin, secretary, professional → equivalentes en CRM: admin, manager, seller/setter). |
| **Frontend base** | React, Vite, Tailwind, AuthContext, LanguageContext, Layout, Sidebar, rutas protegidas, i18n (es/en/fr). |
| **Chat y mensajería** | Flujo WhatsApp (webhook, buffer/debounce, transcripción audio), historial en BD, tenant por conversación. |
| **Patrones de API** | Rutas admin bajo `verify_admin_token`, filtro por tenant_id, estructura de respuestas. |
| **Workflows y agentes** | .agent/workflows (autonomy, specify, bug_fix, update-docs), skills, protocolo SDD. |

---

## 3. Qué cambia por nicho

| Aspecto | Dental (actual) | Otro nicho (ej. CRM vendedores/setters) |
|--------|------------------|----------------------------------------|
| **Dominio** | Pacientes, turnos, profesionales, tratamientos, clínica. | Prospectos, leads, vendedores/setters, plantillas Meta, pipelines, métricas de venta. |
| **Páginas / vistas** | Agenda, Pacientes, Chats, Aprobaciones (staff), Tratamientos, Sedes, Analíticas por profesional, Config. | Dashboard de ventas, Lista de prospectos/leads, Chats por vendedor, Plantillas aprobadas, Conexión de números, Métricas por vendedor/setter, Config. |
| **Tools del agente** | list_services, check_availability, book_appointment, triage_urgency, derivhumano, cancel_appointment, reschedule_appointment, list_my_appointments. | Por definir: ej. list_templates, send_template, log_lead_stage, assign_lead, derivhumano, métricas propias. |
| **System prompt del agente** | Persona asistente dental, voseo, flujo turnos/disponibilidad/agendar. | Persona asistente de ventas/prospección, tono y flujo según uso de plantillas y etapas de lead. |
| **Contrato de API** | Endpoints tipo /admin/patients, /admin/appointments, /admin/professionals, /admin/calendar, treatment_types, etc. | Endpoints tipo /admin/leads, /admin/sellers, /admin/templates, /admin/connections, /admin/metrics, etc. |
| **Modelo de datos** | patients, appointments, professionals, treatment_types, clinical_records, google_calendar_blocks. | leads, sellers, templates, whatsapp_connections, template_sends, events o métricas por vendedor. |

La **lógica** (cómo se estructura la API, cómo se filtran datos por tenant, cómo se integra el agente con el chat y la BD) se mantiene; lo que cambia es el **dominio**, las **entidades**, las **tools** y el **prompt**.

---

## 4. Enfoque recomendado (sin aplicar aún)

- **Fase de diseño:** Definir un “núcleo agnóstico” (auth, tenants, chat, UI shell, rutas base) y un “módulo de nicho” (configuración que define: entidades, endpoints, tools del agente, system prompt, vistas).
- **Estrategias posibles:** (a) Extraer dominio dental a un “plugin” o módulo configurable y dejar el core sin conceptos dentales; (b) Crear un segundo producto en el mismo repo (ej. carpeta `niche_dental` y `niche_crm_sales`) que comparten core; (c) Parametrizar todo por “niche_id” o “product_type” en tenant y cargar configuración (tools, prompt, rutas) desde BD o archivos por nicho. El documento de transformación debe servir para que un agente proponga y documente la estrategia elegida.
- **No aplicar cambios al código en este paso:** Solo documentar y generar prompts para que, en una conversación posterior, el agente ejecute la refactorización paso a paso.

---

## 5. Ejemplo de segundo nicho: CRM vendedores/setters

- **Actores:** Admin (dueño/empresa), managers (opcional), vendedores/setters que usan WhatsApp para prospectar.
- **Funcionalidad objetivo:**
  - Cada vendedor/setter **conecta su número** de WhatsApp (o se le asigna uno) dentro del tenant.
  - Uso de **plantillas aprobadas por Meta** para enviar mensajes de prospección (sin inventar texto libre que Meta rechace).
  - El **admin** ve todas las conversaciones y actividades por vendedor, puede **medir** (mensajes enviados, plantillas usadas, respuestas, conversiones, etc.).
- **Diferencias claras con dental:** No hay “turnos” ni “tratamientos”; hay “leads/prospectos”, “plantillas”, “conexiones de número” y “métricas por vendedor”.

Este ejemplo debe usarse como referencia para que el agente entienda el tipo de contrato de API, tools y vistas que se buscarán en el segundo nicho.

---

## 6. Cómo usar este documento con un agente de código

1. En un **chat nuevo**, hacer que el agente lea primero **docs/CONTEXTO_AGENTE_IA.md** y **docs/PROMPT_CONTEXTO_IA_COMPLETO.md** (o pegar el bloque de PROMPT_CONTEXTO_IA_COMPLETO como primer mensaje).
2. Luego indicar: “Lee **docs/TRANSFORMACION_AGNOSTICA_NICHO.md**. No apliques cambios al código; solo entiende el objetivo y prepara respuestas o un plan de refactorización según lo que ahí se describe.”
3. A partir de ahí, usar los **10 prompts clave** de la sección siguiente para ir guiando la conversación (especificar, planificar, listar conceptos a extraer, diseñar módulo de nicho, etc.).

---

## 7. Diez prompts clave para comenzar el proceso de transformación

Usar estos prompts **en orden sugerido** al iniciar la conversación con el agente (después de que haya leído CONTEXTO_AGENTE_IA, PROMPT_CONTEXTO_IA_COMPLETO y este documento).

1. **Inventario de dominio dental**  
   “Analiza el repositorio actual (orchestrator_service, frontend_react, docs) y lista todos los conceptos, entidades y términos que son específicos del dominio dental (pacientes, turnos, profesionales, tratamientos, clínica, agenda, etc.). Agrupa por: modelo de datos, endpoints de API, tools del agente, textos del system prompt y vistas/pantallas del frontend. No modifiques código; solo documenta en un .md o en la respuesta.”

2. **Núcleo agnóstico**  
   “A partir del inventario anterior, propón qué partes del código y de la base de datos deberían quedar en un ‘núcleo agnóstico’ (auth, tenants, usuarios, chat, historial de mensajes, configuración por tenant) y cuáles deberían moverse a un ‘módulo dental’ o configurarse por nicho. Lista archivos y carpetas concretos. No implementes; solo plan técnico.”

3. **Configuración de nicho**  
   “Diseña (en documento .md o spec) un módulo o esquema de ‘configuración de nicho’ que permita definir por tenant o por producto: (a) nombre del nicho (dental, crm_sales, etc.), (b) lista de tools del agente (nombre y descripción), (c) system prompt base del agente, (d) conjunto de rutas de API (o nombres de recursos) que ese nicho expone. No escribas código; solo el diseño.”

4. **Contrato de API agnóstico vs por nicho**  
   “Describe cómo separar el contrato de API en: (1) rutas comunes (auth, tenants, settings, chat) y (2) rutas por nicho (dental: patients, appointments, professionals, treatment_types; crm_sales: leads, sellers, templates, connections, metrics). Propón convenciones de URL o de versionado (ej. /admin/dental/... vs /admin/crm/...) o una tabla de recursos por niche_id. Solo diseño, sin implementar.”

5. **Tools del agente parametrizables**  
   “El agente actual tiene tools fijas en main.py (list_services, check_availability, book_appointment, etc.). Propón cómo hacer que la lista de tools sea configurable por nicho: por ejemplo, registro de tools por nombre y función, o un loader que importe un módulo de tools según el nicho del tenant. Documenta la propuesta; no cambies el código aún.”

6. **System prompt por nicho**  
   “Hoy el system prompt del agente está hardcodeado para Dentalogic. Propón cómo almacenar o cargar un system prompt distinto por nicho (archivo por nicho, campo en BD en tenants.config, o plantilla con variables). Incluye cómo se inyectarían clinic_name, current_time, etc. Solo diseño.”

7. **Frontend: shell y vistas por nicho**  
   “El frontend tiene vistas como Agenda, Pacientes, Tratamientos. Propón una estructura donde exista un ‘shell’ común (Layout, Sidebar, Login, Config) y las vistas de contenido se carguen según el nicho (dental: Agenda, Pacientes, etc.; crm_sales: Leads, Plantillas, Métricas por vendedor). Puedes proponer rutas tipo /app/dental/agenda y /app/crm/leads o un selector de producto tras login. Solo diseño y estructura de carpetas.”

8. **Modelo de datos para CRM vendedores/setters**  
   “Para el nicho CRM de vendedores/setters (conexión de números, plantillas Meta, prospectos, métricas): escribe una spec o documento que defina las entidades principales (leads, sellers, templates, whatsapp_connections, eventos de mensaje/plantilla), relaciones con tenant_id, y endpoints mínimos (CRUD o lecturas) que necesitaría la API. No implementes en el repo; solo el documento.”

9. **Plan de migración por fases**  
   “Genera un plan por fases (Fase 0: solo documentación y diseño; Fase 1: extraer configuración de nicho sin romper dental; Fase 2: segundo nicho CRM en paralelo o en rama; Fase 3: unificar bajo un solo entrypoint por tenant/niche). Asigna cada fase a tareas concretas (archivos a tocar, orden sugerido). No ejecutes cambios; solo el plan en .md.”

10. **Checklist de validación post-refactor**  
    “Lista un checklist de validación para cuando se aplique la refactorización: (a) Dentalogic sigue funcionando igual (login, agenda, turnos, agente con las mismas tools); (b) un segundo nicho (ej. CRM) puede activarse por tenant o por ruta sin romper el primero; (c) documentación (CONTEXTO_AGENTE_IA, README) actualizada para describir el modelo agnóstico. No implementes; solo el checklist.”

---

## 8. Restricciones durante la fase de documentación

- **No ejecutar SQL** directo en la base del usuario; si hace falta proponer esquemas, hacerlo en documentos o en migraciones propuestas para que el usuario las ejecute.
- **No modificar** el código existente hasta que el usuario apruebe un plan o una fase concreta.
- **Preservar** el comportamiento actual de Dentalogic en cualquier propuesta (retrocompatibilidad hasta que se decida lo contrario).
- **Seguir** las reglas de soberanía (tenant_id) y de documentación (Non-Destructive Fusion) en cualquier doc que se genere o actualice.

---

## 9. Dónde guardar salidas del agente

- Planes, inventarios y diseños generados a partir de los 10 prompts pueden guardarse en **docs/** con nombres como:
  - `docs/transformacion/01_inventario_dominio_dental.md`
  - `docs/transformacion/02_nucleo_agnostico_propuesta.md`
  - `docs/transformacion/03_config_nicho_diseño.md`
  - etc.
- O en un único documento **docs/PLAN_TRANSFORMACION_AGNOSTICA.md** que el agente vaya ampliando por secciones según los prompts.

---

*Este documento es solo documentación para arrancar la conversación con un agente de código. No implica aplicar cambios al repositorio hasta que el usuario lo indique.*
