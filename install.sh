#!/usr/bin/env bash
# ============================================================
# Briven — Visual TUI Installer
#
# Usage:
#   curl -fsSL https://raw.githubusercontent.com/flandriendev/briven/main/install.sh | bash
#
# Supported:
#   Ubuntu 22.04 / 24.04 · Debian 12 / 13
#
# Features:
#   - Visual TUI with colored output and progress tracking
#   - Guided LLM provider selection + channel integration setup
#   - Tailscale zero-trust networking + ACL enforcement
#   - UFW + Fail2ban hardening (optional)
#   - Python 3.13+ compatibility auto-patching
#   - Idempotent: safe to re-run at any time
# ============================================================
set -euo pipefail

REPO="https://github.com/flandriendev/briven.git"
BRIVEN_PORT="${BRIVEN_PORT:-8000}"
TOTAL_STEPS=10
CURRENT_STEP=0

# ── Colors (ANSI-C quoting for proper rendering in heredocs) ──
# Briven red: RGB 221,63,42 / #dd3f2a
BRED=$'\e[38;2;221;63;42m'
RED=$'\e[31m'
YEL=$'\e[33m'
GRN=$'\e[32m'
CYN=$'\e[36m'
WHT=$'\e[97m'
BOLD=$'\e[1m'
DIM=$'\e[2m'
RST=$'\e[0m'

# ── Output helpers ─────────────────────────────────────────
info()    { printf "  ${BRED}[INFO]${RST}    %s\n" "$*"; }
ok()      { printf "  ${GRN}[  OK  ]${RST}  %s\n" "$*"; }
warn()    { printf "  ${YEL}[ WARN ]${RST}  %s\n" "$*"; }
err()     { printf "  ${RED}[ERROR]${RST}   %s\n" "$*" >&2; exit 1; }
dimtext() { printf "  ${DIM}%s${RST}\n" "$*"; }

step() {
    CURRENT_STEP=$((CURRENT_STEP + 1))
    local pct=$((CURRENT_STEP * 100 / TOTAL_STEPS))
    local filled=$((pct / 5))
    local empty=$((20 - filled))
    local bar=""
    for ((i=0; i<filled; i++)); do bar+="█"; done
    for ((i=0; i<empty; i++)); do bar+="░"; done
    printf "\n"
    printf "  ${BRED}${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${RST}\n"
    printf "  ${BRED}${BOLD}  Step %s/%s${RST}  ${WHT}%s${RST}\n" "$CURRENT_STEP" "$TOTAL_STEPS" "$1"
    printf "  ${BRED}  %s${RST}  ${DIM}%s%%${RST}\n" "$bar" "$pct"
    printf "  ${BRED}${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${RST}\n"
}

# ── Spinner for long-running tasks ─────────────────────────
spinner() {
    local pid=$1 msg="${2:-Working...}"
    local frames=('⠋' '⠙' '⠹' '⠸' '⠼' '⠴' '⠦' '⠧' '⠇' '⠏')
    local i=0
    while kill -0 "$pid" 2>/dev/null; do
        printf "\r  ${BRED}%s${RST} %s" "${frames[$((i % ${#frames[@]}))]}" "$msg"
        sleep 0.1
        i=$((i + 1))
    done
    printf "\r%80s\r" ""
}

# ── Interactive input (works with curl | bash via /dev/tty)
ask() {
    local prompt="$1" val=""
    if [[ -t 0 ]]; then
        read -rp "$prompt" val
    elif [[ -e /dev/tty ]]; then
        read -rp "$prompt" val < /dev/tty
    fi
    printf '%s' "$val"
}

ask_secret() {
    local prompt="$1" val=""
    if [[ -t 0 ]]; then
        read -rsp "$prompt" val
        echo
    elif [[ -e /dev/tty ]]; then
        read -rsp "$prompt" val < /dev/tty
        echo >/dev/tty
    fi
    printf '%s' "$val"
}

# ── Write key to usr/.env (uncomment if commented, append if missing)
set_env() {
    local key="$1" val="$2" file="$INSTALL_DIR/usr/.env"
    [[ -z "$val" ]] && return
    if grep -q "^${key}=" "$file" 2>/dev/null; then
        sed -i "s|^${key}=.*|${key}=${val}|" "$file"
    elif grep -q "^# *${key}=" "$file" 2>/dev/null; then
        sed -i "s|^# *${key}=.*|${key}=${val}|" "$file"
    else
        printf '%s=%s\n' "$key" "$val" >> "$file"
    fi
}

