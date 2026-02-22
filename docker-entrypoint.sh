#!/usr/bin/env bash
set -euo pipefail

BRIVEN_PORT="${BRIVEN_PORT:-8000}"
BIND_HOST="0.0.0.0"

# ── Tailscale (if auth key provided) ─────────────────────────
if [[ -n "${TAILSCALE_AUTHKEY:-}" ]]; then
    echo "[briven] Starting Tailscale daemon..."
    tailscaled \
        --state=/var/lib/tailscale/tailscaled.state \
        --socket=/var/run/tailscale/tailscaled.sock \
        --tun=userspace-networking &

    # Wait for daemon to be ready (up to 15s)
    for _ in $(seq 1 15); do
        if tailscale --socket=/var/run/tailscale/tailscaled.sock status >/dev/null 2>&1; then
            break
        fi
        sleep 1
    done

    echo "[briven] Authenticating with Tailscale..."
    if tailscale --socket=/var/run/tailscale/tailscaled.sock up \
        --authkey="$TAILSCALE_AUTHKEY" \
        --accept-routes \
        --accept-dns=false; then

        TS_IP=$(tailscale --socket=/var/run/tailscale/tailscaled.sock ip -4 2>/dev/null || echo "")
        if [[ -n "$TS_IP" ]]; then
            BIND_HOST="$TS_IP"
            echo "[briven] Tailscale connected: $TS_IP"
        fi
    else
        echo "[briven] WARNING: Tailscale auth failed — falling back to 0.0.0.0"
    fi
else
    echo "[briven] No TAILSCALE_AUTHKEY set — binding to 0.0.0.0"
    echo "[briven] Set TAILSCALE_AUTHKEY for zero-trust networking"
fi

# ── Environment file ─────────────────────────────────────────
if [[ ! -f usr/.env && -f usr/.env.example ]]; then
    cp usr/.env.example usr/.env
    echo "[briven] Created usr/.env from template — add your API keys"
fi

# ── Write host binding to .env ───────────────────────────────
if [[ -f usr/.env && "$BIND_HOST" != "0.0.0.0" ]]; then
    if grep -q "^WEB_UI_HOST=" usr/.env 2>/dev/null; then
        sed -i "s|^WEB_UI_HOST=.*|WEB_UI_HOST=$BIND_HOST|" usr/.env
    else
        printf '\nWEB_UI_HOST=%s\n' "$BIND_HOST" >> usr/.env
    fi
fi

# ── Start Briven ─────────────────────────────────────────────
echo "[briven] Starting on $BIND_HOST:$BRIVEN_PORT"
exec python run_ui.py --host "$BIND_HOST" --port "$BRIVEN_PORT"
