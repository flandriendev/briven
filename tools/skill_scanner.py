"""
tools/skill_scanner.py — Malicious Skill Protection for Briven.

Scans skill files before they are loaded into the agent, using two layers:

  1. Static analysis — fast local check for dangerous code patterns
     (subprocess, eval, exec, network exfil, obfuscation, etc.)
  2. VirusTotal API — hash-based lookup (no file upload by default)
     to catch known-malicious payloads that bypass pattern matching.

Results are cached in data/skill_scan_cache.json so unchanged files
are not re-scanned on every load.

Usage:
    python tools/skill_scanner.py --path skills/my-skill/
    python tools/skill_scanner.py --path skills/my-skill/ --upload
    python tools/skill_scanner.py --path skills/my-skill/handler.py
    python tools/skill_scanner.py --cache-stats
    python tools/skill_scanner.py --clear-cache

Env Vars:
    VIRUSTOTAL_API_KEY  — required for VT lookups (free tier: 4 req/min)

Security: if running on a shared host, route outbound VT API calls
through a Tailscale exit node rather than the host's default interface.

Output:
    JSON verdict per file with overall pass/fail for the skill.
"""

import argparse
import hashlib
import json
import os
import re
import sys
import time
import urllib.request
import urllib.error
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

CACHE_PATH = Path(__file__).parent.parent / "data" / "skill_scan_cache.json"

VT_API_BASE = "https://www.virustotal.com/api/v3"

# Maximum file size we'll upload to VT (32 MB API limit, we cap at 5 MB)
MAX_UPLOAD_BYTES = 5 * 1024 * 1024

# File extensions to scan (skip images, data files, etc.)
SCANNABLE_EXTENSIONS = {
    ".py", ".js", ".ts", ".sh", ".bash", ".ps1", ".bat", ".cmd",
    ".rb", ".pl", ".php", ".lua", ".r", ".jl",
}

# Cache entries older than this are re-checked
CACHE_TTL_SECONDS = 7 * 24 * 3600  # 7 days

# ---------------------------------------------------------------------------
# Dangerous pattern definitions (static analysis layer)
# ---------------------------------------------------------------------------

# Each entry: (pattern_regex, severity, description)
DANGEROUS_PATTERNS: List[tuple[str, str, str]] = [
    # Process execution
    (r"\bsubprocess\.(call|run|Popen|check_output|check_call)\b", "high",
     "Subprocess execution"),
    (r"\bos\.(system|popen|exec[lv]?p?e?)\b", "high",
     "OS command execution"),
    (r"\bshutil\.rmtree\b", "medium",
     "Recursive directory deletion"),

    # Code injection
    (r"\beval\s*\(", "high", "eval() — arbitrary code execution"),
    (r"\bexec\s*\(", "high", "exec() — arbitrary code execution"),
    (r"\b__import__\s*\(", "high", "Dynamic import — code injection vector"),
    (r"\bcompile\s*\(.+['\"]exec['\"]", "high",
     "compile() with exec mode"),

    # Network exfiltration
    (r"\burllib\.request\.urlopen\b", "medium",
     "HTTP request — possible data exfiltration"),
    (r"\brequests\.(get|post|put|delete|patch)\b", "medium",
     "HTTP request via requests library"),
    (r"\bhttpx\.(get|post|put|delete|patch|Client)\b", "medium",
     "HTTP request via httpx"),
    (r"\bsocket\.socket\b", "medium",
     "Raw socket — possible network access"),
    (r"\bparamiko\b", "medium",
     "SSH library — possible remote access"),

    # File system abuse
    (r"\bopen\s*\(\s*['\"]/(etc|proc|sys|dev)/", "high",
     "Access to sensitive system paths"),
    (r"\bos\.environ\b.*\b(KEY|TOKEN|SECRET|PASSWORD)\b", "medium",
     "Environment variable access (secrets)"),
    (r"\bkeyring\b", "medium",
     "System keyring access"),

    # Obfuscation / evasion
    (r"\\x[0-9a-fA-F]{2}.*\\x[0-9a-fA-F]{2}.*\\x[0-9a-fA-F]{2}", "high",
     "Hex-encoded strings (possible obfuscation)"),
    (r"\bbase64\.b64decode\b", "low",
     "Base64 decoding (check context)"),
    (r"\bcodecs\.decode\b.*rot", "medium",
     "ROT encoding (obfuscation)"),
    (r"\bmarshall\.loads\b", "high",
     "Marshal deserialization — code execution"),
    (r"\bpickle\.loads?\b", "high",
     "Pickle deserialization — code execution"),
    (r"\bcPickle\.loads?\b", "high",
     "cPickle deserialization — code execution"),

    # Privilege escalation
    (r"\bctypes\.cdll\b", "high",
     "Native library loading via ctypes"),
    (r"\bos\.set(uid|gid|euid|egid)\b", "high",
     "Privilege manipulation"),
]


