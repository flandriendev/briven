#!/usr/bin/env bash
# ============================================================
# Briven — Visual TUI Installer
#
# Usage:
#   curl -fsSL https://raw.githubusercontent.com/flandriendev/briven/main/install.sh | bash
#
# To review before running (recommended — this script gets root-level access):
#   curl -fsSL https://raw.githubusercontent.com/flandriendev/briven/main/install.sh -o install.sh
#   less install.sh
#   bash install.sh
#
# Supported:
#   Linux:   Ubuntu 22.04/24.04, Debian 12/13, Fedora, Arch, etc.
#   macOS:   Apple Silicon & Intel (via Homebrew)
#   Windows: WSL2 (Ubuntu/Debian inside WSL)
#
# Features:
#   - Visual TUI with colored output and progress tracking
#   - Arrow-key navigable selection lists for providers & channels
#   - Guided LLM provider selection (cloud + free local: Ollama, LM Studio)
#   - Channel integration setup (Telegram, WhatsApp, Discord, Slack, Email)
#   - Tailscale zero-trust networking + ACL enforcement (VPS)
#   - UFW + Fail2ban hardening (Linux VPS, optional)
#   - Systemd service (Linux) / manual start (macOS/WSL)
#   - Python 3.13+ compatibility auto-patching
#   - Idempotent: safe to re-run at any time
# ============================================================
set -euo pipefail

REPO="https://github.com/flandriendev/briven.git"
BRIVEN_PORT="${BRIVEN_PORT:-8000}"
TOTAL_STEPS=10
CURRENT_STEP=0

# ── Early OS detection (needed by sedi and other helpers) ──
OS_TYPE=""
case "$(uname -s)" in
    Darwin)  OS_TYPE="macOS" ;;
    Linux)
        if grep -qi "microsoft\|wsl" /proc/version 2>/dev/null; then
            OS_TYPE="WSL"
        else
            OS_TYPE="Linux"
        fi
        ;;
    MINGW*|MSYS*|CYGWIN*)
        OS_TYPE="Windows"
        ;;
    *)
        OS_TYPE="Linux"  # Best guess
        ;;
esac

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

# ── Cross-platform sed -i (macOS requires '' argument) ─────
sedi() {
    if [[ "$OS_TYPE" == "macOS" ]]; then
        sed -i '' "$@"
    else
        sed -i "$@"
    fi
}

# ── Write key to usr/.env (uncomment if commented, append if missing)
set_env() {
    local key="$1" val="$2" file="$INSTALL_DIR/usr/.env"
    [[ -z "$val" ]] && return
    if grep -q "^${key}=" "$file" 2>/dev/null; then
        sedi "s|^${key}=.*|${key}=${val}|" "$file"
    elif grep -q "^# *${key}=" "$file" 2>/dev/null; then
        sedi "s|^# *${key}=.*|${key}=${val}|" "$file"
    else
        printf '%s=%s\n' "$key" "$val" >> "$file"
    fi
}

# ── Write settings delta to usr/settings.json ───────────────
write_settings_json() {
    local delta_json="$1"
    local settings_file="$INSTALL_DIR/usr/settings.json"
    mkdir -p "$INSTALL_DIR/usr"
    if [[ -f "$settings_file" ]]; then
        "$INSTALL_DIR/.venv/bin/python3" -c "
import json, sys
with open('$settings_file') as f:
    current = json.load(f)
delta = json.loads(sys.argv[1])
current.update(delta)
with open('$settings_file', 'w') as f:
    json.dump(current, f, indent=4)
" "$delta_json"
    else
        echo "$delta_json" | "$INSTALL_DIR/.venv/bin/python3" -c "
import json, sys
data = json.load(sys.stdin)
with open('$settings_file', 'w') as f:
    json.dump(data, f, indent=4)
"
    fi
}

# ── Apply model config for all 4 model types ────────────────
apply_model_config() {
    local provider="$1" model="$2" api_base="${3:-}"
    local embed_provider="${4:-huggingface}"
    local embed_model="${5:-sentence-transformers/all-MiniLM-L6-v2}"
    local embed_base="${6:-}"

    local json_delta
    json_delta=$(cat <<ENDJSON
{
    "chat_model_provider": "$provider",
    "chat_model_name": "$model",
    "chat_model_api_base": "$api_base",
    "util_model_provider": "$provider",
    "util_model_name": "$model",
    "util_model_api_base": "$api_base",
    "embed_model_provider": "$embed_provider",
    "embed_model_name": "$embed_model",
    "embed_model_api_base": "$embed_base",
    "browser_model_provider": "$provider",
    "browser_model_name": "$model",
    "browser_model_api_base": "$api_base"
}
ENDJSON
)
    write_settings_json "$json_delta"
}

# ── Test API key via HTTP probe ──────────────────────────────
test_api_connection() {
    local provider="$1" key="$2"
    local status=""
    case "$provider" in
        briven_venice)
            status=$(curl -sf -o /dev/null -w "%{http_code}" \
                -H "Authorization: Bearer $key" \
                "https://llm.briven.ai/v1/models" 2>/dev/null || echo "000") ;;
        anthropic)
            status=$(curl -sf -o /dev/null -w "%{http_code}" \
                -H "x-api-key: $key" \
                -H "anthropic-version: 2023-06-01" \
                "https://api.anthropic.com/v1/models" 2>/dev/null || echo "000") ;;
        openai)
            status=$(curl -sf -o /dev/null -w "%{http_code}" \
                -H "Authorization: Bearer $key" \
                "https://api.openai.com/v1/models" 2>/dev/null || echo "000") ;;
        openrouter)
            status=$(curl -sf -o /dev/null -w "%{http_code}" \
                -H "Authorization: Bearer $key" \
                "https://openrouter.ai/api/v1/models" 2>/dev/null || echo "000") ;;
        google)
            status=$(curl -sf -o /dev/null -w "%{http_code}" \
                "https://generativelanguage.googleapis.com/v1beta/models?key=$key" 2>/dev/null || echo "000") ;;
        groq)
            status=$(curl -sf -o /dev/null -w "%{http_code}" \
                -H "Authorization: Bearer $key" \
                "https://api.groq.com/openai/v1/models" 2>/dev/null || echo "000") ;;
        *)
            [[ -n "$key" ]] && return 0
            return 1 ;;
    esac
    [[ "$status" == "200" ]] && return 0
    return 1
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