# ── Draw a box ─────────────────────────────────────────────
draw_box() {
    local width=59
    local border_color="$BRED$BOLD"
    printf "\n"
    printf "  ${border_color}┌"
    printf '─%.0s' $(seq 1 $width)
    printf "┐${RST}\n"
    while IFS= read -r line; do
        local stripped
        stripped=$(printf '%s' "$line" | sed 's/\x1b\[[0-9;]*m//g')
        local len=${#stripped}
        local pad=$((width - len))
        printf "  ${border_color}│${RST} %s%*s${border_color}│${RST}\n" "$line" "$pad" ""
    done
    printf "  ${border_color}└"
    printf '─%.0s' $(seq 1 $width)
    printf "┘${RST}\n"
}

# ╔══════════════════════════════════════════════════════════╗
# ║                         BANNER                           ║
# ╚══════════════════════════════════════════════════════════╝
clear 2>/dev/null || true
printf "\n"
printf "  ${BRED}${BOLD}"
cat << 'ASCII'
   ____         _
  | __ )  _ __ (_)__   __ ___  _ __
  |  _ \ | '__|| |\ \ / // _ \| '_ \
  | |_) || |   | | \ V /|  __/| | | |
  |____/ |_|   |_|  \_/  \___||_| |_|
ASCII
printf "${RST}\n"

draw_box << EOF
${BRED}${BOLD}Briven — Zero-Trust AI Agent Framework${RST}
${DIM}Self-hosted · Memory-persistent · /atlas-governed${RST}

${BOLD}Installer v2.0${RST}        ${DIM}github.com/flandriendev/briven${RST}
EOF

printf "\n"

# ── Security notice ────────────────────────────────────────
draw_box << EOF
${YEL}${BOLD}⚠  Security Notice${RST}

${WHT}This script will:${RST}
  • Install system packages (git, python3, build tools)
  • Clone the Briven repository
  • Create a Python virtual environment
  • Install Tailscale for zero-trust networking
  • Configure UFW firewall rules (optional)
  • Create a systemd service

${DIM}Review the source: github.com/flandriendev/briven${RST}
${DIM}Press Ctrl+C at any time to abort.${RST}
EOF

printf "\n"
REPLY=$(ask "  Press Enter to continue or Ctrl+C to abort... ")

# ── Detect distro ──────────────────────────────────────────
DISTRO=""
DISTRO_VER=""
if grep -qi "ubuntu" /etc/os-release 2>/dev/null; then
    DISTRO="Ubuntu"
    DISTRO_VER=$(grep VERSION_ID /etc/os-release 2>/dev/null | cut -d'"' -f2 || echo "?")
elif grep -qi "debian" /etc/os-release 2>/dev/null; then
    DISTRO="Debian"
    DISTRO_VER=$(grep VERSION_ID /etc/os-release 2>/dev/null | cut -d'"' -f2 || echo "?")
else
    err "Unsupported distro. Requires Ubuntu 22.04/24.04 or Debian 12/13."
fi

# ── Detect user / install path ─────────────────────────────
if [[ -n "${SUDO_USER:-}" && "${SUDO_USER:-}" != "root" ]]; then
    RUN_USER="$SUDO_USER"
    RUN_HOME=$(getent passwd "$SUDO_USER" | cut -d: -f6)
else
    RUN_USER="${USER:-root}"
    RUN_HOME="$HOME"
fi
INSTALL_DIR="${BRIVEN_DIR:-$RUN_HOME/briven}"

info "Detected: $DISTRO $DISTRO_VER"
info "Install dir: $INSTALL_DIR (user: $RUN_USER)"

# ╔══════════════════════════════════════════════════════════╗
# ║              Step 1 — System Dependencies                ║
# ╚══════════════════════════════════════════════════════════╝
step "System dependencies"

info "Updating package lists..."
sudo apt-get update -qq

info "Installing base packages..."
sudo apt-get install -y -qq \
    git curl wget ca-certificates build-essential \
    python3 python3-venv python3-dev python3-pip \
    libssl-dev zlib1g-dev libbz2-dev libreadline-dev \
    libsqlite3-dev libncursesw5-dev libxml2-dev libxmlsec1-dev \
    libffi-dev liblzma-dev jq ufw fail2ban \
    tesseract-ocr poppler-utils 2>/dev/null || true
