"""
tools/tailscale.py — Tailscale integration helpers for Briven.

Briven prefers Tailscale for all network access:
  - Zero-trust mesh networking
  - No exposed public ports
  - Secure access from any device on your tailnet

Usage:
    python tools/tailscale.py --status
    python tools/tailscale.py --ip
    python tools/tailscale.py --peers
    python tools/tailscale.py --serve --port 8000
"""

import argparse
import json
import subprocess
import sys
from typing import Optional


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
        status_icon = "🟢" if p["online"] else "🔴"
        print(f"    {status_icon}  {p['hostname']} ({p['ip']})  [{p['os']}]")
    print("=" * 48)
    print(f"\n  Bind Briven to Tailscale IP for secure access:")
    print(f"    uvicorn run_ui:app --host {ip4 or '100.x.x.x'} --port 8000")
    print()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Tailscale helpers for Briven",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--status", action="store_true", help="Show Tailscale status")
    parser.add_argument("--ip", action="store_true", help="Print this machine's Tailscale IPv4")
    parser.add_argument("--peers", action="store_true", help="List connected peers as JSON")
    parser.add_argument("--serve", action="store_true", help="Serve a local port via Tailscale Serve")
    parser.add_argument("--port", type=int, default=8000, help="Port to serve (used with --serve)")

    args = parser.parse_args()

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
