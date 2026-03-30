---
name: task_automation
display_name: Task Automation
icon: "⚙️"
description: Design effective automated workflows using scheduled tasks, prompt chaining, and delivery channels.
tools:
  - task
enabled_by_default: false
version: "2.0"
tags:
  - automation
  - productivity
author: Thoth
---

When the user wants to **set up automations**, **create recurring workflows**, **schedule something**, or **set a reminder**, apply these principles:

## How Tasks Work

A task is an ordered list of **prompts** executed sequentially in a dedicated thread. Each step sees the full conversation history from earlier steps, so step 2 can reference, analyse, or build on the output of step 1. This is the core power — **prompt chaining** turns simple instructions into complex multi-turn workflows.

There are three task types:
- **Multi-step prompt tasks** — the agent executes each prompt in order, accumulating context. Use for research, reports, gather-then-summarise workflows.
- **Notify-only tasks** — fire a desktop/channel notification with no agent invocation. Use for simple reminders and timers.
- **One-shot timers** — use `delay_minutes` for quick "remind me in 30 minutes" requests. These auto-delete after firing.

## Prompt Chaining — The Core Pattern

1. **Chain Steps That Build on Each Other** — Design prompts so each step uses the output of the previous one. Example:
   - Step 1: *"Search for the latest news about AI regulation in the EU"*
   - Step 2: *"Now summarise the key findings from above into 5 bullet points with source links"*
   - Step 3: *"Draft a short email to my team highlighting the top 3 developments"*

   Step 2 works because it can see step 1's search results in the conversation. Step 3 works because it can see the summary.

2. **Write Prompts Like Briefings** — State the goal, specify what to check, and describe the desired format. Vague prompts produce vague results. Each prompt should make it clear what the agent should do in *that* step.

3. **Conditional Logic in Prompts** — Write prompts that handle "nothing found" gracefully:
   *"Check for calendar events tomorrow. If there are none, just say 'Clear schedule tomorrow.' If there are events, list them with times and highlight any conflicts."*

4. **Use Template Variables** — `{{date}}`, `{{day}}`, `{{time}}`, `{{month}}`, `{{year}}` make prompts context-aware at runtime. *"Summarise news for {{date}}"* produces different results each day.

## When to Use One Task vs. Multiple Tasks

5. **One multi-step task** when the steps form a pipeline — each step needs the previous step's output. A research task that searches → reads sources → synthesises → formats is one task.
6. **Separate tasks** when the workflows are independent — a morning weather check and an inbox summary don't need each other's output. Separate tasks let the user enable, disable, schedule, or deliver them independently.
7. **Morning stack pattern** — For daily routines, create separate tasks for each piece (weather, news, calendar, project status). The user can toggle individual pieces on/off and schedule them at different times.

## Scheduling

8. **Match the schedule to the rhythm:**
   - `daily:HH:MM` — briefings, digests, check-ins
   - `weekly:DAY:HH:MM` — reviews, summaries, reports
   - `interval:H` / `interval_minutes:M` — monitoring, polling, frequent checks
   - `cron:EXPR` — complex schedules (e.g. `cron:0 9 * * mon-fri` for weekdays only)

## Delivery & Notification

9. **Pick the right channel** — Telegram for mobile-friendly results the user needs on the go, email for reports others need to see, desktop notification (`notify_only`) for simple nudges.
10. **Ask before defaulting** — Don't assume a delivery channel. Ask how the user wants to receive results. Some automations are better consumed on-demand.

## Advanced Features

11. **Model override** — Use the `model` parameter to run a specific task on a different model (e.g. a heavier model for complex research, a lighter one for quick checks).
12. **Persistent threads** — By default each run gets a fresh thread. For tasks that should maintain ongoing context across runs (e.g. a project status tracker that remembers prior updates), use `persistent_thread_id`.
13. **Skills override** — Assign specific skills to a task so it runs with a tailored skill set regardless of the user's global skill settings.

## Maintenance

14. **Check first** — Before creating a new task, check `task_list` to avoid duplicates or overlapping schedules.
15. **Test immediately** — Always suggest `task_run_now` after creation so the user can verify the output before waiting for the first scheduled run.
16. **Iterate prompts** — If the output isn't right, update the prompts with `task_update` rather than deleting and recreating.

## Monitoring / Polling

When the user wants to **monitor a condition** and be notified when it changes ("check X and tell me when Y", "alert me if Z drops below W"), use the **interval + self-disable** pattern:

17. **Use an interval schedule** — `interval_minutes:M` for frequent checks (stock availability, price drops) or `interval:H` for slower checks (daily digest changes).

18. **Write a conditional prompt** — The prompt should:
    - Check the condition (e.g. search the web, read a URL, check a price)
    - If the condition IS met → report the finding and self-disable with `task_update(task_id='{{task_id}}', enabled=false)`
    - If the condition is NOT met → say so briefly (this keeps the persistent thread informed without wasting tokens)

19. **Always use `persistent_thread_id`** — This lets the agent see prior checks across runs. Essential for "notify me if the price drops below X" (needs to compare to last check) or "tell me when there's a new version" (needs to know the old version).

20. **Template: polling prompt pattern** —
    ```
    Search for [condition]. If [success criteria], report your findings
    and call task_update(task_id='{{task_id}}', enabled=false) to stop
    this monitor. If [condition not met], say '[thing] not yet
    available as of {{time}} — will check again.'
    ```

21. **Self-disable, don't self-delete** — Background tasks cannot delete themselves (safety restriction). Use `task_update(enabled=false)` instead. The user can re-enable, delete, or leave the disabled task.
