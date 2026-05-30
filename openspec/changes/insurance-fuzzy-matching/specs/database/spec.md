# Delta for Database

## ADDED Requirements

### Requirement: Migration SHALL create GIN trigram index on provider_name

A new Alembic migration SHALL create a GIN trigram index on `tenant_insurance_providers.provider_name` to enable performant trigram similarity queries.

#### Scenario: Migration runs successfully

- GIVEN the migration `061_insurance_provider_trigram_index.py`
- WHEN `alembic upgrade head` executes
- THEN an index `idx_insurance_provider_name_trgm` is created using `gin(provider_name gin_trgm_ops)` on `tenant_insurance_providers`
- AND no errors occur (pg_trgm extension already exists)

#### Scenario: Index is used in query plan

- GIVEN the GIN trigram index exists
- WHEN a trigram similarity query runs: `SELECT ... WHERE provider_name % $input AND tenant_id = $1`
- THEN the query planner uses bitmap index scan on `idx_insurance_provider_name_trgm`

### Requirement: Migration SHALL be reversible

The migration MUST support downgrade by dropping the GIN index.

#### Scenario: Rollback

- GIVEN the index exists
- WHEN `alembic downgrade -1` executes
- THEN the index `idx_insurance_provider_name_trgm` is dropped
- AND the table schema is unchanged
