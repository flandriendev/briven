#!/usr/bin/env bash
# ============================================================
# Briven — one-liner installer
# Usage: curl -fsSL https://raw.githubusercontent.com/flandriendev/briven/main/install.sh | bash
# ============================================================
set -euo pipefail

REPO="https://github.com/flandriendev/briven.git"
INSTALL_DIR="${BRIVEN_DIR:-$HOME/briven}"
PYTHON="${PYTHON:-python3}"

# ── colors ────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
CYAN='\033[0;36m'; BOLD='\033[1m'; RESET='\033[0m'
info()    { echo -e "${CYAN}[Briven]${RESET} $*"; }
success() { echo -e "${GREEN}[Briven]${RESET} $*"; }
warn()    { echo -e "${YELLOW}[Briven]${RESET} $*"; }
die()     { echo -e "${RED}[Briven] ERROR:${RESET} $*" >&2; exit 1; }

echo -e "${BOLD}"
echo "  ┌─────────────────────────────────────────┐"
echo "  │          Briven  Installer            │"
echo "  │   github.com/flandriendev/briven      │"
echo "  └─────────────────────────────────────────┘"
echo -e "${RESET}"

# ── prerequisites check ───────────────────────────────────────
command -v git  >/dev/null 2>&1 || die "git is required but not installed."
command -v "$PYTHON" >/dev/null 2>&1 || die "Python 3 is required. Install it first."

PYVER=$("$PYTHON" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
info "Python version: $PYVER"
[[ "${PYVER%%.*}" -ge 3 && "${PYVER##*.}" -ge 10 ]] || \
  die "Python 3.10+ required. Got $PYVER"

# ── clone ─────────────────────────────────────────────────────
if [ -d "$INSTALL_DIR/.git" ]; then
    warn "Briven already cloned at $INSTALL_DIR — pulling latest..."
    git -C "$INSTALL_DIR" pull --ff-only
else
    info "Cloning Briven into $INSTALL_DIR ..."
    git clone "$REPO" "$INSTALL_DIR"
fi
cd "$INSTALL_DIR"

# ── virtual environment ───────────────────────────────────────
info "Setting up Python virtual environment..."
"$PYTHON" -m venv .venv
# shellcheck disable=SC1091
source .venv/bin/activate

# ── dependencies ──────────────────────────────────────────────
info "Installing Python dependencies..."
pip install --upgrade pip --quiet
pip install -r requirements.txt --quiet
if [ -f requirements2.txt ]; then
    pip install -r requirements2.txt --quiet
fi

# ── environment file ──────────────────────────────────────────
if [ ! -f .env ]; then
    if [ -f .env.example ]; then
        cp .env.example .env
        warn ".env created from .env.example — fill in your API keys before starting."
    else
        warn "No .env.example found. Create a .env file manually with your API keys."
    fi
else
    info ".env already exists — skipping."
fi

# ── Tailscale hint ────────────────────────────────────────────
echo ""
echo -e "${BOLD}${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${RESET}"
echo -e "${BOLD} 🔒  Tailscale — Recommended Networking Setup${RESET}"
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${RESET}"
echo ""
echo "  Briven recommends Tailscale for secure, zero-trust networking."
echo "  No exposed ports. No public IPs. Access from any device on your tailnet."
echo ""
if command -v tailscale >/dev/null 2>&1; then
    TSIP=$(tailscale ip -4 2>/dev/null || echo "")
    if [ -n "$TSIP" ]; then
        success "Tailscale detected — your IP: $TSIP"
        echo "  Start Briven bound to Tailscale:"
        echo "  ${BOLD}  uvicorn run_ui:app --host $TSIP --port 8000${RESET}"
    else
        warn "Tailscale installed but not logged in. Run: tailscale up"
    fi
else
    echo "  Install Tailscale: https://tailscale.com/download"
    echo "  Then run:  tailscale up"
fi
echo ""
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${RESET}"
echo ""

# ── done ──────────────────────────────────────────────────────
success "Installation complete!"
echo ""
echo "  Next steps:"
echo "  1. Edit .env and add your API keys"
echo "  2. Activate the venv:  source $INSTALL_DIR/.venv/bin/activate"
echo "  3. Start Briven:"
echo "     ${BOLD}uvicorn run_ui:app --host 0.0.0.0 --port 8000${RESET}"
echo "  4. Open http://localhost:8000"
echo ""
echo "  Docs:"
echo "  • Mac Mini setup: $INSTALL_DIR/docs/install-mac-mini.md"
echo "  • VPS setup:      $INSTALL_DIR/docs/install-vps-server.md"
echo ""
