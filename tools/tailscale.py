"""
tools/tailscale.py — Tailscale integration + ACL management for Briven.

Briven prefers Tailscale for all network access:
  - Zero-trust mesh networking
  - No exposed public ports
  - ACL-enforced access control

Usage:
    python tools/tailscale.py --status
    python tools/tailscale.py --ip
    python tools/tailscale.py --peers
    python tools/tailscale.py --serve --port 8000
    python tools/tailscale.py --apply-acl
    python tools/tailscale.py --acl-status
"""

import argparse
import json
import logging
import os
import subprocess
import sys
from typing import Optional

import requests

logger = logging.getLogger("briven.tailscale")

# ── Tailscale API base ────────────────────────────────────────
TAILSCALE_API_BASE = "https://api.tailscale.com/api/v2"

# ── Default Briven ACL policy ────────────────────────────────
# Restrict access: only tag:admin devices can reach tag:briven-server on port 8000.
# All other traffic is denied by default.
# Customize this policy to match your tailnet's needs.
BRIVEN_ACL_POLICY = {
    "acls": [
        {
            "action": "accept",
            "src": ["tag:admin"],
            "dst": ["tag:briven-server:8000"],
        },
    ],
    "tagOwners": {
        "tag:admin": ["autogroup:admin"],
        "tag:briven-server": ["autogroup:admin"],
    },
    "ssh": [
        {
            "action": "accept",
            "src": ["tag:admin"],
            "dst": ["tag:briven-server"],
            "users": ["autogroup:nonroot", "root"],
        },
    ],
}


def _get_api_key() -> str:
    """Load TAILSCALE_API_KEY from environment or usr/.env."""
    key = os.environ.get("TAILSCALE_API_KEY", "")
    if key:
        return key

    # Try loading from usr/.env
    for env_path in ["usr/.env", ".env"]:
        try:
            with open(env_path) as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("TAILSCALE_API_KEY="):
                        val = line.split("=", 1)[1].strip().strip("\"'")
                        if val:
                            return val
        except FileNotFoundError:
            continue

    return ""


def _get_tailnet() -> str:
    """Determine the tailnet name. Uses TAILSCALE_TAILNET env or defaults to '-' (auto)."""
    return os.environ.get("TAILSCALE_TAILNET", "-")


def _api_headers(api_key: str) -> dict:
    """Build authorization headers for the Tailscale API."""
    return {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }


# ── ACL functions ─────────────────────────────────────────────

def get_acl(api_key: str, tailnet: str) -> dict:
    """Fetch the current ACL policy from the Tailscale API."""
    url = f"{TAILSCALE_API_BASE}/tailnet/{tailnet}/acl"
    resp = requests.get(url, headers=_api_headers(api_key), timeout=30)
    resp.raise_for_status()
    return resp.json()


