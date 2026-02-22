# Briven — Ultra-Safe VPS Deployment Guide

> **Hostinger KVM + Ubuntu 24.04 + Tailscale Zero-Trust**
>
> Native Python installation (no Docker). Every command is copy-paste ready.
> The golden rule: **never expose port 8000 or 22 publicly — only via Tailscale.**

---

## Table of Contents

1. [Pre-VPS Preparation Checklist](#step-1--pre-vps-preparation-checklist)
2. [VPS Creation & Initial Hardening](#step-2--vps-creation--initial-hardening)
3. [Tailscale + UFW + Fail2ban Full Setup](#step-3--tailscale--ufw--fail2ban-full-setup)
4. [Briven Installation on VPS](#step-4--briven-installation-on-vps)
5. [Safe First-Time Testing Protocol](#step-5--safe-first-time-testing-protocol)
6. [Rollback & Emergency Steps](#step-6--rollback--emergency-steps)
7. [Final Security Checklist & Next-Day Recommendations](#step-7--final-security-checklist--next-day-recommendations)

---

## Step 1 — Pre-VPS Preparation Checklist

Do all of this **locally on your Mac** before you rent the VPS.

### 1.1 Create a Tailscale Account (if you haven't)

- Sign up at [https://login.tailscale.com](https://login.tailscale.com)
- Install Tailscale on your Mac: `brew install --cask tailscale`
- Open Tailscale, log in, confirm your machine appears in the admin console
- Note your local Tailscale IP: `tailscale ip -4` (e.g. `100.64.x.x`)

### 1.2 Prepare Your `.env` File Locally

Create the file now so you can `scp` it later. This avoids editing secrets on an unfamiliar server:

```bash
mkdir -p ~/briven-deploy
cat > ~/briven-deploy/.env << 'EOF'
# ── Authentication (REQUIRED — protects the web UI) ──────────
AUTH_LOGIN=youruser
AUTH_PASSWORD=YourStr0ng!Pass#2026

# ── LLM Provider (pick at least one) ─────────────────────────
API_KEY_OPENROUTER=sk-or-v1-xxxxxxxxxxxx
# API_KEY_ANTHROPIC=sk-ant-xxxxxxxxxxxx
# API_KEY_OPENAI=sk-xxxxxxxxxxxx

# ── Bind to Tailscale IP (filled in during Step 4) ───────────
# BRIVEN_SET_host=100.x.x.x

# ── Working directory on VPS ─────────────────────────────────
BRIVEN_SET_work_dir=/root/briven-workspace

# ── Optional integrations (leave blank to skip for now) ──────
# TELEGRAM_BOT_TOKEN=
# TELEGRAM_CHAT_ID=
# SLACK_WEBHOOK_URL=
# DISCORD_WEBHOOK_URL=
# EMAIL_SMTP_HOST=smtp.gmail.com
# EMAIL_SMTP_PORT=587
# EMAIL_USER=
# EMAIL_PASSWORD=
EOF
```

### 1.3 Generate an SSH Key Pair (if you don't have one)

```bash
ssh-keygen -t ed25519 -C "briven-vps" -f ~/.ssh/briven_vps
cat ~/.ssh/briven_vps.pub
# Copy this public key — you'll paste it during Hostinger VPS creation
```

### 1.4 Pre-Flight Checklist

| Item | Status |
|------|--------|
| Tailscale account created and working on Mac | |
| `.env` file prepared with at least one API key | |
| SSH key generated (`~/.ssh/briven_vps.pub`) | |
| Auth password is 12+ chars with mixed case/symbols | |
| You know which LLM provider you'll use first | |

---

## Step 2 — VPS Creation & Initial Hardening

### 2.1 Rent the VPS (Hostinger KVM)

| Setting | Value |
|---------|-------|
| **Plan** | KVM 1 (1 vCPU, 4 GB RAM) or KVM 2 |
| **OS** | Ubuntu 24.04 LTS |
| **Region** | Closest to you (Europe for Belgium) |
| **SSH Key** | Paste your `~/.ssh/briven_vps.pub` |
| **Root password** | Set a strong one, but we'll disable password auth |

> **Minimum: 4 GB RAM recommended.** Briven loads sentence-transformers and embedding models into memory. 2 GB will work but may swap.

### 2.2 First SSH Connection (from your Mac)

```bash
ssh -i ~/.ssh/briven_vps root@YOUR_VPS_PUBLIC_IP
```

### 2.3 Immediate Hardening (run these FIRST, before anything else)

```bash
# Update the system
apt update && apt upgrade -y

# Set the timezone
timedatectl set-timezone Europe/Brussels

# Create a non-root user for Briven
adduser --disabled-password --gecos "Briven" briven
usermod -aG sudo briven

# Copy your SSH key to the new user
mkdir -p /home/briven/.ssh
cp /root/.ssh/authorized_keys /home/briven/.ssh/
chown -R briven:briven /home/briven/.ssh
chmod 700 /home/briven/.ssh
chmod 600 /home/briven/.ssh/authorized_keys

# Allow passwordless sudo for briven user (needed for install)
echo "briven ALL=(ALL) NOPASSWD:ALL" > /etc/sudoers.d/briven
chmod 440 /etc/sudoers.d/briven
```

### 2.4 Harden SSH Configuration

```bash
# Backup original config
cp /etc/ssh/sshd_config /etc/ssh/sshd_config.bak

# Apply hardened settings
cat >> /etc/ssh/sshd_config << 'EOF'

# ── Briven hardening ──────────────────────────────────────
PermitRootLogin no
PasswordAuthentication no
PubkeyAuthentication yes
AuthenticationMethods publickey
MaxAuthTries 3
LoginGraceTime 30
X11Forwarding no
AllowTcpForwarding no
PermitEmptyPasswords no
ClientAliveInterval 300
ClientAliveCountMax 2
AllowUsers briven
EOF

# Validate config before restarting (critical!)
sshd -t
```

> **WARNING:** Do NOT restart SSH yet. We need Tailscale installed first, or you could lock yourself out. Continue to Step 3.

---

## Step 3 — Tailscale + UFW + Fail2ban Full Setup

### 3.1 Install Tailscale on the VPS

```bash
# Install Tailscale (official one-liner for Ubuntu)
curl -fsSL https://tailscale.com/install.sh | sh

# Authenticate — this will print a URL, open it in your browser
tailscale up

# Verify connection
tailscale ip -4
# Output: 100.x.x.x — THIS is your VPS Tailscale IP. Write it down!

tailscale status
# Should show your Mac and this VPS both online
```

### 3.2 Test Tailscale Connectivity (from your Mac)

Open a **new terminal on your Mac** (keep the VPS session open as backup):

```bash
# Ping the VPS via Tailscale
ping -c 3 $(tailscale status | grep -i "your-vps-hostname" | awk '{print $1}')

# Or use the IP directly
ping -c 3 100.x.x.x    # replace with actual VPS Tailscale IP

# SSH via Tailscale (this is how you'll ALWAYS connect from now on)
ssh -i ~/.ssh/briven_vps briven@100.x.x.x
```

> **CRITICAL:** Only proceed to the next step if the Tailscale SSH connection works. If it doesn't, DO NOT enable UFW yet.

### 3.3 Install and Configure UFW

**Back on the VPS** (connected via Tailscale SSH now):

```bash
sudo apt install -y ufw

# Reset to defaults
sudo ufw default deny incoming
sudo ufw default allow outgoing

# Allow Tailscale interface (CRITICAL — do this FIRST)
sudo ufw allow in on tailscale0

# Allow SSH only over Tailscale subnet (100.64.0.0/10)
sudo ufw allow from 100.64.0.0/10 to any port 22 proto tcp comment 'SSH via Tailscale only'

# Allow Briven web UI only over Tailscale
sudo ufw allow from 100.64.0.0/10 to any port 8000 proto tcp comment 'Briven via Tailscale only'

# Block ALL public SSH (the public IP will have zero open ports)
# This happens automatically because default is deny incoming

# Enable UFW
sudo ufw enable
# Type 'y' when prompted

# Verify rules
sudo ufw status verbose
```

**Expected output:**

```
Status: active
Logging: on (low)
Default: deny (incoming), allow (outgoing), disabled (routed)

To                         Action      From
--                         ------      ----
Anywhere on tailscale0     ALLOW IN    Anywhere
22/tcp                     ALLOW IN    100.64.0.0/10    # SSH via Tailscale only
8000/tcp                   ALLOW IN    100.64.0.0/10    # Briven via Tailscale only
```

> **WARNING — Common Pitfall:** If you forget `allow in on tailscale0`, Tailscale traffic itself gets blocked and you lose all access. The `tailscale0` rule must exist.

### 3.4 Now Restart SSH (safe to do after Tailscale + UFW are confirmed)

```bash
sudo systemctl restart sshd

# Test immediately — open a NEW terminal on your Mac:
ssh -i ~/.ssh/briven_vps briven@100.x.x.x   # Tailscale IP
# This should work ✓

# Also verify public SSH is blocked:
ssh -i ~/.ssh/briven_vps briven@YOUR_PUBLIC_IP -o ConnectTimeout=5
# This should timeout/fail ✓
```

### 3.5 Install and Configure Fail2ban

```bash
sudo apt install -y fail2ban

# Create local config (never edit jail.conf directly)
sudo cat > /etc/fail2ban/jail.local << 'EOF'
[DEFAULT]
# Ban for 1 hour after 3 failures
bantime  = 3600
findtime = 600
maxretry = 3
banaction = ufw

# Ignore Tailscale subnet (don't ban yourself)
ignoreip = 127.0.0.1/8 ::1 100.64.0.0/10

[sshd]
enabled  = true
port     = ssh
filter   = sshd
logpath  = /var/log/auth.log
maxretry = 3
bantime  = 3600
EOF

# Start and enable
sudo systemctl enable fail2ban
sudo systemctl start fail2ban

# Verify it's running
sudo fail2ban-client status
sudo fail2ban-client status sshd
```

### 3.6 Verify Security Lockdown

Run this checklist from **your Mac**:

```bash
# ✓ Tailscale SSH works
ssh -i ~/.ssh/briven_vps briven@100.x.x.x "echo 'Tailscale SSH OK'"

# ✓ Public SSH is blocked
timeout 5 ssh -i ~/.ssh/briven_vps briven@YOUR_PUBLIC_IP 2>&1 || echo "PUBLIC SSH BLOCKED ✓"

# ✓ Port 8000 is not publicly accessible (nothing running yet, but verify)
timeout 5 curl http://YOUR_PUBLIC_IP:8000 2>&1 || echo "PORT 8000 BLOCKED ✓"

# ✓ No open public ports (optional: install nmap on Mac)
# nmap -Pn YOUR_PUBLIC_IP
# Should show "All 1000 scanned ports are filtered"
```

---

## Step 4 — Briven Installation on VPS

### 4.1 Install System Dependencies

SSH into the VPS via Tailscale as the `briven` user:

```bash
ssh -i ~/.ssh/briven_vps briven@100.x.x.x
```

```bash
# Python 3.12 + build essentials
sudo apt install -y python3 python3-pip python3-venv python3-dev \
    build-essential git curl wget \
    libffi-dev libssl-dev libjpeg-dev libpng-dev \
    tesseract-ocr poppler-utils ffmpeg

# Verify Python version (must be 3.10+)
python3 --version
```

### 4.2 Run the Briven Installer

```bash
# One-liner install (clones to ~/briven, creates venv, installs deps)
curl -fsSL https://raw.githubusercontent.com/flandriendev/briven/main/install.sh | bash
```

This will:
1. Clone the repo to `~/briven`
2. Create a Python virtual environment at `~/briven/.venv`
3. Install all 54+ dependencies from `requirements.txt`
4. Create a `.env` from `.env.example` if none exists
5. Print your Tailscale IP and the startup command

### 4.3 Deploy Your Prepared `.env`

From **your Mac**, upload the `.env` you prepared in Step 1:

```bash
scp -i ~/.ssh/briven_vps ~/briven-deploy/.env briven@100.x.x.x:~/briven/.env
```

### 4.4 Set the Tailscale Bind Address in `.env`

Back on the **VPS**:

```bash
cd ~/briven

# Get your Tailscale IP
TS_IP=$(tailscale ip -4)
echo "Tailscale IP: $TS_IP"

# Add it to .env
echo "BRIVEN_SET_host=$TS_IP" >> .env
```

### 4.5 Create the Working Directory

```bash
mkdir -p ~/briven-workspace
```

### 4.6 Install Playwright Browsers (for browser-use tool)

```bash
cd ~/briven
source .venv/bin/activate
playwright install --with-deps chromium
```

### 4.7 Create a systemd Service (auto-start on reboot)

```bash
sudo cat > /etc/systemd/system/briven.service << EOF
[Unit]
Description=Briven AI Framework
After=network.target tailscaled.service
Wants=tailscaled.service

[Service]
Type=simple
User=briven
Group=briven
WorkingDirectory=/home/briven/briven
Environment="PATH=/home/briven/briven/.venv/bin:/usr/local/bin:/usr/bin:/bin"
ExecStart=/home/briven/briven/.venv/bin/uvicorn run_ui:app --host $(tailscale ip -4) --port 8000
Restart=on-failure
RestartSec=10
StandardOutput=journal
StandardError=journal
SyslogIdentifier=briven

# Security hardening
NoNewPrivileges=yes
ProtectSystem=strict
ReadWritePaths=/home/briven
PrivateTmp=yes

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable briven
```

> **Don't start the service yet** — we'll do a manual test first in Step 5.

---

## Step 5 — Safe First-Time Testing Protocol

### 5.1 Pre-Flight Checks

```bash
cd ~/briven
source .venv/bin/activate

# Verify Tailscale is connected
python3 tools/tailscale.py --status

# Verify .env is loaded (check for AUTH_LOGIN presence)
grep -c "AUTH_LOGIN" .env && echo ".env OK" || echo ".env MISSING AUTH!"

# Verify Python can import the project
python3 -c "import dotenv; dotenv.load_dotenv(); print('imports OK')"
```

### 5.2 First Manual Start (foreground — so you see all output)

```bash
TS_IP=$(tailscale ip -4)
echo "Starting Briven on $TS_IP:8000 ..."

uvicorn run_ui:app --host "$TS_IP" --port 8000
```

**What to watch for in the console:**

| Output | Meaning |
|--------|---------|
| `Uvicorn running on http://100.x.x.x:8000` | Server started correctly |
| `INFO: Application startup complete` | All initializations succeeded |
| Any `ERROR` or traceback | Problem — read the error, don't ignore it |
| `ModuleNotFoundError` | Missing dependency — `pip install <module>` |
| Memory/embedding model download | First run downloads ~100MB of model files — normal |

### 5.3 Test Access from Your Mac

While the server is running in the foreground on the VPS:

```bash
# From your Mac — test basic connectivity
curl -s -o /dev/null -w "%{http_code}" http://100.x.x.x:8000/
# Expected: 302 (redirect to login)

# Test login page loads
curl -s http://100.x.x.x:8000/login | head -5
# Expected: HTML content

# Open in browser
open "http://100.x.x.x:8000"
```

### 5.4 Log In and Send Low-Risk Test Prompts

Log in with the `AUTH_LOGIN` / `AUTH_PASSWORD` from your `.env`, then test with these safe prompts — in this exact order:

**Round 1 — Heartbeat (does the agent respond at all?)**

```
Hello, what is your name and what can you do?
```

Expected: Agent introduces itself, lists capabilities. Confirms LLM API key works.

**Round 2 — Memory check (does persistence work?)**

```
Remember that my favorite color is blue.
```

Then in a new message:

```
What is my favorite color?
```

Expected: Agent recalls "blue". Confirms memory/SQLite is working.

**Round 3 — Tool check (do built-in tools work?)**

```
What time is it right now? What is today's date?
```

Expected: Returns correct date/time. Confirms basic tool execution.

**Round 4 — Tailscale status (does the tool integration work?)**

```
Run the Tailscale status check and show me which devices are connected.
```

Expected: Shows connected tailnet peers. Confirms `tools/tailscale.py` works.

### 5.5 Monitor During Testing

Open a **second SSH session** to the VPS for monitoring:

```bash
# Watch Briven logs in real-time (if running via systemd later)
journalctl -u briven -f

# Watch system resources
htop
# Or: watch -n 2 'free -h && echo "---" && uptime'

# Watch for disk usage
df -h /home/briven

# Watch fail2ban
sudo fail2ban-client status sshd
```

### 5.6 What NOT To Test Yet

| Don't do this yet | Why |
|---|---|
| Send prompts that create/delete files on disk | Verify the sandbox is correct first |
| Test multi-agent parallel calls | High resource usage, test after baseline |
| Run browser-use tasks | Memory-heavy; test after confirming base works |
| Send Telegram/Slack/Discord messages | Confirm API keys and formats first locally |
| Run long autonomous loops | Risk of runaway token usage |

---

## Step 6 — Rollback & Emergency Steps

### 6.1 Emergency: Locked Out of SSH

If you somehow locked yourself out:

1. **Hostinger Console:** Go to Hostinger VPS panel → "VPS Access" → "Browser Terminal" (KVM console). This bypasses SSH entirely.
2. From the console: `sudo ufw disable` to regain access, then fix rules.

### 6.2 Emergency: Briven Won't Start

```bash
# Check logs
journalctl -u briven --since "5 minutes ago" --no-pager

# Common fixes:
cd ~/briven
source .venv/bin/activate

# Fix 1: Missing dependency
pip install -r requirements.txt

# Fix 2: Port already in use
sudo lsof -i :8000
# Kill the stale process if needed:
kill <PID>

# Fix 3: .env syntax error
python3 -c "from dotenv import dotenv_values; print(dotenv_values('.env'))"
```

### 6.3 Emergency: Agent Running Wild (high CPU/memory)

```bash
# Stop the service immediately
sudo systemctl stop briven

# Check what happened
journalctl -u briven --since "10 minutes ago" | tail -50

# Check resource usage
free -h
df -h
```

### 6.4 Emergency: Suspicious Activity Detected

```bash
# Check fail2ban for blocked IPs
sudo fail2ban-client status sshd

# Check recent SSH attempts
sudo grep "Failed" /var/log/auth.log | tail -20

# Check UFW logs
sudo grep "UFW BLOCK" /var/log/syslog | tail -20

# Nuclear option: block all traffic except Tailscale
sudo ufw reset
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow in on tailscale0
sudo ufw enable
```

### 6.5 Common Issues

| Problem | Fix |
|---------|-----|
| Can't reach from local machine | Ensure both machines are on the same tailnet (`tailscale status`) |
| Service fails to start | `journalctl -u briven -n 50` for error details |
| `ModuleNotFoundError` | Wrong Python path in service; check `ExecStart` points to `.venv/bin/uvicorn` |
| LLM API errors | Verify key in `.env`, confirm `EnvironmentFile` path in unit file |
| Tailscale IP changes on restart | Pin IP in Tailscale admin console (Machines → Edit route settings) |

### 6.6 Full Rollback (start over cleanly)

```bash
# Stop the service
sudo systemctl stop briven
sudo systemctl disable briven

# Remove the installation (preserves .env)
cp ~/briven/.env ~/briven-deploy-backup.env
rm -rf ~/briven

# Re-install from scratch
curl -fsSL https://raw.githubusercontent.com/flandriendev/briven/main/install.sh | bash
cp ~/briven-deploy-backup.env ~/briven/.env
```

---

## Step 7 — Final Security Checklist & Next-Day Recommendations

### 7.1 Security Verification Checklist

Run this after everything is working. Every line should pass:

```bash
echo "=== Briven Security Audit ==="

# 1. SSH hardened
echo -n "Root login disabled: "
grep "^PermitRootLogin no" /etc/ssh/sshd_config && echo "PASS" || echo "FAIL — FIX THIS"

echo -n "Password auth disabled: "
grep "^PasswordAuthentication no" /etc/ssh/sshd_config && echo "PASS" || echo "FAIL — FIX THIS"

# 2. UFW active with correct rules
echo -n "UFW active: "
sudo ufw status | grep -q "Status: active" && echo "PASS" || echo "FAIL — FIX THIS"

echo -n "Tailscale interface allowed: "
sudo ufw status | grep -q "tailscale0" && echo "PASS" || echo "FAIL — FIX THIS"

# 3. Fail2ban running
echo -n "Fail2ban running: "
systemctl is-active fail2ban >/dev/null 2>&1 && echo "PASS" || echo "FAIL — FIX THIS"

# 4. Tailscale connected
echo -n "Tailscale connected: "
tailscale status >/dev/null 2>&1 && echo "PASS" || echo "FAIL — FIX THIS"

# 5. Briven not bound to 0.0.0.0
echo -n "Briven bound to Tailscale IP only: "
TS_IP=$(tailscale ip -4)
ss -tlnp | grep 8000 | grep -q "$TS_IP" && echo "PASS ($TS_IP)" || echo "FAIL — CHECK BINDING"

# 6. Auth enabled
echo -n "Auth configured in .env: "
grep -q "^AUTH_LOGIN=" ~/briven/.env && grep -q "^AUTH_PASSWORD=" ~/briven/.env && echo "PASS" || echo "FAIL — FIX THIS"

# 7. No public ports open
echo -n "No public-facing ports: "
echo "(verify with: nmap -Pn YOUR_PUBLIC_IP from another machine)"

echo "=== Audit Complete ==="
```

### 7.2 Next-Day Recommendations

**Day 2: Enable Auto-Updates**

```bash
# Unattended security upgrades
sudo apt install -y unattended-upgrades
sudo dpkg-reconfigure -plow unattended-upgrades
```

**Day 2: Set Up Log Rotation**

```bash
sudo cat > /etc/logrotate.d/briven << 'EOF'
/home/briven/briven/logs/*.log {
    daily
    missingok
    rotate 14
    compress
    delaycompress
    notifempty
    copytruncate
}
EOF
```

**Day 2: Start via systemd (instead of foreground)**

```bash
# After successful manual testing, switch to systemd
sudo systemctl start briven
sudo systemctl status briven

# Verify it survives a reboot
sudo reboot
# Wait 2 minutes, then:
ssh -i ~/.ssh/briven_vps briven@100.x.x.x
sudo systemctl status briven
curl -s -o /dev/null -w "%{http_code}" http://$(tailscale ip -4):8000/
```

**Day 3+: Enable Integrations Gradually**

Test one integration at a time by uncommenting lines in `.env`:

1. Telegram notifications first (low risk, easy to verify)
2. Memory/embeddings (already tested in Step 5)
3. Scheduler/cron tasks
4. Multi-agent features
5. Browser-use (resource intensive — monitor RAM)

**Day 3+: Set Up Tailscale Serve (optional HTTPS)**

```bash
# Enables HTTPS access via your-vps.tailnet-name.ts.net
tailscale serve 8000

# Or via the Briven helper:
cd ~/briven && source .venv/bin/activate
python3 tools/tailscale.py --serve --port 8000
```

**Weekly: Backup Routine**

```bash
# Backup agent memory, config, and workspace
tar -czf ~/briven-backup-$(date +%Y%m%d).tar.gz \
    ~/briven/.env \
    ~/briven/memory/ \
    ~/briven/data/ \
    ~/briven/knowledge/ \
    ~/briven-workspace/
```

---

## Quick Reference Card

```
+-----------------------------------------------------------------+
|                  Briven VPS — Quick Ref                       |
+-----------------------------------------------------------------+
|  SSH:        ssh -i ~/.ssh/briven_vps briven@100.x.x.x    |
|  Web UI:     http://100.x.x.x:8000                              |
|  Start:      sudo systemctl start briven                     |
|  Stop:       sudo systemctl stop briven                      |
|  Logs:       journalctl -u briven -f                         |
|  Status:     python3 tools/tailscale.py --status                |
|  UFW:        sudo ufw status verbose                            |
|  Fail2ban:   sudo fail2ban-client status sshd                   |
|  .env:       nano ~/briven/.env                              |
|  Restart:    sudo systemctl restart briven                   |
|                                                                 |
|  NEVER: expose port 22 or 8000 to the public internet           |
|  ALWAYS: connect exclusively via Tailscale (100.x.x.x)          |
+-----------------------------------------------------------------+
```

---

## Security Architecture

This guide provides a **triple-layer security posture**:

1. **Tailscale zero-trust** — no public ports, encrypted mesh networking
2. **UFW firewall** — defense in depth, deny-all default
3. **Fail2ban** — intrusion detection and automatic banning

Combined with Briven's built-in protections:

- **Login guard** (`python/helpers/login_guard.py`) — brute-force protection with exponential backoff, 15-minute lockout after 5 failures
- **Security headers** (`python/helpers/security_headers.py`) — X-Content-Type-Options, X-Frame-Options, Referrer-Policy, Permissions-Policy
- **Audit logging** (`python/helpers/audit_log.py`) — all security events logged

---

*Guide created for Briven v1.0 — Hostinger KVM + Ubuntu 24.04 + Tailscale deployments.*