ok "Base packages ready"

# ╔══════════════════════════════════════════════════════════╗
# ║              Step 2 — Clone / Update Repo                ║
# ╚══════════════════════════════════════════════════════════╝
step "Clone Briven repository"

if [[ -d "$INSTALL_DIR/.git" ]]; then
    info "Already cloned — pulling latest..."
    git -C "$INSTALL_DIR" checkout -- requirements.txt 2>/dev/null || true
    git -C "$INSTALL_DIR" pull --ff-only || warn "Pull failed — continuing with existing code"
else
    info "Cloning from $REPO..."
    git clone "$REPO" "$INSTALL_DIR"
fi
cd "$INSTALL_DIR"
ok "Repository ready at $INSTALL_DIR"

# ╔══════════════════════════════════════════════════════════╗
# ║          Step 3 — Python venv + Dependencies             ║
# ╚══════════════════════════════════════════════════════════╝
step "Python environment & dependencies"

PYTHON=python3
PY_VER=$("$PYTHON" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
PY_MINOR=$("$PYTHON" -c 'import sys; print(sys.version_info.minor)')
info "Python $PY_VER detected"

# Recreate venv if Python version changed
if [[ -d .venv ]]; then
    VENV_PY=$(.venv/bin/python --version 2>/dev/null | awk '{print $2}' | cut -d. -f1,2 || echo "")
    if [[ "$VENV_PY" != "$PY_VER" ]]; then
        warn "Existing venv is Python $VENV_PY, need $PY_VER — recreating..."
        rm -rf .venv
    fi
fi

if [[ ! -d .venv ]]; then
    info "Creating virtual environment..."
    "$PYTHON" -m venv .venv
fi
# shellcheck disable=SC1091
source .venv/bin/activate

pip install --upgrade pip setuptools wheel --quiet

# ── Python 3.13+ compatibility patches ────────────────────
# These packages have no Python 3.13 support:
#   kokoro              — requires_python <3.13 (explicitly excluded)
#   langchain-unstructured — pins onnxruntime<=1.19.2 (no 3.13 wheel)
#   openai-whisper      — sdist-only, numba/torch chain breaks on 3.13

if [[ "$PY_MINOR" -ge 13 ]]; then
    info "Python 3.13+ detected — disabling incompatible packages..."
    sed -i 's/^kokoro/#kokoro/' requirements.txt
    sed -i 's/^langchain-unstructured/#langchain-unstructured/' requirements.txt
    sed -i 's/^openai-whisper/#openai-whisper/' requirements.txt
    ok "Disabled: kokoro, langchain-unstructured, openai-whisper"
fi

# Ensure /tmp has space (tmpfs can fill up on VPS)
if [[ -d /tmp ]] && command -v df >/dev/null 2>&1; then
    TMP_AVAIL=$(df /tmp 2>/dev/null | awk 'NR==2 {print int($4/1024)}' || echo "999999")
    if [[ "$TMP_AVAIL" -lt 512 ]]; then
        warn "/tmp has only ${TMP_AVAIL}MB free — using $INSTALL_DIR/tmp for pip"
        mkdir -p "$INSTALL_DIR/tmp"
        export TMPDIR="$INSTALL_DIR/tmp"
    fi
fi

info "Installing dependencies (this may take a few minutes)..."
if pip install -r requirements.txt 2>&1; then
    ok "Dependencies installed successfully"
else
    warn "First attempt failed — retrying with reduced packages..."
    # Disable heavy/optional packages that commonly cause conflicts
    sed -i 's/^kokoro/#kokoro/' requirements.txt
    sed -i 's/^langchain-unstructured/#langchain-unstructured/' requirements.txt
    sed -i 's/^openai-whisper/#openai-whisper/' requirements.txt
    sed -i 's/^sentence-transformers/#sentence-transformers/' requirements.txt
    if pip install -r requirements.txt 2>&1; then
        ok "Dependencies installed (some optional packages disabled)"
    else
        err "pip install failed. Run manually: cd $INSTALL_DIR && source .venv/bin/activate && pip install -r requirements.txt"
    fi
fi
[[ -f requirements2.txt ]] && pip install -r requirements2.txt --quiet 2>/dev/null || true
ok "All dependencies ready"

# ╔══════════════════════════════════════════════════════════╗
# ║                Step 4 — Tailscale                        ║
# ╚══════════════════════════════════════════════════════════╝
step "Tailscale zero-trust networking"

if ! command -v tailscale >/dev/null 2>&1; then
    info "Installing Tailscale..."
    curl -fsSL https://tailscale.com/install.sh | sh
fi
sudo systemctl enable --now tailscaled 2>/dev/null || true
ok "Tailscale daemon ready"

# ── Tailscale authentication ───────────────────────────────
TS_STATUS=$(tailscale status --json 2>/dev/null || echo '{}')
TS_BACKEND=$(printf '%s' "$TS_STATUS" | jq -r '.BackendState // ""' 2>/dev/null || echo "")

if [[ "$TS_BACKEND" == "Running" ]]; then
    ok "Tailscale already authenticated"
else
    printf "\n"
    draw_box << EOF
${BRED}${BOLD}Tailscale Authentication${RST}

Tailscale creates a private mesh network between your
devices. No ports are exposed to the public internet.

${BOLD}To get your auth key:${RST}
  1. Go to ${CYN}https://login.tailscale.com/admin/settings/keys${RST}
  2. Click "Generate auth key"
  3. Enable "Reusable" (recommended)
  4. Copy and paste the key below
EOF
    printf "\n"

    TS_OK=false
    for attempt in 1 2 3; do
        KEY=$(ask "  Auth key (tskey-auth-..., Enter to skip): ")

        if [[ -z "$KEY" ]]; then
            warn "Skipped — run later: sudo tailscale up"
            break
        fi

        if [[ "$KEY" != tskey-* ]]; then
            warn "Key should start with 'tskey-' — try again"
            continue
        fi

        if sudo tailscale up --authkey="$KEY" --accept-routes --accept-dns=false 2>/dev/null; then
            sleep 2
            VERIFY=$(tailscale status --json 2>/dev/null || echo '{}')
            VERIFY_STATE=$(printf '%s' "$VERIFY" | jq -r '.BackendState // ""' 2>/dev/null || echo "")
            if [[ "$VERIFY_STATE" == "Running" ]]; then
                TS_OK=true
                ok "Tailscale connected and verified"
                break
            fi
        fi

        if [[ "$attempt" -lt 3 ]]; then
            warn "Attempt $attempt/3 failed — try again..."
        else
            warn "Auth failed after 3 attempts — run later: sudo tailscale up"
        fi
    done
fi

# Get Tailscale IP
TS_IP=$(tailscale ip --4 2>/dev/null | head -1 | tr -d ' ' || echo "")
if [[ -z "$TS_IP" ]]; then
    warn "No Tailscale IP detected — service will bind to 127.0.0.1"
    TS_IP="127.0.0.1"
else
    ok "Tailscale IP: $TS_IP"
fi

# ╔══════════════════════════════════════════════════════════╗
# ║              Step 5 — Environment File                   ║
# ╚══════════════════════════════════════════════════════════╝
step "Environment configuration"

for d in . usr; do
    if [[ -f "$d/.env.example" && ! -f "$d/.env" ]]; then
        cp "$d/.env.example" "$d/.env"
        ok "Created $d/.env from template"
    fi
done
ok "Environment files ready"

# ╔══════════════════════════════════════════════════════════╗
# ║              Step 6 — LLM Provider Selection             ║
# ╚══════════════════════════════════════════════════════════╝
step "LLM provider API keys"

printf "\n"
draw_box << EOF
${BRED}${BOLD}LLM Provider Setup${RST}

Briven needs at least one LLM API key to function.
Select the providers you have keys for, then enter
each key when prompted.

${DIM}You can always add or change keys later in usr/.env${RST}
${DIM}Keys are stored locally and never sent anywhere else.${RST}
EOF
printf "\n"

KEY_COUNT=0

# Provider list: ENV_VAR|Display Name|Key hint|URL hint
PROVIDERS=(
    "API_KEY_OPENROUTER|OpenRouter (200+ models)|sk-or-...|openrouter.ai/keys"
    "API_KEY_ANTHROPIC|Anthropic (Claude)|sk-ant-...|console.anthropic.com"
    "API_KEY_XAI|xAI / Grok|xai-...|console.x.ai"
    "API_KEY_OPENAI|OpenAI (GPT-4o, o1, o3)|sk-...|platform.openai.com"
    "API_KEY_DEEPSEEK|DeepSeek|sk-...|platform.deepseek.com"
    "API_KEY_GOOGLE|Google Gemini|AIzaSy-...|aistudio.google.com"
    "API_KEY_GROQ|Groq (fast inference)|gsk_...|console.groq.com"
    "API_KEY_MISTRAL|Mistral AI|...|console.mistral.ai"
    "API_KEY_PERPLEXITY|Perplexity AI|pplx-...|perplexity.ai"
    "API_KEY_COHERE|Cohere|...|dashboard.cohere.com"
    "API_KEY_HUGGINGFACE|HuggingFace|hf_...|huggingface.co/settings"
    "API_KEY_SAMBANOVA|Sambanova|...|cloud.sambanova.ai"
)

# Display numbered provider list
printf "  ${BOLD}${WHT} #   %-28s %-14s %s${RST}\n" "Provider" "Key prefix" ""
printf "  ${DIM} ──  ──────────────────────────  ────────────── ${RST}\n"
for i in "${!PROVIDERS[@]}"; do
    IFS='|' read -r _env _name _hint _url <<< "${PROVIDERS[$i]}"
    printf "  ${BRED}${BOLD}%2d${RST}   %-28s ${DIM}%-14s${RST}\n" "$((i+1))" "$_name" "$_hint"
done
printf "\n"
dimtext "Tip: OpenRouter gives access to 200+ models with a single key"
printf "\n"

SELECTION=$(ask "  Select providers (e.g. 1,3,5 — Enter to skip): ")

if [[ -n "$SELECTION" ]]; then
    IFS=',' read -ra SELECTED <<< "$SELECTION"
    printf "\n"
    for num in "${SELECTED[@]}"; do
        num=$(printf '%s' "$num" | tr -d ' ')
        # Validate it's a number
        if ! [[ "$num" =~ ^[0-9]+$ ]]; then continue; fi
        idx=$((num - 1))
        if [[ "$idx" -ge 0 && "$idx" -lt "${#PROVIDERS[@]}" ]]; then
            IFS='|' read -r env_var name hint url <<< "${PROVIDERS[$idx]}"
            dimtext "Get key from: $url"
            val=$(ask "  ${name} API key (${hint}): ")
            if [[ -n "$val" ]]; then
                set_env "$env_var" "$val"
                KEY_COUNT=$((KEY_COUNT + 1))
                ok "$name key saved"
            fi
        fi
    done
fi

printf "\n"
if [[ "$KEY_COUNT" -gt 0 ]]; then
    ok "$KEY_COUNT API key(s) saved to usr/.env"
else
    warn "No API keys entered — add at least one later: nano $INSTALL_DIR/usr/.env"
fi

# ╔══════════════════════════════════════════════════════════╗
# ║          Step 7 — Messaging Channel Setup                ║
# ╚══════════════════════════════════════════════════════════╝
step "Messaging channels (optional)"

printf "\n"
draw_box << EOF
${BRED}${BOLD}Channel Integrations${RST}

Connect Briven to your messaging platforms.
Select the channels you want to set up.

${DIM}Skip this step if you only need the Web UI.${RST}
${DIM}You can configure channels later in usr/.env${RST}
EOF
printf "\n"

# Channel list: display_name|env_keys (pipe-separated pairs)
printf "  ${BOLD}${WHT} #   Channel          Required tokens${RST}\n"
printf "  ${DIM} ──  ───────────────  ──────────────────────────────────${RST}\n"
printf "  ${BRED}${BOLD} 1${RST}   Telegram         Bot token + Chat ID\n"
printf "  ${BRED}${BOLD} 2${RST}   WhatsApp         Token + Phone ID + Recipient\n"
printf "  ${BRED}${BOLD} 3${RST}   Discord          Webhook URL\n"
printf "  ${BRED}${BOLD} 4${RST}   Slack            Bot token + Channel\n"
printf "  ${BRED}${BOLD} 5${RST}   Email (SMTP)     SMTP host + credentials\n"
printf "\n"

CH_SELECTION=$(ask "  Select channels (e.g. 1,3 — Enter to skip): ")

if [[ -n "$CH_SELECTION" ]]; then
    IFS=',' read -ra CH_SELECTED <<< "$CH_SELECTION"
    printf "\n"
    for ch_num in "${CH_SELECTED[@]}"; do
        ch_num=$(printf '%s' "$ch_num" | tr -d ' ')
        if ! [[ "$ch_num" =~ ^[0-9]+$ ]]; then continue; fi
        case "$ch_num" in
            1)
                info "Telegram setup"
                dimtext "1. Open Telegram and talk to @BotFather"
                dimtext "2. Send /newbot and follow the prompts"
                dimtext "3. Copy the bot token and paste it below"
                printf "\n"
                TG_TOKEN=$(ask "  Bot token: ")
                if [[ -n "$TG_TOKEN" ]]; then
                    set_env "TELEGRAM_BOT_TOKEN" "$TG_TOKEN"
                    ok "Bot token saved"

                    # Validate token with getMe
                    TG_ME=$(curl -sf "https://api.telegram.org/bot${TG_TOKEN}/getMe" 2>/dev/null || echo "")
                    TG_BOT_NAME=$(printf '%s' "$TG_ME" | jq -r '.result.username // ""' 2>/dev/null || echo "")
                    if [[ -n "$TG_BOT_NAME" ]]; then
                        ok "Bot verified: @$TG_BOT_NAME"
                    else
                        warn "Could not verify bot token — check it later in usr/.env"
                    fi

                    # Generate pairing code (openssl avoids SIGPIPE from tr|head + pipefail)
                    PAIR_CODE="BRV-$(openssl rand -hex 3 2>/dev/null | tr '[:lower:]' '[:upper:]' || printf '%06d' $((RANDOM % 1000000)))"

                    # Clear old updates so we only see new ones
                    curl -sf "https://api.telegram.org/bot${TG_TOKEN}/getUpdates?offset=-1" > /dev/null 2>&1 || true
                    sleep 1
                    LAST_ID=$(curl -sf "https://api.telegram.org/bot${TG_TOKEN}/getUpdates" 2>/dev/null \
                        | jq -r '.result[-1].update_id // 0' 2>/dev/null || echo "0")
                    OFFSET=$((LAST_ID + 1))

                    printf "\n"
                    printf "  ${BRED}${BOLD}Pairing:${RST} briven pairing approve telegram ${BRED}${BOLD}%s${RST}\n" "$PAIR_CODE"
                    printf "\n"
                    dimtext "Open your bot in Telegram and send the command above."
                    dimtext "Waiting for pairing message (60s)..."
                    printf "\n"

                    TG_CHAT_ID=""
                    for _try in $(seq 1 30); do
                        UPDATES=$(curl -sf "https://api.telegram.org/bot${TG_TOKEN}/getUpdates?offset=${OFFSET}&timeout=2" 2>/dev/null || echo '{"result":[]}')
                        # Look for our pairing code in any message
                        TG_CHAT_ID=$(printf '%s' "$UPDATES" | jq -r \
                            "[.result[].message | select(.text != null) | select(.text | ascii_upcase | contains(\"$PAIR_CODE\"))] | .[0].chat.id // empty" \
                            2>/dev/null || echo "")
                        if [[ -n "$TG_CHAT_ID" ]]; then
                            break
                        fi
                    done

                    if [[ -n "$TG_CHAT_ID" ]]; then
                        set_env "TELEGRAM_CHAT_ID" "$TG_CHAT_ID"
                        ok "Telegram paired! Chat ID: $TG_CHAT_ID"
                    else
                        warn "Pairing timed out — set TELEGRAM_CHAT_ID manually in usr/.env"
                    fi
                fi
                ;;
            2)
                info "WhatsApp Business setup"
                dimtext "Get from: developers.facebook.com → WhatsApp → API Setup"
                val=$(ask "  WhatsApp token: ")
                [[ -n "$val" ]] && set_env "WHATSAPP_TOKEN" "$val" && ok "WhatsApp token saved"
                val=$(ask "  Phone number ID: ")
                [[ -n "$val" ]] && set_env "WHATSAPP_PHONE_ID" "$val" && ok "WhatsApp phone ID saved"
                val=$(ask "  Recipient number (+1234567890): ")
                [[ -n "$val" ]] && set_env "WHATSAPP_RECIPIENT" "$val" && ok "WhatsApp recipient saved"
                ;;
            3)
                info "Discord setup"
                dimtext "Server Settings → Integrations → Webhooks → New Webhook → Copy URL"
                val=$(ask "  Webhook URL: ")
                [[ -n "$val" ]] && set_env "DISCORD_WEBHOOK_URL" "$val" && ok "Discord webhook saved"
                ;;
            4)
                info "Slack setup"
                dimtext "Create app at: api.slack.com/apps → OAuth & Permissions"
                val=$(ask "  Bot token (xoxb-...): ")
                [[ -n "$val" ]] && set_env "SLACK_BOT_TOKEN" "$val" && ok "Slack bot token saved"
                val=$(ask "  Channel (#general): ")
                [[ -n "${val:-}" ]] && set_env "SLACK_CHANNEL" "$val" && ok "Slack channel saved"
                ;;
            5)
                info "Email (SMTP) setup"
                val=$(ask "  SMTP host (smtp.gmail.com): ")
                [[ -n "$val" ]] && set_env "EMAIL_SMTP_HOST" "$val"
                val=$(ask "  SMTP port (587): ")
                [[ -n "$val" ]] && set_env "EMAIL_SMTP_PORT" "$val"
                val=$(ask "  Email address: ")
                [[ -n "$val" ]] && set_env "EMAIL_USER" "$val"
                val=$(ask_secret "  Email password: ")
                [[ -n "$val" ]] && set_env "EMAIL_PASSWORD" "$val"
                ok "Email SMTP configured"
                ;;
        esac
    done