def patch_acl(api_key: str, tailnet: str, new_acl: dict) -> dict:
    """
    Replace the tailnet ACL policy via POST (full replace).
    Returns the updated ACL from the API.
    """
    url = f"{TAILSCALE_API_BASE}/tailnet/{tailnet}/acl"
    resp = requests.post(
        url,
        headers=_api_headers(api_key),
        json=new_acl,
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


def _acl_already_applied(current_acl: dict) -> bool:
    """Check if the Briven ACL rules are already present in the current policy."""
    current_acls = current_acl.get("acls", [])
    for rule in current_acls:
        src = rule.get("src", [])
        dst = rule.get("dst", [])
        if "tag:admin" in src and any("tag:briven-server" in d for d in dst):
            return True
    return False


def apply_briven_acl() -> str:
    """
    Apply the Briven zero-trust ACL policy.

    - Validates the API key
    - Checks if ACL is already applied (idempotent)
    - Applies the policy if not present

    Returns a status message string.
    """
    api_key = _get_api_key()
    if not api_key:
        raise ValueError(
            "TAILSCALE_API_KEY not set. "
            "Add it to usr/.env or set the environment variable."
        )

    # Validate: API access tokens start with tskey-api-
    if not api_key.startswith("tskey-api-"):
        hint = ""
        if api_key.startswith("tskey-auth-"):
            hint = " You provided an auth key — ACLs require an API access token instead."
        raise ValueError(
            f"Invalid TAILSCALE_API_KEY format. "
            f"Expected a key starting with 'tskey-api-'.{hint} "
            f"Generate one at https://login.tailscale.com/admin/settings/keys"
        )

    tailnet = _get_tailnet()

    # Fetch current ACL
    try:
        current_acl = get_acl(api_key, tailnet)
    except requests.HTTPError as e:
        if e.response is not None and e.response.status_code == 401:
            raise ValueError("TAILSCALE_API_KEY is invalid or expired.") from e
        raise

    # Idempotent: skip if already applied
    if _acl_already_applied(current_acl):
        return "Briven ACL already applied — no changes needed."

    # Merge: preserve existing ACLs, add Briven rules
    merged = dict(current_acl)

    # Add Briven ACL rules
    existing_acls = merged.get("acls", [])
    existing_acls.extend(BRIVEN_ACL_POLICY["acls"])
    merged["acls"] = existing_acls

    # Merge tagOwners
    existing_tags = merged.get("tagOwners", {})
    for tag, owners in BRIVEN_ACL_POLICY["tagOwners"].items():
        if tag not in existing_tags:
            existing_tags[tag] = owners
    merged["tagOwners"] = existing_tags

    # Merge SSH rules
    existing_ssh = merged.get("ssh", [])
    for ssh_rule in BRIVEN_ACL_POLICY.get("ssh", []):
        existing_ssh.append(ssh_rule)
    merged["ssh"] = existing_ssh

    # Apply
    patch_acl(api_key, tailnet, merged)
    return "Briven ACL applied: tag:admin → tag:briven-server:8000 (deny all others)."


def acl_status() -> str:
    """Check whether the Briven ACL policy is active."""
    api_key = _get_api_key()
    if not api_key:
        return "TAILSCALE_API_KEY not set — cannot check ACL status."

    tailnet = _get_tailnet()
    try:
        current_acl = get_acl(api_key, tailnet)
    except requests.HTTPError as e:
        return f"Failed to fetch ACL: {e}"

    if _acl_already_applied(current_acl):
        return "Briven ACL is ACTIVE — tag:admin → tag:briven-server:8000."
    return "Briven ACL is NOT applied. Run: python tools/tailscale.py --apply-acl"


# ── CLI helpers (existing) ────────────────────────────────────

def run(cmd: list[str], capture: bool = True) -> subprocess.CompletedProcess:
    """Run a shell command and return the result."""
    return subprocess.run(
        cmd,
        capture_output=capture,
        text=True,
        check=False,
    )


def get_status() -> dict:
    """Return parsed `tailscale status --json` output."""
    result = run(["tailscale", "status", "--json"])
    if result.returncode != 0:
        raise RuntimeError(f"tailscale status failed: {result.stderr.strip()}")
    return json.loads(result.stdout)


def get_ip(family: str = "4") -> Optional[str]:
    """Return this machine's Tailscale IP address (IPv4 by default)."""
    flag = "-4" if family == "4" else "-6"
    result = run(["tailscale", "ip", flag])
    if result.returncode != 0:
        return None
    return result.stdout.strip()


def get_peers() -> list[dict]:
    """Return a list of connected Tailscale peers."""
    status = get_status()
    peers = status.get("Peer", {})
    return [
        {
            "hostname": info.get("HostName", "unknown"),
            "ip": info.get("TailscaleIPs", ["?"])[0],
            "online": info.get("Online", False),
            "os": info.get("OS", "unknown"),
        }
        for info in peers.values()
    ]


def is_running() -> bool:
    """Check whether the Tailscale daemon is active."""
    result = run(["tailscale", "status"])
    return result.returncode == 0


def tailscale_serve(port: int, bg: bool = True) -> None:
    """
    Expose a local port via Tailscale Serve (HTTPS on tailnet, no public exposure).
    Requires tailscaled >= 1.40 and the serve feature enabled on your account.
    """
    cmd = ["tailscale", "serve", str(port)]
    if bg:
        subprocess.Popen(cmd)
        print(f"[tailscale] Serving local port {port} via Tailscale (background).")
    else:
        run(cmd, capture=False)


def print_status() -> None:
    """Print a human-readable Tailscale status summary."""
    ip4 = get_ip("4")
    ip6 = get_ip("6")
    peers = get_peers()

    print("=" * 48)
    print("  Briven — Tailscale Status")
    print("=" * 48)
    if ip4:
        print(f"  IPv4 : {ip4}")
    if ip6:
        print(f"  IPv6 : {ip6}")
    print(f"  Peers: {len(peers)}")
    for p in peers:
        status_icon = "+" if p["online"] else "-"
        print(f"    {status_icon}  {p['hostname']} ({p['ip']})  [{p['os']}]")
    print("=" * 48)
    print(f"\n  Bind Briven to Tailscale IP for secure access:")
    print(f"    uvicorn run_ui:app --host {ip4 or '100.x.x.x'} --port 8000")
    print()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Tailscale helpers + ACL management for Briven",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--status", action="store_true", help="Show Tailscale status")
    parser.add_argument("--ip", action="store_true", help="Print this machine's Tailscale IPv4")
    parser.add_argument("--peers", action="store_true", help="List connected peers as JSON")
    parser.add_argument("--serve", action="store_true", help="Serve a local port via Tailscale Serve")
    parser.add_argument("--port", type=int, default=8000, help="Port to serve (used with --serve)")
    parser.add_argument("--apply-acl", action="store_true", help="Apply Briven zero-trust ACL policy")
    parser.add_argument("--acl-status", action="store_true", help="Check if Briven ACL is active")

    args = parser.parse_args()

    # ACL commands don't require the local tailscale daemon
    if args.apply_acl:
        try:
            msg = apply_briven_acl()
            print(f"[tailscale] {msg}")
        except (ValueError, requests.HTTPError) as e:
            print(f"[tailscale] ERROR: {e}", file=sys.stderr)
            sys.exit(1)
        return

    if args.acl_status:
        print(f"[tailscale] {acl_status()}")
        return

    # CLI commands below require the local tailscale daemon
    if not is_running():
        print("[tailscale] Tailscale daemon not running or not installed.", file=sys.stderr)
        print("  Install: https://tailscale.com/download", file=sys.stderr)
        sys.exit(1)

    if args.status:
        print_status()
    elif args.ip:
        ip = get_ip()
        if ip:
            print(ip)
        else:
            print("Not connected to Tailscale.", file=sys.stderr)
            sys.exit(1)
    elif args.peers:
        print(json.dumps(get_peers(), indent=2))
    elif args.serve:
        tailscale_serve(args.port, bg=False)
    else:
        print_status()


if __name__ == "__main__":
    main()
