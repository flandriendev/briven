"""
Tool: call_agents_parallel

Spawns 2-8 specialized subordinate agents that execute concurrently using
asyncio.gather(). Each agent gets its own profile, message, and runs its
full monologue independently. Results are collected and returned together.

This complements the existing call_subordinate tool (sequential, 1 at a time)
by enabling parallel workflows like:
  - Research agent + Developer agent working simultaneously
  - Multiple researcher agents each querying different topics
  - Telegram agent + Email agent sending notifications in parallel

Architecture:
  - Each parallel agent is a fresh Agent instance with its own number
  - All share the parent's AgentContext (same as call_subordinate)
  - Agents run via asyncio.gather() for true concurrency
  - Results are returned as a formatted summary to the parent
  - Parent decides how to combine/use the results

Limits:
  - Minimum 2 agents, maximum 8 (to prevent resource exhaustion)
  - Each agent runs independently (no inter-agent communication during execution)
"""

import asyncio
import json

from agent import Agent, UserMessage
from python.helpers.tool import Tool, Response
from python.helpers.dirty_json import DirtyJson
from python.helpers.print_style import PrintStyle
from initialize import initialize_agent

MIN_AGENTS = 2
MAX_AGENTS = 8


class ParallelDelegation(Tool):

    async def execute(self, agents="", **kwargs):
        # Parse the agents specification
        agent_specs = self._parse_agents(agents)

        if not agent_specs:
            return Response(
                message="Error: 'agents' argument must be a JSON array of objects "
                        "with 'message' and optional 'profile' fields. "
                        f"Provide {MIN_AGENTS}-{MAX_AGENTS} agent specifications.",
                break_loop=False,
            )

        if len(agent_specs) < MIN_AGENTS:
            return Response(
                message=f"Error: Need at least {MIN_AGENTS} agents for parallel execution. "
                        "Use call_subordinate for single agent delegation.",
                break_loop=False,
            )

        if len(agent_specs) > MAX_AGENTS:
            return Response(
                message=f"Error: Maximum {MAX_AGENTS} parallel agents allowed. "
                        f"Got {len(agent_specs)}. Split into smaller batches.",
                break_loop=False,
            )

        # Spawn and run all agents concurrently
        tasks = []
        agent_instances = []

        for i, spec in enumerate(agent_specs):
            config = initialize_agent()

            profile = spec.get("profile", "")
            if profile:
                config.profile = profile

            message = spec.get("message", "")
            if not message:
                continue

            # Create agent with a unique number offset from parent
            # Use parent.number + 100 + i to avoid colliding with regular subordinate numbering
            agent_num = self.agent.number + 100 + i
            sub = Agent(agent_num, config, self.agent.context)
            sub.set_data(Agent.DATA_NAME_SUPERIOR, self.agent)
            agent_instances.append((sub, spec))

            # Create the async task
            tasks.append(self._run_agent(sub, message, i))

        if not tasks:
            return Response(
                message="Error: No valid agent specifications with messages found.",
                break_loop=False,
            )

        # Run all agents concurrently
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Format results
        output_parts = []
        for i, (result, (sub, spec)) in enumerate(zip(results, agent_instances)):
            profile = spec.get("profile", "default")
            label = spec.get("label", f"Agent {i+1} ({profile})")

            if isinstance(result, Exception):
                output_parts.append(
                    f"### {label}\n**Status:** Error\n**Error:** {str(result)}\n"
                )
            else:
                output_parts.append(
                    f"### {label}\n**Status:** Complete\n**Result:**\n{result}\n"
                )

            # Seal the agent's topic after completion
            try:
                sub.history.new_topic()
            except Exception:
                pass

        summary = (
            f"## Parallel Execution Results ({len(tasks)} agents)\n\n"
            + "\n---\n\n".join(output_parts)
        )

        return Response(message=summary, break_loop=False)

    async def _run_agent(self, agent: Agent, message: str, index: int) -> str:
        """Run a single agent's monologue and return the result."""
        agent.hist_add_user_message(UserMessage(message=message, attachments=[]))
        result = await agent.monologue()
        return result

    def _parse_agents(self, agents_arg) -> list[dict]:
        """Parse the agents argument into a list of agent specifications."""
        if not agents_arg:
            return []

        # If already a list (parsed by the framework)
        if isinstance(agents_arg, list):
            return agents_arg

        # Try to parse as JSON string
        if isinstance(agents_arg, str):
            try:
                parsed = DirtyJson.parse_string(agents_arg)
                if isinstance(parsed, list):
                    return parsed
                if isinstance(parsed, dict):
                    return [parsed]
            except Exception:
                pass

            # Try standard json
            try:
                parsed = json.loads(agents_arg)
                if isinstance(parsed, list):
                    return parsed
            except Exception:
                pass

        return []

    def get_log_object(self):
        return self.agent.context.log.log(
            type="subagent",
            heading=f"icon://groups {self.agent.agent_name}: Parallel Agent Execution",
            content="",
            kvps=self.args,
        )
