# Briven — VPS Server Install Guide

Native Python + Tailscale + systemd. Ubuntu 22.04/24.04 or Debian 12.

---

## Prerequisites

- Ubuntu 22.04+ / Debian 12 VPS (1 vCPU / 2 GB RAM minimum; 2 vCPU / 4 GB recommended)
- Python 3.10+ (available via `apt` on Ubuntu 22.04+)
- Root or sudo access
- An LLM API key (OpenRouter, OpenAI, Anthropic, etc.)

---

## 1. Install Tailscale

**Why Tailscale?** Zero-trust networking — your VPS is NOT exposed to the public internet.
Briven listens only on your Tailscale IP. No firewall rules, no nginx reverse proxy needed.

```bash
# Install Tailscale on the VPS:
curl -fsSL https://tailscale.com/install.sh | sh
tailscale up --authkey=tskey-auth-XXXX   # use an auth key from tailscale.com/admin/authkeys
tailscale ip -4   # note your VPS Tailscale IP
```

On your local machine, install Tailscale too → both devices join the same tailnet → done.

---

## 2. System Dependencies

```bash
sudo apt update && sudo apt install -y \
  python3.12 python3.12-venv python3.12-dev \
  git curl build-essential libssl-dev
```

---

## 3. Create a Dedicated User

```bash
sudo useradd -m -s /bin/bash briven
sudo -i -u briven
```

All subsequent steps run as the `briven` user.

---

## 4. Clone & Install

```bash
# One-liner:
curl -fsSL https://raw.githubusercontent.com/flandriendev/briven/main/install.sh | bash

# Or manually:
git clone https://github.com/flandriendev/briven.git ~/briven
cd ~/briven
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

---

## 5. Configure Environment

```bash
cp .env.example .env
nano .env
```

Key settings:

```bash
# LLM provider (pick one):
OPENROUTER_API_KEY=sk-or-...
# OPENAI_API_KEY=sk-...
# ANTHROPIC_API_KEY=sk-ant-...

# Working directory for agent files:
BRIVEN_SET_work_dir=/home/briven/workspace

# Bind to Tailscale IP (gets your VPS tailscale IP):
# Leave this out if you want to set it in the systemd unit directly.
```

---

## 6. Test the Server

```bash
cd ~/briven
source .venv/bin/activate
TS_IP=$(tailscale ip -4)
uvicorn run_ui:app --host "$TS_IP" --port 8000
# Ctrl-C when satisfied
```

From your local machine (connected to same tailnet):

```
http://<vps-tailscale-ip>:8000
```

---

## 7. systemd Service

Exit back to your sudo user, then:

```bash
TS_IP=$(tailscale ip -4)
BRIVEN_HOME=/home/briven/briven

sudo tee /etc/systemd/system/briven.service > /dev/null << EOF
[Unit]
Description=Briven — autonomous AI agent framework
After=network-online.target tailscaled.service
Wants=network-online.target

[Service]
Type=simple
User=briven
Group=briven
WorkingDirectory=${BRIVEN_HOME}
Environment="PATH=${BRIVEN_HOME}/.venv/bin:/usr/local/bin:/usr/bin:/bin"
EnvironmentFile=${BRIVEN_HOME}/.env
ExecStart=${BRIVEN_HOME}/.venv/bin/uvicorn run_ui:app --host ${TS_IP} --port 8000
Restart=on-failure
RestartSec=10
StandardOutput=journal
StandardError=journal
SyslogIdentifier=briven

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable briven
sudo systemctl start briven
sudo systemctl status briven
```

---

## 8. Manage the Service

```bash
sudo systemctl start briven      # start
sudo systemctl stop briven       # stop
sudo systemctl restart briven    # restart
sudo systemctl status briven     # check status

# View logs (live):
sudo journalctl -u briven -f

# View last 100 lines:
sudo journalctl -u briven -n 100
```

---

## 9. Tailscale Serve — HTTPS on Tailnet (optional)

Get automatic HTTPS on your tailnet with no certificate management:

```bash
tailscale serve 8000
# Access via: https://vps-name.your-tailnet.ts.net
```

Or use the Briven tool:

```bash
python tools/tailscale.py --serve --port 8000
```

---

## 10. Security Hardening

Since you're using Tailscale, the attack surface is already minimal. Still recommended:

```bash
# Disable password SSH auth (use keys only):
sudo sed -i 's/#PasswordAuthentication yes/PasswordAuthentication no/' /etc/ssh/sshd_config
sudo systemctl reload sshd

# UFW: allow only SSH and Tailscale (block everything else from public internet)
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow ssh
sudo ufw enable
# Briven port 8000 is only accessible via tailnet — no ufw rule needed.

# Keep system updated:
sudo apt install -y unattended-upgrades
sudo dpkg-reconfigure -plow unattended-upgrades
```

---

## 11. Updating Briven

```bash
sudo -i -u briven
cd ~/briven
git pull
source .venv/bin/activate
pip install -r requirements.txt
exit

sudo systemctl restart briven
```

---

## Troubleshooting

| Problem | Fix |
| ------- | --- |
| Can't reach from local machine | Ensure both machines are on the same tailnet (`tailscale status`) |
| Service fails to start | `journalctl -u briven -n 50` for error details |
| `ModuleNotFoundError` | Wrong Python path in service; check `ExecStart` points to `.venv/bin/uvicorn` |
| LLM API errors | Verify key in `.env`, confirm `EnvironmentFile` path in unit file |
| Tailscale IP changes on restart | Pin IP in Tailscale admin console (Machines → Edit route settings) |

See also: [docs/guides/troubleshooting.md](./guides/troubleshooting.md)