# ══════════════════════════════════════════════════════════════
# Arrow-key navigable selection list
# Usage: select_from_list "prompt" item1 item2 item3 ...
# Returns the 1-based index of the selected item via SELECT_RESULT
# Items can contain ANSI color codes; display is handled cleanly.
# ══════════════════════════════════════════════════════════════
SELECT_RESULT=""
select_from_list() {
    local prompt="$1"
    shift
    local items=("$@")
    local count=${#items[@]}
    local current=0

    # Determine input source for key reading
    local input_fd=0
    if [[ ! -t 0 ]] && [[ -e /dev/tty ]]; then
        exec 4</dev/tty
        input_fd=4
    fi

    # Hide cursor
    printf "\e[?25l"

    # Draw initial list
    printf "  %s\n\n" "$prompt"
    for i in "${!items[@]}"; do
        if [[ $i -eq $current ]]; then
            printf "  ${BRED}${BOLD} ▸ %s${RST}\n" "${items[$i]}"
        else
            printf "    %s\n" "${items[$i]}"
        fi
    done

    while true; do
        # Read a single character
        local key=""
        IFS= read -rsn1 key <&"$input_fd"

        if [[ "$key" == $'\x1b' ]]; then
            # Escape sequence — read next two chars
            local seq1="" seq2=""
            IFS= read -rsn1 -t 0.1 seq1 <&"$input_fd" || true
            IFS= read -rsn1 -t 0.1 seq2 <&"$input_fd" || true
            if [[ "$seq1" == "[" ]]; then
                case "$seq2" in
                    A) # Up arrow
                        current=$(( (current - 1 + count) % count ))
                        ;;
                    B) # Down arrow
                        current=$(( (current + 1) % count ))
                        ;;
                esac
            fi
        elif [[ "$key" == $'\t' ]]; then
            # Tab — move down
            current=$(( (current + 1) % count ))
        elif [[ "$key" == "" ]]; then
            # Enter — confirm selection
            break
        fi

        # Redraw: move cursor up by count lines and overwrite
        printf "\e[%dA" "$count"
        for i in "${!items[@]}"; do
            # Clear line and redraw
            printf "\e[2K"
            if [[ $i -eq $current ]]; then
                printf "  ${BRED}${BOLD} ▸ %s${RST}\n" "${items[$i]}"
            else
                printf "    %s\n" "${items[$i]}"
            fi
        done
    done

    # Show cursor again
    printf "\e[?25l\e[?25h"
    printf "\n"

    # Close extra fd if we opened it
    if [[ $input_fd -eq 4 ]]; then
        exec 4<&-
    fi

    SELECT_RESULT=$((current + 1))
}

# ══════════════════════════════════════════════════════════════
# Multi-select list with arrow keys + space to toggle
# Usage: multi_select_from_list "prompt" item1 item2 ...
# Returns comma-separated 1-based indices in MULTI_SELECT_RESULT
# ══════════════════════════════════════════════════════════════
MULTI_SELECT_RESULT=""
multi_select_from_list() {
    local prompt="$1"
    shift
    local items=("$@")
    local count=${#items[@]}
    local current=0
    local selected=()

    # Initialize all as unselected
    for ((i=0; i<count; i++)); do
        selected[$i]=0
    done

    # Determine input source
    local input_fd=0
    if [[ ! -t 0 ]] && [[ -e /dev/tty ]]; then
        exec 4</dev/tty
        input_fd=4
    fi

    printf "\e[?25l"

    printf "  %s\n"  "$prompt"
    dimtext "Use ↑↓ to navigate, Space to toggle, Enter to confirm"
    printf "\n"

    # Draw initial list
    for i in "${!items[@]}"; do
        local marker="  "
        [[ "${selected[$i]}" -eq 1 ]] && marker="${GRN}✓${RST} "
        if [[ $i -eq $current ]]; then
            printf "  ${BRED}${BOLD} ▸ ${RST}${marker}%s${RST}\n" "${items[$i]}"
        else
            printf "    ${marker}%s\n" "${items[$i]}"
        fi
    done

    while true; do
        local key=""
        IFS= read -rsn1 key <&"$input_fd"

        if [[ "$key" == $'\x1b' ]]; then
            local seq1="" seq2=""
            IFS= read -rsn1 -t 0.1 seq1 <&"$input_fd" || true
            IFS= read -rsn1 -t 0.1 seq2 <&"$input_fd" || true
            if [[ "$seq1" == "[" ]]; then
                case "$seq2" in
                    A) current=$(( (current - 1 + count) % count )) ;;
                    B) current=$(( (current + 1) % count )) ;;
                esac
            fi
        elif [[ "$key" == $'\t' ]]; then
            current=$(( (current + 1) % count ))
        elif [[ "$key" == " " ]]; then
            # Toggle selection
            if [[ "${selected[$current]}" -eq 1 ]]; then
                selected[$current]=0
            else
                selected[$current]=1
            fi
        elif [[ "$key" == "" ]]; then
            break
        fi

        # Redraw
        printf "\e[%dA" "$count"
        for i in "${!items[@]}"; do
            printf "\e[2K"
            local marker="  "
            [[ "${selected[$i]}" -eq 1 ]] && marker="${GRN}✓${RST} "
            if [[ $i -eq $current ]]; then
                printf "  ${BRED}${BOLD} ▸ ${RST}${marker}%s${RST}\n" "${items[$i]}"
            else
                printf "    ${marker}%s\n" "${items[$i]}"
            fi
        done
    done

    printf "\e[?25h"
    printf "\n"

    if [[ $input_fd -eq 4 ]]; then
        exec 4<&-
    fi

    # Build result
    local result=""
    for ((i=0; i<count; i++)); do
        if [[ "${selected[$i]}" -eq 1 ]]; then
            [[ -n "$result" ]] && result+=","
            result+="$((i + 1))"
        fi
    done
    MULTI_SELECT_RESULT="$result"
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

${BOLD}Installer v2.1${RST}        ${DIM}github.com/flandriendev/briven${RST}
EOF

printf "\n"

# ── Security & Disclaimer ─────────────────────────────────
draw_box << EOF
${YEL}${BOLD}⚠  Security & Disclaimer — please read.${RST}

${WHT}Briven is a self-hosted AI agent framework. It can:${RST}
  • Execute shell commands and read/write files
  • Access the internet, APIs, and connected services
  • Run autonomous tasks if tools are enabled

${WHT}A bad prompt or misconfiguration can lead to${RST}
${WHT}unintended actions on your system.${RST}

${BOLD}By continuing, you acknowledge that:${RST}
  • You are solely responsible for how you deploy
    and configure Briven on your infrastructure
  • Briven and its contributors accept no liability
    for any damage, data loss, security breach, or
    other issue arising from its use
  • You will follow security best practices:
    – Use authentication (AUTH_LOGIN / AUTH_PASSWORD)
    – Do not expose the web UI to the public internet
      without Tailscale or a reverse proxy with TLS
    – Keep secrets out of the agent's reachable paths
    – Use the strongest available model for any bot
      with tools or untrusted inboxes

${DIM}Review the source: github.com/flandriendev/briven${RST}
EOF

printf "\n"
select_from_list "  I understand and accept the above. Continue?" \
    "Yes — continue with installation" \
    "No  — cancel and exit"

if [[ "$SELECT_RESULT" -eq 2 ]]; then
    printf "\n"
    info "Installation cancelled. No changes were made."
    printf "\n"
    exit 0
fi

# ── Detect distro / platform ──────────────────────────────
DISTRO=""
DISTRO_VER=""
PKG_MANAGER=""  # apt, brew, dnf, pacman, zypper