# ---------------------------------------------------------------------------
# Cache management
# ---------------------------------------------------------------------------

def _load_cache() -> Dict[str, Any]:
    """Load scan cache from disk."""
    try:
        if CACHE_PATH.exists():
            return json.loads(CACHE_PATH.read_text(encoding="utf-8"))
    except Exception:
        pass
    return {}


def _save_cache(cache: Dict[str, Any]) -> None:
    """Persist scan cache to disk."""
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    CACHE_PATH.write_text(
        json.dumps(cache, indent=2, default=str), encoding="utf-8"
    )


def _is_cache_fresh(entry: Dict[str, Any]) -> bool:
    """Check if a cache entry is still valid."""
    scanned_at = entry.get("scanned_at", "")
    if not scanned_at:
        return False
    try:
        ts = datetime.fromisoformat(scanned_at)
        age = (datetime.now(timezone.utc) - ts).total_seconds()
        return age < CACHE_TTL_SECONDS
    except Exception:
        return False


def clear_cache() -> Dict[str, Any]:
    """Clear the scan cache."""
    _save_cache({})
    return {"success": True, "message": "Scan cache cleared"}


def cache_stats() -> Dict[str, Any]:
    """Return statistics about the scan cache."""
    cache = _load_cache()
    total = len(cache)
    fresh = sum(1 for e in cache.values() if _is_cache_fresh(e))
    stale = total - fresh

    by_verdict = {}
    for entry in cache.values():
        v = entry.get("verdict", "unknown")
        by_verdict[v] = by_verdict.get(v, 0) + 1

    return {
        "success": True,
        "total_entries": total,
        "fresh": fresh,
        "stale": stale,
        "by_verdict": by_verdict,
    }


# ---------------------------------------------------------------------------
# File hashing
# ---------------------------------------------------------------------------

def sha256_file(file_path: Path) -> str:
    """Compute SHA-256 hash of a file."""
    h = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


# ---------------------------------------------------------------------------
# Static analysis (Layer 1 — fast, local)
# ---------------------------------------------------------------------------

def static_scan(file_path: Path) -> Dict[str, Any]:
    """
    Scan a single file for dangerous code patterns.

    Returns:
        dict with findings list and severity assessment
    """
    try:
        content = file_path.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        return {"error": str(e), "findings": []}

    findings: List[Dict[str, str]] = []

    for pattern_re, severity, description in DANGEROUS_PATTERNS:
        matches = re.findall(pattern_re, content)
        if matches:
            # Count occurrences
            line_numbers = []
            for i, line in enumerate(content.split("\n"), 1):
                if re.search(pattern_re, line):
                    line_numbers.append(i)

            findings.append({
                "pattern": description,
                "severity": severity,
                "occurrences": len(matches),
                "lines": line_numbers[:10],  # cap at 10
            })

    # Determine overall severity
    severities = [f["severity"] for f in findings]
    if "high" in severities:
        overall = "high"
    elif "medium" in severities:
        overall = "medium"
    elif "low" in severities:
        overall = "low"
    else:
        overall = "clean"

    return {
        "file": str(file_path),
        "findings": findings,
        "severity": overall,
        "finding_count": len(findings),
    }


