#!/usr/bin/env bash
# ============================================================
# Briven — Zero-Trust VPS Installer
#
# Usage:
#   curl -fsSL https://raw.githubusercontent.com/flandriendev/briven/main/install.sh | bash
#
# Supported:
#   Ubuntu 24.04  → Python 3.12 via deadsnakes PPA
#   Debian 13     → System Python 3.13 + auto kokoro fallback
# Security: Tailscale-only networking + ACL enforcement
# Idempotent: Safe to re-run at any time
# ============================================================
set -euo pipefail

REPO="https://github.com/flandriendev/briven.git"
BRIVEN_PORT="${BRIVEN_PORT:-8000}"

# ── Colors (Briven red: RGB 221,63,42) ───────────────────────
BRED='\e[38;2;221;63;42m'
RED='\e[31m'
YEL='\e[33m'
BOLD='\e[1m'
DIM='\e[2m'
RST='\e[0m'

info()  { printf "${BRED}[briven]${RST} %s\n" "$*"; }
ok()    { printf "${BRED}  ✓${RST} %s\n" "$*"; }
warn()  { printf "${YEL}[briven]${RST} %s\n" "$*"; }
err()   { printf "${RED}[briven] ERROR:${RST} %s\n" "$*" >&2; exit 1; }
step()  { printf "\n${BOLD}${BRED}[%s]${RST} ${BOLD}%s${RST}\n" "$1" "$2"; }

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
    err "Unsupported distro. Requires Ubuntu 24.04 or Debian 13 (Trixie)."
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
step "1/9" "System dependencies"

sudo apt-get update -qq
sudo apt-get install -y -qq git curl ca-certificates build-essential
ok "Base packages ready."

# ══════════════════════════════════════════════════════════════
# Step 2 — Python
# ══════════════════════════════════════════════════════════════
step "2/9" "Python"

PYTHON=""

if [[ "$DISTRO" == "UBUNTU" ]]; then
    # Ubuntu 24.04 → Python 3.12 via deadsnakes PPA
    if ! apt-cache show python3.12 >/dev/null 2>&1; then
        info "Adding deadsnakes PPA for Python 3.12..."
        sudo apt-get install -y -qq software-properties-common
        sudo add-apt-repository -y ppa:deadsnakes/ppa
        sudo apt-get update -qq
    fi
    sudo apt-get install -y -qq python3.12 python3.12-venv python3.12-dev
    PYTHON=python3.12
    ok "Python 3.12 (Ubuntu / deadsnakes)"

