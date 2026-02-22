"""
tools/telegram.py — Telegram notification tool for Briven.

Sends messages to a Telegram chat via Bot API.
Requires: TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID in .env

Usage:
    python tools/telegram.py --message "Task complete"
    python tools/telegram.py --message "Error occurred" --parse-mode HTML
"""

import argparse
import os
import sys
import urllib.parse
import urllib.request
import json


def send_message(
    text: str,
    bot_token: str | None = None,
    chat_id: str | None = None,
    parse_mode: str = "Markdown",
) -> dict:
    """Send a message to a Telegram chat. Returns the API response."""
    token = bot_token or os.environ.get("TELEGRAM_BOT_TOKEN")
    chat = chat_id or os.environ.get("TELEGRAM_CHAT_ID")

    if not token:
        raise ValueError("TELEGRAM_BOT_TOKEN not set in environment or .env")
    if not chat:
        raise ValueError("TELEGRAM_CHAT_ID not set in environment or .env")

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = json.dumps({
        "chat_id": chat,
        "text": text,
        "parse_mode": parse_mode,
    }).encode("utf-8")

    req = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read().decode("utf-8"))


def main() -> None:
    parser = argparse.ArgumentParser(description="Send Telegram messages from Briven")
    parser.add_argument("--message", "-m", required=True, help="Message text to send")
    parser.add_argument("--token", help="Bot token (overrides TELEGRAM_BOT_TOKEN env var)")
    parser.add_argument("--chat-id", help="Chat ID (overrides TELEGRAM_CHAT_ID env var)")
    parser.add_argument("--parse-mode", default="Markdown", choices=["Markdown", "HTML", "MarkdownV2"])
    args = parser.parse_args()

    try:
        result = send_message(
            text=args.message,
            bot_token=args.token,
            chat_id=args.chat_id,
            parse_mode=args.parse_mode,
        )
        if result.get("ok"):
            print(f"[telegram] Message sent (message_id={result['result']['message_id']})")
        else:
            print(f"[telegram] API error: {result}", file=sys.stderr)
            sys.exit(1)
    except Exception as e:
        print(f"[telegram] Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
