import os
import httpx
import structlog
from typing import Dict, Any

logger = structlog.get_logger()


class OrchestratorClient:
    """
    Client for communicating with the internal Orchestrator service.
    Handles authentication via Internal Secret.
    """

    def __init__(self):
        self.base_url = os.getenv("ORCHESTRATOR_URL", "http://orchestrator_service:8000")
        self.internal_secret = os.getenv("INTERNAL_SECRET_KEY", "internal-secret")
        self.headers = {
            "Content-Type": "application/json",
            "X-Internal-Secret": self.internal_secret
        }

    async def ingest_webhook_event(self, event_data: Dict[str, Any]):
        """Forwards a normalized webhook event to the Orchestrator."""
        url = f"{self.base_url}/admin/meta-direct/webhook"
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(url, json=event_data, headers=self.headers)
                resp.raise_for_status()
                logger.info("ingest_success", status=resp.status_code)
                return resp.json()
        except Exception as e:
            logger.error("ingest_failed", error=str(e), url=url)
            raise

    async def sync_credentials(self, credentials: Dict[str, Any]):
        """Syncs Meta credentials (access tokens) to the Orchestrator."""
        url = f"{self.base_url}/admin/credentials/internal-sync"
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(url, json=credentials, headers=self.headers)
                resp.raise_for_status()
                logger.info("credential_sync_success", status=resp.status_code)
                return resp.json()
        except Exception as e:
            logger.error("credential_sync_failed", error=str(e))
            raise