# ---------------------------------------------------------------------------
# VirusTotal API (Layer 2 — hash lookup + optional upload)
# ---------------------------------------------------------------------------

def _vt_api_key() -> Optional[str]:
    """Get VirusTotal API key from environment."""
    return os.environ.get("VIRUSTOTAL_API_KEY")


def vt_hash_lookup(sha256: str, api_key: Optional[str] = None) -> Dict[str, Any]:
    """
    Look up a file hash on VirusTotal (no upload needed).

    Returns:
        dict with VT verdict or error
    """
    key = api_key or _vt_api_key()
    if not key:
        return {"success": False, "error": "VIRUSTOTAL_API_KEY not set"}

    url = f"{VT_API_BASE}/files/{sha256}"
    req = urllib.request.Request(
        url,
        headers={"x-apikey": key, "Accept": "application/json"},
        method="GET",
    )

    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))

        attrs = data.get("data", {}).get("attributes", {})
        stats = attrs.get("last_analysis_stats", {})
        malicious = stats.get("malicious", 0)
        suspicious = stats.get("suspicious", 0)
        undetected = stats.get("undetected", 0)
        total = sum(stats.values()) if stats else 0

        if malicious > 0:
            verdict = "malicious"
        elif suspicious > 0:
            verdict = "suspicious"
        else:
            verdict = "clean"

        return {
            "success": True,
            "verdict": verdict,
            "malicious": malicious,
            "suspicious": suspicious,
            "undetected": undetected,
            "total_engines": total,
            "sha256": sha256,
            "source": "virustotal_hash",
        }

    except urllib.error.HTTPError as e:
        if e.code == 404:
            return {
                "success": True,
                "verdict": "unknown",
                "message": "File not found in VirusTotal database",
                "sha256": sha256,
                "source": "virustotal_hash",
            }
        if e.code == 429:
            return {
                "success": False,
                "error": "VirusTotal rate limit exceeded (4 req/min on free tier)",
            }
        return {"success": False, "error": f"VT API error {e.code}: {e.reason}"}
    except Exception as e:
        return {"success": False, "error": f"VT request failed: {e}"}


def vt_upload_file(file_path: Path, api_key: Optional[str] = None) -> Dict[str, Any]:
    """
    Upload a file to VirusTotal for scanning.

    Returns:
        dict with upload result (analysis ID for polling)
    """
    key = api_key or _vt_api_key()
    if not key:
        return {"success": False, "error": "VIRUSTOTAL_API_KEY not set"}

    if file_path.stat().st_size > MAX_UPLOAD_BYTES:
        return {
            "success": False,
            "error": f"File too large ({file_path.stat().st_size} bytes, max {MAX_UPLOAD_BYTES})",
        }

    # Multipart form upload
    boundary = "----BrivenSkillScan"
    file_content = file_path.read_bytes()
    filename = file_path.name

    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'
        f"Content-Type: application/octet-stream\r\n\r\n"
    ).encode("utf-8") + file_content + f"\r\n--{boundary}--\r\n".encode("utf-8")

    url = f"{VT_API_BASE}/files"
    req = urllib.request.Request(
        url,
        data=body,
        headers={
            "x-apikey": key,
            "Content-Type": f"multipart/form-data; boundary={boundary}",
            "Accept": "application/json",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))

        analysis_id = data.get("data", {}).get("id", "")
        return {
            "success": True,
            "analysis_id": analysis_id,
            "message": f"File uploaded for scanning: {analysis_id}",
            "source": "virustotal_upload",
        }
    except urllib.error.HTTPError as e:
        if e.code == 429:
            return {
                "success": False,
                "error": "VirusTotal rate limit exceeded",
            }
        return {"success": False, "error": f"VT upload error {e.code}: {e.reason}"}
    except Exception as e:
        return {"success": False, "error": f"VT upload failed: {e}"}