case "$OS_TYPE" in
    macOS)
        DISTRO="macOS"
        DISTRO_VER=$(sw_vers -productVersion 2>/dev/null || echo "?")
        if command -v brew >/dev/null 2>&1; then
            PKG_MANAGER="brew"
        else
            warn "Homebrew not found. Install it first: https://brew.sh"
            err "Homebrew is required on macOS. Run: /bin/bash -c \"\$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)\""
        fi
        ;;
    WSL)
        # WSL runs a Linux distro underneath
        if grep -qi "ubuntu" /etc/os-release 2>/dev/null; then
            DISTRO="Ubuntu (WSL)"
        elif grep -qi "debian" /etc/os-release 2>/dev/null; then
            DISTRO="Debian (WSL)"
        else
            DISTRO="Linux (WSL)"
        fi
        DISTRO_VER=$(grep VERSION_ID /etc/os-release 2>/dev/null | cut -d'"' -f2 || echo "?")
        PKG_MANAGER="apt"
        ;;
    Linux)
        if grep -qi "ubuntu" /etc/os-release 2>/dev/null; then
            DISTRO="Ubuntu"
            PKG_MANAGER="apt"
        elif grep -qi "debian" /etc/os-release 2>/dev/null; then
            DISTRO="Debian"
            PKG_MANAGER="apt"
        elif grep -qi "fedora\|rhel\|centos\|rocky\|alma" /etc/os-release 2>/dev/null; then
            DISTRO="Fedora/RHEL"
            PKG_MANAGER="dnf"
            command -v dnf >/dev/null 2>&1 || PKG_MANAGER="yum"
        elif grep -qi "arch\|manjaro\|endeavour" /etc/os-release 2>/dev/null; then
            DISTRO="Arch"
            PKG_MANAGER="pacman"
        elif grep -qi "opensuse\|suse" /etc/os-release 2>/dev/null; then
            DISTRO="openSUSE"
            PKG_MANAGER="zypper"
        else
            DISTRO="Linux"
            # Try to detect package manager
            if command -v apt-get >/dev/null 2>&1; then
                PKG_MANAGER="apt"
            elif command -v dnf >/dev/null 2>&1; then
                PKG_MANAGER="dnf"
            elif command -v pacman >/dev/null 2>&1; then
                PKG_MANAGER="pacman"
            elif command -v zypper >/dev/null 2>&1; then
                PKG_MANAGER="zypper"
            else
                PKG_MANAGER="unknown"
            fi
        fi
        DISTRO_VER=$(grep VERSION_ID /etc/os-release 2>/dev/null | cut -d'"' -f2 || echo "?")
        ;;
esac

# ── Detect user / install path ─────────────────────────────
if [[ -n "${SUDO_USER:-}" && "${SUDO_USER:-}" != "root" ]]; then
    RUN_USER="$SUDO_USER"
    if command -v getent >/dev/null 2>&1; then
        RUN_HOME=$(getent passwd "$SUDO_USER" | cut -d: -f6)
    else
        RUN_HOME=$(eval echo "~$SUDO_USER")
    fi
else
    RUN_USER="${USER:-$(whoami)}"
    RUN_HOME="$HOME"
fi
INSTALL_DIR="${BRIVEN_DIR:-$RUN_HOME/briven}"

info "Detected: $DISTRO $DISTRO_VER ($OS_TYPE)"
info "Package manager: $PKG_MANAGER"
info "Install dir: $INSTALL_DIR (user: $RUN_USER)"

# ╔══════════════════════════════════════════════════════════╗
# ║              Step 1 — System Dependencies                ║
# ╚══════════════════════════════════════════════════════════╝
step "System dependencies"

case "$PKG_MANAGER" in
    apt)
        info "Updating package lists..."
        sudo apt-get update -qq
        info "Installing base packages..."
        sudo apt-get install -y -qq \
            git curl wget ca-certificates build-essential \
            python3 python3-venv python3-dev python3-pip \
            libssl-dev zlib1g-dev libbz2-dev libreadline-dev \
            libsqlite3-dev libncursesw5-dev libxml2-dev libxmlsec1-dev \
            libffi-dev liblzma-dev jq \
            tesseract-ocr poppler-utils 2>/dev/null || true
        # UFW and Fail2ban only on non-WSL Linux (VPS/server use)
        if [[ "$OS_TYPE" == "Linux" ]]; then
            sudo apt-get install -y -qq ufw fail2ban 2>/dev/null || true
        fi
        ;;
    brew)
        info "Installing packages via Homebrew..."
        brew install git curl wget python3 jq tesseract poppler 2>/dev/null || true
        ;;
    dnf|yum)
        info "Installing packages via $PKG_MANAGER..."
        sudo "$PKG_MANAGER" install -y \
            git curl wget ca-certificates gcc gcc-c++ make \
            python3 python3-devel python3-pip \
            openssl-devel zlib-devel bzip2-devel readline-devel \
            sqlite-devel ncurses-devel libxml2-devel libxmlsec1-devel \
            libffi-devel xz-devel jq \
            tesseract poppler-utils 2>/dev/null || true
        ;;
    pacman)
        info "Installing packages via pacman..."
        sudo pacman -Sy --noconfirm --needed \
            git curl wget base-devel python python-pip \
            openssl zlib bzip2 readline sqlite ncurses \
            libxml2 libxmlsec libffi xz jq \
            tesseract poppler 2>/dev/null || true
        ;;
    zypper)
        info "Installing packages via zypper..."
        sudo zypper install -y \
            git curl wget gcc gcc-c++ make \
            python3 python3-devel python3-pip \
            libopenssl-devel zlib-devel libbz2-devel readline-devel \
            sqlite3-devel ncurses-devel libxml2-devel libxmlsec1-devel \
            libffi-devel xz-devel jq \
            tesseract-ocr poppler-tools 2>/dev/null || true
        ;;
    *)
        warn "Unknown package manager — skipping system dependency install"
        dimtext "Make sure git, python3, curl, jq are installed manually"
        ;;
esac
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
if [[ "$PY_MINOR" -ge 13 ]]; then
    info "Python 3.13+ detected — disabling incompatible packages..."
    sedi 's/^kokoro/#kokoro/' requirements.txt
    sedi 's/^langchain-unstructured/#langchain-unstructured/' requirements.txt
    sedi 's/^openai-whisper/#openai-whisper/' requirements.txt
    ok "Disabled: kokoro, langchain-unstructured, openai-whisper"
fi

# ── GPU detection — install PyTorch CPU-only if no GPU ────
# NVIDIA CUDA packages are ~2GB+ and cause "No space left" on small VPS
# macOS uses MPS (Metal) automatically — no CUDA bloat
HAS_GPU=false
if [[ "$OS_TYPE" == "macOS" ]]; then
    # macOS PyTorch uses MPS natively, no NVIDIA packages involved
    info "macOS detected — PyTorch will use Metal (MPS) acceleration"
    HAS_GPU=true  # Skip CPU-only install, default PyTorch is fine on macOS
elif command -v nvidia-smi >/dev/null 2>&1 && nvidia-smi >/dev/null 2>&1; then
    HAS_GPU=true
    info "NVIDIA GPU detected — installing PyTorch with CUDA support"
fi

if ! $HAS_GPU; then
    info "No GPU detected — installing PyTorch CPU-only (saves ~2GB)"
    pip install --no-cache-dir torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu --quiet 2>&1 || true
    ok "PyTorch CPU installed"
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
if pip install --no-cache-dir -r requirements.txt 2>&1; then
    ok "Dependencies installed successfully"
else
    warn "First attempt failed — retrying with reduced packages..."
    sedi 's/^kokoro/#kokoro/' requirements.txt
    sedi 's/^langchain-unstructured/#langchain-unstructured/' requirements.txt
    sedi 's/^openai-whisper/#openai-whisper/' requirements.txt
    sedi 's/^sentence-transformers/#sentence-transformers/' requirements.txt
    if pip install --no-cache-dir -r requirements.txt 2>&1; then
        ok "Dependencies installed (some optional packages disabled)"
    else
        err "pip install failed. Run manually: cd $INSTALL_DIR && source .venv/bin/activate && pip install -r requirements.txt"
    fi
fi
[[ -f requirements2.txt ]] && pip install --no-cache-dir -r requirements2.txt --quiet 2>/dev/null || true
ok "All dependencies ready"

# ╔══════════════════════════════════════════════════════════╗
# ║                Step 4 — Tailscale                        ║
# ╚══════════════════════════════════════════════════════════╝
step "Tailscale zero-trust networking"

# Tailscale is most relevant for VPS/server. On local machines it's optional.
TAILSCALE_AVAILABLE=false

