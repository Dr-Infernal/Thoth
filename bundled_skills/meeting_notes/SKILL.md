---
name: meeting_notes
display_name: Meeting Notes
icon: "📋"
description: Structure raw meeting notes into actionable minutes with follow-ups.
tools:
  - memory
  - calendar
enabled_by_default: false
version: "1.1"
tags:
  - productivity
  - meetings
author: Thoth
---

When the user shares **meeting notes**, asks you to **summarise a meeting**, or says they just finished a meeting, follow these steps:

1. **Parse the Input** — Read through the raw notes, transcript, or description the user provides.
2. **Identify Participants** — List everyone mentioned or involved.
3. **Structure the Minutes** — Organise into:
   - **Meeting Title & Date**
   - **Attendees**
   - **Key Discussion Points** — Summarise each topic discussed in 1–2 sentences
   - **Decisions Made** — Bullet list of any decisions reached
   - **Action Items** — For each action item, capture:
     - What needs to be done
     - Who is responsible
     - When it's due (if mentioned)
4. **Save Action Items** — Store the action items to memory so they can be referenced later. Use a descriptive subject like `Team Standup Actions — March 28`.
5. **Schedule Follow-ups** — If any follow-up meetings were mentioned, offer to create calendar events.
6. **Present** — Output the structured minutes in a clean, skimmable format.

Keep the language professional but concise. The goal is to turn messy notes into something the user can share with their team.
