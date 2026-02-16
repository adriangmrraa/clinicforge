"""
Spec 12: Health Check de Meta Ads Integration.
Verifica que el META_ADS_TOKEN sea válido y que la cuenta de ads esté activa.

Uso CLI:
    python -m scripts.check_meta_health

Uso como módulo (para endpoint):
    from scripts.check_meta_health import check_meta_health
    result = await check_meta_health()

CLINICASV1.0 - Integración Meta Ads & Dentalogic.
"""
import os
import sys
import asyncio
import logging
from typing import Dict, Any

import httpx

logger = logging.getLogger(__name__)

GRAPH_API_VERSION = os.getenv("META_GRAPH_API_VERSION", "v21.0")
GRAPH_API_BASE = f"https://graph.facebook.com/{GRAPH_API_VERSION}"
REQUEST_TIMEOUT = float(os.getenv("META_API_TIMEOUT", "10.0"))


async def check_meta_health() -> Dict[str, Any]:
    """
    Ejecuta health check contra la Meta Graph API.
    
    Returns:
        Dict con:
            - status: "ok" | "error"
            - message: Descripción legible
            - accounts: Lista de cuentas (si status=ok)
            - error_code: Código de error HTTP (si aplica)
    """
    token = os.getenv("META_ADS_TOKEN", "").strip()

    if not token:
        return {
            "status": "error",
            "message": "META_ADS_TOKEN no configurado.",
            "error_code": "NO_TOKEN",
        }

    url = f"{GRAPH_API_BASE}/me/adaccounts"
    params = {
        "fields": "name,account_status,currency",
        "access_token": token,
    }

    try:
        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
            response = await client.get(url, params=params)

        if response.status_code == 401:
            return {
                "status": "error",
                "message": "Token de Meta inválido o expirado (401).",
                "error_code": "AUTH_FAILED",
            }

        if response.status_code == 403:
            return {
                "status": "error",
                "message": "Permisos insuficientes para acceder a cuentas de anuncios (403).",
                "error_code": "FORBIDDEN",
            }

        if response.status_code != 200:
            data = response.json() if "application/json" in response.headers.get("content-type", "") else {}
            error_msg = data.get("error", {}).get("message", response.text[:200])
            return {
                "status": "error",
                "message": f"Error inesperado ({response.status_code}): {error_msg}",
                "error_code": f"HTTP_{response.status_code}",
            }

        data = response.json()
        accounts = data.get("data", [])

        if not accounts:
            return {
                "status": "error",
                "message": "Token válido pero sin cuentas de anuncios asociadas.",
                "error_code": "NO_ACCOUNTS",
            }

        # Parsear cuentas
        account_list = []
        active_count = 0
        for acc in accounts:
            # account_status: 1=ACTIVE, 2=DISABLED, 3=UNSETTLED, 7=PENDING_RISK_REVIEW
            status_code = acc.get("account_status", 0)
            is_active = status_code == 1
            if is_active:
                active_count += 1
            account_list.append({
                "id": acc.get("id", ""),
                "name": acc.get("name", ""),
                "currency": acc.get("currency", ""),
                "active": is_active,
                "status_code": status_code,
            })

        if active_count == 0:
            return {
                "status": "error",
                "message": f"Se encontraron {len(account_list)} cuenta(s) pero ninguna activa.",
                "error_code": "NO_ACTIVE_ACCOUNTS",
                "accounts": account_list,
            }

        return {
            "status": "ok",
            "message": f"Meta Integration: OK — {active_count}/{len(account_list)} cuenta(s) activa(s).",
            "accounts": account_list,
        }

    except httpx.TimeoutException:
        return {
            "status": "error",
            "message": f"Timeout contactando Meta Graph API ({REQUEST_TIMEOUT}s).",
            "error_code": "TIMEOUT",
        }
    except Exception as e:
        logger.error(f"❌ Error inesperado en Meta health check: {e}")
        return {
            "status": "error",
            "message": f"Error inesperado: {str(e)}",
            "error_code": "UNEXPECTED",
        }


# ─── CLI Entry Point ───────────────────────────────────────────
def main():
    """Punto de entrada para ejecución CLI."""
    result = asyncio.run(check_meta_health())

    if result["status"] == "ok":
        print(f"✅ {result['message']}")
        for acc in result.get("accounts", []):
            status = "✅ ACTIVE" if acc["active"] else "❌ INACTIVE"
            print(f"   {acc['name']} ({acc['id']}) — {status}")
        sys.exit(0)
    else:
        print(f"❌ {result['message']}")
        sys.exit(1)


if __name__ == "__main__":
    main()