elif [[ "$DISTRO" == "DEBIAN" ]]; then
    # Debian 13 (Trixie) → system Python 3.13
    sudo apt-get install -y -qq python3 python3-venv python3-dev
    PYTHON=python3
    PYVER=$("$PYTHON" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
    ok "Python $PYVER (Debian system)"
fi

"$PYTHON" --version || err "Python not found after install."

# ══════════════════════════════════════════════════════════════
# Step 3 — Clone / update repository
# ══════════════════════════════════════════════════════════════
step "3/9" "Clone Briven"

if [[ -d "$INSTALL_DIR/.git" ]]; then
    info "Already cloned — pulling latest..."
    git -C "$INSTALL_DIR" pull --ff-only || warn "Pull failed — continuing with existing code."
else
    git clone "$REPO" "$INSTALL_DIR"
fi
cd "$INSTALL_DIR"
ok "Repository ready at $INSTALL_DIR"

# ══════════════════════════════════════════════════════════════
# Step 4 — Venv + dependencies (with kokoro fallback)
# ══════════════════════════════════════════════════════════════
step "4/9" "Python environment"

# Recreate venv if Python version changed
if [[ -d .venv ]]; then
    VENV_PY=$(.venv/bin/python --version 2>/dev/null | awk '{print $2}' | cut -d. -f1,2 || echo "")
    WANT_PY=$("$PYTHON" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
    if [[ "$VENV_PY" != "$WANT_PY" ]]; then
        warn "Existing venv is Python $VENV_PY, need $WANT_PY — recreating..."
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

info "Installing dependencies..."
PIP_LOG=$(mktemp)
if pip install -r requirements.txt > "$PIP_LOG" 2>&1; then
    ok "Dependencies installed."
else
    if grep -qi "kokoro" "$PIP_LOG"; then
        warn "kokoro failed on Python 3.13 — pinning kokoro==0.7.4..."
        sed -i 's/kokoro[^#]*$/kokoro==0.7.4/' requirements.txt
        if pip install -r requirements.txt > "$PIP_LOG" 2>&1; then
            ok "Dependencies installed (kokoro pinned to 0.7.4)."
        else
            cat "$PIP_LOG" >&2
            err "pip install failed even with kokoro pinned. See output above."
        fi
    else
        cat "$PIP_LOG" >&2
        err "pip install failed. See output above."
    fi
fi
[[ -f requirements2.txt ]] && pip install -r requirements2.txt --quiet
rm -f "$PIP_LOG"

# Environment files
for d in . usr; do
    if [[ -f "$d/.env.example" && ! -f "$d/.env" ]]; then
        cp "$d/.env.example" "$d/.env"
        ok "Created $d/.env from template."
    fi
done

# ══════════════════════════════════════════════════════════════
# Step 5 — Tailscale
# ══════════════════════════════════════════════════════════════
step "5/9" "Tailscale"

if ! command -v tailscale >/dev/null 2>&1; then
    info "Installing Tailscale..."
    curl -fsSL https://tailscale.com/install.sh | sh
fi
sudo systemctl start tailscaled || true
ok "Tailscale ready."

# ══════════════════════════════════════════════════════════════
# Step 6 — Tailscale authentication
# ══════════════════════════════════════════════════════════════
step "6/9" "Tailscale authentication"

TS_STATUS=$(tailscale status 2>&1 || true)

if echo "$TS_STATUS" | grep -qE "NeedsLogin|stopped|not logged in|failed"; then
    printf '\n'
    printf '\e[38;2;221;63;42m%s\e[0m\n' \
        "  Go to https://login.tailscale.com/admin/settings/keys"
    printf '\e[38;2;221;63;42m%s\e[0m\n' \
        "  → create new key (reusable/ephemeral) → paste here:"
    printf '\n'

    KEY=""
    if [[ -t 0 ]]; then
        read -rp "  Auth key: " KEY
    elif [[ -e /dev/tty ]]; then
        read -rp "  Auth key: " KEY < /dev/tty
    else
        warn "Non-interactive — run later: sudo tailscale up"
    fi

    if [[ -n "${KEY:-}" ]]; then
        if sudo tailscale up --authkey="$KEY" --accept-routes --accept-dns=false; then
            ok "Tailscale connected."
        else
            warn "Auth failed — retry: sudo tailscale up"
        fi
    fi
else
    ok "Tailscale already authenticated."
fi

TS_IP=$(tailscale ip --4 2>/dev/null | head -1 | awk '{print $1}' || echo "")
if [[ -z "$TS_IP" ]]; then
    warn "No Tailscale IP detected. Service will bind to 127.0.0.1."
    TS_IP="127.0.0.1"
else
    ok "Tailscale IP: $TS_IP"
fi

# ══════════════════════════════════════════════════════════════
# Step 7 — Tailscale ACL (zero-trust policy)
# ══════════════════════════════════════════════════════════════
step "7/9" "Tailscale ACL"

# Read API key from .env or prompt
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
    printf '\e[38;2;221;63;42m%s\e[0m\n' \
        "  Tailscale ACL enforcement requires an API access token."
    printf '\e[38;2;221;63;42m%s\e[0m\n' \
        "  Go to https://login.tailscale.com/admin/settings/keys → API access tokens"
    printf '\e[38;2;221;63;42m%s\e[0m\n' \
        "  → Generate access token → paste here (or press Enter to skip):"
    printf '\n'

    if [[ -t 0 ]]; then
        read -rp "  API key: " TS_API_KEY
    elif [[ -e /dev/tty ]]; then
        read -rp "  API key: " TS_API_KEY < /dev/tty
    fi
fi

if [[ -n "${TS_API_KEY:-}" ]]; then
    # Persist to usr/.env
    ENV_FILE="$INSTALL_DIR/usr/.env"
    if [[ -f "$ENV_FILE" ]]; then
        if grep -q "^TAILSCALE_API_KEY=" "$ENV_FILE" 2>/dev/null; then
            sed -i "s|^TAILSCALE_API_KEY=.*|TAILSCALE_API_KEY=$TS_API_KEY|" "$ENV_FILE"
        else
            printf '\nTAILSCALE_API_KEY=%s\n' "$TS_API_KEY" >> "$ENV_FILE"
        fi
        ok "TAILSCALE_API_KEY saved to usr/.env"
    fi

    # Apply ACL via tools/tailscale.py
    info "Applying Briven zero-trust ACL policy..."
    ACL_RESULT=""
    ACL_OK=false
    for attempt in 1 2; do
        ACL_RESULT=$("$INSTALL_DIR/.venv/bin/python" "$INSTALL_DIR/tools/tailscale.py" --apply-acl 2>&1) && ACL_OK=true && break
        if [[ "$attempt" -eq 1 ]]; then
            warn "ACL apply attempt $attempt failed — retrying..."
            sleep 2
        fi
    done

    if $ACL_OK; then
        ok "Tailscale ACL applied — only tag:admin → tag:briven-server:$BRIVEN_PORT allowed."
    else
        warn "ACL apply failed after 2 attempts: $ACL_RESULT"
        warn "Apply manually later: python tools/tailscale.py --apply-acl"
    fi
else
    warn "No Tailscale API key — skipping ACL enforcement."
    warn "Add TAILSCALE_API_KEY to usr/.env and run: python tools/tailscale.py --apply-acl"
fi

# ══════════════════════════════════════════════════════════════
# Step 8 — Systemd service
# ══════════════════════════════════════════════════════════════
step "8/9" "Systemd service"

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
# Step 9 — Enable + start
# ══════════════════════════════════════════════════════════════
step "9/9" "Start Briven"

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
printf "  ${BOLD}Next steps:${RST}\n"
printf "  1. Edit API keys:   nano %s/usr/.env\n" "$INSTALL_DIR"
printf "  2. Restart:          sudo systemctl restart briven\n"
printf "  3. Logs:             journalctl -u briven -f\n"
printf "  4. ACL status:       python tools/tailscale.py --acl-status\n"
printf "\n"
printf "  ${DIM}Tailscale keys: https://login.tailscale.com/admin/settings/keys${RST}\n"
printf "\n"
