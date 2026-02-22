{{if agent_profiles}}
### call_agents_parallel

spawn 2-8 specialized agents that run concurrently
use when multiple independent subtasks can be done simultaneously
each agent gets its own profile and message, runs full monologue in parallel
results collected and returned together

when to use:
  - multiple independent research queries
  - sending notifications to different channels simultaneously
  - parallel coding tasks that don't depend on each other
  - any workflow where agents don't need to communicate during execution

when NOT to use:
  - tasks that depend on each other (use call_subordinate sequentially)
  - single subtask (use call_subordinate instead)
  - tasks that need to share intermediate results

agents arg: JSON array of objects, each with:
  - "message": task description for this agent (required)
  - "profile": agent profile to use (optional, defaults to default)
  - "label": human-readable label for this agent in results (optional)

example usage
~~~json
{
    "thoughts": [
        "I need to research two topics and send a notification at the same time",
        "These are independent tasks, so I'll run them in parallel"
    ],
    "tool_name": "call_agents_parallel",
    "tool_args": {
        "agents": [
            {"profile": "researcher", "message": "Research the latest trends in AI safety", "label": "AI Safety Research"},
            {"profile": "researcher", "message": "Find recent papers on multi-agent systems", "label": "Multi-Agent Research"},
            {"profile": "developer", "message": "Write a Python script to merge the research results", "label": "Merge Script"}
        ]
    }
}
~~~

**available profiles:**
{{agent_profiles}}
{{endif}}