if command -v tailscale >/dev/null 2>&1; then
    TAILSCALE_AVAILABLE=true
    ok "Tailscale already installed"
else
    case "$OS_TYPE" in
        macOS)
            dimtext "Tailscale is optional for local macOS installations."
            dimtext "Install from: https://tailscale.com/download/mac"
            dimtext "Or: brew install --cask tailscale"
            printf "\n"
            select_from_list "Install Tailscale?" \
                "Yes — install via Homebrew" \
                "Skip — I'll use localhost or install later"
            if [[ "$SELECT_RESULT" -eq 1 ]]; then
                brew install --cask tailscale 2>/dev/null || brew install tailscale 2>/dev/null || true
                command -v tailscale >/dev/null 2>&1 && TAILSCALE_AVAILABLE=true
            fi
            ;;
        WSL)
            dimtext "Tailscale in WSL: install Tailscale on your Windows host instead."
            dimtext "Download from: https://tailscale.com/download/windows"
            dimtext "WSL will share the host's Tailscale connection."
            ;;
        Linux)
            info "Installing Tailscale..."
            curl -fsSL https://tailscale.com/install.sh | sh
            command -v tailscale >/dev/null 2>&1 && TAILSCALE_AVAILABLE=true
            ;;
    esac
fi

# Start tailscaled daemon (Linux only — macOS uses the app)
if $TAILSCALE_AVAILABLE && [[ "$OS_TYPE" == "Linux" ]]; then
    sudo systemctl enable --now tailscaled 2>/dev/null || true
    ok "Tailscale daemon ready"
fi

# ── Tailscale authentication ───────────────────────────────
TS_OK=false
TS_STATUS=""
TS_BACKEND=""

if $TAILSCALE_AVAILABLE; then
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

${BOLD}Two ways to connect:${RST}
  ${BRED}1)${RST} Auth key  — paste a pre-generated key
  ${BRED}2)${RST} Login URL — open a URL in your browser

${BOLD}To generate an auth key:${RST}
  ${CYN}https://login.tailscale.com/admin/settings/keys${RST}
  → Generate auth key → Enable "Reusable"
EOF
    printf "\n"

    select_from_list "How do you want to authenticate Tailscale?" \
        "Auth key  — I have a tskey-auth-... key ready" \
        "Login URL — Generate a URL I can open in my browser" \
        "Skip      — I'll set up Tailscale later"

    TS_OK=false
    case "$SELECT_RESULT" in
        1)
            # Auth key flow
            for attempt in 1 2 3; do
                KEY=$(ask "  Auth key (tskey-auth-...): ")

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
            ;;
        2)
            # Interactive login URL flow
            info "Starting Tailscale login..."
            printf "\n"

            # Run tailscale up in the background and capture the login URL
            TS_UP_OUTPUT=$(mktemp)
            sudo tailscale up --accept-routes --accept-dns=false 2>"$TS_UP_OUTPUT" &
            TS_UP_PID=$!

            # Wait for the URL to appear (up to 15 seconds)
            LOGIN_URL=""
            for _wait in $(seq 1 30); do
                if [[ -f "$TS_UP_OUTPUT" ]]; then
                    LOGIN_URL=$(grep -oP 'https://login\.tailscale\.com/\S+' "$TS_UP_OUTPUT" 2>/dev/null || true)
                    if [[ -n "$LOGIN_URL" ]]; then
                        break
                    fi
                fi
                sleep 0.5
            done

            if [[ -n "$LOGIN_URL" ]]; then
                printf "\n"
                draw_box << EOF
${BRED}${BOLD}Tailscale Login URL${RST}

Open this URL in your browser to connect this
server to your Tailscale account:

${CYN}${BOLD}${LOGIN_URL}${RST}

${DIM}Waiting for you to complete login...${RST}
EOF
                printf "\n"

                # Wait for tailscale up to complete (up to 120 seconds)
                for _wait in $(seq 1 120); do
                    if ! kill -0 "$TS_UP_PID" 2>/dev/null; then
                        break
                    fi
                    # Check if already connected
                    CHECK_STATE=$(tailscale status --json 2>/dev/null | jq -r '.BackendState // ""' 2>/dev/null || echo "")
                    if [[ "$CHECK_STATE" == "Running" ]]; then
                        TS_OK=true
                        break
                    fi
                    sleep 1
                done

                # Clean up
                kill "$TS_UP_PID" 2>/dev/null || true
                wait "$TS_UP_PID" 2>/dev/null || true
            else
                warn "Could not generate login URL. Try manually: sudo tailscale up"
                kill "$TS_UP_PID" 2>/dev/null || true
                wait "$TS_UP_PID" 2>/dev/null || true
            fi
            rm -f "$TS_UP_OUTPUT"

            if $TS_OK; then
                ok "Tailscale connected and verified!"
            else
                warn "Login not completed — run later: sudo tailscale up"
            fi
            ;;
        3)
            dimtext "Skipped Tailscale authentication"
            ;;
    esac
fi  # end TS_BACKEND check

fi  # end TAILSCALE_AVAILABLE

# Get Tailscale IP (or fallback)
TS_IP=""
if $TAILSCALE_AVAILABLE; then
    TS_IP=$(tailscale ip --4 2>/dev/null | head -1 | tr -d ' ' || echo "")
fi
if [[ -z "$TS_IP" ]]; then
    if [[ "$OS_TYPE" == "macOS" || "$OS_TYPE" == "WSL" ]]; then
        dimtext "No Tailscale IP — service will bind to localhost"
        TS_IP="127.0.0.1"
    else
        warn "No Tailscale IP detected — service will bind to 0.0.0.0"
        TS_IP="0.0.0.0"
    fi
else
    ok "Tailscale IP: $TS_IP"
fi

# ╔══════════════════════════════════════════════════════════╗
# ║              Step 5 — Environment File                   ║
# ╚══════════════════════════════════════════════════════════╝
step "Environment configuration"

# Fix: copy usr/.env.example → usr/.env (not root-level .env)
if [[ -f "usr/.env.example" && ! -f "usr/.env" ]]; then
    cp "usr/.env.example" "usr/.env"
    chmod 600 "usr/.env"
    ok "Created usr/.env from template (permissions: 600)"
elif [[ ! -f "usr/.env" ]]; then
    mkdir -p usr
    touch "usr/.env"
    chmod 600 "usr/.env"
    ok "Created empty usr/.env (permissions: 600)"
else
    ok "usr/.env already exists — keeping existing"
fi
# Ensure owner-only even on re-runs
chmod 600 "$INSTALL_DIR/usr/.env" 2>/dev/null || true
ok "Environment files ready"

# ╔══════════════════════════════════════════════════════════╗
# ║              Step 6 — LLM Provider Selection             ║
# ╚══════════════════════════════════════════════════════════╝
step "LLM provider setup"

printf "\n"
draw_box << EOF
${BRED}${BOLD}LLM Provider Setup${RST}

Briven needs at least one LLM provider to function.
Select a cloud API provider, or choose a free local
option like Ollama or LM Studio.

${DIM}You can always change providers later in Settings.${RST}
${DIM}Keys are stored locally and never sent anywhere else.${RST}
EOF
printf "\n"

KEY_COUNT=0

