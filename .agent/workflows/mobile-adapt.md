---
description: "Workflow para adaptar páginas de Dentalogic a mobile de forma segura y estética."
---

# Workflow: /mobile-adapt (Nexus Standardization)

Este workflow guía al agente para transformar una vista de escritorio en una experiencia mobile premium sin afectar la versión Desktop.

## Pasos del Proceso

### 1. Auditoría de Breakpoints
- Abrir el archivo de la vista (ej: `AgendaView.tsx`).
- Identificar contenedores con clases fixed (`w-[...]px`) o grillas rígidas.
- Identificar componentes que requieren transformación a Drawers o Bottom Sheets.

### 2. Refactorización Responsiva
- **Root Container**: Asegurar `min-h-screen` y `overflow-x-hidden`.
- **Grillas**: Cambiar de `grid-cols-N` a `grid-cols-1 lg:grid-cols-N`.
- **Padding/Margin**: Ajustar espaciado lateral (ej: `p-4 lg:p-8`).

### 3. Optimización de Navegación
- Implementar Menú Hamburguesa si el Sidebar no es responsivo.
- Transformar tablas de datos en "Cards" apilables para mobile.

### 4. Verificación Non-Destructive
// turbo
- Comprobar que todos los cambios en mobile usen clases base y que los estilos originales de escritorio tengan el prefijo `lg:`.
- Simular vista mobile (375px) y desktop (1440px).

## Salida Esperada
- Un PR o commit con el sufijo `[Mobile Adapt]`.
- Resumen de cambios visuales específicos.
