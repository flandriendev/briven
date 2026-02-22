"""
python/extensions/monologue_end/_48_sync_daily_log.py

Syncs the current day's markdown log (memory/logs/YYYY-MM-DD.md) into the
atlas/memory SQLite database after each monologue ends.

This bridges the file-based daily logs (used by _05_atlas_memory_load.py)
with the structured SQLite database (used by hybrid_search.py), ensuring
that BM25 keyword search can find content from today's session.

Also extracts key conversation facts from the just-completed monologue
and writes them to the memory_entries table as structured memories.

Configurable via settings:
  - atlas_daily_log_sync_enabled (default: True)
"""

import sys
from datetime import datetime
from pathlib import Path

from python.helpers.extension import Extension
from python.helpers import settings, errors
from python.helpers.print_style import PrintStyle
from python.helpers.defer import DeferredTask, THREAD_BACKGROUND
from python.helpers.log import LogItem
from agent import LoopData

# Path to atlas/memory modules
ATLAS_MEMORY_DIR = str(Path(__file__).parent.parent.parent.parent / "atlas" / "memory")


class SyncDailyLog(Extension):
    """
    After each monologue, sync today's daily log file to the SQLite database
    so hybrid search can index the content.
    """

    async def execute(self, loop_data: LoopData = LoopData(), **kwargs):
        # Only for root agent
        if self.agent.number != 0:
            return

        s = settings.get_settings()
        if not s.get("atlas_daily_log_sync_enabled", True):
            return

        log_item = self.agent.context.log.log(
            type="util",
            heading="Syncing daily log to atlas memory...",
        )

        # Run sync in background to not block
        task = DeferredTask(thread_name=THREAD_BACKGROUND)
        task.start_task(self._sync, loop_data, log_item)
        return task

    async def _sync(self, loop_data: LoopData, log_item: LogItem, **kwargs):
        try:
            if ATLAS_MEMORY_DIR not in sys.path:
                sys.path.insert(0, ATLAS_MEMORY_DIR)

            from memory_write import sync_log_to_db, write_to_memory

            today = datetime.now().strftime("%Y-%m-%d")

            # Step 1: Sync the daily log file to SQLite daily_logs table
            sync_result = sync_log_to_db(today)

            events_count = 0
            if sync_result.get("success"):
                events_count = sync_result.get("events_found", 0)

            # Step 2: Extract a brief summary of this conversation and store
            # as a structured memory entry (so hybrid search finds it)
            history_text = self.agent.history.output_text()
            if history_text and len(history_text.strip()) > 20:
                # Take last portion of conversation as summary
                summary = history_text[-500:].strip()
                if len(history_text) > 500:
                    summary = "..." + summary

                write_to_memory(
                    content=f"Session {today}: {summary}",
                    entry_type="event",
                    source="session",
                    importance=4,
                    tags=["session", today],
                    context=f"Auto-synced from conversation on {today}",
                    log_to_file=False,  # already in daily log
                    add_to_db=True,
                )

            log_item.update(
                heading=f"Daily log synced ({events_count} events indexed)",
            )

        except ImportError:
            log_item.update(heading="Daily log sync skipped (atlas/memory not available)")
        except Exception as e:
            err = errors.format_error(e)
            PrintStyle.warning(f"Daily log sync error: {err}")
            log_item.update(heading=f"Daily log sync error: {str(e)[:100]}")
