---
description: Actualiza documentación y skills usando el protocolo Non-Destructive Fusion
---

# Workflow: Actualizar Documentación

Este workflow implementa el protocolo **Non-Destructive Fusion** de la skill Smart Doc Keeper para actualizar documentación y skills sin perder contenido previo.

## Cuándo usar este workflow

- Después de implementar nuevas features que requieren documentación
- Cuando se detectan inconsistencias entre código y docs
- Al agregar nuevas skills o actualizar existentes
- Para sincronizar cambios arquitectónicos con la documentación

## Pasos del Workflow

### 1. Identificar documentos a actualizar

Determina qué archivos necesitan actualización:

```bash
# Documentación principal
docs/API_REFERENCE.md
docs/INTEGRATIONS_LOGIC_DEEP_DIVE.md
docs/TROUBLESHOOTING.md
docs/YCLOUD_INTEGRATION.md

# Skills
.agent/skills/[nombre_skill]/SKILL.md

# Configuración de agentes
.agent/agents.md
```

### 2. Leer el contenido actual

**CRÍTICO**: Siempre lee el contenido completo del archivo antes de actualizar.

```
// Usa view_file para leer el contenido actual
// Identifica las secciones que necesitan actualización
// Preserva todo el contenido que NO necesita cambios
```

### 3. Aplicar protocolo Non-Destructive Fusion

**Reglas obligatorias**:

1. ✅ **NUNCA elimines secciones existentes** sin confirmación explícita del usuario
2. ✅ **Preserva el formato markdown** y la estructura de encabezados
3. ✅ **Agrega nuevas secciones** al final de bloques relacionados
4. ✅ **Actualiza contenido obsoleto** manteniendo el contexto histórico cuando sea relevante
5. ✅ **Mantén los ejemplos de código** existentes a menos que estén rotos

**Técnicas de fusión**:

- **Agregar**: Inserta nuevas secciones sin tocar las existentes
- **Expandir**: Agrega información a secciones existentes preservando el contenido original
- **Corregir**: Actualiza información incorrecta manteniendo el formato
- **Deprecar**: Marca contenido obsoleto con `> [!WARNING] DEPRECATED` en lugar de eliminarlo

### 4. Actualizar Skills (SKILL.md)

Para actualizar skills, sigue la estructura YAML frontmatter:

```markdown
---
name: Nombre de la Skill
description: Descripción breve de la skill
---

# [Nombre de la Skill]

## Propósito
[Descripción detallada]

## Cuándo usar esta skill
[Lista de casos de uso]

## Protocolo de ejecución
[Pasos específicos]

## Ejemplos
[Casos de uso concretos]

## Reglas críticas
[Restricciones y mejores prácticas]
```

### 5. Sincronizar con AGENTS.md

Después de actualizar skills, ejecuta:

```bash
python .agent/skills/Skill_Sync/sync_skills.py
```

Esto actualiza automáticamente `.agent/agents.md` con los metadatos de todas las skills.

### 6. Verificar cambios

**Checklist de verificación**:

- [ ] El archivo actualizado compila/renderiza correctamente
- [ ] No se eliminó contenido importante sin intención
- [ ] Los links internos siguen funcionando
- [ ] Los ejemplos de código son válidos
- [ ] El formato markdown es consistente
- [ ] Las secciones están en orden lógico

### 7. Documentar cambios en commit

Usa mensajes de commit descriptivos:

```bash
git add docs/[archivo].md
git commit -m "docs: actualizar [archivo] con [cambio específico]"
```

## Ejemplos de uso

### Ejemplo 1: Agregar nueva integración a INTEGRATIONS_LOGIC_DEEP_DIVE.md

```markdown
// 1. Lee el archivo completo
// 2. Identifica la sección de integraciones
// 3. Agrega nueva sección al final:

## Nueva Integración: [Nombre]

### Arquitectura
[Descripción]

### Endpoints
[Lista de endpoints]

### Flujo de datos
[Diagrama o descripción]
```

### Ejemplo 2: Actualizar skill existente

```markdown
// 1. Lee SKILL.md actual
// 2. Identifica sección a actualizar (ej: "Protocolo de ejecución")
// 3. Expande la sección agregando nuevos pasos:

## Protocolo de ejecución

[Contenido existente preservado]

### Nuevos pasos (v2.0)
4. [Nuevo paso]
5. [Nuevo paso]
```

### Ejemplo 3: Deprecar contenido obsoleto

```markdown
> [!WARNING]
> **DEPRECATED (2026-01-27)**: Esta sección describe el método legacy.
> Ver [Nueva Sección](#nueva-seccion) para el enfoque actual.

[Contenido obsoleto preservado para referencia histórica]
```

## Protocolo de emergencia

Si accidentalmente eliminas contenido:

1. **NO hagas commit** inmediatamente
2. Usa `git diff` para ver qué se eliminó
3. Restaura el contenido desde el historial de Git
4. Aplica los cambios correctamente usando Non-Destructive Fusion

## Mejores prácticas

1. **Siempre lee antes de escribir**: Nunca actualices un archivo sin leerlo primero
2. **Commits atómicos**: Un archivo por commit cuando sea posible
3. **Mensajes descriptivos**: Explica QUÉ cambió y POR QUÉ
4. **Preserva el contexto**: La documentación es historia, no solo estado actual
5. **Valida links**: Asegúrate de que los links internos funcionen después de cambios

## Archivos críticos que requieren cuidado especial

- `docs/API_REFERENCE.md` - Contratos de API, cambios pueden romper integraciones
- `.agent/agents.md` - Auto-generado, no editar manualmente
- `docs/TROUBLESHOOTING.md` - Soluciones históricas son valiosas
- `.agent/skills/*/SKILL.md` - Estructura YAML estricta

## Recursos

- Skill: `.agent/skills/Doc_Keeper/SKILL.md`
- Sync script: `.agent/skills/Skill_Sync/sync_skills.py`
- Convenciones de commits: `docs/CONTRIBUTING.md` (si existe)
