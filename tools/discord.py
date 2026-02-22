"""
tools/discord.py — Discord notification tool for Briven.

Sends messages to a Discord channel via Webhook URL.
Requires: DISCORD_WEBHOOK_URL in .env

Usage:
    python tools/discord.py --message "Task complete"
    python tools/discord.py --message "Alert!" --username "Briven Bot"

Docs: https://discord.com/developers/docs/resources/webhook#execute-webhook
"""

import argparse
import json
import os
import sys
import urllib.request


def send_message(
    message: str,
    webhook_url: str | None = None,
    username: str | None = None,
) -> dict:
    """Send a message to a Discord channel via webhook."""
    url = webhook_url or os.environ.get("DISCORD_WEBHOOK_URL")
    if not url:
        raise ValueError("DISCORD_WEBHOOK_URL not set in environment or .env")

    payload: dict = {"content": message}
    if username:
        payload["username"] = username

    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        # Discord returns 204 No Content on success
        if resp.status == 204:
            return {"ok": True}
        body = resp.read().decode("utf-8")
        try:
            return json.loads(body)
        except json.JSONDecodeError:
            return {"ok": resp.status < 300, "response": body}


def send_embed(
    title: str,
    description: str,
    color: int = 0x5865F2,
    webhook_url: str | None = None,
    username: str | None = None,
) -> dict:
    """Send a rich embed to Discord (useful for structured notifications)."""
    url = webhook_url or os.environ.get("DISCORD_WEBHOOK_URL")
    if not url:
        raise ValueError("DISCORD_WEBHOOK_URL not set in environment or .env")

    payload: dict = {
        "embeds": [{
            "title": title,
            "description": description,
            "color": color,
        }],
    }
    if username:
        payload["username"] = username

    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        if resp.status == 204:
            return {"ok": True}
        body = resp.read().decode("utf-8")
        try:
            return json.loads(body)
        except json.JSONDecodeError:
            return {"ok": resp.status < 300, "response": body}


def main() -> None:
    parser = argparse.ArgumentParser(description="Send Discord messages from Briven")
    parser.add_argument("--message", "-m", required=True, help="Message text")
    parser.add_argument("--webhook-url", help="Discord webhook URL")
    parser.add_argument("--username", default="Briven", help="Bot display name")
    args = parser.parse_args()

    try:
        result = send_message(
            message=args.message,
            webhook_url=args.webhook_url,
            username=args.username,
        )
        if result.get("ok"):
            print("[discord] Message sent successfully")
        else:
            print(f"[discord] API error: {result}", file=sys.stderr)
            sys.exit(1)
    except Exception as e:
        print(f"[discord] Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
