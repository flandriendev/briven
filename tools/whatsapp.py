"""
tools/whatsapp.py — WhatsApp notification tool for Briven.

Sends messages via WhatsApp Business Cloud API (Meta).
Requires: WHATSAPP_TOKEN, WHATSAPP_PHONE_ID, WHATSAPP_RECIPIENT in .env

Usage:
    python tools/whatsapp.py --message "Task complete" --to +1234567890
    python tools/whatsapp.py --message "Hello" --template hello_world

Docs: https://developers.facebook.com/docs/whatsapp/cloud-api
"""

import argparse
import json
import os
import sys
import urllib.request


def send_text(
    message: str,
    to: str | None = None,
    token: str | None = None,
    phone_id: str | None = None,
) -> dict:
    """Send a plain text WhatsApp message via Cloud API."""
    _token = token or os.environ.get("WHATSAPP_TOKEN")
    _phone_id = phone_id or os.environ.get("WHATSAPP_PHONE_ID")
    _to = to or os.environ.get("WHATSAPP_RECIPIENT")

    if not _token:
        raise ValueError("WHATSAPP_TOKEN not set")
    if not _phone_id:
        raise ValueError("WHATSAPP_PHONE_ID not set")
    if not _to:
        raise ValueError("Recipient phone number required (--to or WHATSAPP_RECIPIENT)")

    url = f"https://graph.facebook.com/v19.0/{_phone_id}/messages"
    payload = json.dumps({
        "messaging_product": "whatsapp",
        "to": _to.lstrip("+"),
        "type": "text",
        "text": {"body": message},
    }).encode("utf-8")

    req = urllib.request.Request(
        url,
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {_token}",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode("utf-8"))


def main() -> None:
    parser = argparse.ArgumentParser(description="Send WhatsApp messages from Briven")
    parser.add_argument("--message", "-m", required=True, help="Message text")
    parser.add_argument("--to", help="Recipient phone number (E.164 format, e.g. +12125551234)")
    parser.add_argument("--token", help="WhatsApp Cloud API token")
    parser.add_argument("--phone-id", help="WhatsApp phone number ID")
    args = parser.parse_args()

    try:
        result = send_text(
            message=args.message,
            to=args.to,
            token=args.token,
            phone_id=args.phone_id,
        )
        print(f"[whatsapp] Sent: {json.dumps(result, indent=2)}")
    except Exception as e:
        print(f"[whatsapp] Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
