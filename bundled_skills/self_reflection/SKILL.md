---
name: self_reflection
display_name: Self-Reflection
icon: "🪞"
description: Periodically review memory for contradictions, gaps, and stale information.
tools:
  - memory
enabled_by_default: false
version: "1.0"
tags:
  - memory
  - quality
author: Thoth
---

When the user asks you to **review your memories**, **check what you know**, **clean up your knowledge**, or when you notice a potential contradiction in recalled memories, apply this process:

## Contradiction Detection

1. **Flag Conflicts** — When recalled memories contradict each other (e.g. two different birthdays for the same person, or "lives in London" vs. "moved to Berlin"), surface the conflict to the user immediately. Don't silently pick one.
2. **Ask, Don't Assume** — Say exactly what conflicts you see and ask the user which version is correct. Then update the wrong memory and confirm the fix.
3. **Check Dates** — When you see a memory that might be outdated (job titles, addresses, project statuses), mention it: *"I have that you work at X — is that still current?"*

## Memory Audit (when explicitly requested)

4. **Systematic Sweep** — Use `search_memory` with broad category queries (person, preference, fact, event, project, place) to surface everything. Use `explore_connections` to visualise relationships and spot gaps. Review each category for:
   - **Duplicates** — Same fact stored under different wording
   - **Stale entries** — Jobs, addresses, or statuses that may have changed
   - **Orphans** — Entities with no connections to anything else
   - **Missing links** — Related memories that aren't connected (e.g. a person and their workplace)
5. **Fix As You Go** — Update or `link_memories` during the audit rather than compiling a report first. Confirm each change with the user.
6. **Summary** — After the audit, give a brief count: how many memories reviewed, how many updated, how many linked, and flag any that need the user's input.

## Ongoing Awareness

7. **Correction Logging** — When the user corrects you on a fact ("Actually, it's March 20, not March 15"), always update the existing memory. After updating, briefly acknowledge the correction so the user knows it stuck.
8. **Confidence Signals** — If you recall a memory but aren't confident it's still accurate (e.g. it's about a fast-changing topic like a project status), say so: *"Last I saved, the deadline was June 1 — is that still the plan?"*
