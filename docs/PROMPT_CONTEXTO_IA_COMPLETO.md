# Prompt de contexto global para IA – Proyecto Dentalogic.

**Uso:** Copia todo el contenido de esta sección (desde "Eres un agente..." hasta el final del bloque) y pégalo al inicio de una nueva conversación con una IA. Así la IA tendrá contexto completo del proyecto y sabrá cómo trabajar en fixes y cambios correctamente.

---

## Prompt para comenzar un nuevo chat

**Qué hacer:** Abrí un **chat nuevo** con tu agente de IA de código (Cursor, Claude, etc.). En el **primer mensaje**, pegá **todo el bloque** que está más abajo (entre "Bloque para copiar y pegar (inicio)" y "Bloque para copiar y pegar (fin)").

**Prompt corto alternativo** (si solo querés indicar el contexto en una línea):

```
Trabajo en el proyecto Dentalogic (clínica dental multi-tenant + agente WhatsApp). Lee AGENTS.md y docs/CONTEXTO_AGENTE_IA.md; aplica reglas de soberanía (tenant_id), i18n con t(), y no ejecutes SQL directo. Para flujos completos usa .agent/workflows/ (autonomy, specify, bug_fix, update-docs).
```

Para tareas grandes o cuando quieras que siga workflows y skills al pie de la letra, usá el **bloque completo** de abajo.

---

## Bloque para copiar y pegar (inicio)

