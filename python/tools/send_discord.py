"""
Agent tool: send_discord

Sends a message to a Discord channel from within the agent loop.
Uses the standalone tools/discord.py module for the actual API call.
"""

from python.helpers.tool import Tool, Response
from python.helpers import dotenv


class SendDiscord(Tool):

    async def execute(self, **kwargs):
        message = self.args.get("message", "")
        username = self.args.get("username", "Briven")

        if not message:
            return Response(
                message="Error: 'message' argument is required.",
                break_loop=False,
            )

        webhook = dotenv.get_dotenv_value("DISCORD_WEBHOOK_URL")
        if not webhook:
            return Response(
                message="Error: Discord not configured. Set DISCORD_WEBHOOK_URL in .env",
                break_loop=False,
            )

        try:
            from tools.discord import send_message
            result = send_message(
                message=message,
                username=username or None,
            )
            if result.get("ok"):
                return Response(
                    message="Discord message sent successfully.",
                    break_loop=False,
                )
            else:
                return Response(
                    message=f"Discord API error: {result}",
                    break_loop=False,
                )
        except Exception as e:
            return Response(
                message=f"Failed to send Discord message: {e}",
                break_loop=False,
            )
