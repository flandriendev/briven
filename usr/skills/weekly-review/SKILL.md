---
name: "weekly-review"
description: "Structured weekly business review and planning session. Analyzes the past 7 days of daily session logs and produces a review of accomplishments, missed items, patterns, and next week's priorities. Use when user says 'weekly review', 'let's do a review', 'what happened this week', or at the start of a new week."
version: "1.0.0"
author: "Briven"
license: "MIT"
tags: ["productivity", "review", "planning", "weekly", "logs"]
triggers:
  - "weekly review"
  - "let's do a review"
  - "what happened this week"
  - "week in review"
  - "review my week"
allowed_tools:
  - code_execution_tool
  - knowledge_tool
  - response
metadata:
  complexity: "beginner"
  category: "productivity"
  estimated_time: "5 minutes"
---

# Weekly Review

Structured review of the past week and planning for the next.

## Process

### Step 1: Gather Data

Read the past 7 days of daily logs from `usr/logs/`:
- Today's log and the 6 preceding days (files named `YYYY-MM-DD.md`)
- If logs don't exist for some days, note which days are missing

Also check the user's business context in `usr/context/my-business.md` for current goals and priorities (if configured).

### Step 2: Review Format

Present the review in this structure:

```markdown
## Weekly Review: [Week of Mon DD - Sun DD]

### What Happened This Week
- [Key events, tasks, and sessions from logs]
- [Notable accomplishments]
- [Unexpected issues or changes]

### What Got Done
- [Completed tasks and deliverables]
- [Progress on goals]

### What Didn't Get Done
- [Tasks that slipped]
- [Why they slipped (if apparent from logs)]

### Patterns & Insights
- [Recurring themes across the week]
- [Types of tasks that dominated]
- [Observations — what took the most effort]

### Next Week's Plan
- **Priority 1:** [Most important thing]
- **Priority 2:** [Second most important]
- **Priority 3:** [Third most important]
- **Carry-over:** [Tasks from this week that roll forward]
```

### Step 3: Update & Follow-up

After the review:
1. Ask user if any priorities need adjustment
2. Offer to create scheduled tasks for next week's priorities
3. If the business context files exist, suggest updates if goals have changed

## Rules

- Be honest about what didn't get done — don't spin it
- If logs are sparse, note this and suggest the user interact with Briven more regularly so daily logs accumulate
- Keep the review concise — scannable in 5 minutes
- The planning section is the most important output — make it actionable
- If no daily logs exist yet, explain how the daily logging system works and offer to start tracking from today
