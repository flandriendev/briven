"""
tools/email_send.py — Email notification tool for Briven.

Sends email via SMTP. Works with Gmail, Fastmail, Sendgrid SMTP relay, etc.
Requires: EMAIL_SMTP_HOST, EMAIL_SMTP_PORT, EMAIL_USER, EMAIL_PASSWORD in .env

Usage:
    python tools/email_send.py --to user@example.com --subject "Alert" --body "Task done"
    python tools/email_send.py --to user@example.com --subject "Report" --body-file report.html --html
"""

import argparse
import os
import smtplib
import sys
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path


def send_email(
    to: str,
    subject: str,
    body: str,
    from_addr: str | None = None,
    smtp_host: str | None = None,
    smtp_port: int | None = None,
    username: str | None = None,
    password: str | None = None,
    html: bool = False,
) -> None:
    """Send an email via SMTP with TLS."""
    _host = smtp_host or os.environ.get("EMAIL_SMTP_HOST", "smtp.gmail.com")
    _port = smtp_port or int(os.environ.get("EMAIL_SMTP_PORT", "587"))
    _user = username or os.environ.get("EMAIL_USER")
    _pass = password or os.environ.get("EMAIL_PASSWORD")
    _from = from_addr or _user

    if not _user or not _pass:
        raise ValueError("EMAIL_USER and EMAIL_PASSWORD must be set in .env")

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = _from
    msg["To"] = to

    mime_type = "html" if html else "plain"
    msg.attach(MIMEText(body, mime_type, "utf-8"))

    with smtplib.SMTP(_host, _port, timeout=15) as server:
        server.ehlo()
        server.starttls()
        server.login(_user, _pass)
        server.sendmail(_from, [to], msg.as_string())


def main() -> None:
    parser = argparse.ArgumentParser(description="Send email from Briven")
    parser.add_argument("--to", required=True, help="Recipient email address")
    parser.add_argument("--subject", "-s", required=True, help="Email subject")
    parser.add_argument("--body", "-b", help="Email body text")
    parser.add_argument("--body-file", help="Read body from this file")
    parser.add_argument("--html", action="store_true", help="Send as HTML email")
    parser.add_argument("--from", dest="from_addr", help="Sender address (overrides EMAIL_USER)")
    parser.add_argument("--smtp-host", help="SMTP host (overrides EMAIL_SMTP_HOST)")
    parser.add_argument("--smtp-port", type=int, help="SMTP port (overrides EMAIL_SMTP_PORT)")
    args = parser.parse_args()

    if args.body_file:
        body = Path(args.body_file).read_text(encoding="utf-8")
    elif args.body:
        body = args.body
    else:
        print("[email] --body or --body-file required", file=sys.stderr)
        sys.exit(1)

    try:
        send_email(
            to=args.to,
            subject=args.subject,
            body=body,
            from_addr=args.from_addr,
            smtp_host=args.smtp_host,
            smtp_port=args.smtp_port,
            html=args.html,
        )
        print(f"[email] Sent '{args.subject}' to {args.to}")
    except Exception as e:
        print(f"[email] Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
