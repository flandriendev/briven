import asyncio
from datetime import datetime
import time
from python.helpers.task_scheduler import TaskScheduler
from python.helpers.print_style import PrintStyle
from python.helpers import errors
from python.helpers import runtime


SLEEP_TIME_DEFAULT = 60

keep_running = True
pause_time = 0


def _get_tick_interval() -> int:
    """Get configurable tick interval from settings, with a safe minimum of 30s."""
    try:
        from python.helpers import settings
        s = settings.get_settings()
        interval = s.get("scheduler_tick_interval", SLEEP_TIME_DEFAULT)
        # Enforce minimum of 30s to prevent runaway loops
        return max(30, interval)
    except Exception:
        return SLEEP_TIME_DEFAULT


async def run_loop():
    global pause_time, keep_running

    while True:
        sleep_time = _get_tick_interval()

        if runtime.is_development():
            # Signal to container that the job loop should be paused
            # if we are runing a development instance to avoid duble-running the jobs
            try:
                await runtime.call_development_function(pause_loop)
            except Exception as e:
                PrintStyle().error("Failed to pause job loop by development instance: " + errors.error_text(e))
        if not keep_running and (time.time() - pause_time) > (sleep_time * 2):
            resume_loop()
        if keep_running:
            try:
                await scheduler_tick()
            except Exception as e:
                PrintStyle().error(errors.format_error(e))
        await asyncio.sleep(sleep_time)


async def scheduler_tick():
    # Get the task scheduler instance and print detailed debug info
    scheduler = TaskScheduler.get()
    # Run the scheduler tick
    await scheduler.tick()


def pause_loop():
    global keep_running, pause_time
    keep_running = False
    pause_time = time.time()


def resume_loop():
    global keep_running, pause_time
    keep_running = True
    pause_time = 0
