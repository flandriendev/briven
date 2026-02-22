"""
python/helpers/scheduler_history.py

Persistent execution history for the task scheduler.

Appends a record for every task run (success or failure) to a JSON file
at usr/scheduler/history.json. This provides the audit trail that the
scheduler was missing — you can see what ran, when, how long it took,
and whether it succeeded or failed.

Configurable via settings:
  - scheduler_history_enabled (default: True)
  - scheduler_history_max_entries (default: 200)
"""

import json
import threading
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from python.helpers.files import get_abs_path, make_dirs, read_file, write_file
from python.helpers.print_style import PrintStyle

HISTORY_FILE = "usr/scheduler/history.json"
_lock = threading.RLock()


def _load_history() -> List[Dict[str, Any]]:
    """Load history entries from disk."""
    try:
        path = get_abs_path(HISTORY_FILE)
        content = read_file(path)
        if content:
            data = json.loads(content)
            if isinstance(data, list):
                return data
    except Exception:
        pass
    return []


def _save_history(entries: List[Dict[str, Any]]) -> None:
    """Save history entries to disk."""
    path = get_abs_path(HISTORY_FILE)
    make_dirs(path)
    write_file(path, json.dumps(entries, indent=2, default=str))


def record_task_run(
    task_uuid: str,
    task_name: str,
    task_type: str,
    status: str,
    result: Optional[str] = None,
    error: Optional[str] = None,
    started_at: Optional[datetime] = None,
    duration_seconds: Optional[float] = None,
    retry_count: int = 0,
) -> None:
    """
    Append a task execution record to the history file.

    Called from task_scheduler._run_task() on both success and failure.
    """
    from python.helpers import settings

    s = settings.get_settings()
    if not s.get("scheduler_history_enabled", True):
        return

    max_entries = s.get("scheduler_history_max_entries", 200)

    entry: Dict[str, Any] = {
        "task_uuid": task_uuid,
        "task_name": task_name,
        "task_type": task_type,
        "status": status,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "retry_count": retry_count,
    }

    if started_at:
        entry["started_at"] = started_at.isoformat()
    if duration_seconds is not None:
        entry["duration_seconds"] = round(duration_seconds, 2)
    if result:
        # Truncate long results for storage efficiency
        entry["result"] = result[:500] if len(result) > 500 else result
    if error:
        entry["error"] = error[:500] if len(error) > 500 else error

    with _lock:
        try:
            history = _load_history()
            history.append(entry)

            # Trim to max entries (keep most recent)
            if len(history) > max_entries:
                history = history[-max_entries:]

            _save_history(history)
        except Exception as e:
            PrintStyle.warning(f"Failed to record scheduler history: {e}")


def get_task_history(
    task_uuid: Optional[str] = None,
    limit: int = 50,
) -> List[Dict[str, Any]]:
    """
    Retrieve execution history, optionally filtered by task UUID.
    Returns most recent entries first.
    """
    with _lock:
        history = _load_history()

    if task_uuid:
        history = [h for h in history if h.get("task_uuid") == task_uuid]

    # Most recent first
    history.reverse()
    return history[:limit]
