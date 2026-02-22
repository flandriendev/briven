### send_slack:
Send a message to a Slack channel. Requires SLACK_WEBHOOK_URL or SLACK_BOT_TOKEN + SLACK_CHANNEL to be configured in .env.

Use this tool for:
- Notifying team channels about task completions or errors
- Sending alerts, reports, or summaries to Slack
- Any situation where the user asks you to "send to Slack" or "notify Slack"

#### Arguments:
 *  "message" (string) : The message text to send. Supports Slack mrkdwn formatting.
 *  "channel" (Optional, string) : Target channel (e.g. "#general"). Only used with Bot API, not webhooks.

#### Usage example:
```json
{
    "thoughts": [
        "The user wants me to notify the team on Slack that the deployment is complete.",
    ],
    "tool_name": "send_slack",
    "tool_args": {
        "message": "Deployment completed successfully. All tests passing."
    }
}
```
