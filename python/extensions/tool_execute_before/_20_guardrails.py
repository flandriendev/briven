import re
from typing import Any
from python.helpers.extension import Extension
from python.helpers.print_style import PrintStyle


# Patterns that should be blocked before tool execution.
# Each entry is (compiled_regex, human_readable_description).
_DANGEROUS_PATTERNS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"\brm\s+(-[a-zA-Z]*f[a-zA-Z]*\s+)?/\b"), "recursive delete from root (rm -rf /)"),
    (re.compile(r"\bgit\s+push\s+--force\b"), "force push (git push --force)"),
    (re.compile(r"\bgit\s+reset\s+--hard\b"), "hard reset (git reset --hard)"),
    (re.compile(r"\bDROP\s+(TABLE|DATABASE)\b", re.IGNORECASE), "SQL DROP statement"),
    (re.compile(r"\bTRUNCATE\s+TABLE\b", re.IGNORECASE), "SQL TRUNCATE statement"),
    (re.compile(r"\bmkfs\b"), "filesystem format (mkfs)"),
    (re.compile(r"\bdd\s+.*of=/dev/"), "raw disk write (dd of=/dev/)"),
    (re.compile(r">\s*/dev/sd[a-z]"), "redirect to block device"),
    (re.compile(r"\bchmod\s+(-[a-zA-Z]*\s+)?777\s+/\b"), "chmod 777 on root"),
    (re.compile(r"\b:()\{.*\|.*&.*\};:"), "fork bomb"),
]


class Guardrails(Extension):
    """
    Pre-tool-execution guardrail that inspects tool arguments for dangerous
    patterns and blocks execution when a match is found.

    The agent is informed of the block so it can warn the user or ask for
    confirmation before retrying.
    """

    async def execute(
        self,
        tool_name: str = "",
        tool_args: dict[str, Any] | None = None,
        **kwargs,
    ):
        if not tool_args:
            return

        # Only inspect tools that run arbitrary commands
        inspectable_tools = {
            "code_execution_tool",
            "call_subordinate",
            "knowledge_tool",
        }

        # For non-command tools we have nothing to check
        if tool_name and tool_name not in inspectable_tools:
            return

        # Scan all string values in tool_args
        for key, value in tool_args.items():
            if not isinstance(value, str):
                continue
            for pattern, description in _DANGEROUS_PATTERNS:
                if pattern.search(value):
                    warning = (
                        f"Guardrail blocked: detected '{description}' "
                        f"in tool '{tool_name}' argument '{key}'. "
                        f"The command was not executed. "
                        f"Ask the user for explicit confirmation before retrying."
                    )
                    PrintStyle(
                        font_color="red", bold=True, padding=True
                    ).print(f"⚠ GUARDRAIL: {warning}")

                    # Replace the dangerous argument with a warning message
                    # so the agent sees the block in the tool result
                    tool_args[key] = (
                        f"[BLOCKED BY GUARDRAIL] {description} — "
                        f"This command was blocked for safety. "
                        f"Ask the user to confirm before retrying."
                    )
                    return  # one block per execution is enough
