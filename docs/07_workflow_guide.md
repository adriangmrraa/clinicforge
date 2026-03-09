# Guía de Flujo de Trabajo y Colaboración

Este documento detalla cómo trabajar efectivamente en el proyecto **Dentalogic** (Nexus v7.6), asegurando éxito, estabilidad y escalabilidad.

## 1. Ciclo de Vida de una Tarea

Para cualquier nueva funcionalidad o corrección, sigue este ciclo:

### 1️⃣ Planificación
- **Define el objetivo:** "Arreglar bug X", "Agregar feature Y"
- **Investiga el código actual** relacionado
- **Crea un plan** detallando qué archivos se tocarán
- **Espera aprobación** antes de escribir código

### 2️⃣ Ejecución
- Edita los archivos según el plan
- Mantén un registro de cambios
- Si encuentras algo inesperado, actualiza el plan

### 3️⃣ Verificación
- Prueba el código localmente
- Si existen tests, córrelosy
- Solicita que se pruebe manualmente si es necesario
- Documenta los resultados

### 4️⃣ Commit / Entrega
- Sellamos el trabajo con un commit
```bash
git add .
git commit -m "feat: descripción clara de cambios"
```

---

## 2. Estrategia de Git

### Rama Principal
- Trabajamos sobre `main` directamente para desarrollo rápido
- **Requiere testeo riguroso** antes de cada commit

### Recomendación para Tareas Grandes
- Usar feature branches para trabajos significativos:
```bash
git checkout -b feature/nueva-funcionalidad
# ... trabajo ...
git push origin feature/nueva-funcionalidad
```

---

## 3. Documentación

### Antes de Codificar
- Actualiza la documentación si cambias comportamiento
- Agrega ejemplos si creas una nueva feature

### Después de Codificar
- Verifica que los docs reflejen los cambios
- Actualiza README.md si es un cambio importante

### Ubicaciones
- **Cambios fundamentales:** actualiza `README.md`
- **Arquitectura:** actualiza `docs/01_architecture.md`
- **Configuración:** actualiza `docs/02_environment_variables.md`
- **Despliegue:** actualiza `docs/03_deployment_guide.md`
- **Persona/Reglas:** actualiza `docs/04_agent_logic_and_persona.md`
- **Desarrollo:** actualiza `docs/05_developer_notes.md`
- **Prompt:** actualiza `docs/06_ai_prompt_template.md`
- **Estado detallado (endpoints, frontend, BD):** actualiza `docs/AUDIT_ESTADO_PROYECTO.md`
- **Idioma UI y agente:** ver README (Idiomas) y `docs/SPECS_IMPLEMENTADOS_INDICE.md`
- **Landing / demo pública:** ver README (Landing / Demo) y `docs/SPECS_IMPLEMENTADOS_INDICE.md`
- **Contexto para otra IA:** actualiza `docs/CONTEXTO_AGENTE_IA.md` (punto de entrada para agentes en otra conversación)

---

## 4. Checklist Pre-Commit

Antes de hacer commit, verifica:

- [ ] El código funciona localmente
- [ ] Los tests pasan (si existen)
- [ ] La documentación está actualizada
- [ ] No hay archivos temporales o .env en el commit
- [ ] El mensaje de commit es claro y descriptivo

---

## 5. Troubleshooting Durante Desarrollo

### El bot no responde
1. Verificar logs: `docker-compose logs -f orchestrator_service`
2. Chequear variables de entorno
3. Verificar conectividad con PostgreSQL y Redis

### Cambios no se reflejan
1. Reiniciar el contenedor: `docker-compose restart orchestrator_service`
2. Verificar que el archivo fue guardado
3. Limpiar caché de Redis si es necesario

### Errores de BD
1. Ver logs de PostgreSQL: `docker-compose logs -f postgres`
2. Si está corrupta, resetear: `docker-compose down -v && docker-compose up`
3. Las migraciones se ejecutan automáticamente en startup

---

## 6. Comunicación Entre Servicios

### Flujo Principal de un Mensaje
```
Usuario WhatsApp
    ↓
YCloud API
    ↓
WhatsApp Service (8002) - validar firma, deduplicar, transcribir
    ↓
POST /chat al Orchestrator (8000)
    ↓
Orchestrator - LangChain agent, ejecutar tools
    ↓
Respuesta JSON con mensajes
    ↓
WhatsApp Service - enviar burbujas a YCloud
    ↓
Usuario recibe mensajes
```

