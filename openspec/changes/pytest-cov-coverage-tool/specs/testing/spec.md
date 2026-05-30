# Testing Coverage Specification

## Purpose

Define requirements for test coverage measurement using pytest-cov, including local development and CI integration.

## Requirements

### Requirement: Coverage Tool Integration

The system **MUST** integrate `pytest-cov` as the coverage measurement tool for Python tests.

#### Scenario: Running pytest with coverage locally

- GIVEN `pytest-cov` is installed in the virtual environment
- WHEN the developer runs `pytest --cov`
- THEN coverage measurement is executed
- AND a summary report is printed to the terminal
- AND an HTML report is generated in the `htmlcov/` directory

#### Scenario: No tests produce zero coverage

- GIVEN there are no test files
- WHEN `pytest --cov` is executed
- THEN coverage measurement runs
- AND reports 0% coverage
- AND no errors occur

### Requirement: Configuration in pytest.ini

The system **MUST** store coverage configuration in `pytest.ini` to avoid manual command‑line flags.

#### Scenario: Default coverage behavior

- GIVEN `pytest.ini` contains `addopts = --cov`
- WHEN the developer runs `pytest` without extra arguments
- THEN coverage measurement is automatically enabled
- AND the output includes coverage summary

### Requirement: Coverage Source Paths

The coverage tool **MUST** measure all Python source code in the project, including all service directories.

#### Scenario: Coverage includes all services

- GIVEN source code exists in `orchestrator_service/`, `whatsapp_service/`, `bff_service/`, and `meta_service/`
- WHEN `pytest --cov` runs
- THEN coverage is measured for each of those directories
- AND the report shows separate coverage per module

### Requirement: Dependencies Management

The `pytest‑cov` package **SHALL** be added to `requirements.txt` (or `requirements-dev.txt`) as a development dependency.

#### Scenario: Installation via requirements

- GIVEN `requirements.txt` includes `pytest-cov`
- WHEN the developer runs `pip install -r requirements.txt`
- THEN `pytest‑cov` is installed and available

### Requirement: CI Integration

The CI workflow **MUST** run coverage measurement and generate a coverage report artifact.

#### Scenario: GitHub Actions runs coverage

- GIVEN a GitHub Actions workflow runs the test suite
- WHEN the workflow executes `pytest --cov`
- THEN coverage data is collected
- AND a coverage report artifact (e.g., `htmlcov/`) is uploaded as a workflow artifact
- AND the workflow summary includes coverage percentage

#### Scenario: Coverage threshold (optional)

- GIVEN a minimum coverage threshold is configured (e.g., `--cov-fail-under=80`)
- WHEN coverage falls below the threshold
- THEN the CI run fails with a descriptive error

### Requirement: Report Accessibility

The coverage report **SHOULD** be easily accessible for review, both locally and from CI.

#### Scenario: Local HTML report

- GIVEN `pytest --cov` has been run
- WHEN the developer opens `htmlcov/index.html` in a browser
- THEN a detailed, navigable coverage report is displayed

#### Scenario: CI artifact download

- GIVEN a CI run has completed
- WHEN a developer downloads the `coverage‑report` artifact
- THEN they can view the same HTML report as generated locally