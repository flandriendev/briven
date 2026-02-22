"""
python/extensions/monologue_end/_49_embed_new_entries.py

After the daily log sync (_48), embeds any new SQLite memory entries that
don't have vector embeddings yet. This ensures that the atlas/memory
semantic search component of hybrid search stays current.

Uses the agent's configured embedding model rather than hardcoded OpenAI,
so it works with HuggingFace, Ollama, or any other provider the user has set.

Runs after _48_sync_daily_log.py (which creates new entries) and before
_50_memorize_fragments.py.

Configurable via settings:
  - atlas_auto_embed_enabled (default: True)
"""

import sys
from pathlib import Path

from python.helpers.extension import Extension
from python.helpers import settings, errors
from python.helpers.print_style import PrintStyle
from python.helpers.defer import DeferredTask, THREAD_BACKGROUND
from python.helpers.log import LogItem
from agent import LoopData

# Path to atlas/memory modules
ATLAS_MEMORY_DIR = str(Path(__file__).parent.parent.parent.parent / "atlas" / "memory")

# Max entries to embed per monologue end (avoid long-running operations)
MAX_BATCH_SIZE = 20


class AutoEmbedEntries(Extension):
    """
    Embeds new atlas/memory SQLite entries that lack vector embeddings,
    keeping the semantic search index fresh.
    """

    async def execute(self, loop_data: LoopData = LoopData(), **kwargs):
        # Only for root agent
        if self.agent.number != 0:
            return

        s = settings.get_settings()
        if not s.get("atlas_auto_embed_enabled", True):
            return

        log_item = self.agent.context.log.log(
            type="util",
            heading="Embedding new atlas memory entries...",
        )

        # Run in background
        task = DeferredTask(thread_name=THREAD_BACKGROUND)
        task.start_task(self._embed, loop_item=log_item)
        return task

    async def _embed(self, log_item: LogItem, **kwargs):
        try:
            if ATLAS_MEMORY_DIR not in sys.path:
                sys.path.insert(0, ATLAS_MEMORY_DIR)

            from memory_db import get_entries_without_embeddings, store_embedding
            from embed_memory import embedding_to_bytes, EMBEDDING_MODEL

            # Check if there are entries needing embeddings
            pending = get_entries_without_embeddings(limit=MAX_BATCH_SIZE)
            if not pending.get("success"):
                log_item.update(heading="No pending entries to embed")
                return

            entries = pending.get("entries", [])
            if not entries:
                log_item.update(heading="All atlas memory entries already embedded")
                return

            # Use the agent's embedding model
            embedding_model = self.agent.get_embedding_model()

            processed = 0
            failed = 0

            for entry in entries:
                try:
                    content = entry.get("content", "")
                    if not content:
                        continue

                    # Generate embedding using the agent's model
                    embedding_vector = embedding_model.embed_query(content)

                    # Convert to bytes for SQLite storage
                    import struct
                    embedding_bytes = struct.pack(
                        f"{len(embedding_vector)}f", *embedding_vector
                    )

                    # Store in SQLite
                    model_name = getattr(
                        embedding_model, "model_name",
                        getattr(embedding_model, "model", "agent-configured")
                    )
                    store_embedding(entry["id"], embedding_bytes, str(model_name))
                    processed += 1

                except Exception as e:
                    failed += 1
                    PrintStyle.warning(
                        f"Failed to embed entry {entry.get('id')}: {e}"
                    )

            heading = f"Embedded {processed}/{len(entries)} atlas memory entries"
            if failed:
                heading += f" ({failed} failed)"
            log_item.update(heading=heading)

        except ImportError:
            log_item.update(heading="Auto-embed skipped (atlas/memory not available)")
        except Exception as e:
            err = errors.format_error(e)
            PrintStyle.warning(f"Auto-embed error: {err}")
            log_item.update(heading=f"Auto-embed error: {str(e)[:100]}")
