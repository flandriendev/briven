# Briven — Mac Mini Install Guide

Native Python + Tailscale setup. No Docker required.

---

## Prerequisites

- macOS 13+ (Ventura or later)
- [Homebrew](https://brew.sh/) installed
- [Tailscale](https://tailscale.com/download/mac) installed and logged in
- An LLM API key — or use a free local provider (Ollama, LM Studio)

> **Note:** The interactive installer will automatically install Python 3.12, Git, and all other dependencies via Homebrew.

---

## 1. Install Tailscale

```bash
# Download from https://tailscale.com/download/mac or via brew:
brew install --cask tailscale
open -a Tailscale   # log in via the menu bar icon
tailscale ip -4     # note your Tailscale IP (e.g. 100.x.x.x)
```

No port forwarding needed. Briven will bind to your Tailscale IP for secure access.

---

## 2. Install Briven (Interactive Installer)

The installer provides a full TUI (text-based UI) with arrow-key navigation, progress bars, and guided setup for all 10 steps:

```bash
curl -fsSL https://raw.githubusercontent.com/flandriendev/briven/main/install.sh | bash
```

The installer will:
1. Detect macOS and install dependencies via Homebrew (Python 3.12, Git, curl, jq, tesseract, poppler)
2. Clone the repo to `~/briven`
3. Create a Python virtual environment and install all packages (with Apple Silicon MPS support — no bloated NVIDIA downloads)
4. Optionally configure Tailscale (offers `brew install` if not present)
5. Create `usr/.env` from the template
6. **Interactively set up your LLM provider** — choose from Briven API, Ollama (free/local), LM Studio (free/local), OpenRouter, Anthropic, OpenAI, Google, Groq, DeepSeek, Mistral, or xAI
7. Optionally configure messaging channels (Telegram, Discord, Slack, WhatsApp, Email)
8. Skip firewall setup (macOS uses its built-in firewall)
9. Create a `start.sh` launch script (macOS doesn't use systemd)
10. Optionally start Briven immediately

### Manual Install (alternative)

```bash
git clone https://github.com/flandriendev/briven.git ~/briven
cd ~/briven
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp usr/.env.example usr/.env
```

---

## 3. Configure Environment

If you used the interactive installer, your environment is already configured. To make manual changes:

```bash
nano ~/briven/usr/.env
```

Key fields:

```bash
# LLM provider (set by installer, or edit manually):
API_KEY_OPENROUTER=sk-or-...
# API_KEY_OPENAI=sk-...
# API_KEY_ANTHROPIC=sk-ant-...

# Set your working directory:
BRIVEN_SET_work_dir=/Users/yourname/briven-workspace

# Optional: bind to Tailscale IP automatically
# BRIVEN_SET_host=100.x.x.x
```

---

## 4. Start Briven

```bash
cd ~/briven
source .venv/bin/activate

# Get your Tailscale IP
TS_IP=$(tailscale ip -4)

# Start server bound to Tailscale IP (secure — only tailnet peers can reach it)
python3 run_ui.py --host "$TS_IP" --port 8000
```

Access from any device on your tailnet: `http://100.x.x.x:8000`

For localhost-only (no Tailscale):

```bash
python3 run_ui.py --host 127.0.0.1 --port 8000
```

Or use the start script created by the installer:

```bash
bash ~/briven/start.sh
```

---

## 5. Auto-start with launchd (run on login)

Create a launchd plist so Briven starts automatically:

```bash
cat > ~/Library/LaunchAgents/com.briven.plist << 'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>com.briven</string>
  <key>ProgramArguments</key>
  <array>
    <string>/Users/yourname/briven/.venv/bin/python3</string>
    <string>run_ui.py</string>
    <string>--host</string>
    <string>0.0.0.0</string>
    <string>--port</string>
    <string>8000</string>
  </array>
  <key>WorkingDirectory</key>
  <string>/Users/yourname/briven</string>
  <key>RunAtLoad</key>
  <true/>
  <key>KeepAlive</key>
  <true/>
  <key>StandardOutPath</key>
  <string>/tmp/briven.log</string>
  <key>StandardErrorPath</key>
  <string>/tmp/briven.err</string>
  <key>EnvironmentVariables</key>
  <dict>
    <key>PATH</key>
    <string>/usr/local/bin:/usr/bin:/bin:/opt/homebrew/bin</string>
  </dict>
</dict>
</plist>
EOF

# Replace 'yourname' with your actual macOS username:
sed -i '' "s/yourname/$(whoami)/g" ~/Library/LaunchAgents/com.briven.plist

# Load it:
launchctl load ~/Library/LaunchAgents/com.briven.plist
```

Manage the service:

```bash
launchctl start com.briven    # start
launchctl stop com.briven     # stop
launchctl unload ~/Library/LaunchAgents/com.briven.plist  # remove
tail -f /tmp/briven.log       # view logs
```

---

## 6. Tailscale Serve (optional — HTTPS on tailnet)

Tailscale Serve wraps your local port with HTTPS on your tailnet — no cert management needed:

```bash
tailscale serve 8000
# Access via: https://your-machine-name.your-tailnet.ts.net
```

Or use the helper:

```bash
python tools/tailscale.py --serve --port 8000
```

---

## 7. Verify Installation

```bash
# Check Tailscale status
python tools/tailscale.py --status

# Check Briven is running
curl http://$(tailscale ip -4):8000/api/health 2>/dev/null && echo "OK"

# Open in browser
open "http://$(tailscale ip -4):8000"
```

---

## Updating

```bash
cd ~/briven
git pull
source .venv/bin/activate
pip install -r requirements.txt
# Restart the service:
launchctl stop com.briven && launchctl start com.briven
```

---

## Troubleshooting

| Problem | Fix |
| ------- | --- |
| Port not accessible from other devices | Ensure you're binding to Tailscale IP, not 127.0.0.1 |
| `python3: command not found` | Install via Homebrew: `brew install python@3.12` |
| `ModuleNotFoundError` | Activate venv first: `source ~/briven/.venv/bin/activate` |
| Agent not responding | Check logs: `tail -f /tmp/briven.log` |
| LLM errors | Verify API key in `usr/.env`, check provider dashboard |
| Tailscale not connected | Run `tailscale up` and log in |
| Disk space during install | macOS uses Apple MPS — no large NVIDIA downloads needed |

See also: [Troubleshooting Guide](../guides/troubleshooting.md)
