#!/usr/bin/env bash
# ============================================================
# Briven — Zero-Trust VPS Installer
#
# Usage:
#   curl -fsSL https://raw.githubusercontent.com/flandriendev/briven/main/install.sh | bash
#
# Target:  Fresh Ubuntu/Debian VPS (sudo access assumed)
# Also:    macOS (skips systemd, prints manual start commands)
# Security: Tailscale-only networking — no ports exposed
# Idempotent: Safe to re-run at any time
# ============================================================
set -eo pipefail

REPO="https://github.com/flandriendev/briven.git"
INSTALL_DIR="${BRIVEN_DIR:-$HOME/briven}"
PYTHON="${PYTHON:-python3}"
BRIVEN_PORT="${BRIVEN_PORT:-8000}"

# ── Colors ────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
CYAN='\033[0;36m'; BOLD='\033[1m'; DIM='\033[2m'; RESET='\033[0m'

info()    { echo -e "${CYAN}[briven]${RESET} $*"; }
success() { echo -e "${GREEN}  ✓${RESET} $*"; }
warn()    { echo -e "${YELLOW}[briven]${RESET} $*"; }
die()     { echo -e "${RED}[briven] ERROR:${RESET} $*" >&2; exit 1; }
step()    { echo -e "\n${BOLD}${CYAN}[$1]${RESET} ${BOLD}$2${RESET}"; }

# ── Banner ────────────────────────────────────────────────────
echo ""
echo -e "${BOLD}${CYAN}"
cat << 'BANNER'
  ┌──────────────────────────────────────────────┐
  │       Briven — Zero-Trust VPS Installer       │
  │        github.com/flandriendev/briven         │
  └──────────────────────────────────────────────┘
BANNER
echo -e "${RESET}"

# ── Detect platform ──────────────────────────────────────────
OS="$(uname -s)"
IS_LINUX=false
IS_MAC=false
if [[ "$OS" == "Linux" ]]; then
    IS_LINUX=true
    command -v apt-get >/dev/null 2>&1 || die "Only Debian/Ubuntu (apt) is supported."
elif [[ "$OS" == "Darwin" ]]; then
    IS_MAC=true
else
    die "Unsupported OS: $OS"
fi

# ══════════════════════════════════════════════════════════════
# Step 1 — System dependencies
# ══════════════════════════════════════════════════════════════
step "1/10" "System dependencies"

