# Comandos de Workflows y Skills – Dentalogic / Antigravity

Este documento es la **referencia única** para que tú (humano) y el agente (IA) trabajen en coordinación.  
Cuando uses un comando, el agente debe cargar el workflow o la skill correspondiente y actuar según sus instrucciones.

---

## Cómo usar los comandos en Cursor

Los comandos de workflow están definidos como **Cursor Commands** en la carpeta `.cursor/commands/`. Cada archivo `.md` (ej. `autonomy.md`, `specify.md`) se convierte en un comando que aparece al escribir **`/`** en el chat de Cursor.

1. **Abrir el chat** (Composer o Chat).
2. **Escribir `/`** (barra).
3. **Elegir el comando** en la lista (ej. `autonomy`, `specify`, `plan`, `implement`).
4. El agente recibe la instrucción del archivo y ejecuta el workflow correspondiente en `.agent/workflows/`.

También puedes **escribir el comando a mano** en el chat (ej. "Ejecuta /autonomy" o "usa el workflow specify"); la regla en `.cursor/rules/agent-workflows.mdc` hace que el agente cargue el workflow correcto.

- **Encadenar:** después de un comando puedes pedir el siguiente (ej. "ahora /plan").
- **Motor completo:** usa el comando **autonomy** para el flujo SDD completo.
- **Skill por contexto:** si tu petición coincide con un *trigger* de la tabla de skills, el agente carga esa skill sin necesidad de comando.

---

## Comandos de Workflow (por fase)

### Fase A: Preparación

| Comando | Archivo | Descripción |
|--------|---------|-------------|
| `/newproject` | [newproject.md](workflows/newproject.md) | Estructura `.agent/`, vincula workflows/skills globales, crea `docs/specs/` y `docs/plans/`. |
| `/advisor` | [advisor.md](workflows/advisor.md) | Consultor estratégico: valida la idea con los 3 pilares (Ciencia, Mercado, Comunidad). Si es viable → sugerir `/specify` o `/plan`. |
| `/skills` | [agents.md](agents.md) | Referencia: el agente debe conocer las skills en `agents.md` y cargar la que aplique según el trigger. |

### Fase B: Especificación y planificación

| Comando | Archivo | Descripción |
|--------|---------|-------------|
| `/specify` | [specify.md](workflows/specify.md) | Genera una especificación técnica rigurosa (`.spec.md`) a partir de requerimientos vagos. Incluye Soberanía de Datos. |
| `/clarify` | [clarify.md](workflows/clarify.md) | Ronda de clarificación: lee el `.spec.md`, detecta ambigüedades y hace hasta 5 preguntas clave. No pasar a `/plan` hasta resolver. |
| `/plan` | [plan.md](workflows/plan.md) | Convierte el `.spec.md` en un plan técnico paso a paso (incl. pasos de DB y comandos de verificación). |
| `/gate` | [gate.md](workflows/gate.md) | Umbral de confianza: evalúa si se puede seguir a implementación. &lt;70% → `/clarify`; ≥90% → se puede `/implement`. |
| `/tasks` | [tasks.md](workflows/tasks.md) | (Opcional) Descompone un plan grande en tickets atómicos (checklist con estados). |

### Fase C: Construcción y calidad

| Comando | Archivo | Descripción |
|--------|---------|-------------|
| `/implement` | [implement.md](workflows/implement.md) | Ejecuta el plan: backend (main, admin_routes, db, gcal), frontend (views/components), luego `/verify`. |
| `/verify` | [verify.md](workflows/verify.md) | Ciclo de verificación: backend (scripts, pytest), frontend (build), integraciones, y opcionalmente `/audit`. |
| `/audit` | [audit.md](workflows/audit.md) | Compara código vs `.spec.md` (SSOT); detecta drift y sugiere correcciones. |
| `/review` | [review.md](workflows/review.md) | Revisión multi-perspectiva: arquitectura, seguridad, clean code. |

### Fase D: Finalización

| Comando | Archivo | Descripción |
|--------|---------|-------------|
| `/push` | [push.md](workflows/push.md) | Sincroniza con GitHub (init si no hay repo, remote, commit, push). Repo privado por defecto. |
| `/finish` | [finish.md](workflows/finish.md) | Cierre de hito: limpieza, registro en memoria, resumen de entrega y siguiente paso sugerido. |

### Workflows por contexto (sin obligación de “fase”)

| Comando | Archivo | Descripción |
|--------|---------|-------------|
| `/autonomy` | [autonomy.md](workflows/autonomy.md) | Motor completo SDD: scaffolding → advisor → specify → plan → gate → implement → verify → audit → review → push → finish. Se detiene si confianza &lt;70%, drift crítico o tests fallan 3 veces. |
| `/bug_fix` o **bug fix** | [bug_fix.md](workflows/bug_fix.md) | Proceso para diagnosticar y solucionar bugs (logs, integraciones, patrones de arreglo, verificación). |
| `/new_feature` | [new_feature.md](workflows/new_feature.md) | Nueva funcionalidad siguiendo arquitectura plana y protocolo Gala (DB, GCal, WhatsApp, frontend, verificación Sovereign). |
| `/mobile-adapt` | [mobile-adapt.md](workflows/mobile-adapt.md) | Adaptar una vista de escritorio a experiencia mobile sin romper desktop. |
| `/update-docs` | [update-docs.md](workflows/update-docs.md) | Actualizar documentación con protocolo Non-Destructive Fusion (Doc Keeper). |

### Secuencia recomendada (referencia)

Ver orden completo en [secuency.md](workflows/secuency.md). Resumen:

