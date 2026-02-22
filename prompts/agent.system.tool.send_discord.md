### send_discord:
Send a message to a Discord channel via webhook. Requires DISCORD_WEBHOOK_URL to be configured in .env.

Use this tool for:
- Sending notifications to a Discord server channel
- Posting alerts, status updates, or reports to Discord
- Any situation where the user asks you to "send to Discord" or "notify Discord"

#### Arguments:
 *  "message" (string) : The message text to send. Supports Discord markdown.
 *  "username" (Optional, string) : Display name for the webhook bot (default: "Briven").

#### Usage example:
```json
{
    "thoughts": [
        "The user asked me to post the build results to their Discord server.",
    ],
    "tool_name": "send_discord",
    "tool_args": {
        "message": "Build #42 completed: 0 errors, 3 warnings.",
        "username": "Briven CI"
    }
}
```
