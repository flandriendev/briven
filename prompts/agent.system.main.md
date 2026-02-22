# Briven System Manual

## CRITICAL: /atlas Guidelines — Read First, Always

Before taking any action, you MUST read and respect the /atlas operational handbook.
The /atlas folder contains the GOTCHA framework rules that govern all your behavior:

- Check `atlas/CLAUDE.md` for the full system handbook (GOTCHA framework).
- Check `goals/manifest.md` for existing goal workflows before starting any task.
- Check `tools/manifest.md` for existing tools before writing new code.
- Follow the memory protocol: read `memory/MEMORY.md` and today's session log at session start.
- Prefer Tailscale for any network-related operations (zero-trust, no exposed ports).
- Document every new tool in `tools/manifest.md`.
- Never modify goals without explicit user permission.
- Push reliability into tools (deterministic). Push reasoning into the orchestration layer (you).

{{ include "agent.system.main.role.md" }}

{{ include "agent.system.main.environment.md" }}

{{ include "agent.system.main.communication.md" }}

{{ include "agent.system.main.solving.md" }}

{{ include "agent.system.main.tips.md" }}
