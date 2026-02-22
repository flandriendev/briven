"""
python/helpers/skills_registry.py

Local registry of installed skills with metadata, status, and usage tracking.

The registry lives at usr/skills/registry.json and provides:
  - Inventory of all discovered skills and their metadata
  - Enable/disable status per skill (without deleting files)
  - Last-used timestamps for usage analytics
  - A single source of truth for the skills ecosystem

The registry is rebuilt on demand by scanning all skill roots
and merging with any existing registry data (preserving user overrides
like enabled/disabled status).
"""

import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from python.helpers.files import get_abs_path, make_dirs, read_file, write_file
from python.helpers.print_style import PrintStyle

REGISTRY_FILE = "usr/skills/registry.json"
_lock = threading.RLock()


def _load_registry() -> Dict[str, Any]:
    """Load the registry from disk."""
    try:
        path = get_abs_path(REGISTRY_FILE)
        content = read_file(path)
        if content:
            data = json.loads(content)
            if isinstance(data, dict):
                return data
    except Exception:
        pass
    return {"skills": {}, "updated_at": None}


def _save_registry(registry: Dict[str, Any]) -> None:
    """Persist the registry to disk."""
    registry["updated_at"] = datetime.now(timezone.utc).isoformat()
    path = get_abs_path(REGISTRY_FILE)
    make_dirs(path)
    write_file(path, json.dumps(registry, indent=2, default=str))


def rebuild_registry(agent=None) -> Dict[str, Any]:
    """
    Scan all skill roots, discover skills, and merge into the registry.
    Preserves user overrides (enabled/disabled) from the existing registry.
    """
    from python.helpers.skills import get_skill_roots, discover_skill_md_files, skill_from_markdown

    with _lock:
        existing = _load_registry()
        existing_skills = existing.get("skills", {})

        new_skills: Dict[str, Any] = {}
        roots = get_skill_roots(agent)

        for root_str in roots:
            root = Path(root_str)
            for skill_md in discover_skill_md_files(root):
                try:
                    skill = skill_from_markdown(skill_md)
                    if not skill:
                        continue

                    key = skill.name
                    # Preserve user overrides from existing registry
                    prev = existing_skills.get(key, {})

                    new_skills[key] = {
                        "name": skill.name,
                        "description": skill.description,
                        "version": skill.version,
                        "author": skill.author,
                        "tags": skill.tags,
                        "license": skill.license,
                        "path": str(skill.skill_md_path),
                        "enabled": prev.get("enabled", True),
                        "last_used": prev.get("last_used"),
                        "use_count": prev.get("use_count", 0),
                        "discovered_at": prev.get("discovered_at",
                                                   datetime.now(timezone.utc).isoformat()),
                    }
                except Exception as e:
                    PrintStyle.warning(f"Skills registry: failed to parse {skill_md}: {e}")

        registry = {
            "skills": new_skills,
            "total": len(new_skills),
            "enabled": sum(1 for s in new_skills.values() if s.get("enabled", True)),
            "updated_at": None,
        }
        _save_registry(registry)
        return registry


def get_registry() -> Dict[str, Any]:
    """Get the current registry, rebuilding if it doesn't exist."""
    with _lock:
        reg = _load_registry()
        if not reg.get("skills"):
            return rebuild_registry()
        return reg


def set_skill_enabled(skill_name: str, enabled: bool) -> bool:
    """Enable or disable a skill by name. Returns True if found."""
    with _lock:
        registry = _load_registry()
        skills = registry.get("skills", {})
        if skill_name not in skills:
            return False
        skills[skill_name]["enabled"] = enabled
        registry["enabled"] = sum(1 for s in skills.values() if s.get("enabled", True))
        _save_registry(registry)
        return True


def record_skill_use(skill_name: str) -> None:
    """Record that a skill was used (updates last_used and use_count)."""
    with _lock:
        registry = _load_registry()
        skills = registry.get("skills", {})
        if skill_name in skills:
            skills[skill_name]["last_used"] = datetime.now(timezone.utc).isoformat()
            skills[skill_name]["use_count"] = skills[skill_name].get("use_count", 0) + 1
            _save_registry(registry)


def get_enabled_skills() -> List[str]:
    """Return list of enabled skill names."""
    with _lock:
        registry = _load_registry()
        return [
            name for name, data in registry.get("skills", {}).items()
            if data.get("enabled", True)
        ]


def get_disabled_skills() -> List[str]:
    """Return list of disabled skill names."""
    with _lock:
        registry = _load_registry()
        return [
            name for name, data in registry.get("skills", {}).items()
            if not data.get("enabled", True)
        ]