### Tokens y Autenticación
- **INTERNAL_API_TOKEN:** Entre microservicios
- **ADMIN_TOKEN:** Para Platform UI → Orchestrator
- **YCLOUD_WEBHOOK_SECRET:** Para validar webhooks de YCloud
- **OPENAI_API_KEY:** Para LLM y Whisper

---

## 7. Performance y Optimizaciones

### Cómo Hacer Más Rápido
- Reducir STORE_CATALOG_KNOWLEDGE si es muy largo (> 2KB)
- Aumentar `REDIS_URL` connection pool si hay bottleneck
- Cachear búsquedas frecuentes en Redis (1 hora TTL)

### Debugging Lento
- Agregar logs con timestamp
- Usar Prometheus metrics para profiling
- Chequear latencia de BD con `EXPLAIN`

---

## 8. Cuando Estés Atascado

1. Revisa los logs: `docker-compose logs | grep error`
2. Consulta `docs/03_deployment_guide.md` sección "Troubleshooting"
3. Revisa `AGENTS.md` para reglas críticas
4. Para contexto completo (otra IA o nueva conversación): lee `docs/CONTEXTO_AGENTE_IA.md`
5. Lee el código fuente (siempre es la fuente de verdad)

---

## 9. Workflows Estructurados SDD v3.0 (Adoptados Febrero 2026)

El proyecto ha adoptado el **Motor de Autonomía SDD v3.0** con workflows estructurados para desarrollo consistente:

### **Workflows Principales:**

#### **⚡ Autonomy Engine (`/autonomy`)**
Motor completo de 7 fases para transformar requerimientos vagos en software funcional:
1. **Triage** - Clasificación de solicitud
2. **Scaffolding** - Preparación de contexto
3. **Specification** - Generación SSOT (`.spec.md`)
4. **Planning & Gatekeeping** - Planificación y evaluación de confianza
5. **Implementation** - Ejecución con checkpoints
6. **Validation** - Testing, auditoría, revisión
7. **Completion** - Sync GitHub, documentación

#### **📋 Especificación (`/specify`)**
Generación de Single Source of Truth (SSOT):
- Contexto y objetivos
- Requerimientos técnicos (backend, frontend, UI/UX)
- Criterios de aceptación (Gherkin)
- Esquema de datos
- Riesgos y mitigación

#### **📋 Planificación (`/plan`)**
Transformación de especificaciones en planes ejecutables:
- Goal description
- User review required (breaking changes)
- Proposed changes por componente
- Verification plan (tests, quality gates)

#### **🔧 Implementación (`/implement`)**
Ejecución disciplinada con checkpoints:
- Sigue `implementation_plan.md`
- Checkpoints de calidad durante implementación
- Non-destructive fusion (preserva lógica existente)

#### **✅ Verificación (`/verify`)**
Validación y corrección autónoma:
- Ejecución de tests automatizados
- Auto-corrección de fallos (máximo 3 intentos)
- Auditoría de drift (`/audit`)
- Revisión de calidad (`/review`)

### **Workflows de Soporte:**

- **🐛 `/bug_fix`** - Corrección de errores
- **📚 `/document`** - Documentación
- **📱 `/mobile-adapt`** - Adaptación mobile
- **🔄 `/update-docs`** - Actualización documentación
- **🎯 `/advisor`** - Análisis de viabilidad
- **❓ `/clarify`** - Clarificación de ambigüedades
- **🚪 `/gate`** - Gatekeeping técnico (evaluación confianza)
- **📋 `/tasks`** - Desglose en tareas
- **🔄 `/push`** - Sync con GitHub
- **🏁 `/finish`** - Cierre de sprint

### **Principios Arquitectónicos No Negociables:**

1. **Data Sovereignty** - Todos los queries SQL incluyen `tenant_id` filtering
2. **Scroll Isolation** - UI: `h-screen overflow-hidden` + `min-h-0 overflow-y-auto`
3. **Idempotent Migrations** - Database changes seguros para múltiples ejecuciones
4. **Non-Destructive Fusion** - Preservar lógica existente mientras se agrega nueva

### **Skills Especializadas:**

- **Sovereign Backend Engineer** - Multi-tenancy, JIT logic
- **Nexus UI Architect** - Scroll Isolation, Mobile-First
- **DB Schema Surgeon** - Evolución segura de esquemas
- **Spec Architect** - Generación y validación de specs
- **Deep Researcher** - Validación en documentación oficial

---

*Guía de Flujo de Trabajo Dentalogic © 2026*  
*Actualizado con SDD v3.0 - Febrero 2026*