# Provider selection with arrow-key navigation
select_from_list "Select your LLM provider:" \
    "${BOLD}Briven API${RST}      — Briven's own API endpoint ${DIM}(recommended)${RST}" \
    "${BOLD}Ollama${RST}          — Free, local models on your machine" \
    "${BOLD}LM Studio${RST}       — Free, local GUI with model server" \
    "OpenRouter      — Access many providers with one key" \
    "Anthropic       — Claude models" \
    "OpenAI          — GPT models" \
    "Google          — Gemini models" \
    "Groq            — Fast Llama/Mixtral inference" \
    "DeepSeek" \
    "Mistral AI" \
    "xAI             — Grok models" \
    "${DIM}Skip — I'll configure later in Settings${RST}"

LLM_CHOICE="$SELECT_RESULT"

case "$LLM_CHOICE" in
    1)
        # ── Briven API ────────────────────────────────────────
        info "Briven API"
        dimtext "Endpoint: https://llm.briven.ai/v1"
        printf "\n"
        BKEY=$(ask "  Enter your Briven API key: ")
        printf "\n"

        if [[ -n "$BKEY" ]]; then
            printf "  Testing connection... "
            if test_api_connection "briven_venice" "$BKEY"; then
                printf "${GRN}valid${RST}\n"
            else
                printf "${YEL}could not verify (may still work)${RST}\n"
            fi
            set_env "API_KEY_BRIVEN_VENICE" "$BKEY"
            apply_model_config "briven_venice" "default" "https://llm.briven.ai/v1"
            KEY_COUNT=1
            ok "Briven API configured"
        else
            warn "No key entered. Skipping."
        fi
        ;;
    2)
        # ── Ollama (free, local) ──────────────────────────────
        info "Ollama Setup"
        printf "\n"

        OLLAMA_READY=false
        if command -v ollama >/dev/null 2>&1; then
            # Check if server is responding
            if curl -sf http://localhost:11434/api/tags >/dev/null 2>&1; then
                ok "Ollama detected at http://localhost:11434"
                OLLAMA_READY=true
            else
                warn "Ollama installed but server not running. Starting..."
                nohup ollama serve >/dev/null 2>&1 &
                sleep 3
                if curl -sf http://localhost:11434/api/tags >/dev/null 2>&1; then
                    ok "Ollama server started"
                    OLLAMA_READY=true
                else
                    warn "Could not start Ollama server"
                fi
            fi
        else
            warn "Ollama is not installed."
            printf "\n"
            select_from_list "Install Ollama?" \
                "Install Ollama now" \
                "Skip — I'll install it myself later"

            if [[ "$SELECT_RESULT" -eq 1 ]]; then
                info "Installing Ollama via official script..."
                curl -fsSL https://ollama.com/install.sh | sh
                nohup ollama serve >/dev/null 2>&1 &
                sleep 3
                if curl -sf http://localhost:11434/api/tags >/dev/null 2>&1; then
                    ok "Ollama installed and running"
                    OLLAMA_READY=true
                else
                    warn "Ollama installed but server not responding"
                fi
            else
                dimtext "Skipped. Install Ollama later and configure in Settings."
            fi
        fi

        if $OLLAMA_READY; then
            # List installed models
            MODELS_JSON=$(curl -sf http://localhost:11434/api/tags 2>/dev/null || echo '{"models":[]}')
            MODEL_LIST=()
            while IFS= read -r m; do
                [[ -n "$m" ]] && MODEL_LIST+=("$m")
            done < <(printf '%s' "$MODELS_JSON" | jq -r '.models[].name // empty' 2>/dev/null)

            SELECTED_MODEL=""
            if [[ ${#MODEL_LIST[@]} -gt 0 ]]; then
                ok "Found ${#MODEL_LIST[@]} installed model(s)"
                printf "\n"

                # Build selection list: installed models + pull option
                SELECT_ITEMS=()
                for m in "${MODEL_LIST[@]}"; do
                    SELECT_ITEMS+=("$m")
                done
                SELECT_ITEMS+=("Pull a different model")

                select_from_list "Select a model:" "${SELECT_ITEMS[@]}"
                MIDX=$SELECT_RESULT

                if [[ $MIDX -le ${#MODEL_LIST[@]} ]]; then
                    SELECTED_MODEL="${MODEL_LIST[$((MIDX - 1))]}"
                else
                    PULL_NAME=$(ask "  Enter model name to pull (e.g. llama3.1:8b): ")
                    if [[ -n "$PULL_NAME" ]]; then
                        info "Pulling $PULL_NAME..."
                        ollama pull "$PULL_NAME"
                        SELECTED_MODEL="$PULL_NAME"
                    fi
                fi
            else
                warn "No models installed yet."
                SELECTED_MODEL="llama3.1:8b"
                printf "\n"
                select_from_list "Pull recommended model ($SELECTED_MODEL)?" \
                    "Yes — pull llama3.1:8b" \
                    "No — enter a different model name"

                if [[ "$SELECT_RESULT" -eq 2 ]]; then
                    PULL_NAME=$(ask "  Enter model name to pull: ")
                    [[ -n "$PULL_NAME" ]] && SELECTED_MODEL="$PULL_NAME"
                fi

                info "Pulling $SELECTED_MODEL (this may take several minutes)..."
                ollama pull "$SELECTED_MODEL"
            fi

            # Pull embedding model if not present
            HAS_EMBED=$(printf '%s' "$MODELS_JSON" | jq -r '.models[].name // empty' 2>/dev/null | grep -c "nomic-embed-text" || true)
            if [[ "$HAS_EMBED" -eq 0 ]]; then
                info "Pulling embedding model nomic-embed-text..."
                ollama pull nomic-embed-text
            fi

            if [[ -n "$SELECTED_MODEL" ]]; then
                apply_model_config "ollama" "$SELECTED_MODEL" "" "ollama" "nomic-embed-text" ""
                KEY_COUNT=1
                ok "Ollama configured: $SELECTED_MODEL"
            fi
        fi
        ;;
    3)
        # ── LM Studio (free, local) ──────────────────────────
        info "LM Studio Setup"
        printf "\n"

        LMS_READY=false
        for _try in 1 2; do
            if curl -sf http://localhost:1234/v1/models >/dev/null 2>&1; then
                ok "LM Studio detected at http://localhost:1234/v1"
                LMS_READY=true
                break
            else
                if [[ $_try -eq 1 ]]; then
                    warn "Could not connect to LM Studio at http://localhost:1234"
                    dimtext "Make sure LM Studio is running with its local server started."
                    printf "\n"
                    select_from_list "What would you like to do?" \
                        "Retry connection" \
                        "Skip — I'll configure later"
                    [[ "$SELECT_RESULT" -ne 1 ]] && break
                fi
            fi
        done

        if $LMS_READY; then
            # Fetch available models
            LMS_MODELS=()
            while IFS= read -r m; do
                [[ -n "$m" ]] && LMS_MODELS+=("$m")
            done < <(curl -sf http://localhost:1234/v1/models 2>/dev/null | jq -r '.data[].id // empty' 2>/dev/null)

            SELECTED_MODEL=""
            if [[ ${#LMS_MODELS[@]} -gt 0 ]]; then
                SELECT_ITEMS=()
                for m in "${LMS_MODELS[@]}"; do
                    SELECT_ITEMS+=("$m")
                done
                SELECT_ITEMS+=("Enter a model name manually")

                select_from_list "Select a model:" "${SELECT_ITEMS[@]}"
                MIDX=$SELECT_RESULT

                if [[ $MIDX -le ${#LMS_MODELS[@]} ]]; then
                    SELECTED_MODEL="${LMS_MODELS[$((MIDX - 1))]}"
                else
                    SELECTED_MODEL=$(ask "  Enter model name: ")
                fi
            else
                SELECTED_MODEL=$(ask "  Enter the model name loaded in LM Studio: ")
            fi

            if [[ -n "$SELECTED_MODEL" ]]; then
                apply_model_config "lm_studio" "$SELECTED_MODEL" "http://localhost:1234/v1"
                KEY_COUNT=1
                ok "LM Studio configured: $SELECTED_MODEL"
            else
                warn "No model selected. Skipping."
            fi
        else
            dimtext "Skipped. Configure LM Studio in Settings after starting it."
        fi
        ;;
    4)
        # ── OpenRouter (with model sub-selection) ─────────────
        info "OpenRouter"
        dimtext "One API key, access to many models"
        printf "\n"
        dimtext "Get your key at: https://openrouter.ai/keys"
        printf "\n"

        OR_KEY=$(ask "  Enter your OpenRouter API key (sk-or-...): ")
        printf "\n"

        if [[ -n "$OR_KEY" ]]; then
            printf "  Testing connection... "
            if test_api_connection "openrouter" "$OR_KEY"; then
                printf "${GRN}valid${RST}\n"
            else
                printf "${YEL}could not verify${RST}\n"
            fi

            # Model sub-selection
            printf "\n"
            select_from_list "Select your preferred model on OpenRouter:" \
                "Anthropic Claude Sonnet 4.6  ${DIM}(recommended)${RST}" \
                "Google Gemini 2.5 Flash" \
                "Meta Llama 3.3 70B" \
                "DeepSeek Chat V3" \
                "Mistral Large" \
                "Enter a model ID manually"

            case "$SELECT_RESULT" in
                1) OR_MODEL="anthropic/claude-sonnet-4.6" ;;
                2) OR_MODEL="google/gemini-2.5-flash" ;;
                3) OR_MODEL="meta-llama/llama-3.3-70b" ;;
                4) OR_MODEL="deepseek/deepseek-chat-v3" ;;
                5) OR_MODEL="mistralai/mistral-large" ;;
                6) OR_MODEL=$(ask "  Enter OpenRouter model ID: ") ;;
                *) OR_MODEL="anthropic/claude-sonnet-4.6" ;;
            esac
            [[ -z "$OR_MODEL" ]] && OR_MODEL="anthropic/claude-sonnet-4.6"

            set_env "API_KEY_OPENROUTER" "$OR_KEY"
            apply_model_config "openrouter" "$OR_MODEL" ""
            KEY_COUNT=1
            ok "OpenRouter configured: $OR_MODEL"
        else
            warn "No key entered. Skipping."
        fi
        ;;
    5)
        # ── Anthropic ─────────────────────────────────────────
        info "Anthropic (Claude)"
        dimtext "Get your key at: https://console.anthropic.com/settings/keys"
        dimtext "Key format: sk-ant-..."
        printf "\n"
        CKEY=$(ask "  Enter your Anthropic API key: ")
        printf "\n"
        if [[ -n "$CKEY" ]]; then
            printf "  Testing connection... "
            if test_api_connection "anthropic" "$CKEY"; then
                printf "${GRN}valid${RST}\n"
            else
                printf "${YEL}could not verify (may still work)${RST}\n"
            fi
            set_env "API_KEY_ANTHROPIC" "$CKEY"
            apply_model_config "anthropic" "claude-sonnet-4-6" ""
            KEY_COUNT=1
            ok "Anthropic configured"
        else
            warn "No key entered. Skipping."
        fi
        ;;
    6)
        # ── OpenAI ────────────────────────────────────────────
        info "OpenAI (GPT)"
        dimtext "Get your key at: https://platform.openai.com/api-keys"
        dimtext "Key format: sk-..."
        printf "\n"
        OKEY=$(ask "  Enter your OpenAI API key: ")
        printf "\n"
        if [[ -n "$OKEY" ]]; then
            printf "  Testing connection... "
            if test_api_connection "openai" "$OKEY"; then
                printf "${GRN}valid${RST}\n"
            else
                printf "${YEL}could not verify (may still work)${RST}\n"
            fi
            set_env "API_KEY_OPENAI" "$OKEY"
            apply_model_config "openai" "gpt-4o" ""
            KEY_COUNT=1
            ok "OpenAI configured"
        else
            warn "No key entered. Skipping."
        fi
        ;;
    7)
        # ── Google ────────────────────────────────────────────
        info "Google Gemini"
        dimtext "Get your key at: https://aistudio.google.com/apikey"
        printf "\n"
        GKEY=$(ask "  Enter your Google API key: ")
        printf "\n"
        if [[ -n "$GKEY" ]]; then
            printf "  Testing connection... "
            if test_api_connection "google" "$GKEY"; then
                printf "${GRN}valid${RST}\n"
            else
                printf "${YEL}could not verify (may still work)${RST}\n"
            fi
            set_env "API_KEY_GOOGLE" "$GKEY"
            apply_model_config "google" "gemini-2.5-flash" ""
            KEY_COUNT=1
            ok "Google configured"
        else
            warn "No key entered. Skipping."
        fi
        ;;
    8)
        # ── Groq ─────────────────────────────────────────────
        info "Groq (fast inference)"
        dimtext "Get your key at: https://console.groq.com/keys"
        dimtext "Key format: gsk_..."
        printf "\n"
        QKEY=$(ask "  Enter your Groq API key: ")
        printf "\n"
        if [[ -n "$QKEY" ]]; then
            printf "  Testing connection... "
            if test_api_connection "groq" "$QKEY"; then
                printf "${GRN}valid${RST}\n"
            else
                printf "${YEL}could not verify (may still work)${RST}\n"
            fi
            set_env "API_KEY_GROQ" "$QKEY"
            apply_model_config "groq" "llama-3.3-70b-versatile" ""
            KEY_COUNT=1
            ok "Groq configured"
        else
            warn "No key entered. Skipping."
        fi
        ;;
    9)
        # ── DeepSeek ──────────────────────────────────────────
        info "DeepSeek"
        dimtext "Get your key at: https://platform.deepseek.com/api_keys"
        printf "\n"
        DKEY=$(ask "  Enter your DeepSeek API key: ")
        printf "\n"
        if [[ -n "$DKEY" ]]; then
            set_env "API_KEY_DEEPSEEK" "$DKEY"
            apply_model_config "deepseek" "deepseek-chat" ""
            KEY_COUNT=1
            ok "DeepSeek configured"
        else
            warn "No key entered. Skipping."
        fi
        ;;
    10)
        # ── Mistral AI ────────────────────────────────────────
        info "Mistral AI"
        dimtext "Get your key at: https://console.mistral.ai/api-keys"
        printf "\n"
        MKEY=$(ask "  Enter your Mistral AI API key: ")
        printf "\n"
        if [[ -n "$MKEY" ]]; then
            set_env "API_KEY_MISTRAL" "$MKEY"
            apply_model_config "mistral" "mistral-large-latest" ""
            KEY_COUNT=1
            ok "Mistral AI configured"
        else
            warn "No key entered. Skipping."
        fi
        ;;
    11)
        # ── xAI / Grok ───────────────────────────────────────
        info "xAI / Grok"
        dimtext "Get your key at: https://console.x.ai"
        dimtext "Key format: xai-..."
        printf "\n"
        XKEY=$(ask "  Enter your xAI API key: ")
        printf "\n"
        if [[ -n "$XKEY" ]]; then
            set_env "API_KEY_XAI" "$XKEY"
            apply_model_config "xai" "grok-3" ""
            KEY_COUNT=1
            ok "xAI configured"
        else
            warn "No key entered. Skipping."
        fi
        ;;
    12)
        dimtext "Skipped. Configure your LLM provider in Settings after starting Briven."
        ;;
    *)
        dimtext "Skipped. Configure your LLM provider in Settings after starting Briven."
        ;;
