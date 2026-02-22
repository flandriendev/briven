"""
python/extensions/system_prompt/_05_atlas_prompt.py

Injects the /atlas GOTCHA framework handbook into the system prompt.
Runs BEFORE _10_system_prompt.py so /atlas rules appear at the top of every
LLM context — guaranteeing the agent reads them before its main instructions.

The /atlas folder is the operational layer that governs Briven's behavior:
  - atlas/CLAUDE.md  → the full GOTCHA framework system handbook
  - goals/manifest.md → available workflows
  - tools/manifest.md → available tools
"""

from typing import Any
from pathlib import Path
from python.helpers.extension import Extension
from python.helpers import settings
from agent import LoopData
from python.helpers import files


# By default, only inject for the root agent (number == 0) to avoid bloating
# subordinate agent contexts. When atlas_subordinate_injection is enabled in
# settings, subordinates also receive a condensed /atlas summary for direct
# governance of parallel agents that have no superior orchestrating them.
ROOT_AGENT_ONLY_DEFAULT = True

# Maximum characters of atlas content to include (trim if file is very large)
MAX_ATLAS_CHARS = 8000


def _read_atlas_file(relative_path: str) -> str:
    """Read a file relative to the Briven project root. Returns '' on error."""
    try:
        abs_path = files.get_abs_path(relative_path)
        p = Path(abs_path)
        if p.exists() and p.is_file():
            return p.read_text(encoding="utf-8").strip()
    except Exception:
        pass
    return ""


def _read_manifest(manifest_path: str) -> str:
    """Read a manifest file, returning a trimmed summary."""
    content = _read_atlas_file(manifest_path)
    if not content:
        return f"(no {manifest_path} found — create it)"
    # Trim to first 2000 chars for context efficiency
    return content[:2000] + ("..." if len(content) > 2000 else "")


class AtlasPrompt(Extension):
    """
    Prepends /atlas guidelines to every system prompt.

    This extension ensures the agent is governed by the GOTCHA framework
    before reading its main role, tools, and behavior instructions.
    """

    async def execute(
        self,
        system_prompt: list[str] = [],
        loop_data: LoopData = LoopData(),
        **kwargs: Any,
    ):
        s = settings.get_settings()
        subordinate_injection = s.get("atlas_subordinate_injection", False)

        # Skip non-root agents unless subordinate injection is enabled
        if self.agent.number != 0 and not subordinate_injection:
            return

        is_subordinate = self.agent.number != 0

        # Read atlas/CLAUDE.md (the GOTCHA handbook)
        atlas_content = _read_atlas_file("atlas/CLAUDE.md")
        if not atlas_content:
            # Fall back to a minimal reminder if the file isn't found
            atlas_content = (
                "GOTCHA Framework: check goals/manifest.md and tools/manifest.md "
                "before acting. Prefer Tailscale for networking."
            )
        else:
            # Subordinates get a shorter version to save context space
            max_chars = MAX_ATLAS_CHARS // 2 if is_subordinate else MAX_ATLAS_CHARS
            atlas_content = atlas_content[:max_chars]
            if len(atlas_content) == max_chars:
                atlas_content += "\n\n[/atlas content trimmed for context efficiency]"

        # Read available goals and tools manifests (brief summaries)
        goals_manifest = _read_manifest("goals/manifest.md")
        tools_manifest = _read_manifest("tools/manifest.md")

        if is_subordinate:
            # Condensed block for subordinate agents
            atlas_block = f"""
## /atlas — GOTCHA Framework (Subordinate Summary)

You are a subordinate agent. Follow these operational guidelines:

{atlas_content}

### Available Tools (tools/manifest.md)
{tools_manifest}

**/atlas check complete. Execute your assigned task below.**
""".strip()
        else:
            atlas_block = f"""
## /atlas — GOTCHA Framework (Read This First)

The following is your operational handbook. You MUST consult this before every action.

{atlas_content}

---

### Available Goals (goals/manifest.md)
{goals_manifest}

---

### Available Tools (tools/manifest.md)
{tools_manifest}

---

**/atlas check complete. Proceed with your main instructions below.**
""".strip()

        # Insert at position 0 so /atlas is the very first thing the LLM sees
        system_prompt.insert(0, atlas_block)
