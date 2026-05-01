# Cloudflare CDN/WAF Setup Runbook — ClinicForge

**Estimated time:** 90 minutes
**Risk level:** Low (rollback is fast — toggle proxy off per DNS record; see Part 9 for timing details)
**Context:** Hostinger VPS running EasyPanel/Traefik. Ports 3000 (BFF) and 4173→80 (Frontend/Nginx) published to host. Orchestrator, DB, and Redis are on the internal Docker network and never exposed to the internet.

---

## Prerequisites

- [ ] Access to the domain registrar (to change nameservers)
- [ ] Free Cloudflare account at https://dash.cloudflare.com (free tier is sufficient)
- [ ] Know the VPS public IP (check EasyPanel or `curl ifconfig.me` on the VPS)
- [ ] Know your domain (e.g., `clinicforge.app`, `tudominio.com`)
- [ ] 15–60 min for DNS propagation after nameserver change

---

## Part 1 — Add Domain to Cloudflare

1. Log into https://dash.cloudflare.com → **Add a site**
2. Enter your domain → select **Free plan**
3. Cloudflare scans existing DNS records. Review the imported records — keep them.
4. Copy the two Cloudflare nameservers shown (e.g., `aria.ns.cloudflare.com`, `brad.ns.cloudflare.com`)
5. Go to your domain registrar → update nameservers to the Cloudflare ones
6. Click **Done** in Cloudflare — propagation takes 5–60 minutes

**Verify propagation:**
```bash
dig NS yourdomain.com +short
# Should return cloudflare nameservers
```

---

## Part 2 — DNS Records

### Before migration: verify MX records

**CRITICAL — run this BEFORE switching nameservers:**
```bash
dig MX yourdomain.com +short
# Record all existing MX records — you must re-create them in Cloudflare exactly
```

Create or confirm these records in **Cloudflare DNS** (Dashboard → DNS → Records).

| Type | Name | Content | Proxy status | TTL |
|------|------|---------|--------------|-----|
| A | `@` | `<VPS_IP>` | Proxied (orange cloud) | Auto |
| A | `www` | `<VPS_IP>` | Proxied (orange cloud) | Auto |
| A | `api` | `<VPS_IP>` | Proxied (orange cloud) | Auto |

> **Never put the real VPS IP in a DNS-only (grey cloud) record unless it is a record that MUST bypass Cloudflare (e.g., mail server MX)**. Proxied records hide the VPS IP behind Cloudflare's IPs — this is the core DDoS protection.

**MX records (MUST be grey cloud — DNS only):**

| Type | Name | Content | Proxy status |
|------|------|---------|--------------|
| MX | `@` | `mail.yourdomain.com` (or your mail provider) | DNS only (grey cloud) |

> MX records **must always be grey cloud (DNS-only)**. Proxying mail traffic through Cloudflare will break email delivery. Cloudflare does not proxy SMTP.

**Webhook subdomains** (if you use a dedicated webhook subdomain):

| Type | Name | Content | Proxy status | Notes |
|------|------|---------|--------------|-------|
| A | `hooks` | `<VPS_IP>` | Proxied | YCloud/Chatwoot webhooks if using a subdomain |

### After migration: verify MX records survived

```bash
dig MX yourdomain.com +short
# Must return the same MX records as before migration
# If empty or different — add/fix them in Cloudflare DNS immediately
```

---

## Part 3 — SSL/TLS Settings

**Dashboard → SSL/TLS → Overview**

Set mode to: **Full (strict)**

> Rationale: EasyPanel/Traefik already handles SSL termination with a valid Let's Encrypt cert on the VPS. "Full strict" means Cloudflare verifies the origin cert — no MITM between Cloudflare and the VPS.

### ACME / Let's Encrypt Certificate Renewal Behind Cloudflare

> **WARNING: HTTP-01 challenges fail behind Cloudflare proxy.** When Cloudflare proxies your domain, HTTP-01 challenge requests go to Cloudflare's edge, not to your VPS — so Let's Encrypt cannot verify ownership. You have two options:

**Option A (Recommended) — Cloudflare Origin Certificate (free, 15 years)**