esac

printf "\n"
if [[ "$KEY_COUNT" -gt 0 ]]; then
    # Show summary
    draw_box << EOF
${GRN}${BOLD}✓  Provider Configured${RST}

${DIM}Settings saved to usr/settings.json${RST}
${DIM}You can change these any time in Settings.${RST}
EOF
else
    warn "No LLM provider configured — set one up in Settings after starting Briven"
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

# Multi-select for channels
multi_select_from_list "Select channels to configure:" \
    "Telegram         — Bot token + Chat ID" \
    "WhatsApp         — Token + Phone ID + Recipient" \
    "Discord          — Webhook URL" \
    "Slack            — Bot token + Channel" \
    "Email (SMTP)     — SMTP host + credentials"

if [[ -n "$MULTI_SELECT_RESULT" ]]; then
    IFS=',' read -ra CH_SELECTED <<< "$MULTI_SELECT_RESULT"
    printf "\n"
    for ch_num in "${CH_SELECTED[@]}"; do
        case "$ch_num" in
            1)
                info "Telegram setup"
                printf "\n"
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

                    # ── Telegram pairing ──────────────────────────────
                    # To pair, the user needs to send /start to the bot,
                    # which makes the bot aware of the user's chat ID.
                    printf "\n"
                    draw_box << EOF
