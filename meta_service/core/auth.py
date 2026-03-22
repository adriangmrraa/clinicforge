import os
import httpx
import structlog
from fastapi import HTTPException

logger = structlog.get_logger()


class MetaAuthService:
    """
    Handles Meta Graph API for OAuth 2.0 Token Exchange and Asset Discovery.
    Facebook Login for Business: code exchange does NOT require redirect_uri.
    """

    def __init__(self):
        self.app_id = os.getenv("META_APP_ID")
        self.app_secret = os.getenv("META_APP_SECRET")
        self.api_version = os.getenv("META_GRAPH_API_VERSION", "v22.0")
        self.base_url = f"https://graph.facebook.com/{self.api_version}"

    async def exchange_code(self, code: str, redirect_uri: str = None) -> str:
        """
        Exchanges an Authorization Code for a long-lived Access Token.

        Strategy 1: Exchange WITHOUT redirect_uri (Facebook Login for Business with config_id).
        Strategy 2: Fallback WITH redirect_uri variants (standard OAuth).
        Strategy 3: Upgrade to long-lived token via fb_exchange_token.
        """
        url = f"{self.base_url}/oauth/access_token"

        async with httpx.AsyncClient(timeout=15.0) as client:
            # Strategy 1: Exchange WITHOUT redirect_uri
            logger.info("code_exchange_start", strategy="no_redirect_uri")
            resp = await client.get(url, params={
                "client_id": self.app_id,
                "client_secret": self.app_secret,
                "code": code
            })
            data = resp.json()

            if "error" in data:
                first_error = data["error"].get("message", "")
                logger.warning("exchange_without_redirect_failed", error=first_error)

                # Strategy 2: Try WITH redirect_uri variants
                if redirect_uri:
                    from urllib.parse import urlparse
                    parsed = urlparse(redirect_uri)
                    origin = f"{parsed.scheme}://{parsed.netloc}"
                    forced = os.getenv("META_REDIRECT_URI")

                    uris = []
                    if forced:
                        uris.append(forced)
                    uris.extend([redirect_uri, origin, origin + "/"])
                    uris = list(dict.fromkeys(uris))

                    for uri in uris:
                        resp2 = await client.get(url, params={
                            "client_id": self.app_id,
                            "client_secret": self.app_secret,
                            "redirect_uri": uri,
                            "code": code
                        })
                        data2 = resp2.json()
                        if "access_token" in data2:
                            logger.info("code_exchanged_with_redirect", uri=uri)
                            data = data2
                            break
                        else:
                            logger.warning("redirect_attempt_failed", uri=uri,
                                           error=data2.get("error", {}).get("message", ""))

            if "error" in data:
                error_msg = data["error"].get("message", "Unknown error")
                logger.error("code_exchange_failed", error=error_msg)
                raise HTTPException(status_code=400, detail=f"Meta token exchange failed: {error_msg}")

            token = data.get("access_token")
            if not token:
                raise HTTPException(status_code=400, detail="No access_token in Meta response")

            logger.info("token_obtained", token_type=data.get("token_type", "unknown"))

            # Strategy 3: Upgrade to long-lived token
            try:
                resp_ll = await client.get(url, params={
                    "grant_type": "fb_exchange_token",
                    "client_id": self.app_id,
                    "client_secret": self.app_secret,
                    "fb_exchange_token": token
                })
                ll_data = resp_ll.json()
                if "access_token" in ll_data:
                    expires_in = ll_data.get("expires_in")
                    logger.info("long_lived_token_obtained",
                                valid_days=round(expires_in / 86400) if expires_in else "unknown")
                    return ll_data["access_token"]
                else:
                    logger.info("token_already_long_lived_or_suat")
            except Exception as e:
                logger.warning("long_lived_exchange_skipped", error=str(e))

            return token

    async def get_accounts(self, access_token: str):
        """
        Fetches Pages, Instagram Business Accounts, and WhatsApp Business Accounts.
        Auto-subscribes pages to webhooks. Fetches WhatsApp phone numbers.
        """
        assets = {"pages": [], "instagram": [], "whatsapp": []}

        async with httpx.AsyncClient(timeout=15.0) as client:
            # 1. PAGES + INSTAGRAM
            try:
                resp = await client.get(f"{self.base_url}/me/accounts", params={
                    "access_token": access_token,
                    "fields": "id,name,access_token,instagram_business_account{id,username,profile_picture_url},tasks"
                })
                data = resp.json()

                if "error" in data:
                    logger.error("meta_pages_error", error=data["error"])
                    raise HTTPException(400, f"Meta API Error: {data['error'].get('message')}")

                for page in data.get("data", []):
                    tasks = page.get("tasks", [])
                    if not any(t in tasks for t in ["MANAGE", "MODERATE", "CREATE_CONTENT"]):
                        continue

                    page_token = page["access_token"]

                    try:
                        await self.subscribe_page(client, page["id"], page_token)
                    except Exception as sub_err:
                        logger.warning("page_auto_subscribe_failed", page_id=page["id"], error=str(sub_err))

                    assets["pages"].append({
                        "id": page["id"],
                        "name": page["name"],
                        "access_token": page_token
                    })

                    if "instagram_business_account" in page:
                        ig = page["instagram_business_account"]
                        assets["instagram"].append({
                            "id": ig["id"],
                            "username": ig.get("username"),
                            "profile_picture_url": ig.get("profile_picture_url"),
                            "linked_page_id": page["id"],
                            "access_token": page_token
                        })

            except httpx.ConnectError as e:
                logger.error("meta_connection_error_pages", error=str(e))
                raise HTTPException(503, "Could not connect to Meta API")

            # 2. WHATSAPP BUSINESS ACCOUNTS
            try:
                resp_waba = await client.get(f"{self.base_url}/me/whatsapp_business_accounts", params={
                    "access_token": access_token,
                    "fields": "id,name,currency,timezone_id,message_template_namespace"
                })
                data_waba = resp_waba.json()

                for waba in data_waba.get("data", []):
                    waba_id = waba["id"]
                    phone_numbers = []
                    try:
                        resp_phones = await client.get(f"{self.base_url}/{waba_id}/phone_numbers", params={
                            "access_token": access_token,
                            "fields": "id,display_phone_number,verified_name,quality_rating,code_verification_status"
                        })
                        for phone in resp_phones.json().get("data", []):
                            phone_numbers.append({
                                "id": phone["id"],
                                "display_phone_number": phone.get("display_phone_number"),
                                "verified_name": phone.get("verified_name"),
                                "quality_rating": phone.get("quality_rating"),
                                "status": phone.get("code_verification_status")
                            })
                    except Exception as ph_err:
                        logger.warning("waba_phone_fetch_failed", waba_id=waba_id, error=str(ph_err))

                    assets["whatsapp"].append({
                        "id": waba_id,
                        "name": waba["name"],
                        "currency": waba.get("currency"),
                        "timezone_id": waba.get("timezone_id"),
                        "namespace": waba.get("message_template_namespace"),
                        "phone_numbers": phone_numbers,
                        "access_token": access_token
                    })

            except Exception as e:
                logger.warning("waba_fetch_failed", error=str(e))

            logger.info("assets_discovered",
                        pages=len(assets["pages"]),
                        instagram=len(assets["instagram"]),
                        whatsapp=len(assets["whatsapp"]))
            return assets

    async def subscribe_page(self, client: httpx.AsyncClient, page_id: str, page_token: str):
        """Subscribes app to page messaging webhook events."""
        url = f"{self.base_url}/{page_id}/subscribed_apps"
        params = {
            "access_token": page_token,
            "subscribed_fields": "messages,messaging_postbacks,message_reads,message_deliveries"
        }
        try:
            resp = await client.post(url, params=params)
            data = resp.json()
            if resp.status_code == 200 and data.get("success"):
                logger.info("webhook_subscribed", page_id=page_id)
            else:
                logger.warning("webhook_subscribe_failed", page_id=page_id, response=data)
        except Exception as e:
            logger.error("webhook_subscribe_error", page_id=page_id, error=str(e))
