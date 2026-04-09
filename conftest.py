# Root-level conftest — handles collection exclusions for cross-service tests.
# test_whatsapp.py belongs to whatsapp_service which has its own deps
# (prometheus_client) not installed in the orchestrator venv.
# Run it separately inside whatsapp_service/ with its own pytest config.
collect_ignore = [
    "tests/test_whatsapp.py",
]
