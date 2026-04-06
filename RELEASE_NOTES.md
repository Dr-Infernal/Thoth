# 𓁟 Thoth — Release Notes

---

## v3.12.0 — Plugin System, Multi-Channel Architecture & Image Generation

Thoth gains a full **plugin architecture** with a built-in **marketplace**, a **multi-channel messaging framework** that abstracts Telegram behind a generic Channel ABC (ready for Slack, Discord, and more), a complete **Telegram upgrade** with voice transcription, photo analysis, document extraction, and emoji reactions, an **image generation tool** powered by OpenAI/OpenRouter, a **Google Account setup wizard**, and expanded **task delivery** to any channel. Ships with **168 new tests** across 8 sections, bringing the total to **1133 PASS**, 0 FAIL, 2 WARN.

### 🔌 Plugin Architecture

A self-contained plugin runtime in `plugins/` handles the full lifecycle — discovery, validation, sandboxing, loading, and teardown.

- **Plugin API** — `PluginAPI` bridge object and `PluginTool` base class are the only core imports a plugin needs; provides `get_config()`, `set_config()`, `get_secret()`, `set_secret()`, `register_tool()`, `register_skill()`
- **Manifest system** — each plugin declares metadata in `plugin.json`: ID, version, author, description, tools, skills, settings schema, API keys, and Python dependencies; validated against a strict schema (ID regex, semver, required fields)
- **Security sandbox** — static scan blocks `eval()`, `exec()`, `os.system()`, `subprocess`, and `__import__()`; import guard prevents loading from core modules (`tools`, `agent`, `models`, `ui`); `register()` call has a 5-second timeout
- **Dependency safety** — freezes core dependency versions before installing plugin deps; blocks downgrades that could break Thoth
- **State persistence** — enable/disable state, config values, and API key secrets stored in `plugin_state.json` and `plugin_secrets.json` (restricted file permissions) under `~/.thoth/`
- **Hot reload** — "Reload Plugins" button in Settings clears the registry and re-runs discovery without restarting the app; agent cache is invalidated automatically
- **Skill auto-discovery** — `SKILL.md` files in a plugin's `skills/` directory are detected and injected into the agent's system prompt alongside built-in skills
- **Version gating** — plugins declare `min_thoth_version`; loader rejects incompatible plugins with a clear error message

### 🏪 Plugin Marketplace

A browse-and-install marketplace powered by a GitHub-hosted `index.json` catalog.

- **Marketplace client** — fetches and caches the plugin index with TTL-based refresh; provides search, tag filtering, and update detection
- **Browse dialog** — NiceGUI dialog with search bar, tag filter pills, and one-click install buttons
- **Install/update/uninstall** — downloads plugin archives, validates before install, manages `~/.thoth/installed_plugins/`; duplicate installs rejected; security violations block installation
- **Update detection** — `check_updates()` compares installed versions against the marketplace index

### ⚙️ Plugin Settings UI

A dedicated **Plugins** tab in Settings for managing all installed plugins.

- **Card grid** — each plugin rendered as a card with icon, name, version badge, description, tool/skill count badges, and enable/disable toggle
- **Missing API key warnings** — cards show a warning badge when required secrets are not configured
- **Per-plugin config dialog** — opens plugin details with API key inputs, settings controls, tools/skills list, and actions (update, uninstall)
- **Empty state** — "No plugins installed" with a marketplace call-to-action

### 🔗 Plugin API v2

Plugin tools gain richer return types and safety metadata.

- **`_run()` method** — plugins can now override `_run()` instead of `execute()` for a cleaner interface; base class handles argument parsing and error wrapping
- **`background_allowed` flag** — plugin tools declare whether they are safe to run in background task workflows; defaults to `False`
- **`destructive` flag** — marks tools that perform irreversible actions; gated from background execution unless explicitly allowed
- **Rich returns** — tool results can include structured data (dicts, lists) that the agent interprets contextually

### 🖼️ Image Generation Tool

Generate and edit images via OpenAI/OpenRouter, rendered inline in chat.

- **`generate_image`** — creates images from text prompts; supports `gpt-image-1`, `gpt-image-1.5`, `gpt-image-1-mini` models with configurable size and quality
- **`edit_image`** — modifies existing images; sources: `"last"` (most recent generation), filename (from attachment cache), or file path on disk
- **Side-channel rendering** — `_last_generated_image` passed to UI streaming layer for inline display; cleared after use
- **Attachment cache** — pasted/attached images stored in `_image_cache` (populated by `ui/streaming.py`) so the agent can reference them by filename
- **Model selector** — configurable in Settings → Models; default `openai/gpt-image-1.5`

### 📡 Channel Architecture (Multi-Channel Foundation)

A generic channel abstraction that decouples messaging from any single platform.

- **`Channel` ABC** — abstract base class all channel adapters inherit from; lifecycle methods `start()`, `stop()`, `is_configured()`, `is_running()`; outbound methods `send_message()`, `send_photo()`, `send_document()`, `send_approval_request()`
- **`ChannelCapabilities`** — declarative feature flags per channel (photo in/out, voice in, document in, buttons, streaming, reactions, slash commands); UI and tool factory read capabilities to auto-generate tooling
- **`ConfigField`** — describes user-configurable fields that render automatically in the Settings UI
- **Channel registry** — `register()`, `all_channels()`, `running_channels()`, `configured_channels()`; central routing via `deliver(channel_name, target, text)` with validation
- **Shared media pipeline** — `channels/media.py` provides `transcribe_audio()` (faster-whisper), `analyze_image()` (Vision service), `extract_document_text()` (PDF/CSV/JSON/plain-text), and `save_inbound_file()` — reusable by any channel
- **Tool factory** — `channels/tool_factory.py` auto-generates LangChain tools (`send_{name}_message`, `send_{name}_photo`, `send_{name}_document`) for each registered channel based on its capabilities; Pydantic input schemas; multi-strategy file path resolution
- **Channel config** — `channels/config.py` provides per-channel key-value store in `~/.thoth/channels_config.json`

### 📱 Telegram Upgrade

Telegram evolves from a basic text relay into a full-featured channel with rich media handling.

- **Voice messages** — inbound voice/audio transcribed via faster-whisper through the shared media pipeline; transcript sent to agent as user text
- **Photo messages** — inbound photos analyzed via Vision service; analysis sent to agent with optional caption
- **Document handling** — inbound documents saved to `~/.thoth/inbox/`, text extracted (PDF, CSV, JSON, plain text), file path + extracted content + caption sent to agent as one message
- **Image generation delivery** — `_grab_generated_image()` retrieves the last generated image from the image gen side-channel and sends it as a photo in Telegram
- **Emoji reactions** — real-time status feedback using Telegram's native reaction API: 👀 (processing), 👍 (success), 💔 (error); graceful fallback if bot lacks permission
- **Interrupt approval** — tool calls requiring human approval render as inline keyboard buttons in Telegram (Approve / Deny)
- **Auto-recovery** — handles orphaned tool calls gracefully; offers fresh thread on persistent failures
- **Bot commands** — registered with BotFather for discoverability

### 🔑 Google Account Setup Wizard

A unified setup flow for Google OAuth (Gmail + Calendar) in the Settings UI.

- **Step-by-step wizard** — guides users through creating OAuth credentials, downloading `credentials.json`, and completing the authorization flow
- **Token health checks** — periodic validation (every 6 hours) with silent refresh; desktop notifications on token expiry
- **Unified section** — Gmail and Calendar OAuth managed together under a single "Google Account" settings section

### 📋 Task System Enhancements

- **Delivery channels** — tasks can route results to Telegram (or future channels) via `delivery_channel` / `delivery_target` fields with validation
- **Model override** — per-task LLM selection via `model_override` field
- **Persistent threads** — `persistent_thread_id` reuses the same conversation thread across task runs
- **Notify-only mode** — `notify_only` flag fires a notification without agent invocation
- **Skills override** — `skills_override` for per-task skill selection
- **Schema migration** — new columns added to tasks table with automatic migration from old `workflows.db`

### 🔗 Core Integration

The plugin system and channel framework touch a minimal set of core files.

- **`app.py`** — calls `load_plugins()` at startup; auto-starts configured channels; periodic OAuth token health check (every 6 hours)
- **`agent.py`** — injects plugin tools + channel tools into the LangChain tools list; plugin skills into the system prompt; `clear_agent_cache()` exported for plugin/channel reload
- **`ui/settings.py`** — Plugins tab, marketplace dialog, Google Account wizard, channel configuration sections

### 🐛 Bug Fixes

- **Telegram reactions not appearing** — 🔄/✅/❌ are not in Telegram's supported reaction set; swapped to 👀/👍/💔 which are supported natively
- **Image generation not shown in Telegram** — `_grab_generated_image()` now retrieves the side-channel image and sends it as a photo
- **"Tool limit reached" false message** — misleading error when tool calls completed normally; message removed
- **Document text extraction for Telegram** — inbound documents now have text extracted and included in the agent message
- **Plugin dependency install crash** — `install_dependencies()` returns `tuple[bool, str]` but installer called `.ok`/`.conflicts` on it; fixed with proper tuple unpacking
- **No auto-reload after marketplace install** — installed plugins now trigger full plugin reload + agent cache clear so tools are available immediately
- **Plugin tools not reaching agent after reload** — agent cache key only includes core tool names; `clear_agent_cache()` now called in both manual reload and marketplace install flows

### 🧪 Tests

- **168 new tests** across 8 sections (49–56), bringing the total to **1133 PASS**, 0 FAIL, 2 WARN
- **Section 49: Plugin System** (25 tests) — imports, manifest validation, PluginAPI, PluginTool, state, secrets, registry, security scan, full lifecycle, broken plugin handling, disabled plugins, skills prompt, unregister, state cleanup, agent/app source verification
- **Section 50: Plugin Settings UI** (7 tests) — UI module imports, `_get_missing_keys` logic, callability checks, settings wiring, AST parse validation
- **Section 51: Marketplace & Installer** (19 tests) — marketplace parse/search/tags/entries, installer install/update/uninstall, duplicate rejection, security violation blocking, update detection
- **Section 52: Image Generation Tool** (31 tests) — model registry, provider detection, input schemas, generate/edit tool creation, side-channel image retrieval, attachment cache, base64 data-URI rendering, config parsing
- **Section 53: Plugin API v2** (17 tests) — `_run()` override, `background_allowed`/`destructive` flags, rich return types, backward compatibility with `execute()`
- **Section 54: Google Account Setup** (17 tests) — OAuth wizard flow, token validation, credential file handling, unified settings section, periodic health check
- **Section 55: Channel Infrastructure** (26 tests) — Channel ABC, ChannelCapabilities, ConfigField, registry lifecycle, media pipeline (transcribe/analyze/extract), tool factory generation, delivery routing and validation
- **Section 56: Telegram Phase 1** (26 tests) — voice/photo/document inbound handling, reaction emoji (👀/👍/💔), image gen delivery, interrupt buttons, auto-recovery, bot command registration

### 🔄 Other Changes

- **License** — switched from MIT to Apache 2.0 across the entire project
- **`channels/email.py` removed** — replaced by the generic channel architecture
- **`ui/render.py`** — `render_image_with_save()` for inline image thumbnails with download; `autolink_urls()` for bare URL wrapping
- **`ui/streaming.py`** — image generation side-channel capture; tool result image extraction pipeline
- **`ui/helpers.py`** — thread reload now filters empty-content AI messages that caused rendering errors

### 📁 Files Changed

| File | Change |
|------|--------|
| **`plugins/__init__.py`** | **New** — Package init; re-exports `load_plugins` and `get_load_summary` |
| **`plugins/api.py`** | **New** — Plugin author API: `PluginAPI` bridge and `PluginTool` base class |
| **`plugins/loader.py`** | **New** — Plugin discovery, validation, security scan, loading with timeout |
| **`plugins/manifest.py`** | **New** — Manifest parser and schema validator for `plugin.json` |
| **`plugins/registry.py`** | **New** — Plugin tool/skill registry with collision detection |
| **`plugins/state.py`** | **New** — State persistence for enable/disable, config, and secrets |
| **`plugins/sandbox.py`** | **New** — Dependency safety: freeze core deps, block downgrades |
| **`plugins/installer.py`** | **New** — Install, update, uninstall; fixed tuple unpacking in `_install_plugin_deps()` |
| **`plugins/marketplace.py`** | **New** — Marketplace client: fetch index, search, check updates |
| **`plugins/ui_settings.py`** | **New** — Plugins tab: card grid, reload button, missing key warnings; `clear_agent_cache()` on reload |
| **`plugins/ui_plugin_dialog.py`** | **New** — Per-plugin config dialog: details, API keys, settings, actions |
| **`plugins/ui_marketplace.py`** | **New** — Marketplace browse dialog; `_reload_plugins_and_agent()` auto-reload after install |
| **`channels/base.py`** | **New** — Channel ABC, `ChannelCapabilities`, `ConfigField` |
| **`channels/registry.py`** | **New** — Channel registry: register, discover, route, validate delivery |
| **`channels/media.py`** | **New** — Shared media pipeline: transcribe, analyze, extract, save |
| **`channels/tool_factory.py`** | **New** — Auto-generate LangChain tools per channel from capabilities |
| **`channels/config.py`** | Per-channel key-value config store |
| **`channels/telegram.py`** | Full upgrade: voice/photo/document inbound, reactions, image gen delivery, interrupt buttons |
| **`channels/email.py`** | **Removed** — replaced by generic channel architecture |
| **`tools/image_gen_tool.py`** | **New** — Image generation + editing via OpenAI/OpenRouter with side-channel rendering |
| **`tools/__init__.py`** | Added `image_gen_tool` import for registry auto-registration |
| **`app.py`** | Plugin loading, channel auto-start loop, periodic OAuth health check |
| **`agent.py`** | Plugin + channel tool injection; `clear_agent_cache()` export; background workflow gating |
| **`tasks.py`** | Delivery channels, model override, persistent threads, notify-only, skills override, schema migration |
| **`ui/settings.py`** | Plugins tab, marketplace dialog, Google Account wizard, channel config sections |
| **`ui/render.py`** | `render_image_with_save()`, `autolink_urls()` for inline images and URL linking |
| **`ui/streaming.py`** | Image gen side-channel capture, tool result image extraction |
| **`ui/helpers.py`** | Thread reload filters empty-content AI messages |
| **`ui/chat.py`** | Minor fix for drag-drop handler |
| **`ui/home.py`** | Removed legacy email status references |
| **`ui/status_checks.py`** | Removed legacy email health-check pill |
| **`LICENSE`** | MIT → Apache 2.0 |
| **`NOTICE`** | **New** — Apache 2.0 attribution file |
| **`test_suite.py`** | 168 new tests in sections 49–56 |

---

## v3.11.0 — Wiki Vault, Dream Cycle, Document Extraction & Knowledge Consolidation

Three major knowledge systems land in this release. **Wiki Vault** exports the entire knowledge graph as an Obsidian-compatible markdown vault with YAML frontmatter, wiki-links, and per-type indexes. **Dream Cycle** runs nightly background refinement — merging duplicate entities, enriching thin descriptions from conversation context, and inferring missing relationships — with a three-layer anti-contamination system that prevents cross-entity fact-bleed. **Document Knowledge Extraction** processes uploaded documents through a map-reduce LLM pipeline, extracting entities and relations into the knowledge graph with full source provenance. The Settings UI consolidates all knowledge features under a unified **Knowledge tab**, the graph panel gains source filtering and recency glow, and the status bar grows to 17 health-check pills.

### 📚 Wiki Vault (Obsidian Export)

The knowledge graph can now be exported as a structured markdown vault, compatible with Obsidian, VS Code, and any markdown editor.

- **Vault structure** — entities grouped by type (`wiki/person/`, `wiki/project/`, `wiki/event/`, etc.) with one `.md` file per entity; sparse entities (<20 chars) roll up into `_index.md` per type; per-type indexes and a master `index.md` auto-generated on rebuild
- **YAML frontmatter** — each article includes `id`, `type`, `subject`, `aliases`, `tags`, `source`, `created`, `updated` metadata
- **Wiki-links** — related entities linked via `[[Entity Name]]` syntax, enabling Obsidian backlinks and graph view
- **Connections section** — outgoing and incoming relations listed with arrow notation
- **Live export** — entities are exported on save (≥20 chars), deleted on entity removal, and rebuilt on batch operations
- **Search** — full-text search across all `.md` files with title, snippet, and entity ID results
- **Conversation export** — any thread can be exported as a vault-compatible markdown file
- **Agent tool** — 5 sub-tools (`wiki_search`, `wiki_read`, `wiki_rebuild`, `wiki_stats`, `wiki_export_conversation`) let the agent interact with the vault
- **Settings UI** — enable/disable toggle, vault path configuration with Browse button, stats display, rebuild and open-folder buttons

### 🌙 Dream Cycle (Nightly Knowledge Refinement)