fi

# ╔══════════════════════════════════════════════════════════╗
# ║          Step 8 — UFW + Fail2ban Hardening               ║
# ╚══════════════════════════════════════════════════════════╝
step "Firewall & security hardening"

printf "\n"
draw_box << EOF
${BRED}${BOLD}Security Hardening${RST}

UFW (firewall) blocks all incoming traffic except SSH
and Tailscale. Fail2ban protects against brute-force.

${BOLD}Briven binds ONLY to your Tailscale IP${RST} — it is
never exposed on public interfaces.
EOF
printf "\n"

SETUP_UFW=$(ask "  Enable UFW firewall + Fail2ban? (Y/n): ")
SETUP_UFW="${SETUP_UFW:-Y}"

if [[ "${SETUP_UFW,,}" != "n" ]]; then
    # UFW configuration
    if command -v ufw >/dev/null 2>&1; then
        info "Configuring UFW firewall..."
        sudo ufw default deny incoming 2>/dev/null || true
        sudo ufw default allow outgoing 2>/dev/null || true
        sudo ufw allow ssh 2>/dev/null || true
        # Allow Tailscale subnet (100.64.0.0/10)
        sudo ufw allow in on tailscale0 2>/dev/null || true
        sudo ufw --force enable 2>/dev/null || true
        ok "UFW enabled — SSH + Tailscale allowed, all else denied"
    else
        warn "UFW not available — skipping firewall setup"
    fi

    # Fail2ban configuration
    if command -v fail2ban-client >/dev/null 2>&1; then
        info "Configuring Fail2ban..."
        if [[ ! -f /etc/fail2ban/jail.local ]]; then
            sudo tee /etc/fail2ban/jail.local > /dev/null << 'F2B'