if $IS_LINUX; then
    DEPS=(git curl python3 python3-pip python3-venv python3-dev build-essential)
    MISSING=()
    for dep in "${DEPS[@]}"; do
        if ! dpkg-query -W -f='${Status}' "$dep" 2>/dev/null | grep -q "ok installed"; then
            MISSING+=("$dep")
        fi
    done
    if [[ ${#MISSING[@]} -gt 0 ]]; then
        info "Installing: ${MISSING[*]}"
        sudo apt-get update -qq
        sudo apt-get install -y -qq "${MISSING[@]}"
    fi
    success "System packages ready."
else
    command -v git >/dev/null 2>&1 || die "git required. Install: brew install git"
    command -v "$PYTHON" >/dev/null 2>&1 || die "Python 3 required. Install: brew install python"
    success "System packages ready (macOS)."
fi

# Verify Python version
command -v "$PYTHON" >/dev/null 2>&1 || die "Python 3 not found."
PYVER=$("$PYTHON" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
PYMAJOR="${PYVER%%.*}"
PYMINOR="${PYVER##*.}"
[[ "$PYMAJOR" -ge 3 && "$PYMINOR" -ge 10 ]] || die "Python 3.10+ required (got $PYVER)."
success "Python $PYVER"

# ══════════════════════════════════════════════════════════════
# Step 2 — Install Tailscale
# ══════════════════════════════════════════════════════════════
step "2/10" "Install Tailscale"

if command -v tailscale >/dev/null 2>&1; then
    success "Tailscale already installed."
else
    if $IS_LINUX; then
        info "Installing Tailscale..."
        curl -fsSL https://tailscale.com/install.sh | sh
        success "Tailscale installed."
    else
        echo ""
        echo -e "  ${YELLOW}macOS:${RESET} Install Tailscale from the App Store or:"
        echo "    brew install --cask tailscale"
        echo ""
        warn "Tailscale not found — continuing without it."
    fi
fi

# ══════════════════════════════════════════════════════════════
# Step 3 — Start Tailscale daemon
# ══════════════════════════════════════════════════════════════
step "3/10" "Tailscale daemon"

if $IS_LINUX; then
    if ! systemctl is-active --quiet tailscaled 2>/dev/null; then
        info "Starting tailscaled..."
        sudo systemctl enable --now tailscaled
    fi
    success "Tailscale daemon running."
else
    info "On macOS, ensure the Tailscale app is running."
fi

# ══════════════════════════════════════════════════════════════
# Step 4 — Clone / update repository
# ══════════════════════════════════════════════════════════════
step "4/10" "Clone Briven"

if [[ -d "$INSTALL_DIR/.git" ]]; then
    info "Already cloned at $INSTALL_DIR — pulling latest..."
    git -C "$INSTALL_DIR" pull --ff-only || warn "Pull failed — continuing with existing code."
else
    info "Cloning into $INSTALL_DIR ..."
    git clone "$REPO" "$INSTALL_DIR"
fi
cd "$INSTALL_DIR"
success "Repository ready."

# ══════════════════════════════════════════════════════════════
# Step 5 — Python venv + dependencies
# ══════════════════════════════════════════════════════════════
step "5/10" "Python environment"

if [[ ! -d .venv ]]; then
    info "Creating virtual environment..."
    "$PYTHON" -m venv .venv
fi
# shellcheck disable=SC1091
source .venv/bin/activate

info "Installing dependencies (this may take a minute)..."
pip install --upgrade pip --quiet
pip install -r requirements.txt --quiet
[[ -f requirements2.txt ]] && pip install -r requirements2.txt --quiet
success "Dependencies installed."

# ══════════════════════════════════════════════════════════════
# Step 6 — Environment file
# ══════════════════════════════════════════════════════════════
step "6/10" "Environment file"

ENV_DIR="$INSTALL_DIR/usr"
ENV_FILE="$ENV_DIR/.env"
ENV_EXAMPLE="$ENV_DIR/.env.example"

mkdir -p "$ENV_DIR"
if [[ ! -f "$ENV_FILE" ]]; then
    if [[ -f "$ENV_EXAMPLE" ]]; then
        cp "$ENV_EXAMPLE" "$ENV_FILE"
        success ".env created from template."
    else
        warn "No .env.example found. Create $ENV_FILE manually."
    fi
else
    success ".env already exists — skipping."
fi

# ══════════════════════════════════════════════════════════════
# Step 7 — Tailscale authentication
# ══════════════════════════════════════════════════════════════
step "7/10" "Tailscale authentication"

TS_CONNECTED=false

if command -v tailscale >/dev/null 2>&1; then
    TS_STATUS=$(tailscale status 2>&1 || true)

    if echo "$TS_STATUS" | grep -qE "Tailscale is stopped|NeedsLogin|not logged in|failed"; then
        echo ""
        echo -e "  ${BOLD}${YELLOW}Tailscale needs authentication.${RESET}"
        echo ""
        echo -e "  Go to: ${BOLD}https://login.tailscale.com/admin/settings/keys${RESET}"
        echo -e "  Create a new key (reusable or ephemeral recommended)"
        echo -e "  Copy & paste it here now:"
        echo ""

        # Read from /dev/tty so this works when piped from curl
        TS_KEY=""
        if [[ -t 0 ]]; then
            read -rp "  Tailscale auth key: " TS_KEY
        elif [[ -e /dev/tty ]]; then
            read -rp "  Tailscale auth key: " TS_KEY < /dev/tty
        else
            warn "Non-interactive shell — skipping Tailscale auth prompt."
            warn "Run manually after install:  sudo tailscale up"
        fi
        echo ""

        if [[ -n "${TS_KEY:-}" ]]; then
            info "Authenticating with Tailscale..."
            if sudo tailscale up --authkey="$TS_KEY" --accept-routes --accept-dns=false 2>&1; then
                TS_CONNECTED=true
                success "Tailscale connected."
            else
                warn "First attempt failed — retrying in 3s..."
                sleep 3
                if sudo tailscale up --authkey="$TS_KEY" --accept-routes --accept-dns=false 2>&1; then
                    TS_CONNECTED=true
                    success "Tailscale connected (retry succeeded)."
                else
                    warn "Authentication failed. Run manually:  sudo tailscale up"
                fi
            fi
        else
            warn "No key entered. Run later:  sudo tailscale up"
        fi
    else
        TS_CONNECTED=true
        success "Tailscale already authenticated."
    fi
else
    warn "Tailscale not found — skipping authentication."
fi

# ══════════════════════════════════════════════════════════════
# Step 8 — Get Tailscale IP
# ══════════════════════════════════════════════════════════════
step "8/10" "Tailscale IP"

TS_IP=""
if command -v tailscale >/dev/null 2>&1; then
    TS_IP=$(tailscale ip -4 2>/dev/null || echo "")
fi

if [[ -n "$TS_IP" ]]; then
    success "Tailscale IP: $TS_IP"

    # Persist host binding in usr/.env
    if [[ -f "$ENV_FILE" ]]; then
        if grep -q "^WEB_UI_HOST=" "$ENV_FILE" 2>/dev/null; then
            sed -i.bak "s|^WEB_UI_HOST=.*|WEB_UI_HOST=$TS_IP|" "$ENV_FILE" && rm -f "$ENV_FILE.bak"
        else
            printf '\nWEB_UI_HOST=%s\n' "$TS_IP" >> "$ENV_FILE"
        fi
        info "Wrote WEB_UI_HOST=$TS_IP to usr/.env"
    fi
else
    warn "No Tailscale IP detected. Briven will bind to localhost only."
    warn "After connecting Tailscale, re-run this script to update."
fi

# ══════════════════════════════════════════════════════════════
# Step 9 — Create systemd service (Linux only)
# ══════════════════════════════════════════════════════════════
step "9/10" "Systemd service"

if $IS_LINUX; then
    SERVICE_FILE="/etc/systemd/system/briven.service"
    RUN_USER="${SUDO_USER:-$USER}"
    RUN_HOME=$(eval echo "~$RUN_USER")
    BIND_HOST="${TS_IP:-localhost}"

    sudo tee "$SERVICE_FILE" > /dev/null << UNIT
[Unit]
Description=Briven AI Agent Framework
After=network-online.target tailscaled.service
Wants=network-online.target tailscaled.service

[Service]
Type=simple
User=$RUN_USER
Group=$RUN_USER
WorkingDirectory=$INSTALL_DIR
Environment="PATH=$INSTALL_DIR/.venv/bin:/usr/local/bin:/usr/bin:/bin"
ExecStart=$INSTALL_DIR/.venv/bin/python $INSTALL_DIR/run_ui.py --host $BIND_HOST --port $BRIVEN_PORT
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal
SyslogIdentifier=briven

# Security hardening
NoNewPrivileges=yes
ProtectSystem=strict
ReadWritePaths=$RUN_HOME
PrivateTmp=yes

[Install]
WantedBy=multi-user.target
UNIT

    success "Created $SERVICE_FILE"

    # ══════════════════════════════════════════════════════════
    # Step 10 — Enable and start
    # ══════════════════════════════════════════════════════════
    step "10/10" "Start Briven"

    sudo systemctl daemon-reload
    sudo systemctl enable briven --quiet

    if $TS_CONNECTED; then
        sudo systemctl restart briven
        sleep 3
        if sudo systemctl is-active --quiet briven; then
            success "Briven service is running."
        else
            warn "Service may still be starting. Check:  journalctl -u briven -f"
        fi
    else
        info "Service enabled but not started yet (Tailscale not connected)."
        info "After connecting Tailscale, run:  sudo systemctl start briven"
    fi
else
    step "10/10" "macOS — manual start"
    info "systemd not available on macOS. Start manually:"
    echo ""
    if [[ -n "$TS_IP" ]]; then
        echo "  cd $INSTALL_DIR && source .venv/bin/activate"
        echo "  python run_ui.py --host $TS_IP --port $BRIVEN_PORT"
    else
        echo "  cd $INSTALL_DIR && source .venv/bin/activate"
        echo "  python run_ui.py --port $BRIVEN_PORT"
    fi
    echo ""
fi

# ══════════════════════════════════════════════════════════════
# Done
# ══════════════════════════════════════════════════════════════
echo ""
echo -e "${GREEN}${BOLD}"
cat << 'DONE'
  ┌──────────────────────────────────────────────┐
  │            Installation complete!              │
  └──────────────────────────────────────────────┘
DONE
echo -e "${RESET}"

if [[ -n "$TS_IP" ]]; then
    echo -e "  ${BOLD}Web UI:${RESET}     http://$TS_IP:$BRIVEN_PORT"
else
    echo -e "  ${BOLD}Web UI:${RESET}     http://localhost:$BRIVEN_PORT  ${DIM}(connect Tailscale for remote access)${RESET}"
fi

echo ""
echo -e "  ${BOLD}Next steps:${RESET}"
echo ""
echo -e "  ${CYAN}1.${RESET} Add your LLM API key:"
echo "     nano $INSTALL_DIR/usr/.env"
echo ""
echo -e "  ${CYAN}2.${RESET} Restart to apply:"
if $IS_LINUX; then
    echo "     sudo systemctl restart briven"
else
    echo "     (re-run python run_ui.py)"
fi
echo ""
echo -e "  ${CYAN}3.${RESET} View logs:"
if $IS_LINUX; then
    echo "     journalctl -u briven -f"
else
    echo "     (output in terminal)"
fi
echo ""
echo -e "  ${DIM}Tailscale auth keys:  https://login.tailscale.com/admin/settings/keys${RESET}"
echo -e "  ${DIM}Full VPS guide:       $INSTALL_DIR/docs/setup/vps-tailscale-secure.md${RESET}"
echo ""