A background daemon refines the knowledge graph during idle hours, running three non-destructive operations.

- **Duplicate merge** — entities with ≥0.93 semantic similarity and same type are merged; LLM synthesizes the best description, aliases are unioned, relations re-pointed to the survivor
- **Description enrichment** — thin entities (<80 chars) appearing in 2+ conversations get richer descriptions from conversation context and relationship graph
- **Relationship inference** — co-occurring entity pairs with no existing edge are evaluated for a meaningful connection (tagged `source="dream_infer"`)
- **Three-layer anti-contamination** — (1) sentence-level excerpt filtering extracts only sentences mentioning the target entity, (2) deterministic post-enrichment cross-entity validation scans LLM output for unrelated entity subjects and rejects contaminated results before DB write, (3) strengthened prompt with concrete negative examples and subject-name substitution
- **Subject-name guard** — entities with different normalized subjects require ≥0.98 similarity to merge, preventing false merges of distinct people/concepts
- **Configurable window** — default 1–5 AM local time; checks every 30 minutes if conditions met (enabled, in window, idle, not yet run today)
- **Dream journal** — all operations logged to `~/.thoth/dream_journal.json` with cycle ID, summary, and duration; viewable in the Activity tab
- **Settings UI** — enable/disable toggle, window display, last run summary in the Knowledge tab
- **Status pill** — new Dream Cycle health-check pill shows enabled state and last run time

### 📄 Document Knowledge Extraction (Map-Reduce Pipeline)

Uploaded documents are now processed through a three-phase LLM pipeline that extracts structured knowledge.

- **Map phase** — document split into ~6K-char windows; each window summarized to 3–5 sentences
- **Reduce phase** — window summaries combined into a coherent 300–600 word article
- **Extract phase** — core entities and relations pulled from the final article; 3–8 entities per document
- **Hub entity** — the document itself is saved as a `media` entity; extracted entities linked via `extracted_from` relation for provenance
- **Cross-window dedup** — entities with the same subject across windows are merged before saving
- **Live progress** — status bar shows pulsing progress pill with phase indicator, progress bar, queue count, and stop button (updates every 2 seconds)
- **Background queue** — documents queued for processing; worker thread handles one at a time
- **New file formats** — document upload now supports `.md`, `.html`, and `.epub` in addition to PDF, DOCX, and TXT
- **Per-document cleanup** — individual document delete button removes vector store entries and all extracted entities with matching source tag; bulk "Clear all documents" removes everything with `document:*` prefix

### 🧠 Knowledge Tab Consolidation

All knowledge management features are unified under a single **Knowledge** settings tab.

- **Renamed** — "Memory" tab → "Knowledge" tab throughout settings, home Activity panel, and status pills
- **Unified sections** — Memory Extraction settings, Wiki Vault settings, Dream Cycle settings, and Danger Zone all in one place
- **Activity panel** — shows extraction counters (threads scanned, entities saved, islands repaired), Dream Cycle window/status/last run, and up to 3 recent dream journal entries
- **Danger zone** — "Delete all knowledge" now clears entities, vector store, and wiki vault folder in one operation with confirmation dialog

### 🕸️ Knowledge Graph Visualization Enhancements

The graph panel gains filtering tools and visual indicators for entity provenance and recency.

- **Source filter pills** — toggleable `💬 chat` and `📄 documents` buttons filter nodes by origin
- **Recency glow** — node border width and color reflect how recently the entity was updated: bright amber (≤7 days), orange (7–30 days), dim brown (30–90 days), stale grey (90+ days)
- **User hub toggle** — show or hide the central User node
- **Hide unlinked toggle** — hide entities connected only to the User node, revealing natural clusters
- **Source border style** — document-sourced entities render with dashed borders
- **Detail card** — now shows source label and recency (e.g., "📄 document · 1 day ago")
- **Edge IDs** — `graph_to_vis_json()` now includes `id` field on edges for stable updates

### 🔗 Memory Tool Improvements

- **Subject-name arguments** — `link_memories` and `explore_connections` now accept entity **names** (preferred) instead of hex IDs; `_resolve_entity()` helper looks up by name first, falls back to ID
- **Contradiction detection** — `save_memory` runs LLM-based contradiction check before updating; if a conflict is detected, the agent returns a warning and asks the user which version is correct
- **Cross-entity overwrite guard** — system prompt guardrail prevents `update_memory` from overwriting a memory belonging to a different subject than the one being discussed
- **Retry on parallel calls** — `link_memories` includes 0.5s retry delay for parallel tool invocations that race against entity creation

### 🔧 Rendering Fixes

- **Mermaid diagram extraction** — fenced mermaid blocks are now extracted from text *before* `markdown2` processing (which was mangling them), rendered as `<pre class="mermaid">` elements, and processed by `mermaid.js` with a 100ms post-render delay
- **Streaming finalization** — all streamed messages now get unconditionally re-rendered at finalization (was previously gated on YouTube/mermaid detection), fixing code block syntax highlighting that only appeared on refresh

### 📊 Status Monitor Updates

- **17 health-check pills** — 3 new checks for Dream Cycle, TTS (Kokoro), and Wiki Vault; total up from 14
- **Renamed** — "Memory" pill → "Knowledge" pill
- **Tab routing fixes** — Disk pill now links to System tab; FAISS Index pill no longer links anywhere (informational only)
- **Extraction progress pill** — live document extraction progress with phase, bar, queue count, and stop button

### 📋 Bundled Skills Updated

- **Knowledge Base** — new bundled skill guiding the agent through the unified knowledge system (graph + documents + wiki)
- **Self-Reflection** — updated to reference `wiki_search` and `wiki_rebuild` for the reflection cycle
- **Deep Research** — added "Check Existing Knowledge" and "Save Key Findings" steps
- **Brain Dump** — added "Check Existing Knowledge" step to prevent duplicating facts
- **Meeting Notes** — references knowledge graph and wiki linking
- **Tool fields removed** — `tools:` field removed from all updated skill frontmatters (skills auto-discover tools)

### 🧪 Tests

- **974 PASS**, 0 FAIL, 1 WARN (up from 886 in v3.10.0)
- New: Wiki Vault (74 tests), Auto-Recall improvements, Wiki Tool (5 sub-tools), Bundled Skills validation, Document Knowledge Extraction (map-reduce, dedup, queue, cleanup), Wiki Cleanup & Knowledge Tab consolidation, Dream Cycle (config, journal, safety checks, 14 assertions), Status monitor count updates

### 📁 Files Changed

| File | Change |
|------|--------|
| **`wiki_vault.py`** | **New** — Obsidian-compatible markdown vault export: per-entity articles, YAML frontmatter, wiki-links, indexes, search, conversation export |
| **`tools/wiki_tool.py`** | **New** — Agent tool with 5 sub-tools: wiki_search, wiki_read, wiki_rebuild, wiki_stats, wiki_export_conversation |
| **`dream_cycle.py`** | **New** — Nightly knowledge refinement daemon: merge, enrich, infer with 3-layer anti-contamination, configurable window, dream journal |
| **`document_extraction.py`** | **New** — Background map-reduce LLM pipeline: split → summarize → extract entities; queue-based with live progress |
| **`bundled_skills/knowledge_base/SKILL.md`** | **New** — Bundled skill for the unified knowledge system |
| **`prompts.py`** | 8 new prompt templates: DOC_MAP/REDUCE/EXTRACT, DREAM_MERGE/ENRICH/INFER, updated EXTRACTION_PROMPT (10 entity types), cross-entity guardrail in UPDATING MEMORIES, search_documents→documents fix |
| **`knowledge_graph.py`** | `delete_entities_by_source()`, `delete_entities_by_source_prefix()`, `repair_graph_islands()`, edge IDs in vis JSON, `_updated_at`/`_source` fields on nodes, wiki vault auto-export on save/delete |
| **`documents.py`** | New loaders for `.md`, `.html`, `.epub`; `remove_document()` with source cleanup |
| **`tools/memory_tool.py`** | `_resolve_entity()` name-first lookup, `_check_contradiction()` LLM call, subject-name arguments on link/explore, 0.5s retry |
| **`memory_extraction.py`** | Calls `repair_graph_islands()`, extraction status counters (threads_scanned, entities_saved, islands_repaired) |
| **`ui/settings.py`** | Knowledge tab consolidation (Memory+Wiki+Dream Cycle), document upload triggers extraction queue, per-doc delete, Wiki Vault section, Dream Cycle section, danger zone clears wiki |
| **`ui/home.py`** | Activity panel: extraction counters, Dream Cycle status/journal, renamed Memory→Knowledge |
| **`ui/graph_panel.py`** | Source filter pills, recency glow, user hub toggle, hide unlinked toggle, source border style, detail card enhancements |
| **`ui/render.py`** | `_MERMAID_FENCE_RE`, `_split_mermaid()`, mermaid extraction before markdown2, `<pre class="mermaid">` rendering |
| **`ui/streaming.py`** | Unconditional re-render at finalization, `mermaid.run()` with 100ms delay |
| **`ui/status_bar.py`** | Document extraction progress pill with phase/bar/stop button |
| **`ui/status_checks.py`** | 3 new checks (Dream Cycle, TTS, Wiki Vault), Memory→Knowledge rename, Disk→System tab, FAISS unlinked |
| **`ui/chat.py`** | Drag-drop safety timer, document-level drop handler with Quasar guard |
| **`app.py`** | `start_dream_loop()` at startup |
| **`tools/__init__.py`** | `wiki_tool` import for registry auto-registration |
| **`bundled_skills/self_reflection/SKILL.md`** | References wiki_search + wiki_rebuild, removed tools field |
| **`bundled_skills/deep_research/SKILL.md`** | Added Check Existing Knowledge + Save Key Findings steps |
| **`bundled_skills/brain_dump/SKILL.md`** | Added Check Existing Knowledge step |
| **`bundled_skills/meeting_notes/SKILL.md`** | References knowledge graph + wiki linking |
| **`test_suite.py`** | 88 new tests across 7 sections (42–48); check count updates |
| **`integration_tests.py`** | New integration tests for document extraction + wiki vault |

---

## v3.10.0 — Status Monitor, Mermaid Diagrams, Image Persistence, Vision Files & Rich PDF Export

The home screen gets an interactive **status monitor panel** — a frosted-glass bar with an animated avatar, 14 health-check pills, and a one-click diagnosis button. Images now **survive thread reload** — pasted, captured, and attached images are persisted in per-thread sidecar files and rehydrated when you revisit a conversation. **Mermaid diagram rendering** brings flowcharts, sequence diagrams, and state diagrams to life inline in chat via mermaid.js. The **vision tool** gains `source='file'` for analyzing workspace image files by path, and the **filesystem tool** displays images inline when read. **PDF export** is upgraded to Playwright (headless Chromium) for full Unicode, emoji, chart, and styled markdown support. **OAuth token health checks** proactively validate Gmail and Calendar tokens at startup with silent refresh and periodic re-validation. A rewritten **Arxiv tool**, **clipboard image paste**, **right-click context menu** (pywebview), and a knowledge graph **opacity-based filter** round out the release.

### 📊 Status Monitor Panel

- **Animated avatar** — customizable emoji with conic-gradient spinning ring, ECG-synced glow pulses, and subtle wobble; ring color picker with 15 presets; config persisted in `~/.thoth/user_config.json`
- **14 health-check pills** — two centered rows covering Ollama, Active Model, Cloud API, Email, Telegram, Gmail OAuth, Calendar OAuth, Task Scheduler, Memory Extraction, Disk Space, Threads DB, FAISS Index, Document Store, and Network; color-coded (green/amber/red/grey) with tooltip detail
- **Click-to-settings** — clicking any pill opens the relevant settings tab
- **Diagnosis button** — runs all 14 checks on demand (icon spins during execution), opens a dialog with expandable results per service and a copy-to-clipboard report
- **ECG background** — animated heart-rate-monitor line scrolls behind the frosted-glass panel
- **Light/heavy check split** — 4 instant checks (Ollama, Model, Cloud API, Memory Extraction) always fresh; 10 heavier checks (network, OAuth, disk, DB) cached for 5 minutes

### 🖼️ Image Persistence

Images in chat messages now survive thread reload and app restart.

- **Per-thread sidecar files** — image payloads (base64) are saved to `~/.thoth/thread_ui/<thread_id>.images.json` alongside conversation checkpoints
- **Signature-based hydration** — on reload, images are matched back to their messages using content signatures with index fallback for checkpoint-reconstructed user messages
- **All image types covered** — pasted images, vision captures, browser screenshots, and file attachments are all persisted
- **Cleanup on delete** — sidecar files are removed when a thread is deleted
- **MIME-aware data URIs** — PNG, JPEG, GIF, and WebP images are detected by magic bytes and rendered with the correct MIME type

### 📊 Mermaid Diagram Rendering

Mermaid diagrams now render as interactive visual diagrams inline in chat.