1. `/newproject` → `/advisor` → `/skills` (preparación)  
2. `/specify` → `/clarify` → `/plan` → `/gate` → `/tasks` (especificación y plan)  
3. `/implement` → `/verify` → `/audit` → `/review` (construcción y calidad)  
4. `/push` → `/finish` (finalización)

---

## Skills (activación por trigger)

Las skills se activan cuando tu **mensaje o tarea** coincide con los triggers. El agente debe leer el `SKILL.md` correspondiente en `.agent/skills/<NombreSkill>/`.

### Core (infraestructura)

| Skill | Triggers típicos | Uso |
|-------|-------------------|-----|
| **Backend_Sovereign** | `backend`, `fastapi`, `db`, `auth`, `v8.0`, `JIT`, `tenancy` | Arquitectura, endpoints, seguridad, multi-tenant, idempotencia. |
| **Frontend_Nexus** | `frontend`, `react`, `ui`, `hooks`, `tsx`, `componentes` | Componentes React, API, estado, Tailwind. |
| **DB_Evolution** | `schema`, `migration`, `sql`, `rag`, `idempotent` | Cambios de DB, migraciones, JSONB clínico. |

### Comunicación e integraciones

| Skill | Triggers típicos | Uso |
|-------|-------------------|-----|
| **Omnichannel_Chat_Operator** | `chats`, `whatsapp`, `meta`, `mensajes`, `human override` | Mensajería, handoff, YCloud. |
| **Meta_Integration_Diplomat** | `oauth`, `facebook`, `instagram`, `waba`, `pages` | OAuth Meta, activos de negocio. |
| **TiendaNube_Commerce_Bridge** | `tiendanube`, `products`, `orders`, `e-commerce` | Catálogo, órdenes, OAuth Tienda Nube. |

### IA y onboarding

| Skill | Triggers típicos | Uso |
|-------|-------------------|-----|
| **Agent_Configuration_Architect** | `agents`, `prompts`, `tools`, `templates`, `wizard` | Configuración de agentes IA. |
| **Magic_Onboarding_Orchestrator** | `magic`, `wizard`, `onboarding`, `hacer magia` | Proceso “Hacer Magia”, assets. |
| **Business_Forge_Engineer** | `forge`, `canvas`, `visuals`, `assets`, `fusion` | Assets post-magia, Fusion Engine. |
| **Skill_Forge_Master** | `crear skill`, `skill architect`, `nueva skill` | Definir y crear nuevas skills. |
| **Prompt_Architect** | system prompts, plantillas de agentes, RAG, identidad | Ingeniería de prompts (ej. Dra. Laura Delgado). |
| **Spec_Architect** | “crea una especificación”, “planifica esta feature”, `/specify` | Generar y validar `.spec.md` (SDD v2.0). |

### Seguridad y calidad

| Skill | Triggers típicos | Uso |
|-------|-------------------|-----|
| **Credential_Vault_Specialist** | `credentials`, `vault`, `api keys`, `tokens` | Gestión segura de secretos, encriptación. |
| **Sovereign_Auditor** | antes de commit, “revisar seguridad”, “aislamiento” | Ciberseguridad, Protocolo Soberanía. |
| **Testing_Quality** | “crear tests”, “probar feature”, “corregir bugs” | Pytest, Vitest, QA. |

### Documentación y mantenimiento

| Skill | Triggers típicos | Uso |
|-------|-------------------|-----|
| **Doc_Keeper** | “actualiza la doc”, “documenta este cambio” | Actualizar docs con Non-Destructive Fusion. |
| **Skill_Sync** | “sincronizar skills”, después de crear/modificar skill | Actualizar índice en AGENTS.md. |
| **Maintenance_Robot_Architect** | mantenimiento de `db.py`, auto-migración | Maintenance Robot en orchestrator. |

### UI/UX y móvil

| Skill | Triggers típicos | Uso |
|-------|-------------------|-----|
| **Nexus_UI_Architect** | diseño responsivo, mobile first, DKG | Estándar visual y estructural. |
| **Mobile_Adaptation_Architect** | `v8.0`, `mobile`, `responsive`, `DKG`, `scroll isolation` | Blueprint Universal, Scroll Isolation. |

### Otros

| Skill | Triggers típicos | Uso |
|-------|-------------------|-----|
| **Deep_Research** | “investiga esto”, librería nueva, error desconocido | Documentación oficial, validación en la web. |
| **DevOps_EasyPanel** | Dockerfile, docker-compose, variables de entorno | Docker, EasyPanel. |
| **Template_Transplant_Specialist** | trasplante de instrucciones entre capas | Extraer instrucciones a Wizard/Tool Config. |

---

## Comportamiento esperado del agente

1. **Al ver un comando `/X`:**  
   - Resolver `X` en la tabla de comandos de este archivo.  
   - Leer el workflow en `.agent/workflows/X.md` (o el nombre indicado en la tabla).  
   - Ejecutar los pasos del workflow.

2. **Al ver `/autonomy`:**  
   - Leer [autonomy.md](workflows/autonomy.md) y seguir las fases, deteniéndose según las condiciones definidas allí.

3. **Cuando la tarea coincida con un trigger de skill:**  
   - Leer el `SKILL.md` en `.agent/skills/<NombreSkill>/`.  
   - Aplicar las reglas y protocolos de esa skill mientras realiza la tarea.

4. **Coordinación contigo:**  
   - Si un workflow pide “Go” del usuario (p. ej. después de `/gate`), el agente debe preguntar antes de seguir.  
   - No ejecutar `psql` u otros comandos SQL directos en tu entorno; proponer el comando y esperar que tú lo ejecutes y pegues el resultado.

---

*Referencia: agents.md (índice de skills), secuency.md (orden SDD), AGENTS.md (reglas de oro del proyecto).*
