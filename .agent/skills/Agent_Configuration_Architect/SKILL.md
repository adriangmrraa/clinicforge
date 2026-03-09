---
name: "Agent Configuration Architect"
description: "Especialista en configuración de agentes de IA: templates, tools, models, prompts y seed data."
trigger: "agents, agentes, AI, tools, templates, models, prompts, system prompt, wizard"
scope: "AGENTS"
auto-invoke: true
---

# Agent Configuration Architect - Dentalogic (v7.1.2)

## 1. Concepto: La Arquitectura de Agentes Nexus

### Filosofía Multi-Capa
Nexus no usa un único system prompt estático. Utiliza una arquitectura de **3 capas** para construir la inteligencia del agente en runtime:

1.  **Capa 1: Template Base (Polimorfismo)**: Definida en `agent_service/app/core/agent_templates.py`. Provee la estructura de identidad y reglas core según el rol (Sales, Support, Leads, Logistics).
2.  **Capa 2: Wizard Overrides (Identidad de Negocio)**: Datos específicos del cliente (Tono, Reglas de Negocio, Diccionario de Sinónimos) que sobreescriben los valores del template.
3.  **Capa 3: Instrucciones de Tools (Táctica de Ejecución)**: Instrucciones detalladas sobre CÓMO usar cada herramienta y CÓMO formatear la respuesta, inyectadas dinámicamente.

---

## 2. Configuración de Templates (Wizard Defaults)

Los valores predeterminados para el Wizard se definen en `orchestrator_service/app/api/agents.py` → `AGENT_TEMPLATES`.

### Ejemplo: Sales Agent (Pointe Coach inspired)
```python
AGENT_TEMPLATES = {
    "sales": {
        "agent_name": "Agente de Ventas (IA)",
        "model_provider": "openai",
        "model_version": "gpt-4o",
        "temperature": 0.7,
        "defaultValue": {
            "agent_tone": "Sos una asesora experta en danza clásica... usamos voseo argentino...",
            "synonym_dictionary": "mallas: Leotardos\ncancanes: Medias...",
            "business_rules": "1. Prioridad: Venta asistida...\n2. Fitting: Ofrecer siempre para puntas...",
            "catalog_knowledge": "Categorías: Zapatillas, Medias, Leotardos, Accesorios.",
            "store_website": "https://pointecoach.com"
        }
    }
}
```

---

## 3. Dynamic Global Templates (v7.2+)

Nexus ahora soporta **Templates Dinámicos** almacenados en la base de datos. Esto permite crear plantillas que aparecen automáticamente en el Wizard de todos los inquilinos.

### Lógica de Visibilidad
El endpoint `/admin/agent-templates` mezcla los templates hardcoded con los de la base de datos siguiendo esta lógica:
-   `is_template = TRUE`: El registro es tratado como una plantilla, no como un agente vivo.
-   `tenant_id IS NULL`: **Template Global**. Visible para todas las cuentas del sistema.
-   `tenant_id = X`: **Template Privado**. Visible solo para el inquilino X.

### Mapeo de Campos
El JSON en la columna `config` del template debe mapear a los campos expected del Wizard:
- `store_description` -> Descripción en el Wizard.
- `agent_tone` -> Tono y Personalidad.
- `business_rules` -> Reglas de Negocio.
- `synonym_dictionary` -> Diccionario de Sinónimos.

---

## 4. Instrucciones de Herramientas (Tool Config)

Cada herramienta tiene dos componentes de inyección de prompt definidos en `orchestrator_service/main.py`:

1.  **Táctica (`tactical_injections`)**: Instrucciones sobre el proceso de pensamiento y validación antes de llamar a la tool.
2.  **Guía de Respuesta (`response_guides`)**: Instrucciones sobre el formato y contenido de la salida (ej: Formato WhatsApp limpio, CTAs obligatorios).

### Distribución de Instrucciones
El sistema busca instrucciones en este orden de prioridad:
1.  **Personalización por Tienda**: Configurada en el modal "Configurar Herramientas" (`tenant.tool_config`).
2.  **Configuración de la Tool en DB**: Tabla `tools`, campos `prompt_injection` y `response_guide`.
3.  **Global Defaults**: Diccionarios `tactical_injections` y `response_guides` en `main.py`.

---

## 4. Inyección Dinámica y Variables Mágicas

El Orchestrator inyecta variables en el prompt antes de enviarlo al `agent_service`:

-   `{STORE_NAME}`: Nombre del comercio.
-   `{STORE_CATALOG_KNOWLEDGE}`: Descripción del catálogo (Wizard).
-   `{STORE_DESCRIPTION}`: Descripción del negocio.
-   `{store_website}`: URL del sitio (usado en guías de respuesta).

---

## 5. El Proceso de "Trasplante" de Templates

Cuando integres un agente de un proyecto legacy o una configuración compleja (como Pointe Coach), utilizá la técnica de **Distribución Multi-Capa**:

| Componente | Ubicación en Código | Propósito |
| :--- | :--- | :--- |
| **Identidad/Tono** | `agents.py` (Wizard) | Estilo de habla y personalidad. |
| **Reglas de Negocio** | `agents.py` (Wizard) | Políticas de venta, derivación y fitting. |
| **Diccionario** | `agents.py` (Wizard) | Mapeo de términos informales a categorías. |
| **Táctica de Tool** | `main.py` (Tactical) | Lógica de búsqueda y validación. |
| **Formato Respuesta** | `main.py` (Response) | Estructura visual de los mensajes (WhatsApp). |
| **Reglas de Calidez** | `templates.py` (Base) | Puntuación, prohibiciones críticas (anti-markdown). |

> [!TIP]
> Consultá la skill `Template_Transplant_Specialist` para ver el proceso paso a paso de extracción textual 1:1.

---

## 6. Checklist de Arquitecto

1.  **Wizard Alignment**: Asegurate de que los campos `agent_tone`, `business_rules` y `synonym_dictionary` del Wizard lleguen como `wizard_overrides` al `agent_service`.
2.  **Tool Parity**: Verificá que el modal "Configurar Herramientas" en el Frontend muestre los defaults del sistema si no hay customización.
3.  **Prompt Merge**: Verificá en `agent_service/main.py` que el prompt final sea la unión de: `template.build_system_prompt()` + `request.context.system_prompt` + `injected_content` (RAG y Tools).
4.  **Token Flow**: Confirmá que el `meta_user_long_token` se obtenga del Vault y se pase limpio al `agent_service` sin fallbacks legacy.

---

**Protocolo Omega**: En el 2026, los agentes se definen por su capacidad de seguir instrucciones tácticas precisas por herramienta. Menos "instrucciones generales" y más "guías de respuesta específicas".
