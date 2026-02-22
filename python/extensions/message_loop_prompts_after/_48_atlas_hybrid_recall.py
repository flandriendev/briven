"""
python/extensions/message_loop_prompts_after/_48_atlas_hybrid_recall.py

Bridges the atlas/memory hybrid search (BM25 + vector) into the agent's
recall pipeline. Runs between _45_atlas_context.py (static MEMORY.md) and
_50_recall_memories.py (FAISS-only recall), giving the agent combined
keyword + semantic results from the SQLite-backed atlas memory database.

This extension adds value because:
- FAISS recall (_50) only uses vector similarity → misses exact keyword matches
- BM25 in atlas/memory/hybrid_search.py catches those keyword hits
- Combined scoring (configurable weights) gives the best of both worlds

Configurable via settings:
  - atlas_hybrid_recall_enabled (default: True)
  - atlas_hybrid_recall_bm25_weight (default: 0.7)
  - atlas_hybrid_recall_semantic_weight (default: 0.3)
  - atlas_hybrid_recall_limit (default: 5)
  - atlas_hybrid_recall_min_score (default: 0.1)
"""

import sys
from pathlib import Path
from typing import Any

from python.helpers.extension import Extension
from python.helpers import settings
from python.helpers.print_style import PrintStyle
from agent import LoopData

# Add atlas/memory to import path so we can use hybrid_search
ATLAS_MEMORY_DIR = str(Path(__file__).parent.parent.parent.parent / "atlas" / "memory")

# Maximum chars to inject to avoid ballooning context
MAX_RECALL_CHARS = 3000


class AtlasHybridRecall(Extension):
    """
    Queries the atlas/memory SQLite database using hybrid BM25 + vector search
    and injects relevant results into the agent's prompt context.
    """

    async def execute(
        self,
        loop_data: LoopData = LoopData(),
        **kwargs: Any,
    ):
        # Only for root agent
        if self.agent.number != 0:
            return

        s = settings.get_settings()

        if not s.get("atlas_hybrid_recall_enabled", True):
            return

        # Only search on the same interval as FAISS recall to avoid double cost
        recall_interval = s.get("memory_recall_interval", 3)
        if loop_data.iteration % recall_interval != 0:
            return

        # Extract user message text for search query
        user_msg = ""
        if loop_data.user_message:
            user_msg = loop_data.user_message.output_text()
        if not user_msg or len(user_msg.strip()) < 3:
            return

        try:
            # Import hybrid_search from atlas/memory
            if ATLAS_MEMORY_DIR not in sys.path:
                sys.path.insert(0, ATLAS_MEMORY_DIR)

            from hybrid_search import hybrid_search

            result = hybrid_search(
                query=user_msg[:500],  # cap query length
                limit=s.get("atlas_hybrid_recall_limit", 5),
                bm25_weight=s.get("atlas_hybrid_recall_bm25_weight", 0.7),
                semantic_weight=s.get("atlas_hybrid_recall_semantic_weight", 0.3),
                min_score=s.get("atlas_hybrid_recall_min_score", 0.1),
            )

            if not result.get("success") or not result.get("results"):
                return

            # Format results for prompt injection
            entries = result["results"]
            lines = []
            for entry in entries:
                score = entry.get("score", 0)
                content = entry.get("content", "")
                entry_type = entry.get("type", "unknown")
                lines.append(f"- [{entry_type}] (score: {score:.2f}) {content}")

            if not lines:
                return

            recall_text = "\n".join(lines)

            # Trim if too large
            if len(recall_text) > MAX_RECALL_CHARS:
                recall_text = recall_text[:MAX_RECALL_CHARS] + "\n[...truncated]"

            prompt_block = f"""
## Atlas Hybrid Memory Recall (BM25 + Semantic)

The following structured memories were found via keyword + semantic search
in the atlas memory database. Use these alongside FAISS recall results.

{recall_text}
""".strip()

            loop_data.extras_persistent["atlas_hybrid_recall"] = prompt_block

        except ImportError:
            # atlas/memory modules not available — skip silently
            pass
        except Exception as e:
            PrintStyle.warning(f"Atlas hybrid recall error: {e}")
