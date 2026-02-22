<div align="center">

<!-- Replace with your actual Briven logo -->
<!-- <img src="docs/res/briven-logo.png" alt="Briven Logo" width="200"> -->

# `Briven`

**A personal, autonomous AI agent framework — disciplined by /atlas, secured by Tailscale.**

**Website: [briven.ai](https://briven.ai)**

[![GitHub](https://img.shields.io/badge/GitHub-flandriendev%2Fbriven-181717?style=for-the-badge&logo=github&logoColor=white)](https://github.com/flandriendev/briven)
[![Website](https://img.shields.io/badge/Website-briven.ai-blue?style=for-the-badge&logo=safari&logoColor=white)](https://briven.ai)
[![License](https://img.shields.io/badge/License-MIT-green?style=for-the-badge)](./LICENSE)
[![Python](https://img.shields.io/badge/Python-3.12%20%7C%203.13-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![Tailscale](https://img.shields.io/badge/Networking-Tailscale-4B32C3?style=for-the-badge&logo=tailscale&logoColor=white)](https://tailscale.com)

## Documentation

[Introduction](#what-is-briven) •
[Quick Start](#quick-start) •
[Installation](./docs/setup/mac-mini.md) •
[VPS Deployment](./docs/setup/vps-tailscale-secure.md) •
[Usage](./docs/guides/usage.md) •
[Architecture](./docs/developer/architecture.md)

</div>

---

## What is Briven?

**Briven** is a personal, organic agentic framework — self-extending, memory-persistent, and structurally governed by the **[/atlas](./atlas/)** instruction layer.

- **Not pre-programmed for specific tasks.** Give it a task; it gathers information, executes code, cooperates with subordinate agents, and learns.
- **Fully transparent and customizable.** Every prompt, tool, and behavior is readable and editable.
- **Governed by /atlas.** Before acting, the agent always reads and respects the `/atlas` guidelines — keeping behavior disciplined and process-aware.
- **Secured by Tailscale.** Preferred networking approach: zero-trust, no exposed ports, no tunnels needed.
- **Memory-persistent.** SQLite + embeddings + hybrid BM25/semantic search. The agent remembers across sessions.

---

## ⚡ Quick Start

### Native Install (recommended)

One command on a fresh Ubuntu/Debian VPS — the guided installer walks you through everything:

```bash
curl -fsSL https://raw.githubusercontent.com/flandriendev/briven/main/install.sh | bash
```

The installer handles system deps, Python, Tailscale, and a systemd service — and **asks for your API keys during setup** so Briven is ready to use immediately:

1. **[Tailscale auth key](https://login.tailscale.com/admin/settings/keys)** — zero-trust networking (no exposed ports)
2. **LLM API keys** — OpenRouter, Anthropic, xAI/Grok, OpenAI, DeepSeek, Google (enter any you have, skip the rest)
3. **[Tailscale API token](https://login.tailscale.com/admin/settings/keys)** — optional ACL enforcement (`tag:admin` → `tag:briven-server:8000`)

After install, open **http://\<your-tailscale-ip\>:8000** from any device on your tailnet.

To edit keys or settings later:

```bash
nano ~/briven/usr/.env          # Edit API keys or add new providers
sudo systemctl restart briven   # Apply changes
journalctl -u briven -f         # Watch logs
```

> **Supported distros:** Ubuntu 22.04 / 24.04, Debian 12 / 13. On Python 3.13+ the installer auto-patches `unstructured→0.20.8` and disables `kokoro` (TTS) for compatibility.

### Docker Install (optional)

> Docker is optional — it provides better isolation, but native install is still preferred for full modularity and direct access to all tools.

```bash
git clone https://github.com/flandriendev/briven.git && cd briven
cp usr/.env.example usr/.env && nano usr/.env   # Add your API keys

# Build and start (with Tailscale inside the container):
TAILSCALE_AUTHKEY=tskey-auth-xxxxx docker compose up -d --build
```

Without `TAILSCALE_AUTHKEY`, the container binds to `127.0.0.1:8000` (local access only — no public exposure).
With `TAILSCALE_AUTHKEY`, it auto-authenticates and binds to its Tailscale IP.

> **Tailscale auth key:** [login.tailscale.com/admin/settings/keys](https://login.tailscale.com/admin/settings/keys) — create a reusable key.

> **More guides:** [Mac Mini Setup](./docs/setup/mac-mini.md) | [VPS + Tailscale Hardening](./docs/setup/vps-tailscale-secure.md) (UFW, fail2ban, SSH lockdown)

---

## 🗂 Architecture: The /atlas Layer

Briven uses the **GOTCHA Framework** — a 6-layer architecture:

| Layer | Folder | Purpose |
|-------|--------|---------|
| **Goals** | `goals/` | What needs to happen (process definitions) |
| **Orchestration** | AI manager (you) | Coordinates execution; reads /atlas first |
| **Tools** | `tools/` | Deterministic scripts that do actual work |
| **Context** | `context/` | Domain knowledge, tone, ICP |
| **Hard Prompts** | `hardprompts/` | Reusable LLM instruction templates |
| **Args** | `args/` | Behavior settings (models, modes, schedules) |

**The `/atlas` folder** contains the operational handbook. The system prompt and agent orchestration layer **always reference /atlas before any action** — ensuring disciplined, process-driven behavior.

---

## 💡 Key Features

### 1. General-purpose Autonomous Agent
- No predefined task scope. Give it any goal — it plans, executes, and adapts.
- Persistent memory: facts, code snippets, past solutions, instructions — all retrievable via hybrid search.

### 2. Multi-agent Cooperation
- Every agent has a superior (human or parent agent). Every agent can spawn subordinates.
- The root agent (Briven) talks directly to the human user. Subordinates handle subtasks.

### 3. /atlas-governed Behavior
- System prompt always loads `/atlas` guidelines before acting.
- Keeps the agent disciplined: checks `goals/manifest.md`, uses existing tools, documents failures.

### 4. Tailscale-first Networking + ACL Enforcement
- No exposed public ports. Access via Tailscale mesh network.
- Secure remote access from any device on your tailnet.
- **ACL enforcement:** Only `tag:admin` devices can reach Briven on port 8000 — all others denied.
- See `tools/tailscale.py` for integration helpers and ACL management (`--apply-acl`, `--acl-status`).

### 5. Memory System
- SQLite + vector embeddings + BM25 hybrid search.
- Daily session logs in `memory/logs/`.
- Persistent facts in `memory/MEMORY.md`.
- Tools: `atlas/memory/memory_read.py`, `memory_write.py`, `hybrid_search.py`.

### 6. Fully Customizable
- Every prompt lives in `prompts/` — edit to change behavior completely.
- Every tool lives in `python/tools/` — extend without touching core code.
- Subagent profiles in `agents/` — specialized roles (developer, researcher, hacker, etc.).
- Env-var driven configuration via `BRIVEN_SET_*` prefix.

### 7. Skills (SKILL.md Standard)
- Portable, structured agent capabilities.
- Compatible with Claude Code, Cursor, OpenAI Codex CLI, GitHub Copilot.
- Import and manage via the Web UI.

### 8. MCP + A2A Protocol
- Briven can act as an MCP server or consume external MCP tools.
- Agent-to-Agent (A2A) protocol for multi-agent orchestration across systems.

---

## 📁 Project Structure

```
briven/
├── atlas/                  # /atlas: operational handbook + memory module
│   ├── CLAUDE.md           # GOTCHA framework system handbook
│   ├── SETUP_GUIDE.md      # Setup reference
│   └── memory/             # Memory tools (read, write, search)
├── agents/                 # Subagent profiles
│   ├── briven/          # Root agent profile
│   ├── developer/          # Developer-specialized agent
│   ├── researcher/         # Research-specialized agent
│   └── hacker/             # Security-specialized agent
├── prompts/                # All system prompts (fully editable)
├── python/
│   ├── tools/              # Built-in tools (code execution, browser, memory, etc.)
│   ├── helpers/            # Framework utilities
│   ├── api/                # REST API endpoints
│   └── extensions/         # Hook-based extensions
├── tools/                  # Custom/user tools (tailscale, telegram, etc.)
├── memory/                 # Persistent memory (MEMORY.md + daily logs)
├── knowledge/              # RAG knowledge base
├── docs/                   # Documentation
│   └── setup/
│       ├── mac-mini.md
│       ├── vps-tailscale-secure.md
│   └── guides/
├── webui/                  # Web interface
├── run_ui.py               # Main server entrypoint
├── install.sh              # One-liner installer
└── .env.example            # Environment variable template
```

---

## 🚀 Real-world Use Cases

- **Financial Analysis** — Scrape, correlate, chart Bitcoin trends vs. news events.
- **Excel Automation** — Validate, clean, consolidate spreadsheets; generate executive reports.
- **API Integration** — Feed it an API snippet; it learns and stores the integration for future use.
- **Server Monitoring** — Scheduled checks: CPU, disk, memory. Alert on threshold breaches.
- **Multi-client Isolation** — Separate projects per client: isolated memory, secrets, instructions.

---

## ⚙️ Configuration

Copy `usr/.env.example` to `usr/.env` and fill in your API keys:

```bash
# LLM provider — pick one or more (Briven uses LiteLLM for multi-provider switching)
API_KEY_OPENROUTER=sk-or-...   # OpenRouter (200+ models with one key, recommended)
API_KEY_OPENAI=sk-...          # OpenAI (GPT-4o, o1, o3)
API_KEY_ANTHROPIC=sk-ant-...   # Anthropic (Claude 4.5, Claude 4)
API_KEY_XAI=xai-...            # xAI / Grok (strong reasoning/code)
API_KEY_GOOGLE=AIzaSy-...      # Google Gemini (multimodal)
API_KEY_DEEPSEEK=sk-...        # DeepSeek (cost-effective)

# Tailscale (optional but recommended)
TAILSCALE_AUTHKEY=tskey-auth-...
TAILSCALE_API_KEY=tskey-api-...     # ACL enforcement (optional)

# Automated settings via env vars
BRIVEN_SET_chat_model=openrouter/anthropic/claude-sonnet-4-6
BRIVEN_SET_work_dir=/home/briven/workspace
```

> See `usr/.env.example` for all supported providers (20+), messaging integrations, and configuration options.

---

## 📚 Documentation

| Page | Description |
|------|-------------|
| [Mac Mini Setup](./docs/setup/mac-mini.md) | Native Python + Tailscale setup on Mac Mini |
| [VPS + Tailscale](./docs/setup/vps-tailscale-secure.md) | VPS deployment with Tailscale zero-trust |
| [Usage Guide](./docs/guides/usage.md) | Basic and advanced usage |
| [Architecture](./docs/developer/architecture.md) | System design and components |
| [Extensions](./docs/developer/extensions.md) | Extending Briven |
| [MCP Setup](./docs/guides/mcp-setup.md) | MCP server/client configuration |
| [A2A Setup](./docs/guides/a2a-setup.md) | Agent-to-Agent protocol |
| [Troubleshooting](./docs/guides/troubleshooting.md) | Common issues and solutions |
| [Contributing](./docs/guides/contribution.md) | How to contribute |

---

## 🔒 Security Notes

1. **Briven has root-level access in its environment.** Run it in Docker or a dedicated VM unless you know what you're doing.
2. **Tailscale is strongly preferred** over port forwarding or public exposure.
3. **Secrets management** — Agent can use credentials without them appearing in context. Store in `.env` or the secrets manager.

---

## 🤝 Contributing

Issues and PRs welcome at [github.com/flandriendev/briven](https://github.com/flandriendev/briven).

---

## 💛 Sponsor Briven

Briven is and will always remain **100% open-source and free**. If you find value in this project and want to support its continued development, consider becoming a sponsor!

Your sponsorship helps fund:
- Ongoing development of new skills and features
- Security hardening and infrastructure
- Community support and documentation

### Sponsorship Tiers

| Tier | Price | Perks |
|------|-------|-------|
| ☕ **Supporter** | €5/month | Shoutout in README + private Discord channel |
| 🚀 **Early Adopter** | €10/month | Everything above + early access to new skills + priority Discord support |
| 🛠️ **Builder** | €25/month | Everything above + 1 custom skill request/month (2–4 hrs scope) |

<a href="https://github.com/sponsors/flandriendev">
  <img src="https://img.shields.io/badge/Sponsor-Briven-ea4aaa?style=for-the-badge&logo=github-sponsors" alt="Sponsor Briven" />
</a>

Every contribution matters — thank you for helping keep Briven alive and growing!

---

<div align="center">

**[Website](https://briven.ai)** · **[GitHub](https://github.com/flandriendev/briven)** · **[Documentation](./docs/)**

Copyright (c) 2026 Briven by flndrn · MIT License

</div>