- **mermaid.js integration** — bundled `static/mermaid.min.js` loaded in head HTML with `securityLevel: 'strict'` and dark theme
- **Auto-fence detection** — `_auto_fence_mermaid()` in `ui/render.py` detects unfenced Mermaid syntax (graph, flowchart, sequenceDiagram, classDiagram, erDiagram, stateDiagram, gantt, mindmap, timeline, pie) and wraps it in ` ```mermaid ` fences before rendering
- **Streaming support** — `_format_assistant_markdown()` chains auto-fence + URL auto-linking on all streaming `set_content()` calls
- **Post-render swap** — after markdown rendering, `<pre><code class="language-mermaid">` blocks are swapped to `<div class="mermaid-rendered">` and processed by `mermaid.run()`
- **Chart tool guard** — requests for Mermaid diagram types (flow, sequence, state, ER, etc.) in `create_chart` are caught early with a helpful error message redirecting to fenced Mermaid blocks

### 👁️ Vision: Image File Analysis

The vision tool now analyzes image files in the workspace without needing a camera or screen capture.

- **`source='file'` parameter** — new source option on `analyze_image` with `file_path` argument for workspace-relative or absolute paths
- **Path resolution** — tries absolute path, then workspace root (from filesystem tool config), then current working directory
- **Prompt routing** — system prompt updated to guide the model: use `source='file'` for workspace images, don't re-analyze already-attached images
- **Filesystem inline display** — `workspace_read_file` on image files (PNG, JPEG, GIF, WebP, BMP, TIFF, SVG) displays the image inline in chat and returns a hint to use `analyze_image` for content analysis

### 📄 Rich PDF Export

PDF export upgraded from basic fpdf2 text to full-fidelity Playwright rendering.

- **Playwright-first** — conversation export and `export_to_pdf` filesystem tool both use headless Chromium for full Unicode, emoji, embedded images, Plotly charts, styled markdown tables, and syntax-highlighted code blocks
- **Automatic fallback** — if Playwright is unavailable, falls back to the basic fpdf2 text-only renderer
- **Separate browser instance** — PDF rendering uses `headless=True` in a thread pool worker — does not interfere with the visible BrowserTool browser
- **Professional styling** — A4 layout, system fonts, color-coded roles (blue for User, gold for Thoth), collapsible tool-result blocks, responsive images

### 🔑 OAuth Token Health Checks

Gmail and Calendar OAuth tokens are now proactively monitored.

- **Startup check** — on launch, enabled Gmail/Calendar tools have their tokens validated; expired access tokens are silently refreshed
- **Periodic re-check** — APScheduler job runs every 6 hours to catch tokens that expire mid-session
- **Granular status** — `check_token_health()` on both tools returns `valid`, `refreshed`, `expired`, `missing`, or `error` with detail
- **Settings UI feedback** — Gmail and Calendar settings tabs show token status (healthy, refreshed, expired, error) instead of a generic "✅ Authenticated"
- **User-facing warnings** — expired tokens trigger desktop notifications and in-app toasts with re-authentication instructions

### 📚 Arxiv Tool Rewrite

The Arxiv tool is rewritten from scratch — no longer uses `ArxivRetriever`.

- **Direct `arxiv` package** — uses `arxiv.Client` with rate-limiting (`delay_seconds=3.0`) and retries
- **Newest-first sorting** — results sorted by `SubmittedDate` descending
- **Rich output** — title, authors (truncated at 5 with "et al."), published date, primary category, abstract, full-text HTML link, PDF link, and source URL per result
- **Version-stripped HTML URLs** — `arxiv.org/html/<id>` links strip the version suffix for clean access
- **Query syntax hints** — tool description mentions `ti:`, `au:`, `abs:`, `cat:` arXiv query syntax

### 📋 Clipboard Image Paste

- **Ctrl+V paste support** — paste images directly from the clipboard into chat; images are converted to file uploads with timestamped names (e.g. `pasted_image_1712345678.png`)
- **Singleton listener** — paste handler installs once and reads the dynamic upload widget ID, surviving thread switches without duplicate bindings

### 🖱️ Right-Click Context Menu (pywebview)

- **Custom context menu** — Cut, Copy, Paste, and Select All in the native desktop window, since pywebview suppresses the browser's default context menu
- **pywebview-only** — only activates inside pywebview; normal browsers keep their native context menu
- **Clipboard integration** — Paste reads from `navigator.clipboard` and inserts via `execCommand`

### 🕸️ Knowledge Graph Filter Overhaul

- **Opacity-based filtering** — search and entity-type filters now dim non-matching nodes/edges (opacity 0.12) instead of rebuilding the entire network, preserving layout stability and spatial context
- **Edge dimming** — edges between non-matching nodes fade to 0.06 opacity; edges connecting two matching nodes stay fully visible

### 🔧 Other Improvements

- **Immediate user message rendering** — file attachments are now processed asynchronously; the user message (with 📎 badges and image thumbnails) appears instantly while vision analysis runs in the background with a "🔍 Analyzing image..." indicator
- **Browser screenshot persistence** — browser screenshots taken during tool execution are added to `captured_images`, persisted via the image sidecar system, and restored on reload
- **Terminal chevron fix** — inline terminal panel expand/collapse chevron direction corrected (was inverted)
- **Drag-and-drop singleton** — drag-and-drop file handler installs once and reads the dynamic upload widget ID, preventing duplicate handlers across thread switches
- **Context window minimum** — minimum context size raised from 4K to 16K tokens; legacy values below 16K auto-clamp
- **Notify-only tasks** — tasks with `notify_only` flag skip thread creation, reducing clutter for simple timer/notification tasks
- **Skill editor simplified** — removed tool-dependency checkboxes from the skill editor UI (tools declared in SKILL.md frontmatter are informational, not enforced)

### 🧪 Tests

- **886 PASS**, 0 FAIL, 1 WARN (up from 842 in v3.9.0)
- New: Status monitor panel (20 tests), OAuth token health checks (7 tests), Arxiv tool rewrite (6 tests), image persistence & hydration, Mermaid auto-fence, PDF export (Playwright + fallback), filesystem image display, vision file analysis, streaming format pipeline, badge parsing

### 📁 Files Changed

| File | Change |
|------|--------|
| **`ui/status_checks.py`** | **New** — 14 health-check functions with `CheckResult` dataclass, `ALL_CHECKS`/`LIGHT_CHECKS`/`HEAVY_CHECKS` registries |
| **`ui/status_bar.py`** | **New** — Status bar UI: avatar, pills, diagnosis dialog, ECG animation, avatar picker |
| **`ui/home.py`** | Logo replaced with `build_status_bar()` call; `open_settings` callback wired in |
| **`threads.py`** | Per-thread image sidecar I/O (`save_thread_ui_images`, `load_thread_ui_images`, `_thread_ui_images_path`); cleanup in `_delete_thread` |
| **`ui/helpers.py`** | `persist_thread_image_state()`, `_hydrate_thread_images()` with signature + index matching; `strip_file_context` badge parsing for "ALREADY ANALYZED" markers; Playwright-based `_render_pdf_playwright()` conversation PDF export with `_build_conversation_html()`; fpdf2 fallback |
| **`ui/render.py`** | `_img_data_uri()` MIME detection; `_auto_fence_mermaid()` with `_MERMAID_START_RE` and `_is_mermaid_continuation_line()`; Mermaid post-render JS swap; wired into `render_text_with_embeds` and `render_message_content` |
| **`ui/streaming.py`** | `_format_assistant_markdown()` chains auto-fence + autolink on all streaming content; `_img_data_uri()` for screenshot display; `persist_thread_image_state` calls after user/assistant messages; filesystem image display via `get_and_clear_displayed_image()`; immediate user message rendering with async file processing; Mermaid post-render JS |
| **`ui/chat.py`** | Clipboard image paste JS listener; drag-and-drop singleton fix; `persist_thread_image_state` on detached generation reattach; terminal chevron direction fix |
| **`ui/head_html.py`** | `mermaid.min.js` script tag + `mermaid.initialize()` with dark theme and strict security; `.mermaid-rendered` CSS; right-click context menu JS (pywebview-only) |
| **`ui/graph_panel.py`** | Opacity-based filter/search using `ds.update()` instead of network rebuild |
| **`ui/settings.py`** | Gmail/Calendar token health status display; skill editor: removed tool-dependency checkboxes, moved Create button to top |
| **`tools/arxiv_tool.py`** | Full rewrite — `execute()` using `arxiv.Client` directly; removed `get_retriever`/`ArxivRetriever`; newest-first sorting, HTML links, rate limiting |
| **`tools/chart_tool.py`** | `_MERMAID_DIAGRAM_TYPES` guard in `_create_chart`; updated tool description to exclude Mermaid |
| **`tools/filesystem_tool.py`** | Image file inline display via `_last_displayed_image` buffer + `get_and_clear_displayed_image()`; Playwright-first `export_to_pdf` with fpdf2 fallback |
| **`tools/vision_tool.py`** | `source='file'` + `file_path` parameter on `analyze_image`; updated schema and description |
| **`tools/gmail_tool.py`** | `_check_google_token()` with silent refresh; `check_token_health()` method |
| **`tools/calendar_tool.py`** | `_check_google_token()` with silent refresh; `check_token_health()` method |
| **`tools/memory_tool.py`** | `explore_connections` description updated to "Mermaid graph diagram" |
| **`tools/browser_tool.py`** | Minor cleanup |
| **`vision.py`** | `source='file'` support in `capture_and_analyze()`; `_analyze_from_file()` and `_resolve_image_path()` helpers; source-aware question prefixes |
| **`app.py`** | `_check_oauth_tokens()` startup check; `_periodic_oauth_check()` scheduled every 6 h; passes `open_settings` to `build_home()` |
| **`models.py`** | Removed 4K/8K context options; auto-clamp legacy values below 16K |
| **`prompts.py`** | Vision `source='file'` routing; attached image "do NOT re-analyze" guidance; `workspace_read_file` image support mention |
| **`tasks.py`** | `notify_only` tasks skip thread creation |
| **`skills.py`** | Removed tool-dependency enforcement from `update_skill`/`create_skill` |
| **`ui/export.py`** | Minor fix |
| **`ui/sidebar.py`** | Minor update |
| **`ui/setup_wizard.py`** | Minor fix |
| **`static/mermaid.min.js`** | **New** — bundled Mermaid.js library |
| **`test_suite.py`** | 46 new tests covering status monitor (20), OAuth, Arxiv, image persistence, Mermaid, PDF, filesystem images, vision files, streaming |
| **`README.md`** | Updated for all new features; test badge 842→868; version references updated |

---

## v3.9.0 — Modular UI, Thinking Models & Cloud Model Expansion

Thoth's monolithic 6,500-line frontend is now a **clean modular architecture** — `app.py` + a `ui/` package of 15 focused modules. **Thinking model support** lands with full reasoning-token extraction, collapsible thinking bubbles, and persistence across thread reloads. **OpenRouter gets first-class support** via `ChatOpenRouter`, and a new **Data Analyst** bundled skill rounds out the skill library to 10. Multiple rendering fixes (URL auto-linking, YouTube embeds) and a privacy improvement round out the release.

### 🏗️ UI Modularization

The monolith `app_nicegui.py` (6,535 lines) has been replaced by `app.py` + `ui/` package using a strangler-fig migration pattern.

- **15 focused modules** — `state.py` (dataclasses), `constants.py`, `head_html.py`, `helpers.py` (config, file processing, exports), `render.py` (message rendering), `streaming.py` (generation consumer, send/interrupt), `setup_wizard.py`, `settings.py`, `graph_panel.py` (knowledge graph vis), `sidebar.py`, `home.py`, `tasks_ui.py`, `voice_bar.py`, `export.py`, `__init__.py`
- **Zero functionality loss** — every feature from the monolith is preserved; all imports resolve cleanly
- **Launcher updated** — `launcher.py`, both installer scripts (Windows ISS + macOS build), CI workflow, test suite, and all documentation updated to reference the new entry point

### 💡 Thinking Model Support

Full support for reasoning models (DeepSeek-R1, Qwen3, QwQ, etc.) across local and cloud providers.

- **Reasoning token extraction** — `additional_kwargs["reasoning_content"]` is extracted from streaming chunks before content, surfacing the model's chain-of-thought in real time
- **`reasoning=True`** — all four `ChatOllama` instantiation sites now enable native reasoning mode
- **`<think>` tag stripping** — models that embed `<think>…</think>` blocks in content have them separated into thinking tokens and stripped from the visible response
- **Collapsible thinking bubble** — during streaming, thinking content displays live in italic at 55% opacity, then auto-collapses into a `💭 Thinking` expansion with `psychology` icon when the real response begins
- **Thinking persistence on thread reload** — `load_thread_messages()` now recovers reasoning content from both `additional_kwargs` and `<think>` tags in the LangGraph checkpoint; historical messages render a collapsed thinking expansion matching the live-streaming style

### ☁️ Cloud Model Expansion

- **ChatOpenRouter** — OpenRouter models now use `langchain-openrouter`'s dedicated `ChatOpenRouter` class instead of the generic `ChatOpenAI` wrapper, enabling proper provider-specific features
- **New dependency** — `langchain-openrouter` added to `requirements.txt`

### 📊 Data Analyst Skill

- **New bundled skill** — `bundled_skills/data_analyst/SKILL.md` (v1.1) — guides the agent through dataset analysis, statistical summaries, and insightful Plotly chart creation
- **10 bundled skills total** — Brain Dump, Daily Briefing, Data Analyst, Deep Research, Humanizer, Meeting Notes, Proactive Agent, Self-Reflection, Task Automation, Web Navigator

### 🔗 Rendering Fixes

- **URL auto-linking** — bare `https://` URLs in messages now automatically render as clickable links; a regex preprocessor safely skips URLs already inside markdown links, angle brackets, inline code, or fenced code blocks
- **YouTube embed fix** — `render_text_with_embeds()` rewritten to match the full `**[text](youtube_url)**` context, eliminating `**` and `)**` artifacts that appeared when YouTube links were wrapped in markdown bold/link syntax

### 📊 Chart Tool Fixes

- **Reliable chart rendering** — chart tool improvements for consistent Plotly chart creation and inline display

### 🔒 Privacy

