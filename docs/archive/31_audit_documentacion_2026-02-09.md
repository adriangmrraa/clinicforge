# Auditoría de documentación – Alineación con plataforma SaaS (2026-02-09)

**Workflow:** Audit + Update Docs (Non-Destructive Fusion).  
**Objetivo:** Verificar que toda la documentación esté alineada con la última versión de la plataforma SaaS y corregir referencias rotas o desactualizadas.

---

## 1. Alcance

- **Documentación revisada:** README.md, AGENTS.md, docs/*.md (arquitectura, API_REFERENCE, CONTEXTO_AGENTE_IA, AUDIT_ESTADO_PROYECTO, cambios_recientes, PROMPT_CONTEXTO_IA_COMPLETO, PROTOCOLO_AUTONOMIA_SDD, SPECS_IMPLEMENTADOS_INDICE, 08_troubleshooting, 29_seguridad_owasp_auditoria, etc.).
- **Código de referencia:** Rutas frontend (App.tsx), vistas (LandingView, ConfigView, UserApprovalView), rutas API (admin_routes, auth_routes, main.py), AGENTS.md.

---
   
## 2. Verificación doc vs código (plataforma actual)

| Área | Estado | Comentario |
|------|--------|------------|
| **Rutas públicas** | ✅ Match | README y docs indican `/demo`, `/login`; código: `Route path="/demo"` (LandingView), login en `/login`. |
| **Configuración** | ✅ Match | README/AGENTS: selector idioma en Configuración, ruta `/configuracion`; Sidebar: `path: '/configuracion'`, ConfigView. |
| **Auth y admin** | ✅ Match | API_REFERENCE y AGENTS: JWT + X-Admin-Token, verify_admin_token; auth_routes y admin_routes coherentes. |
| **OpenAPI / Swagger** | ✅ Match | README y API_REFERENCE: `/docs`, `/redoc`, `/openapi.json`; main.py con docs_url, openapi_tags, securitySchemes. |
| **Multi-tenant e idioma** | ✅ Match | README (idiomas es/en/fr, multi-sede), AGENTS.md (tenant_id, ui_language, LanguageProvider). |
| **Landing / Demo** | ✅ Match | README describe landing en `/demo`, Probar app, Probar Agente IA; LandingView y ruta `/demo` presentes. |

**Conclusión:** La documentación principal (README, AGENTS, API_REFERENCE, 01_architecture) está **alineada** con el estado actual del código SaaS.

---

## 3. Drift detectado y correcciones aplicadas (Update Docs)

### 3.1 Referencias a archivos .spec.md eliminados

Tras la consolidación del 2026-02-09, varios documentos seguían enlazando a `.spec.md` ya eliminados. Se aplicó **Non-Destructive Fusion** (expandir/referenciar sin borrar contexto):

| Documento | Cambio aplicado |
|-----------|------------------|
| **AUDIT_ESTADO_PROYECTO.md** | Añadida nota al inicio indicando consolidación en SPECS_IMPLEMENTADOS_INDICE. Tabla "Specs vs código" (sección 6): columna "Ubicación" sustituida por "Documentación actual" con referencias a SPECS_IMPLEMENTADOS_INDICE, README, API_REFERENCE, AGENTS.md. Sección 9.3 reescrita para apuntar a trazabilidad en el índice en lugar de paths a .spec.md. |
| **cambios_recientes_2026-02-10.md** | Reemplazadas referencias a `docs/27_staff_scroll_aislamiento.spec.md` y `docs/28_landing_demo_publica.spec.md` por SPECS_IMPLEMENTADOS_INDICE y AGENTS.md/README. |
| **PROMPT_CONTEXTO_IA_COMPLETO.md** | En /specify se aclara que las especificaciones históricas están en docs/SPECS_IMPLEMENTADOS_INDICE.md y que los .spec.md antiguos fueron retirados. |
| **PROTOCOLO_AUTONOMIA_SDD.md** | Regla de "especificación" ampliada: documento en docs/ o .spec.md; trazabilidad de features implementados en SPECS_IMPLEMENTADOS_INDICE. Criterio de detención para /audit actualizado: "documentación de referencia (docs/, AGENTS.md, SPECS_IMPLEMENTADOS_INDICE)" en lugar de solo ".spec.md". |

### 3.2 Documentos sin cambios (ya correctos o solo mención genérica)

- **SPECS_IMPLEMENTADOS_INDICE.md:** Lista los .spec.md retirados y dónde está cada tema; no requiere enlaces a archivos eliminados.
- **PROMPT_CONTEXTO_IA_COMPLETO / PROTOCOLO_AUTONOMIA_SDD:** Las menciones genéricas a "generar .spec.md" para *nuevas* features se mantienen; se añadió contexto de consolidación.
- **repomix-output-*.md:** Export largo; las referencias a .spec.md son descriptivas del flujo; no se modificó (documento de apoyo).

---

## 4. Enlaces y rutas comprobados

- README: enlaces a docs/01_architecture, 02_environment_variables, API_REFERENCE, SPECS_IMPLEMENTADOS_INDICE, 29_seguridad_owasp_auditoria, CONTEXTO_AGENTE_IA, etc. **Válidos** (archivos existen).
- CONTEXTO_AGENTE_IA: tabla de documentación actualizada en sesión anterior; apunta a SPECS_IMPLEMENTADOS_INDICE y documentos actuales.
- audit_26_calendario_hibrido_2026-02-10.md: referencia a spec 26 reemplazada por "contenido migrado a 01_architecture, 08_troubleshooting, SPECS_IMPLEMENTADOS_INDICE".

---

## 5. Resumen

| Criterio | Resultado |
|----------|-----------|
| Documentación vs código (SaaS actual) | ✅ **Match** |
| Referencias a .spec.md eliminados | ✅ **Corregidas** (AUDIT_ESTADO_PROYECTO, cambios_recientes, PROMPT, PROTOCOLO) |
| Enlaces internos | ✅ Sin enlaces rotos detectados a documentos existentes |
| Protocolo aplicado | Non-Destructive Fusion (expandir/referenciar sin eliminar contenido útil) |

**Veredicto:** La documentación queda **alineada con la última versión de la plataforma SaaS**. Las correcciones realizadas son compatibles con el workflow Update Docs y con la consolidación previa de especificaciones en SPECS_IMPLEMENTADOS_INDICE.md.

---

*Auditoría ejecutada según .agent/workflows/audit.md y update-docs.md (Non-Destructive Fusion).*