# ---------------------------------------------------------------------------
# Combined scanning (both layers)
# ---------------------------------------------------------------------------

def scan_file(
    file_path: Path,
    use_vt: bool = True,
    upload: bool = False,
    api_key: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Scan a single file through both static analysis and VirusTotal.

    Args:
        file_path: Path to the file
        use_vt: Whether to check VirusTotal (requires API key)
        upload: Whether to upload unknown files to VT
        api_key: Optional VT API key override

    Returns:
        dict with combined verdict
    """
    if not file_path.exists():
        return {"success": False, "error": f"File not found: {file_path}"}

    file_hash = sha256_file(file_path)

    # Check cache first
    cache = _load_cache()
    cached = cache.get(file_hash)
    if cached and _is_cache_fresh(cached) and cached.get("file") == str(file_path):
        cached["from_cache"] = True
        return cached

    result: Dict[str, Any] = {
        "success": True,
        "file": str(file_path),
        "sha256": file_hash,
        "scanned_at": datetime.now(timezone.utc).isoformat(),
        "from_cache": False,
    }

    # Layer 1: Static analysis
    static = static_scan(file_path)
    result["static"] = static

    # Layer 2: VirusTotal (if enabled and key available)
    vt_result = None
    if use_vt and (_vt_api_key() or api_key):
        vt_result = vt_hash_lookup(file_hash, api_key)
        result["virustotal"] = vt_result

        # Upload if requested and file is unknown
        if (upload
                and vt_result.get("success")
                and vt_result.get("verdict") == "unknown"):
            upload_result = vt_upload_file(file_path, api_key)
            result["virustotal_upload"] = upload_result

    # Combined verdict
    static_severity = static.get("severity", "clean")
    vt_verdict = vt_result.get("verdict", "unknown") if vt_result else "skipped"

    if static_severity == "high" or vt_verdict == "malicious":
        result["verdict"] = "blocked"
        result["reason"] = _build_reason(static_severity, vt_verdict)
    elif static_severity == "medium" or vt_verdict == "suspicious":
        result["verdict"] = "warning"
        result["reason"] = _build_reason(static_severity, vt_verdict)
    elif static_severity == "low":
        result["verdict"] = "info"
        result["reason"] = _build_reason(static_severity, vt_verdict)
    else:
        result["verdict"] = "clean"

    # Update cache
    cache[file_hash] = result
    _save_cache(cache)

    return result


def _build_reason(static_severity: str, vt_verdict: str) -> str:
    """Build a human-readable reason string."""
    parts = []
    if static_severity != "clean":
        parts.append(f"static analysis: {static_severity}")
    if vt_verdict not in ("clean", "unknown", "skipped"):
        parts.append(f"VirusTotal: {vt_verdict}")
    return "; ".join(parts) if parts else "clean"


def scan_skill(
    skill_path: Path,
    use_vt: bool = True,
    upload: bool = False,
    api_key: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Scan all scannable files in a skill directory.

    Args:
        skill_path: Path to the skill directory (or a single file)
        use_vt: Whether to check VirusTotal
        upload: Whether to upload unknown files to VT
        api_key: Optional VT API key override

    Returns:
        dict with per-file results and overall verdict
    """
    if skill_path.is_file():
        file_result = scan_file(skill_path, use_vt, upload, api_key)
        return {
            "success": True,
            "skill_path": str(skill_path),
            "files_scanned": 1,
            "verdict": file_result.get("verdict", "unknown"),
            "results": [file_result],
        }

    if not skill_path.is_dir():
        return {"success": False, "error": f"Path not found: {skill_path}"}

    results = []
    blocked = False
    warnings = False
    vt_delay_needed = False

    for root, _dirs, files in os.walk(skill_path):
        for filename in sorted(files):
            fp = Path(root) / filename
            if fp.suffix.lower() not in SCANNABLE_EXTENSIONS:
                continue

            # Rate limit VT calls (free tier: 4/min)
            if use_vt and vt_delay_needed:
                time.sleep(16)  # ~4 requests per minute
            vt_delay_needed = use_vt and bool(_vt_api_key() or api_key)

            file_result = scan_file(fp, use_vt, upload, api_key)
            results.append(file_result)

            verdict = file_result.get("verdict", "unknown")
            if verdict == "blocked":
                blocked = True
            elif verdict == "warning":
                warnings = True

    if not results:
        return {
            "success": True,
            "skill_path": str(skill_path),
            "files_scanned": 0,
            "verdict": "clean",
            "message": "No scannable files found",
            "results": [],
        }

    if blocked:
        overall = "blocked"
    elif warnings:
        overall = "warning"
    else:
        overall = "clean"

    return {
        "success": True,
        "skill_path": str(skill_path),
        "files_scanned": len(results),
        "verdict": overall,
        "blocked_files": [r["file"] for r in results if r.get("verdict") == "blocked"],
        "warning_files": [r["file"] for r in results if r.get("verdict") == "warning"],
        "results": results,
    }


# ---------------------------------------------------------------------------
# Integration helper — called from the skill loading pipeline
# ---------------------------------------------------------------------------

def check_skill_safe(skill_path: Path, strict: bool = False) -> tuple[bool, str]:
    """
    Quick safety check for integration into the skill loading pipeline.

    Args:
        skill_path: Path to skill directory or file
        strict: If True, warnings also block loading

    Returns:
        (is_safe, reason) tuple
    """
    # Use VT only if key is available; don't block on missing key
    use_vt = bool(_vt_api_key())
    result = scan_skill(skill_path, use_vt=use_vt, upload=False)

    verdict = result.get("verdict", "unknown")

    if verdict == "blocked":
        blocked_files = result.get("blocked_files", [])
        return False, f"Blocked by security scan: {', '.join(blocked_files)}"

    if strict and verdict == "warning":
        warning_files = result.get("warning_files", [])
        return False, f"Security warnings: {', '.join(warning_files)}"

    return True, "clean"


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Briven Skill Scanner — malicious skill protection"
    )
    parser.add_argument(
        "--path", "-p",
        help="Path to skill directory or file to scan",
    )
    parser.add_argument(
        "--upload", action="store_true",
        help="Upload unknown files to VirusTotal (slower, more thorough)",
    )
    parser.add_argument(
        "--no-vt", action="store_true",
        help="Skip VirusTotal (static analysis only)",
    )
    parser.add_argument(
        "--strict", action="store_true",
        help="Treat warnings as failures",
    )
    parser.add_argument(
        "--cache-stats", action="store_true",
        help="Show scan cache statistics",
    )
    parser.add_argument(
        "--clear-cache", action="store_true",
        help="Clear the scan cache",
    )

    args = parser.parse_args()

    if args.cache_stats:
        print(json.dumps(cache_stats(), indent=2))
        return

    if args.clear_cache:
        print(json.dumps(clear_cache(), indent=2))
        return

    if not args.path:
        parser.print_help()
        sys.exit(0)

    skill_path = Path(args.path)
    result = scan_skill(
        skill_path,
        use_vt=not args.no_vt,
        upload=args.upload,
    )

    verdict = result.get("verdict", "unknown")
    files_scanned = result.get("files_scanned", 0)
    blocked = result.get("blocked_files", [])
    warnings_list = result.get("warning_files", [])

    if verdict == "blocked":
        print(f"BLOCKED  {files_scanned} files scanned — {len(blocked)} blocked")
        for f in blocked:
            print(f"  !! {f}")
    elif verdict == "warning":
        print(f"WARNING  {files_scanned} files scanned — {len(warnings_list)} warnings")
        for f in warnings_list:
            print(f"  ?  {f}")
    else:
        print(f"OK  {files_scanned} files scanned — all clean")

    print(json.dumps(result, indent=2, default=str))

    if verdict == "blocked" or (args.strict and verdict == "warning"):
        sys.exit(1)


if __name__ == "__main__":
    main()