[DEFAULT]
bantime  = 1h
findtime = 10m
maxretry = 5

[sshd]
enabled = true
port    = ssh
filter  = sshd
logpath = /var/log/auth.log
F2B
        fi
        sudo systemctl enable --now fail2ban 2>/dev/null || true
        ok "Fail2ban enabled — SSH brute-force protection active"
    else
        warn "Fail2ban not available — skipping"
    fi
else
    dimtext "Skipped firewall setup"
fi

# ╔══════════════════════════════════════════════════════════╗
# ║          Step 9 — Tailscale ACL + Systemd                ║
# ╚══════════════════════════════════════════════════════════╝
step "Tailscale ACL & system service"

# ── Tailscale ACL (optional) ──────────────────────────────
TS_API_KEY=""
for envfile in "$INSTALL_DIR/usr/.env" "$INSTALL_DIR/.env"; do
    if [[ -f "$envfile" ]]; then
        val=$(grep -E "^TAILSCALE_API_KEY=" "$envfile" 2>/dev/null | head -1 | cut -d= -f2- | tr -d '"' | tr -d "'" || true)
        if [[ -n "${val:-}" ]]; then
            TS_API_KEY="$val"
            break
        fi
    fi
done

if [[ -z "$TS_API_KEY" ]]; then
    printf "\n"
    draw_box << EOF
