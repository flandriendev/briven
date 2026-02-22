<div align="center">

<!-- Replace with your actual Briven logo -->
<!-- <img src="docs/res/briven-logo.png" alt="Briven Logo" width="200"> -->

# `Briven`

**A personal, autonomous AI agent framework — disciplined by /atlas, secured by Tailscale.**

**Website: [briven.ai](https://briven.ai)**

[![GitHub](https://img.shields.io/badge/GitHub-flandriendev%2Fbriven-181717?style=for-the-badge&logo=github&logoColor=white)](https://github.com/flandriendev/briven)
[![Website](https://img.shields.io/badge/Website-briven.ai-blue?style=for-the-badge&logo=safari&logoColor=white)](https://briven.ai)
[![License](https://img.shields.io/badge/License-MIT-green?style=for-the-badge)](./LICENSE)
[![Python](https://img.shields.io/badge/Python-3.10+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![Tailscale](https://img.shields.io/badge/Networking-Tailscale-4B32C3?style=for-the-badge&logo=tailscale&logoColor=white)](https://tailscale.com)

## Documentation

[Introduction](#what-is-briven) •
[Quick Start](#quick-start) •
[Installation](./docs/install-mac-mini.md) •
[VPS Deployment](./docs/install-vps-server.md) •
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

```bash
# One-liner install (Mac Mini or VPS):
curl -fsSL https://raw.githubusercontent.com/flandriendev/briven/main/install.sh | bash
```

Or manually:

```bash
git clone https://github.com/flandriendev/briven.git
cd briven
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # then fill in your API keys
uvicorn run_ui:app --host 0.0.0.0 --port 8000
# Visit http://localhost:8000
```

> **Tailscale users:** After setup, bind to your Tailscale IP (`--host 100.x.x.x`) for zero-trust access with no exposed ports.
> See [install-mac-mini.md](./docs/install-mac-mini.md) for the full Tailscale-native setup.

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

### 4. Tailscale-first Networking
- No exposed public ports. Access via Tailscale mesh network.
- Secure remote access from any device on your tailnet.
- See `tools/tailscale.py` for integration helpers.

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
│   ├── install-mac-mini.md
│   ├── install-vps-server.md
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

Copy `.env.example` to `.env` and fill in:

```bash
# LLM provider (openrouter recommended)
OPENROUTER_API_KEY=sk-or-...

# Or OpenAI directly
OPENAI_API_KEY=sk-...

# Tailscale (optional but recommended)
TAILSCALE_AUTH_KEY=tskey-auth-...

# Automated settings via env vars
BRIVEN_SET_chat_model=openrouter/anthropic/claude-sonnet-4-6
BRIVEN_SET_work_dir=/home/user/briven-workspace
```

---

## 📚 Documentation

| Page | Description |
|------|-------------|
| [install-mac-mini.md](./docs/install-mac-mini.md) | Native Python + Tailscale setup on Mac Mini |
| [install-vps-server.md](./docs/install-vps-server.md) | VPS deployment with systemd + Tailscale |
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

