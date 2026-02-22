"""
python/extensions/message_loop_prompts_after/_45_atlas_context.py

Injects the persistent memory context (loaded by _05_atlas_memory_load.py)
into each message loop as a prompt extra — so every LLM call has access to
the agent's cross-session memory: preferences, key facts, and recent events.

Runs after memory recall (_50_recall_memories.py indexes at 50) but still
within the message_loop_prompts_after phase, giving the LLM both the
framework-level MEMORY.md context and the semantic memory recall results.

Ordering: _45_ → runs before _50_ (recall_memories) intentionally.
Memory recall adds dynamic searched content; this adds static curated content.
"""

from typing import Any
from python.helpers.extension import Extension
from agent import LoopData
from python.extensions.agent_init._05_atlas_memory_load import ATLAS_MEMORY_KEY

# Maximum chars to inject per loop to avoid ballooning the context
MAX_MEMORY_CHARS = 4000


class AtlasContext(Extension):
    """
    Injects /atlas persistent memory (MEMORY.md + daily logs) into each
    message loop prompt, so the agent remembers across sessions.
    """

    async def execute(
        self,
        loop_data: LoopData = LoopData(),
        **kwargs: Any,
    ):
        # Only inject for the root agent
        if self.agent.number != 0:
            return

        memory_content = self.agent.get_data(ATLAS_MEMORY_KEY)
        if not memory_content:
            return

        # Trim if too large
        trimmed = memory_content[:MAX_MEMORY_CHARS]
        if len(memory_content) > MAX_MEMORY_CHARS:
            trimmed += "\n\n[memory content trimmed — use atlas/memory/hybrid_search.py for full recall]"

        atlas_memory_prompt = f"""
## Cross-Session Memory (/atlas Memory Protocol)

The following is your persistent memory loaded from memory/MEMORY.md and today's session log.
Use this to maintain continuity across sessions and apply known preferences immediately.

{trimmed}
""".strip()

        # Inject into extras_persistent so it appears in every iteration
        loop_data.extras_persistent["atlas_memory"] = atlas_memory_prompt
