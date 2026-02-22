"""
tools/slack.py — Slack notification tool for Briven.

Sends messages to a Slack channel via Incoming Webhooks or Bot API.
Requires one of:
  - SLACK_WEBHOOK_URL in .env (easiest — no bot token needed)
  - SLACK_BOT_TOKEN + SLACK_CHANNEL in .env (richer features)

Usage:
    python tools/slack.py --message "Task complete"
    python tools/slack.py --message "Deploy finished" --channel "#ops"

Docs:
  Webhooks: https://api.slack.com/messaging/webhooks
  Bot API:  https://api.slack.com/methods/chat.postMessage
"""

import argparse
import json
import os
import sys
import urllib.request


def send_webhook(
    message: str,
    webhook_url: str | None = None,
) -> dict:
    """Send a message via Slack Incoming Webhook (simplest setup)."""
    url = webhook_url or os.environ.get("SLACK_WEBHOOK_URL")
    if not url:
        raise ValueError("SLACK_WEBHOOK_URL not set in environment or .env")

    payload = json.dumps({"text": message}).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        body = resp.read().decode("utf-8")
        # Webhook returns "ok" as plain text on success
        return {"ok": body.strip() == "ok", "response": body.strip()}


def send_bot_message(
    message: str,
    channel: str | None = None,
    bot_token: str | None = None,
) -> dict:
    """Send a message via Slack Bot API (chat.postMessage)."""
    token = bot_token or os.environ.get("SLACK_BOT_TOKEN")
    ch = channel or os.environ.get("SLACK_CHANNEL")

    if not token:
        raise ValueError("SLACK_BOT_TOKEN not set in environment or .env")
    if not ch:
        raise ValueError("SLACK_CHANNEL not set (--channel or SLACK_CHANNEL env var)")

    url = "https://slack.com/api/chat.postMessage"
    payload = json.dumps({
        "channel": ch,
        "text": message,
    }).encode("utf-8")

    req = urllib.request.Request(
        url,
        data=payload,
        headers={
            "Content-Type": "application/json; charset=utf-8",
            "Authorization": f"Bearer {token}",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read().decode("utf-8"))


def send_message(
    message: str,
    channel: str | None = None,
    webhook_url: str | None = None,
    bot_token: str | None = None,
) -> dict:
    """Send a Slack message using whichever method is configured.
    Prefers webhook (simpler), falls back to bot API."""
    wh = webhook_url or os.environ.get("SLACK_WEBHOOK_URL")
    if wh:
        return send_webhook(message, webhook_url=wh)
    return send_bot_message(message, channel=channel, bot_token=bot_token)


def main() -> None:
    parser = argparse.ArgumentParser(description="Send Slack messages from Briven")
    parser.add_argument("--message", "-m", required=True, help="Message text")
    parser.add_argument("--channel", help="Slack channel (e.g. #general)")
    parser.add_argument("--webhook-url", help="Incoming Webhook URL")
    parser.add_argument("--bot-token", help="Bot OAuth token (overrides SLACK_BOT_TOKEN)")
    args = parser.parse_args()

    try:
        result = send_message(
            message=args.message,
            channel=args.channel,
            webhook_url=args.webhook_url,
            bot_token=args.bot_token,
        )
        if result.get("ok"):
            print(f"[slack] Message sent successfully")
        else:
            print(f"[slack] API error: {result}", file=sys.stderr)
            sys.exit(1)
    except Exception as e:
        print(f"[slack] Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
