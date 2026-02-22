#!/usr/bin/env bash
# ============================================================
# Briven — Guided Zero-Trust VPS Installer
#
# Usage:
#   curl -fsSL https://raw.githubusercontent.com/flandriendev/briven/main/install.sh | bash
#
# Supported:
#   Ubuntu 22.04 / 24.04
#   Debian 12 / 13
#
# Features:
#   - Guided setup: Tailscale auth + LLM API keys asked during install
#   - Tailscale-only networking + ACL enforcement
#   - Idempotent: safe to re-run at any time
#   - System ready to use immediately after install completes
# ============================================================
set -euo pipefail

REPO="https://github.com/flandriendev/briven.git"
BRIVEN_PORT="${BRIVEN_PORT:-8000}"

# ── Colors (Briven red: RGB 221,63,42 / #dd3f2a) ────────────
BRED='\e[38;2;221;63;42m'
RED='\e[31m'
YEL='\e[33m'
GRN='\e[32m'
BOLD='\e[1m'
DIM='\e[2m'
RST='\e[0m'

info()  { printf "${BRED}[briven]${RST} %s\n" "$*"; }
ok()    { printf "${BRED}  ✓${RST} %s\n" "$*"; }
warn()  { printf "${YEL}[briven]${RST} %s\n" "$*"; }
err()   { printf "${RED}[briven] ERROR:${RST} %s\n" "$*" >&2; exit 1; }
step()  { printf "\n${BOLD}${BRED}[%s]${RST} ${BOLD}%s${RST}\n" "$1" "$2"; }

