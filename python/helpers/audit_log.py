"""
python/helpers/audit_log.py

Structured audit logging for security-relevant events.

Writes JSON log entries to usr/logs/audit.jsonl (one JSON object per line).
Handles log rotation by capping the file at MAX_ENTRIES lines.

Events logged:
  - login_success / login_failed
  - login_locked (brute force lockout triggered)
  - settings_changed
  - task_created / task_deleted
  - extension_blocked (security check)
  - api_key_auth_failed
  - rate_limit_hit
"""

import json
import os
import threading
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from python.helpers.files import get_abs_path, make_dirs

AUDIT_LOG_FILE = "usr/logs/audit.jsonl"
MAX_ENTRIES = 5000
_lock = threading.RLock()


def _get_log_path() -> str:
    path = get_abs_path(AUDIT_LOG_FILE)
    make_dirs(path)
    return path


def log_event(
    event: str,
    ip: Optional[str] = None,
    user: Optional[str] = None,
    detail: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> None:
    """
    Append a structured audit event to the log file.

    Args:
        event: Event type (e.g. "login_failed", "settings_changed")
        ip: Client IP address
        user: Username if applicable
        detail: Human-readable description
        metadata: Additional structured data
    """
    entry: Dict[str, Any] = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "event": event,
    }
    if ip:
        entry["ip"] = ip
    if user:
        entry["user"] = user
    if detail:
        entry["detail"] = detail
    if metadata:
        entry["meta"] = metadata

    line = json.dumps(entry, separators=(",", ":")) + "\n"

    with _lock:
        try:
            path = _get_log_path()
            with open(path, "a", encoding="utf-8") as f:
                f.write(line)

            # Rotate: if file exceeds MAX_ENTRIES, trim to last half
            _maybe_rotate(path)
        except Exception:
            pass  # Audit logging must never crash the app


def _maybe_rotate(path: str) -> None:
    """Trim log file if it exceeds MAX_ENTRIES lines."""
    try:
        size = os.path.getsize(path)
        # Only check line count if file is large enough to matter (~100 bytes/line)
        if size < MAX_ENTRIES * 50:
            return

        with open(path, "r", encoding="utf-8") as f:
            lines = f.readlines()

        if len(lines) > MAX_ENTRIES:
            # Keep the most recent half
            keep = lines[-(MAX_ENTRIES // 2):]
            with open(path, "w", encoding="utf-8") as f:
                f.writelines(keep)
    except Exception:
        pass


def get_recent_events(limit: int = 100, event_type: Optional[str] = None) -> list:
    """Read the most recent audit events."""
    with _lock:
        try:
            path = _get_log_path()
            if not os.path.exists(path):
                return []
            with open(path, "r", encoding="utf-8") as f:
                lines = f.readlines()

            events = []
            for line in reversed(lines):
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                    if event_type and entry.get("event") != event_type:
                        continue
                    events.append(entry)
                    if len(events) >= limit:
                        break
                except json.JSONDecodeError:
                    continue
            return events
        except Exception:
            return []
