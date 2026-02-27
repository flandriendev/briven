import os
from datetime import datetime
from python.helpers.extension import Extension
from python.helpers import files
from python.helpers.print_style import PrintStyle
from agent import LoopData


LOGS_DIR = "usr/logs"


class DailyLog(Extension):
    """
    Appends a lightweight session summary to a daily log file after each
    monologue completes.

    Log files are stored at usr/logs/YYYY-MM-DD.md and accumulate entries
    throughout the day. No extra LLM call is made — the extension captures
    the user message and the final response text from loop_data.
    """

    async def execute(self, loop_data: LoopData = LoopData(), **kwargs):
        try:
            now = datetime.now()
            date_str = now.strftime("%Y-%m-%d")
            time_str = now.strftime("%H:%M")

            # Extract the user message
            user_msg = ""
            if loop_data.user_message and loop_data.user_message.content:
                content = loop_data.user_message.content
                if isinstance(content, str):
                    user_msg = content.strip()
                elif isinstance(content, list):
                    # Multi-part message — take first text part
                    for part in content:
                        if isinstance(part, str):
                            user_msg = part.strip()
                            break
                        elif isinstance(part, dict) and part.get("type") == "text":
                            user_msg = part.get("text", "").strip()
                            break

            if not user_msg:
                return  # nothing meaningful to log

            # Truncate long messages for the log
            if len(user_msg) > 200:
                user_msg = user_msg[:200] + "..."

            # Get the last response (if available)
            response_summary = ""
            if loop_data.last_response:
                resp = loop_data.last_response.strip()
                if len(resp) > 200:
                    resp = resp[:200] + "..."
                response_summary = f"\n  - **Response:** {resp}"

            # Build the log entry
            entry = f"- **{time_str}** — {user_msg}{response_summary}\n"

            # Ensure the logs directory exists
            logs_dir = files.get_abs_path(LOGS_DIR)
            os.makedirs(logs_dir, exist_ok=True)

            # Append to today's log file
            log_path = os.path.join(logs_dir, f"{date_str}.md")
            if not os.path.exists(log_path):
                header = f"# Daily Log — {date_str}\n\n"
                files.write_file(log_path, header)

            existing = files.read_file(log_path) or ""
            files.write_file(log_path, existing + entry)

        except Exception as e:
            # Never let logging break the agent flow
            PrintStyle(font_color="yellow", padding=False).print(
                f"Daily log warning: {e}"
            )
