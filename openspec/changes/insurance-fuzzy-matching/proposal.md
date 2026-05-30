# Proposal: Insurance Fuzzy Matching (pg_trgm)

## Intent

DLD-87 — Pacientes del ISSN/Instituto/Neuquén no son reconocidos por el agente y se pierden antes de llegar al flujo correcto. El matching actual (exact match → ILIKE) falla cuando el paciente dice "ISSN" y la DB tiene "Instituto de Seguridad Social del Neuquén", o viceversa.

## Scope

### In Scope
- Agregar paso de trigram similarity (`%` operator + `similarity()`) en las 3 funciones de matching de obra social
- Crear índice GIN trigram en `tenant_insurance_providers.provider_name` (nueva migration Alembic)
- Mantener orden de precedencia: exact → trigram → ILIKE → not_found
- Sin cambios en DB schema, sin cambios en UI, sin migración de schema

### Out of Scope
- No se agrega columna `synonyms` a la DB
- No se modifica el frontend
- No se tocan las prompts del agente
- DLD-85 (colisión día/opción) queda para otro change

## Approach

pg_trgm ya está habilitado en producción vía `start.sh` y migration `055`. Solo falta:

1. **Migration 061**: `CREATE INDEX IF NOT EXISTS idx_insurance_provider_name_trgm ON tenant_insurance_providers USING gin(provider_name gin_trgm_ops)`
2. **Modificar `check_insurance_coverage`** (main.py ~7656): agregar paso trigram entre exact e ILIKE
3. **Modificar `_consultar_obra_social`** (nova_tools.py ~9278): mismo cambio
4. **Modificar create/update duplicate check** (admin_routes.py ~9618): mismo criterio

Pipeline de matching final:
```
input → LOWER(provider_name) = LOWER(input)  → match
      → provider_name % input                  → match (trigram, >0.3 threshold)
      → provider_name ILIKE '%input%'          → match
      → not_found
```

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `orchestrator_service/main.py` | Modified | `check_insurance_coverage` — agregar paso trigram |
| `orchestrator_service/services/nova_tools.py` | Modified | `_consultar_obra_social` — agregar paso trigram |
| `orchestrator_service/admin_routes.py` | Modified | Duplicate check en create/update — usar trigram |
| `orchestrator_service/alembic/versions/` | New | Migration `061_insurance_provider_trigram_index.py` |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Trigram threshold muy bajo (default 0.3) cause falsos positivos | Low | El pipeline mantiene exact match primero, trigram es paso 2 intermedio |
| Performance sin índice en DB grande | Low | El índice GIN se crea en migration, `%` operator usa el índice |
| pg_trgm no disponible en algún entorno | Low | `start.sh` ya lo instala + migration 055 ya lo requiere |

## Rollback Plan

- Migration: `alembic downgrade -1` elimina el índice
- Código: revertir las 3 funciones a su estado original (git revert)

## Dependencies

- pg_trgm ya habilitado (no requiere nueva instalación)

## Success Criteria

- [ ] "ISSN" matchea "Instituto de Seguridad Social del Neuquén"
- [ ] "Instituto" matchea el mismo registro
- [ ] "I.S.S.N." matchea el mismo registro
- [ ] "OSDE 210" matchea "Osde 210" (existing behavior intacto)
- [ ] Exact match sigue funcionando primero (no hay regression)
- [ ] ILIKE sigue funcionando como fallback final