${BRED}${BOLD}Tailscale ACL (Optional)${RST}

ACL restricts Briven access to ${BOLD}tag:admin${RST} devices only.
Without ACL, any device on your tailnet can access Briven.

${BOLD}To get an API token:${RST}
  ${CYN}https://login.tailscale.com/admin/settings/keys${RST}
  → API access tokens → Generate
EOF
    printf "\n"

    TS_API_KEY=$(ask "  Tailscale API token (tskey-api-..., Enter to skip): ")
fi

if [[ -n "${TS_API_KEY:-}" ]]; then
    set_env "TAILSCALE_API_KEY" "$TS_API_KEY"
    ok "TAILSCALE_API_KEY saved"

    info "Applying zero-trust ACL policy..."
    ACL_OK=false
    for attempt in 1 2; do
        if "$INSTALL_DIR/.venv/bin/python" "$INSTALL_DIR/tools/tailscale.py" --apply-acl 2>&1; then
            ACL_OK=true
            break
        fi
        [[ "$attempt" -eq 1 ]] && sleep 2
    done

    if $ACL_OK; then
        ok "ACL applied — only tag:admin → tag:briven-server:$BRIVEN_PORT"
    else
        warn "ACL apply failed — run manually: python tools/tailscale.py --apply-acl"
    fi
