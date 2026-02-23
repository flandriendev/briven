from __future__ import annotations

from pathlib import Path
from typing import List

from python.helpers.tool import Tool, Response
from python.helpers import projects, files, file_tree
from python.helpers import skills as skills_helper, runtime


DATA_NAME_LOADED_SKILLS = "loaded_skills"


class SkillsTool(Tool):
    """
    Manage and use SKILL.md-based Skills (Anthropic open standard).

    Methods (tool_args.method):
      - list
      - search (query)
      - load (skill_name)
      - read_file (skill_name, file_path)

    Script execution is handled by code_execution_tool directly.
    """

    async def execute(self, **kwargs) -> Response:
        method = (
            (kwargs.get("method") or self.args.get("method") or self.method or "")
            .strip()
            .lower()
        )

        try:
            if method == "list":
                return Response(message=self._list(), break_loop=False)
            # if method == "search":
            #     query = str(kwargs.get("query") or "").strip()
            #     return Response(message=self._search(query), break_loop=False)
            if method == "load":
                skill_name = str(kwargs.get("skill_name") or "").strip()
                return Response(message=self._load(skill_name), break_loop=False)
            # if method == "read_file":
            #     skill_name = str(kwargs.get("skill_name") or "").strip()
            #     file_path = str(kwargs.get("file_path") or "").strip()
            #     return Response(
            #         message=self._read_file(skill_name, file_path), break_loop=False
            #     )

            return Response(
                message="Error: missing/invalid 'method'. Supported: list, load.",
                break_loop=False,
            )
        except (
            Exception
        ) as e:  # keep tool robust; return error instead of crashing loop
            return Response(message=f"Error in skills_tool: {e}", break_loop=False)

    def _list(self) -> str:
        skills = skills_helper.list_skills(
            agent=self.agent,
            include_content=False,
        )
        if not skills:
            return "No skills found."

        # Get disabled skills from registry
        disabled_names: set[str] = set()
        try:
            from python.helpers.skills_registry import get_disabled_skills
            disabled_names = set(get_disabled_skills())
        except Exception:
            pass

        # Stable output: sort by name
        skills_sorted = sorted(skills, key=lambda s: s.name.lower())

        lines: List[str] = []
        enabled_count = sum(1 for s in skills_sorted if s.name not in disabled_names)
        lines.append(f"Available skills ({enabled_count} enabled, {len(skills_sorted)} total):")
        for s in skills_sorted:
            tags = f" tags={','.join(s.tags)}" if s.tags else ""
            ver = f" v{s.version}" if s.version else ""
            desc = (s.description or "").strip()
            if len(desc) > 200:
                desc = desc[:200].rstrip() + "…"
            status = " [DISABLED]" if s.name in disabled_names else ""
            lines.append(f"- {s.name}{ver}{tags}{status}: {desc}")
        lines.append("")
        lines.append("Tip: use skills_tool method=search or method=load for details.")
        return "\n".join(lines)

    # def _search(self, query: str) -> str:
    #     if not query:
    #         return "Error: 'query' is required for method=search."

    #     results = skills_helper.search_skills(
    #         query,
    #         limit=25,
    #         agent=self.agent,
    #     )
    #     if not results:
    #         return f"No skills matched query: {query!r}"

    #     lines: List[str] = []
    #     lines.append(f"Skills matching {query!r} ({len(results)}):")
    #     for s in results:
    #         desc = (s.description or "").strip()
    #         if len(desc) > 200:
    #             desc = desc[:200].rstrip() + "…"
    #         lines.append(f"- {s.name}: {desc}")
    #     lines.append("")
    #     lines.append(
    #         "Tip: use skills_tool method=load skill_name=<name> to load full instructions."
    #     )
    #     return "\n".join(lines)

    def _load(self, skill_name: str) -> str:
        skill_name = skill_name.strip()
        if skill_name.startswith("**") and skill_name.endswith("**"):
            skill_name = skill_name[2:-2]

        if not skill_name:
            return "Error: 'skill_name' is required for method=load."

        # Check if skill is disabled in registry
        try:
            from python.helpers.skills_registry import get_disabled_skills, record_skill_use
            if skill_name in get_disabled_skills():
                return f"Error: skill '{skill_name}' is disabled. Enable it in the skills registry first."
        except Exception:
            pass

        # Verify skill exists
        skill = skills_helper.find_skill(
            skill_name,
            include_content=False,
            agent=self.agent,
        )
        if not skill:
            return f"Error: skill not found: {skill_name!r}. Try skills_tool method=list or method=search."

        # Security scan for user-supplied skills (from usr/ paths)
        try:
            if "/usr/" in str(skill.path):
                from tools.skill_scanner import check_skill_safe
                is_safe, reason = check_skill_safe(skill.path)
                if not is_safe:
                    return f"Error: skill '{skill_name}' blocked by security scan: {reason}"
        except ImportError:
            pass  # scanner not available — allow loading

        # Record usage in registry
        try:
            record_skill_use(skill.name)
        except Exception:
            pass

        # Store skill name for fresh loading each turn
        if not self.agent.data[DATA_NAME_LOADED_SKILLS]:
            self.agent.data[DATA_NAME_LOADED_SKILLS] = []
        loaded = self.agent.data[DATA_NAME_LOADED_SKILLS]
        if skill.name in loaded:
            loaded.remove(skill.name)
        loaded.append(skill.name)
        self.agent.data[DATA_NAME_LOADED_SKILLS] = loaded[-max_loaded_skills():]

        return f"Loaded skill '{skill.name}' into EXTRAS."


def max_loaded_skills() -> int:
    return 5 # TODO move to settings
