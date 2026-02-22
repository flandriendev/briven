"""
python/extensions/agent_init/_05_atlas_memory_load.py

Loads the persistent memory state at agent initialization:
  - memory/MEMORY.md  → curated long-term facts, preferences, context
  - memory/logs/YYYY-MM-DD.md  → today's session log
  - memory/logs/YYYY-MM-DD.md  → yesterday's log (for continuity)

Stores the content in agent data under ATLAS_MEMORY_KEY so other
extensions (e.g., _45_atlas_context.py) can inject it into the system prompt.

Per the /atlas Memory Protocol (atlas/CLAUDE.md §8):
  "At session start, read memory/MEMORY.md and today's log."
"""

from datetime import datetime, timedelta
from pathlib import Path
from python.helpers.extension import Extension
from python.helpers import files


# Key used to store atlas memory in agent.data
ATLAS_MEMORY_KEY = "_atlas_memory"
ATLAS_LOADED_KEY = "_atlas_memory_loaded"


def _read_file(relative_path: str) -> str:
    """Read a file relative to project root. Returns '' on error."""
    try:
        abs_path = files.get_abs_path(relative_path)
        p = Path(abs_path)
        if p.exists() and p.is_file():
            return p.read_text(encoding="utf-8").strip()
    except Exception:
        pass
    return ""


class AtlasMemoryLoad(Extension):
    """
    Loads MEMORY.md and daily session logs into agent data on init.
    Runs once per agent lifecycle (root agent only).
    """

    async def execute(self, **kwargs):
        # Only for the root agent (number == 0); subordinates don't need this
        if self.agent.number != 0:
            return

        # Avoid double-loading if already initialized
        if self.agent.get_data(ATLAS_LOADED_KEY):
            return

        today = datetime.now()
        yesterday = today - timedelta(days=1)

        memory_md = _read_file("memory/MEMORY.md")
        today_log = _read_file(f"memory/logs/{today.strftime('%Y-%m-%d')}.md")
        yesterday_log = _read_file(f"memory/logs/{yesterday.strftime('%Y-%m-%d')}.md")

        parts = []
        if memory_md:
            parts.append(f"### Persistent Memory (memory/MEMORY.md)\n{memory_md}")
        if today_log:
            parts.append(f"### Today's Session Log ({today.strftime('%Y-%m-%d')})\n{today_log}")
        if yesterday_log:
            parts.append(f"### Yesterday's Log ({yesterday.strftime('%Y-%m-%d')})\n{yesterday_log}")

        combined = "\n\n---\n\n".join(parts) if parts else ""

        self.agent.set_data(ATLAS_MEMORY_KEY, combined)
        self.agent.set_data(ATLAS_LOADED_KEY, True)