else
    dimtext "Skipped ACL — any tailnet device can access Briven"
fi

# ── Systemd service ────────────────────────────────────────
info "Creating systemd service..."

sudo tee /etc/systemd/system/briven.service > /dev/null << UNIT
[Unit]
Description=Briven AI Agent Framework
After=network-online.target tailscaled.service
Wants=network-online.target tailscaled.service

[Service]
Type=simple
User=$RUN_USER
WorkingDirectory=$INSTALL_DIR
Environment="PATH=$INSTALL_DIR/.venv/bin:/usr/local/bin:/usr/bin:/bin"
ExecStart=$INSTALL_DIR/.venv/bin/uvicorn run_ui:app --host $TS_IP --port $BRIVEN_PORT
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal
SyslogIdentifier=briven

NoNewPrivileges=yes
ProtectSystem=strict
ReadWritePaths=$RUN_HOME
PrivateTmp=yes

[Install]
WantedBy=multi-user.target
UNIT

ok "Created /etc/systemd/system/briven.service"

# ╔══════════════════════════════════════════════════════════╗
# ║              Step 10 — Start & Verify                    ║
# ╚══════════════════════════════════════════════════════════╝
step "Start Briven"

sudo systemctl daemon-reload
sudo systemctl enable --now briven

info "Starting service..."
sleep 3

