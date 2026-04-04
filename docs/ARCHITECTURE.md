# 𓁟 Thoth — Architecture & Detailed Design

> Full technical reference for every feature, module, and subsystem in Thoth.
> For a concise overview, see the [README](../README.md).

---

## Table of Contents

- [ReAct Agent Architecture](#react-agent-architecture)
- [Long-Term Memory & Knowledge Graph](#long-term-memory--knowledge-graph)
- [Wiki Vault](#wiki-vault)
- [Dream Cycle](#dream-cycle)
- [Document Knowledge Extraction](#document-knowledge-extraction)
- [Brain Model & Cloud Models](#brain-model--cloud-models)
- [Voice Input & Text-to-Speech](#voice-input--text-to-speech)
- [Shell Access](#shell-access)
- [Browser Automation](#browser-automation)
- [Vision](#vision)
- [Tasks & Scheduling](#tasks--scheduling)
- [Messaging Channels](#messaging-channels)
- [Habit & Health Tracker](#habit--health-tracker)
- [Desktop App](#desktop-app)
- [Chat & Conversations](#chat--conversations)
- [Notifications](#notifications)
- [Bundled Skills](#bundled-skills)
- [Core Modules](#core-modules)
- [Data Storage](#data-storage)
- [Comparison with Other Tools](#comparison-with-other-tools)

---

## ReAct Agent Architecture

- **Autonomous tool use** — the agent decides which tools to call, when, and how many times, based on your question
- **24 tools / 67 sub-tools** — web search, email, calendar, file management, shell access, browser automation, Telegram messaging, vision, memory, scheduled tasks, habit tracking, and more (see [Tools](#tools))
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

---

## Long-Term Memory & Knowledge Graph

Thoth doesn't just store isolated facts — it builds a **personal knowledge graph**: a connected web of people, places, preferences, events, and their relationships. Every memory is an entity linked to others through typed relations, so the agent can reason about how things in your life connect.

- **Entity-relation model** — memories are stored as entities with a type, subject, description, aliases, and tags; entities are connected by typed directional relations (e.g. `Dad --[father_of]--> User`, `User --[lives_in]--> London`)
- **10 entity types** — `person`, `preference`, `fact`, `event`, `place`, `project`, `organisation`, `concept`, `skill`, `media`
- **Memory tool** — 7 sub-tools let the agent save, search, list, update, delete, **link**, and **explore** memories through natural conversation — *"Remember that my mom's birthday is March 15"*, *"What do you know about me?"*, *"How are these memories connected?"*
- **Link memories** — the agent can create relationships between any two entities — *"Link Mom to Mom's Birthday Party with relation has_event"* — building a richer graph over time
- **Explore connections** — the agent can traverse the graph outward from any entity, discovering chains of relationships — useful for broad questions like *"Tell me about my family"* or *"What do you know about my work?"*
- **Interactive memory visualization** — a dedicated **Knowledge tab** on the home screen renders the entire knowledge graph as an interactive network diagram: search bar, entity-type filters, clickable detail cards, full-graph / ego-graph toggle, and a fit-to-view button; color-coded by category, with relation types shown as edge labels
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
- **Settings UI** — browse, search, and bulk-delete memories from the Knowledge tab in Settings; graph statistics (entity count, relations, connected components) displayed in the Knowledge Graph settings section

---

## Wiki Vault

The knowledge graph can be exported as a structured **Obsidian-compatible markdown vault** — one `.md` file per entity with YAML frontmatter, `[[wiki-links]]`, and auto-generated indexes.

- **Vault structure** — entities grouped by type (`wiki/person/`, `wiki/project/`, `wiki/event/`, etc.) with one `.md` file per entity; sparse entities (<20 chars) roll up into `_index.md` per type; per-type indexes and a master `index.md` auto-generated on rebuild
- **YAML frontmatter** — each article includes `id`, `type`, `subject`, `aliases`, `tags`, `source`, `created`, `updated` metadata
- **Wiki-links** — related entities linked via `[[Entity Name]]` syntax, enabling Obsidian backlinks and graph view
- **Connections section** — outgoing and incoming relations listed with arrow notation
- **Live export** — entities are exported on save (≥20 chars), deleted on entity removal, and rebuilt on batch operations
- **Search** — full-text search across all `.md` files with title, snippet, and entity ID results
- **Conversation export** — any thread can be exported as a vault-compatible markdown file
- **Agent tool** — 5 sub-tools (`wiki_search`, `wiki_read`, `wiki_rebuild`, `wiki_stats`, `wiki_export_conversation`) let the agent interact with the vault directly
- **Settings UI** — enable/disable toggle, vault path configuration with Browse button, stats display, rebuild and open-folder buttons in the Knowledge tab

---

## Dream Cycle

A background daemon that refines the knowledge graph during idle hours, running three non-destructive operations with a three-layer anti-contamination system.

- **Duplicate merge** — entities with ≥0.93 semantic similarity and same type are merged; LLM synthesizes the best description, aliases are unioned, relations re-pointed to the survivor
- **Subject-name guard** — entities with different normalized subjects require ≥0.98 similarity to merge, preventing false merges of distinct people/concepts
- **Description enrichment** — thin entities (<80 chars) appearing in 2+ conversations get richer descriptions from conversation context and relationship graph
- **Relationship inference** — co-occurring entity pairs with no existing edge are evaluated for a meaningful connection (tagged `source="dream_infer"`)
- **Three-layer anti-contamination** — (1) sentence-level excerpt filtering extracts only sentences mentioning the target entity, (2) deterministic post-enrichment cross-entity validation scans LLM output for unrelated entity subjects and rejects contaminated results before DB write, (3) strengthened prompt with concrete negative examples and subject-name substitution
- **Configurable window** — default 1–5 AM local time; checks every 30 minutes if conditions met (enabled, in window, idle, not yet run today)
- **Dream journal** — all operations logged to `~/.thoth/dream_journal.json` with cycle ID, summary, and duration; viewable in the Activity tab
- **Settings UI** — enable/disable toggle, window display, and last run summary in the Knowledge tab
- **Status pill** — dedicated health-check pill shows enabled state and last run time

---

## Document Knowledge Extraction

Uploaded documents are processed through a three-phase **map-reduce LLM pipeline** that extracts structured knowledge into the graph with full source provenance.

- **Map phase** — document split into ~6K-char windows; each window summarized to 3–5 sentences
- **Reduce phase** — window summaries combined into a coherent 300–600 word article
- **Extract phase** — core entities and relations pulled from the final article; 3–8 entities per document
- **Hub entity** — the document itself is saved as a `media` entity; extracted entities linked via `extracted_from` relation for provenance tracking
- **Cross-window dedup** — entities with the same subject across windows are merged before saving
- **New file formats** — supports PDF, DOCX, TXT, Markdown (`.md`), HTML, and EPUB
- **Live progress** — status bar shows pulsing progress pill with phase indicator, progress bar, queue count, and stop button (updates every 2 seconds)
- **Background queue** — documents queued for processing; worker thread handles one at a time
- **Per-document cleanup** — individual document delete button removes vector store entries and all extracted entities with matching source tag; bulk "Clear all documents" removes everything with `document:*` prefix

---

## Brain Model & Cloud Models

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
- **Configurable context window** — 16K to 256K tokens via selector; if you choose a value that exceeds the model's native maximum, trimming and the token counter automatically use the model's actual limit
- **Local & cloud indicators** — local models show ✅ (downloaded) or ⬇️ (needs download); cloud models show ☁️

---

## Voice Input & Text-to-Speech

- **Toggle-based voice** — simple manual toggle to start/stop listening, no wake word needed
- **4-state pipeline** — stopped → listening → transcribing → muted, with clean state transitions
- **Local speech-to-text** — transcription via faster-whisper (tiny/base/small/medium models), CPU-only int8 quantization, no cloud APIs
- **Voice-aware responses** — voice input is tagged so the agent knows you're speaking and responds conversationally
- **Neural TTS** — high-quality text-to-speech via Kokoro TTS, fully offline
- **10 voice options** — US and British English, male and female variants
- **Streaming TTS** — responses are spoken sentence-by-sentence as they stream in
- **Mic gating** — microphone is automatically muted during TTS playback to prevent echo and feedback loops
- **Hands-free mode** — combine voice input + TTS for a fully conversational experience

---

## Shell Access

- **Full shell access** — the agent can run shell commands on your machine — install packages, manage git repos, run scripts, inspect processes, and automate system tasks through natural conversation
- **Persistent sessions** — `cd`, environment variables, and other state persists across commands within a conversation; each thread gets its own isolated shell session
- **3-tier safety classification** — every command is classified as *safe* (runs automatically), *moderate* (requires user confirmation), or *blocked* (rejected outright); safety rules are applied before execution
- **Safe commands run instantly** — `ls`, `pwd`, `cat`, `git status`, `pip list`, `echo`, and similar read-only commands execute without interruption
- **Dangerous commands require approval** — destructive or system-modifying commands (`rm`, `chmod`, `kill`, `pip install`, `brew`, `apt`) trigger the interrupt mechanism so you can accept or reject before execution
- **Blocked by default** — high-risk commands (`shutdown`, `reboot`, `mkfs`, `:(){ :|:& };:`) are rejected outright and never reach the shell
- **Background task permissions** — safe (read-only) commands always execute; moderate commands are blocked by default in background tasks but can be allowed per-task by configuring command prefix allowlists in the task editor; dangerous commands are always blocked
- **Inline terminal panel** — command output appears in a collapsible terminal panel in the chat UI with clear and history controls
- **History persistence** — command history is saved per-thread in `~/.thoth/shell_history.json` and reloaded when you revisit a conversation

---

## Browser Automation

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

---

## Vision

- **Camera analysis** — capture and analyze images from your webcam in real-time
- **Screen capture** — take screenshots and ask questions about what's on your screen
- **Image file analysis** — analyze image files in the workspace by path without needing a camera or screen capture
- **Configurable vision model** — choose from popular vision models (gemma3, llava, etc.)
- **Camera selection** — pick which camera to use if you have multiple
- **Inline image display** — captured and workspace images are shown inline in the chat
- **Cloud vision models** — cloud models with vision capability (GPT, Claude, etc.) are auto-detected and work seamlessly alongside local vision models

---

## Tasks & Scheduling

- **Unified task engine** — create named, multi-step tasks that run sequentially in a fresh thread, powered by APScheduler
- **7 schedule types** — `daily`, `weekly`, `weekdays`, `weekends`, `interval` (minutes), `cron` (full cron expression), `delay_minutes` (one-shot quick timer with notification)
- **Template variables** — use `{{date}}`, `{{day}}`, `{{time}}`, `{{month}}`, `{{year}}`, `{{task_id}}` in prompts — replaced at runtime; `{{task_id}}` lets prompts reference their own task for self-management (e.g. self-disable after a condition is met)
- **Channel delivery** — tasks can deliver their output to Telegram or Email after execution; per-task `delivery_channel` and `delivery_target` configuration
- **Per-task model override** — each task can specify a different LLM; the engine loads the override, runs the task, then restores the default
- **Prompt chaining** — each step sees the output of the previous step, enabling research → summarise → action pipelines
- **Always-background execution** — tasks always run in the background so you can keep chatting; the sidebar shows a ⏳ indicator while running
- **Background permissions** — background tasks use a tiered permission system: safe operations always run, low-risk operations (move file, send email) are allowed with optional per-task allowlists, and irreversible operations (file delete, memory delete) are always blocked; configure allowed shell command prefixes and email recipients per-task in the "🔒 Background permissions" section of the task editor
- **Pre-built templates** — ships with 5 starter tasks (Daily Briefing, Research Summary, Email Digest, Weekly Review, Quick Reminder)
- **Home screen dashboard** — manage tasks from the home screen with a tabbed layout: ⚡ Tasks (tiles with edit/run/delete) and 📋 Activity (monitoring panel with upcoming runs, recent history, channel status); the home screen’s status monitor panel shows 17 health-check pills at a glance with a diagnosis button
- **Persistent run history** — task execution history survives task deletion; displayed in the Activity tab with ✅/❌/⏳ status icons
- **Monitoring / polling** — use interval schedules with conditional prompts to monitor conditions (stock availability, price drops, new releases); the agent checks periodically, reports when the condition is met, and self-disables the task via `{{task_id}}` — no manual intervention needed
- **Task stop / cancel** — stop a running task from the chat header, activity panel, or task card; stopped tasks skip delivery and auto-delete, and are recorded in run history

---

## Messaging Channels

- **Telegram bot** — connect a Telegram bot via Bot API token; messages are processed by the full ReAct agent with all tools available; each chat gets its own conversation thread; supports interrupt-based approval for destructive actions (reply APPROVE/DENY); `/model` command to list and switch models (local or cloud); corrupt thread recovery with user-friendly messages; HTML-formatted responses
- **Telegram tool** — the agent can proactively send messages, photos, and documents to any Telegram chat via `send_telegram_message`, `send_telegram_photo`, and `send_telegram_document`
- **Email channel** — polls Gmail for unread emails with `[Thoth]` in the subject line (from your own address only); each Gmail thread gets its own agent conversation thread; replies inline; interrupt-based approval via email reply; corrupt thread recovery
- **Gmail attachments** — `send_gmail_message` and `create_gmail_draft` support file attachments; files are MIME-encoded automatically; workspace-relative paths are resolved
- **Auto-start** — channels can be set to start automatically when Thoth launches
- **Settings UI** — configure, start/stop, and manage channels from Settings → Channels tab

---

## Habit & Health Tracker

- **Conversational tracking** — log medications, symptoms, exercise, periods, mood, sleep, or any recurring activity through natural conversation — *"I took my Lexapro"*, *"Headache level 6"*, *"Period started"*
- **Auto-detect & confirm** — the agent recognises trackable events and asks *"Want me to log that?"* before writing, so nothing is recorded by accident
- **3 sub-tools** — `tracker_log` (structured input, auto-creates trackers), `tracker_query` (free-text read-only), `tracker_delete` (destructive, requires confirmation)
- **7 built-in analyses** — adherence rate, current/longest streaks, numeric stats (mean/min/max/σ), frequency, day-of-week distribution, cycle estimation (for period tracking), and co-occurrence between any two trackers
- **Trend analysis & charting** — query trends over any time window; results export to CSV automatically, then the agent chains to the Chart tool for interactive Plotly visualisations
- **Fully local** — all data stored in `~/.thoth/tracker/tracker.db` (SQLite); nothing leaves your machine
- **Smart memory separation** — tracker data is excluded from the memory system; logging a medication won't pollute the agent's long term memory

---

## Desktop App

- **Native window** — runs in a native OS window via pywebview instead of a browser, a real desktop application
- **Right-click context menu** — Cut, Copy, Paste, and Select All in the native desktop window (pywebview), since the default webview suppresses the browser context menu
- **Splash screen** — two-tier startup splash: tkinter GUI (dark background, gold Thoth logo, animated loading indicator) with automatic console fallback for environments where tkinter isn't available; self-closes when the server is ready
- **First-launch setup wizard** — on first install, a guided wizard offers two paths: **Local** (select and download Ollama models) or **Cloud** (enter an API key and pick a cloud model); vision model selection included for local setups
- **System tray** — `launcher.py` runs a pystray system tray icon showing app status (green = running, grey = stopped) with Open / Quit menu
- **Auto-restart** — if the native window is closed, re-opening from the tray relaunches it instantly
- **Self-contained installers** — Windows (Inno Setup) and macOS (.app bundle via python-build-standalone) bundle all dependencies at build time; no post-install downloads
- **CI/CD pipeline** — `.github/workflows/release.yml` automates test → build → code sign → notarize → GitHub Release on tag push

---

## Chat & Conversations

- **Multi-turn conversational Q&A** with full message history
- **Persistent conversation threads** stored in a local SQLite database via LangGraph checkpointer
- **Auto-naming** — threads are automatically named after the first question
- **Thread switching** — resume any previous conversation seamlessly
- **Thread deletion** — remove individual conversations or delete all at once with confirmation
- **Per-thread model switching** — pick a different model (local or cloud) for each conversation from the chat header dropdown; overrides persist across app restarts; cloud threads show a banner indicating the active provider
- **Conversation export** — export any thread as Markdown (.md), plain text (.txt), or PDF (.pdf); PDF export uses Playwright (headless Chromium) for full Unicode/emoji support, embedded images, charts, and styled markdown with automatic fpdf2 fallback
- **File attachments** — attach images (analyzed via vision model), PDFs (text extracted), CSV, Excel, JSON, and text files directly in chat; paste images from the clipboard (Ctrl+V); drag-and-drop files onto the chat window; structured data files return schema + stats + preview via pandas
- **Image persistence** — pasted, captured, and attached images survive thread reload; stored as per-thread sidecar files alongside conversation checkpoints
- **Inline image display** — reading an image file via the filesystem tool displays it inline in chat; the agent can then analyze the image contents via the vision tool
- **Inline charts** — interactive Plotly charts rendered inline when the agent visualises data (zoom, hover, pan)
- **Mermaid diagram rendering** — flowcharts, sequence diagrams, state diagrams, and other Mermaid diagrams render as interactive visual diagrams inline in chat; auto-fence detection wraps unfenced Mermaid syntax; mermaid.js bundled with strict security and dark theme
- **Inline YouTube embeds** — YouTube links in responses are rendered as playable embedded videos
- **Syntax-highlighted code blocks** — fenced code blocks render with language-aware highlighting and a built-in copy button
- **Onboarding guide** — first-run welcome message with tool overview and clickable example prompts; `👋` button in sidebar to re-show anytime
- **Status monitor panel** — replaces the home-screen logo with a frosted-glass panel containing an animated avatar (customizable emoji + ring color), 17 health-check pills in two rows (Ollama, Model, Cloud API, Email, Telegram, Gmail OAuth, Calendar OAuth, Task Scheduler, Knowledge, Dream Cycle, TTS, Wiki Vault, Disk, Threads DB, FAISS Index, Documents, Network), and a diagnosis button that runs all checks on demand with a copy-to-clipboard report; click any pill to jump to the relevant settings tab; ECG heartbeat animation scrolls behind the panel
- **Startup health check** — verifies model availability on launch; skips Ollama check when using a cloud brain model
- **OAuth token health** — Gmail and Calendar tokens are proactively checked at startup with silent refresh; periodic re-validation every 6 hours with user-facing warnings when tokens expire

---

## Notifications

- **Desktop notifications** — task completions and timer expirations trigger a desktop notification with timestamp
- **Sound effects** — distinct audio chimes for task completion (two-tone C5→E5) and timer alerts (5-beep A5), played asynchronously
- **In-app toasts** — toast messages appear in the UI with contextual emoji icons; success/info toasts auto-dismiss after 5 seconds, while error toasts (e.g. API errors) are persistent red banners with a close button
- **Unified system** — all notification channels (desktop, sound, toast) fire from a single `notify()` call with a `toast_type` parameter, keeping notification logic consistent across features

---

## Bundled Skills

Skills are reusable instruction packs that shape how the agent thinks and responds. Each skill is a `SKILL.md` file with YAML frontmatter (display name, icon, description, required tools, tags) and freeform instructions injected into the system prompt when enabled. Thoth ships with **10 bundled skills** — enable any combination from **⚙️ Settings → Skills**.

| Skill | Description |
|-------|-------------|
| **🧠 Brain Dump** | Capture unstructured thoughts and organize them into structured notes saved to memory |
| **📊 Data Analyst** | Analyse datasets, produce statistical summaries, and create insightful charts |
| **☀️ Daily Briefing** | Compile a morning briefing with weather, calendar, and news headlines |
| **🔬 Deep Research** | Perform multi-source research on a topic and produce a structured report |
| **🗣️ Humanizer** | Write in a natural, human tone — no AI-speak, no filler, no corporate fluff |
| **📋 Meeting Notes** | Structure raw meeting notes into actionable minutes with follow-ups |
| **🎯 Proactive Agent** | Anticipate user needs, ask clarifying questions, and self-check work at milestones |
| **🪞 Self-Reflection** | Periodically review memory for contradictions, gaps, and stale information |
| **⚙️ Task Automation** | Design effective automated workflows using scheduled tasks, prompt chaining, and delivery channels |
| **🌐 Web Navigator** | Strategic patterns for effective browser automation — research, forms, and data extraction |

- **10 bundled skills** cover data analysis, research, automation, meeting notes, daily briefings, and more
- **User skills** — create your own skills in `~/.thoth/skills/<name>/SKILL.md`; user skills with the same name as a bundled skill override it
- **In-app skill editor** — create and edit skills directly from Settings → Skills with a visual editor — set the name, icon, description, and write instructions without touching any files
- **Enable/disable per-skill** — toggle individual skills from Settings; only enabled skills are injected into the system prompt
- **Tool-aware** — each skill declares which tools it needs; the agent knows what capabilities are available for each skill
- **Versioned & tagged** — skills carry version numbers and tags for organization

---

## Core Modules

| File | Purpose |
|------|---------|
| **`app.py`** + **`ui/`** | NiceGUI UI — chat interface, sidebar thread manager with live token counter, Settings dialog (13 tabs including Cloud), tabbed home screen (Tasks + Activity + Knowledge graph), status monitor panel with animated avatar, 17 health-check pills, and diagnosis button (`status_bar.py` + `status_checks.py`), Task Edit dialog, file attachment handling with clipboard paste and drag-and-drop, streaming event loop with error recovery, Playwright PDF export, voice bar, first-launch setup wizard (Local/Cloud paths), per-thread model picker, task stop buttons, inline terminal panel, interactive knowledge graph visualization (vis-network), Mermaid diagram rendering (mermaid.js), OAuth token health checks (startup + periodic 6 h re-check), right-click context menu (pywebview), centralized logging configuration |
| **`agent.py`** | LangGraph ReAct agent — system prompt, automatic conversation summarization, pre-model context trimming with proportional tool-output shrinking, streaming event generator with thinking/reasoning token extraction, interrupt handling for destructive actions, live token usage reporting, graph-enhanced auto-recall with memory IDs and relation context, model override propagation via ContextVar, configurable retrieval compression (Smart/Deep/Off), task cancellation via stop_event, displaced tool-call auto-repair |
| **`threads.py`** | SQLite-backed thread metadata, `SqliteSaver` checkpointer for persisting LangGraph conversation state, and per-thread image sidecar persistence (`thread_ui/`) |
| **`memory.py`** | Backward-compatible memory wrapper — delegates all operations to `knowledge_graph.py`, mapping legacy column names (`category`/`content` to `entity_type`/`description`); provides `save_memory`, `find_by_subject`, `update_memory`, `delete_memory`, `semantic_search`, and `count_memories` with unchanged signatures |
| **`knowledge_graph.py`** | Personal knowledge graph engine — SQLite entity + relation tables (WAL mode), NetworkX DiGraph for traversal, FAISS vector index for semantic search; entity CRUD with alias resolution, relation CRUD with cascade delete, `graph_enhanced_recall()` for semantic + graph expansion, `graph_to_vis_json()` for visualization; deterministic dedup via normalized subject matching |
| **`wiki_vault.py`** | Obsidian-compatible markdown vault export — per-entity articles with YAML frontmatter, wiki-links, type-based directory grouping, per-type and master indexes, full-text search, conversation export, live export on save/delete |
| **`dream_cycle.py`** | Nightly knowledge refinement daemon — duplicate merge (≥0.93 similarity), description enrichment from conversation context, relationship inference between co-occurring entities; three-layer anti-contamination, configurable 1–5 AM window, dream journal logging |
| **`document_extraction.py`** | Background map-reduce LLM pipeline for document knowledge extraction — split → summarize → extract entities with source provenance; queue-based with live progress in status bar |
| **`models.py`** | Ollama + cloud model management — local model listing/downloading/switching, cloud provider support (OpenAI direct, OpenRouter via ChatOpenRouter), starred models, context-size catalog with heuristics, model override routing, cloud vision detection, reasoning model support (`reasoning=True` for thinking models) |
| **`documents.py`** | Document ingestion — PDF/DOCX/TXT/Markdown/HTML/EPUB loading, chunking, FAISS embedding and storage; per-document removal with source cleanup |
| **`voice.py`** | Local STT pipeline — toggle-based 4-state machine (stopped/listening/transcribing/muted) with faster-whisper CPU-only int8 transcription |
| **`tts.py`** | Kokoro TTS integration — cross-platform neural TTS, model auto-downloaded on first use (~169 MB), 10 built-in voices, streaming sentence-by-sentence playback |
| **`vision.py`** | Camera/screen capture via OpenCV/MSS, workspace image file analysis, image analysis via local or cloud vision models |
| **`data_reader.py`** | Shared pandas-based reader for CSV, TSV, Excel, JSON, JSONL — returns schema + stats + preview rows |
| **`launcher.py`** | Desktop launcher — system tray (pystray), native window management (pywebview), two-tier splash screen (tkinter with console fallback), manages NiceGUI server lifecycle; structured logging to `~/.thoth/thoth_app.log` |
| **`api_keys.py`** | API key management — tool keys from `~/.thoth/api_keys.json`, cloud LLM provider keys and starred models from `~/.thoth/cloud_config.json` |
| **`prompts.py`** | Centralized LLM prompts — system prompt (with BUILDING CONNECTIONS, EXPLORING CONNECTIONS, and BACKGROUND TASK PERMISSIONS sections), extraction prompt (triple-based with User entity convention, 10 entity types, and relation taxonomy), summarization prompt, dream cycle prompts (merge/enrich/infer), document extraction prompts (map/reduce/extract); memory guidelines with dedup, update, and cross-entity overwrite guard |
| **`memory_extraction.py`** | Background memory extraction — scans past conversations via LLM, extracts entities and relations as structured triples, two-pass dedup (entities with alias merging, then relations with subject-to-ID resolution), User entity pre-population, excludes active threads, runs on startup + every 6 hours |
| **`skills.py`** | Skills engine — discovers, loads, and caches bundled and user skill definitions from `SKILL.md` files with YAML frontmatter; builds prompt text for enabled skills injected into the system prompt; config persistence in `~/.thoth/skills_config.json` |
| **`bundled_skills/`** | 10 built-in skill packages (Brain Dump, Daily Briefing, Data Analyst, Deep Research, Humanizer, Meeting Notes, Proactive Agent, Self-Reflection, Task Automation, Web Navigator) — each a directory containing a `SKILL.md` instruction file |
| **`tasks.py`** | Task engine — SQLite CRUD, APScheduler integration, 7 schedule types, template variable expansion, sequential prompt execution, background runner with threading, channel delivery (Telegram/Email), per-task model override, run history persistence, task stop/cancel, auto-migration from workflows.db, 5 default templates, per-task `allowed_commands` and `allowed_recipients` permission fields |
| **`notifications.py`** | Unified notification system — desktop notifications (plyer), sound effects, and in-app toast queue with `toast_type` support (positive/negative); error toasts render as persistent red banners; coordinates task completion chimes and timer alerts |
| **`channels/`** | Messaging channel adapters — Telegram bot (long polling, interrupt approval, corrupt thread recovery, HTML formatting) and Email channel (Gmail polling, interrupt approval, corrupt thread recovery, sender-only filter), with shared config store |
| **`tools/`** | 24 self-registering tool modules + base class + registry |
| **`static/`** | Bundled JS libraries — `vis-network.min.js` for knowledge graph visualization, `mermaid.min.js` for diagram rendering |

---

## Data Storage

All user data is stored in `~/.thoth/` (`%USERPROFILE%\.thoth\` on Windows):

```
~/.thoth/
├── threads.db              # Conversation history & LangGraph checkpoints
├── thread_ui/              # Per-thread image sidecar files for reload persistence
├── memory.db               # Knowledge graph — entities, relations, and memory data
├── memory_vectors/         # FAISS vector index for semantic memory search
├── memory_extraction_state.json  # Tracks last extraction run timestamp
├── dream_journal.json      # Dream Cycle operation log (cycle ID, summary, duration)
├── api_keys.json           # API keys (Tavily, Wolfram, etc.)
├── cloud_config.json       # Cloud LLM provider keys and starred models
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
├── user_config.json        # Avatar emoji & ring color preferences
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
├── wiki/                   # Obsidian-compatible markdown vault export
└── kokoro/                 # Kokoro TTS model & voice data
```

> Override the data directory by setting the `THOTH_DATA_DIR` environment variable.

---

## Comparison with Other Tools

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
| **Tools** | Browser automation, Canvas, Skills platform | 24 tools / 67 sub-ops — Gmail, Calendar, filesystem, shell, browser, vision, habit tracker, charts, Wolfram, and more |
| **Desktop experience** | macOS menu bar app, WebChat | Native desktop window with system tray, splash screen, dark mode UI |
| **Tasks** | Cron jobs + webhooks | Named tasks with 7 schedule types, stop/cancel, channel delivery, per-task model override, and template variables |
| **Platforms** | macOS (primary), Linux, Windows via WSL2 only | Windows & macOS |