Dashboard → SSL/TLS → Origin Server → Create Certificate

- Free Cloudflare cert valid for up to 15 years
- No renewal needed for the foreseeable future
- Works only for traffic going through Cloudflare (which is all of it once proxied)
- Install the generated cert + key in Traefik/EasyPanel instead of Let's Encrypt

**Option B — DNS-01 Challenge (keeps Let's Encrypt)**

Use Certbot with the Cloudflare DNS plugin:
```bash
pip install certbot-dns-cloudflare
certbot certonly \
  --dns-cloudflare \
  --dns-cloudflare-credentials ~/.secrets/cloudflare.ini \
  -d yourdomain.com -d '*.yourdomain.com'
```

DNS-01 validates through DNS TXT records, not HTTP — works fine behind the proxy. Requires a Cloudflare API token with `Zone:DNS:Edit` permission.

**Option C — Temporarily disable proxy during renewal**

Toggle the A record to grey cloud (DNS-only), run Certbot with HTTP-01, then re-enable orange cloud. Adds ~2 minutes of exposed VPS IP during renewal window. Automate with a pre/post hook in the Certbot systemd timer.

**Dashboard → SSL/TLS → Edge Certificates**

- [ ] Enable **Always Use HTTPS** (redirects HTTP→HTTPS at the edge)
- [ ] Enable **Automatic HTTPS Rewrites** (fixes mixed content warnings)
- [ ] Set **Minimum TLS Version** to `TLS 1.2`
- [ ] Enable **TLS 1.3**
- [ ] Enable **HSTS** — settings:
  - Max age: 6 months (15768000 seconds)
  - Include subdomains: **No** (start with No — only enable after confirming all subdomains have valid HTTPS)
  - Preload: No (leave off until setup is stable)

---

## Part 4 — WebSocket Configuration

ClinicForge has two WebSocket paths that must work through Cloudflare:

| Path | Service | Session length |
|------|---------|----------------|
| `/socket.io/*` | Socket.IO real-time events (appointments, chats) | Short polling + long-poll fallback |
| `/public/nova/*` | Nova voice assistant (OpenAI Realtime API bridge) | Up to 600 seconds |

**Cloudflare free tier supports WebSocket** — it is enabled by default for proxied records. No extra toggle needed.

### Critical: Nova session timeout

Cloudflare free tier has a **100-second WebSocket idle timeout**. Nova sessions can last up to 600 seconds. To keep connections alive:

**Option A — Cloudflare Network settings (Dashboard → Network)**
- Enable **WebSockets** (should already be on)

**Option B — Application-level keepalive (REQUIRED before enabling Cloudflare)**

> **CONFIRMED:** `NovaWidget.tsx` has **NO heartbeat** implemented. The `startVoice()` function's `ws.onopen` handler does not send any ping frames. This **will** cause Nova sessions to drop after 100 seconds of audio silence through Cloudflare. **This code change is REQUIRED before enabling Cloudflare.**

Add the following to `frontend_react/src/components/NovaWidget.tsx` inside `startVoice()`:

```typescript
// In startVoice(), after ws.onopen:
const heartbeat = setInterval(() => {
  if (wsRef.current?.readyState === WebSocket.OPEN) {
    wsRef.current.send(JSON.stringify({ type: 'ping' }));
  }
}, 30_000);
// Update ws.onclose: clearInterval(heartbeat); stopRealtimeAudio();
```

The Nginx config already sets `proxy_read_timeout 600s` and `proxy_send_timeout 600s` for `/api/public/nova/` — the missing piece is the client-side keepalive.

**Option C — Cloudflare Workers (only if needed)**

If idle timeouts remain an issue, a Cloudflare Worker can forward the WS connection without the 100s limit. This is overkill for free tier — implement Option B first.

### Socket.IO compatibility

Socket.IO uses long-polling as a fallback when WebSocket fails. Cloudflare proxied connections handle both. Ensure the BFF sets:

```
# BFF already sets trust proxy = 1 for EasyPanel/Traefik
# This also covers Cloudflare's X-Forwarded-For headers
app.set('trust proxy', 1);
```

This is already configured in `bff_service/src/index.ts:71`.

### WebSocket test

```bash
# Install wscat if not present
npm install -g wscat

# Test Nova WebSocket upgrade
wscat -c "wss://yourdomain.com/public/nova/realtime-ws/test?token=test"
# Expected: connection opened (then 401/403 error from server — that's correct, WS reached the server)

# Test Socket.IO (fallback polling)
curl -I "https://yourdomain.com/socket.io/?EIO=4&transport=polling"
# Expected: 200 with cf-ray header
```

---

## Part 5 — WAF Rules

**Dashboard → Security → WAF**

### Rule 1: Block bad bots and scanners

**Dashboard → Security → Bots**
- Enable **Bot Fight Mode** (free) — blocks known malicious bots automatically

### Rule 2: Rate limit the AI webhook endpoints

**Dashboard → Security → WAF → Rate limiting rules** → Create rule:

```
Rule name: Webhook rate limit
Expression: (http.request.uri.path contains "/admin/ycloud/webhook") or
            (http.request.uri.path contains "/admin/chatwoot/webhook") or
            (http.request.uri.path contains "/telegram/webhook/")
Action: Block
Rate: 300 requests per minute per IP
```

> YCloud/Chatwoot deliver WhatsApp messages in bursts when a conversation has high activity. 300/min accommodates these delivery bursts while still blocking abuse. The path `/telegram/webhook/` uses a trailing slash — ensure exact match.

### Rule 3: Protect admin endpoints

**Dashboard → Security → WAF → Custom rules** → Create rule:

```
Rule name: Block brute-force on /auth
Expression: (http.request.uri.path starts_with "/auth/login")
Action: Managed Challenge (CAPTCHA) after 10 requests per 1 minute per IP
```

> The BFF already has `authLimiter` (30/min), but Cloudflare's edge challenge stops attackers before they even reach the VPS.

### Rule 4: Managed ruleset with WAF exclusions for webhook/Nova paths

**Dashboard → Security → WAF → Managed rules**
- Enable **Cloudflare Managed Ruleset** (free tier includes basic rules)
- Sensitivity: **Medium**

**IMPORTANT — Skip managed rules for sensitive paths:**

Add WAF exceptions for the following paths to prevent false positives:

```
Skip expression:
  (http.request.uri.path contains "/admin/ycloud/webhook") or
  (http.request.uri.path contains "/admin/chatwoot/webhook") or
  (http.request.uri.path contains "/telegram/webhook/") or
  (http.request.uri.path contains "/public/nova/") or
  (http.request.uri.path contains "/public/anamnesis/")
```

> Patient symptom text sent via WhatsApp/Chatwoot webhooks frequently contains medical terminology (pain descriptions, drug names, anatomical terms) that trigger managed WAF rules as false positives. The `/public/nova/` WebSocket path also triggers binary-data rules. The app-level token validation on all webhook endpoints provides equivalent security.

### Rule 5: Geo-block (optional, if Argentina-only clinic)

**Dashboard → Security → WAF → Custom rules** → Create rule:

```
Rule name: Geo restrict (optional)
Expression: (not ip.geoip.country in {"AR" "UY" "CL" "ES"}) and
            (not http.request.uri.path contains "/health") and
            (not http.request.uri.path contains "/public/anamnesis")
Action: Managed Challenge
```

> Adjust country codes. Exclude `/health` and `/public/anamnesis` so external health checks and patient anamnesis links from abroad still work.

---

## Part 6 — VPS Firewall Lock (Restrict to Cloudflare IP Ranges)

Once Cloudflare is proxying all traffic, **lock the VPS firewall to accept 80/443 only from Cloudflare IP ranges**. This prevents attackers from bypassing Cloudflare by connecting to your VPS IP directly (discoverable via Shodan, SecurityTrails, or certificate transparency logs).

> **Note:** Tools like Shodan and SecurityTrails can reveal your VPS IP from historical DNS records or TLS certificate scans — even after you start proxying through Cloudflare. The firewall lock is essential to make the Cloudflare protection effective.

```bash
#!/bin/bash
# Script: lock-vps-to-cloudflare.sh
# Run on the VPS as root. Fetches current Cloudflare IP ranges and replaces
# the allow-rules for ports 80 and 443.

set -e

# Fetch current Cloudflare IPv4 ranges
CF_IPS=$(curl -s https://www.cloudflare.com/ips-v4)
CF_IPS6=$(curl -s https://www.cloudflare.com/ips-v6)

# Remove existing Cloudflare rules (idempotent re-run)
ufw delete allow 80/tcp 2>/dev/null || true
ufw delete allow 443/tcp 2>/dev/null || true

# Allow only from Cloudflare IPv4 ranges
for ip in $CF_IPS; do
  ufw allow from "$ip" to any port 80 proto tcp
  ufw allow from "$ip" to any port 443 proto tcp
done

# Allow only from Cloudflare IPv6 ranges
for ip6 in $CF_IPS6; do
  ufw allow from "$ip6" to any port 80 proto tcp
  ufw allow from "$ip6" to any port 443 proto tcp
done

# Keep SSH open (adjust port if non-standard)
ufw allow 22/tcp

ufw --force enable
echo "VPS firewall locked to Cloudflare IP ranges."
echo "Verify: ufw status numbered"
```

> **Run this script AFTER confirming Cloudflare proxy is working end-to-end.** If you run it before, you will lock yourself out of the web UI. Keep an SSH session open while testing.
>
> Cloudflare IP ranges update occasionally. Subscribe to https://www.cloudflare.com/ips/ change notifications, or schedule the script to re-run quarterly.

---

## Part 7 — Webhook Source Whitelisting

YCloud, Chatwoot, Telegram, and Meta all validate requests at the application level:
- **YCloud**: token in URL query param, validated by `resolve_tenant_from_webhook_token()`
- **Chatwoot**: same token mechanism
- **Telegram**: Telegram sends to a bot-specific URL; BFF proxies it internally
- **Meta**: `META_VERIFY_TOKEN` for webhook verification + request signature validation

Application-level validation is already in place. Cloudflare adds a network layer on top. If you want to whitelist known IPs at the Cloudflare level:

**Dashboard → Security → WAF → Custom rules** → Create rule:

```
Rule name: Allow known webhook sources
Expression: (ip.src in {66.241.124.0/24 66.241.125.0/24}) and  # YCloud ranges (verify at ycloud.com/docs)
            (http.request.uri.path contains "/webhook")
Action: Skip all WAF rules
```

> Check YCloud, Chatwoot, and Meta's current IP ranges in their documentation before hardcoding. These change. The app-level token validation is more reliable than IP whitelisting for webhooks — treat IP bypass as defense-in-depth, not the primary control.

**Meta webhook IPs** (as of 2026): Meta Graph API sends from `31.13.24.0/21` and `66.220.144.0/20` ranges. See: https://developers.facebook.com/docs/messenger-platform/webhook

**Telegram Bot API**: Telegram sends from `149.154.160.0/20` and `91.108.4.0/22`.

---

## Part 8 — Performance Settings

**Dashboard → Speed → Optimization**

- Enable **Auto Minify** for JS, CSS, HTML
- Enable **Brotli compression**
- **Rocket Loader**: Keep DISABLED — it breaks some React apps by deferring scripts

**Dashboard → Caching → Configuration**

- **Caching level**: Standard
- **Browser Cache TTL**: Respect Existing Headers (Nginx already sets 1y for static assets)
- **Always Online**: Enable (serves cached pages if VPS goes down briefly)

---

## Part 9 — Verification Checklist

Run these after DNS has propagated (verify with `dig A yourdomain.com` — should return Cloudflare IPs, not your VPS IP).

### HTTP/HTTPS

```bash
# 1. Confirm traffic is going through Cloudflare (cf-ray header must be present)
curl -I https://yourdomain.com
# Expected: HTTP/2 200 + cf-ray: <id>-<datacenter>

# 2. HTTP redirects to HTTPS
curl -I http://yourdomain.com
# Expected: 301 → https://yourdomain.com

# 3. BFF health check through the proxy
curl -I https://yourdomain.com/health
# Expected: 200 with cf-ray header

# 4. Auth endpoint reachable
curl -s -o /dev/null -w "%{http_code}" https://yourdomain.com/auth/clinics
# Expected: 200

# 5. Admin endpoint correctly blocked without token
curl -I https://yourdomain.com/admin/patients
# Expected: 401 or 403 (not 502 or 000)
```

### WebSocket

```bash
# Install wscat if not present
npm install -g wscat

# Test Nova WebSocket (replace with a valid session token for a real test)
wscat -c "wss://yourdomain.com/public/nova/realtime-ws/test?token=test"
# Expected: connection opened (server-side 401/403 is fine — WS upgrade succeeded)

# From browser DevTools:
# Open ClinicForge, check Network → WS → Frames
# Should see Socket.IO handshake completing
```

### Security headers

```bash
curl -I https://yourdomain.com | grep -E "x-frame|x-content|strict-transport|cf-ray"
# Expected: x-frame-options, x-content-type-options, strict-transport-security, cf-ray all present
```

### Webhook reachability (test from your phone or a different network)

```bash
# Public anamnesis form (must work for patients without auth)
curl -I https://yourdomain.com/public/anamnesis/1/test-token-that-wont-exist
# Expected: 404 (not 502 or connection refused)
```

---

## Part 10 — Rollback Procedure

> **Before enabling proxy:** lower the TTL of affected A records to **60 seconds** in Cloudflare DNS. This makes rollback effective in 60 seconds. If you forget to do this, Cloudflare Auto TTL is 5 minutes — rollback will take up to 5 minutes to propagate to resolvers.

**Rollback timing:**
- TTL pre-lowered to 60s → rollback effective in **~60 seconds**
- TTL at Auto (Cloudflare default) → rollback effective in **up to 5 minutes**

**Per-record rollback:**
1. Dashboard → DNS → Records
2. Find the affected A record
3. Click the orange cloud icon → toggle to grey (DNS only)
4. Save → traffic bypasses Cloudflare once TTL expires

**Full rollback (go back to direct VPS):**
1. Toggle ALL A records to grey cloud (DNS only)
2. Optionally point nameservers back to registrar's own NS — but this takes hours to propagate
3. Toggling to grey cloud is faster and sufficient for emergency

**What NOT to do during rollback:**
- Do not delete the domain from Cloudflare before confirming old nameservers are active
- Do not change nameservers unless the grey cloud toggle doesn't solve the issue

---

## Part 11 — Post-Setup Hardening (optional, after stability is confirmed)

Once the site has been running through Cloudflare for 48h with no issues:

1. **Enable HSTS subdomains** — only after confirming all subdomains have valid HTTPS certificates
2. **Enable HSTS Preload** — submit domain to https://hstspreload.org (irreversible, do last)
3. **Cloudflare Access** (Zero Trust, free tier: 50 users) — protect the EasyPanel admin UI with email OTP auth
4. **Health check alerts** — Dashboard → Notifications → create alert for origin error rate > 5%
5. **Analytics** — Dashboard → Analytics & Logs → enable HTTP traffic logs (free 24h retention)
6. **Schedule firewall IP update** — re-run `lock-vps-to-cloudflare.sh` quarterly (Cloudflare IP ranges change)

---

## Summary

| What | Setting |
|------|---------|
| SSL mode | Full (strict) |
| Origin cert | Cloudflare Origin Certificate (free, 15yr) recommended over Let's Encrypt HTTP-01 |
| WebSocket | Enabled by default (free) |
| Nova heartbeat | **REQUIRED before enabling proxy** — add 30s ping in NovaWidget.tsx `startVoice()` |
| Bot protection | Bot Fight Mode (free) |
| WAF | Managed ruleset, medium sensitivity, with exclusions for webhook/Nova/anamnesis paths |
| Rate limits | 300/min for webhooks (burst-tolerant), challenge on /auth/login |
| HSTS subdomains | Start with `No` — enable after confirming all subdomains have HTTPS |
| Rollback | Toggle orange cloud → grey; 60s if TTL pre-lowered, up to 5min otherwise |
| VPS firewall | Lock 80/443 to Cloudflare IP ranges after proxy confirmed working |
| MX records | Must be grey cloud (DNS-only) — verify before and after migration |
| Estimated time | 90 minutes |