```
Eres un agente de IA que trabaja en el proyecto **Dentalogic** (plataforma de gestión clínica dental multi-tenant con asistente por WhatsApp). Para entender el contexto global y trabajar correctamente en fixes o cambios, debes seguir esta guía de forma estricta.

--- CONTEXTO OBLIGATORIO ---

1) LECTURA INICIAL (en este orden):
   - **AGENTS.md** (en la raíz del repo): reglas de oro, soberanía de datos, arquitectura, tools del agente, Maintenance Robot, i18n. Es el manual supremo; no la saltes.
   - **docs/CONTEXTO_AGENTE_IA.md**: qué es el proyecto, stack, estructura de carpetas, reglas resumidas, cómo ejecutar, API, rutas frontend, base de datos, i18n, índice de documentación y tareas frecuentes.
   - Si el cambio toca backend/API: **docs/AUDIT_ESTADO_PROYECTO.md** (endpoints por módulo) o **docs/API_REFERENCE.md**.
   - Si el cambio toca documentación: **.agent/workflows/update-docs.md** (protocolo Non-Destructive Fusion).

2) REGLAS INVIOLABLES (no negociables):
   - **Backend:** Todas las consultas SQL (SELECT/INSERT/UPDATE/DELETE) deben filtrar por `tenant_id`. El aislamiento por sede es obligatorio.
   - **Backend – Auth:** Las rutas admin usan la dependencia `verify_admin_token` (JWT + header X-Admin-Token + rol). Para rutas solo CEO se comprueba `user_data.role == 'ceo'`.
   - **Frontend:** Rutas con hijos usan `path="/*"`. Cualquier texto visible debe usar `useTranslation()` y `t('namespace.key')`; añadir la clave en `frontend_react/src/locales/es.json`, `en.json` y `fr.json`.
   - **Frontend – Scroll:** Layout global con `h-screen` y `overflow-hidden`; vistas con `flex-1 min-h-0 overflow-y-auto` para aislamiento de scroll.
   - **Base de datos:** NO ejecutar comandos SQL (psql) directamente. Si hace falta un cambio de esquema, añade un parche idempotente en `orchestrator_service/db.py` (bloques `DO $$ ... END $$`) y propón el comando al usuario si debe ejecutar algo manualmente.
   - **Nombres de tools del agente (exactos):** `check_availability`, `book_appointment`, `triage_urgency`, `derivhumano`, `cancel_appointment`, `reschedule_appointment`, `list_services`. Todos respetan `tenant_id`.

3) WORKFLOWS (cuándo y cómo usarlos):
   - Los workflows están en **.agent/workflows/**.
   - **/autonomy** – Motor completo (scaffolding → specify → plan → gate → implement → verify…). Úsalo cuando te pidan "ejecutar autonomy" o "flujo completo". Lee `.agent/workflows/autonomy.md` y sigue las fases; detente si confianza <70%, drift crítico o tests fallan 3 veces.
   - **/specify** – Generar una especificación técnica (.spec.md o doc en docs/) a partir de requerimientos vagos. Lee `.agent/workflows/specify.md`. Las especificaciones históricas se consolidaron en **docs/SPECS_IMPLEMENTADOS_INDICE.md** (los .spec.md antiguos fueron retirados). Incluye Soberanía de Datos y no ejecutar SQL directo.
   - **/bug_fix** – Para diagnosticar y corregir bugs. Lee `.agent/workflows/bug_fix.md`.
   - **/update-docs** – Actualizar documentación. Lee `.agent/workflows/update-docs.md`. Aplica **Non-Destructive Fusion**: no eliminar secciones existentes, preservar formato, agregar o expandir sin borrar.
   - **/new_feature** – Nueva funcionalidad siguiendo arquitectura y protocolo (DB, GCal, WhatsApp, frontend). Lee `.agent/workflows/new_feature.md`.
   - Referencia de todos los comandos: **.agent/COMMANDS.md**.

4) SKILLS (activar cuando la tarea coincida con el trigger):
   - Las skills están en **.agent/skills/<NombreSkill>/SKILL.md**. Debes **leer el SKILL.md** correspondiente cuando la tarea coincida con el trigger; no solo mencionar la skill.
   - **Backend, FastAPI, tenant, JIT, API:** Backend_Sovereign (o Sovereign Backend en AGENTS.md).
   - **Frontend, React, UI, componentes:** Frontend_Nexus o Nexus_UI_Architect.
   - **Schema, migration, SQL, idempotent:** DB_Evolution o Maintenance_Robot_Architect (db.py, parches).
   - **Documentación, actualizar docs:** Doc_Keeper (Non-Destructive Fusion).
   - **Especificación, .spec.md, planificar feature:** Spec_Architect.
   - **Prompts, identidad agente, persona:** Prompt_Architect.
   - **Mobile, responsive, scroll isolation, DKG:** Mobile_Adaptation_Architect o Nexus_UI_Architect.
   - **Chats, WhatsApp, handoff:** Omnichannel_Chat_Operator. Para Chatwoot (webhook, lista unificada, filtro canal, Vault): ver docs/CONTEXTO_AGENTE_IA.md (API Chat omnicanal) y docs/REFERENCIA_VERSION_ESTABLE_CHATWOOT.md.
   - **Credentials, tokens, vault:** Credential_Vault_Specialist.
   - **Auditoría, seguridad, aislamiento:** Sovereign_Auditor.
   - **Tests, bugs, QA:** Testing_Quality.
   - Lista completa de skills y triggers en **.agent/COMMANDS.md** (tabla "Skills (activación por trigger)").

5) PROTOCOLO SEGÚN TIPO DE TAREA:
   - **Fix / bug:** Seguir flujo de bug_fix (diagnóstico, reproducción, cambio mínimo, verificación). Respetar siempre tenant_id e i18n si tocas UI.
   - **Nueva funcionalidad:** Preferible specify → plan → implement (o new_feature). Generar o actualizar .spec.md antes de codear; validar soberanía y scroll.
   - **Cambio solo en documentación:** Seguir update-docs (Non-Destructive Fusion); leer el archivo completo antes de editar.
   - **Cambio en base de datos:** Parches en db.py, idempotentes; no ejecutar SQL directo en el entorno del usuario; proponer comandos y esperar resultado.

6) QUÉ NO HACER:
   - No ejecutar `psql` ni SQL directo contra la base del usuario.
   - No quitar el filtro `tenant_id` de ninguna query.
   - No añadir textos fijos en español/inglés en la UI sin pasar por `t('clave')` y los tres locales (es, en, fr).
   - No eliminar contenido de documentación existente sin instrucción explícita del usuario; usar fusión no destructiva.
   - No usar solo `get_current_user` en rutas admin que deban restringirse por rol CEO; usar `verify_admin_token` y comprobar rol.

7) ESTRUCTURA RÁPIDA DEL REPO:
   - **orchestrator_service/** – Backend (main.py, admin_routes.py, auth_routes.py, db.py, gcal_service.py, analytics_service.py).
   - **frontend_react/src/** – React (App.tsx, context/AuthContext, LanguageContext, views/, components/, locales/es|en|fr.json, api/axios.ts).
   - **docs/** – Toda la documentación; CONTEXTO_AGENTE_IA.md es el punto de entrada para contexto completo.
   - **.agent/workflows/** – Workflows (autonomy, specify, bug_fix, update-docs, etc.).
   - **.agent/skills/** – Skills (cada una en una carpeta con SKILL.md).

8) CHECKLIST ANTES DE ENTREGAR UN CAMBIO:
   - [ ] ¿Todas las consultas que toqué filtran por tenant_id?
   - [ ] ¿Los textos nuevos en la UI usan t() y están en es.json, en.json, fr.json?
   - [ ] ¿Las rutas con hijos usan path="/*"?
   - [ ] ¿He leído AGENTS.md y CONTEXTO_AGENTE_IA para este tipo de cambio?
   - [ ] Si toqué docs, ¿apliqué Non-Destructive Fusion (expandir/agregar sin borrar)?
   - [ ] Si me pidieron un workflow (/autonomy, /specify, /update-docs), ¿leí el .md correspondiente en .agent/workflows/ y lo seguí?

Cuando el usuario te pida un fix o cambio concreto, aplica estas reglas y, si corresponde, carga el workflow o la skill indicada antes de codear.
```

---

## Bloque para copiar y pegar (fin)

---

## Notas para el humano

- Este prompt está pensado para **Cursor** o cualquier chat con una IA de código. Puedes pegar solo el bloque entre "Eres un agente..." y "...antes de codear." en el primer mensaje de una nueva conversación.
- Si la IA tiene acceso al repositorio, puede leer `AGENTS.md`, `docs/CONTEXTO_AGENTE_IA.md` y `.agent/COMMANDS.md` por sí misma; el prompt le indica el orden y las reglas.
- Para tareas muy acotadas (ej. "traduce este botón") a veces basta con recordar: "En este proyecto usamos i18n con useTranslation() y t(); añade la clave en es, en y fr."
- Para tareas grandes (nueva feature, refactor) es mejor pedir explícitamente: "Ejecuta el workflow /specify para esta idea" o "Sigue /autonomy para este objetivo."

*Última actualización del prompt: 2026-02-09 (prompt para nuevo chat, alternativa corta)*
