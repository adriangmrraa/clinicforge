# RUNBOOK: UFW Firewall Activation — ClinicForge VPS

**Severity:** HIGH — ufw is currently INACTIVE, all ports potentially exposed
**Estimated time:** 15–30 minutes
**Risk:** SSH lockout if steps are not followed in order. Have KVM Console open BEFORE starting.

---

## Context

### Port map (docker-compose.yml)

| Port | Service | Published to host? | Should be public? |
|------|---------|-------------------|-------------------|
| 3000 | BFF (Express) | YES (`"3000:3000"`) | YES — API entrypoint |
| 4173 | Frontend (nginx) | YES (`"4173:80"`) | YES — Web UI |
| 8000 | Orchestrator (FastAPI) | NO — internal Docker network only | NO |
| 8002 | WhatsApp service | NO — internal Docker network only | NO |
| 5432 | PostgreSQL | NO — internal Docker network only | NO |
| 6379 | Redis | NO — internal Docker network only | NO |

### The Docker + ufw problem

**Docker bypasses ufw.** Docker inserts iptables rules into the `DOCKER` chain, which runs **before** ufw's `INPUT` chain. This means `ufw deny 8000` has zero effect on Docker-published ports — traffic reaches the container regardless.

The correct fix is the `DOCKER-USER` chain: it runs before the `DOCKER` chain and Docker respects rules placed there. This runbook uses that approach.

### docker-compose.override.yml

A `docker-compose.override.yml` does **NOT exist** in this repo. This is the safe state. If it ever appears (e.g., for local dev), it must NOT be deployed to production — it could accidentally publish 5432 (PostgreSQL) and 8000 (orchestrator) to the host.

---

## Phase 0 — Pre-flight (DO THIS FIRST)

### 0.1 Open Hostinger KVM Console

Before touching any firewall rule, open the browser-based KVM console in Hostinger's VPS panel. This gives you out-of-band access if SSH gets locked out.

