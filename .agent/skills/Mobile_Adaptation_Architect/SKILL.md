---
name: "Mobile_Adaptation_Architect"
description: "v8.0: Senior UI/UX Architect. Especialista en Blueprint Universal, DKG y Scroll Isolation."
trigger: "v8.0, mobile, responsive, isolation, DKG, adaptive"
scope: "FRONTEND"
auto-invoke: true
---

# 📱 Mobile Adaptation Architect - Nexus v7.6

## 1. Concepto: Blueprint Universal & AI-Aware Design

### Filosofía de Interpretación Clínica
Antes de proponer o replicar un diseño, se debe identificar el **'Dato Clave de Gestión' (DKG)** del contexto:
- **Profesionales**: Horarios de actividad (Sincronización IA).
- **Pacientes**: Alertas médicas y antecedentes (Seguridad Clínica).
- **Agenda**: Huecos JIT (Prevención de Colisiones).

**Regla de Oro**: El DKG siempre tiene prioridad visual y debe estar vinculado directamente a una Tool de IA o a un estado de base de datos.

## 2. Patrones de Diseño Nexus Mobile v2.0

### A. Gestión de Densidad (Stacking Pattern)
Si una vista tiene >5 campos de información, se debe forzar el patrón de "Lista de Atributos" en Mobile:
- Label arriba (texto mini, font-black) + Valor abajo (texto normal).
- Uso intensivo de iconos para ahorrar espacio.
- Componentización: Usar Accordions o Tabs colapsables para datos secundarios, manteniendo el DKG fijo/visible en la cabecera.

### B. Arquitectura de Scroll (Overflow Isolation)
Protocolo obligatorio basado en `01_architecture.md`:
- **Layout Global**: `h-screen` y `overflow-hidden` (prohibido el scroll del body).
- **Vista Maestra**: `h-full overflow-y-auto` para gestionar desplazamientos internos de forma independiente.

### C. Modales Estratégicos
- **Ancho Adaptativo**: `w-full` en mobile, `max-w-2xl` a `max-w-5xl` en desktop según densidad.
- **Sticky Actions**: Botones de Guardar/Cerrar siempre en `sticky bottom-0 bg-white border-t` en mobile.
- **Touch Target**: Mínimo de 44x44px para todo elemento interactivo (selectores, inputs, botones).

### D. Vista Estratégica (CEO Toggle)
Integrar la capacidad de transformar la vista operativa en un dashboard analítico:
- Toggle superior para cambiar entre "Vista Operativa" y "Vista Estratégica" (KPIs, Gráficos, Chips de filtrado).
- Reutilizar los datos de la vista para alimentar métricas de rendimiento (ej: % de ausentismo, rentabilidad por profesional).

## 3. Protocolo de Ejecución para el Agente

1. **Analizar el Contexto**: Identificar el DKG (Dato Clave de Gestión).
2. **Aplicar Scroll Isolation**: Asegurar que los contenedores `div` tengan las clases correctas.
3. **Refactorizar Modales**: Asegurar botones sticky y targets de 44px.
4. **Sincronizar con IA**: Los campos de disponibilidad o criterios médicos deben alimentar los parámetros de las Tools de IA correspondientes.

---
*Nexus v8.0 - Senior UI/UX Architecture & AI Pattern Specialist Protocol*
