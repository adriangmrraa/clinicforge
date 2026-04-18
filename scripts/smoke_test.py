"""Post-deploy smoke test. Exits 0 on success, 1 on any failure."""
import sys
import os
import httpx
import asyncio

BASE_URL = os.getenv("SMOKE_TEST_URL", "http://localhost:8000")
ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "")
TIMEOUT = int(os.getenv("SMOKE_TIMEOUT", "10"))


async def check(name, method, url, expected_status=200, **kwargs):
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            resp = await getattr(client, method)(url, **kwargs)
            if resp.status_code == expected_status:
                print(f"  PASS  {name} ({resp.status_code})")
                return True
            else:
                print(f"  FAIL  {name} — expected {expected_status}, got {resp.status_code}")
                return False
    except Exception as e:
        print(f"  FAIL  {name} — {e}")
        return False


async def main():
    print("ClinicForge Post-Deploy Smoke Test")
    print("=" * 40)

    headers = {"X-Admin-Token": ADMIN_TOKEN} if ADMIN_TOKEN else {}
    results = []

    # 1. Liveness
    results.append(await check("Health/Live", "get", f"{BASE_URL}/health/live"))

    # 2. Readiness (DB + Redis)
    results.append(await check("Health/Ready", "get", f"{BASE_URL}/health/ready"))

    # 3. AI Engine Health
    results.append(
        await check(
            "AI Engine Health",
            "get",
            f"{BASE_URL}/admin/ai-engine/health",
            headers=headers,
        )
    )

    # 4. Auth endpoint reachable
    results.append(
        await check(
            "Auth Login (reachable)",
            "post",
            f"{BASE_URL}/auth/login",
            expected_status=422,  # 422 = endpoint exists, just no body
            json={},
        )
    )

    print("=" * 40)
    passed = sum(results)
    total = len(results)
    print(f"Result: {passed}/{total} checks passed")

    sys.exit(0 if all(results) else 1)


if __name__ == "__main__":
    asyncio.run(main())
