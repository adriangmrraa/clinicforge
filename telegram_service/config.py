"""
config.py — Environment configuration for telegram_service.
"""
import os

ORCHESTRATOR_URL = os.getenv("ORCHESTRATOR_URL", "http://orchestrator_service:8000")
ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "")
TELEGRAM_SERVICE_PORT = int(os.getenv("TELEGRAM_SERVICE_PORT", "8003"))

# Frontend URL for building webhook URLs
FRONTEND_URL = os.getenv("FRONTEND_URL", "")
# Override for webhook base URL (if different from FRONTEND_URL)
TELEGRAM_WEBHOOK_BASE_URL = os.getenv("TELEGRAM_WEBHOOK_BASE_URL", "")

def get_webhook_base_url() -> str:
    """Get the base URL for Telegram webhooks."""
    return TELEGRAM_WEBHOOK_BASE_URL or ORCHESTRATOR_URL