${BRED}${BOLD}Telegram Pairing${RST}

To connect your Telegram account to Briven:

  1. Open Telegram
  2. Search for ${BOLD}@${TG_BOT_NAME:-your_bot}${RST}
  3. Press ${BOLD}START${RST} or send ${BOLD}/start${RST}

${DIM}Waiting for you to start the bot (90 seconds)...${RST}
${DIM}Press Enter to skip if you want to pair later.${RST}
EOF
                    printf "\n"

                    # Flush old updates
                    curl -sf "https://api.telegram.org/bot${TG_TOKEN}/getUpdates?offset=-1" > /dev/null 2>&1 || true
                    sleep 1

                    # Get offset for new messages only
                    LAST_UPDATE=$(curl -sf "https://api.telegram.org/bot${TG_TOKEN}/getUpdates" 2>/dev/null || echo '{"result":[]}')
                    LAST_ID=$(printf '%s' "$LAST_UPDATE" | jq -r '.result[-1].update_id // 0' 2>/dev/null || echo "0")
                    OFFSET=$((LAST_ID + 1))

                    TG_CHAT_ID=""
                    info "Waiting for /start message..."
                    for _try in $(seq 1 45); do
                        # Check if user pressed Enter to skip
                        if read -t 0 -n 0 2>/dev/null; then
                            read -r 2>/dev/null || true
                            break
                        fi

                        UPDATES=$(curl -sf "https://api.telegram.org/bot${TG_TOKEN}/getUpdates?offset=${OFFSET}&timeout=2" 2>/dev/null || echo '{"result":[]}')

                        # Look for any message from the user (including /start)
                        TG_CHAT_ID=$(printf '%s' "$UPDATES" | jq -r \
                            '[.result[].message | select(.text != null)] | .[0].chat.id // empty' \
                            2>/dev/null || echo "")

                        if [[ -n "$TG_CHAT_ID" ]]; then
                            break
                        fi
                    done

                    if [[ -n "$TG_CHAT_ID" ]]; then
                        set_env "TELEGRAM_CHAT_ID" "$TG_CHAT_ID"
                        ok "Telegram paired! Chat ID: $TG_CHAT_ID"

                        # Send a confirmation message to the user
                        curl -sf -X POST "https://api.telegram.org/bot${TG_TOKEN}/sendMessage" \
                            -d "chat_id=${TG_CHAT_ID}" \
                            -d "text=✅ Briven is now connected to this chat!" \
                            > /dev/null 2>&1 || true
                    else
                        warn "Pairing not completed — set TELEGRAM_CHAT_ID manually in usr/.env"
                        dimtext "To find your chat ID: send any message to your bot, then run:"
                        dimtext "  curl -s https://api.telegram.org/bot<TOKEN>/getUpdates | jq '.result[0].message.chat.id'"
                    fi
                fi
                ;;
            2)
                info "WhatsApp Business setup"
                dimtext "Requires a Meta Business account + phone number verification"
                dimtext "Get from: developers.facebook.com → WhatsApp → API Setup"
                printf "\n"
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
                printf "\n"
                val=$(ask "  Webhook URL: ")
                [[ -n "$val" ]] && set_env "DISCORD_WEBHOOK_URL" "$val" && ok "Discord webhook saved"
                ;;
            4)
                info "Slack setup"
                dimtext "Create app at: api.slack.com/apps → OAuth & Permissions"
                printf "\n"
                val=$(ask "  Bot token (xoxb-...): ")
                [[ -n "$val" ]] && set_env "SLACK_BOT_TOKEN" "$val" && ok "Slack bot token saved"
                val=$(ask "  Channel (#general): ")
                [[ -n "${val:-}" ]] && set_env "SLACK_CHANNEL" "$val" && ok "Slack channel saved"
                ;;
            5)
                info "Email (SMTP) setup"
                dimtext "Gmail users: enable 2FA first, then create an App Password"
                dimtext "at https://myaccount.google.com/apppasswords"
                printf "\n"
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

if [[ "$OS_TYPE" == "Linux" ]]; then
    # Firewall hardening only on Linux VPS/server
    printf "\n"
    draw_box << EOF
${BRED}${BOLD}Security Hardening${RST}

UFW (firewall) blocks all incoming traffic except SSH
and Tailscale. Fail2ban protects against brute-force.

${BOLD}Briven binds ONLY to your Tailscale IP${RST} — it is
never exposed on public interfaces.
EOF
    printf "\n"

    select_from_list "Enable UFW firewall + Fail2ban?" \
        "Yes — enable firewall hardening (recommended)" \
        "No  — skip security hardening"

    if [[ "$SELECT_RESULT" -eq 1 ]]; then
        # UFW configuration
        if command -v ufw >/dev/null 2>&1; then
            info "Configuring UFW firewall..."
            sudo ufw default deny incoming 2>/dev/null || true
            sudo ufw default allow outgoing 2>/dev/null || true
            sudo ufw allow ssh 2>/dev/null || true
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
else
    # macOS / WSL — no UFW/Fail2ban needed
    dimtext "Firewall hardening skipped (not applicable on $OS_TYPE)"
    if [[ "$OS_TYPE" == "macOS" ]]; then
        dimtext "macOS has its own built-in firewall (System Settings → Network → Firewall)"
    fi
fi

# ╔══════════════════════════════════════════════════════════╗
# ║          Step 9 — Tailscale ACL + Systemd                ║
# ╚══════════════════════════════════════════════════════════╝
step "Tailscale ACL & system service"

# Determine the bind address
BIND_HOST="$TS_IP"
if [[ "$BIND_HOST" == "0.0.0.0" || -z "$BIND_HOST" ]]; then
    BIND_HOST="0.0.0.0"
fi

# ── Tailscale ACL (optional, only when Tailscale is available) ──
if $TAILSCALE_AVAILABLE; then
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

        if "$INSTALL_DIR/.venv/bin/python" "$INSTALL_DIR/tools/tailscale.py" --help 2>&1 | grep -q "apply-acl"; then
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
                warn "ACL apply failed — configure ACL manually in Tailscale admin console"
            fi
        else
            dimtext "ACL auto-apply not available — configure manually"
            dimtext "Visit: https://login.tailscale.com/admin/acls"
        fi
    else
        dimtext "Skipped ACL — any tailnet device can access Briven"
    fi
