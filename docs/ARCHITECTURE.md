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
- [Workflows & Scheduling](#workflows--scheduling)
- [Messaging Channels](#messaging-channels)
- [Tunnel Manager](#tunnel-manager)
- [Image Generation](#image-generation)
- [X (Twitter) Tool](#x-twitter-tool)
- [Tool Guides](#tool-guides)
- [Plugin System & Marketplace](#plugin-system--marketplace)
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
- **25 tools / 79 sub-tools** — web search, email, calendar, file management, shell access, browser automation, 5 messaging channels (Telegram, WhatsApp, Discord, Slack, SMS), X (Twitter), vision, image generation, memory, scheduled tasks, habit tracking, and more (see [Tools](#tools))
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
- **Automatic memory extraction** — a background process scans past conversations on startup and every 6 hours, extracting entities and relations the agent missed during live conversation; active threads and workflow threads (⚡-prefixed) are excluded; assistant messages are truncated to 200 chars to prevent extracting from AI-generated content; an 0.80 confidence floor rejects low-confidence entities
- **Deterministic deduplication** — both live saves and background extraction check for existing entities by normalised subject before creating new entries; cross-category matching prevents fragmentation (e.g. a birthday stored as `person` won't be duplicated as `event`); alias resolution ensures "Mom" and "Mother" map to the same entity; richer content is always kept
- **Vague-type banning** — `related_to`, `associated_with`, `connected_to`, `linked_to`, `has_relation`, `involves`, and `correlates_with` are rejected before saving, preventing noisy low-value edges
- **Relation pre-normalisation** — `normalize_relation_type()` canonicalises aliases (e.g. `is_father_of` → `father_of`) before any checks (ban, confidence gate, dedup)
- **67 valid relation types** — curated vocabulary with 60+ alias mappings; 6 document-specific types: `extracted_from`, `uploaded`, `builds_on`, `cites`, `extends`, `contradicts`; self-loop rejection blocks relations where source and target are the same entity
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
- **Agent tool** — 4 sub-tools (`wiki_read`, `wiki_rebuild`, `wiki_stats`, `wiki_export_conversation`) let the agent interact with the vault directly
- **Settings UI** — enable/disable toggle, vault path configuration with Browse button, stats display, rebuild and open-folder buttons in the Knowledge tab

---

## Dream Cycle

A 4-phase background daemon that refines the knowledge graph during idle hours, running non-destructive operations with a three-layer anti-contamination system.

- **Phase 1: Duplicate merge** — entities with ≥0.93 semantic similarity and same type are merged; LLM synthesizes the best description, aliases are unioned, relations re-pointed to the survivor
- **Subject-name guard** — entities with different normalized subjects require ≥0.98 similarity to merge, preventing false merges of distinct people/concepts
- **Phase 1: Description enrichment** — thin entities (<80 chars) appearing in 2+ conversations get richer descriptions from conversation context and relationship graph
- **Phase 2: Relationship inference** — co-occurring entity pairs with no existing edge are evaluated for a meaningful connection (tagged `source="dream_infer"`); hub diversity cap limits any single entity to at most 3 appearances across inferred pairs per cycle; batch rotation with stored offset and half-overlap ensures fresh entity pairs each cycle; 7-day rejection cache (`dream_rejections.json`) avoids wasting LLM calls on previously rejected combinations; pre-flight merge check skips pairs where one entity's description already mentions the other's subject; multi-excerpt evidence provides richer context per pair; `uses` prompt rule: "`uses` means actively employs as a tool, dependency, or platform — NOT merely mentions, searches for, or discusses"; skip vague edges — existing vague relations (`related_to`, `associated_with`, etc.) are ignored when checking for existing connections
- **Phase 3: Confidence decay** — relations older than 90 days lose 10% confidence per cycle; relations below 0.3 are pruned automatically
- **Three-layer anti-contamination** — (1) sentence-level excerpt filtering extracts only sentences mentioning the target entity, (2) deterministic post-enrichment cross-entity validation scans LLM output for unrelated entity subjects and rejects contaminated results before DB write, (3) strengthened prompt with concrete negative examples and subject-name substitution
- **Ollama busy check** — queries `/api/ps` before starting a dream cycle; defers if Ollama is actively serving a user request to avoid GPU competition
- **Configurable window** — default 1–5 AM local time; checks every 30 minutes if conditions met (enabled, in window, idle, not yet run today); interactive HH:00 time pickers in Settings
- **Dream journal** — all operations logged to `~/.thoth/dream_journal.json` with cycle ID, summary, and duration; expandable entries in the Activity tab showing merges, enrichments, inferred relations, and errors per cycle
- **🌙 Dream button** — manual dream cycle trigger in the Knowledge graph panel; async execution with status notifications
- **Settings UI** — enable/disable toggle, window display, and last run summary in the Knowledge tab
- **Status pill** — dedicated health-check pill shows enabled state and last run time

---

## Document Knowledge Extraction

Uploaded documents are processed through a three-phase **map-reduce LLM pipeline** that extracts structured knowledge into the graph with full source provenance.

- **Map phase** — document split into ~6K-char windows; each window summarized to 3–5 sentences
- **Reduce phase** — window summaries combined into a coherent 300–600 word article
- **Extract phase** — core entities and relations pulled from the final article; capped at 12 entities per document to prevent over-extraction
- **Curated relation vocabulary** — 67 valid relation types with 60+ alias mappings (e.g. `published_by → authored`, `implements → uses`, `used_by → uses`, `references → cites`); 6 document-specific types: `extracted_from`, `uploaded`, `builds_on`, `cites`, `extends`, `contradicts`
- **Hub entity** — the document itself is saved as a `media` entity; extracted entities linked via `extracted_from` relation for provenance tracking; `find_by_subject` dedup ensures re-uploading a document updates the existing hub rather than creating a duplicate
- **Quality gates** — minimum description length (30 chars) rejects thin stub entities; self-loop rejection blocks relations where source and target are the same entity; vague relation types (`related_to`, `associated_with`, etc.) are rejected before saving
- **Cross-window dedup** — entities with the same subject across windows are merged before saving
- **Cross-source merge protection** — when a document entity matches a personal entity via FAISS semantic search, the similarity threshold is raised from 0.80 to 0.90 to prevent impersonal document content from overwriting personal memories
- **New file formats** — supports PDF, DOCX, TXT, Markdown (`.md`), HTML, and EPUB
- **Live progress** — status bar shows pulsing progress pill with phase indicator, progress bar, queue count, and stop button (updates every 2 seconds)
- **Background queue** — documents queued for processing; worker thread handles one at a time
- **Per-document cleanup** — individual document delete button removes vector store entries and all extracted entities with matching source tag; bulk "Clear all documents" removes everything with `document:*` prefix

---

## Brain Model & Cloud Models

The brain model is Thoth's default LLM — the model used for conversations, memory extraction, and any thread or task without a specific override. It can be a local Ollama model or an opt-in cloud model.

Thoth is built and tested for local models first. Every feature supports local models, and that will always be the priority. Local models are already amazing — tool calling, multi-step reasoning, memory extraction, and long conversations all work well with a 14B+ model. As local models improve and hardware requirements drop, the goal is to reduce any dependency on cloud models over time.

Some users don't have a dedicated GPU. Others need frontier-level reasoning (GPT, Claude, Gemini) for specific tasks, or want to try different models without downloading gigabytes. Thoth supports opt-in cloud models through **OpenAI** (direct API), **Anthropic** (Claude), **Google AI** (Gemini), **xAI** (Grok), and **OpenRouter** (100+ models from all major providers) for these cases — configured entirely from the Settings panel, no config files or terminal commands.

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
- **3-tier safety classification** — every command is classified as *safe* (runs automatically), *moderate* (requires user confirmation), or *blocked* (rejected outright); safety rules are applied before execution; enhanced destructive-command detection for workflow safety-mode integration
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

## Workflows & Scheduling

Tasks have been renamed to **Workflows** throughout the application. The workflow engine adds a full step-based pipeline system on top of the existing scheduling infrastructure.

### Core Engine

- **Unified workflow engine** — create named, multi-step workflows that run sequentially in a fresh thread, powered by APScheduler
- **7 schedule types** — `daily`, `weekly`, `weekdays`, `weekends`, `interval` (minutes), `cron` (full cron expression), `delay_minutes` (one-shot quick timer with notification)
- **Template variables** — use `{{date}}`, `{{day}}`, `{{time}}`, `{{month}}`, `{{year}}`, `{{task_id}}`, `{{step.X.output}}` in prompts — replaced at runtime; `{{task_id}}` lets prompts reference their own workflow for self-management; `{{step.X.output}}` references the output of a previous step for data flow between steps
- **Channel delivery** — workflows can deliver their output to any registered channel (Telegram, etc.) after execution; per-task `delivery_channel` and `delivery_target` configuration
- **Per-task model override** — each workflow can specify a different LLM; the engine loads the override, runs the task, then restores the default
- **Persistent threads** — `persistent_thread_id` reuses the same conversation thread across workflow runs
- **Notify-only mode** — `notify_only` flag fires a notification without agent invocation
- **Skills override** — per-workflow skill selection via `skills_override`

### Step-Based Pipelines

- **5 step types** — Prompt (runs an LLM prompt), Condition (evaluates an expression and branches), Approval (pauses for human decision), Subtask (runs a sub-prompt), Notify (sends a notification)
- **Conditional branching** — condition steps evaluate expressions with operators: `contains`, `not_contains`, `regex`, `json_path`, `llm_evaluate`; each condition has `if_true` and `if_false` targets pointing to the next step
- **Approval gates** — approval steps pause workflow execution and wait for a human to approve or deny; configurable timeout; routing via `if_approved` and `if_denied` step targets; approval requests sent to configured channels (Telegram, desktop notifications) with inline approval/deny buttons
- **Webhook triggers** — workflows can be triggered via `POST /api/webhook/<task_id>` with auto-generated secrets (`X-Webhook-Secret` header) for authentication
- **Task-completion triggers** — one workflow can trigger another on completion, enabling chained automation
- **Concurrency groups** — prevent parallel execution of related workflows; only one workflow per group runs at a time
- **Safety mode** — per-workflow setting with three levels: `block_destructive` (block all destructive tools), `require_approval` (pause at destructive actions for approval), `allow_all` (no restrictions); enforced across shell, task, and channel tools via tool filtering in the agent
- **Tools override** — per-step tool selection with auto-detection from prompt content
- **Agent-callable** — the task tool now accepts step definitions, triggers, safety mode, and concurrency group for programmatic workflow creation

### Workflow Builder UI

- **Simple/Advanced toggle** — simple mode preserves the existing single-prompt interface; advanced mode exposes the full pipeline builder
- **Step builder** — drag-to-reorder, delete, type-change for each step; visual condition builder with operator picker, JSON path input, and LLM question textarea
- **Variable insertion menu** — `{{step.X.output}}`, `{{date}}`, `{{time}}`, and context variables insertable via dropdown
- **Flow preview** — Mermaid diagram generated from step graph with refresh button
- **Validation** — required field checks, reference validation, and operator-specific rules before save

### Approval System

- **Pending approvals panel** — Activity tab shows pending approval cards with task name, message, and Approve / Deny buttons; auto-refreshes every 5 seconds
- **Sidebar badge** — orange count badge on the Home button when approvals are pending; compact approval strip above the thread list with quick-approve buttons
- **Multi-channel routing** — approval requests sent to configured channels (Telegram, desktop notifications) with inline keyboard buttons
- **Agent integration** — agent checks pending approvals before resuming; routes to `if_approved` or `if_denied` step based on user response

### Existing Features

- **Prompt chaining** — each step sees the output of the previous step, enabling research → summarise → action pipelines
- **Always-background execution** — workflows always run in the background so you can keep chatting; the sidebar shows a ⏳ indicator while running
- **Background permissions** — background workflows use a tiered permission system: safe operations always run, low-risk operations (move file, send email) are allowed with optional per-task allowlists, and irreversible operations (file delete, memory delete) are always blocked; configure allowed shell command prefixes and email recipients per-task in the "🔒 Background permissions" section of the workflow editor
- **Pre-built templates** — ships with 5 starter workflows (Daily Briefing, Research Summary, Email Digest, Weekly Review, Quick Reminder)
- **Home screen dashboard** — manage workflows from the home screen with a tabbed layout: ⚡ Workflows (tiles with edit/run/delete) and 📋 Activity (monitoring panel with upcoming runs, recent history, channel status, pending approvals, extraction journal, dream journal); the home screen's status monitor panel shows 17 health-check pills at a glance with a diagnosis button
- **Persistent run history** — workflow execution history survives deletion; displayed in the Activity tab with ✅/❌/⏳ status icons
- **Monitoring / polling** — use interval schedules with conditional prompts to monitor conditions (stock availability, price drops, new releases); the agent checks periodically, reports when the condition is met, and self-disables the workflow via `{{task_id}}` — no manual intervention needed
- **Task stop / cancel** — stop a running workflow from the chat header, activity panel, or workflow card; stopped workflows skip delivery and auto-delete, and are recorded in run history

---

## Messaging Channels

Thoth uses a generic **Channel ABC** — any messaging platform can plug in by subclassing `Channel`, declaring its capabilities, and registering itself. The system auto-generates LangChain tools, Settings UI, and health checks for each registered channel. Five channels ship out of the box: **Telegram**, **WhatsApp**, **Discord**, **Slack**, and **SMS**.

### Channel Architecture

- **`Channel` ABC** — abstract base class all channel adapters inherit from; lifecycle methods `start()`, `stop()`, `is_configured()`, `is_running()`; outbound methods `send_message()`, `send_photo()`, `send_document()`, `send_approval_request()`; extensibility hooks `extra_tools()` and `build_custom_ui()`; `get_default_target()` for target resolution; `webhook_port` and `needs_tunnel` properties for tunnel integration
- **`ChannelCapabilities`** — declarative feature flags per channel: `photo_in`, `photo_out`, `voice_in`, `document_in`, `buttons`, `streaming`, `typing`, `reactions`, `slash_commands`; the UI and tool factory read these to auto-generate tooling
- **`ConfigField`** — describes user-configurable fields (name, label, type, required flag) that render automatically in the Settings UI
- **Channel registry** — `register()` at import time, `all_channels()`, `running_channels()`, `configured_channels()`; central routing via `deliver(channel_name, target, text)` with validation; used by the task engine for delivery
- **Shared media pipeline** — `channels/media.py` provides reusable media processing for any channel: `transcribe_audio()` (faster-whisper, OGG/MP3/WAV/WebM), `analyze_image()` (Vision service), `extract_document_text()` (PDF/CSV/JSON/plain-text with truncation), `save_inbound_file()` (persist to `~/.thoth/inbox/`), `copy_to_workspace()` (copies received files into the filesystem-tool workspace under `Received Files/` with dedup)
- **Shared utilities** — `channels/auth.py` (common auth helpers), `channels/commands.py` (slash command handling), `channels/approval.py` (approval routing), `channels/media_capture.py` (vision/image-gen capture helpers), `channels/thread_repair.py` (corrupt-thread detection for stuck tool-call errors)
- **Tool factory** — `channels/tool_factory.py` auto-generates LangChain tools for each registered channel based on capabilities: `send_{name}_message`, `send_{name}_photo`, `send_{name}_document`; Pydantic input schemas; multi-strategy file path resolution (absolute, workspace-relative, tracker exports, cwd); target resolution delegates to each channel's `get_default_target()` method
- **Channel tool injection** — `agent.py` iterates `running_channels()` at graph creation time and injects auto-generated channel tools into the LangChain tools list; each running channel contributes its send/photo/document tools dynamically
- **Activity tracker** — `channels/base.py` maintains a module-level `_channel_activity` dict mapping channel names to epoch timestamps; `record_activity()` called by all 5 channel handlers on each inbound message; `get_last_activity()` read by the sidebar monitor
- **YouTube URL extraction** — `channels/__init__.py` provides `extract_youtube_urls(text)` that strips YouTube URLs (including Shorts) from message text so they can be sent as separate messages for native platform previews
- **Channel config** — per-channel key-value store in `~/.thoth/channels_config.json`
- **Auto-start** — channels with `auto_start` enabled start automatically when Thoth launches; `app.py` imports all 5 channel adapters at startup
- **Settings UI** — configure, start/stop, and manage channels from Settings → Channels tab; dynamic `_build_channel_panel(ch)` renders auto-generated config UI for any registered channel using `config_fields`
- **Health checks** — `check_channels()` returns a `CheckResult` per channel (ok/warn/error/inactive); `check_tunnel()` reports tunnel status; both included in `ALL_CHECKS` and `LIGHT_CHECKS`
- **Sidebar channel monitor** — live panel below the conversation list shows status dots (green = running, amber = stopped, grey = not configured), channel-specific icons, display names, and relative last-activity times ("2m ago", "1h ago"); 5-second polling timer; click any row to open Settings; channel pills filtered from the status bar to avoid duplication

### Telegram

- **Full ReAct agent access** — messages processed by the full agent with all tools available; each chat gets its own conversation thread
- **Streaming responses** — sends a "⏳" placeholder message, then progressively edits it with accumulated tokens and tool status lines via `_tg_edit_consumer()`; rate-limited edits (every 1.5s) to respect Telegram API limits; overflow protection falls back to split messages when text exceeds `MAX_TG_MESSAGE_LEN`
- **Voice messages** — inbound voice/audio transcribed via faster-whisper through the shared media pipeline; transcript sent to agent as user text
- **Photo messages** — inbound photos analyzed via Vision service; analysis sent to agent with optional caption
- **Document handling** — inbound documents saved to `~/.thoth/inbox/`, text extracted (PDF, CSV, JSON, plain text), file path + extracted content + caption sent to agent as one message
- **Image generation delivery** — retrieves the last generated image from the image gen tool’s side-channel and sends it as a photo
- **Emoji reactions** — real-time status feedback using Telegram's native reaction API: 👀 (processing), 👍 (success), 💔 (error); graceful fallback if bot lacks permission
- **Interrupt approval** — tool calls requiring human approval render as inline keyboard buttons (Approve / Deny)
- **Multi-channel approval routing** — workflow approval gates send approval requests to Telegram with inline Approve / Deny buttons; responses routed back to the workflow engine
- **Safety mode enforcement** — respects per-workflow safety mode settings; destructive tool calls in `require_approval` mode trigger approval requests via Telegram
- **Proactive messaging** — the agent can send messages, photos, and documents to any Telegram chat via auto-generated channel tools
- **`/model` command** — list and switch models (local or cloud) from within Telegram
- **Auto-recovery** — handles orphaned tool calls gracefully; offers fresh thread on persistent failures; corrupt thread recovery via shared `thread_repair` module
- **HTML formatting** — responses formatted with Telegram-compatible HTML
- **Bot commands** — registered with BotFather for discoverability

### WhatsApp

- **Baileys bridge** — Node.js bridge (`channels/whatsapp_bridge/bridge.js`) using Baileys v6 for WhatsApp Web protocol; communicates with the Python adapter via stdin/stdout JSON messages
- **QR code pairing** — QR code displayed in Settings → Channels for scanning with WhatsApp mobile app; auth state persisted for reconnection
- **Inbound media** — voice messages transcribed via faster-whisper; photos analyzed via Vision; documents saved and text extracted; all routed through the shared media pipeline
- **YouTube rich previews** — YouTube URLs extracted from outbound messages and sent separately with native link preview metadata (oEmbed title/description + JPEG thumbnail) via Baileys `linkPreview` format; Shorts URLs supported
- **Markdown-to-WhatsApp formatting** — converts Markdown bold/italic/code to WhatsApp-native formatting; table conversion for readability
- **Streaming responses** — rate-limited message edits for progressive response display
- **Typing indicators & reactions** — typing presence and emoji reactions on inbound messages
- **Thread management** — `_get_or_create_thread` with "📲 WhatsApp conversation" naming; always bumps `updated_at` for sidebar ordering

### Discord

- **`discord.py` adapter** — DM-based messaging via Discord bot with OAuth bot token; numeric User ID gating via `_get_allowed_user_id()`
- **Streaming responses** — progressive message edits in Discord DMs
- **Reactions & typing** — emoji reactions and typing indicators
- **Slash commands** — Discord slash command support via shared commands module
- **Media support** — photo and document sending/receiving
- **Thread management** — `_get_or_create_thread` with "🎮 Discord conversation" naming; always bumps `updated_at`

### Slack

- **`slack-bolt` adapter** — Socket Mode for zero-webhook operation (no public URL needed); DM-based messaging
- **Streaming responses** — progressive updates via `chat.update` API
- **Reactions & typing** — emoji reactions and typing indicators
- **File uploads** — photo and document support via Slack Files API
- **Thread management** — DM threading with sidebar thread list integration

### SMS

- **Twilio adapter** — inbound webhook receiver for incoming SMS/MMS; outbound via Twilio REST API
- **MMS photo support** — send and receive photos via MMS
- **Tunnel required** — needs a public URL for Twilio to deliver inbound messages; auto-integrates with the tunnel manager
- **Thread management** — per-phone-number threads

### Gmail Tools

- **Gmail attachments** — `send_gmail_message` and `create_gmail_draft` support file attachments; files are MIME-encoded automatically; workspace-relative paths are resolved

---

## Tunnel Manager

A provider-agnostic tunnel infrastructure for exposing local webhook ports to the internet. Channels that need inbound webhooks (e.g. SMS/Twilio) use the tunnel manager to obtain public HTTPS URLs without manual port forwarding.

- **`tunnel.py`** — `TunnelProvider` ABC that each backend implements; `NgrokProvider` concrete implementation using `pyngrok`; thread-safe `TunnelManager` singleton created at import time but dormant until first use
- **Auto-lifecycle** — channels call `tunnel_manager.start_tunnel(port)` on start and `stop_tunnel(port)` on shutdown; multiple ports can be tunneled simultaneously
- **Main app tunnel** — optional toggle to tunnel the main Thoth web UI port for remote access (with warning about UI exposure)
- **Settings UI** — Tunnel Settings section in the Channels tab with provider picker (ngrok), auth token input, active tunnel display with port→URL mapping, and save button
- **Health check** — `check_tunnel()` reports provider availability, active tunnel count and URLs, or "not configured" status

---
all running messaging channels retrieve the generated image from the side-channel and send it as a photo message
- **Disk persistence** — `_save_image_to_disk()` writes every generated image to `~/.thoth/media/` with timestamped filenames; file path included in tool response so the agent can reference or re-send the image later
## X (Twitter) Tool

Full-featured X / Twitter integration with 13 tools for reading, posting, and managing content.

- **13 tools** — `post_tweet`, `post_thread`, `reply_to_tweet`, `retweet`, `like_tweet`, `unlike_tweet`, `delete_tweet`, `get_tweet`, `get_user_tweets`, `search_tweets`, `get_user_profile`, `get_followers`, `get_following`
- **OAuth 2.0 PKCE** — browser-based OAuth flow with PKCE challenge; tokens stored in `~/.thoth/x/`; auto-refresh with refresh tokens; revoke-and-reauth on persistent 403s
- **Rate limiting** — per-endpoint rate tracking with configurable tier limits; `_check_rate_limit()` before every call; `_record_rate_usage()` after; proactive budget warnings injected into tool responses
- **Tier detection** — auto-detects Free/Basic/Pro tier from API responses and adjusts rate limits accordingly; falls back to Free tier defaults
- **Thread posting** — `post_thread` splits long content into a chain of reply tweets; returns all tweet IDs and URLs
- **Media uploads** — `post_tweet` and `post_thread` accept image file paths; images uploaded via Twitter media API; multi-strategy path resolution (absolute, workspace-relative, tracker exports)
- **Settings UI** — X / Twitter section in Settings → Accounts with OAuth connect/disconnect button, tier display, and rate limit status
- **Graceful degradation** — all tools return structured error messages with remaining rate budget on failure; never raises to the agent

---

## Tool Guides

A system for attaching contextual usage instructions to tools via lightweight SKILL.md files.
or, charts, DuckDuckGo, filesystem, Gmail, image generation, memory, shell, Telegram, tracker, URL reader, and web search tools
- **`tools` activation field** — each guide's SKILL.md frontmatter declares a `tools:` list; the guide is auto-activated when any listed tool appears in the agent's tool belt
- **Prompt injection** — `prompts.py` scans active tool guides and injects their content into the system prompt, replacing hardcoded per-tool instructions
- **Prompt cleanup** — old hardcoded tool instructions in `prompts.py` removed in favor of the guide system

---

#--

## Image Generation

-# Image Generationall running messaging channels retrieve the generated image from the side-channel and send it as a photo message
- **Disk persistence** — every generated image is saved to `~/.thoth/images/` with a timestamped filename; the chat UI links to the saved file so images survive page reloads and can be shared across channels

- **Generate images** — create images from text prompts via OpenAI, xAI (Grok Imagine), and Google (Imagen 4, Nano Banana); supports OpenAI (`gpt-image-1`, `gpt-image-1.5`, `gpt-image-1-mini`), xAI (`grok-imagine-image` with quality-to-resolution mapping), and Google (`imagen-4.0-generate-001`, `imagen-4.0-fast-generate-001`, `imagen-4.0-ultra-generate-001`, plus Gemini image models via `generate_content` API) with configurable size and quality
- **Edit images** — modify existing images with a text prompt; image sources: `"last"` (most recent generation), filename (from attachment cache), or file path on disk
- **Side-channel rendering** — `_last_generated_image` global holds the base64 image data; the UI streaming layer picks it up and renders it inline in chat; automatically cleared after retrieval
- **Attachment cache** — pasted and attached images are stored in `_image_cache` (populated by `ui/streaming.py`) so the agent can reference them by filename for editing
- **Channel delivery** — all running messaging channels retrieve the generated image from the side-channel and send it as a photo message
- **Disk persistence** — every generated image is saved to `~/.thoth/images/` with a timestamped filename; the chat UI links to the saved file so images survive page reloads and can be shared across channels
- **Base64 data-URI** — auto-detects PNG/JPEG/WebP/GIF format from image bytes and renders with the correct MIME type
- **Model selector** — configurable in Settings → Models; default `openai/gpt-image-1.5`

---

## Plugin System & Marketplace

A sandboxed, hot-reloadable extension system that lets anyone add new tools and skills without touching core code.

### Plugin Architecture

- **Plugin API** — `PluginAPI` bridge object and `PluginTool` base class are the only core imports a plugin needs; provides `get_config()`, `set_config()`, `get_secret()`, `set_secret()`, `register_tool()`, `register_skill()`
- **Plugin API v2** — `_run()` method override for cleaner interface; `background_allowed` and `destructive` flags for safety gating; rich return types (dicts, lists)
- **Manifest system** — each plugin declares metadata in `plugin.json`: ID, version, author, description, tools, skills, settings schema, API keys, and Python dependencies; validated against a strict schema (ID regex, semver, required fields)
- **Security sandbox** — static scan blocks `eval()`, `exec()`, `os.system()`, `subprocess`, and `__import__()`; import guard prevents loading from core modules (`tools`, `agent`, `models`, `ui`); `register()` call has a 5-second timeout
- **Dependency safety** — freezes core dependency versions before installing plugin deps; blocks downgrades that could break Thoth
- **State persistence** — enable/disable state, config values, and API key secrets stored in `plugin_state.json` and `plugin_secrets.json` (restricted file permissions) under `~/.thoth/`
- **Hot reload** — "Reload Plugins" button in Settings clears the registry and re-runs discovery without restarting the app; agent cache is invalidated automatically
- **External link handling** — `JsApi.open_url()` opens external links in the system browser instead of navigating the app webview; viewport lock prevents the webview from zooming or scrolling unexpectedly
- **Paste fix** — clipboard paste support in the native webview (Ctrl+V / Cmd+V)
- **Skill auto-discovery** — `SKILL.md` files in a plugin’s `skills/` directory are detected and injected into the agent’s system prompt alongside built-in skills
- **Version gating** — plugins declare `min_thoth_version`; loader rejects incompatible plugins with a clear error message

### Marketplace

- **Marketplace client** — fetches and caches the plugin index from a GitHub-hosted `index.json` with TTL-based refresh; provides search, tag filtering, and update detection
- **Browse dialog** — NiceGUI dialog with search bar, tag filter pills, and one-click install buttons
- **Install/update/uninstall** — downloads plugin archives, validates before install, manages `~/.thoth/installed_plugins/`; duplicate installs rejected; security violations block installation
- **Auto-reload** — after marketplace install/update, plugins are automatically reloaded and agent cache cleared so new tools are available immediately
- **Update detection** — `check_updates()` compares installed versions against the marketplace index

### External link handling** — `JsApi.open_url()` opens external links in the system browser instead of navigating the app webview; viewport lock prevents the webview from zooming or scrolling unexpectedly
- **Paste fix** — clipboard paste support in the native webview (Ctrl+V / Cmd+V)
- **Plugin Settings UI

- **Card grid** — each plugin rendered as a card with icon, name, version badge, description, tool/skill count badges, and enable/disable toggle
- **Missing API key warnings** — cards show a warning badge when required secrets are not configured
- **Per-plugin config dialog** — opens plugin details with API key inputs, settings controls, tools/skills list, and actions (update, uninstall)
- **Empty state** — "No plugins installed" with a marketplace call-to-action

### Core Integration

- **`app.py`** — calls `load_plugins()` asynchronously at startup; logs loaded/failed counts; surfaces failures as startup warnings
- **`agent.py`** — injects plugin tools into the LangChain tools list and plugin skills into the system prompt; `clear_agent_cache()` ensures new tools take effect after reload
- **`ui/settings.py`** — wires the Pluand YouTube Shorts links in responses are rendered as playable embedded videos; Shorts URLs normalized to standard embed format
- **Syntax-highlighted code blocks** — fenced code blocks render with language-aware highlighting and a built-in copy button
- **Modern chat input** — redesigned input area with a card-based layout: rounded input field with attachment button (left), send button (right), and model selector pill below; replaces the previous flat textarea
- **Finish-reason truncation warning** — when a model response is cut short by token limits (`finish_reason: length`), a warning banner appears below the message explaining the truncation
- **Auto-scroll fix** — wheel and touch events on the chat container properly cancel auto-scroll to prevent the view from jumping while the user is reading
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
- **Image persistence** — all media (generated images, captures, attachments) saved to `~/.thoth/media/{thread_id}/` with sequential filenames and sidecar `.media.json`; two-tier persistence — Tier 1 (generated content) survives thread deletion, Tier 2 (transient captures) cleaned up automatically; hydrated from disk on thread load
- **Inline image display** — reading an image file via the filesystem tool displays it inline in chat; the agent can then analyze the image contents via the vision tool
- **Inline charts** — interactive Plotly charts rendered inline when the agent visualises data (zoom, hover, pan)
- **Mermaid diagram rendering** — flowcharts, sequence diagrams, state diagrams, and other Mermaid diagrams render as interactive visual diagrams inline in chat; auto-fence detection wraps unfenced Mermaid syntax; mermaid.js bundled with strict security, dark theme, and `suppressErrors: true` for robustness
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
| **📋 Meeting Notes** | Structure raw meeting notes into actionable minutes with follow-ups | with `JsApi` for external link handling and viewport lock
| **13 tool guides** — lightweight skill files in `tool_guides/` that attach contextual usage instructions to specific tools; auto-activated via the `tools:` frontmatter field when the corresponding tool is in the agent's tool belt; covers browser, calculator, charts, DuckDuckGo, filesystem, Gmail, image generation, memory, shell, Telegram, tracker, URL reader, and web search
- **🎯 Proactive Agent** | Anticipate user needs, ask clarifying questions, and self-check work at milestones |
| **🪞 Self-Reflection** | Periodically review memory for contradictions, gaps, and stale information |
| **⚙️ Task Automation** | Design effective advanced workflows with step pipelines, conditions, approval gates, and delivery channels |
| **🌐 Web Navigator** | Strategic patterns for effective browser automation — research, forms, and data extraction |

- **10 bundled skills** cover data analysis, research, automation, meeting notes, daily briefings, and more
- **User skills** — create your own skills in `~/.thoth/skills/<name>/SKILL.md`; user skills with the same name as a bundled skill override it
- **In-app skill editor** — create and edit skills directly from Settings → Skills with a visual editor — set the name, icon, description, and write instructions without touching any files
- **Enable/disable per-skill** — toggle individual skills from Settings; only enabled skills are injected into the system prompt
- **Tool-aware** — each skill declares which tools it needs; the agent knows what capabilities are available for each skill
- **Versioned & tagged** — skills carry version numbers and tags for organization

--- and finish-reason detection (truncation warnings) with modern card-based input layout, sidebar thread manager with live token counter, approval badge, and channel monitor panel (status dots, activity times, 5s polling), Settings dialog (13 tabs including Cloud, Plugins, and Channels with tunnel settings), tabbed home screen (Workflows + Activity + Knowledge graph), pending approvals panel, extraction journal viewer, dream journal viewer, status monitor panel with animated avatar, 17 health-check pills, and diagnosis button (`status_bar.py` + `status_checks.py`), Workflow Edit dialog with Simple/Advanced mode toggle and step-builder UI with Mermaid flow preview, file attachment handling with clipboard paste and drag-and-drop, streaming event loop with error recovery and finish-reason truncation warnings

## Core Modules

| File | Purpose |
|------|---------|
| **`app.py`** + **`ui/`** | NiceGUI UI — chat interface, sidebar thread manager with live token counter and approval badge, Settings dialog (13 tabs including Cloud, Plugins, and Channels), tabbed home screen (Workflows + Activity + Knowledge graph), pending approvals panel, extraction journal viewer, dream journal viewer, status monitor panel with animated avatar, 17 health-check pills, and diagnosis button (`status_bar.py` + `status_checks.py`), Workflow Edit dialog with Simple/Advanced mode toggle and step-builder UI with Mermaid flow preview, file attachment handling with clipboard paste and drag-and-drop, streaming event loop with error recovery, Playwright PDF export, voice bar, first-launch setup wizard (Local/Cloud paths), Google Account setup wizard, per-thread model picker, task stop buttons, inline terminal panel, interactive knowledge graph visualization (vis-network) with Dream button, Mermaid diagram rendering (mermaid.js), image generation inline rendering, OAuth token health checks (startup + periodic 6 h re-check), right-click context menu (pywebview), plugin marketplace dialog, centralized logging configuration |
| **`agent.py`** | LangGraph ReAct agent — system prompt, automatic conversation summarization, pre-model context trimming with proportional tool-output shrinking, streaming event generator with thinking/reasoning token extraction, interrupt handling for destructive actions, approval-gate integration (pause/resume workflows at approval steps), step branching execution, safety-mode tool filtering, live token usage reporting, graph-enhanced auto-recall with memory IDs and relation context, model override propagation via ContextVar, configurable retrieval compression (Smart/Deep/Off), task cancellation via stop_event, displaced tool-call auto-repair, plugin tool + channel tool injection, `clear_agent_cache()` for reload |
| **`threads.py`** | SQLite-backed thread metadata, `SqliteSaver` checkpointer for persisting LangGraph conversation state, and per-thread media storage (`~/.thoth/media/`) with sidecar `.media.json` files and two-tier persistence (Tier 1 generated / Tier 2 transient) |
| **`memory.py`** | Backward-compatible memory wrapper — delegates all operations to `knowledge_graph.py`, mapping legacy column names (`category`/`content` to `entity_type`/`description`); provides `save_memory`, `find_by_subject`, `update_memory`, `delete_memory`, `semantic_search`, and `count_memories` with unchanged signatures |
| **`knowledge_graph.py`** | Personal knowledge graph engine — SQLite entity + relation tables (WAL mode), NetworkX DiGraph for traversal, FAISS vector index for semantic search; entity CRUD with alias resolution, relation CRUD with cascade delete, 67 valid relation types with 60+ aliases and self-loop rejection, `graph_enhanced_recall()` for semantic + graph expansion, `graph_to_vis_json()` for visualization; deterministic dedup via normalized subject matching |
| **`wiki_vault.py`** | Obsidian-compatible markdown vault export — per-entity articles with YAML frontmatter, wiki-links, type-based directory grouping, per-type and master indexes, full-text search, conversation export, live export on save/delete |
| **`dream_cycle.py`** | 4-phase nightly knowledge refinement daemon — duplicate merge (≥0.93 similarity), description enrichment from conversation context, relationship inference with hub diversity cap, batch rotation, 7-day rejection cache, pre-flight merge check, Ollama busy check, and confidence decay on stale relations; three-layer anti-contamination, configurable dream window, dream journal logging |
| **`document_extraction.py`** | Background map-reduce LLM pipeline for document knowledge extraction — split → summarize → extract entities with source provenance; curated 67-type relation vocabulary, entity cap (12), min description length (30 chars), hub entity dedup, quality gates; queue-based with live progress in status bar |
| **`models.py`** | Ollama + cloud model management — local model listing/downloading/switching, clo with `JsApi` for external link handling and viewport lockud provider support (OpenAI, Anthropic via ChatAnthropic, Google AI via ChatGoogleGenerativeAI, xAI via ChatXAI, OpenRouter via ChatOpenRouter), starred models, context-size catalog with xAI Grok 2M-token entries, model override routing, cloud vision detection, reasoning model support (`reasoning=True` for thinking models) |
| **`documents.py`** | Document ingestion — PDF/DOCX/TXT/Markdown/HTML/EPUB loading, chunking, FAISS embedding and storage; per-document removal with source cleanup |
| **`voice.py`** | Local STT pipeline — toggle-based 4-state machine (stopped/listening/transcribing/muted) with faster-whisper CPU-only int8 transcripti with tool guide injection replacing hardcoded per-tool instructionson |
| **`tts.py`** | Kokoro TTS integration — cross-platform neural TTS, model auto-downloaded on first use (~169 MB), 10 built-in voices, streaming sentence-by-sentence playback |
| **`vision.py`** | Camera/screen capture via OpenCV/MSS, workspace image file analysis, image analysis via local or cloud vision models |
| **`data_reader.py`** | Shared pandas-based reader for CSV, TSV, Excel, JSON, JSONL — returns schema + stats + preview rows |
| **`launcher.py`** | Desktop launcher — system tray (pystray), native window management (pywebview), two-tier splash screen (tkinter with console fallback), manages NiceGUI server lifecycle; structured logging to `~/.thoth/thoth_app.log` |
| **`api_keys.py`** | API key management — tool keys from `~/.thoth/api_keys.json`, cloud LLM provider keys and starred models from `~/.thoth/cloud_config.json` |
| **`prompts.py`** | Centralized LLM prompts — system prompt (with BUILDING CONNECTIONS, EXP (`get_default_target()`, `webhook_port`, `needs_tunnel`), channel registry with auto-start and delivery routing, activity tracker (`record_activity`/`get_last_activity`), shared media pipeline (transcribe/analyze/extract/save/`copy_to_workspace`), shared utilities (`auth.py`, `commands.py`, `approval.py`, `media_capture.py`, `thread_repair.py`), YouTube URL extraction, tool factory for auto-generated LangChain tools per channel with `get_default_target()` delegation; 5 adapters: Telegram (streaming, voice/photo/document inbound, emoji reactions, interrupt buttons, multi-channel approval, safety mode, image gen delivery, `/model`, HTML formatting), WhatsApp (Baileys bridge, QR pairing, YouTube rich previews, Markdown-to-WhatsApp formatting, streaming), Discord (`discord.py`, DM-based, streaming, reactions, slash commands), Slack (`slack-bolt`, Socket Mode, streaming, file uploads), SMS (Twilio, webhook, MMS, tunnel integration); sidebar channel monitor with live status dots and activity times |
| **`tunnel.py`** | Provider-agnostic tunnel infrastructure — `TunnelProvider` ABC, `NgrokProvider` (pyngrok), `TunnelManager` singleton; auto-lifecycle for channel webhooks, orphan cleanup, graceful shutdown, main app tunnel toggle, Settings UI, health check |
| **`tools/x_tool.py`** | X (Twitter) integration — 13 tools (post/reply/retweet/like/unlike/delete/get/search/profile/followers/following), OAuth 2.0 PKCE flow, per-endpoint rate limiting, tier detection (Free/Basic/Pro), media uploads, thread posting, Settings Accounts panellation vocabulary and 0.80 confidence floor alignment), prompt-injection defence layers (instruction override, role impersonation, data exfiltration, encoding evasion, social engineering); memory guidelines with dedup, update, and cross-entity overwrite guard |
| **`memory_extraction.py`** | Background memory extraction — scans past conversations via LLM, extracts entities and relations as structured triples, two-pass dedup (entities with alias merging, then relations with subject-to-ID resolution), vague-type banning, relation pre-normalisation, cross-source merge protection (0.90 threshold), User entity pre-population, excludes active and workflow (⚡) threads, assistant message truncation (200 chars), 0.80 confidence floor, runs on startup + every 6 hours |
| **`skills.py`** | Skills engine — discovers, loads, and caches bundled skills, tool guides, and user skill definitions from `SKILL.md` files with YAML frontmatter; tool guides (skills with a `tools:` list) auto-activate when their linked tool is enabled and are always injected into the system prompt; manual skills are user-toggled and shown in the Skills tab; builds prompt text for injection; config persistence in `~/.thoth/skills_config.json` |
| **`bundled_skills/`** | 11 built-in manual skill packages (Brain Dump, Daily Briefing, Data Analyst, Deep Research, Humanizer, Knowledge Base, Meeting Notes, Proactive Agent, Self-Reflection, Task Automation, Web Navigator) — each a directory containing a `SKILL.md` instruction file |
| **`tool_guides/`** | 13 built-in tool guide packages (Browser, Calendar, Chart, Email, Filesystem, Math, Shell, Telegram, Tracker, Vision, Weather, Wiki, X) — auto-activated when their linked tool is enabled; invisible to the user in the Skills tab |
| **`tasks.py`** | Workflow engine — SQLite CRUD, APScheduler integration, 7 schedule types, template variable expansion, step-based pipelines (5 step types: Prompt, Condition, Approval, Subtask, Notify), conditional branching, approval gates, webhook triggers, task-completion triggers, concurrency groups, safety mode, sequential prompt execution, background runner with threading, channel delivery (any registered channel), per-task model override, persistent threads, notify-only mode, skills override, run history persistence, task stop/cancel, auto-migration from workflows.db, 5 default templates, per-task `allowed_commands` and `allowed_recipients` permission fields |
| **`notifications.py`** | Unified notification system — desktop notifications (plyer), sound effects, and in-app toast queue with `toast_type` support (positive/negative); error toasts render as persistent red banners; coordinates task completion chimes, timer alerts, and approval gate notifications |
| **`channels/`** | Messaging channel framework — `Channel` ABC with capability declarations, channel registry with auto-start and delivery routing, shared media pipeline (transcribe/analyze/extract/save), tool factory for auto-generated LangChain tools per channel, per-channel config store; Telegram adapter with voice/photo/document inbound, emoji reactions, interrupt buttons, multi-channel approval routing, safety mode enforcement, image gen delivery, `/model` command, and HTML formatting |
| **`tools/`** | 25 self-registering tool modules + base class + registry |
| **`plugins/`** | Plugin runtime — `PluginAPI` bridge, `PluginTool` base class, manifest validation, security scanner, dependency sandbox, state/secrets persistence, loader, installer, marketplace client, and settings/marketplace UI |
| **`static/`** | Bundled JS libraries — `vis-network.min.js` for knowledge graph visualization, `mermaid.min.js` for diagram rendering |

---

## Data Storage

All user data is stored in `~/.thoth/` (`%USERPROFILE%\.thoth\` on Windows):

```
~/.thoth/
├── threads.db              # Conversation history & LangGraph checkpoints
├── media/                  # Per-thread media files (images, future video) with .media.json sidecars
├── memory.db               # Knowledge graph — entities, relations, and memory data
├── memory_vectors/         # FAISS vector index for semantic memory search
├── memory_extraction_state.json  # Tracks last extraction run timestamp
├── extraction_journal.json # Memory extraction run log (threads scanned, entities saved)
├── dream_journal.json      # Dream Cycle operation log (cycle ID, summary, duration)
├── dream_rejections.json   # Dream Cycle 7-day rejection cache for inference pairs
├── api_keys.json           # API keys (Tavily, Wolfram, etc.)
├── cloud_config.json       # Cloud LLM provider keys and starred models
├── app_config.json         # Onboarding / firstauto-start, per-channel config for all 5 adapters, tunnel config)
├── inbox/                  # Inbound files received via messaging channels
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
├── x/                      # X (Twitter) OAuth tokens and auth stateolor preferences
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
├── installed_plugins/      # Marketplace-installed plugins
├── plugin_state.json       # Plugin enable/disable state and config values
├── plugin_secrets.json     # Plugin API key secrets (restricted file permissions)
└── kokoro/                 # Kokoro TTS model & voice data
```

> Override the data directory by setting the `THOTH_DATA_DIR` environment variable.

---

## Comparison with Other Tools

### Why not just use another open-source assistant?

Most open-source AI assistants are **developer tools disguised as products** — CLI-first, config-file-driven, Linux-only, and held together with Docker, YAML, and `.env` files. Getting them running means cloning repos, editing configs, wiring up databases, and debugging dependency conflicts before you can ask a single question.

**Thoth is different.** One-click installer, native desktop GUI, works out of the box on Windows and macOS, zero accounts required. Install it, launch it, start talking. No terminal expertise needed, no Docker, no YAML — just a private AI assistant that works.
7
### Why not just use ChatGPT?

| | ChatGPT / Claude / Gemini | Thoth |
|---|---|---|
| **Your data** | Stored on provider servers, subject to their privacy policies | Stays on your machine — always. With opt-in cloud models, only the current conversation is sent to the LLM provider; memories, files, and history never leave |
| **Conversations** | Owned by the provider — can be deleted, leaked, or used for training | Stored locally in SQLite, fully yours, exportable anytime |
| **Cost** | $20+/month per subscription | Free with local models. Cloud models use pay-per-token APIs — typically pennies per conversation with smart context trimming |
| **Memory** | Limited, opaque, provider-controlled | Personal knowledge graph — entities, relationships, visual explorer, fully yours |
| **Tools** | Sandboxed plugins, limited integrations | Direct access to your Gmail, Calendar, filesystem, shell, browser, webcam — 25 tools, 69 sub-operations, plus a plugin marketplace for third-party extensions |
| **Customisation** | Pick a model, write a system prompt | Swap models per conversation or per workflow, build advanced workflows with step pipelines, conditions, approval gates, and cron/daily/weekly/interval triggers, mix local and cloud models freely |
| **Voice** | Cloud-processed speech | Local Whisper STT + Kokoro TTS — never leaves your mic |
| **Availability** | Requires internet, subject to outages & rate limits | Local models work offline; cloud models available when connected |

> **Bottom line:** Cloud AI assistants rent you access to someone else's system. Thoth gives you **personal AI sovereignty** — run local models for full privacy, add cloud when you need it, and keep your data on your machine either way.

### How is Thoth different from OpenClaw?

[OpenClaw](https://github.com/openclaw/openclaw) is the most popular open-source personal AI assistant (~350k stars). It's a powerful multi-channel gateway built for developers comfortable in the terminal. Here's how the two compare:

| | Thoth | OpenClaw |
|---|---|---|79 sub-operations — Gmail, Calendar, Arxiv, YouTube, Wolfram Alpha, Plotly charts, wiki vault, habit tracker, image generation, X (Twitter)
| **Getting started** | **O**5 channels** — Telegram, WhatsApp (Baileys bridge), Discord, Slack (Socket Mode), SMS (Twilio) + Gmail. Tunnel manager for webhook channels. Sidebar channel monitor with live statusnpm install -g openclaw@latest` → CLI onboarding. Requires Node.js 24. Windows needs WSL2 (no native Windows support) |
| **Local AI (offline)** | **Local-first** — Ollama with 39 curated models out of the box. Works fully offline. Cloud is opt-in | Cloud-first design — requires an API key to start. Local model support through provider config |
| **Memory** | **Personal knowledge graph** — 10 entity types, typed directional relations, visual explorer, FAISS semantic search + 1-hop graph expansion, memory decay, orphan repair | Flat markdown files (`MEMORY.md` + daily notes) with semantic search. No structured graph |
| **Knowledge refinement** | **Dream Cycle** — 4-phase nightly engine: duplicate merging (≥0.93 similarity), description enrichment, relationship inference with hub diversity caps and rejection cache, confidence decay on stale relations. 3-layer anti-contamination system, dream journal | Dreaming (experimental) — Light/Deep/REM phases that promote short-term signals to long-term memory via scoring thresholds |
| **Document intelligence** | **Map-reduce LLM pipeline** — extracts structured entities and relations into the knowledge graph with source provenance. Curated 67-type relation vocabulary, entity caps, self-loop rejection. Supports PDF, DOCX, EPUB, HTML, Markdown | File read/write/edit operations in the workspace |
| **Wiki vault** | **Obsidian-compatible export** — one `.md` per entity with `[[wiki-links]]`, YAML frontmatter, and per-type indexes | Not available |
| **Voice** | **Fully local** — faster-whisper STT + Kokoro TTS with 10 voices. Audio never leaves your machine | ElevenLabs (cloud TTS) + system fallback. Voice Wake on macOS/iOS |
| **Health tracking** | **Built-in tracker** — medications, symptoms, exercise, mood, sleep, periods. Streak analysis, CSV export, Plotly charts | Not available |
| **Tools** | 25 tools / 69 sub-operations — Gmail, Calendar, Arxiv, YouTube, Wolfram Alpha, Plotly charts, wiki vault, habit tracker, image generation | ~20 built-in tools — exec, browser, web search, canvas, cron, image/music/video generation |
| **Messaging channels** | Telegram (voice, photo, documents, reactions, buttons) + Gmail. *Slack, Discord, WhatsApp, Teams coming soon* | **23+ channels** — WhatsApp, Telegram, Slack, Discord, Signal, iMessage, Teams, Matrix, IRC, and many more |
| **Autonomous agents** | **Advanced workflows** — step-based pipelines with conditions, approval gates, webhook triggers, concurrency groups, and per-workflow safety mode. Multiple run in parallel with their own persistent threads | Multi-agent routing with isolated sessions per sender/channel |
| **Desktop app** | Native window (pywebview) + system tray on **Windows & macOS**. One-click installers for both | macOS menu bar app. No native Windows app (WSL2 required). iOS & Android companion apps |
| **Canvas** | Mermaid diagrams and Plotly charts rendered inline | A2UI — agent-driven interactive visual workspace |
| **Plugins** | Sandboxed plugin marketplace with hot-reload and security scanning | npm plugin ecosystem + ClawHub skill registry. Large community catalog |
| **Privacy** | All data local. No account, no server, no telemetry. API keys stored locally — Thoth has no servers | Self-hosted gateway. Data stays on your machine. Some channel integrations require external services |
| **Cost** | **Free** with local models. Cloud: pay-per-token (pennies/conversation) | Free + open source. Requires a cloud API key to function |

> **In short:** OpenClaw is a powerful gateway for developers who want their AI assistant on every messaging platform. Thoth is built for people who want **personal AI sovereignty** — local-first intelligence, a structured knowledge graph that grows with you, one-click setup, and tools that work without touching a terminal. Different philosophies, both open source.