# ── Interactive input (works with curl | bash via /dev/tty) ──
ask() {
    local prompt="$1" val=""
    if [[ -t 0 ]]; then
        read -rp "$prompt" val
    elif [[ -e /dev/tty ]]; then
        read -rp "$prompt" val < /dev/tty
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

# ── Banner ────────────────────────────────────────────────────
printf "\n${BRED}${BOLD}"
cat << 'BANNER'
  ┌──────────────────────────────────────────────┐
  │       Briven — Zero-Trust VPS Installer       │
  │        github.com/flandriendev/briven         │
  └──────────────────────────────────────────────┘
BANNER
printf "${RST}\n"

# ── Detect distro ────────────────────────────────────────────
DISTRO=""
if grep -qi "ubuntu" /etc/os-release 2>/dev/null; then
    DISTRO="UBUNTU"
elif grep -qi "debian" /etc/os-release 2>/dev/null; then
    DISTRO="DEBIAN"
else
    err "Unsupported distro. Requires Ubuntu 22.04/24.04 or Debian 12/13."
fi
info "Detected: $DISTRO"

# ── Detect user / install path ───────────────────────────────
if [[ -n "${SUDO_USER:-}" && "${SUDO_USER:-}" != "root" ]]; then
    RUN_USER="$SUDO_USER"
    RUN_HOME=$(getent passwd "$SUDO_USER" | cut -d: -f6)
else
    RUN_USER="${USER:-root}"
    RUN_HOME="$HOME"
fi
INSTALL_DIR="${BRIVEN_DIR:-$RUN_HOME/briven}"
info "Install dir: $INSTALL_DIR (user: $RUN_USER)"

# ══════════════════════════════════════════════════════════════
# Step 1 — System dependencies
# ══════════════════════════════════════════════════════════════
step "1/10" "System dependencies"

sudo apt-get update -qq
sudo apt-get install -y -qq \
    git curl wget ca-certificates build-essential \
    python3 python3-venv python3-dev python3-pip \
    libssl-dev zlib1g-dev libbz2-dev libreadline-dev \
    libsqlite3-dev libncursesw5-dev libxml2-dev libxmlsec1-dev \
    libffi-dev liblzma-dev jq
ok "Base packages ready."

# ══════════════════════════════════════════════════════════════
# Step 2 — Clone / update repository
# ══════════════════════════════════════════════════════════════
step "2/10" "Clone Briven"

if [[ -d "$INSTALL_DIR/.git" ]]; then
    info "Already cloned — pulling latest..."
    git -C "$INSTALL_DIR" pull --ff-only || warn "Pull failed — continuing with existing code."
else
    git clone "$REPO" "$INSTALL_DIR"
fi
cd "$INSTALL_DIR"
ok "Repository ready at $INSTALL_DIR"

# ══════════════════════════════════════════════════════════════
# Step 3 — Python venv + dependencies
# ══════════════════════════════════════════════════════════════
step "3/10" "Python environment"

PYTHON=python3
PY_VER=$("$PYTHON" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
info "Python $PY_VER"

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

# ── Fix incompatible deps for Python >= 3.13 ─────────────────
PY_MINOR=$("$PYTHON" -c 'import sys; print(sys.version_info.minor)')
if [[ "$PY_MINOR" -ge 13 ]]; then
    info "Python 3.13+ detected — patching requirements for compatibility..."
    # 1. Disable kokoro (no 3.13 wheel)
    sed -i 's/^kokoro/#kokoro/' requirements.txt
    # 2. Disable langchain-unstructured (pins onnxruntime<=1.19.2, no 3.13 wheel)
    sed -i 's/^langchain-unstructured/#langchain-unstructured/' requirements.txt
    # 3. Upgrade unstructured (0.16.23 needs onnxruntime<=1.19.2 via transitive deps)
    sed -i 's/^unstructured\[all-docs\]==0.16.23/unstructured[all-docs]==0.20.8/' requirements.txt
    # 4. Unpin packages that conflict with unstructured 0.20.8
    sed -i 's/^markdown==.*/markdown/' requirements.txt
    sed -i 's/^unstructured-client==.*/unstructured-client/' requirements.txt
    sed -i 's/^pypdf==.*/pypdf/' requirements.txt
    sed -i 's/^browser-use==.*/browser-use/' requirements.txt
    ok "Patched: kokoro+langchain-unstructured disabled, unstructured→0.20.8, conflict pins removed"
fi

info "Installing dependencies (this may take a few minutes)..."
if pip install -r requirements.txt --quiet 2>&1; then
    ok "Dependencies installed."
else
    # Fallback: try disabling kokoro + upgrading unstructured
    warn "pip install failed — retrying with compatibility patches..."
    sed -i 's/^kokoro/#kokoro/' requirements.txt
    sed -i 's/^langchain-unstructured/#langchain-unstructured/' requirements.txt
    sed -i 's/^unstructured\[all-docs\]==0.16.23/unstructured[all-docs]==0.20.8/' requirements.txt
    sed -i 's/^markdown==.*/markdown/' requirements.txt
    sed -i 's/^unstructured-client==.*/unstructured-client/' requirements.txt
    sed -i 's/^pypdf==.*/pypdf/' requirements.txt
    sed -i 's/^browser-use==.*/browser-use/' requirements.txt
    if pip install -r requirements.txt --quiet 2>&1; then
        ok "Dependencies installed (kokoro/TTS disabled for compatibility)."
    else
        err "pip install failed. Check requirements.txt and Python version."
    fi
fi
[[ -f requirements2.txt ]] && pip install -r requirements2.txt --quiet
ok "All dependencies ready."

# ══════════════════════════════════════════════════════════════
# Step 4 — Tailscale
# ══════════════════════════════════════════════════════════════
step "4/10" "Tailscale"

if ! command -v tailscale >/dev/null 2>&1; then
    info "Installing Tailscale..."
    curl -fsSL https://tailscale.com/install.sh | sh
fi
sudo systemctl enable --now tailscaled 2>/dev/null || true
ok "Tailscale ready."

# ══════════════════════════════════════════════════════════════
# Step 5 — Tailscale authentication (guided, with retry)
# ══════════════════════════════════════════════════════════════
step "5/10" "Tailscale authentication"

TS_STATUS=$(tailscale status --json 2>/dev/null || echo '{}')
TS_BACKEND=$(printf '%s' "$TS_STATUS" | jq -r '.BackendState // ""' 2>/dev/null || echo "")

if [[ "$TS_BACKEND" == "Running" ]]; then
    ok "Tailscale already authenticated."
else
    printf '\n'
    printf '  \e[38;2;221;63;42m%s\e[0m\n' "Tailscale connects your server to a private, zero-trust mesh network."
    printf '  \e[38;2;221;63;42m%s\e[0m\n' "No ports are exposed to the public internet."
    printf '\n'
    printf '  \e[38;2;221;63;42m%s\e[0m\n' "1. Go to: https://login.tailscale.com/admin/settings/keys"
    printf '  \e[38;2;221;63;42m%s\e[0m\n' "2. Create a new auth key (reusable recommended)"
    printf '  \e[38;2;221;63;42m%s\e[0m\n' "3. Paste it below"
    printf '\n'

    TS_OK=false
    for attempt in 1 2 3; do
        KEY=$(ask "  Auth key (tskey-auth-...): ")

        if [[ -z "$KEY" ]]; then
            warn "Skipped — run later: sudo tailscale up"
            break
        fi

        if [[ "$KEY" != tskey-* ]]; then
            warn "Key should start with 'tskey-' — try again."
            continue
        fi

        if sudo tailscale up --authkey="$KEY" --accept-routes --accept-dns=false 2>/dev/null; then
            # Verify connection
            sleep 2
            VERIFY=$(tailscale status --json 2>/dev/null || echo '{}')
            VERIFY_STATE=$(printf '%s' "$VERIFY" | jq -r '.BackendState // ""' 2>/dev/null || echo "")
            if [[ "$VERIFY_STATE" == "Running" ]]; then
                TS_OK=true
                ok "Tailscale connected and verified."
                break
            fi
        fi

        if [[ "$attempt" -lt 3 ]]; then
            warn "Attempt $attempt failed — try again (${attempt}/3)..."
        else
            warn "Auth failed after 3 attempts — run later: sudo tailscale up"
        fi
    done
fi

# Get Tailscale IP
TS_IP=$(tailscale ip --4 2>/dev/null | head -1 | tr -d ' ' || echo "")
if [[ -z "$TS_IP" ]]; then
    warn "No Tailscale IP detected. Service will bind to 127.0.0.1."
    TS_IP="127.0.0.1"
else
    ok "Tailscale IP: $TS_IP"
fi

# ══════════════════════════════════════════════════════════════
# Step 6 — Environment file
# ══════════════════════════════════════════════════════════════
step "6/10" "Environment"

for d in . usr; do
    if [[ -f "$d/.env.example" && ! -f "$d/.env" ]]; then
        cp "$d/.env.example" "$d/.env"
        ok "Created $d/.env from template."
    fi
done

# ══════════════════════════════════════════════════════════════
# Step 7 — LLM API keys (guided prompts)
# ══════════════════════════════════════════════════════════════
step "7/10" "LLM API keys"

printf '\n'
printf '  \e[38;2;221;63;42m%s\e[0m\n' "Briven needs at least one LLM API key to work."
printf '  \e[38;2;221;63;42m%s\e[0m\n' "You can always add or change keys later in usr/.env"
printf '\n'

KEY_COUNT=0

# Provider list: ENV_VAR|Display Name|Key hint
PROVIDERS=(
    "API_KEY_OPENROUTER|OpenRouter|sk-or-..."
    "API_KEY_ANTHROPIC|Anthropic (Claude)|sk-ant-..."
    "API_KEY_XAI|xAI / Grok|xai-..."
    "API_KEY_OPENAI|OpenAI|sk-..."
    "API_KEY_DEEPSEEK|DeepSeek|sk-..."
    "API_KEY_GOOGLE|Google Gemini|AIzaSy-..."
    "API_KEY_GROQ|Groq|gsk_..."
    "API_KEY_MISTRAL|Mistral AI|..."
    "API_KEY_PERPLEXITY|Perplexity AI|pplx-..."
    "API_KEY_COHERE|Cohere|..."
    "API_KEY_HUGGINGFACE|HuggingFace|hf_..."
)

# Display numbered provider list
printf '  \e[1m%-4s %-22s %s\e[0m\n' "#" "Provider" "Key prefix"
printf '  \e[2m%s\e[0m\n' "──────────────────────────────────────"
for i in "${!PROVIDERS[@]}"; do
    IFS='|' read -r _env _name _hint <<< "${PROVIDERS[$i]}"
    printf '  %-4s %-22s \e[2m%s\e[0m\n' "$((i+1))." "$_name" "$_hint"
done
printf '\n'

SELECTION=$(ask "  Which providers? (e.g. 1,3,5 — Enter to skip): ")

if [[ -n "$SELECTION" ]]; then
    IFS=',' read -ra SELECTED <<< "$SELECTION"
    printf '\n'
    for num in "${SELECTED[@]}"; do
        num=$(printf '%s' "$num" | tr -d ' ')
        idx=$((num - 1))
        if [[ "$idx" -ge 0 && "$idx" -lt "${#PROVIDERS[@]}" ]]; then
            IFS='|' read -r env_var name hint <<< "${PROVIDERS[$idx]}"
            val=$(ask "  [$num] $name API key ($hint): ")
            if [[ -n "$val" ]]; then
                set_env "$env_var" "$val"
                KEY_COUNT=$((KEY_COUNT + 1))
                ok "$name saved"
            fi
        fi
    done
fi

printf '\n'
if [[ "$KEY_COUNT" -gt 0 ]]; then
    ok "$KEY_COUNT API key(s) saved to usr/.env"
else
    warn "No API keys entered — add at least one later: nano $INSTALL_DIR/usr/.env"
fi

# ══════════════════════════════════════════════════════════════
# Step 8 — Tailscale ACL (zero-trust policy)
# ══════════════════════════════════════════════════════════════
step "8/10" "Tailscale ACL"

# Check if API key already in .env
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
    printf '\n'
    printf '  \e[38;2;221;63;42m%s\e[0m\n' "Optional: Tailscale ACL restricts access to tag:admin devices only."
    printf '  \e[38;2;221;63;42m%s\e[0m\n' "Go to: https://login.tailscale.com/admin/settings/keys → API access tokens"
    printf '\n'

    TS_API_KEY=$(ask "  API key (tskey-api-..., or Enter to skip): ")
fi

if [[ -n "${TS_API_KEY:-}" ]]; then
    set_env "TAILSCALE_API_KEY" "$TS_API_KEY"
    ok "TAILSCALE_API_KEY saved to usr/.env"

    info "Applying Briven zero-trust ACL policy..."
    ACL_OK=false
    for attempt in 1 2; do
        if "$INSTALL_DIR/.venv/bin/python" "$INSTALL_DIR/tools/tailscale.py" --apply-acl 2>&1; then
            ACL_OK=true
            break
        fi
        [[ "$attempt" -eq 1 ]] && sleep 2
    done

    if $ACL_OK; then
        ok "Tailscale ACL applied — only tag:admin → tag:briven-server:$BRIVEN_PORT allowed."
    else
        warn "ACL apply failed — run manually: python tools/tailscale.py --apply-acl"
    fi
else
    warn "Skipped ACL — add TAILSCALE_API_KEY later and run: python tools/tailscale.py --apply-acl"
fi

# ══════════════════════════════════════════════════════════════
# Step 9 — Systemd service
# ══════════════════════════════════════════════════════════════
step "9/10" "Systemd service"

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

# ══════════════════════════════════════════════════════════════
# Step 10 — Enable + start
# ══════════════════════════════════════════════════════════════
step "10/10" "Start Briven"

sudo systemctl daemon-reload
sudo systemctl enable --now briven

sleep 3
if sudo systemctl is-active --quiet briven; then
    ok "Briven is running."
else
    warn "Service may still be starting. Check: journalctl -u briven -f"
fi

# ══════════════════════════════════════════════════════════════
# Done
# ══════════════════════════════════════════════════════════════
printf "\n${BRED}${BOLD}"
cat << 'DONE'
  ┌──────────────────────────────────────────────┐
  │            Installation complete!              │
  └──────────────────────────────────────────────┘
DONE
printf "${RST}\n"

printf "  ${BRED}${BOLD}Tailscale IP:${RST}  %s\n" "$TS_IP"
printf "  ${BRED}${BOLD}Web UI:${RST}       http://%s:%s\n" "$TS_IP" "$BRIVEN_PORT"
printf "\n"
printf "  ${BOLD}Quick reference:${RST}\n"
printf "    Edit API keys:   nano %s/usr/.env\n" "$INSTALL_DIR"
printf "    Restart:          sudo systemctl restart briven\n"
printf "    Logs:             journalctl -u briven -f\n"
printf "    ACL status:       python tools/tailscale.py --acl-status\n"
printf "\n"
printf "  ${DIM}Tailscale keys: https://login.tailscale.com/admin/settings/keys${RST}\n"
printf "\n"
