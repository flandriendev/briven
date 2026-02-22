# Tools Manifest

> **RULE:** Always check this file before writing new tool scripts. If a tool exists, use it.
> If you create a new tool, add it here with a one-sentence description.

## Available Tools

| Tool | Path | Description |
| ---- | ---- | ----------- |
| Tailscale helpers | `tools/tailscale.py` | Status, IP lookup, peer list, and Tailscale Serve integration for secure zero-trust networking. |
| Telegram notify | `tools/telegram.py` | Send messages to a Telegram chat via Bot API (requires `TELEGRAM_BOT_TOKEN` + `TELEGRAM_CHAT_ID`). |
| WhatsApp notify | `tools/whatsapp.py` | Send messages via WhatsApp Business Cloud API (requires `WHATSAPP_TOKEN` + `WHATSAPP_PHONE_ID`). |
| Email send | `tools/email_send.py` | Send plain-text or HTML email via SMTP (requires `EMAIL_USER` + `EMAIL_PASSWORD`). |
| Slack notify | `tools/slack.py` | Send messages to Slack via Webhook or Bot API (requires `SLACK_WEBHOOK_URL` or `SLACK_BOT_TOKEN` + `SLACK_CHANNEL`). |
| Discord notify | `tools/discord.py` | Send messages or rich embeds to Discord via Webhook (requires `DISCORD_WEBHOOK_URL`). |
| Claude code gen | `tools/claude_code.py` | Generate, review, or explain code using the Anthropic API (`claude-sonnet-4-6` by default). |
| Memory read | `atlas/memory/memory_read.py` | Read stored memories from the SQLite database in formatted output. |
| Memory write | `atlas/memory/memory_write.py` | Write facts, events, preferences, or insights to the memory database. |
| Memory DB | `atlas/memory/memory_db.py` | Direct SQLite memory queries — search, list, delete entries. |
| Semantic search | `atlas/memory/semantic_search.py` | Vector-embedding similarity search over stored memories. |
| Hybrid search | `atlas/memory/hybrid_search.py` | Combined BM25 + semantic search over memories (best recall). |
| Embed memory | `atlas/memory/embed_memory.py` | Generate and store embeddings for memory entries. |

---

*Add new tools above. Format: `| Name | path | One-sentence description. |`*
