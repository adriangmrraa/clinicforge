"""AI Engine Health Check endpoint.

GET /admin/ai-engine/health

Returns the health status of both engines (solo and multi).
Used by the frontend before allowing a switch between engines.

See: openspec/changes/engine-mode-toggle-and-multi-agent/spec.md §7
"""

import asyncio
import logging
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from services.engine_router import SoloEngine, MultiAgentEngine

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin/ai-engine", tags=["ai-engine"])


class HealthResponse(BaseModel):
    """Response model for health check."""

    solo: dict
    multi: dict


@router.get("/health", response_model=HealthResponse)
async def get_ai_engine_health():
    """Check health of both AI engines.

    Runs parallel probes for both SoloEngine and MultiAgentEngine.
    Returns status and latency for each engine.
    """
    solo_probe = SoloEngine()
    multi_probe = MultiAgentEngine()

    # Run probes in parallel with timeouts
    try:
        solo_result, multi_result = await asyncio.wait_for(
            asyncio.gather(
                solo_probe.probe(),
                multi_probe.probe(),
                return_exceptions=True,
            ),
            timeout=20.0,  # Total timeout for both probes
        )

        # Handle exceptions from gather
        if isinstance(solo_result, Exception):
            solo_result = type(
                "ProbeResult",
                (),
                {
                    "ok": False,
                    "latency_ms": 0,
                    "error": str(solo_result),
                    "detail": f"Probe failed: {type(solo_result).__name__}",
                },
            )()

        if isinstance(multi_result, Exception):
            multi_result = type(
                "ProbeResult",
                (),
                {
                    "ok": False,
                    "latency_ms": 0,
                    "error": str(multi_result),
                    "detail": f"Probe failed: {type(multi_result).__name__}",
                },
            )()

    except asyncio.TimeoutError:
        # Both probes timed out
        solo_result = type(
            "ProbeResult",
            (),
            {
                "ok": False,
                "latency_ms": 20000,
                "error": "Timeout",
                "detail": "Health check timed out after 20s",
            },
        )()
        multi_result = type(
            "ProbeResult",
            (),
            {
                "ok": False,
                "latency_ms": 20000,
                "error": "Timeout",
                "detail": "Health check timed out after 20s",
            },
        )()

    # Format response
    def format_probe(result):
        return {
            "ok": result.ok,
            "latency_ms": result.latency_ms,
            **({"detail": result.detail} if hasattr(result, "detail") else {}),
            **(
                {"error": result.error}
                if hasattr(result, "error") and result.error
                else {}
            ),
        }

    return HealthResponse(
        solo=format_probe(solo_result),
        multi=format_probe(multi_result),
    )