1. Log in to [hpanel.hostinger.com](https://hpanel.hostinger.com)
2. Go to **VPS** → select your server → **Remote Console** (or "VNC/KVM")
3. Confirm the console opens and you can see a login prompt
4. Keep this tab open for the entire procedure

### 0.2 Confirm your SSH session survives a disconnect

In your active SSH session, start a `tmux` or `screen` session so commands keep running if the connection drops:

```bash
tmux new -s firewall
```

### 0.3 Check current state

```bash
# Confirm ufw is inactive
sudo ufw status verbose

# Confirm your current SSH port (default 22, might be custom)
sudo ss -tlnp | grep sshd

# Confirm Docker-published ports right now
sudo docker ps --format "table {{.Names}}\t{{.Ports}}"

# Confirm your public IP (to avoid locking yourself out)
curl -s https://api.ipify.org && echo
```

Note the SSH port from step 2. If it is not 22, **substitute your actual port in every command below**.

### 0.4 Check EasyPanel ports

EasyPanel typically uses port **3000** for its admin web UI. On this stack, BFF also uses port 3000. Verify which one is actually listening:

```bash
sudo ss -tlnp | grep ':3000'

# Check ALL potential EasyPanel ports
sudo ss -tlnp | grep -E ':(3000|3001|3002|8080|8443)'
# If any port besides 3000 is found, add it:
# sudo ufw allow <port>/tcp
# sudo iptables -I DOCKER-USER -i $IFACE -p tcp --dport <port> -j ACCEPT
```

- If EasyPanel runs on 3000 and BFF also on 3000, they share the port via EasyPanel's proxy — confirm in EasyPanel's dashboard which port its own admin UI uses (often 80/443 after initial setup, or a custom port like 8080 or 3001).
- If EasyPanel admin is on a different port (e.g., 8080), add that port in Step 1.3 below.

### 0.5 Check Docker daemon API exposure (CRITICAL)

```bash
# CRITICAL: Check if Docker daemon is exposed on TCP
sudo ss -tlnp | grep -E ':(2375|2376)'
cat /etc/docker/daemon.json 2>/dev/null | grep -i host
# If port 2375 or 2376 is listening: STOP. This is a critical security hole.
# Fix: Remove "hosts" TCP binding from /etc/docker/daemon.json
# Then restart Docker: sudo systemctl restart docker
```

> **WARNING:** Never proceed with firewall setup if Docker is exposed on TCP 2375 (unencrypted) or 2376. Fix this first.

---

## Phase 1 — Configure ufw Rules

**Work inside the `tmux` session from 0.2.**

### 1.1 Reset to clean state

```bash
sudo ufw --force reset
```

### 1.2 Set default policies

```bash
sudo ufw default deny incoming
sudo ufw default allow outgoing
```

### 1.3 Allow legitimate inbound ports

```bash
# SSH — rate-limited to block brute force (6 attempts/30s per source IP)
sudo ufw limit 22/tcp comment 'SSH rate-limited'

# HTTP and HTTPS (nginx/reverse proxy, Let's Encrypt)
sudo ufw allow 80/tcp comment 'HTTP'
sudo ufw allow 443/tcp comment 'HTTPS'

# BFF API — needed if accessed directly without a reverse proxy
# If your nginx proxy handles this and port 3000 is NOT meant to be public,
# REMOVE the line below and add the nginx proxy IP instead.
sudo ufw allow 3000/tcp comment 'BFF API'

# Frontend
sudo ufw allow 4173/tcp comment 'Frontend nginx'

# EasyPanel admin UI — only if it runs on a port NOT already covered above.
# Example: if EasyPanel admin is on 8080:
# sudo ufw allow 8080/tcp comment 'EasyPanel admin'
# If EasyPanel runs behind 80/443 (already allowed), skip this line.
```

> **Note on 3000/4173:** If you put nginx in front and proxy to these ports internally,
> you can remove these rules and only keep 80/443. That reduces attack surface further.

### 1.4 Second SSH session gate

> **STOP — Before running `ufw enable`:**
>
> 1. Open a **NEW terminal window**
> 2. SSH into the VPS from that new window
> 3. Confirm the connection works
> 4. **ONLY THEN** run `sudo ufw --force enable` in the original terminal
> 5. Verify the second SSH session is still connected after ufw is enabled

```bash
sudo ufw --force enable
```

Type `y` when prompted. **Your SSH connection should remain alive** because port 22 was allowed in 1.3.

Verify immediately:

```bash
sudo ufw status verbose
```

Expected output includes:
```
Status: active
...
22/tcp (rate limited)   ALLOW IN    Anywhere
80/tcp                  ALLOW IN    Anywhere
443/tcp                 ALLOW IN    Anywhere
3000/tcp                ALLOW IN    Anywhere
4173/tcp                ALLOW IN    Anywhere
```

---

## Phase 2 — Block Docker-published ports from the internet (DOCKER-USER chain)

ufw is now active but Docker-published ports still bypass it. This phase fixes that.

```
╔════════════════════════════════════════════════════════════╗
║  WHY TWO LAYERS?                                          ║
║  • ufw controls the INPUT chain → host-level traffic      ║
║  • DOCKER-USER controls the FORWARD chain → containers    ║
║  • Docker BYPASSES ufw entirely — it injects rules in     ║
║    the DOCKER chain which runs BEFORE ufw's INPUT chain   ║
║  • Both layers are REQUIRED for complete protection       ║
╚════════════════════════════════════════════════════════════╝
```

### 2.1 Detect the external network interface

```bash
# Detect the external network interface — DO NOT hardcode eth0
IFACE=$(ip route | awk '/^default/ {print $5; exit}')
echo "External interface: $IFACE"
# Verify it's correct (should show your VPS public IP)
ip addr show $IFACE | grep "inet "
```

> **WARNING:** Hostinger VPS typically uses `ens3` or `ens18`, NOT `eth0`. Always detect dynamically — never hardcode the interface name.

### 2.2 Add DOCKER-USER rules via iptables

These rules block all inbound traffic to Docker-managed ports **except** ports you explicitly allow. They survive Docker restarts because Docker only manages the `DOCKER` chain, not `DOCKER-USER`.

```bash
# FIRST: Allow SSH through DOCKER-USER (safety net — must be rule #1)
sudo iptables -I DOCKER-USER 1 -i $IFACE -p tcp --dport 22 -j ACCEPT

# Allow established/related connections (required for response traffic)
sudo iptables -I DOCKER-USER -i $IFACE -m conntrack --ctstate ESTABLISHED,RELATED -j ACCEPT

# Allow BFF port 3000 from the internet
sudo iptables -I DOCKER-USER -i $IFACE -p tcp --dport 3000 -j ACCEPT

# Allow Frontend port 4173 from the internet
sudo iptables -I DOCKER-USER -i $IFACE -p tcp --dport 4173 -j ACCEPT

# Block everything else coming in on $IFACE before it hits Docker
sudo iptables -A DOCKER-USER -i $IFACE -j DROP
```

> **Order matters.** The ACCEPT rules must come before the DROP rule. The `-I` flag inserts at the top; `-A` appends at the bottom. The commands above are already in correct order.

### 2.3 Verify SSH is reachable after DOCKER-USER rules

```bash
# Verify SSH port is open in both INPUT and FORWARD chains
sudo iptables -L INPUT -n | grep 22
sudo iptables -L FORWARD -n | grep 22
```

Open a **new SSH connection** to the VPS now. If it works, proceed. If not, use KVM Console to flush and recover.

### 2.4 Verify the DOCKER-USER chain

```bash
sudo iptables -L DOCKER-USER -n -v --line-numbers
```

Expected (line numbers may differ):
```
num   pkts bytes target     prot opt in     out     source          destination
1        0     0 ACCEPT     tcp  --  $IFACE *       0.0.0.0/0       0.0.0.0/0   tcp dpt:22
2        0     0 ACCEPT     all  --  $IFACE *       0.0.0.0/0       0.0.0.0/0   ctstate RELATED,ESTABLISHED
3        0     0 ACCEPT     tcp  --  $IFACE *       0.0.0.0/0       0.0.0.0/0   tcp dpt:3000
4        0     0 ACCEPT     tcp  --  $IFACE *       0.0.0.0/0       0.0.0.0/0   tcp dpt:4173
5        0     0 DROP       all  --  $IFACE *       0.0.0.0/0       0.0.0.0/0
```

### 2.5 Check IPv6 and mirror rules if enabled

```bash
# Check if IPv6 is enabled
grep "IPV6" /etc/default/ufw
# If IPV6=yes, add mirror rules:
sudo ip6tables -I DOCKER-USER -p tcp --dport 22 -j ACCEPT
sudo ip6tables -A DOCKER-USER -p tcp -m conntrack --ctstate ESTABLISHED,RELATED -j ACCEPT
sudo ip6tables -A DOCKER-USER -i $IFACE -p tcp --dport 3000 -j ACCEPT
sudo ip6tables -A DOCKER-USER -i $IFACE -p tcp --dport 4173 -j ACCEPT
sudo ip6tables -A DOCKER-USER -i $IFACE -j DROP
```

---

## Phase 3 — Verification (DO BEFORE PERSISTING)

> **Run external verification BEFORE `netfilter-persistent save`.**
> Only persist rules after confirming they work correctly.

### 3.1 From inside the VPS (sanity check)

```bash
# Confirm ufw is active and rules are correct
sudo ufw status numbered

# Confirm iptables DOCKER-USER chain
sudo iptables -L DOCKER-USER -n --line-numbers

# Confirm Docker containers are still running
sudo docker ps
```

### 3.2 From an external machine (the real test — run BEFORE saving)

From your local machine or another server (NOT the VPS), test each port:

```bash
VPS_IP="<your-vps-public-ip>"

# These should SUCCEED (connection accepted or proper HTTP response)
curl -s -o /dev/null -w "%{http_code}" http://$VPS_IP:3000/health
curl -s -o /dev/null -w "%{http_code}" http://$VPS_IP:4173

# These should FAIL (connection refused or timeout = firewall is working)
nc -zv -w 3 $VPS_IP 8000   # orchestrator — must be blocked
nc -zv -w 3 $VPS_IP 8002   # whatsapp — must be blocked
nc -zv -w 3 $VPS_IP 5432   # postgres — must be blocked
nc -zv -w 3 $VPS_IP 6379   # redis — must be blocked
```

If you have `nmap` available:

```bash
nmap -sT -p 3000,4173,8000,8002,5432,6379 $VPS_IP
```

Expected:
- 3000, 4173 → `open`
- 8000, 8002, 5432, 6379 → `filtered` or `closed`

### 3.3 Persist DOCKER-USER rules across reboots (only after verification passes)

```bash
sudo apt-get install -y iptables-persistent
sudo netfilter-persistent save
```

If `iptables-persistent` is already installed:

```bash
sudo netfilter-persistent save
```

Verify saved rules:

```bash
sudo cat /etc/iptables/rules.v4 | grep DOCKER-USER
```

### 3.4 Mandatory reboot test

```bash
# MANDATORY: Test rules survive reboot
# 1. Keep KVM Console open
# 2. Run: sudo reboot
# 3. Wait 1-2 minutes
# 4. SSH back in
# 5. Verify: sudo ufw status && sudo iptables -L DOCKER-USER -n --line-numbers
# 6. If SSH fails, use KVM Console: sudo ufw disable && sudo iptables -F DOCKER-USER
```

```bash
sudo reboot
```

After reconnecting:

```bash
sudo ufw status
sudo iptables -L DOCKER-USER -n --line-numbers
sudo docker ps
```

### 3.5 Docker restart survival test

```bash
docker compose down && docker compose up -d
sudo iptables -L DOCKER-USER -n --line-numbers
# Confirm DOCKER-USER rules are UNCHANGED after Docker restart
```

---

## Phase 4 — docker-compose.override.yml Safety

The file does NOT exist in production (correct). Prevent accidental creation:

**Rule:** Never create `docker-compose.override.yml` on the production VPS. This file is automatically loaded by `docker-compose up` without requiring `-f`, and it can publish internal ports (5432, 8000) to the host.

If you need a local dev override, create it locally only and add it to `.gitignore`:

```bash
# In local dev only — never commit, never deploy
echo "docker-compose.override.yml" >> .gitignore
```

On the production VPS, verify it is absent before any Docker operation:

```bash
ls docker-compose*.yml
```

Only `docker-compose.yml` should exist.

---

## Rollback Procedure

If something goes wrong (services unreachable, SSH issues):

### Option A — Via SSH (if still connected)

```bash
# Disable ufw entirely (reverts to open access)
sudo ufw disable

# Flush DOCKER-USER chain
sudo iptables -F DOCKER-USER

# Re-add the default Docker-USER RETURN rule
sudo iptables -I DOCKER-USER -j RETURN

# Save the restored (open) state so it survives reboot
sudo netfilter-persistent save
```

### Option B — Via Hostinger KVM Console (SSH locked out)

1. Open the KVM Console tab you kept open in Phase 0
2. Log in with your root/sudo credentials
3. Run:
   ```bash
   sudo ufw disable
   sudo iptables -F DOCKER-USER
   sudo iptables -I DOCKER-USER -j RETURN
   # Save the restored state
   sudo netfilter-persistent save
   ```
4. Your SSH access is restored

---

## Maintenance Notes

- **Adding a new public port:** `sudo ufw allow <port>/tcp` AND `sudo iptables -I DOCKER-USER -i $IFACE -p tcp --dport <port> -j ACCEPT` (insert BEFORE the DROP rule), then `sudo netfilter-persistent save`
- **After server reboot:** ufw reloads automatically; iptables rules reload via `netfilter-persistent` (installed in Phase 3.3)
- **After Docker restarts:** DOCKER-USER rules are preserved; Docker only touches the `DOCKER` chain
- **Checking rule order:** `sudo iptables -L DOCKER-USER -n --line-numbers` — SSH ACCEPT must be rule #1, DROP rule must always be last
- **Interface variable:** Always re-export `IFACE=$(ip route | awk '/^default/ {print $5; exit}')` before running iptables commands in a new session

---

## Summary of What Was Done

| Layer | Action | Effect |
|-------|--------|--------|
| ufw | `default deny incoming` | Blocks all uninvited inbound traffic at OS level |
| ufw | Allow 22 (rate-limited), 80, 443, 3000, 4173 | Legitimate traffic passes |
| DOCKER-USER | SSH ACCEPT (rule #1); ACCEPT 3000, 4173; DROP everything else | Docker-published ports blocked at iptables before Docker chain; SSH always reachable |
| ip6tables | Mirror SSH + service rules for IPv6 | IPv6 traffic protected equally |
| iptables-persistent | Save rules | Survives reboots |
| Reboot test | Mandatory post-save verification | Confirms persistence end-to-end |
