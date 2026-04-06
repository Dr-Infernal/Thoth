<p align="center">
  <img src="docs/thoth_glyph_256.png" alt="Thoth" width="180">
</p>

<h1 align="center">𓁟 Thoth — Personal AI Sovereignty</h1>

<p align="center">
  <a href="https://github.com/siddsachar/Thoth/releases"><img src="https://img.shields.io/github/v/release/siddsachar/Thoth?style=flat&label=release&color=c9a227" alt="Release"></a>
  <a href="LICENSE"><img src="https://img.shields.io/github/license/siddsachar/Thoth?style=flat" alt="License"></a>
  <img src="https://img.shields.io/badge/platform-Windows%20%7C%20macOS-c9a227?style=flat" alt="Platform">
  <img src="https://img.shields.io/badge/tests-1133%20unit%20%7C%20155%20integration-brightgreen?style=flat" alt="Tests">
</p>

Thoth is a **local-first AI assistant built for personal AI sovereignty** — your models, your data, your rules. It combines a powerful ReAct agent with 25 integrated tools (70 sub-operations) — web search, email, calendar, file management, shell access, browser automation, vision, image generation, long-term memory with a personal knowledge graph, scheduled tasks, habit tracking, and more — plus a **plugin system** with a built-in marketplace and a **multi-channel messaging framework** (Telegram with full media support; more channels coming). Run everything locally via [Ollama](https://ollama.com/), or add opt-in cloud models (GPT, Claude, Gemini, and more) when you need frontier reasoning or don't have a GPU. Either way, your data — conversations, memories, documents, and history — stays on your machine.

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

> 📖 Every feature below is documented in full technical detail in [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

### 🤖 ReAct Agent Architecture

LangGraph-based autonomous agent with **25 tools / 70 sub-operations** — the agent decides which tools to call, how many times, and in what order. Real-time token streaming with thinking model support (DeepSeek-R1, Qwen3, QwQ — collapsible reasoning bubbles). Smart context management via tiktoken: auto-summarization at 80% capacity, proportional tool-output shrinking, and dynamic tool budgets that adapt to available headroom. Destructive actions require explicit confirmation; orphaned tool calls are auto-repaired; recursive loops are caught with a wind-down warning at 75%.

[Details →](docs/ARCHITECTURE.md#react-agent-architecture)

### 🧠 Long-Term Memory & Knowledge Graph

Thoth builds a **personal knowledge graph** — entities (person, place, event, preference, fact, project, organisation, concept, skill, media) linked by typed directional relations (`Dad --[father_of]--> User`), with alias resolution, auto-linking on save, memory decay, and background orphan repair. The agent can save, search, link, and explore memories through natural conversation. Graph-enhanced auto-recall retrieves semantically similar entities via FAISS and expands 1 hop in the NetworkX graph before every LLM call. An interactive **Knowledge tab** visualizes the full graph with search, entity-type filters, ego-graph toggle, and clickable detail cards. Background extraction produces structured triples with deterministic cross-category dedup.

[Details →](docs/ARCHITECTURE.md#long-term-memory--knowledge-graph)

### 📚 Wiki Vault (Obsidian Export)

Export the entire knowledge graph as an **Obsidian-compatible markdown vault** — one `.md` file per entity with YAML frontmatter, `[[wiki-links]]`, and per-type indexes. Entities grouped by type (`wiki/person/`, `wiki/project/`, …); sparse entities roll up into index files. Live export on save/delete, full-text search, and conversation export. The agent has 5 sub-tools (`wiki_search`, `wiki_read`, `wiki_rebuild`, `wiki_stats`, `wiki_export_conversation`) to interact with the vault directly.

[Details →](docs/ARCHITECTURE.md#wiki-vault)

### 🌙 Dream Cycle (Nightly Knowledge Refinement)

A background daemon that refines the knowledge graph during idle hours — **merging duplicates** (≥0.93 similarity), **enriching thin descriptions** from conversation context, and **inferring missing relationships** between co-occurring entities. Three-layer anti-contamination system prevents cross-entity fact-bleed: sentence-level excerpt filtering, deterministic post-enrichment validation, and hardened prompts. Configurable 1–5 AM window; all operations logged to a dream journal viewable in the Activity tab.

[Details →](docs/ARCHITECTURE.md#dream-cycle)

### 📄 Document Knowledge Extraction

Uploaded documents are processed through a **map-reduce LLM pipeline** that extracts structured knowledge into the graph. Documents are split into windows, summarized, then reduced into a coherent article; core entities and relations are extracted with full source provenance. Supports PDF, DOCX, TXT, Markdown, HTML, and EPUB. Live progress pill in the status bar with phase indicator and stop button. Per-document cleanup removes vector store entries and all extracted entities.

[Details →](docs/ARCHITECTURE.md#document-knowledge-extraction)

### 🤖 Brain Model & Cloud Models

Run **fully local** via Ollama (39 curated tool-calling models) or connect **OpenAI / OpenRouter** for 100+ cloud models (GPT, Claude, Gemini) — switchable per-thread and per-task from the GUI. First-launch wizard offers Local or Cloud paths; star favorites for quick access; cloud vision models are auto-detected. Privacy controls disable memory extraction and auto-recall for cloud threads. Smart context trimming reduces token usage and cloud API costs.

[Details →](docs/ARCHITECTURE.md#brain-model--cloud-models)

### 🎤 Voice Input & 🔊 Text-to-Speech

Toggle-based voice input with local **faster-whisper** STT (4 model sizes, CPU-only int8) — no cloud APIs. Neural TTS via **Kokoro** with 10 voices (US/British, male/female), streaming sentence-by-sentence with automatic mic gating during playback. Combine both for a fully hands-free conversational experience.

[Details →](docs/ARCHITECTURE.md#voice-input--text-to-speech)

### 🖥️ Shell Access

Full shell access with **3-tier safety** — safe commands (`ls`, `git status`) auto-execute, moderate commands (`rm`, `pip install`) require confirmation, dangerous commands (`shutdown`, `reboot`, `mkfs`) are blocked outright. Persistent sessions per thread, inline terminal panel, command history saved to disk. Background tasks support per-task command prefix allowlists.

[Details →](docs/ARCHITECTURE.md#shell-access)

### 🌐 Browser Automation

Autonomous browsing in a **visible Chromium window** — navigate, click, type, scroll, and manage tabs through natural conversation. Accessibility-tree snapshots with numbered element references; per-thread tab isolation; persistent login profile; smart snapshot compression for context efficiency; crash recovery and automatic browser detection (Chrome → Edge → Playwright).

[Details →](docs/ARCHITECTURE.md#browser-automation)

### 👁️ Vision

Camera capture, screen capture, and **workspace image file analysis** via local or cloud vision models. Cloud models with vision capability (GPT-4o, Claude) are auto-detected. Images displayed inline in chat; configurable vision model selection.

[Details →](docs/ARCHITECTURE.md#vision)

### ⚡ Tasks & Scheduling

Unified task engine powered by **APScheduler** with 7 schedule types (daily, weekly, weekdays, weekends, interval, cron, one-shot delay). Template variables (`{{date}}`, `{{time}}`, `{{task_id}}`), multi-step prompt chaining, channel delivery (Telegram/Email), per-task model override, and configurable background permissions. Monitoring/polling patterns let the agent self-disable when conditions are met. Home-screen dashboard with task tiles, activity monitor, and run history.

[Details →](docs/ARCHITECTURE.md#tasks--scheduling)

### 📬 Messaging Channels

A generic **Channel ABC** lets any messaging platform plug into Thoth — channels declare capabilities (photo, voice, documents, reactions, buttons) and the system auto-generates tools and settings UI for each one. **Telegram** is the first full-featured channel: inbound voice transcription (faster-whisper), photo analysis (Vision), document handling with text extraction (PDF/CSV/JSON), emoji reactions (👀/👍/💔) for real-time status, inline keyboard buttons for interrupt approval, and image generation delivery. The agent can proactively send messages, photos, and documents to any registered channel.

[Details →](docs/ARCHITECTURE.md#messaging-channels)

### 🖼️ Image Generation

Generate and edit images via **OpenAI/OpenRouter** — rendered inline in chat and delivered to Telegram. Supports `gpt-image-1`, `gpt-image-1.5`, and `gpt-image-1-mini` with configurable size and quality. Edit existing images by referencing the last generation, a pasted attachment, or a file path. Model selector in Settings → Models.

[Details →](docs/ARCHITECTURE.md#image-generation)

### 🔌 Plugin System & Marketplace

A sandboxed, hot-reloadable **plugin architecture** lets anyone add new tools and skills without touching core code. Plugins declare metadata in `plugin.json`, are security-scanned (no `eval`/`exec`/`subprocess`), and run in a dependency-safe sandbox. A built-in **marketplace** lets users browse, install, update, and uninstall plugins from a curated GitHub-hosted catalog. Plugin settings, API keys, enable/disable toggles, and per-plugin config dialogs are all managed from Settings → Plugins.

[Details →](docs/ARCHITECTURE.md#plugin-system--marketplace)

### 📋 Habit & Health Tracker

Conversational tracking for medications, symptoms, exercise, periods, mood, sleep — *"I took my Lexapro"*, *"Headache level 6"*. Auto-detection with confirmation; 7 built-in analyses (adherence, streaks, numeric stats, trends, co-occurrence, cycle estimation); CSV export chains to Plotly charts. All data in local SQLite, excluded from the memory system.

[Details →](docs/ARCHITECTURE.md#habit--health-tracker)

### 🖥️ Desktop App

Native window via **pywebview** with system tray, splash screen, right-click context menu, and auto-restart. First-launch setup wizard (Local or Cloud). Self-contained one-click installers for **Windows** (Inno Setup) and **macOS** (.app with code signing + notarization) — CI/CD pipeline automates builds, signing, and GitHub Releases.

[Details →](docs/ARCHITECTURE.md#desktop-app)

### 💬 Chat & Conversations

Multi-turn threads with LangGraph checkpointer, auto-naming, per-thread model switching, and export (Markdown, text, PDF via Playwright). Attach images, PDFs, CSV, Excel, JSON — plus clipboard paste and drag-and-drop. Images persist across reloads via sidecar files. Inline rendering: **Plotly charts**, **Mermaid diagrams** (flowchart, sequence, state, ER, Gantt, mindmap), **YouTube embeds**, and syntax-highlighted code. **Status monitor panel** with animated avatar, 17 health-check pills, OAuth token monitoring, and one-click diagnosis.

[Details →](docs/ARCHITECTURE.md#chat--conversations)

### 🔔 Notifications

Desktop notifications, distinct audio chimes (task completion, timer alerts), and contextual in-app toasts — success auto-dismisses, errors persist as red banners. Unified `notify()` call across all channels.

[Details →](docs/ARCHITECTURE.md#notifications)

### 🧩 Bundled Skills

**10 reusable instruction packs** injected into the system prompt when enabled — each a `SKILL.md` with YAML frontmatter. Toggle from Settings; create custom skills via the in-app editor or `~/.thoth/skills/`.

| Skill | Description |
|-------|-------------|
| 🧠 **Brain Dump** | Capture unstructured thoughts → organized notes |
| 📊 **Data Analyst** | Dataset analysis, stats, and Plotly charts |
| ☀️ **Daily Briefing** | Weather, calendar, and news roundup |
| 🔬 **Deep Research** | Multi-source research → structured report |
| 🗣️ **Humanizer** | Natural human tone — no AI-speak |
| 📋 **Meeting Notes** | Raw notes → actionable minutes |
| 🎯 **Proactive Agent** | Anticipate needs, self-check at milestones |
| 🪞 **Self-Reflection** | Review memory for gaps and contradictions |
| ⚙️ **Task Automation** | Design effective scheduled workflows |
| 🌐 **Web Navigator** | Strategic browser automation patterns |

[Details →](docs/ARCHITECTURE.md#bundled-skills)

---

## 🔧 Tools (25 Tools / 70 Sub-tools)

Thoth's agent has access to 25 tools that expose 70 individual operations to the model. Tools can be enabled/disabled from the Settings panel.

### Search & Knowledge

| Tool | Description | API Key? |
|------|-------------|----------|
| **🔍 Web Search** | Live web search via Tavily for current events, news, real-time data | `TAVILY_API_KEY` |
| **🦆 DuckDuckGo** | Free web search — no API key needed | None |
| **🌐 Wikipedia** | Encyclopedic knowledge with contextual compression | None |
| **📚 Arxiv** | Academic paper search — newest-first sorting, full-text HTML links, arXiv query syntax (`ti:`, `au:`, `abs:`, `cat:`) | None |
| **▶️ YouTube** | Search videos + fetch full transcripts/captions | None |
| **🔗 URL Reader** | Fetch and extract text content from any URL | None |
| **📄 Documents** | Semantic search over your uploaded files (FAISS vector store) | None |
| **📚 Wiki Vault** | Search, read, rebuild, and export the knowledge graph as an Obsidian markdown vault | None |

### Productivity

| Tool | Description | API Key? |
|------|-------------|----------|
| **📧 Gmail** | Search, read, draft, and send emails with file attachments (Google OAuth) | OAuth credentials |
| **📅 Google Calendar** | View, create, update, move, and delete events (Google OAuth) | OAuth credentials |
| **📁 Filesystem** | Sandboxed file operations — read, write, copy, move, delete within a workspace folder; reads PDF, CSV, Excel (.xlsx/.xls), JSON/JSONL, TSV, and image files; images displayed inline in chat; structured data files return schema + stats + preview via pandas; PDF export via `export_to_pdf` (Playwright with fpdf2 fallback) | None |
| **🖥️ Shell** | Execute shell commands with 3-tier safety (safe/moderate/blocked); persistent sessions per thread; user approval for destructive commands; inline terminal panel | None |
| **🌐 Browser** | Autonomous web browsing in a visible Chromium window — navigate, click, type, scroll, snapshot, back, tab management; accessibility-tree snapshots with numbered element references; persistent profile for logins | None |
| **📋 Tasks** | Create, list, update, delete, and run scheduled tasks — 7 trigger types (daily, weekly, weekdays, weekends, interval, cron, delay), channel delivery, per-task model override | None |
| **📋 Tracker** | Habit/health tracker — log meds, symptoms, exercise, periods; streak, adherence, trend analysis; CSV export | None |
| **📬 Telegram** | Send messages, photos, and documents to any Telegram chat; receive voice, photo, and document messages with transcription, analysis, and text extraction | Bot API token |
| **🖼️ Image Generation** | Generate images from text prompts and edit existing images via OpenAI/OpenRouter; rendered inline in chat and deliverable to channels | Cloud API key |

### Computation & Analysis

| Tool | Description | API Key? |
|------|-------------|----------|
| **🧮 Calculator** | Safe math evaluation — arithmetic, trig, logs, factorials, combinatorics | None |
| **🔢 Wolfram Alpha** | Advanced computation, symbolic math, unit conversion, scientific data | `WOLFRAM_ALPHA_APPID` |
| **🌤️ Weather** | Current conditions and multi-day forecasts via Open-Meteo | None |
| **👁️ Vision** | Camera capture, screen capture, and workspace image file analysis via vision model | None |
| **🧠 Memory** | Save, search, update, delete, **link**, and **explore** memories in the knowledge graph | None |
| **🔍 Conversation Search** | Search past conversations by keyword or list all saved threads | None |
| **🖥️ System Info** | OS, CPU, RAM, disk space, IP addresses, battery, and top processes | None |
| **📊 Chart** | Interactive Plotly charts — bar, line, scatter, pie, histogram, box, area, heatmap from data files; PNG export via `save_to_file` | None |

### Safety & Permissions

- **Destructive operations require confirmation**: `workspace_file_delete`, `workspace_move_file`, `run_command` (moderate-risk), `send_gmail_message`, `move_calendar_event`, `delete_calendar_event`, `delete_memory`, `tracker_delete`, `task_delete`
- **Filesystem is sandboxed**: only the configured workspace folder is accessible (defaults to `~/Documents/Thoth`, auto-created on first use)
- **Shell commands are safety-classified**: safe (auto), moderate (confirm), blocked (rejected); high-risk commands like `shutdown`, `reboot`, `mkfs` are blocked outright; moderate commands in background tasks require per-task command prefix allowlists
- **Browser tabs are isolated per thread**: each chat or background task gets its own browser tab; tabs are cleaned up on task completion or thread deletion
- **Background task permissions are configurable per-task**: shell command prefixes and email recipients can be allowlisted in the task editor
- **Gmail/Calendar operations are tiered**: read, compose/write, and destructive tiers can be toggled independently
- **Tools can be individually disabled** from Settings to reduce model decision complexity

---

### How does Thoth compare to OpenClaw?

[OpenClaw](https://github.com/openclaw/openclaw) is the most popular open-source personal AI assistant (~350k stars). It's a powerful multi-channel gateway built for developers comfortable in the terminal. Here's how the two compare:

| | Thoth | OpenClaw |
|---|---|---|
| **Getting started** | **One-click installer** (`.exe` / `.dmg`) — download, run, done. Built-in setup wizard, no terminal required | `npm install -g openclaw@latest` → CLI onboarding. Requires Node.js 24. Windows needs WSL2 (no native Windows support) |
| **Local AI (offline)** | **Local-first** — Ollama with 39 curated models out of the box. Works fully offline. Cloud is opt-in | Cloud-first design — requires an API key to start. Local model support through provider config |
| **Memory** | **Personal knowledge graph** — 10 entity types, typed directional relations, visual explorer, FAISS semantic search + 1-hop graph expansion, memory decay, orphan repair | Flat markdown files (`MEMORY.md` + daily notes) with semantic search. No structured graph |
| **Knowledge refinement** | **Dream Cycle** — nightly duplicate merging (≥0.93 similarity), description enrichment from conversation context, relationship inference, 3-layer anti-contamination system, dream journal | Dreaming (experimental) — Light/Deep/REM phases that promote short-term signals to long-term memory via scoring thresholds |
| **Document intelligence** | **Map-reduce LLM pipeline** — extracts structured entities and relations into the knowledge graph with source provenance. Supports PDF, DOCX, EPUB, HTML, Markdown | File read/write/edit operations in the workspace |
| **Wiki vault** | **Obsidian-compatible export** — one `.md` per entity with `[[wiki-links]]`, YAML frontmatter, and per-type indexes | Not available |
| **Voice** | **Fully local** — faster-whisper STT + Kokoro TTS with 10 voices. Audio never leaves your machine | ElevenLabs (cloud TTS) + system fallback. Voice Wake on macOS/iOS |
| **Health tracking** | **Built-in tracker** — medications, symptoms, exercise, mood, sleep, periods. Streak analysis, CSV export, Plotly charts | Not available |
| **Tools** | 25 tools / 70 sub-operations — Gmail, Calendar, Arxiv, YouTube, Wolfram Alpha, Plotly charts, wiki vault, habit tracker, image generation | ~20 built-in tools — exec, browser, web search, canvas, cron, image/music/video generation |
| **Messaging channels** | Telegram (voice, photo, documents, reactions, buttons) + Gmail. *Slack, Discord, WhatsApp, Teams coming soon* | **23+ channels** — WhatsApp, Telegram, Slack, Discord, Signal, iMessage, Teams, Matrix, IRC, and many more |
| **Autonomous agents** | **Background tasks as sub-agents** — each task overrides model, skills, and permissions independently. Multiple run in parallel with their own persistent threads | Multi-agent routing with isolated sessions per sender/channel |
| **Desktop app** | Native window (pywebview) + system tray on **Windows & macOS**. One-click installers for both | macOS menu bar app. No native Windows app (WSL2 required). iOS & Android companion apps |
| **Canvas** | Mermaid diagrams and Plotly charts rendered inline | A2UI — agent-driven interactive visual workspace |
| **Plugins** | Sandboxed plugin marketplace with hot-reload and security scanning | npm plugin ecosystem + ClawHub skill registry. Large community catalog |
| **Privacy** | All data local. No account, no server, no telemetry. API keys stored locally — Thoth has no servers | Self-hosted gateway. Data stays on your machine. Some channel integrations require external services |
| **Cost** | **Free** with local models. Cloud: pay-per-token (pennies/conversation) | Free + open source. Requires a cloud API key to function |

> **In short:** OpenClaw is a powerful gateway for developers who want their AI assistant on every messaging platform. Thoth is built for people who want **personal AI sovereignty** — local-first intelligence, a structured knowledge graph that grows with you, one-click setup, and tools that work without touching a terminal. Different philosophies, both open source.

> For comparisons with ChatGPT and other cloud assistants, see [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md#comparison-with-other-tools).

---

## 🏗️ Architecture

```
┌──────────────────────────────────────────────────────────────────────┐
│                    NiceGUI Frontend (app.py + ui/ package)              │
│  ┌────────────┐  ┌──────────────────────┐  ┌───────────────────┐   │
│  │  Sidebar   │  │   Chat Interface     │  │   Settings Dialog │   │
│  │  Threads   │  │   Streaming Tokens   │  │   13 Tabs         │   │
│  │  Controls  │  │   Tool Status        │  │   Tool Config     │   │
│  │ Knowledge  │  │ Knowledge Graph View │  │   Cloud Settings  │   │
│  └────────────┘  └──────────────────────┘  └───────────────────┘   │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │  Status Monitor — Avatar · 17 Health Pills · Diagnosis Btn  │   │
│  └──────────────────────────────────────────────────────────────┘   │
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
│   70 LangChain sub-tools from 25 registered tool modules            │
│   + plugin tools + auto-generated channel tools                     │
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

> 📖 **Module descriptions, data storage layout, and full system internals →** [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md#core-modules)

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

> **Note:** The default local model (`qwen3:14b`, ~9 GB) runs well on CPU with 16 GB RAM, but a GPU makes responses significantly faster. Smaller models like `qwen3:8b` (~5 GB) work on 8 GB RAM machines.

### For Cloud Models Only (No Local GPU Needed)

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

1. Download **[ThothSetup_3.12.0.exe](https://github.com/siddsachar/Thoth/releases/latest)** from the latest release
2. Run the installer — it installs Python, Ollama, and all dependencies automatically
3. Launch **Thoth** from the Start Menu or Desktop shortcut

### macOS

1. Download **[Thoth-3.12.0-macOS-arm64.dmg](https://github.com/siddsachar/Thoth/releases/latest)** from the latest release
2. Open the DMG and drag **Thoth.app** into the **Applications** folder
3. Launch **Thoth** from Applications or Launchpad
   - First run may prompt "Thoth is an app downloaded from the internet" → click **Open**
   - First run installs Homebrew (if needed), Python, Ollama, and all dependencies automatically
   - Subsequent launches skip installation and start in ~3 seconds

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
   python app.py
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

Configure cloud keys in **⚙️ Settings → ☁️ Cloud** tab. Keys are stored locally in `~/.thoth/cloud_config.json` — never sent to Thoth's servers (there are none).

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

**Local models (default):** All LLM inference runs on your machine via Ollama. Documents, memories, and conversations stored locally in `~/.thoth/`. External network calls only when using online tools (web search, Gmail, Calendar) — each individually disableable. No telemetry, no tracking.

**Cloud models (opt-in):** Only the current conversation is sent to the LLM provider (OpenAI/OpenRouter). Memories, knowledge graph, documents, files, and other conversations never leave your machine. Your API key connects directly to the provider — Thoth has no servers and no middleman.

**Always:** API keys stored locally; no Thoth account required; no sign-up; no server to phone home to. Tools can be individually disabled to control what the agent can access.

---

## 📄 License

Apache 2.0 — see [LICENSE](LICENSE) for details.

---

## 🙏 Acknowledgements

Built with [NiceGUI](https://nicegui.io/), [LangGraph](https://langchain-ai.github.io/langgraph/), [LangChain](https://python.langchain.com/), [Ollama](https://ollama.com/), [FAISS](https://github.com/facebookresearch/faiss), [Kokoro TTS](https://github.com/thewh1teagle/kokoro-onnx), [faster-whisper](https://github.com/SYSTRAN/faster-whisper), [HuggingFace](https://huggingface.co/), and [tiktoken](https://github.com/openai/tiktoken).
