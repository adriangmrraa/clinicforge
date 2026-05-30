# Delta for Backend

## ADDED Requirements

### Requirement: Insurance matching SHALL use trigram similarity

The system SHALL add a trigram similarity step between exact match and ILIKE in all insurance matching functions.

The matching pipeline MUST follow this order:
1. Exact match: `LOWER(provider_name) = LOWER($input)`
2. Trigram similarity: `provider_name % $input` (uses `gin_trgm_ops` index)
3. Substring ILIKE: `provider_name ILIKE '%$input%'`
4. Not found

#### Scenario: ISSN matches Instituto de Seguridad Social

- GIVEN a tenant with `provider_name = "Instituto de Seguridad Social del Neuquén"` and `status = "external_derivation"`
- WHEN `check_insurance_coverage("ISSN")` is called
- THEN the trigram step matches the record (`similarity > 0.3` between "ISSN" and "Instituto de Seguridad Social del Neuquén")
- AND the function returns `{"status": "external_derivation", "provider_name": "Instituto de Seguridad Social del Neuquén"}`

#### Scenario: "Instituto" matches the same record

- GIVEN the same preconditions
- WHEN `_consultar_obra_social({"nombre": "Instituto"})` is called
- THEN trigram matches the record
- AND returns the correct derivation info

#### Scenario: Exact match still takes priority

- GIVEN a tenant with `provider_name = "OSDE"` and `status = "accepted"`
- WHEN `check_insurance_coverage("OSDE")` is called
- THEN the exact match step succeeds first (no trigram query needed)
- AND the function returns `{"status": "accepted", "provider_name": "OSDE"}`

#### Scenario: No match at all

- GIVEN a tenant with no matching insurance
- WHEN `check_insurance_coverage("NONEXISTENT_XYZ")` is called
- THEN exact match fails, trigram fails, ILIKE fails
- AND the function returns `{"status": "not_found"}`

#### Scenario: Multiple trigram matches ranked by similarity

- GIVEN a tenant with `provider_name IN ("OSDE 210", "OSDE 310", "Swiss Medical")`
- WHEN `check_insurance_coverage("OSDE")` is called
- THEN trigram returns both OSDE records ordered by similarity DESC
- AND the function returns the top match or multiple_matches based on count

## MODIFIED Requirements

### Requirement: Duplicate check on insurance create SHALL use trigram

The create-insurance duplicate check SHALL use the same trigram approach for consistency.

(Previously: used plain ILIKE without wildcards — effectively case-insensitive exact match)

#### Scenario: Creating "ISSN" when "Instituto de Seguridad Social" exists

- GIVEN a tenant with existing `provider_name = "Instituto de Seguridad Social del Neuquén"`
- WHEN POST `/admin/insurance-providers` with `provider_name = "ISSN"`
- THEN trigram returns similarity > 0.3
- AND the API returns 409 Conflict with "Ya existe una obra social con ese nombre"
