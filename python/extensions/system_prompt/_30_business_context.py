from typing import Any
from python.helpers.extension import Extension
from python.helpers import files
from agent import LoopData


_PLACEHOLDER_MARKER = "<!-- PLACEHOLDER"


class BusinessContext(Extension):
    """
    Injects the user's business identity and communication style into the
    system prompt when the context files have been configured.

    Reads:
      - usr/context/my-business.md
      - usr/context/my-voice.md

    Files that are missing or still contain the placeholder marker are
    silently skipped.
    """

    async def execute(
        self,
        system_prompt: list[str] = [],
        loop_data: LoopData = LoopData(),
        **kwargs: Any,
    ):
        sections: list[str] = []

        for filename, heading in [
            ("usr/context/my-business.md", "Business Context"),
            ("usr/context/my-voice.md", "Communication Style"),
        ]:
            path = files.get_abs_path(filename)
            if not files.exists(path):
                continue
            content = files.read_file(path)
            if not content or _PLACEHOLDER_MARKER in content:
                continue
            sections.append(f"## {heading}\n{content}")

        if sections:
            system_prompt.append(
                "# User Business Profile\n\n" + "\n\n".join(sections)
            )