- **User content removed from logs** — `send_message()` no longer logs `agent_input_preview` (the first 200 characters of the user's message); log now shows only file names and content lengths

### 📁 Housekeeping

- **`workflows.py` removed** — fully superseded by `tasks.py` since v3.5.0; dead code deleted
- **Version bump** — v3.8.0 → v3.9.0 across installers, CI, documentation, and landing page
- **Test suite** — all `app_nicegui` references updated to `app`

### 📁 Files Changed

| File | Change |
|------|--------|
| **`app.py`** | **Renamed** from `app_v2.py` — modular entry point, port 8080, title "Thoth" |
| **`ui/`** | **New** — 15-module UI package extracted from monolith |
| **`app_nicegui.py`** | **Deleted** — archived as `.bak` |
| **`workflows.py`** | **Deleted** — dead code, superseded by `tasks.py` |
| **`agent.py`** | Thinking/reasoning token extraction from `additional_kwargs["reasoning_content"]`; `<think>` tag separation |
| **`models.py`** | `reasoning=True` on all `ChatOllama` calls; `ChatOpenRouter` for OpenRouter cloud models |
| **`requirements.txt`** | Added `langchain-openrouter` |
| **`tools/chart_tool.py`** | Chart creation and rendering fixes |
| **`prompts.py`** | System prompt refinements |
| **`bundled_skills/data_analyst/`** | **New** — Data Analyst skill v1.1 |
| **`launcher.py`** | References updated `app_nicegui.py` → `app.py` |
| **`installer/thoth_setup.iss`** | Version 3.9.0; `app_nicegui.py` → `app.py`; added `ui\` package (15 files) |
| **`installer/build_mac_app.sh`** | Version 3.9.0; added `ui` to rsync; removed `app.py` from skip list |
| **`installer/build_installer.ps1`** | Version 3.9.0 |
| **`.github/workflows/release.yml`** | `DEFAULT_VERSION` → 3.9.0 |
| **`test_suite.py`** | 67× `app_nicegui` → `app`; docstring version v3.9.0 |
| **`README.md`** | Architecture diagram, module table, installer filenames updated; skills count 10; models.py description updated |
| **`docs/index.html`** | Download links v3.9.0; skills 9→10; new Thinking Models feature card; footer version |
| **`installer/README.md`** | Version reference updated |
| **`memory.py`**, **`tts.py`**, **`tasks.py`**, **`vision.py`** | Comment/docstring references updated |

---

## v3.8.0 — Bundled Skills, Memory Intelligence & Self-Contained Installers

Thoth ships with **9 bundled skills** — reusable instruction packs that shape how the agent thinks and responds. The memory system gets smarter with **auto-linking, FAISS fallback search, background orphan repair, and memory decay**. Token counting is now accurate via **tiktoken**, and the agent dynamically adjusts its tool set based on available context. Installers are now fully **self-contained** (no post-install downloads), and a new **CI/CD pipeline** automates builds, code signing, notarization, and GitHub Releases.

### 🧩 Bundled Skills Engine

New `skills.py` engine and `bundled_skills/` directory — a system for packaging and injecting domain-specific instructions into the agent's behavior.

- **SKILL.md format** — each skill is a Markdown file with YAML frontmatter (`display_name`, `icon`, `description`, `tools`, `tags`, `version`, `author`, `enabled_by_default`) followed by freeform instructions
- **9 bundled skills** — 🧠 Brain Dump, ☀️ Daily Briefing, 🔬 Deep Research, 🗣️ Humanizer, 📋 Meeting Notes, 🎯 Proactive Agent, 🪞 Self-Reflection, ⚙️ Task Automation, 🌐 Web Navigator
- **Two-tier discovery** — bundled skills ship read-only in `<app_root>/bundled_skills/`; user skills in `~/.thoth/skills/` override bundled skills by name
- **Prompt injection** — enabled skills have their instructions injected into the system prompt before every LLM call
- **Per-skill enable/disable** — toggle skills from Settings → Skills tab; config persisted in `~/.thoth/skills_config.json`
- **Tool-aware** — each skill declares the tools it uses (`tools` field in frontmatter)
- **In-app skill editor** — create and edit user skills from Settings → Skills with a visual form — name, icon, description, tools, and freeform instructions; no need to manually create `SKILL.md` files
- **Cache & reload** — skills are cached in memory after first load; `load_skills(force_refresh=True)` forces a re-scan

### 🧠 Memory Intelligence

Four improvements to the knowledge graph that make memory recall smarter and the graph healthier.

- **Auto-link on save** — when a new entity is saved, the engine automatically scans existing entities for potential relationships and creates links, building the knowledge graph organically without manual `link_memories` calls
- **FAISS fallback search** — if the primary semantic recall returns no results above the 0.80 similarity threshold, a broader relaxed search is attempted automatically; prevents empty recall on edge-case queries
- **Background orphan repair** — a periodic background process detects entities with zero relationships and attempts to link them to related entities, keeping the knowledge graph connected over time
- **Memory decay** — memories that haven't been recalled recently are gradually deprioritized in retrieval results, ensuring frequently relevant information surfaces first

### 📏 Accurate Token Counting & Dynamic Tool Budgets

Context window management is now more precise and adaptive.

- **tiktoken integration** — token counting uses OpenAI's `tiktoken` library (cl100k_base encoding) instead of character-based estimates; the live token counter and all trimming decisions are now accurate to the token
- **Dynamic tool budgets** — the agent automatically adjusts how many tools are exposed to the model based on available context headroom; when context usage is high, lower-priority tools are temporarily hidden to prevent the system prompt from crowding out conversation history
- **Cloud model context fix** — `contextvars.ContextVar` now correctly propagates model overrides through the full agent pipeline, fixing a bug where cloud model threads could miscalculate available context

### 📦 Self-Contained Installers

Both Windows and macOS installers now bundle all dependencies at build time — no post-install downloads.

- **Windows (`build_installer.ps1`)** — patches Python's `._pth` file, installs pip, and runs `pip install -r requirements.txt` into the bundled Python during the build step; `install_deps.bat` and `get-pip.py` removed from the installer
- **macOS (`build_mac_app.sh`)** — new self-contained build script using python-build-standalone; downloads a standalone Python, installs all pip deps, assembles a `.app` bundle with entitlements, code-signs, and creates a `.pkg` installer
- **Inno Setup (`thoth_setup.iss`)** — updated to include `bundled_skills/` and `workflows.py`; removed post-install dependency download steps

### 🔄 CI/CD Pipeline

New `.github/workflows/release.yml` — automated build, sign, notarize, and release.

- **Trigger** — tag push (`v*`) or manual `workflow_dispatch`
- **Test stage** — runs full test suite before building
- **Parallel builds** — Windows (Inno Setup) and macOS (build_mac_app.sh) build in parallel
- **macOS code signing** — signs the `.app` and `.pkg` with Apple Developer certificates (Application + Installer)
- **macOS notarization** — submits the `.pkg` to Apple for notarization and staples the ticket
- **GitHub Release** — creates a draft release with both platform installers attached
- **6 GitHub secrets** — `APPLE_CERTIFICATE_P12`, `APPLE_INSTALLER_P12`, `APPLE_CERT_PASSWORD`, `APPLE_ID`, `APPLE_TEAM_ID`, `APPLE_APP_PASSWORD`

### 🐛 Bug Fixes

- **Cloud model override propagation** — `contextvars.ContextVar` replaces thread-local storage for model overrides, fixing context window miscalculation in cloud model threads
- **User entity prompt** — memory extraction prompt updated to fix entity naming for the canonical "User" node
- **Memory content merge** — fixed a bug where merging duplicate entities could lose content from the richer entry

### 🌐 Per-Thread Browser Tabs & Background Browsing

Browser automation now works in background tasks. Each thread (interactive chat or scheduled task) gets its own isolated browser tab.

- **Per-thread tab isolation** — replaced the single shared page with a `_thread_pages` dict; each thread claims or creates its own tab; the agent never hijacks tabs belonging to other threads
- **Blank-page-only claiming** — only pages at `about:blank` or `chrome://newtab/` are eligible for claiming; pages with content from prior sessions are never auto-claimed
- **Background browsing** — removed `_block_if_background()` entirely; browser tools now work in background tasks through per-thread tab isolation
- **Browser crash recovery** — if the browser is closed externally, a `disconnected` handler detects it, clears stale state, and the next browser action automatically relaunches the session
- **Retry on close** — `_run_on_pw_thread()` catches "has been closed" errors, resets the session, and retries once
- **Tab cleanup on task completion** — `run_task_background` finally block calls `kill_session(thread_id)` to close the task's tab
- **Screenshot thread-awareness** — `take_screenshot(thread_id)` uses a new `get_page_for_screenshot()` that never creates tabs or steals focus from other threads

### 📊 Monitoring / Polling Tasks

New task pattern for monitoring conditions and self-disabling when met.

- **`{{task_id}}` template variable** — `expand_template_vars()` now supports `{{task_id}}`; lets prompts reference their own task for self-management
- **System prompt triage** — 4-line monitoring hint helps the agent distinguish "check X and notify me when Y" (monitoring task) from simple reminders
- **SKILL.md guidance** — Task Automation skill gained items 17–21: interval schedules, conditional prompts, persistent threads, polling template, self-disable vs self-delete

### 🔴 Error Notification Improvements

API errors are now visible, persistent, and survive thread refresh.

- **Red persistent toast** — `notify()` gained a `toast_type` parameter; API errors fire `toast_type="negative"` → red banner, no auto-dismiss, close button
- **Error persistence in checkpoint** — error messages are written to the LangGraph checkpoint via `update_state()` so they appear when the thread is refreshed or revisited
- **Content normalization** — `_normalise_content()` handles gpt-5.4 list-type `AIMessage.content` in streaming and memory extraction

### 🛡️ Agent Robustness

- **Recursion limits** — raised from 25 to 50 (interactive) / 100 (background tasks); wind-down warning injected at 75% asking the model to wrap up; 4× repeated tool-call loop detection
- **Thread rendering fix** — `load_thread_messages()` now handles interrupted tool-call loops (orphaned `ToolMessage` without matching `AIMessage`)

### 🧪 Tests

- **842 PASS**, 0 FAIL, 2 WARN (up from 841 in v3.8.0 baseline)
- New: per-thread tab isolation test (19g), `{{task_id}}` expansion test (24j2)
- Updated: `kill_session` assertion (19e), security audit assertion (32g)
- Removed: `_block_if_background` test (replaced by per-thread tabs)
- Context-size-aware browser snapshot test scaling

### 📁 Files Changed

| File | Change |
|------|--------|
| **`skills.py`** | **New** — skills engine: YAML frontmatter parsing, bundled + user skill discovery, enable/disable config, prompt building, caching |
| **`bundled_skills/`** | **New** — 9 skill directories, each with `SKILL.md` (Brain Dump, Daily Briefing, Deep Research, Humanizer, Meeting Notes, Proactive Agent, Self-Reflection, Task Automation, Web Navigator) |
| **`agent.py`** | Dynamic tool budgets based on context headroom; tiktoken-based token counting; `contextvars.ContextVar` for model override propagation; skills prompt injection in pre-model hook; content normalization for list-type `AIMessage.content`; API error surfacing with `toast_type="negative"`; recursion limits 50/100 with wind-down and loop detection |
| **`app_nicegui.py`** | Thread rendering fix for interrupted tool loops; error persistence to LangGraph checkpoint via `update_state()`; red persistent error toasts; screenshot passes `thread_id`; `AIMessage` import |
| **`notifications.py`** | `toast_type` parameter on `notify()` (default `"positive"`); toast queue carries `toast_type`; `drain_toasts()` returns dicts with type |
| **`tools/browser_tool.py`** | Per-thread tab isolation (`_thread_pages` dict, `_BLANK_URLS` claiming filter); `get_page_for_screenshot()`; `release_thread()`; crash recovery (`_on_close` handler, retry logic); removed `_block_if_background()`; all 7 actions accept `thread_id` |
| **`tasks.py`** | `{{task_id}}` in `expand_template_vars()`; browser tab cleanup in finally block |
| **`tools/task_tool.py`** | `_TaskCreateInput.prompts` description mentions `{{task_id}}` |
| **`prompts.py`** | 4-line monitoring/polling triage hint; `{{task_id}}` in template variables list |
| **`bundled_skills/task_automation/SKILL.md`** | Monitoring / Polling section (items 17–21) |
| **`memory_extraction.py`** | Content normalization for list-type `AIMessage.content`; user entity prompt fix; content merge bug fix |
| **`knowledge_graph.py`** | Auto-link on save; FAISS fallback search with relaxed threshold; background orphan repair; memory decay scoring |
| **`models.py`** | `contextvars.ContextVar` for cloud model override |
| **`installer/build_installer.ps1`** | Pre-installs pip deps at build time; patches `._pth` file |
| **`installer/build_mac_app.sh`** | **New** — self-contained macOS build with python-build-standalone, code signing, `.pkg` creation |
| **`installer/entitlements.plist`** | **New** — macOS hardened runtime entitlements |
| **`installer/thoth_setup.iss`** | Removed post-install downloads; added `bundled_skills/` and `workflows.py` |
| **`.github/workflows/release.yml`** | **New** — CI/CD: test → build → sign → notarize → GitHub Release |
| **`.gitignore`** | Added `installer/apple_signing/` |
| **`test_suite.py`** | ~101 new tests across skills, memory intelligence, tool budgets, tiktoken, per-thread tabs, `{{task_id}}`, error persistence |
| **`requirements.txt`** | Added `tiktoken` |
| **`README.md`** | Added Skills section, updated Memory/Agent/Architecture docs, browser per-thread tabs, monitoring/polling tasks, error notification improvements, updated safety section, test count badge |

---

## v3.7.0 — Cloud-Primary Mode, Per-Thread Model Switching & Task Stop

Thoth now works **without Ollama**. Connect your OpenAI or OpenRouter API key and use cloud models (GPT-4o, Claude, Gemini, etc.) as your default — or mix cloud and local models across different conversations. A new **per-thread model picker** lets you switch models mid-conversation, and a **task stop** feature lets you cancel running tasks at any point.

### ☁️ Cloud-Primary Mode

New `models.py` cloud engine — Thoth can now run entirely on cloud LLMs with no local Ollama dependency.

- **Dual-provider support** — connect OpenAI (direct API) and/or OpenRouter (100+ models from all major providers); keys stored in `api_keys.json` and managed via Settings → Cloud
- **Setup wizard** — fresh installs present two paths: **🖥️ Local (Ollama)** or **☁️ Cloud (API key)**; cloud path validates keys, fetches available models, and lets you pick a default — no Ollama needed
- **Starred models** — star your favorite cloud models in Settings → Cloud; starred models appear in the chat header model picker alongside local models
- **Cloud-first startup** — when the default model is cloud, Thoth skips Ollama auto-start entirely; no "Ollama not found" warnings on machines without it
- **Context-size catalog** — OpenRouter model metadata is cached locally; for OpenAI models (which don't expose context length), a built-in heuristic table covers GPT-4o/4.1/4.5/5, o1/o3/o4, Claude 2–4, and Gemini 2–3 families
- **Cloud vision detection** — cloud models with vision capability (e.g. `gpt-4o`, `claude-3.5-sonnet`) are auto-detected from provider metadata; the vision tool works seamlessly with cloud models
- **Privacy controls** — Settings → Cloud includes toggles for auto-recall, memory extraction, and conversation history; memory extraction defaults to OFF for cloud threads

### 🔀 Per-Thread Model Switching

Every conversation can now use a different model — cloud or local.

- **Chat header model picker** — dropdown in the chat header shows: "Default (current model)" + starred cloud models + local Ollama models; selecting a model sets the override for that thread only
- **Thread-level persistence** — `model_override` column added to `thread_meta` (auto-migrated); overrides survive app restarts
- **Cloud warning banner** — when a thread uses a cloud model, a colored banner shows: "☁️ Using gpt-4o via OpenAI — data is sent to the cloud"
- **Sidebar icons** — threads show ☁️ (cyan) for cloud models, 🖥️ (grey) for local models
- **Reset to default** — selecting "Default" in the picker clears the override; thread reverts to the app-wide default model
- **Summarization uses override** — context compression uses the thread's override model, not the global default
- **Telegram /model command** — `/model` lists available models; `/model gpt-4o` switches; `/model default` resets; invalid model names show an error with available options

### ⏹️ Task Stop / Cancel

Running tasks can now be stopped from the UI at any point during execution.

- **Node-level cancellation** — when a task has a `stop_event`, `invoke_agent()` uses `agent.stream(stream_mode="updates")` instead of `agent.invoke()`, checking the stop event between every LangGraph node; tasks stop between steps, not mid-LLM-call
- **`TaskStoppedError`** — new exception raised when a stop is detected; caught by the task runner for clean shutdown
- **`stop_task(thread_id)`** — signals the stop event for a running task; returns `True` if found
- **Three stop buttons** — red stop button in: (1) chat header when viewing a running task's thread, (2) Activity tab "Running Now" section per task, (3) task card (replaces the play button while running)
- **Stopped state** — stopped tasks are recorded as status "stopped" in run history; thread is renamed with "(stopped)"; orange `stop_circle` icon in Recent Runs; notification sent; delivery and auto-delete are skipped
- **Delete stops task** — deleting a thread while a task is running now signals `stop_task()` first; thread stays deleted (no ghost re-creation)
- **Thread existence guard** — task completion/stop handlers check if the thread still exists before renaming, preventing `INSERT ON CONFLICT` from re-creating deleted threads
- **Orphaned tool-call repair** — if stopped mid-tool-call, orphaned tool calls are auto-repaired before the thread is finalized
- **Backward compatible** — when `stop_event` is `None` (chat, Telegram, CLI), `invoke_agent()` uses the original `agent.invoke()` path unchanged

### 🔧 Displaced Tool-Call Repair

New repair logic in `invoke_agent()` fixes a class of LangGraph checkpoint corruption bugs.

- **Problem** — `trim_messages` or checkpoint corruption can displace `ToolMessage` responses away from their parent `AIMessage` with `tool_calls`, violating OpenAI's strict ordering requirement (tool_calls must be immediately followed by their ToolMessages)
- **Fix** — after trimming, a scan detects AIMessages whose tool_calls are not immediately followed by matching ToolMessages; stubs are injected in the correct position and displaced originals are removed
- **Auto-retry on orphan errors** — both `invoke_agent()` and `_stream_graph()` catch "tool_call without response" errors, run `repair_orphaned_tool_calls()`, and retry once automatically

### ⚡ FAISS Rebuild Optimization

Reduced redundant FAISS index rebuilds during memory extraction.

- **Before** — `_dedup_and_save()` called `rebuild_index()` at the end of each thread's extraction; processing 4 threads meant 4 full FAISS rebuilds (re-embedding all entities each time)
- **After** — `rebuild_index()` moved to `run_extraction()`, called once after all threads are processed; per-entity upserts are still suppressed via `_skip_reindex` during batch processing
- **Incremental upsert** — new `_upsert_index()` in `knowledge_graph.py` adds/updates a single entity vector without rebuilding the entire index; used for individual memory saves outside of batch extraction

### 🐛 Bug Fixes

- **Scheduled tasks missing thread** — `_on_task_fire()` now calls `_save_thread_meta()` and `_set_thread_model_override()` before `run_task_background()`, matching the manual-run handler; previously scheduled tasks never created a `thread_meta` row, so threads never appeared in the sidebar and the completion handler's `_thread_exists()` guard silently skipped the final save
- **Telegram displaced tool_call** — Telegram channel now propagates `model_override` from thread config to the LangGraph configurable, fixing "tool_call without response" errors when using cloud models via Telegram
- **Memory system concurrent access** — additional `threading.Lock()` protection around FAISS operations during incremental upserts
- **Email channel import** — fixed minor import path issue in `channels/email.py`
- **Conversation search tool** — minor fix for result formatting
- **Voice module** — minor compatibility fix

### 🧪 Tests

- **745 PASS**, 0 FAIL, 2 WARN (up from 676 in v3.6.0)
- New test sections: Cloud model engine (model detection, provider routing, context heuristics, starred models, vision detection)
- New test sections: Per-thread model override (DB migration, override persistence, picker logic, cloud banner, sidebar icons)
- New test sections: Task stop (TaskStoppedError, stop_event propagation, stop_task(), get_running_task_thread(), stopped state handling, thread existence guard, delete-while-running)
- New test sections: Displaced tool-call repair (stub injection, displaced ToolMessage removal, ordering validation)
- New test sections: FAISS incremental upsert, rebuild optimization
- Extended integration tests for cloud model routing and Telegram /model command

### 📁 Files Changed

| File | Change |
|------|--------|
| **`models.py`** | **Major** — cloud model engine: dual-provider support (OpenAI + OpenRouter), model fetching/caching, starred models, context-size catalog + heuristics, cloud vision detection, `get_llm_for()` / `_get_cloud_llm()` / `is_cloud_model()` / `get_cloud_provider()` |
| **`agent.py`** | **Major** — `TaskStoppedError` exception; `invoke_agent()` rewritten with `stop_event` param and node-level streaming path; displaced tool-call repair after `trim_messages`; auto-retry on orphan errors in both `invoke_agent()` and `_stream_graph()`; cloud model override support in agent/summarizer |
| **`tasks.py`** | **Major** — `stop_task()`, `get_running_task_thread()`, `stop_event` in `_active_runs`, `TaskStoppedError` handling, `_thread_exists()` guard on thread rename, stopped state (status, naming, notification, skip delivery); `_on_task_fire()` now saves thread meta + model override before launching background run |
| **`app_nicegui.py`** | **Major** — cloud setup wizard, Settings → Cloud tab, chat header model picker, cloud warning banner, sidebar cloud/local icons; task stop buttons (3 locations), `stop_task()` in delete handlers, delayed refresh timer; privacy toggles |
| **`threads.py`** | `model_override` column with auto-migration; `_get_thread_model_override()` / `_set_thread_model_override()` |
| **`api_keys.py`** | OpenAI + OpenRouter key definitions; `cloud_config.json` management (starred models, privacy toggles) |
| **`channels/telegram.py`** | `/model` command (list, set, reset); model override propagation to LangGraph config |
| **`memory_extraction.py`** | FAISS rebuild moved from per-thread `_dedup_and_save()` to single call in `run_extraction()` |
| **`knowledge_graph.py`** | `_upsert_index()` for incremental FAISS updates; additional thread-safety |
| **`vision.py`** | Cloud vision model compatibility |
| **`test_suite.py`** | ~67 new tests across cloud, model switching, task stop, tool-call repair, FAISS optimization |
| **`requirements.txt`** | Added `openai` |
| **`installer/*`** | Version bump to 3.7.0; cloud-aware launcher (skip Ollama warning when cloud default) |
| **`.github/workflows/ci.yml`** | CI updates for cloud test coverage |
| **`.gitignore`** | New ignore patterns |

---

## v3.6.0 — Knowledge Graph, Memory Visualization & Triple Extraction

Thoth now builds a **personal knowledge graph** from your conversations — a connected web of people, places, facts, and their relationships. Memories are no longer isolated records: they are linked entities that the agent can traverse, explore, and reason about. A new interactive **Memory tab** visualizes the graph in real time, and the extraction pipeline now produces structured triples (entity + relation + entity) instead of flat facts.

### 🕸️ Knowledge Graph Engine

New `knowledge_graph.py` — the foundation for all memory storage, replacing the standalone SQLite + FAISS implementation that lived in `memory.py`.

- **Entity-relation model** — every memory is now an entity with a type, subject, description, aliases, tags, and structured properties; entities are connected by typed, directional relations (e.g. `Dad --[father_of]--> User`, `User --[lives_in]--> London`)
- **Triple storage** — SQLite `entities` + `relations` tables with full CRUD; WAL mode for concurrent reads; cascade delete removes orphaned relations when an entity is deleted
- **NetworkX in-memory graph** — a `DiGraph` mirror of the database, rebuilt on startup, used for all traversals and pathfinding; updated atomically on every write
- **FAISS vector index** — unchanged Qwen3-Embedding-0.6B embeddings for semantic similarity; now indexes entity descriptions from the graph layer
- **Alias resolution** — entities can have comma-separated aliases (e.g. "Mom, Mother, Mama"); `find_by_subject()` checks both the `subject` column and the `aliases` column via normalized substring matching, preventing duplicates across names
- **Graph-enhanced recall** — `graph_enhanced_recall(query, top_k, threshold, hops)` first retrieves semantically similar entities via FAISS, then expands N hops in the NetworkX graph to include connected neighbors; the agent sees both the entity and the relationships that connect it
- **Backward-compatible wrapper** — `memory.py` is now a thin delegation layer (~80 lines) that maps legacy column names (`category` to `entity_type`, `content` to `description`) so all existing callers (agent, tools, extraction, UI) work without changes
- **Graph statistics** — `get_graph_stats()` returns entity count, relation count, connected components, and category breakdown for the Settings panel and Memory tab

### 🗺️ Interactive Memory Visualization

A new **Memory tab** on the home screen renders the knowledge graph as an interactive network diagram using vis-network.

- **vis-network integration** — bundled `vis-network.min.js` (9.1.9), served as a static file; renders a force-directed physics simulation in a full-height dark canvas
- **Color-coded entity types** — each category (person, place, fact, preference, event, project) has a distinct color; relation edges show their type as a label
- **Search bar** — live client-side filtering; type a name and the graph highlights matching nodes and fades everything else
- **Entity-type filter buttons** — toggle visibility of entire categories (e.g. show only people and places); buttons are generated dynamically from the data
- **Full map / ego-graph toggle** — switch between the complete graph and a focused 2-hop neighborhood around a selected node
- **Clickable detail card** — clicking a node shows a floating card with the entity's type, description, aliases, tags, source, and a list of all its relationships
- **Fit-to-view button** — resets the camera to fit all visible nodes
- **Live refresh** — graph data is reloaded from the database every time you switch to the Memory tab, so newly extracted entities appear immediately
- **Stats bar** — shows total memories and connections at the top of the panel; expanded stats in Settings show connected components and category breakdown

### 🔗 Memory Tool: Link & Explore

Two new sub-tools on the Memory tool give the agent direct access to the knowledge graph:

- **`link_memories`** — create a typed relationship between any two entities by ID; the agent can say *"Link Mom to Mom's Birthday Party with relation has_event"*; validates both entities exist and returns a confirmation with the relation details
- **`explore_connections`** — traverse the graph outward from an entity; returns all neighbors up to N hops with their relationship types and details; useful for questions like *"Tell me about my family"* or *"What do you know about my work?"*; capped at 3 hops to prevent excessive traversal

### 🧬 Triple-Based Extraction Pipeline

The background extraction pipeline now produces structured triples instead of flat entity records.

- **Entity + Relation extraction** — the LLM prompt now asks for two types of objects: entities (category/subject/content/aliases) and relations (relation_type/source_subject/target_subject/confidence); a worked example in the prompt guides the model
- **"User" entity convention** — the user is always represented by the entity with subject "User"; when the user says *"My name is Alex"*, extraction creates an alias on the User entity rather than a separate "Alex" entity; all user-facing relations use "User" as the source or target
- **Relation type taxonomy** — the prompt includes 30+ suggested relation types across family, social, location, work, preference, and temporal categories, encouraging consistent labeling
- **Two-pass dedup** — Pass 1 saves/updates entities while building a `subject-to-id` map (pre-populated with the User entity), with alias merging; Pass 2 resolves relation subjects to entity IDs and creates relations in the graph
- **Cross-category dedup** — `find_by_subject(None, subject)` searches across all categories, so a "Dad" stored as `person` won't be duplicated when extraction classifies a related fact as `event`
- **Alias-as-list fix** — handles LLMs that return aliases as a JSON array instead of a comma-separated string

### 🔄 Agent Recall Upgrade

Auto-recall now uses the knowledge graph instead of flat semantic search.

- **Graph-enhanced auto-recall** — before every LLM call, the agent retrieves relevant entities via `graph_enhanced_recall()` with 1-hop expansion, so related entities are surfaced alongside direct matches
- **Relation context in recalled memories** — recalled memories now include their graph connections (e.g. "connected via: Dad --> father_of --> User"), giving the agent richer context for answering relational questions
- **System prompt update** — new BUILDING CONNECTIONS and EXPLORING CONNECTIONS sections guide the agent on when to use `link_memories` and `explore_connections`

### 🐛 Bug Fixes

- **Aliases-as-list crash** — fixed `AttributeError` when the extraction LLM returned aliases as a JSON array instead of a comma-separated string
- **Extraction relation resolution** — relations with unresolvable subjects (no matching entity in the DB or current batch) are silently skipped instead of crashing
- **Memory visualization toolbar reliability** — fixed intermittent loss of filter buttons and broken Fit button on the Memory tab; root cause was `ui.add_body_html()` accumulating persistent `<script>` tags on every panel rebuild, causing racing IIFE closures with stale data; replaced with `ui.run_javascript()` (no persistent tags), added teardown that destroys the old vis.Network and cancels stale boot timers, moved vis-network library load to `<head>` (once per page), and made `thothGraphRedraw` perform a full reinit (filter pills + event handlers + network) instead of just re-creating the network
- **Email channel feedback loop** — sent replies weren't marked as read, so the Email channel re-processed its own outbound messages in an infinite loop; fixed by calling `_mark_as_read(service, sent_id)` after both `_send_reply()` and `_send_reply_and_get_id()`
- **macOS MPS/FAISS crash** — `HuggingFaceEmbeddings` defaulted to MPS on Apple Silicon, causing dtype mismatches when FAISS (CPU-only) consumed the tensors; fixed by forcing `model_kwargs={"device": "cpu"}` in `documents.py`
- **FAISS concurrent-access crash** — concurrent calls to `rebuild_index()` and `semantic_search()` could corrupt the in-memory FAISS index; fixed by adding a `threading.Lock()` around all FAISS read/write operations in `knowledge_graph.py`
- **Conversation export 0-byte files on Windows** — thread names containing colons (from timestamps like `02:20 AM`) caused NTFS Alternate Data Streams instead of normal files; exports appeared as 0-byte files with no extension; fixed by sanitizing `\ / : * ? " < > |` from export filenames before writing

### 🚀 Out-of-Box Tool Defaults

Three tools that previously required manual setup are now **enabled by default** on fresh installs, with sensible defaults that work immediately.

- **Filesystem** — enabled by default; workspace auto-defaults to `~/Documents/Thoth` (created on first use); `move_file` added to default operations (protected by interrupt gate — user must approve before execution); `file_delete` still requires opt-in
- **Shell** — enabled by default; already has 3-tier safety (safe commands auto-execute, moderate commands require user approval via interrupt, dangerous commands are blocked outright)
- **Browser** — enabled by default; lazy-launched on first use (no overhead if unused); uses system Chrome/Edge if available, falls back to Playwright's bundled Chromium

### 📬 Telegram Tool & File Pipeline

New **Telegram tool** (`tools/telegram_tool.py`) — the agent can now send messages, photos, and documents to any Telegram chat via the configured bot.

- **3 sub-tools** — `send_telegram_message`, `send_telegram_photo`, `send_telegram_document`; all accept a `chat_id` parameter (defaults to the configured channel)
- **File path resolution** — workspace-relative paths are automatically resolved to absolute paths before sending; works for both Telegram and Gmail attachments
- **Chart PNG export** — `save_to_file` parameter on the Chart tool lets the agent save charts as PNG files (via kaleido) for attaching to messages or emails
- **PDF export** — new `export_to_pdf` operation on the Filesystem tool creates PDF reports from text content (via fpdf2)
- **Gmail attachments** — `send_gmail_message` and `create_gmail_draft` now accept an `attachments` list; files are MIME-encoded and attached via `_build_mime_message()`; missing files are silently skipped with a warning in the message body

### 📨 Channel Resilience & Interrupt Handling

Both the Telegram and Email channels now handle interrupts (destructive action approvals) robustly, with matching logic across both adapters.

- **List-of-dicts interrupt data** — `_format_interrupt()` handles both single interrupt dicts and lists of dicts (produced by multi-step tool chains); extracts the description from each item
- **Interrupt ID propagation** — `_extract_interrupt_ids()` pulls tool-call IDs from interrupt data for correct LangGraph `resume()` targeting; both `_resume_agent_sync()` implementations pass `interrupt_ids` to avoid replaying stale interrupts
- **Corrupt thread recovery** — both channels detect corrupt checkpoints (orphaned tool calls without results) via `_is_corrupt_thread_error()` pattern matching; users receive a friendly message asking them to start a new thread instead of a raw traceback
- **HTML formatting** — Telegram channel formats agent responses as HTML (`parse_mode="HTML"`) with proper escaping for special characters
- **Email sender filter** — the Email channel only processes messages from the authenticated user's own address (`from:{my_email}` in the Gmail query), preventing unauthorized triggering

### 🔒 Task-Scoped Background Permissions

Background tasks now support fine-grained permission controls for operations that would normally require interactive approval.

- **Tiered tool filtering** — background tasks no longer blanket-strip all destructive tools; instead, a tiered system applies:
  - **Always allowed in background**: `workspace_move_file`, `move_calendar_event`, `send_gmail_message` (low-risk or guarded at runtime)
  - **Allowed with runtime guard**: `run_command` (shell) checks against a per-task command prefix allowlist; `send_gmail_message` checks against a per-task recipient allowlist
  - **Always blocked in background**: `workspace_file_delete`, `delete_calendar_event`, `delete_memory`, `tracker_delete`, `task_delete` (irreversible)
- **Per-task allowlists** — two new fields on each task: `allowed_commands` (shell command prefixes) and `allowed_recipients` (email addresses); stored as JSON arrays in `tasks.db`
- **Shell tool runtime guard** — in background mode, commands classified as `needs_approval` are checked against `allowed_commands` (case-insensitive prefix match); blocked patterns (e.g. `rm -rf`) are still rejected before the allowlist check; safe commands (e.g. `dir`, `echo`) always execute
- **Gmail tool runtime guard** — in background mode, all recipients (to/cc/bcc) are validated against `allowed_recipients` (case-insensitive); any disallowed recipient blocks the send
- **UI configuration** — the task editor has a new "🔒 Background permissions (optional)" expandable section with two textareas (one-per-line entry); if the allowlist is blank and the task needs the operation, it fails with a user-friendly error directing the user to configure permissions in the task editor
- **No LLM awareness required** — the agent writes prompts naturally; the permission system operates transparently at the tool execution layer

### 🛡️ Security: ContextVar Background Flag

Fixed a critical security issue where the background-mode flag did not propagate to LangGraph executor threads.

- **Bug**: `threading.local()` was used for `_tlocal.background_workflow`, but LangGraph runs tool functions in separate executor threads where `threading.local()` values are not inherited — so `is_background_workflow()` always returned `False` in tool execution, bypassing background safety gates
- **Fix**: Replaced with `ContextVar` (`_background_workflow_var`), which correctly propagates to child threads via Python's `contextvars` module; updated all 6 references across `agent.py`, `tasks.py`, and `workflows.py`
- **Impact**: Shell tool and Gmail tool background guards now work correctly; `_wrap_with_interrupt_gate()` properly detects background mode in executor threads

### 🧪 Tests

- **676 PASS**, 0 FAIL, 2 WARN (up from 408 in v3.5.0)
- 3 new offline test sections: Knowledge Graph core (section 26, 55 tests), Graph Visualization (section 27, 28 tests — includes 7 visualization reliability regression tests), Triple Extraction (section 28, 18 tests)
- Section 30: File & Messaging Pipeline (30 tests) — Telegram tool, file resolution, chart PNG export, PDF export, Gmail attachments, channel interrupt handling, corrupt thread recovery
- Section 31: Task-scoped background permissions (15 tests) — allowlist columns, ContextVar propagation, shell prefix matching, Gmail recipient checks, UI permission fields
- Section 32: Security audit (12 tests) — ContextVar usage verification, background flag propagation, interactive channel safety, blocked pattern enforcement
- Section 33: Tool default configuration (8 tests) — filesystem/shell/browser enabled by default, default workspace auto-creation, DEFAULT_OPERATIONS validation, interrupt gate coverage
- Section 34: Export filename sanitization (8 tests) — colon replacement, emoji preservation, all illegal-char removal, pathlib suffix correctness, edge cases
- New `integration_tests.py` — 15-section integration test suite (~122 tests) that runs against a live Ollama instance; covers agent routing, memory CRUD, knowledge graph relations, extraction pipeline, task engine, TTS, tool functions, edge cases, extended tool sub-tools (shell classify, filesystem sandbox, chart pipeline, PDF export), channel utilities (Telegram message splitting & HTML formatting), background permissions & ContextVars, bug-fix verifications, and tool default validations; supports `--fast` (skip LLM tests) and `--section N` (run one section)

### 📁 Files Changed

| File | Change |
|------|--------|
| **`knowledge_graph.py`** | **New** — entity-relation graph engine with SQLite + NetworkX + FAISS; `threading.Lock()` around FAISS operations for thread safety |
| **`static/vis-network.min.js`** | **New** — bundled vis-network 9.1.9 for graph visualization |
| **`integration_tests.py`** | **New** — 15-section live integration test suite (~122 tests) |
| **`tools/telegram_tool.py`** | **New** — Telegram messaging tool with 3 sub-tools (send message, photo, document) |
| **`memory.py`** | Refactored from ~530 lines of standalone SQLite+FAISS to ~80-line wrapper delegating to `knowledge_graph.py`; all public signatures unchanged |
| **`agent.py`** | Auto-recall switched to `graph_enhanced_recall()` with 1-hop expansion; tiered background tool filtering with `_ALWAYS_ALLOWED_BG` set; `_background_workflow_var` ContextVar replaces `threading.local()`; interrupt gate reads ContextVar in executor threads |
| **`tools/memory_tool.py`** | 2 new sub-tools: `link_memories` and `explore_connections`; imports `knowledge_graph` |
| **`tools/shell_tool.py`** | Background mode: runtime allowlist check against `_task_allowed_commands_var` for `needs_approval` commands; blocked patterns still enforced first; enabled by default |
| **`tools/gmail_tool.py`** | `send_gmail_message` / `create_gmail_draft`: `attachments` parameter with MIME encoding; background mode: recipient allowlist check against `_task_allowed_recipients_var` |
| **`tools/chart_tool.py`** | `save_to_file` parameter on `_create_chart` for PNG export via kaleido |
| **`tools/filesystem_tool.py`** | New `export_to_pdf` operation (via fpdf2); enabled by default with auto-workspace (`~/Documents/Thoth`); `move_file` added to default operations |
| **`channels/telegram.py`** | List-of-dicts interrupt handling; corrupt thread recovery; HTML formatting; interrupt ID propagation |
| **`channels/email.py`** | List-of-dicts interrupt handling; corrupt thread recovery; interrupt ID propagation; sender-only filter; feedback-loop fix (`_mark_as_read` on sent replies) |
| **`prompts.py`** | System prompt: BUILDING CONNECTIONS + EXPLORING CONNECTIONS sections; BACKGROUND TASK PERMISSIONS note. Extraction prompt: rewritten for triple extraction with User entity convention, relation taxonomy, and worked example |
| **`memory_extraction.py`** | Two-pass pipeline (entities then relations); alias merging; `subject-to-id` map with User pre-population; aliases-as-list fix |
| **`tasks.py`** | `allowed_commands` and `allowed_recipients` columns with DB migration; `run_task_background` sets ContextVars; `_background_workflow_var.set(True)` |
| **`workflows.py`** | `_background_workflow_var.set(True)` (ContextVar migration) |
| **`app_nicegui.py`** | Memory tab with vis-network graph visualization; task editor "🔒 Background permissions" section with allowlist textareas; visualization toolbar reliability fix; export filename sanitization (`_safe_filename`) for Windows NTFS compatibility |
| **`tools/browser_tool.py`** | Enabled by default |
| **`documents.py`** | Forced `model_kwargs={"device": "cpu"}` on `HuggingFaceEmbeddings` to prevent MPS/FAISS crash on Apple Silicon |
| **`requirements.txt`** | Added `networkx`, `fpdf2` |
| **`test_suite.py`** | 8 new sections (26-28, 30-34), ~238 new test assertions |
| **`.gitignore`** | Added `_*.py` and `seed_knowledge_graph.py` |

---

## v3.5.0 — Task Engine, Channel Delivery & Configurable Compression

Complete rewrite of the automation engine — workflows and timers are replaced by a unified **Task Engine** with APScheduler, 7 schedule types, per-task model override, channel delivery (Telegram / Email), persistent run history, a redesigned home screen dashboard, and configurable retrieval compression.

### ⚡ Task Engine (replaces Workflows + Timer)

The old `workflows.py` + `timer_tool.py` are replaced by a single `tasks.py` module backed by APScheduler.

- **7 schedule types** — `daily`, `weekly`, `weekdays`, `weekends`, `interval` (minutes), `cron` (full cron expression), `delay_minutes` (one-shot quick timer with notify-only)
- **SQLite persistence** — `tasks.db` with `tasks` + `task_runs` tables; all schedule formats, delivery config, and model override stored per task
- **Auto-migration** — on first launch, existing `workflows.db` entries are migrated to `tasks.db` automatically; old daily/weekly schedules map to the new types
- **APScheduler integration** — tasks are registered as APScheduler jobs on startup; fire times, pause/resume, and next-run queries come from the scheduler directly
- **Per-task model override** — each task can specify a different LLM; the engine loads the override model, runs the task, then restores the default; retry fallback if the override model fails (HTTP 500)
- **Template variables** — `{{date}}`, `{{day}}`, `{{time}}`, `{{month}}`, `{{year}}` expanded at runtime in prompt steps
- **5 default templates** — Daily Briefing, Research Summary, Email Digest, Weekly Review, and Quick Reminder (new)
- **Run history persistence** — `task_runs` rows survive task deletion (no FK cascade); `get_recent_runs()` uses LEFT JOIN + COALESCE so history displays even after the parent task is removed
- **Status tracking** — each run records `status` (`completed` / `failed` / `completed_delivery_failed`), `status_message`, `task_name`, and `task_icon` columns

### 📋 Task Tool (replaces Timer Tool)

New `tools/task_tool.py` with 5 sub-tools (up from 3 in the old timer):

- `task_create` — create a scheduled task with any of the 7 trigger types
- `task_list` — list all tasks with next fire times
- `task_update` — update task name, prompts, schedule, delivery, or model override
- `task_run_now` — execute a task immediately
- `task_delete` — delete a task (requires user confirmation via interrupt gate)

### 📡 Channel Delivery

Tasks can now deliver their output to a messaging channel after execution.

- **`delivery_channel`** + **`delivery_target`** fields on each task — supports `telegram` (chat ID) and `email` (address + subject)
- **`_validate_delivery()`** — pre-flight check ensures the channel is configured and reachable before the task runs
- **`_deliver_to_channel()`** — sends the task's last LLM response to the configured channel; returns `(status, message)` tuple
- **`completed_delivery_failed`** status — task succeeds but delivery fails (channel error, empty response, etc.)
- **Telegram `send_outbound(chat_id, text)`** — new method on the Telegram channel; captures the bot event loop; RuntimeError guard for missing loop
- **Email `send_outbound(to, subject, body)`** — new method on the Email channel; sends via Gmail OAuth

### 🏠 Dashboard Redesign

- **Tabbed home screen** — two tabs: **⚡ Tasks** (task tiles with edit/run/delete) and **📋 Activity** (monitoring panel)
- **Task Edit dialog** — inline editor for name, icon, prompts, schedule, delivery channel, and model override
- **Activity panel** — 5 sections: Running Now (progress + spinner), Upcoming (next fire times from APScheduler), Recent Runs (last 10 with ✅/❌/⏳ icons), Memory Extraction status, Channel status (🟢/🔴)
- **Settings Workflows tab removed** — 12 → 11 settings tabs; task management moved to the home screen
- **Wider layout** — `max-w-5xl` → `max-w-7xl` for better use of wide screens

### 🔍 Configurable Retrieval Compression

Retrieval-based tools (Documents, Wikipedia, Arxiv, Web Search) now support 3 compression modes, selectable from Settings → Search:

- **Smart** (default) — `EmbeddingsFilter` with cosine similarity threshold 0.5; fast, no extra LLM call; preserves source metadata and citations
- **Deep** — `LLMChainExtractor`; sends each retrieved document through the LLM for precise extraction; slower but highest relevance
- **Off** — no compression; returns raw retrieved chunks as-is

Global config stored in `tools_config.json` under the `"global"` key via `registry.get_global_config()` / `set_global_config()`.

### 🐛 Bug Fixes

- **Model override 500 errors** — retry fallback when per-task model fails to load
- **Context size cap** — `get_llm_for()` uses `min(model_max, user_setting)` to prevent context overflows
- **Model swap during override tasks** — `_model_override_var` ContextVar propagates override model name to `_get_compressor()` and `_do_summarize()`, preventing GPU model eviction
- **Delivery content bug** — `invoke_agent()` returns `str`, not `dict`; fixed `isinstance(result, dict)` check that was always False
- **Empty delivery** — tasks now deliver even when `last_response` is empty (falls back to status message)
- **Telegram error propagation** — `send_outbound` now properly raises on failure instead of silently swallowing errors
- **Email error propagation** — same fix for the Email channel

### 🧪 Tests

- **408 PASS**, 0 FAIL, 2 WARN (up from 322)
- 4 new test sections: Task Tool (§21, 11 tests), Activity Tab (§22, 10 tests), Channel Delivery (§23, 20 tests), Task Engine + Compression (§24–25, 45 tests)

### 📁 Files Changed

| File | Change |
|------|--------|
| **`tasks.py`** | **New** — unified task engine replacing `workflows.py` + `timer_tool.py` |
| **`tools/task_tool.py`** | **New** — 5 sub-tools for task CRUD + execute |
| **`tools/timer_tool.py`** | **Deleted** — subsumed by `task_tool.py` |
| **`agent.py`** | `_model_override_var` ContextVar; `_get_compressor()` rewritten with 3 modes (Smart/Deep/Off); `EmbeddingsFilter` import; multi-interrupt support |
| **`app_nicegui.py`** | Tabbed home screen (Tasks + Activity); Task Edit dialog; Settings tabs 12→11; Retrieval Compression selector; wider layout |
| **`channels/telegram.py`** | New `send_outbound()` with RuntimeError guard |
| **`channels/email.py`** | New `send_outbound()` via Gmail OAuth |
| **`models.py`** | `get_llm_for()` context cap with `min(model_max, user_setting)` |
| **`prompts.py`** | Removed timer instructions; added TASKS & REMINDERS section (~45 lines) |
| **`tools/registry.py`** | Global config: `get_global_config()` / `set_global_config()` |
| **`tools/__init__.py`** | `timer_tool` → `task_tool` import swap |
| **`memory_extraction.py`** | New `get_extraction_status()` |
| **`installer/thoth_setup.iss`** | `workflows.py` → `tasks.py`, `timer_tool.py` → `task_tool.py` |
| **`test_suite.py`** | 4 new sections (§21–25), 86 new tests |

---

## v3.4.0 — Browser Automation

Full browser automation via Playwright, giving the agent the ability to navigate websites, click elements, fill forms, and manage tabs in a visible Chromium window — plus browser snapshot compression for long browsing sessions and a fix for the gold color regression.

### 🌐 Browser Tool

A new `browser_tool.py` module gives the agent 7 browser sub-tools for autonomous web browsing in a real, visible browser window.

- **Shared visible browser** — runs with `headless=False` so the user can see what the agent is doing and intervene (e.g. type passwords, solve CAPTCHAs)
- **Persistent profile** — `launch_persistent_context()` stores cookies, logins, and localStorage in `~/.thoth/browser_profile/` so sites stay logged-in across restarts
- **Accessibility-tree snapshots** — after every action the tool captures the page's accessibility tree, assigning numbered references (`[1]`, `[2]`, …) to interactive elements so the model can click/type by number
- **Smart snapshot filtering** — deduplicates links, drops hidden elements, soft-caps at 100 interactive elements, and truncates at 25K chars to stay within context limits
- **7 sub-tools**:
  - `browser_navigate` — go to a URL
  - `browser_click` — click an interactive element by its reference number
  - `browser_type` — type text into an input element by reference number
  - `browser_scroll` — scroll the page up or down
  - `browser_snapshot` — take a fresh accessibility snapshot of the current page
  - `browser_back` — go back one page in browser history
  - `browser_tab` — manage tabs (list, switch, new, close)
- **Browser channel detection** — automatically detects installed Chrome, then Edge (Windows), then falls back to Playwright's bundled Chromium
- **PID-scoped crash recovery** — detects stale browser processes from previous crashes and cleans up the profile lock before relaunching
- **Background workflow blocking** — browser actions are blocked when running inside a background workflow

### 🧠 Browser Snapshot Compression

Long browsing sessions (6–10+ actions) can produce 150K+ characters of accessibility snapshots, easily overflowing the context window. A new pre-model trimming pass compresses older browser results.

- **Keep last 2 snapshots in full** — the two most recent browser tool results are sent to the LLM unmodified
- **Compact stubs for older results** — older snapshots are replaced with a one-line stub containing the URL, page title, and action name (`[Prior browser navigate — URL: …, Title: …. Full snapshot omitted to save context.]`)
- **Checkpoint preservation** — only the LLM-visible copy is trimmed; full snapshots remain in the conversation checkpoint for the UI

### 🎨 Gold Color Fix

- **Root cause** — NiceGUI 3.8.0's `ui.html()` defaults to `sanitize=True`, which uses the browser's `setHTML()` Sanitizer API; a WebView2 auto-update between March 12–18 enabled the Sanitizer, which strips inline `style` attributes — breaking all gold-colored text
- **Fix** — added `sanitize=False` to all 18 `ui.html()` calls in `app_nicegui.py` to bypass the Sanitizer API

### 🛠️ Other Improvements

- **Sidebar tagline** — changed from *"Your Knowledgeable Personal Agent"* to *"Personal AI Sovereignty"*
- **System prompt updates** — `prompts.py` updated with BROWSER AUTOMATION routing rules, guiding the agent to use `browser_*` tools when the user mentions browsing and `read_url` only for raw text extraction
- **Test suite** — 293 → 322 tests (added browser tool registration, sub-tool count, snapshot filtering, crash recovery, tab management, and channel detection tests)

### Files Changed

| File | Change |
|------|--------|
| **`tools/browser_tool.py`** | **New** — browser automation tool with `BrowserSession`, `_detect_channel()`, 7 sub-tools, accessibility snapshot with smart filtering, PID-scoped crash recovery, persistent profile |
| **`agent.py`** | Browser snapshot compression in `_pre_model_trim()` — keeps last 2 full, stubs older snapshots |
| **`app_nicegui.py`** | `sanitize=False` on all 18 `ui.html()` calls (gold fix); sidebar tagline changed to *"Personal AI Sovereignty"* |
| **`tools/__init__.py`** | Added `browser_tool` import |
| **`prompts.py`** | BROWSER AUTOMATION routing rules in system prompt |
| **`requirements.txt`** | Added `playwright~=1.58` |
| **`test_suite.py`** | Browser tool tests (293 → 322) |

---

## v3.3.0 — Shell Access & Stop Button

Full shell access with safety classification, a reliable stop button with clean generation cancellation, and filesystem sandboxing improvements.

### 🖥️ Shell Tool

A new `shell_tool.py` module gives the agent the ability to run shell commands on the user's machine — making Thoth a true system assistant.

- **Persistent sessions** — each conversation thread gets its own shell session; `cd`, environment variables, and other state persists across commands
- **3-tier safety classification** — every command is classified before execution:
  - **Safe** (auto-executes) — read-only commands like `ls`, `pwd`, `cat`, `git status`, `pip list`, `echo`, `df`
  - **Moderate** (user approval required) — system-modifying commands like `pip install`, `apt`, `brew`, `kill`, `chmod`, `rm`
  - **Blocked** (rejected outright) — dangerous commands like `shutdown`, `reboot`, `mkfs`, `:(){ :|:& };:`
- **Background workflow blocking** — shell commands are automatically blocked when running inside a background workflow to prevent unattended destructive actions
- **Inline terminal panel** — command output appears in a collapsible terminal panel in the chat UI with clear and history controls
- **History persistence** — command history is saved per-thread in `~/.thoth/shell_history.json` and reloaded when you revisit a conversation
- **Session cleanup** — shell sessions and history entries are cleaned up when threads are deleted

### ⏹️ Stop Button Overhaul

The stop button has been rebuilt from scratch for reliable generation cancellation.

- **`threading.Event` cancellation** — replaces the old boolean flag with a proper `threading.Event` for race-free stop signalling
- **Drain mechanism** — after stop is signalled, the consumer drains the streaming queue until the producer's sentinel `None` arrives or a 30-second timeout expires, preventing stale tokens from leaking into the next generation
- **Checkpoint marker** — a `⏹️ *[Stopped]*` marker is appended to the conversation checkpoint so thread reloads show that a generation was interrupted (works for both mid-thinking and mid-tool-call stops)
- **Orphaned tool call repair** — `repair_orphaned_tool_calls()` now unconditionally appends the stop marker, fixing mid-tool-call stops where no orphans exist but the generation was still interrupted
- **UI feedback** — stop button shows an hourglass icon during the drain phase

### 📁 Filesystem Sandboxing

- **`workspace_*` tool renaming** — all filesystem tools are now prefixed with `workspace_` (e.g. `workspace_read_file`, `workspace_list_directory`) so the LLM understands their scope is limited to the configured workspace folder
- **Out-of-workspace rejection** — file operations targeting paths outside the workspace are rejected with a clear error message directing the agent to use `run_command` instead
- **Filesystem vs Shell routing rules** — the system prompt now includes explicit routing guidelines: `workspace_*` tools for files inside the workspace, `run_command` for anything outside

### 🛠️ Other Improvements

- **Settings tab reorder** — the 12 Settings tabs have been reordered for better workflow (Models first, then Memory, Voice, Workflows, System, Tracker, etc.)
- **System tab** — the old "Filesystem" settings tab has been renamed to "System" with a terminal icon, now containing both filesystem workspace configuration and shell settings
- **Terminal panel UI** — inline terminal panel in chat with toggle bar, auto-show on shell output, clear button, and history reload on thread switch
- **Agent prompt updates** — `prompts.py` updated with FILESYSTEM vs SHELL ROUTING rules, destructive tool name updates, and shell usage guidance
- **Test suite** — 270 → 293 tests (added shell tool tests, stop button tests, filesystem sandboxing tests)

### Files Changed

| File | Change |
|------|--------|
| **`tools/shell_tool.py`** | **New** — shell tool with `ShellSession`, `ShellSessionManager`, `classify_command()`, 3-tier safety, persistent sessions, history |
| **`agent.py`** | `threading.Event` stop mechanism, `repair_orphaned_tool_calls()` with unconditional stop marker, `AIMessage` import, `raw_name` in tool_done payload |
| **`app_nicegui.py`** | Stop button drain mechanism, inline terminal panel, System tab rename, settings tab reorder, shell cleanup on thread delete, `code-friendly` markdown extra |
| **`tools/filesystem_tool.py`** | `_is_outside_workspace()` guard, `workspace_*` renaming, out-of-workspace rejection |
| **`tools/__init__.py`** | Added `shell_tool` import |
| **`prompts.py`** | FILESYSTEM vs SHELL ROUTING rules, destructive tool name updates |
| **`test_suite.py`** | Shell tool tests, stop button tests, filesystem sandboxing tests (270 → 293) |

---

## v3.2.0 — Smart Context & Memory Overhaul

Automatic conversation summarization for unlimited conversation length, a complete rewrite of the memory deduplication system, and centralized prompt management.

### 🧠 Memory System Overhaul

The memory deduplication pipeline has been completely rewritten to fix a critical bug where background extraction could create duplicates or update the wrong memory.

#### Deterministic Dedup (replaces semantic dedup)
- **`find_by_subject()` for live saves** — when the agent saves a memory, an exact normalised-subject lookup (SQL) checks if one already exists in the same category; if it does, the richer content is kept silently — no duplicates created
- **Cross-category dedup for extraction** — background extraction now passes `category=None` to `find_by_subject()`, matching against all categories. This prevents fragmentation when the extraction LLM classifies a fact differently than the live tool (e.g. a birthday saved as `person/Dad` won't be re-created as `event/Dad`)
- **Why not semantic?** — semantic similarity (cosine) proved unreliable for dedup: short extracted content ("Priya") vs rich live content ("User's sister is named Priya and she lives in Manchester") scored only 0.78 — well below any safe threshold. Semantic search remains the right tool for *recall*; deterministic SQL is the right tool for *dedup*

#### Source Tracking
- **`source` column** — every memory is tagged `live` (agent during chat) or `extraction` (background scanner) for diagnostics
- **Migration** — existing databases are automatically migrated via `ALTER TABLE`

#### Active Thread Exclusion
- **`set_active_thread()` API** — the UI layer tells the extractor which thread is currently active; background extraction skips it to avoid race conditions with the live agent

#### Extended Update
- **`update_memory()`** — now accepts optional `subject`, `tags`, `category`, and `source` keyword arguments, not just content

#### Consolidation
- **`consolidate_duplicates(threshold)`** — utility to scan and merge near-duplicate memories that may have accumulated over time

#### Auto-Recall with IDs
- **Memory IDs in context** — auto-recalled memories now include their IDs (`[id=abc123]`) so the agent can use `update_memory` or `delete_memory` with the exact ID when the user corrects or retracts previously saved information

#### Prompt Guidance
- **DEDUPLICATION section** — system prompt tells the agent that `save_memory` handles dedup automatically
- **UPDATING MEMORIES section** — system prompt instructs the agent to use `update_memory` with the recalled ID for corrections, not create a new memory

### 📝 Context Summarization

A new automatic summarization system that compresses older conversation turns, enabling effectively unlimited conversation length within any context window.

- **Automatic trigger** — when token usage exceeds 80% of the context window, a background summarization compresses older conversation turns into a running summary
- **Protected turns** — the 5 most recent turns are never summarized, preserving immediate conversational context
- **Hard trim safety net** — a secondary 85% budget drops the oldest non-protected messages if summarization alone isn't enough
- **Transparent** — the summary is injected as a system message; the user experience is seamless

### 📄 Centralized Prompts

- **New `prompts.py` module** — all LLM prompts extracted from inline strings into a single file: `AGENT_SYSTEM_PROMPT`, `EXTRACTION_PROMPT`, `SUMMARIZATION_PROMPT`
- **Easier tuning** — modify agent behavior, extraction rules, or summarization instructions in one place

### 🛠️ Other Improvements

- **URL Reader** — `MAX_CHARS` increased from 12,000 → 30,000 for more complete page reads
- **System prompt polish** — improved URL reader guidance, documents tool instructions, YouTube transcript handling, consolidated honesty directives
- **Test suite** — 233 → 270 tests (added context summarization tests + 40 memory system integrity tests)

### Files Changed

| File | Change |
|------|--------|
| **`prompts.py`** | **New** — centralized LLM prompts |
| **`memory.py`** | `source` column, `find_by_subject()`, `find_duplicate()`, `consolidate_duplicates()`, `_normalize_subject()`, extended `update_memory()` and `save_memory()` |
| **`memory_extraction.py`** | `_dedup_and_save()` rewritten (deterministic dedup), `set_active_thread()` API, active thread exclusion |
| **`tools/memory_tool.py`** | `_save_memory()` rewritten with deterministic dedup via `find_by_subject()` |
| **`agent.py`** | Context summarization (`_maybe_summarize()`, `_pre_model_trim()`), auto-recall with memory IDs, prompts extracted to `prompts.py` |
| **`app_nicegui.py`** | `set_active_thread()` wired into thread management |
| **`tools/url_reader_tool.py`** | `MAX_CHARS` 12K → 30K |
| **`test_suite.py`** | Sections 16 (context summarization) and 17 (memory integrity) added |

---

## v3.1.0 — macOS Support & Kokoro TTS

Cross-platform macOS support and a complete TTS engine migration from Piper to Kokoro.

### 🍎 macOS Support

- **Native macOS installer** — `Start Thoth.command` — double-click in Finder to install and launch; auto-installs Homebrew, Python 3.12, and Ollama if not present
- **Apple Silicon & Intel** — works on M1/M2/M3/M4 and Intel Macs (macOS 12+)
- **Thoth.app bundle** — auto-generated `.app` with option to copy to /Applications for Dock/Launchpad access
- **CI-built macOS zip** — GitHub Actions builds the macOS release on a real macOS runner with correct Unix permissions
- **Cross-platform codebase** — all Python modules updated to work on both Windows and macOS (platform-specific imports, path handling, sound playback)

### 🔊 Kokoro TTS (replaces Piper)

- **New TTS engine** — Kokoro TTS via ONNX Runtime replaces Piper TTS on all platforms
- **Cross-platform** — Kokoro runs natively on Windows, macOS (Apple Silicon & Intel), and Linux — Piper only worked on Windows/Linux
- **10 built-in voices** — 5 American (4 female, 1 male), 3 American male, 1 British female, 1 British male (up from 8 Piper voices)
- **Auto-download** — model files (~169 MB) are downloaded automatically on first TTS use; no bundling required in the installer
- **Same streaming UX** — sentence-by-sentence playback, mic gating, code block skipping — all preserved
- **Smaller installer** — Windows installer reduced from ~90 MB to ~30 MB (Piper engine + voice no longer bundled)

### 🛠️ Infrastructure

- **CI updated** — GitHub Actions `ci.yml` now includes a `build-mac-release` job that builds the macOS zip on `macos-latest` and uploads as an artifact
- **Test suite** — 205 tests passing (added Kokoro TTS tests, all platforms)
- **Windows installer** — Piper download steps removed from `build_installer.ps1` and `thoth_setup.iss`

---

## v3.0.0 — NiceGUI, Messaging Channels & Habit Tracker

Complete frontend rewrite from Streamlit to NiceGUI, new messaging channel adapters for Telegram and Email, and a conversational habit/health tracking system.

### 📋 Habit & Health Tracker

A new conversational tracker for logging and analysing recurring activities — medications, symptoms, exercise, periods, mood, sleep, or anything you want to track over time.

#### Tracking
- **Natural-language logging** — tell the agent *"I took my Lexapro"* or *"Headache level 6"* and it offers to log the entry; no forms or dashboards needed
- **Auto-create trackers** — trackers are created on first mention; supports boolean, numeric, duration, and categorical types
- **Backfill** — log entries with a past timestamp: *"I took my meds at 8am"*
- **3 sub-tools** — `tracker_log` (structured input), `tracker_query` (free-text read-only), `tracker_delete` (destructive, requires confirmation via interrupt)

#### Analysis
- **7 built-in analyses** — adherence rate, current/longest streaks, numeric stats (mean/min/max/σ), frequency (per week/month), day-of-week distribution, cycle estimation (period tracking), co-occurrence between any two trackers
- **Trend queries** — *"Show my headache trends this month"* returns stats + exports CSV for charting
- **Chart chaining** — CSV exports are passed to the existing Chart tool for interactive Plotly visualisations (bar, line, scatter, etc.)
- **Co-occurrence** — *"Do headaches correlate with my period?"* compares two trackers within a configurable time window

#### Privacy & Integration
- **Fully local** — SQLite database at `~/.thoth/tracker/tracker.db`; CSV exports in `~/.thoth/tracker/exports/`
- **Memory separation** — tracker data is excluded from the memory extraction system; logging meds won't pollute your personal knowledge base
- **Agent prompt integration** — system prompt instructs the agent to confirm before logging and to chain to `create_chart` for visual outputs

### 🎯 Context-Size Capping

- **Automatic model-max enforcement** — if you select a context window larger than the model's native maximum (e.g. 64K on a 40K-max model), trimming and the token counter automatically use the model's actual limit instead of the user-selected value
- **Model metadata query** — `get_model_max_context()` queries Ollama's `show()` API for the model's `context_length` and caches the result per model
- **Toast notifications** — a warning toast appears when changing models or context size if the selection exceeds the model's native max, explaining which value will actually be used
- **Settings info label** — the Models tab shows an inline note below the context selector when capping is active

---

### 🖥️ NiceGUI Frontend

The entire UI has been rewritten using [NiceGUI](https://nicegui.io/), replacing Streamlit. The new frontend runs on port **8080** and offers a faster, more responsive experience with true real-time streaming.

- **Full feature parity** — all existing functionality ported: chat interface, sidebar thread manager, settings dialog (now 11 tabs), file attachments, streaming, voice bar, export, workflows
- **Real-time updates** — no more page reloads; token streaming, tool status, and toast notifications update instantly via websocket
- **System tray launcher** — `launcher.py` updated to manage the NiceGUI process
- **Native desktop window** — runs in a native OS window via pywebview instead of a browser tab; `--native` flag passed by default from the launcher
- **Two-tier splash screen** — branded splash (dark background, gold Thoth logo, animated loading indicator) displays while the server starts; tries tkinter GUI first, falls back to a console-based splash if tkinter is unavailable; runs as an isolated subprocess to avoid Tcl/threading conflicts with pystray; self-closes when port 8080 responds
- **First-launch setup wizard** — on first run, a guided dialog lets the user pick a brain model and vision model and download them before the main UI loads
- **Explicit download buttons** — model downloads in Settings are triggered by dedicated Download buttons instead of auto-downloading on selection

### 📬 Messaging Channels

New `channels/` package with two messaging channel adapters:

#### Telegram Bot
- **Long-polling adapter** — connect a Telegram bot via Bot API token
- **Full agent access** — messages are processed by the same ReAct agent with all tools available
- **Thread per chat** — each Telegram chat gets its own conversation thread with a 📱 icon
- **Settings UI** — configure bot token, start/stop, and auto-start on launch from Settings → Channels tab

#### Email Channel
- **Gmail polling** — polls inbox at configurable intervals for new messages
- **OAuth 2.0 authentication** — uses existing Gmail OAuth credentials with re-authenticate button
- **Smart filtering** — responds only to emails from approved senders list
- **Thread per sender** — each email sender gets a dedicated thread with a 📧 icon
- **Auto-start** — channels can be set to auto-start when Thoth launches

### 🔧 Infrastructure

- **Version bump** — v2.2.0 → v3.0.0
- **Installer updated** — Inno Setup script updated for NiceGUI, channels package included; `._pth` patched at install time to add the app directory for channels import; tkinter bundled from system Python for embedded environment
- **Dependencies** — `streamlit` replaced by `nicegui`; `pywebview` added for native window; `pythonnet` added for Python 3.14 compatibility; added missing packages (`apscheduler`, `plyer`, `youtube-search`, `numpy`, `requests`, `pydantic`) to `requirements.txt`
- **Structured logging** — comprehensive `logging` added across 14 modules (`models`, `tts`, `threads`, `api_keys`, `documents`, `agent`, `app_nicegui`, `tools/registry`, `tools/base`, `tools/gmail_tool`, `tools/calendar_tool`, `tools/weather_tool`, `tools/conversation_search_tool`, `tools/system_info_tool`); all output written to `~/.thoth/thoth_app.log` via stderr capture
- **Log noise suppression** — noisy third-party loggers (`httpx`, `httpcore`, `urllib3`, `sentence_transformers`, `transformers`, `huggingface_hub`, `googleapiclient`, `primp`, `ddgs`, `nicegui`, `uvicorn`, etc.) silenced to WARNING+; tqdm/safetensors weight-loading spam suppressed by redirecting stderr during embedding model init; `OPENCV_LOG_LEVEL=ERROR` set at startup
- **Ollama launch fix** — launcher starts `ollama app.exe` (tray icon) instead of bare `ollama serve` for proper Windows integration
- **Unicode fix** — `PYTHONIOENCODING=utf-8` set at startup to prevent cp1252 crashes on non-ASCII model output
- **Lazy FAISS initialization** — embedding model and vector store are now lazy-loaded via getter functions to avoid double-initialization caused by NiceGUI's `multiprocessing.Process` (Windows spawn) re-importing the module
- **Old Streamlit app** — `app.py` kept in repo but git-ignored; not deleted

---

## v2.2.0 — Workflows

A new workflow engine for reusable, multi-step prompt sequences with scheduling support.

---

### ⚡ Workflow Engine

Create named workflows — ordered sequences of prompts that run in a fresh conversation thread. Each step sees the output of the previous one, enabling chained research → summarisation → action pipelines.

#### Core Features
- **Multi-step prompt sequences** — define 1+ prompts that execute sequentially in a single thread
- **Template variables** — `{{date}}`, `{{day}}`, `{{time}}`, `{{month}}`, `{{year}}` are replaced at runtime
- **Live streaming** — workflows stream in real-time with a step progress indicator in the chat header
- **Background completion** — navigate away mid-workflow and it continues silently; the sidebar shows a running indicator
- **Desktop notifications** — scheduled and background runs trigger a Windows notification on completion

#### Scheduling
- **Daily schedule** — run a workflow automatically at a specific time every day
- **Weekly schedule** — run on a specific day and time each week
- **Scheduler engine** — background thread checks for due workflows every 60 seconds
- **Enable/disable** — toggle scheduled workflows on or off without deleting the schedule

#### UI
- **Home screen tiles** — workflows appear as clickable cards on the home screen (no thread selected) with Run buttons
- **Inline quick-create** — create new workflows directly from the home screen
- **Settings → Workflows tab** — full management view with name, icon, description, prompt editor (add/remove/reorder steps), schedule config, run history
- **Duplicate & Delete** — one-click workflow cloning and deletion
- **Run history** — past executions shown per workflow with timestamps, step counts, and status

#### Pre-built Templates
Ships with 4 starter workflows that can be customised or deleted:
- **📰 Daily Briefing** — top news + weather + today's calendar (3 steps)
- **🔬 Research Summary** — search latest AI developments + summarise with citations (2 steps)
- **📧 Email Digest** — check Gmail inbox + summarise by priority (2 steps)
- **📋 Weekly Review** — past week's calendar events + review and recommendations (2 steps)

#### Safety
- **Destructive tool exclusion** — background workflow runs automatically exclude destructive tools (send email, delete files, etc.) so they can never execute unattended; the LLM adapts by using safe alternatives (e.g. creating a draft instead of sending)
- **Scheduler double-fire prevention** — `last_run` is set immediately when a scheduled workflow triggers, before execution begins, preventing duplicate runs within the cooldown window

### 🔔 Unified Notification System

A new `notifications.py` module replaces scattered notification calls with a single `notify()` function that fires across three channels simultaneously:

- **Desktop notifications** — via plyer, with timestamped messages showing when the task actually completed
- **Sound effects** — via winsound (lazy-imported for cross-platform safety), played asynchronously in a background thread
- **In-app toasts** — queued for the next Streamlit rerun via `drain_toasts()`, with emoji icons

#### Sound Files
- `sounds/workflow.wav` — two-tone chime (C5→E5) on workflow completion
- `sounds/timer.wav` — 5-beep alert (A5) for timer expiration

Both generated as clean sine-wave tones via Python's `wave` module.

### 🎨 UI Polish

- **Sidebar running indicator** — simplified from step count (`⏳ 2/4`) to just `⏳` since the sidebar doesn't auto-refresh
- **Settings tab renamed** — "🎛️ Preferences" → "🎤 Voice" to better describe the tab's contents
- **Workflow emoji picker** — replaced free-text icon input with a selectbox of 20 curated emojis
- **Streamlit sidebar toggle** — added `.streamlit/config.toml` with `toolbarMode = "minimal"` and `hideTopBar = true`

### 📦 Dependency & Compatibility

- **`streamlit>=1.45`** pinned in `requirements.txt` for `st.tabs` stability
- **`winsound` lazy import** — non-Windows platforms gracefully skip sound playback instead of crashing

#### Technical Details
- **New modules** — `workflows.py` (workflow engine + scheduler), `notifications.py` (unified notify + toast queue)
- **New assets** — `sounds/workflow.wav`, `sounds/timer.wav`
- **New config** — `.streamlit/config.toml` (sidebar/toolbar settings)
- **Prompt chaining** — first step streams live, subsequent steps continue via `stream_agent` or fall back to `invoke_agent` in background
- **Thread naming** — workflow threads are prefixed with ⚡ and include the workflow name and timestamp
- **Settings tab count** — Settings dialog now has 10 tabs (added Workflows, renamed Preferences → Voice)
- **Background flag** — `threading.local()` (`_tlocal`) flags background workflows; agent graph cache key includes `bg:{True/False}` for separate tool sets
- **Timer tool updated** — replaced inline `_notify()` with `notifications.notify()` for consistent sound + desktop + toast

---

## v2.1.0 — Semantic Memory & Voice Simplification

A major upgrade to the memory system and a complete simplification of the voice pipeline.

---

### 🧠 Semantic Memory System

The memory system has been upgraded from keyword-based search to full **FAISS semantic vector search** with automatic recall and background extraction.

#### Semantic Search
- **FAISS vector index** — memories are now embedded with `Qwen3-Embedding-0.6B` and stored in a FAISS index at `~/.thoth/memory_vectors/`
- **Cosine similarity search** — `semantic_search()` replaces the old keyword `LIKE` queries for much better recall on indirect/paraphrased queries
- **Auto-rebuild** — the FAISS index automatically rebuilds on any memory mutation (save, update, delete)

#### Auto-Recall
- **Automatic memory injection** — before every LLM call, the current user message is embedded and the top-5 most relevant memories (threshold ≥ 0.35) are injected as a system message
- **Assertive phrasing** — recalled memories are presented as "You KNOW the following facts about this user" so the model treats them as ground truth
- **System prompt reinforcement** — the agent is explicitly instructed to save buried personal info alongside other requests

#### Background Memory Extraction
- **LLM-powered extraction** — on startup and every 6 hours, past conversations are scanned by the LLM to extract personal facts (names, preferences, projects, etc.)
- **Semantic deduplication** — extracted facts are compared against existing memories using cosine similarity; duplicates (> 0.85) update existing entries, novel facts create new ones
- **Incremental scanning** — only conversations updated since the last extraction run are processed
- **State persistence** — extraction timestamps tracked in `~/.thoth/memory_extraction_state.json`
- **New module** — `memory_extraction.py` added to the codebase

### 🎤 Voice Pipeline Simplification

The voice pipeline has been completely rewritten for reliability and simplicity.

#### What Changed
- **Removed wake word detection** — no more OpenWakeWord, ONNX models, or "Hey Jarvis"/"Hey Mycroft" activation
- **Removed `wake_models/` directory** — deleted all bundled ONNX wake word model files
- **Removed auto-timeout and heartbeat** — no more inactivity timer or browser heartbeat polling
- **Removed follow-up mode** — no more timed mic re-open window after TTS playback
- **Removed tool call announcements** — TTS no longer speaks tool names aloud during execution

#### New Design
- **Toggle-based activation** — simple manual toggle to start/stop listening
- **4-state machine** — clean state transitions: `stopped` → `listening` → `transcribing` → `muted`
- **CPU-only Whisper** — faster-whisper runs exclusively on CPU with int8 quantization for consistent performance
- **Medium model support** — added `medium` to the Whisper model size options (tiny/base/small/medium)
- **Voice-aware responses** — voice input is tagged with a system hint so the agent responds conversationally
- **Status safety net** — auto-unmutes when TTS finishes but pipeline state is stuck on "muted"

### 🔊 TTS Markdown-to-Speech Improvements

The `_MD_STRIP` regex pipeline in `tts.py` has been overhauled for cleaner speech output:
- Fixed bold/italic/strikethrough pattern ordering (triple before double before single)
- Added black circle, middle dot, and additional bullet character stripping
- Added numbered list prefix stripping (both `1.` and `1)` styles)
- Moved bullet stripping before emphasis patterns to prevent partial matches
- Removed broken `_italic_` pattern

### 🚀 Startup UX Revamp

- **Live progress steps** — replaced generic "Loading models…" spinner with `st.status` widget showing each initialization step (core modules, documents, models, API keys, voice/TTS, vision, memory extraction)
- **No flicker on reruns** — startup UI only shows on first run; thread switches and page reruns skip it entirely via session state gate
- **Clean banner removal** — startup status wrapped in `st.empty()` placeholder for clean removal after load

### 🧹 Cleanup

- **Deleted `wake_models/` directory** — removed all bundled ONNX wake word model files (alexa, hey_jarvis, hey_mycroft, hey_thought)
- **Cleaned installer references** — removed wake_models from `installer/thoth_setup.iss` and `installer/README.md`
- **Removed OpenWakeWord dependency** — no longer referenced in codebase or acknowledgements

### 📦 Data Storage Updates

Two new entries in `~/.thoth/`:
- `memory_vectors/` — FAISS index (`index.faiss`) and ID mapping (`id_map.json`) for semantic memory search
- `memory_extraction_state.json` — tracks last extraction run timestamp per thread

### 🧹 Codebase Changes

- **Added**: `memory_extraction.py` (background extraction + dedup + periodic timer)
- **Updated**: `memory.py` (FAISS vector index, `semantic_search()`, `_rebuild_memory_index()`, shared embedding model)
- **Updated**: `agent.py` (auto-recall injection in `_pre_model_trim`, updated system prompt for memory awareness)
- **Updated**: `voice.py` (complete rewrite — 4-state toggle machine, CPU-only int8 Whisper, no wake word)
- **Updated**: `tts.py` (overhauled `_MD_STRIP` patterns, removed tool call announcements)
- **Updated**: `app.py` (startup UX revamp, memory extraction integration, voice simplification)
- **Updated**: `tools/memory_tool.py` (`search_memory` now uses `semantic_search()`)
- **Updated**: `installer/thoth_setup.iss` (removed wake_models references)
- **Updated**: `installer/README.md` (removed wake_models from bundled files)
- **Deleted**: `wake_models/` directory (4 ONNX files)

---

## v2.0.0 — ReAct Agent Rewrite

**A complete architectural overhaul.** Thoth v2 replaces the original RAG pipeline with a fully autonomous ReAct agent that can reason, use tools, and carry persistent memory across conversations.

---

### 🏗️ Architecture: RAG Pipeline → ReAct Agent

The original Thoth (v1.x) used a custom LangGraph `StateGraph` with three nodes (`needs_context` → `get_context` → `generate_answer`) to decide whether retrieval was needed, fetch context, and generate cited answers. This worked well for Q&A but couldn't take actions, compose emails, manage files, or remember things.

**Thoth v2** replaces this with a LangGraph `create_react_agent()` — a reasoning loop where the LLM autonomously decides which tools to call, interprets results, and continues until it has a complete answer. The agent can chain multiple tools, retry with different queries, and combine information from several sources in a single turn.

Key changes:
- **`rag.py` removed** — the custom RAG state machine is gone
- **`agent.py` added** — new ReAct agent with system prompt, pre-model message trimming, streaming event generator, and interrupt mechanism
- **Smart context management** — pre-model hook trims history to 80% of context window; oversized tool outputs (e.g. multiple PDFs) are proportionally shrunk so multi-file workflows fit; file reads capped at 80K characters
- **Tool system** — new `tools/` package with `BaseTool` ABC, auto-registration registry, and 19 self-registering tool modules
- **42 sub-tools** exposed to the model (up from 4 retrieval sources)

### 🔧 17 Integrated Tools

Every tool is a self-registering module in `tools/` with configurable enable/disable, API key management, and optional sub-tool selection.

#### Search & Knowledge (7 tools)
- **🔍 Web Search** — Tavily-powered live web search with contextual compression
- **🦆 DuckDuckGo** — free web search fallback, no API key required
- **🌐 Wikipedia** — encyclopedic knowledge retrieval with compression
- **📚 Arxiv** — academic paper search with source URL rewriting
- **▶️ YouTube** — video search + full transcript/caption fetching
- **🔗 URL Reader** — fetch and extract clean text from any web page
- **📄 Documents** — semantic search over user-uploaded files via FAISS vector store

#### Productivity (4 tools)
- **📧 Gmail** — search, read, draft, and send emails via Google OAuth; operations tiered into read/compose/send with individual toggles
- **📅 Google Calendar** — view, search, create, update, move, and delete events via Google OAuth; shares credentials with Gmail
- **📁 Filesystem** — sandboxed file operations (read, write, copy, move, delete) within a user-configured workspace folder; reads PDF, CSV, Excel (.xlsx/.xls), JSON/JSONL, and TSV files; structured data files parsed with pandas (schema + stats + preview); large reads capped at 80K chars; operations tiered into safe/write/destructive
- **⏰ Timer** — desktop notification timers with SQLite persistence via APScheduler; supports set, list, and cancel

#### Computation & Analysis (6 tools)
- **🧮 Calculator** — safe math evaluation via simpleeval — arithmetic, trig, logs, factorials, combinatorics, all `math` module functions
- **🔢 Wolfram Alpha** — advanced computation, symbolic math, unit/currency conversion, scientific data, chemistry, physics
- **🌤️ Weather** — current conditions and multi-day forecasts via Open-Meteo (free, no API key); includes geocoding, wind direction, and WMO weather code descriptions
- **👁️ Vision** — camera capture and screen capture with analysis via Ollama vision models; configurable camera and vision model selection
- **🧠 Memory** — persistent personal knowledge base with save, search, list, update, and delete operations across 6 categories
- **🔍 Conversation Search** — natural language search across all past conversations; keyword matching over checkpoint history with thread names and dates
- **🖥️ System Info** — full system snapshot via psutil: OS, CPU, RAM, disk space per drive, local & public IP, battery status, and top 10 processes by CPU usage
- **📊 Chart** — interactive Plotly charts from data files; structured spec tool supporting bar, horizontal_bar, line, scatter, pie, donut, histogram, box, area, and heatmap; reads from workspace files or cached attachments; auto-picks columns when x/y are omitted; dark theme with interactive zoom/hover/pan

### 🧠 Long-Term Memory

A completely new feature. The agent can now remember personal information across conversations:

- **6 categories**: `person`, `preference`, `fact`, `event`, `place`, `project`
- **Agent-driven saving** — the agent recognizes when you share something worth remembering and saves it automatically
- **Cross-conversation recall** — search and retrieve memories from any conversation
- **Full CRUD** — save, search, list, update, and delete memories via natural language
- **SQLite storage** at `~/.thoth/memory.db` with WAL mode
- **Settings UI** — browse, search, filter by category, and bulk-delete from the Memory tab
- **Destructive confirmation** — deleting memories requires explicit user approval

### 👁️ Vision System

New camera and screen capture integration:

- **Webcam analysis** — *"What's in front of me?"*, *"Read this document I'm holding up"*
- **Screen capture** — *"What's on my screen?"*, *"Describe what I'm looking at"*
- **Configurable models** — choose from gemma3, llava, and other Ollama vision models
- **Multi-camera support** — select which camera to use from Settings
- **Inline display** — captured images appear in the chat alongside the analysis

### 🎤 Voice Input

Fully local, hands-free voice interaction:

- **Wake word detection** — 2 built-in wake words (Hey Jarvis, Hey Mycroft) via OpenWakeWord ONNX models
- **Speech-to-text** — faster-whisper with selectable model size (tiny/base/small)
- **Configurable sensitivity** — wake word threshold slider (0.1–0.95)
- **Audio chime** on wake word detection
- **Voice bar UI** — shows listening/transcribing status with real-time feedback
- **Mic gating** — microphone automatically muted during TTS playback to prevent echo and feedback loops
- **Follow-up mode** — after TTS finishes speaking, the mic re-opens briefly so you can ask follow-up questions without re-triggering the wake word

### 🔊 Text-to-Speech

Neural speech synthesis, fully offline:

- **Piper TTS engine** — bundled with installer at the time (engine + default voice); additional voices downloaded from HuggingFace on demand *(replaced by Kokoro TTS in v3.1.0)*
- **8 voices** — US and British English, male and female variants *(expanded to 10 voices with Kokoro in v3.1.0)*
- **Streaming playback** — responses spoken sentence-by-sentence as tokens stream in
- **Smart truncation** — long responses are summarized aloud with full text in the app
- **Code block skipping** — TTS intelligently skips fenced code blocks
- **Mic gating integration** — coordinates with voice input to mute mic during playback and re-enable after

### 💬 Chat Improvements

- **Streaming responses** — tokens appear in real-time with a typing indicator animation
- **Thinking indicators** — "Working…" status when the model is reasoning
- **Tool call status** — expandable status widgets showing which tools are being called and their results
- **Inline YouTube embeds** — YouTube URLs in responses render as playable embedded videos
- **Syntax-highlighted code blocks** — fenced code blocks render with language-aware highlighting and a built-in copy button via `st.code()`
- **File attachments** — drag-and-drop images, PDFs, CSV, Excel, JSON, and text files into the chat input; images analyzed via vision model, PDFs text-extracted, structured data files parsed with pandas (schema + stats + preview), text files injected as context
- **Inline charts** — interactive Plotly charts rendered inline in chat when the Chart tool is used; charts persist across page reloads; dark theme with zoom/hover/pan
- **Image captions** — user-attached images display as "📎 Attached image", vision captures display as "📷 Captured image"
- **Onboarding guide** — first-run welcome message with tool categories, settings guidance, voice tips, and file attachment instructions; 6 clickable example prompts; `?` button in sidebar to re-display; persistence via `~/.thoth/app_config.json`
- **Startup health check** — verifies Ollama connectivity and model availability on launch with user-friendly error messages
- **Conversation export** — export threads as Markdown, plain text, or PDF with formatted role headers and timestamps
- **Stop generation** — circular stop button to cancel streaming at any time- **Live token counter** — gold-themed progress bar in the sidebar showing real-time context window usage based on trimmed (model-visible) history
- **Truncation warnings** — inline warnings when file content was truncated to fit context
- **Error recovery** — agent tool loops (GraphRecursionError) are caught gracefully with a user-friendly message; orphaned tool calls are automatically repaired
### 🛡️ Destructive Action Confirmation

The agent now uses LangGraph's `interrupt()` mechanism to pause and ask for user confirmation before performing dangerous operations:

- File deletion and moves (Filesystem)
- Sending emails (Gmail)
- Moving and deleting calendar events (Calendar)
- Deleting memories (Memory)

The user sees a confirmation dialog with the action details and can approve or deny.

### ⚙️ Settings Overhaul

The Settings dialog has been expanded from a simple panel to a **9-tab dialog**:

1. **🤖 Models** — brain model selection, context window slider, vision model selection, camera picker
2. **🔍 Search** — toggle and configure search tools (Web Search, DuckDuckGo, Wikipedia, Arxiv, YouTube, Wolfram Alpha) with inline API key inputs and setup instructions
3. **📄 Local Documents** — upload, index, and manage documents for the FAISS vector store
4. **📁 Filesystem** — workspace folder picker, operation tier checkboxes (read/write/destructive)
5. **📧 Gmail** — OAuth setup with step-by-step instructions, credentials path picker, authentication status, operation tier checkboxes
6. **📅 Calendar** — OAuth setup (shared credentials with Gmail), authentication, operation tiers
7. **🔧 Utilities** — toggle Timer, URL Reader, Calculator, Weather tools
8. **🧠 Memory** — enable/disable, browse stored memories, search, filter by category, bulk delete
9. **🏛️ Preferences** — voice input (wake word, Whisper model, sensitivity), TTS (voice selection, speed) *(TTS engine changed to Kokoro in v3.1.0)*

### 🖥️ System Tray Launcher

`launcher.py` provides a system tray experience:

- **Tray icon** with color-coded voice state (green = listening, yellow = processing, grey = off)
- **Manages Streamlit subprocess** on port 8501
- **Auto-opens browser** on launch
- **Polls `~/.thoth/status.json`** for live state updates
- **Graceful shutdown** — clean process termination on Quit

### 📦 Data Storage

All user data now lives in `~/.thoth/`:

- `threads.db` — conversation history and LangGraph checkpoints
- `memory.db` — long-term memories (new)
- `api_keys.json` — API keys
- `tools_config.json` — tool enable/disable state and configuration (new)
- `model_settings.json` — selected model and context size (new)
- `processed_files.json` — tracked indexed documents
- `status.json` — voice state for system tray (new)
- `timers.sqlite` — scheduled timer jobs (new)
- `gmail/` — Gmail OAuth tokens (new)
- `calendar/` — Calendar OAuth tokens (new)
- `piper/` — Piper TTS engine and voice models *(replaced by `kokoro/` in v3.1.0)*

### 🧹 Codebase Changes

- **Removed**: `rag.py` (old RAG pipeline — dead code, no longer imported)
- **Added**: `agent.py`, `memory.py`, `voice.py`, `tts.py`, `vision.py`, `launcher.py`
- **Added**: `tools/` package with 16 tool modules, `base.py` (ABC), `registry.py` (auto-registration)
- **Updated**: `app.py` (complete UI rewrite — streaming, voice bar, Settings dialog, export, attachments)
- **Updated**: `threads.py` (added `_delete_thread`, `pick_or_create_thread`)
- **Updated**: `models.py` (added context size management, vision model support)
- **Updated**: `documents.py` (moved vector store to `~/.thoth/`)
- **Default model**: Changed from `qwen3:8b` to `qwen3:14b`

---

## v1.1.0 — Sharpened Recall

### RAG Pipeline Improvements
- Contextual compression retrieval — each retriever wrapped with `ContextualCompressionRetriever` + `LLMChainExtractor`
- Query rewriting — follow-up questions automatically rewritten into standalone search queries
- Parallel retrieval — all enabled sources queried simultaneously via `ThreadPoolExecutor`
- Context deduplication — embedding-based cosine similarity at within-retrieval and cross-turn levels
- Character-based context & message trimming
- Smarter context assessment — embedding similarity check before LLM fallback

### UI Improvements
- Auto-scroll to show new messages and thinking spinner

---

## v1.0.0 — Initial Release

- Multi-turn conversational Q&A with persistent threads
- 4 retrieval sources: Documents (FAISS), Wikipedia, Arxiv, Web Search (Tavily)
- Source citations on every answer
- Document upload and indexing (PDF, DOCX, TXT)
- Dynamic Ollama model switching with auto-download
- In-app API key management
- LangGraph RAG state machine (`needs_context` → `get_context` → `generate_answer`)
