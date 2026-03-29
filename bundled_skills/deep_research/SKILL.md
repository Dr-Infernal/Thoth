---
name: deep_research
display_name: Deep Research
icon: "🔬"
description: Perform multi-source research on a topic and produce a structured report.
tools:
  - web_search
  - url_reader
  - arxiv
enabled_by_default: false
version: "1.0"
tags:
  - research
  - analysis
author: Thoth
---

When the user asks you to **research a topic in depth**, **write a research report**, or **investigate something thoroughly**, follow these steps:

1. **Clarify Scope** — If the topic is broad, ask one focused question to narrow it down before proceeding. Otherwise, proceed directly.
2. **Initial Search** — Run 2–3 web searches with varied queries to gather diverse perspectives on the topic.
3. **Source Deep-Dive** — Pick the 3–5 most promising URLs from the search results and read their full content using the URL reader.
4. **Academic Check** — If the topic is scientific or technical, search arXiv for relevant recent papers. Summarise key findings from the top 1–2 results.
5. **Synthesise** — Compile findings into a structured report:
   - **Executive Summary** — 2–3 sentence overview
   - **Key Findings** — Numbered list of the most important points
   - **Details** — Deeper discussion organised by sub-topic
   - **Open Questions** — What remains unclear or debated
   - **Sources** — List all URLs and papers referenced
6. **Cite Everything** — Every claim should reference its source with a numbered citation.

Aim for thoroughness over brevity. The user wants depth — give them a report they can act on.
