<p align="center">
  <img src="docs/thoth_glyph_256.png" alt="Thoth" width="180">
</p>

<h1 align="center">𓁟 Thoth — Personal AI Sovereignty</h1>

<p align="center">
  <a href="https://github.com/siddsachar/Thoth/releases"><img src="https://img.shields.io/github/v/release/siddsachar/Thoth?style=flat&label=release&color=c9a227" alt="Release"></a>
  <a href="LICENSE"><img src="https://img.shields.io/github/license/siddsachar/Thoth?style=flat" alt="License"></a>
  <img src="https://img.shields.io/badge/platform-Windows%20%7C%20macOS-c9a227?style=flat" alt="Platform">
  <img src="https://img.shields.io/badge/tests-842%20unit%20%7C%20155%20integration-brightgreen?style=flat" alt="Tests">
</p>

Thoth is a **local-first AI assistant built for personal AI sovereignty** — your models, your data, your rules. It combines a powerful ReAct agent with 23 integrated tools (61 sub-operations) — web search, email, calendar, file management, shell access, browser automation, vision, long-term memory with a personal knowledge graph, scheduled tasks, habit tracking, and more — plus Telegram and Email messaging channels. Run everything locally via [Ollama](https://ollama.com/), or add opt-in cloud models (GPT, Claude, Gemini, and more) when you need frontier reasoning or don't have a GPU. Either way, your data — conversations, memories, documents, and history — stays on your machine.

> **Local models are already amazing.** You'll be surprised what a 14B+ local model can do. If you start with cloud models today, and as local models get smarter and hardware gets cheaper, transition to fully local, fully private, fully free AI — seamlessly, with no changes to your setup.

> Governments are investing billions to keep AI infrastructure within their borders. Thoth applies the same principle to the individual — your compute, your data, your choice of model, **accountable to no one but you.**

> **🖥️ One-click install on Windows & macOS** — download, run, done. No terminal, no Docker, no config files. [Get it here.](https://github.com/siddsachar/Thoth/releases)

<table align="center">
  <tr>
    <td align="center"><a href="https://youtu.be/xYJC2IVKH7Y"><img src="https://img.youtube.com/vi/xYJC2IVKH7Y/mqdefault.jpg" width="360" alt="Demo 1 — Power User"><br><b>Demo 1 — Power User</b></a></td>
    <td align="center"><a href="https://youtu.be/zEma6vXKWH4"><img src="https://img.youtube.com/vi/zEma6vXKWH4/mqdefault.jpg" width="360" alt="Demo 2 — Small Business"><br><b>Demo 2 — Small Business</b></a></td>
  </tr>
  <tr>
    <td align="center"><a href="https://youtu.be/3vg1po9IQVg"><img src="https://img.youtube.com/vi/3vg1po9IQVg/mqdefault.jpg" width="360" alt="Demo 3 — Researcher"><br><b>Demo 3 — Researcher</b></a></td>
    <td align="center"><a href="https://youtu.be/dMoSay7uyoc"><img src="https://img.youtube.com/vi/dMoSay7uyoc/mqdefault.jpg" width="360" alt="Demo 4 — Developer"><br><b>Demo 4 — Developer</b></a></td>
  </tr>
</table>

### Why the name "Thoth"?

In ancient Egyptian mythology, **Thoth** (𓁟) was the god of wisdom, writing, and knowledge — the divine scribe who recorded all human understanding. Like its namesake, this tool is built to gather, organize, and faithfully retrieve knowledge — while keeping everything under your control.

---

## ✨ Features

### 🤖 ReAct Agent Architecture
- **Autonomous tool use** — the agent decides which tools to call, when, and how many times, based on your question
- **23 tools / 61 sub-tools** — web search, email, calendar, file management, shell access, browser automation, Telegram messaging, vision, memory, scheduled tasks, habit tracking, and more (see [full list below](#-tools-23-tools--61-sub-tools))
- **Streaming responses** — tokens stream in real-time with a typing indicator
- **Thinking indicators** — shows when the model is reasoning before responding
- **Smart context management** — automatic conversation summarization compresses older turns when token usage exceeds 80% of the context window, preserving the 5 most recent turns and a running summary; a hard trim at 85% drops oldest messages as a safety net; oversized tool outputs (e.g. large PDF reads) are proportionally shrunk so multi-tool chains fit within context; accurate token counting via tiktoken (cl100k_base)
- **Dynamic tool budgets** — the agent automatically adjusts how many tools are exposed to the model based on available context headroom; when context usage is high, lower-priority tools are temporarily hidden to prevent the system prompt from crowding out conversation history
- **Centralized prompts** — all LLM prompts (system prompt, extraction prompt, summarization prompt) managed in a single `prompts.py` module for easy tuning
- **Live token counter** — progress bar in the sidebar shows real-time context window usage based on trimmed (model-visible) history
- **Graceful stop & error recovery** — stop button cleanly halts generation with drain timeout; agent tool loops are caught automatically (50-step limit for chat, 100 for tasks) with a wind-down warning at 75% and 4× loop detection; orphaned tool calls are repaired; API errors are surfaced as persistent red toasts and saved to the conversation checkpoint so they survive thread refresh
- **Task cancellation** — running background tasks can be stopped from the chat header, activity panel, or task card; cancellation is checked between every LangGraph node for clean shutdown
- **Displaced tool-call auto-repair** — if context trimming displaces tool-call/response pairs, the agent automatically detects and repairs the ordering before the next LLM call; orphaned tool calls trigger an automatic retry
- **Date/time awareness** — current date and time is injected into every LLM call so the model always knows "today"
- **Destructive action confirmation** — dangerous operations (file deletion, sending emails, deleting calendar events, deleting memories, deleting tasks) require explicit user approval via an interrupt mechanism
- **Task-scoped background permissions** — background tasks use a tiered system: safe operations always run, low-risk operations (move file, move calendar, send email) are allowed with optional runtime guards, and irreversible operations (delete file, delete memory) are always blocked; shell commands and email recipients can be allowlisted per-task via the task editor UI

### 🧠 Long-Term Memory & Knowledge Graph
Thoth doesn't just store isolated facts — it builds a **personal knowledge graph**: a connected web of people, places, preferences, events, and their relationships. Every memory is an entity linked to others through typed relations, so the agent can reason about how things in your life connect.

- **Entity-relation model** — memories are stored as entities with a type, subject, description, aliases, and tags; entities are connected by typed directional relations (e.g. `Dad --[father_of]--> User`, `User --[lives_in]--> London`)
- **6 entity types** — `person`, `preference`, `fact`, `event`, `place`, `project`
- **Memory tool** — 7 sub-tools let the agent save, search, list, update, delete, **link**, and **explore** memories through natural conversation — *"Remember that my mom's birthday is March 15"*, *"What do you know about me?"*, *"How are these memories connected?"*
- **Link memories** — the agent can create relationships between any two entities — *"Link Mom to Mom's Birthday Party with relation has_event"* — building a richer graph over time
- **Explore connections** — the agent can traverse the graph outward from any entity, discovering chains of relationships — useful for broad questions like *"Tell me about my family"* or *"What do you know about my work?"*
- **Interactive memory visualization** — a dedicated **Memory tab** on the home screen renders the entire knowledge graph as an interactive network diagram: search bar, entity-type filters, clickable detail cards, full-graph / ego-graph toggle, and a fit-to-view button; color-coded by category, with relation types shown as edge labels
- **Graph-enhanced auto-recall** — before every response, the agent retrieves semantically relevant entities via FAISS and then expands one hop in the graph to surface connected neighbors; recalled memories include their relationship context (e.g. "connected via: Dad --> father_of --> User"); includes FAISS fallback search — if the primary semantic recall returns no results above 0.80 similarity, a broader relaxed search is attempted automatically
- **Auto-linking on save** — when a new memory is saved, the engine automatically scans existing entities for potential relationships and creates links, building the knowledge graph organically without manual intervention
- **Background orphan repair** — a periodic background process detects entities with zero relationships and attempts to link them to related entities, keeping the knowledge graph connected
- **Memory decay** — memories that haven't been recalled recently are gradually deprioritized, ensuring frequently relevant information surfaces first
- **Triple-based extraction** — the background extraction pipeline produces structured triples (entity + relation + entity) instead of flat facts; a "User" entity convention ensures the user is always a single canonical node with aliases for their names
- **Automatic memory extraction** — a background process scans past conversations on startup and every 6 hours, extracting entities and relations the agent missed during live conversation; active threads are excluded to avoid race conditions
- **Deterministic deduplication** — both live saves and background extraction check for existing entities by normalised subject before creating new entries; cross-category matching prevents fragmentation (e.g. a birthday stored as `person` won't be duplicated as `event`); alias resolution ensures "Mom" and "Mother" map to the same entity; richer content is always kept
- **Source tracking** — each entity is tagged with its origin (`live` from conversation or `extraction` from background scan) for diagnostics
- **Semantic recall** — FAISS vector index with Qwen3-Embedding-0.6B for similarity-based memory retrieval; relevant memories are automatically retrieved and injected into context before every LLM call based on semantic similarity to the current message
- **Memory IDs in context** — auto-recalled memories include their IDs so the agent can update or delete specific entries when the user corrects previously saved information
- **Consolidation** — a built-in `consolidate_duplicates()` utility merges near-duplicate memories that may have accumulated over time
- **Local SQLite + NetworkX + FAISS storage** — entities and relations stored in `~/.thoth/memory.db`, mirrored in a NetworkX graph for fast traversal, with FAISS vector index in `~/.thoth/memory_vectors/`; never sent to the cloud
- **Settings UI** — browse, search, and bulk-delete memories from the Memory tab in Settings; graph statistics (entity count, relations, connected components) displayed in the Knowledge Graph settings section

### 🤖 Brain Model & Cloud Models

The brain model is Thoth's default LLM — the model used for conversations, memory extraction, and any thread or task without a specific override. It can be a local Ollama model or an opt-in cloud model.

Thoth is built and tested for local models first. Every feature supports local models, and that will always be the priority. Local models are already amazing — tool calling, multi-step reasoning, memory extraction, and long conversations all work well with a 14B+ model. As local models improve and hardware requirements drop, the goal is to reduce any dependency on cloud models over time.

Some users don't have a dedicated GPU. Others need frontier-level reasoning (GPT, Claude, Gemini) for specific tasks, or want to try different models without downloading gigabytes. Thoth supports opt-in cloud models through **OpenAI** (direct API) and **OpenRouter** (100+ models from all major providers) for these cases — configured entirely from the Settings panel, no config files or terminal commands.

- **Dynamic model switching** — change the brain model from Settings; choose from 39 curated local models or any connected cloud model
- **Per-thread & per-task model override** — pick a different model for each conversation or each scheduled task; local and cloud models can be mixed freely across threads
- **Starred models** — star your favorite cloud models in Settings → Cloud; starred models appear in the chat header model picker alongside local models for quick access
- **Cost-efficient context management** — smart context trimming compresses older conversation turns, reducing token usage and API costs for cloud models; oversized tool outputs are proportionally shrunk to fit within context limits
- **39 curated local models** — Qwen, Llama, Mistral, Nemotron, and more — only models that support tool calling are included
- **Tool-support validation** — downloaded local models not in the curated list are flagged with a ⚠️ warning; selecting one triggers a live tool-call check and auto-reverts if the model can't use tools
- **Download buttons** — local models not yet downloaded show a Download button with live progress
- **Configurable context window** — 4K to 256K tokens via selector; if you choose a value that exceeds the model's native maximum, trimming and the token counter automatically use the model's actual limit
- **Local & cloud indicators** — local models show ✅ (downloaded) or ⬇️ (needs download); cloud models show ☁️

### 🎤 Voice Input & 🔊 Text-to-Speech
- **Toggle-based voice** — simple manual toggle to start/stop listening, no wake word needed
- **4-state pipeline** — stopped → listening → transcribing → muted, with clean state transitions
- **Local speech-to-text** — transcription via faster-whisper (tiny/base/small/medium models), CPU-only int8 quantization, no cloud APIs
- **Voice-aware responses** — voice input is tagged so the agent knows you're speaking and responds conversationally
- **Neural TTS** — high-quality text-to-speech via Kokoro TTS, fully offline
- **10 voice options** — US and British English, male and female variants
- **Streaming TTS** — responses are spoken sentence-by-sentence as they stream in
- **Mic gating** — microphone is automatically muted during TTS playback to prevent echo and feedback loops
- **Hands-free mode** — combine voice input + TTS for a fully conversational experience

### 🖥️ Shell Access
- **Full shell access** — the agent can run shell commands on your machine — install packages, manage git repos, run scripts, inspect processes, and automate system tasks through natural conversation
- **Persistent sessions** — `cd`, environment variables, and other state persists across commands within a conversation; each thread gets its own isolated shell session
- **3-tier safety classification** — every command is classified as *safe* (runs automatically), *moderate* (requires user confirmation), or *blocked* (rejected outright); safety rules are applied before execution
- **Safe commands run instantly** — `ls`, `pwd`, `cat`, `git status`, `pip list`, `echo`, and similar read-only commands execute without interruption
- **Dangerous commands require approval** — destructive or system-modifying commands (`rm`, `chmod`, `kill`, `pip install`, `brew`, `apt`) trigger the interrupt mechanism so you can accept or reject before execution
- **Blocked by default** — high-risk commands (`shutdown`, `reboot`, `mkfs`, `:(){ :|:& };:`) are rejected outright and never reach the shell
- **Background task permissions** — safe (read-only) commands always execute; moderate commands are blocked by default in background tasks but can be allowed per-task by configuring command prefix allowlists in the task editor; dangerous commands are always blocked
- **Inline terminal panel** — command output appears in a collapsible terminal panel in the chat UI with clear and history controls
- **History persistence** — command history is saved per-thread in `~/.thoth/shell_history.json` and reloaded when you revisit a conversation

### 🌐 Browser Automation
- **Full browser automation** — the agent can navigate websites, click elements, fill forms, scroll pages, and manage tabs in a real, visible Chromium window through natural conversation
- **Shared visible browser** — runs with `headless=False` so you can see what the agent is doing and intervene (e.g. type passwords, solve CAPTCHAs)
- **Persistent profile** — cookies, logins, and localStorage are stored in `~/.thoth/browser_profile/` and survive across restarts
- **Accessibility-tree snapshots** — after every action the tool captures the page's accessibility tree with numbered references (`[1]`, `[2]`, …) so the model can click/type by number
- **Smart snapshot filtering** — deduplicates links, drops hidden elements, and soft-caps at 100 interactive elements to stay within context limits
- **Browser snapshot compression** — older browser snapshots are automatically compressed to one-line stubs (URL + title) while keeping the last 2 in full, preventing context window overflow during long browsing sessions
- **7 sub-tools** — `browser_navigate`, `browser_click`, `browser_type`, `browser_scroll`, `browser_snapshot`, `browser_back`, `browser_tab`
- **Per-thread tab isolation** — each agent thread (interactive chat or background task) gets its own browser tab; tabs are cleaned up when a thread is deleted or a task completes; the agent never hijacks tabs belonging to other threads
- **Automatic browser detection** — detects installed Chrome, then Edge (Windows), then falls back to Playwright's bundled Chromium
- **Crash recovery** — if the browser is closed externally, the agent detects the disconnection, clears stale state, and automatically relaunches on the next browser action

### 👁️ Vision
- **Camera analysis** — capture and analyze images from your webcam in real-time
- **Screen capture** — take screenshots and ask questions about what's on your screen
- **Configurable vision model** — choose from popular vision models (gemma3, llava, etc.)
- **Camera selection** — pick which camera to use if you have multiple
- **Inline image display** — captured images are shown inline in the chat
- **Cloud vision models** — cloud models with vision capability (GPT, Claude, etc.) are auto-detected and work seamlessly alongside local vision models

### ⚡ Tasks & Scheduling
- **Unified task engine** — create named, multi-step tasks that run sequentially in a fresh thread, powered by APScheduler
- **7 schedule types** — `daily`, `weekly`, `weekdays`, `weekends`, `interval` (minutes), `cron` (full cron expression), `delay_minutes` (one-shot quick timer with notification)
- **Template variables** — use `{{date}}`, `{{day}}`, `{{time}}`, `{{month}}`, `{{year}}`, `{{task_id}}` in prompts — replaced at runtime; `{{task_id}}` lets prompts reference their own task for self-management (e.g. self-disable after a condition is met)
- **Channel delivery** — tasks can deliver their output to Telegram or Email after execution; per-task `delivery_channel` and `delivery_target` configuration
- **Per-task model override** — each task can specify a different LLM; the engine loads the override, runs the task, then restores the default
- **Prompt chaining** — each step sees the output of the previous step, enabling research → summarise → action pipelines
- **Always-background execution** — tasks always run in the background so you can keep chatting; the sidebar shows a ⏳ indicator while running
- **Background permissions** — background tasks use a tiered permission system: safe operations always run, low-risk operations (move file, send email) are allowed with optional per-task allowlists, and irreversible operations (file delete, memory delete) are always blocked; configure allowed shell command prefixes and email recipients per-task in the "🔒 Background permissions" section of the task editor
- **Pre-built templates** — ships with 5 starter tasks (Daily Briefing, Research Summary, Email Digest, Weekly Review, Quick Reminder)
- **Home screen dashboard** — manage tasks from the home screen with a tabbed layout: ⚡ Tasks (tiles with edit/run/delete) and 📋 Activity (monitoring panel with upcoming runs, recent history, channel status)
- **Persistent run history** — task execution history survives task deletion; displayed in the Activity tab with ✅/❌/⏳ status icons
- **Monitoring / polling** — use interval schedules with conditional prompts to monitor conditions (stock availability, price drops, new releases); the agent checks periodically, reports when the condition is met, and self-disables the task via `{{task_id}}` — no manual intervention needed
- **Task stop / cancel** — stop a running task from the chat header, activity panel, or task card; stopped tasks skip delivery and auto-delete, and are recorded in run history

### 📬 Messaging Channels
- **Telegram bot** — connect a Telegram bot via Bot API token; messages are processed by the full ReAct agent with all tools available; each chat gets its own conversation thread; supports interrupt-based approval for destructive actions (reply APPROVE/DENY); `/model` command to list and switch models (local or cloud); corrupt thread recovery with user-friendly messages; HTML-formatted responses
- **Telegram tool** — the agent can proactively send messages, photos, and documents to any Telegram chat via `send_telegram_message`, `send_telegram_photo`, and `send_telegram_document`
- **Email channel** — polls Gmail for unread emails with `[Thoth]` in the subject line (from your own address only); each Gmail thread gets its own agent conversation thread; replies inline; interrupt-based approval via email reply; corrupt thread recovery
- **Gmail attachments** — `send_gmail_message` and `create_gmail_draft` support file attachments; files are MIME-encoded automatically; workspace-relative paths are resolved
- **Auto-start** — channels can be set to start automatically when Thoth launches
- **Settings UI** — configure, start/stop, and manage channels from Settings → Channels tab

### 📋 Habit & Health Tracker
- **Conversational tracking** — log medications, symptoms, exercise, periods, mood, sleep, or any recurring activity through natural conversation — *"I took my Lexapro"*, *"Headache level 6"*, *"Period started"*
- **Auto-detect & confirm** — the agent recognises trackable events and asks *"Want me to log that?"* before writing, so nothing is recorded by accident
- **3 sub-tools** — `tracker_log` (structured input, auto-creates trackers), `tracker_query` (free-text read-only), `tracker_delete` (destructive, requires confirmation)
- **7 built-in analyses** — adherence rate, current/longest streaks, numeric stats (mean/min/max/σ), frequency, day-of-week distribution, cycle estimation (for period tracking), and co-occurrence between any two trackers
- **Trend analysis & charting** — query trends over any time window; results export to CSV automatically, then the agent chains to the Chart tool for interactive Plotly visualisations
- **Fully local** — all data stored in `~/.thoth/tracker/tracker.db` (SQLite); nothing leaves your machine
- **Smart memory separation** — tracker data is excluded from the memory system; logging a medication won't pollute the agent's long term memory

### 🖥️ Desktop App
- **Native window** — runs in a native OS window via pywebview instead of a browser, a real desktop application
- **Splash screen** — two-tier startup splash: tkinter GUI (dark background, gold Thoth logo, animated loading indicator) with automatic console fallback for environments where tkinter isn't available; self-closes when the server is ready
- **First-launch setup wizard** — on first install, a guided wizard offers two paths: **Local** (select and download Ollama models) or **Cloud** (enter an API key and pick a cloud model); vision model selection included for local setups
- **System tray** — `launcher.py` runs a pystray system tray icon showing app status (green = running, grey = stopped) with Open / Quit menu
- **Auto-restart** — if the native window is closed, re-opening from the tray relaunches it instantly

### 💬 Chat & Conversations
- **Multi-turn conversational Q&A** with full message history
- **Persistent conversation threads** stored in a local SQLite database via LangGraph checkpointer
- **Auto-naming** — threads are automatically named after the first question
- **Thread switching** — resume any previous conversation seamlessly
- **Thread deletion** — remove individual conversations or delete all at once with confirmation
- **Per-thread model switching** — pick a different model (local or cloud) for each conversation from the chat header dropdown; overrides persist across app restarts; cloud threads show a banner indicating the active provider
- **Conversation export** — export any thread as Markdown (.md), plain text (.txt), or PDF (.pdf)
- **File attachments** — attach images (analyzed via vision model), PDFs (text extracted), CSV, Excel, JSON, and text files directly in chat; structured data files return schema + stats + preview via pandas
- **Inline charts** — interactive Plotly charts rendered inline when the agent visualises data (zoom, hover, pan)
- **Inline YouTube embeds** — YouTube links in responses are rendered as playable embedded videos
- **Syntax-highlighted code blocks** — fenced code blocks render with language-aware highlighting and a built-in copy button
- **Onboarding guide** — first-run welcome message with tool overview and clickable example prompts; `👋` button in sidebar to re-show anytime
- **Startup health check** — verifies model availability on launch; skips Ollama check when using a cloud brain model

### 🔔 Notifications
- **Desktop notifications** — task completions and timer expirations trigger a desktop notification with timestamp
- **Sound effects** — distinct audio chimes for task completion (two-tone C5→E5) and timer alerts (5-beep A5), played asynchronously
- **In-app toasts** — toast messages appear in the UI with contextual emoji icons; success/info toasts auto-dismiss after 5 seconds, while error toasts (e.g. API errors) are persistent red banners with a close button
- **Unified system** — all notification channels (desktop, sound, toast) fire from a single `notify()` call with a `toast_type` parameter, keeping notification logic consistent across features

### 🧩 Bundled Skills

Skills are reusable instruction packs that shape how the agent thinks and responds. Each skill is a `SKILL.md` file with YAML frontmatter (display name, icon, description, required tools, tags) and freeform instructions injected into the system prompt when enabled. Thoth ships with 9 bundled skills — enable any combination from **⚙️ Settings → Skills**.

| Skill | Description |
|-------|-------------|
| **🧠 Brain Dump** | Capture unstructured thoughts and organize them into structured notes saved to memory |
| **☀️ Daily Briefing** | Compile a morning briefing with weather, calendar, and news headlines |
| **🔬 Deep Research** | Perform multi-source research on a topic and produce a structured report |
| **🗣️ Humanizer** | Write in a natural, human tone — no AI-speak, no filler, no corporate fluff |
| **📋 Meeting Notes** | Structure raw meeting notes into actionable minutes with follow-ups |
| **🎯 Proactive Agent** | Anticipate user needs, ask clarifying questions, and self-check work at milestones |
| **🪞 Self-Reflection** | Periodically review memory for contradictions, gaps, and stale information |
| **⚙️ Task Automation** | Design effective automated workflows using scheduled tasks, prompt chaining, and delivery channels |
| **🌐 Web Navigator** | Strategic patterns for effective browser automation — research, forms, and data extraction |

- **User skills** — create your own skills in `~/.thoth/skills/<name>/SKILL.md`; user skills with the same name as a bundled skill override it
- **In-app skill editor** — create and edit skills directly from Settings → Skills with a visual editor — set the name, icon, description, required tools, and write instructions without touching any files
- **Enable/disable per-skill** — toggle individual skills from Settings; only enabled skills are injected into the system prompt
- **Tool-aware** — each skill declares which tools it needs; the agent knows what capabilities are available for each skill
- **Versioned & tagged** — skills carry version numbers and tags for organization

---

## 🔧 Tools (23 Tools / 61 Sub-tools)

Thoth's agent has access to 23 tools that expose 61 individual operations to the model. Tools can be enabled/disabled from the Settings panel.

### Search & Knowledge

| Tool | Description | API Key? |
|------|-------------|----------|
| **🔍 Web Search** | Live web search via Tavily for current events, news, real-time data | `TAVILY_API_KEY` |
| **🦆 DuckDuckGo** | Free web search — no API key needed | None |
| **🌐 Wikipedia** | Encyclopedic knowledge with contextual compression | None |
| **📚 Arxiv** | Academic/scientific paper search | None |
| **▶️ YouTube** | Search videos + fetch full transcripts/captions | None |
| **🔗 URL Reader** | Fetch and extract text content from any URL | None |
| **📄 Documents** | Semantic search over your uploaded files (FAISS vector store) | None |

### Productivity

| Tool | Description | API Key? |
|------|-------------|----------|
| **📧 Gmail** | Search, read, draft, and send emails with file attachments (Google OAuth) | OAuth credentials |
| **📅 Google Calendar** | View, create, update, move, and delete events (Google OAuth) | OAuth credentials |
| **📁 Filesystem** | Sandboxed file operations — read, write, copy, move, delete within a workspace folder; reads PDF, CSV, Excel (.xlsx/.xls), JSON/JSONL, and TSV files; structured data files return schema + stats + preview via pandas; PDF export via `export_to_pdf` | None |
| **🖥️ Shell** | Execute shell commands with 3-tier safety (safe/moderate/blocked); persistent sessions per thread; user approval for destructive commands; inline terminal panel | None |
| **🌐 Browser** | Autonomous web browsing in a visible Chromium window — navigate, click, type, scroll, snapshot, back, tab management; accessibility-tree snapshots with numbered element references; persistent profile for logins | None |
| **📋 Tasks** | Create, list, update, delete, and run scheduled tasks — 7 trigger types (daily, weekly, weekdays, weekends, interval, cron, delay), channel delivery, per-task model override | None |
| **📋 Tracker** | Habit/health tracker — log meds, symptoms, exercise, periods; streak, adherence, trend analysis; CSV export | None |
| **📬 Telegram** | Send messages, photos, and documents to any Telegram chat via the configured bot | Bot API token |

### Computation & Analysis

| Tool | Description | API Key? |
|------|-------------|----------|
| **🧮 Calculator** | Safe math evaluation — arithmetic, trig, logs, factorials, combinatorics | None |
| **🔢 Wolfram Alpha** | Advanced computation, symbolic math, unit conversion, scientific data | `WOLFRAM_ALPHA_APPID` |
| **🌤️ Weather** | Current conditions and multi-day forecasts via Open-Meteo | None |
| **👁️ Vision** | Camera/screen capture and analysis via vision model | None |
| **🧠 Memory** | Save, search, update, delete, **link**, and **explore** memories in the knowledge graph | None |
| **🔍 Conversation Search** | Search past conversations by keyword or list all saved threads | None |
| **🖥️ System Info** | OS, CPU, RAM, disk space, IP addresses, battery, and top processes | None |
| **📊 Chart** | Interactive Plotly charts — bar, line, scatter, pie, histogram, box, area, heatmap from data files; PNG export via `save_to_file` | None |

### Safety & Permissions

- **Destructive operations require confirmation**: `workspace_file_delete`, `workspace_move_file`, `run_command` (moderate-risk), `send_gmail_message`, `move_calendar_event`, `delete_calendar_event`, `delete_memory`, `tracker_delete`, `task_delete`
- **Filesystem is sandboxed**: only the configured workspace folder is accessible (defaults to `~/Documents/Thoth`, auto-created on first use)
- **Shell commands are safety-classified**: safe (auto), moderate (confirm), blocked (rejected); high-risk commands like `shutdown`, `reboot`, `mkfs` are blocked outright; moderate commands in background tasks require per-task command prefix allowlists
- **Browser tabs are isolated per thread**: each chat or background task gets its own browser tab; the agent cannot access or interfere with tabs belonging to other threads; tabs are cleaned up on task completion or thread deletion
- **Background task permissions are configurable per-task**: shell command prefixes and email recipients can be allowlisted in the task editor; if no allowlist is configured, the operation fails with a user-friendly message
- **Gmail/Calendar operations are tiered**: read, compose/write, and destructive tiers can be toggled independently
- **Tools can be individually disabled** from Settings to reduce model decision complexity

---

## 🏗️ Architecture

```
┌──────────────────────────────────────────────────────────────────────┐
│                    NiceGUI Frontend (app_nicegui.py)                 │
│  ┌────────────┐  ┌──────────────────────┐  ┌───────────────────┐   │
│  │  Sidebar   │  │   Chat Interface     │  │   Settings Dialog │   │
│  │  Threads   │  │   Streaming Tokens   │  │   12 Tabs         │   │
│  │  Controls  │  │   Tool Status        │  │   Tool Config     │   │
│  │  Memory Tab│  │   Memory Graph View  │  │   Cloud Settings  │   │
│  └────────────┘  └──────────────────────┘  └───────────────────┘   │
└──────────────────────────┬───────────────────────────────────────────┘
                           │
                           ▼
┌──────────────────────────────────────────────────────────────────────┐
│               LangGraph ReAct Agent (agent.py)                       │
│                                                                      │
│   create_react_agent() with pre-model message trimming              │
│   System prompt with TOOL USE, MEMORY, and CITATION guidelines      │
│   Interrupt mechanism for destructive action confirmation            │
│   Graph-enhanced auto-recall (semantic + 1-hop expansion)           │
│   Per-thread model override (local or cloud)                        │
│                                                                      │
│   61 LangChain sub-tools from 23 registered tool modules            │
└───────┬──────────┬──────────┬──────────┬──────────┬─────────────────┘
        │          │          │          │          │
        ▼          ▼          ▼          ▼          ▼
  ┌──────────┐ ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐
  │   LLMs   │ │Knowledge│ │ SQLite │ │ FAISS  │ │External│
  │  Ollama  │ │ Graph  │ │Threads │ │ Vector │ │  APIs  │
  │ + Cloud  │ │(SQLite+│ │(local) │ │ Store  │ │(opt-in)│
  │ (opt-in) │ │NetworkX)│ │        │ │        │ │        │
  └──────────┘ └────────┘ └────────┘ └────────┘ └────────┘
```

### Why not just use ChatGPT?

| | ChatGPT / Claude / Gemini | Thoth |
|---|---|---|
| **Your data** | Stored on provider servers, subject to their privacy policies | Stays on your machine — always. With opt-in cloud models, only the current conversation is sent to the LLM provider; memories, files, and history never leave |
| **Conversations** | Owned by the provider — can be deleted, leaked, or used for training | Stored locally in SQLite, fully yours, exportable anytime |
| **Cost** | $20+/month per subscription | Free with local models. Cloud models use pay-per-token APIs — typically pennies per conversation with smart context trimming |
| **Memory** | Limited, opaque, provider-controlled | Personal knowledge graph — entities, relationships, visual explorer, fully yours |
| **Tools** | Sandboxed plugins, limited integrations | Direct access to your Gmail, Calendar, filesystem, shell, browser, webcam — 23 tools, 61 sub-operations |
| **Customisation** | Pick a model, write a system prompt | Swap models per conversation or per task, build scheduled tasks with cron/daily/weekly/interval triggers, mix local and cloud models freely |
| **Voice** | Cloud-processed speech | Local Whisper STT + Kokoro TTS — never leaves your mic |
| **Availability** | Requires internet, subject to outages & rate limits | Local models work offline; cloud models available when connected |

> **Bottom line:** Cloud AI assistants rent you access to someone else’s system. Thoth gives you **personal AI sovereignty** — run local models for full privacy, add cloud when you need it, and keep your data on your machine either way.

### Why not just use another open-source assistant?

Most open-source AI assistants are **developer tools disguised as products** — CLI-first, config-file-driven, Linux-only, and held together with Docker, YAML, and `.env` files. Getting them running means cloning repos, editing configs, wiring up databases, and debugging dependency conflicts before you can ask a single question.

**Thoth is different.** One-click installer, native desktop GUI, works out of the box on Windows and macOS, zero accounts required. Install it, launch it, start talking. No terminal expertise needed, no Docker, no YAML — just a private AI assistant that works.

### How is Thoth different from OpenClaw?

[OpenClaw](https://github.com/openclaw/openclaw) is a solid open-source project, but it targets a different audience and solves a different problem. OpenClaw is a **developer-oriented messaging infrastructure platform**: it routes LLM calls to 25+ chat surfaces like WhatsApp, Slack, and Discord. It supports both cloud and local models, but getting it running requires Node.js, Docker, YAML config files, and considerable developer expertise.

Thoth is a **desktop AI assistant for everyone**: one-click install, native GUI, everything configurable from the settings panel — no terminal, no config files, no Docker. Whether you use local or cloud models, all your data stays on your machine — only the LLM inference can optionally go to the cloud.

> **Pick Thoth** if you want a private, full-featured AI assistant with a polished desktop experience — local-first with optional cloud models, a personal knowledge graph, health tracking, and zero setup friction.
> **Pick OpenClaw** if you're a developer who wants to build a cloud-powered assistant that connects to every chat platform you already use.

| | OpenClaw | Thoth |
|---|---|---|
| **Target audience** | Developers comfortable with Node.js, Docker, and YAML | Everyone — one-click installer, native GUI, zero config files |
| **LLM execution** | Cloud or local (requires manual Docker/config setup) | Local via Ollama (default) or opt-in cloud (OpenAI, OpenRouter) — switchable from the GUI |
| **Data privacy** | Depends on your configuration | All data stays local — conversations, memories, files, history. Only LLM calls touch the cloud when using cloud models |
| **Setup** | Node.js + Docker + YAML + channel config + API keys | One-click installer (Windows/macOS); cloud setup needs just an API key |
| **Ongoing cost** | Free software, but typically requires paid API keys | Free with local models; cloud models billed per-token (pennies per conversation with smart trimming) |
| **Offline capability** | Requires configuration for local LLMs | Local models work fully offline out of the box |
| **Long-term memory** | Session compaction + pruning | Personal knowledge graph — entities, relations, visual explorer, semantic search, auto-extraction |
| **Health & Habit Tracking** | ❌ None | Conversational tracker for meds, symptoms, exercise, periods — streaks, adherence, and trend analysis |
| **Voice** | ElevenLabs (cloud TTS), wake words on Apple devices | Local Whisper STT + Kokoro TTS — fully offline, 10 voices |
| **Tools** | Browser automation, Canvas, Skills platform | 23 tools / 61 sub-ops — Gmail, Calendar, filesystem, shell, browser, vision, habit tracker, charts, Wolfram, and more |
| **Desktop experience** | macOS menu bar app, WebChat | Native desktop window with system tray, splash screen, dark mode UI |
| **Tasks** | Cron jobs + webhooks | Named tasks with 7 schedule types, stop/cancel, channel delivery, per-task model override, and template variables |
| **Platforms** | macOS (primary), Linux, Windows via WSL2 only | Windows & macOS |


### Core Modules

| File | Purpose |
|------|---------|
| **`app_nicegui.py`** | NiceGUI UI — chat interface, sidebar thread manager with live token counter, Settings dialog (12 tabs including Cloud), tabbed home screen (Tasks + Activity + Memory graph), Task Edit dialog, file attachment handling, streaming event loop with error recovery, export, voice bar, first-launch setup wizard (Local/Cloud paths), per-thread model picker, task stop buttons, inline terminal panel, interactive knowledge graph visualization (vis-network), centralized logging configuration |
| **`agent.py`** | LangGraph ReAct agent — system prompt, automatic conversation summarization, pre-model context trimming with proportional tool-output shrinking, streaming event generator, interrupt handling for destructive actions, live token usage reporting, graph-enhanced auto-recall with memory IDs and relation context, model override propagation via ContextVar, configurable retrieval compression (Smart/Deep/Off), task cancellation via stop_event, displaced tool-call auto-repair |
| **`threads.py`** | SQLite-backed thread metadata and `SqliteSaver` checkpointer for persisting LangGraph conversation state |
| **`memory.py`** | Backward-compatible memory wrapper — delegates all operations to `knowledge_graph.py`, mapping legacy column names (`category`/`content` to `entity_type`/`description`); provides `save_memory`, `find_by_subject`, `update_memory`, `delete_memory`, `semantic_search`, and `count_memories` with unchanged signatures |
| **`knowledge_graph.py`** | Personal knowledge graph engine — SQLite entity + relation tables (WAL mode), NetworkX DiGraph for traversal, FAISS vector index for semantic search; entity CRUD with alias resolution, relation CRUD with cascade delete, `graph_enhanced_recall()` for semantic + graph expansion, `graph_to_vis_json()` for visualization; deterministic dedup via normalized subject matching |
| **`models.py`** | Ollama + cloud model management — local model listing/downloading/switching, cloud provider support (OpenAI, OpenRouter), starred models, context-size catalog with heuristics, model override routing, cloud vision detection |
| **`documents.py`** | Document ingestion — PDF/DOCX/TXT loading, chunking, FAISS embedding and storage |
| **`voice.py`** | Local STT pipeline — toggle-based 4-state machine (stopped/listening/transcribing/muted) with faster-whisper CPU-only int8 transcription |
| **`tts.py`** | Kokoro TTS integration — cross-platform neural TTS, model auto-downloaded on first use (~169 MB), 10 built-in voices, streaming sentence-by-sentence playback |
| **`vision.py`** | Camera/screen capture via OpenCV/MSS, image analysis via local or cloud vision models |
| **`data_reader.py`** | Shared pandas-based reader for CSV, TSV, Excel, JSON, JSONL — returns schema + stats + preview rows |
| **`launcher.py`** | Desktop launcher — system tray (pystray), native window management (pywebview), two-tier splash screen (tkinter with console fallback), manages NiceGUI server lifecycle; structured logging to `~/.thoth/thoth_app.log` |
| **`api_keys.py`** | API key management — tool keys from `~/.thoth/api_keys.json`, cloud LLM provider keys and starred models from `~/.thoth/cloud_config.json` |
| **`prompts.py`** | Centralized LLM prompts — system prompt (with BUILDING CONNECTIONS, EXPLORING CONNECTIONS, and BACKGROUND TASK PERMISSIONS sections), extraction prompt (triple-based with User entity convention and relation taxonomy), summarization prompt; memory guidelines with dedup and update instructions |
| **`memory_extraction.py`** | Background memory extraction — scans past conversations via LLM, extracts entities and relations as structured triples, two-pass dedup (entities with alias merging, then relations with subject-to-ID resolution), User entity pre-population, excludes active threads, runs on startup + every 6 hours |
| **`skills.py`** | Skills engine — discovers, loads, and caches bundled and user skill definitions from `SKILL.md` files with YAML frontmatter; builds prompt text for enabled skills injected into the system prompt; config persistence in `~/.thoth/skills_config.json` |
| **`bundled_skills/`** | 9 built-in skill packages (Brain Dump, Daily Briefing, Deep Research, Humanizer, Meeting Notes, Proactive Agent, Self-Reflection, Task Automation, Web Navigator) — each a directory containing a `SKILL.md` instruction file |
| **`tasks.py`** | Task engine — SQLite CRUD, APScheduler integration, 7 schedule types, template variable expansion, sequential prompt execution, background runner with threading, channel delivery (Telegram/Email), per-task model override, run history persistence, task stop/cancel, auto-migration from workflows.db, 5 default templates, per-task `allowed_commands` and `allowed_recipients` permission fields |
| **`notifications.py`** | Unified notification system — desktop notifications (plyer), sound effects, and in-app toast queue with `toast_type` support (positive/negative); error toasts render as persistent red banners; coordinates task completion chimes and timer alerts |
| **`channels/`** | Messaging channel adapters — Telegram bot (long polling, interrupt approval, corrupt thread recovery, HTML formatting) and Email channel (Gmail polling, interrupt approval, corrupt thread recovery, sender-only filter), with shared config store |
| **`tools/`** | 23 self-registering tool modules + base class + registry |
| **`static/`** | Bundled JS libraries — `vis-network.min.js` for knowledge graph visualization |

### Data Storage

All user data is stored in `~/.thoth/` (`%USERPROFILE%\.thoth\` on Windows):

```
~/.thoth/
├── threads.db              # Conversation history & LangGraph checkpoints
├── memory.db               # Knowledge graph — entities, relations, and memory data
├── memory_vectors/         # FAISS vector index for semantic memory search
├── memory_extraction_state.json  # Tracks last extraction run timestamp
├── api_keys.json           # API keys (Tavily, Wolfram, etc.)
├── cloud_config.json         # Cloud LLM provider keys and starred models
├── app_config.json         # Onboarding / first-run state
├── tools_config.json       # Tool enable/disable state & config
├── model_settings.json     # Selected model & context size
├── tts_settings.json       # Selected TTS voice
├── vision_settings.json    # Vision model & camera selection
├── voice_settings.json     # Whisper model size preference
├── processed_files.json    # Tracks indexed documents
├── tasks.db                # Task definitions, schedules, run history & delivery config
├── channels_config.json    # Channel settings (Telegram, Email auto-start)
├── shell_history.json      # Shell command history per thread
├── skills_config.json      # Skill enable/disable state
├── thoth_app.log           # Application log (structured, timestamped)
├── splash.log              # Splash screen diagnostic log
├── tracker/
│   ├── tracker.db          # Habit/health tracker data (trackers + entries)
│   └── exports/            # CSV exports from trend analysis queries
├── vector_store/           # FAISS index for uploaded documents
├── gmail/                  # Gmail OAuth tokens
├── calendar/               # Calendar OAuth tokens
├── browser_profile/        # Playwright persistent browser profile (cookies, logins, localStorage)
├── browser_history.json    # Browser browsing history
└── kokoro/                 # Kokoro TTS model & voice data
```

> Override the data directory by setting the `THOTH_DATA_DIR` environment variable.

---

## 💻 System Requirements

### For Local Models (Ollama)

| | Minimum | Recommended |
|--|---------|-------------|
| **OS** | Windows 10/11 (64-bit) or macOS 12+ (Apple Silicon & Intel) | Same |
| **Python** | 3.11+ | 3.11+ |
| **RAM** | 8 GB (for 8B models) | 16–32 GB (for 14B–30B models) |
| **GPU** | Not required — Ollama runs on CPU | NVIDIA 8+ GB VRAM (CUDA) or Apple Silicon — dramatically faster |
| **Disk** | ~5 GB (app + one small model like `qwen3:8b`) | 20+ GB for multiple or larger models |
| **Internet** | Required for install and model download; optional at runtime | Same |

> **Note:** The default local model (`qwen3:14b`, ~9 GB) runs well on CPU with 16 GB RAM, but a GPU makes responses significantly faster. Smaller models like `qwen3:8b` (~5 GB) work on 8 GB RAM machines. You'll be surprised what a 14B+ local model can do.

### For Cloud Models Only (No Local GPU Needed)

If you don't plan to run local models, Thoth's requirements drop significantly:

| Requirement | Details |
|-------------|---------|
| **OS** | Windows 10/11 (64-bit) or macOS 12+ (Apple Silicon & Intel) |
| **Python** | 3.11+ |
| **RAM** | 4 GB |
| **Disk** | ~1 GB (app + packages, no model downloads) |
| **GPU** | Not needed |
| **Internet** | Required (LLM inference happens on the provider's servers) |

> You still need an API key from [OpenAI](https://platform.openai.com/) or [OpenRouter](https://openrouter.ai/). Cloud models are billed per-token by the provider — typically pennies per conversation.

---

## 📥 One-Click Install

### Windows

1. Download **[ThothSetup_3.8.0.exe](https://github.com/siddsachar/Thoth/releases/latest)** from the latest release
2. Run the installer — it installs Python, Ollama, and all dependencies automatically
3. Launch **Thoth** from the Start Menu or Desktop shortcut

### macOS

1. Download **[Thoth-3.8.0-macOS.zip](https://github.com/siddsachar/Thoth/releases/latest)** from the latest release
2. Unzip the file — this creates a `Thoth` folder
3. Open the `Thoth` folder and double-click **`Start Thoth.command`**
   - If macOS blocks it: right-click → **Open** → click **Open** in the dialog
   - First run installs Homebrew (if needed), Python, Ollama, and all dependencies automatically
   - Subsequent launches skip installation and start in ~3 seconds
4. *(Optional)* Drag the included **Thoth.app** to `/Applications` for Dock/Launchpad access

> **Works on Apple Silicon (M1/M2/M3/M4) and Intel Macs** (macOS 12+). No terminal, no manual setup — just double-click and go.

> **Using cloud models only?** The installer still sets up Ollama by default, but you can skip model downloads. On first launch, choose the **Cloud** setup path, enter your API key, and start chatting — no GPU required.

---

## 📦 Installation (From Source)

> **Prefer a manual install?** A few commands from source:

1. **Install [Ollama](https://ollama.com/)** *(required for local models — skip if using cloud models only)*

2. **Clone the repository**
   ```bash
   git clone https://github.com/siddsachar/Thoth.git
   cd Thoth
   ```

3. **Create and activate a virtual environment**
   ```bash
   python -m venv .venv
   # Windows
   .venv\Scripts\activate
   # macOS / Linux
   source .venv/bin/activate
   ```

4. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

5. **Start Ollama** *(if using local models)*
   ```bash
   ollama serve
   ```

6. **Launch Thoth**
   ```bash
   python launcher.py
   ```
   This starts the system tray icon and opens the app at `http://localhost:8080`.

   Alternatively, run directly without the tray:
   ```bash
   python app_nicegui.py
   ```

> **First launch:** A setup wizard lets you choose between **Local** (Ollama) and **Cloud** (API key) setup paths. For local, the default brain model (`qwen3:14b`, ~9 GB) is recommended. For cloud, enter your OpenAI or OpenRouter API key and pick a default model.

---

## 🔑 API Key Setup (Optional)

Most tools work without any API keys. For cloud models and enhanced functionality:

### Cloud LLM Providers

| Service | Key | Purpose | How to Get |
|---------|-----|---------|------------|
| **OpenAI** | `OPENAI_API_KEY` | GPT and other OpenAI models | [platform.openai.com](https://platform.openai.com/) |
| **OpenRouter** | `OPENROUTER_API_KEY` | 100+ models from all major providers (Claude, Gemini, Llama, etc.) | [openrouter.ai](https://openrouter.ai/) |

Configure cloud keys in **⚙️ Settings → ☁️ Cloud** tab. Keys are stored locally in `~/.thoth/cloud_config.json` — never sent to Thoth’s servers (there are none).

### Tool API Keys

| Service | Key | Purpose | How to Get |
|---------|-----|---------|------------|
| **Tavily** | `TAVILY_API_KEY` | Web search (1,000 free searches/month) | [app.tavily.com](https://app.tavily.com/) |
| **Wolfram Alpha** | `WOLFRAM_ALPHA_APPID` | Advanced computation & scientific data | [developer.wolframalpha.com](https://developer.wolframalpha.com/) |

Configure tool keys in **⚙️ Settings → 🔍 Search** tab. Keys are saved locally to `~/.thoth/api_keys.json`.

For **Gmail** and **Google Calendar**, you'll need a Google Cloud OAuth `credentials.json` — setup instructions are provided in the respective Settings tabs.

---

## 🚀 Quick Start

### Local Models (Default)

1. **Launch Thoth** and wait for the default model to download (first time only)
2. **Click "＋ New conversation"** in the sidebar
3. **Ask anything** — the agent will automatically choose which tools to use:
   - *"What's the weather in Tokyo?"* → uses Weather tool
   - *"Search for recent papers on transformer architectures"* → uses Arxiv
   - *"Remember that my mom's birthday is March 15"* → saves to Memory
   - *"Read the file report.pdf in my workspace"* → uses Filesystem
   - *"Run git status on my project"* → uses Shell (safe, auto-executes)
   - *"Install pandas with pip"* → uses Shell (moderate, asks for approval)
   - *"What's on my screen right now?"* → uses Vision (screen capture)
   - *"I took my Lexapro"* → asks to log, then saves to Tracker
   - *"Show my headache trends this month"* → uses Tracker + Chart
   - *"Remind me to call the dentist tomorrow at 9am"* → uses Tasks with scheduling
   - *"What did I ask about taxes last week?"* → uses Conversation Search
4. **Open ⚙️ Settings** to configure models, enable/disable tools, and set up integrations

### Cloud Models (No GPU? Start Here)

1. **Launch Thoth** → on the setup wizard, choose **☁️ Cloud**
2. **Enter your API key** (OpenAI or OpenRouter) → Thoth validates and fetches available models
3. **Pick a default model** (e.g. GPT) and start chatting — no downloads, no GPU needed
4. Switch models per conversation anytime from the chat header dropdown

---

## 🔒 Privacy & Security — Personal AI Sovereignty

### With Local Models (Default)

- **All LLM inference runs on your machine** via Ollama — nothing sent to any cloud provider
- **Documents, memories, and conversations are stored locally** in `~/.thoth/`
- **External network calls** are only made when you use online tools (web search, Wikipedia, Arxiv, Gmail, Calendar, Weather) — and each can be individually disabled
- **No telemetry, no tracking, no cloud dependencies** for core functionality

### With Opt-In Cloud Models

- **Only the current conversation is sent to the LLM provider** (OpenAI or OpenRouter) — your memories, knowledge graph, documents, files, and other conversations never leave your machine
- **Your API key connects directly to the provider** over HTTPS — Thoth has no servers, no accounts, and no middleman between you and the API
- **All data is still stored locally** — conversations, memories, files, and history remain in `~/.thoth/` regardless of which model you use
- **No telemetry from Thoth** in either mode — local or cloud

### Always

- **API keys are stored locally** in `~/.thoth/` and only transmitted to their respective services
- **No Thoth account required** — there is no sign-up, no login, no server to phone home to
- **Tools can be individually disabled** from Settings to control exactly what the agent can access

---

## 📄 License

MIT License — see [LICENSE](LICENSE) for details.

---

## 🙏 Acknowledgements

Built with [NiceGUI](https://nicegui.io/), [LangGraph](https://langchain-ai.github.io/langgraph/), [LangChain](https://python.langchain.com/), [Ollama](https://ollama.com/), [FAISS](https://github.com/facebookresearch/faiss), [Kokoro TTS](https://github.com/thewh1teagle/kokoro-onnx), [faster-whisper](https://github.com/SYSTRAN/faster-whisper), [HuggingFace](https://huggingface.co/), and [tiktoken](https://github.com/openai/tiktoken).
