"""
python/helpers/login_guard.py

Brute-force protection for the login endpoint.

Tracks failed login attempts per IP address and enforces:
  - Progressive delay after failures (1s, 2s, 4s, 8s...)
  - Lockout after MAX_ATTEMPTS failures within WINDOW_SECONDS
  - Lockout duration: LOCKOUT_SECONDS (default 15 minutes)

All events are written to the audit log.
"""

import time
import threading
from typing import Dict, Tuple

MAX_ATTEMPTS = 5
WINDOW_SECONDS = 300      # 5-minute window
LOCKOUT_SECONDS = 900     # 15-minute lockout

_lock = threading.RLock()
# ip -> (attempt_count, first_attempt_time, lockout_until)
_attempts: Dict[str, Tuple[int, float, float]] = {}


def check_rate_limit(ip: str) -> Tuple[bool, str]:
    """
    Check if a login attempt is allowed for the given IP.

    Returns:
        (allowed, reason) — True if login attempt is permitted,
        False with a reason string if blocked.
    """
    now = time.time()

    with _lock:
        if ip in _attempts:
            count, first_time, lockout_until = _attempts[ip]

            # Check lockout
            if lockout_until > now:
                remaining = int(lockout_until - now)
                return False, f"Too many failed attempts. Try again in {remaining}s."

            # Reset if window expired
            if now - first_time > WINDOW_SECONDS:
                _attempts[ip] = (0, now, 0)
                return True, ""

            # Check if at threshold
            if count >= MAX_ATTEMPTS:
                # Apply lockout
                _attempts[ip] = (count, first_time, now + LOCKOUT_SECONDS)
                _log_lockout(ip, count)
                return False, f"Too many failed attempts. Try again in {LOCKOUT_SECONDS // 60} minutes."

        return True, ""


def record_failure(ip: str) -> int:
    """Record a failed login attempt. Returns the current failure count."""
    now = time.time()

    with _lock:
        if ip in _attempts:
            count, first_time, lockout_until = _attempts[ip]
            # Reset window if expired
            if now - first_time > WINDOW_SECONDS:
                _attempts[ip] = (1, now, 0)
                return 1
            new_count = count + 1
            _attempts[ip] = (new_count, first_time, lockout_until)
            return new_count
        else:
            _attempts[ip] = (1, now, 0)
            return 1


def record_success(ip: str) -> None:
    """Clear attempt tracking on successful login."""
    with _lock:
        _attempts.pop(ip, None)


def get_delay(ip: str) -> float:
    """Get progressive delay in seconds based on failure count."""
    with _lock:
        if ip not in _attempts:
            return 0
        count = _attempts[ip][0]
    # Exponential backoff: 1, 2, 4, 8... capped at 16s
    if count <= 0:
        return 0
    return min(2 ** (count - 1), 16)


def _log_lockout(ip: str, count: int) -> None:
    """Log lockout event to audit log."""
    try:
        from python.helpers.audit_log import log_event
        log_event(
            event="login_locked",
            ip=ip,
            detail=f"Locked out after {count} failed attempts for {LOCKOUT_SECONDS}s",
        )
    except Exception:
        pass