else
    dimtext "Tailscale not installed — skipping ACL setup"
fi

# ── System service (platform-dependent) ────────────────────
HAS_SYSTEMD=false
SERVICE_OK=false

if [[ "$OS_TYPE" == "Linux" ]] && command -v systemctl >/dev/null 2>&1; then
    HAS_SYSTEMD=true
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
ExecStart=$INSTALL_DIR/.venv/bin/python3 run_ui.py --host $BIND_HOST --port $BRIVEN_PORT
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
else
    # macOS / WSL — create a start script instead
    info "Creating start script..."
    cat > "$INSTALL_DIR/start.sh" << STARTSCRIPT
#!/usr/bin/env bash
# Start Briven — run this script to launch the Web UI
cd "$INSTALL_DIR"
source .venv/bin/activate
exec python3 run_ui.py --host ${BIND_HOST} --port ${BRIVEN_PORT}
STARTSCRIPT
    chmod +x "$INSTALL_DIR/start.sh"
    ok "Created $INSTALL_DIR/start.sh"
fi

# ╔══════════════════════════════════════════════════════════╗
# ║              Step 10 — Start & Verify                    ║
# ╚══════════════════════════════════════════════════════════╝
step "Start Briven"

if $HAS_SYSTEMD; then
    sudo systemctl daemon-reload
    sudo systemctl enable --now briven

    info "Starting service..."
    sleep 5

    # Status check with retry
    for _check in 1 2 3; do
        if sudo systemctl is-active --quiet briven; then
            SERVICE_OK=true
            break
        fi
        sleep 3
    done

    # If service failed, check why
    if ! $SERVICE_OK; then
        FAIL_LOG=$(journalctl -u briven --no-pager -n 20 2>/dev/null || echo "")
        if echo "$FAIL_LOG" | grep -qi "ModuleNotFoundError\|ImportError"; then
            warn "Service failed — missing Python dependency. Check: journalctl -u briven -n 50"
        elif echo "$FAIL_LOG" | grep -qi "address already in use\|bind"; then
            warn "Port $BRIVEN_PORT is already in use. Stop the existing process or change BRIVEN_PORT."
        fi
    fi
else
    # macOS / WSL — no systemd, just show how to start
    info "No systemd available — Briven will not auto-start."
    dimtext "Start Briven manually with:"
    dimtext "  bash $INSTALL_DIR/start.sh"
    printf "\n"

    select_from_list "Start Briven now?" \
        "Yes — start Briven in the background" \
        "No  — I'll start it manually later"

    if [[ "$SELECT_RESULT" -eq 1 ]]; then
        info "Starting Briven..."
        nohup bash "$INSTALL_DIR/start.sh" > "$INSTALL_DIR/briven.log" 2>&1 &
        BRIVEN_PID=$!
        sleep 3
        if kill -0 "$BRIVEN_PID" 2>/dev/null; then
            SERVICE_OK=true
            ok "Briven started (PID: $BRIVEN_PID)"
            dimtext "Log file: $INSTALL_DIR/briven.log"
        else
            warn "Briven failed to start. Check: cat $INSTALL_DIR/briven.log"
        fi
    fi
fi

# ╔══════════════════════════════════════════════════════════╗
# ║                    Final Summary                         ║
# ╚══════════════════════════════════════════════════════════╝
printf "\n\n"

# Build the access URL
if [[ "$TS_IP" != "0.0.0.0" ]]; then
    ACCESS_URL="http://$TS_IP:$BRIVEN_PORT"
else
    ACCESS_URL="http://localhost:$BRIVEN_PORT"
fi

if $SERVICE_OK; then
    draw_box << EOF
${GRN}${BOLD}✓  Installation Complete!${RST}

${BOLD}Briven is running and ready to use.${RST}

  ${BRED}${BOLD}Web UI:${RST}        ${ACCESS_URL}
  ${BRED}${BOLD}Tailscale IP:${RST}  ${TS_IP}
  ${BRED}${BOLD}Port:${RST}          ${BRIVEN_PORT}
  ${BRED}${BOLD}Status:${RST}        ${GRN}active (running)${RST}
EOF
else
    draw_box << EOF
${YEL}${BOLD}⚠  Installation Complete (service issue)${RST}

The service may still be initializing, or there may
be an issue. Check logs for details.

  ${BRED}${BOLD}Web UI:${RST}        ${ACCESS_URL}
  ${BRED}${BOLD}Tailscale IP:${RST}  ${TS_IP}
  ${BRED}${BOLD}Port:${RST}          ${BRIVEN_PORT}
  ${BRED}${BOLD}Status:${RST}        ${YEL}check logs below${RST}
EOF
fi

# ── Post-install checks ────────────────────────────────────
CHANNELS_CONFIGURED=$(grep -cE "^(TELEGRAM_|DISCORD_|SLACK_|WHATSAPP_|EMAIL_)" "$INSTALL_DIR/usr/.env" 2>/dev/null || echo "0")
if [[ "$CHANNELS_CONFIGURED" -gt 0 ]]; then
    ok "$CHANNELS_CONFIGURED messaging channel variable(s) configured"
else
    warn "No messaging channels configured — Web UI only. Add channels later in usr/.env"
fi

printf "\n"
if $HAS_SYSTEMD; then
    draw_box << EOF
${BOLD}Quick Reference${RST}

  ${BRED}Edit API keys:${RST}     nano $INSTALL_DIR/usr/.env
  ${BRED}Edit settings:${RST}     nano $INSTALL_DIR/usr/settings.json
  ${BRED}Restart:${RST}           sudo systemctl restart briven
  ${BRED}Logs:${RST}              journalctl -u briven -f
  ${BRED}Status:${RST}            sudo systemctl status briven
  ${BRED}Firewall:${RST}          sudo ufw status

${DIM}Tailscale admin:  https://login.tailscale.com/admin${RST}
${DIM}Documentation:    https://github.com/flandriendev/briven${RST}
EOF
else
    draw_box << EOF
${BOLD}Quick Reference${RST}

  ${BRED}Start Briven:${RST}      bash $INSTALL_DIR/start.sh
  ${BRED}Edit API keys:${RST}     nano $INSTALL_DIR/usr/.env
  ${BRED}Edit settings:${RST}     nano $INSTALL_DIR/usr/settings.json
  ${BRED}Stop:${RST}              kill \$(lsof -ti:$BRIVEN_PORT)
  ${BRED}Log file:${RST}          $INSTALL_DIR/briven.log

${DIM}Documentation:    https://github.com/flandriendev/briven${RST}
EOF
fi

if ! $SERVICE_OK; then
    printf "\n"
    if $HAS_SYSTEMD; then
        warn "Service may not be running. Try these commands:"
        dimtext "  journalctl -u briven -n 50     # View recent logs"
        dimtext "  sudo systemctl restart briven  # Restart the service"
        dimtext "  sudo systemctl status briven   # Check current status"
    else
        warn "Briven is not running. Start it with:"
        dimtext "  bash $INSTALL_DIR/start.sh"
    fi
fi

printf "\n"
printf "  ${BRED}${BOLD}Thank you for installing Briven!${RST}\n"
if [[ "$TS_IP" != "0.0.0.0" && "$TS_IP" != "127.0.0.1" ]]; then
    printf "  ${DIM}Open ${ACCESS_URL} from any device on your tailnet.${RST}\n"
else
    printf "  ${DIM}Open ${ACCESS_URL} to access the Web UI.${RST}\n"
fi
printf "\n"
