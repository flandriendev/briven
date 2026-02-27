---
name: "business-setup"
description: "Initial business configuration wizard. Runs a conversational questionnaire to configure Briven for your specific business, voice, and goals. Use when user says 'set up my business', 'configure my business', 'initialize', or 'start fresh'."
version: "1.0.0"
author: "Briven"
license: "MIT"
tags: ["onboarding", "setup", "business", "configuration", "wizard"]
triggers:
  - "set up my business"
  - "configure my business"
  - "initialize"
  - "start fresh"
  - "business setup"
allowed_tools:
  - code_execution_tool
  - response
metadata:
  complexity: "beginner"
  category: "productivity"
  estimated_time: "10 minutes"
---

# Business Setup Wizard

Configure Briven for a specific business through a conversational questionnaire.

## When to Use

- `usr/context/my-business.md` contains placeholder text
- User says "set up my business", "configure", "initialize", or "start fresh"
- User wants to reconfigure from scratch

## Process

Run the phases below **conversationally** — ask a batch of questions, wait for answers, then move to the next phase. Do NOT dump all questions at once.

### Phase 1: Your Business

Ask these questions (one batch):

1. What does your business do? (one sentence)
2. Who are your customers? (industry, size, role they talk to)
3. What's your main offer? (service/product, rough price range)
4. Where do most of your leads come from? (referrals, LinkedIn, ads, content, etc.)
5. What's your biggest business challenge right now?

### Phase 2: Your Voice

Ask these questions:

1. How would you describe your communication style? (e.g., direct and no-BS, warm and approachable, technical and precise)
2. Paste a message, email, or post you've written that sounds like "you" — something you'd actually send
3. What words or phrases do you use often?
4. What tone do you NEVER want to sound like? (e.g., corporate, salesy, overly casual)

### Phase 3: Your Tools & Integrations

Ask these questions:

1. What tools do you use daily? (CRM, email platform, project management, calendar)
2. Do you create content? If so, what platforms? (LinkedIn, YouTube, blog, newsletter, etc.)
3. What tasks do you wish were automated?

### Phase 4: Your Goals

Ask these questions:

1. What are your top 3 priorities for the next 90 days?
2. What does success look like for this quarter?
3. What tasks drain your energy and you want off your plate?

### Phase 5: Auto-Configure

After collecting all answers:

1. **Write `usr/context/my-business.md`** — Structured business profile from Phase 1 answers. Include: business description, target customer, main offer, lead sources, current challenge. Remove the placeholder comment.

2. **Write `usr/context/my-voice.md`** — Voice guide from Phase 2 answers. Include: communication style description, sample text, characteristic phrases, anti-patterns (what to avoid). Remove the placeholder comment.

3. **Validation test** — Write a 2-sentence introduction of the user's business in their voice. Ask: "Does this sound like you?" If not, refine the voice guide.

4. **Print capabilities** — Show the user what they can now do:
   ```
   You're set up! Here's what you can do now:

   - "Research [company/person/topic]" — Deep research on anything
   - "Write a LinkedIn post about [topic]" — Content in your voice
   - "Help with this email: [paste]" — Triage, draft replies
   - "Weekly review" — Review your week and plan the next
   - "Create a skill for [workflow]" — Build new reusable workflows
   ```

## Edge Cases

- If user wants to skip a phase, that's fine — write what you have
- If user gives very short answers, ask one follow-up for the most critical info
- If reconfiguring, back up existing files before overwriting
- If user pastes a very long voice sample, extract the key patterns (don't store the full text)