# ── Status check ───────────────────────────────────────────
SERVICE_OK=false
if sudo systemctl is-active --quiet briven; then
    SERVICE_OK=true
fi

# ╔══════════════════════════════════════════════════════════╗
# ║                    Final Summary                         ║
# ╚══════════════════════════════════════════════════════════╝
printf "\n\n"

if $SERVICE_OK; then
    draw_box << EOF
${GRN}${BOLD}✓  Installation Complete!${RST}

${BOLD}Briven is running and ready to use.${RST}

  ${BRED}${BOLD}Tailscale IP:${RST}  $TS_IP
  ${BRED}${BOLD}Web UI:${RST}        http://$TS_IP:$BRIVEN_PORT
  ${BRED}${BOLD}Status:${RST}        ${GRN}active (running)${RST}
EOF
else
    draw_box << EOF
${YEL}${BOLD}⚠  Installation Complete (service starting)${RST}

The service may still be initializing.

  ${BRED}${BOLD}Tailscale IP:${RST}  $TS_IP
  ${BRED}${BOLD}Web UI:${RST}        http://$TS_IP:$BRIVEN_PORT
  ${BRED}${BOLD}Status:${RST}        ${YEL}starting...${RST}
EOF
fi

printf "\n"
draw_box << EOF
${BOLD}Quick Reference${RST}

  ${BRED}Edit API keys:${RST}     nano $INSTALL_DIR/usr/.env
  ${BRED}Restart:${RST}           sudo systemctl restart briven
  ${BRED}Logs:${RST}              journalctl -u briven -f
  ${BRED}Status:${RST}            sudo systemctl status briven
  ${BRED}ACL status:${RST}        python tools/tailscale.py --acl-status
  ${BRED}Firewall:${RST}          sudo ufw status

${DIM}Tailscale keys: https://login.tailscale.com/admin/settings/keys${RST}
${DIM}Documentation:  https://github.com/flandriendev/briven${RST}
EOF

printf "\n"
printf "  ${BRED}${BOLD}Thank you for installing Briven!${RST}\n"
printf "  ${DIM}Open http://$TS_IP:$BRIVEN_PORT from any device on your tailnet.${RST}\n"
printf "\n"
