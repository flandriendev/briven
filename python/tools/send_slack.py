"""
Agent tool: send_slack

Sends a message to a Slack channel from within the agent loop.
Uses the standalone tools/slack.py module for the actual API call.
"""

from python.helpers.tool import Tool, Response
from python.helpers import dotenv


class SendSlack(Tool):

    async def execute(self, **kwargs):
        message = self.args.get("message", "")
        channel = self.args.get("channel", "")

        if not message:
            return Response(
                message="Error: 'message' argument is required.",
                break_loop=False,
            )

        # Check if Slack is configured
        webhook = dotenv.get_dotenv_value("SLACK_WEBHOOK_URL")
        bot_token = dotenv.get_dotenv_value("SLACK_BOT_TOKEN")

        if not webhook and not bot_token:
            return Response(
                message="Error: Slack not configured. Set SLACK_WEBHOOK_URL or "
                        "SLACK_BOT_TOKEN + SLACK_CHANNEL in .env",
                break_loop=False,
            )

        try:
            from tools.slack import send_message
            result = send_message(
                message=message,
                channel=channel or None,
            )
            if result.get("ok"):
                return Response(
                    message="Slack message sent successfully.",
                    break_loop=False,
                )
            else:
                return Response(
                    message=f"Slack API error: {result}",
                    break_loop=False,
                )
        except Exception as e:
            return Response(
                message=f"Failed to send Slack message: {e}",
                break_loop=False,
            )
