---
name: Maintenance Robot Architect
description: Especialista en la actualización del sistema de auto-migración "Maintenance Robot" en orchestrator_service/db.py.
---

# Maintenance Robot Architect

Este Skill instruye al agente sobre cómo modificar, extender y mantener el sistema de inicialización y evolución de base de datos automatizado, conocido como "Maintenance Robot". Dicho sistema reside en `orchestrator_service/db.py`.

## Propósito

Asegurar que **CADA NUEVO DESPLIEGUE** en un entorno limpio nazca funcional y que las **BASES EXISTENTES** se actualicen sin intervención humana:
1.  **Foundation**: Creación de tablas base si no existen.
2.  **Evolution**: Aplicación de parches quirúrgicos para nuevas features.
3.  **Idempotencia**: Garantizar que el servicio pueda reiniciar infinitas veces sin errores.

## Reglas de Oro (Protocolo Omega)

1.  **Idempotencia Absoluta**:
    *   Toda alteración de columna o tabla debe usar bloques `DO $$ ... END $$` con cláusulas `IF NOT EXISTS` sobre `information_schema`.
    *   NUNCA uses `ALTER TABLE` directo sin verificación previa en el parche.

2.  **Ubicación de la Lógica**:
    *   La evolución vive en el método `_run_evolution_pipeline` de `db.py`.
    *   Los parches se agregan como strings SQL a la lista `patches`.

3.  **No Modificar Patches Antiguos**:
    *   Los parches son históricos. Agrega siempre al final de la lista.
    *   Solo se modifican si rompen el arranque por error de sintaxis grave.

4.  **Smart SQL Splitting**:
    *   El motor en `db.py` ya maneja el split por `;` respetando bloques `$$`. 
    *   Asegúrate de que cada parche termine en `;` y use `$$` para envolver bloques anónimos.

## Guía de Implementación

### 1. Agregar una nueva columna/feature
Cuando el código requiera un cambio en la BD, añade un parche a la lista en `db.py`:

```python
    # Parche N: [Descripción]
    """
    DO $$ 
    BEGIN 
        IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='appointments' AND column_name='ai_notes') THEN
            ALTER TABLE appointments ADD COLUMN ai_notes TEXT;
        END IF;
    END $$;
    """
```

### 2. Sincronización del Foundation
Si el cambio es permanente para nuevos usuarios, actualiza también `db/init/dentalogic_schema.sql` y corre `./sync-schema.ps1` para que las nuevas instalaciones tengan la estructura final desde el inicio.

## Casos de Uso
- **Nuevas Tablas**: Usar `CREATE TABLE IF NOT EXISTS`.
- **Nuevos Índices**: Usar `CREATE INDEX IF NOT EXISTS`.
- **Nuevas Columnas**: Usar el bloque `DO` con el `ALTER TABLE` interno.
- **Seeds de Configuración**: Usar `INSERT ... ON CONFLICT DO NOTHING`.
