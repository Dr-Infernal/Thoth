import threading

from models import get_llm, get_llm_for, get_context_size, get_current_model, is_model_local, is_cloud_model, get_model_max_context, set_active_model_override
from api_keys import apply_keys
from prompts import AGENT_SYSTEM_PROMPT, SUMMARIZE_PROMPT
from langchain_classic.retrievers import ContextualCompressionRetriever
from langchain_classic.retrievers.document_compressors import LLMChainExtractor
from langchain_core.messages import trim_messages, ToolMessage, AIMessage
from langgraph.types import interrupt, Command
from threads import pick_or_create_thread, checkpointer
import logging

logger = logging.getLogger(__name__)


class TaskStoppedError(Exception):
    """Raised when a running task is cancelled via its stop_event."""


apply_keys()

# ── Contextual compression: extract only query-relevant content per doc ──────
_compressor = None

def _get_compressor():
    """Return a compressor based on the configured mode (deep / off).

    * **deep** — ``LLMChainExtractor``.  K extra LLM calls per tool
      invocation; highest relevance.  Respects ``_model_override_var``.
    * **off** (default) — no compression; ``_pre_model_trim()`` handles
      context overflow by proportionally shrinking tool outputs.
    """
    global _compressor
    from tools.registry import get_global_config
    mode = get_global_config("compression_mode", "off")

    if mode != "deep":
        _compressor = None
        return None

    # mode == "deep" — LLMChainExtractor behaviour
    _ov = _model_override_var.get() or ""
    if _ov and _ov != get_current_model() and (is_model_local(_ov) or is_cloud_model(_ov)):
        _compressor = LLMChainExtractor.from_llm(get_llm_for(_ov))
    else:
        _compressor = LLMChainExtractor.from_llm(get_llm())
    return _compressor

def _compressed(base_retriever):
    """Wrap any retriever with contextual compression.  Public so tool
    modules can call ``from agent import _compressed``."""
    comp = _get_compressor()
    if comp is None:
        return base_retriever
    return ContextualCompressionRetriever(
        base_compressor=comp,
        base_retriever=base_retriever,
    )

# ── Import tools package (triggers auto-registration of all tools) ───────────
import tools  # noqa: E402 — must come after _compressed is defined
from tools import registry as tool_registry


# ═════════════════════════════════════════════════════════════════════════════
# ReAct Agent — LLM decides which tools to call
# ═════════════════════════════════════════════════════════════════════════════
from langgraph.prebuilt import create_react_agent
from datetime import datetime as _datetime


# ── Content normalisation helpers ────────────────────────────────────────────

# Recursion limits: how many LangGraph node executions (LLM call + tool call
# = 2 steps).  50 ≈ 25 tool invocations for interactive; 100 ≈ 50 for tasks.
RECURSION_LIMIT_CHAT = 50
RECURSION_LIMIT_TASK = 100

def _content_to_str(content) -> str:
    """Normalise ``AIMessage.content`` to a plain string.

    Newer models (e.g. gpt-5.4 via OpenAI Responses API) may return content as
    a *list* of typed dicts instead of a plain string.  This extracts all
    ``{"type": "text"}`` blocks and joins them; non-text blocks (reasoning,
    function_call) are discarded.
    """
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, dict):
                if block.get("type") == "text":
                    parts.append(block.get("text", ""))
            elif isinstance(block, str):
                parts.append(block)
        return "\n".join(parts)
    return str(content) if content else ""


def _friendly_api_error(exc_str: str) -> str:
    """Return a user-friendly description for an API / provider error."""
    s = exc_str.lower()
    if "recursion" in s or "recursion limit" in s:
        return "⚠️ I got stuck in a tool loop and had to stop. Try rephrasing your request or starting a new conversation."
    if "insufficient_quota" in s or "exceeded your current quota" in s:
        return "⚠️ API quota exceeded — please check your billing dashboard."
    if "rate_limit" in s or "rate limit" in s or "429" in s:
        return "⚠️ Rate limit reached — please wait a moment and try again."
    if "invalid_api_key" in s or "incorrect api key" in s or "authentication" in s or "unauthorized" in s:
        return "⚠️ Authentication failed — please verify your API key in Settings → API Keys."
    if "billing" in s:
        return "⚠️ Billing limit reached — please review your plan at the provider dashboard."
    if "context_length_exceeded" in s or "context length" in s or "maximum context" in s:
        return "⚠️ Context too long — try starting a new conversation or a model with a larger context window."
    if "server_error" in s or "internal server error" in s or "status code: 500" in s:
        return "⚠️ The AI provider had a server error — please try again shortly."
    if "bad gateway" in s or "status code: 502" in s:
        return "⚠️ The AI provider is temporarily unavailable (502) — please try again shortly."
    if "service unavailable" in s or "status code: 503" in s:
        return "⚠️ The AI provider is temporarily unavailable (503) — please try again shortly."
    if "timeout" in s or "timed out" in s:
        return "⚠️ Request timed out — please try again."
    if "does not support tools" in s or "status code: 400" in s:
        return f"⚠️ {get_current_model()} does not support tool calling — switch to a compatible model in Settings → Models."
    # Fallback — expose the raw error so nothing is silently swallowed
    return f"⚠️ API error: {exc_str}"


def _notify_api_error(friendly_msg: str) -> None:
    """Fire a persistent desktop notification for an API error."""
    try:
        from notifications import notify
        notify("Thoth – API Error", friendly_msg, sound="error", icon="⚠️",
               toast_type="negative")
    except Exception:
        pass


# ── Pre-model hook: trim messages to fit context window ──────────────────────
def _keep_browser_snapshots() -> int:
    """How many recent browser snapshots to keep in full (rest become stubs)."""
    return min(8, max(2, get_context_size() // 40_000))
# Extra tokens to account for content injected by _pre_model_trim that is NOT
# stored in the checkpoint: skills prompt, date/time line, auto-recalled
# memories, per-message framing tokens.
_INJECTION_OVERHEAD_TOKENS = 800

import json as _json
import tiktoken as _tiktoken

# Lazily-initialised tiktoken encoder (cl100k_base works well as a universal
# approximation — it slightly over-counts for Llama/Qwen which is *safer*).
_tiktoken_enc: _tiktoken.Encoding | None = None


def _get_encoder() -> _tiktoken.Encoding:
    global _tiktoken_enc
    if _tiktoken_enc is None:
        _tiktoken_enc = _tiktoken.get_encoding("cl100k_base")
    return _tiktoken_enc


def _count_tokens(text: str) -> int:
    """Count tokens using tiktoken (cl100k_base)."""
    if not text:
        return 0
    return len(_get_encoder().encode(text))


def _message_tokens(m) -> int:
    """Return the token count for a single message including content,
    tool_calls payloads, and per-message framing overhead (~4 tokens)."""
    parts: list[str] = []
    content = _content_to_str(getattr(m, "content", ""))
    if content:
        parts.append(content)
    tool_calls = getattr(m, "tool_calls", None)
    if tool_calls:
        for tc in tool_calls:
            parts.append(tc.get("name", ""))
            args = tc.get("args", {})
            if isinstance(args, str):
                parts.append(args)
            elif isinstance(args, dict):
                parts.append(_json.dumps(args, separators=(",", ":"), default=str))
    tokens = _count_tokens("\n".join(parts)) if parts else 0
    return tokens + 4  # role markers / framing overhead per message


def _count_message_list_tokens(messages: list) -> int:
    """Token counter compatible with LangChain's trim_messages."""
    return sum(_message_tokens(m) for m in messages)


def _pre_model_trim(state: dict) -> dict:
    """Trim conversation history to ~70% of the context window before each
    LLM call, and inject the current date/time so it is always accurate.

    Uses ``llm_input_messages`` so the full history stays intact in the
    checkpointer — only the LLM sees the trimmed version."""
    max_tokens = int(get_context_size() * 0.85)

    messages = list(state["messages"])

    # ── Compress stale browser snapshots ─────────────────────────────
    # Each browser tool result can be ~25 K chars.  A multi-step browsing
    # session (6–10 actions) easily fills 150 K+ chars, overflowing even
    # a 64 K-token context window.  We keep the last N snapshots in full
    # and replace older ones with a compact stub (URL + title + action)
    # so the model still knows *what it did* but without the full DOM.
    # The checkpoint is NOT modified — full snapshots remain for the UI.
    _BROWSER_PREFIX = "browser_"
    browser_indices = [
        i for i, m in enumerate(messages)
        if m.type == "tool"
        and (getattr(m, "name", "") or "").startswith(_BROWSER_PREFIX)
    ]
    _n_keep = _keep_browser_snapshots()
    if len(browser_indices) > _n_keep:
        for i in browser_indices[:-_n_keep]:
            m = messages[i]
            content = _content_to_str(m.content)
            # Extract URL and Title from the snapshot header lines
            url = ""
            title = ""
            for line in content.split("\n"):
                if line.startswith("URL: ") and not url:
                    url = line[5:].strip()
                elif line.startswith("Title: ") and not title:
                    title = line[7:].strip()
                if url and title:
                    break
            action = (m.name or "browser").replace("browser_", "", 1)
            stub = (
                f"[Prior browser {action} — "
                f"URL: {url or '(unknown)'}, "
                f"Title: {title or '(none)'}. "
                f"Full snapshot omitted to save context.]"
            )
            messages[i] = ToolMessage(
                content=stub,
                name=m.name,
                tool_call_id=m.tool_call_id,
            )

    # ── Proportionally shrink oversized ToolMessages ─────────────────
    # Without this, trim_messages (strategy="last") may drop ALL context
    # when a single huge ToolMessage — or the sum of several — exceeds
    # the token budget.  We leave ~35 % for system prompt, human/AI
    # messages, and generation headroom.  Budget is in chars (~3 chars/tok)
    # since the truncation operates on string slicing.
    tool_budget_chars = int(max_tokens * 0.65) * 3

    tool_indices = [
        i for i, m in enumerate(messages)
        if m.type == "tool" and len(_content_to_str(getattr(m, "content", ""))) > 0
    ]
    if tool_indices:
        total_tool_chars = sum(
            len(_content_to_str(messages[i].content)) for i in tool_indices
        )
        if total_tool_chars > tool_budget_chars:
            for i in tool_indices:
                m = messages[i]
                content = _content_to_str(m.content)
                # Each tool gets a share proportional to its original size
                share = len(content) / total_tool_chars
                cap = max(2_000, int(tool_budget_chars * share))
                if len(content) > cap:
                    messages[i] = ToolMessage(
                        content=(
                            content[:cap]
                            + f"\n\n[Truncated to fit context – first "
                              f"{cap:,} of {len(content):,} chars shown]"
                        ),
                        name=m.name,
                        tool_call_id=m.tool_call_id,
                    )

    # ── Apply cached context summary (if available) ──────────────────
    # If a summary was produced by _do_summarize, replace the older
    # messages with a single SystemMessage so the LLM sees a compact
    # version.  The full history remains in the checkpoint.
    _thread_id = _current_thread_id_var.get() or None
    if _thread_id and _thread_id in _summary_cache:
        from langchain_core.messages import SystemMessage as _SM
        cached = _summary_cache[_thread_id]
        _split = cached["msg_count"]
        if 0 < _split < len(messages):
            # Keep the system prompt (position 0) if present
            _sys = [messages[0]] if messages and messages[0].type == "system" else []
            _summary_msg = _SM(
                content=(
                    "[Conversation Summary — the following condenses earlier "
                    "messages that are no longer shown in full]\n"
                    + cached["summary"]
                    + "\n[End of summary — recent messages follow]"
                )
            )
            messages = _sys + [_summary_msg] + messages[_split:]

    trimmed = trim_messages(
        messages,
        max_tokens=max_tokens,
        token_counter=_count_message_list_tokens,
        strategy="last",
        start_on="human",
        include_system=True,
        allow_partial=False,
    )

    # ── Repair tool_call / ToolMessage ordering broken by trimming ────
    # OpenAI requires that an AIMessage with tool_calls is IMMEDIATELY
    # followed by ToolMessages for each tool_call_id (no intervening
    # human/ai messages).  trim_messages or checkpoint corruption can
    # break this.  Fix: for each AIMessage with tool_calls, check that
    # the immediately-following messages (while type=="tool") cover all
    # needed IDs.  If not, inject stubs right after the AIMessage and
    # remove any displaced ToolMessages found later.
    _stubs_needed: dict[int, list[dict]] = {}   # msg_index → [tool_call dicts]
    _stubbed_ids: set[str] = set()

    for i, m in enumerate(trimmed):
        tc_list = getattr(m, "tool_calls", [])
        if not tc_list:
            continue
        needed = {tc["id"]: tc for tc in tc_list if tc.get("id")}
        # Check immediately following tool messages
        j = i + 1
        while j < len(trimmed) and trimmed[j].type == "tool":
            needed.pop(getattr(trimmed[j], "tool_call_id", None), None)
            j += 1
        if needed:
            _stubs_needed[i] = list(needed.values())
            _stubbed_ids.update(needed.keys())

    if _stubs_needed:
        logger.debug("_pre_model_trim: fixing %d displaced tool_call(s)",
                      len(_stubbed_ids))
        _patched: list = []
        for i, m in enumerate(trimmed):
            # Skip displaced ToolMessages that we're replacing with stubs
            if m.type == "tool" and getattr(m, "tool_call_id", None) in _stubbed_ids:
                continue
            _patched.append(m)
            if i in _stubs_needed:
                for tc in _stubs_needed[i]:
                    _patched.append(ToolMessage(
                        content="[Result not available — earlier context was trimmed]",
                        name=tc.get("name", "unknown"),
                        tool_call_id=tc["id"],
                    ))
        trimmed = _patched

    # Inject current date & time right after the system message so the
    # model always has an up-to-date reference.  This runs on every LLM
    # call, so even after days of uptime the date stays correct.
    from langchain_core.messages import SystemMessage
    now = _datetime.now()
    time_msg = SystemMessage(
        content=(
            f"Current date and time: {now.strftime('%A, %B %d, %Y at %I:%M %p')}."
        )
    )
    # Insert after the first system message (the main prompt)
    insert_idx = 1  # default: after position 0
    for i, m in enumerate(trimmed):
        if isinstance(m, SystemMessage):
            insert_idx = i + 1
            break
    trimmed.insert(insert_idx, time_msg)

    # ── Inject background-mode override when running as a BG task ────
    if is_background_workflow():
        from prompts import AGENT_BG_OVERRIDE
        bg_msg = SystemMessage(content=AGENT_BG_OVERRIDE)
        trimmed.insert(insert_idx + 1, bg_msg)

    # ── Inject enabled skill instructions ────────────────────────────
    # Skills are user-configured workflows (SKILL.md files) whose
    # instructions are appended as an extra SystemMessage right after the
    # date/time message.  The prompt text is built from an in-memory
    # cache, so this adds zero I/O latency.
    try:
        from skills import get_skills_prompt
        from threads import get_thread_skills_override

        _thread_id = _current_thread_id_var.get() or None
        skills_override = None
        if _thread_id:
            skills_override = get_thread_skills_override(_thread_id)

        skills_text = get_skills_prompt(skills_override)
        if skills_text:
            skills_msg = SystemMessage(content=skills_text)
            # Insert right after time_msg (which is at insert_idx)
            trimmed.insert(insert_idx + 1, skills_msg)
    except Exception as exc:
        logger.debug("Skill injection skipped (non-fatal): %s", exc)

    # Plugin skills — appended after built-in skills
    try:
        from plugins import registry as _plugin_reg
        plugin_skills_text = _plugin_reg.get_skills_prompt()
        if plugin_skills_text:
            plugin_skills_msg = SystemMessage(content=plugin_skills_text)
            # Insert after the skills msg (or after time_msg if no skills)
            _ins_idx = insert_idx + (2 if skills_text else 1)
            trimmed.insert(_ins_idx, plugin_skills_msg)
    except Exception as exc:
        logger.debug("Plugin skill injection skipped: %s", exc)

    # ── Auto-recall: inject relevant memories before the last user msg ───
    # Embed the latest human message and pull the top-5 most relevant
    # memories from the FAISS index, then expand 1 hop in the knowledge
    # graph to include connected entities.  This ensures the model always
    # has rich personal context without needing to call search_memory.
    #
    if True:  # Always recall — memories enrich every conversation
      try:
        # Gather last 2-3 user messages for richer recall context
        human_texts = []
        last_human_idx = None
        for i in range(len(trimmed) - 1, -1, -1):
            if trimmed[i].type == "human":
                if last_human_idx is None:
                    last_human_idx = i
                content = trimmed[i].content
                if isinstance(content, str) and content.strip():
                    human_texts.append(content.strip())
                if len(human_texts) >= 3:
                    break

        if human_texts and last_human_idx is not None:
            from knowledge_graph import graph_enhanced_recall, count_entities

            if count_entities() > 0:
                # Build query: latest message first (most important), then
                # older messages as context.  Truncation drops older text,
                # preserving the user's most recent intent.
                query = human_texts[0]  # latest (collected first via reverse scan)
                for older in human_texts[1:]:
                    if len(query) + len(older) + 1 > 2000:
                        break
                    query = query + " " + older
                query = query[:2000]
                memories = graph_enhanced_recall(query, top_k=8, threshold=0.35, hops=1)
                if memories:
                    lines = []
                    for m in memories:
                        # Use legacy column names if available, fall back to graph names
                        category = m.get("category", m.get("entity_type", ""))
                        content = m.get("content", m.get("description", ""))
                        via = m.get("via", "semantic")
                        line = f"- [id={m['id']}] [{category}] {m['subject']}: {content}"
                        if m.get("tags"):
                            line += f" (tags: {m['tags']})"
                        if via == "graph" and m.get("relations"):
                            rels = m["relations"]
                            rel_strs = [f"{r['from']} → {r['type']} → {r['to']}" for r in rels]
                            line += f" (connected via: {'; '.join(rel_strs)})"
                        lines.append(line)
                    recall_msg = SystemMessage(
                        content=(
                            "You KNOW the following facts about this user "
                            "(from your long-term memory and knowledge graph):\n"
                            + "\n".join(lines)
                            + "\n\nTreat these as things you already know. "
                            "Use them to answer the user's question directly — "
                            "do NOT say you don't know or search for this info. "
                            "Do not mention that these were recalled from memory. "
                            "If you need to update or delete one of these, use its ID. "
                            "If you notice related entities, you can use explore_connections "
                            "to see the full relationship graph."
                        )
                    )
                    trimmed.insert(last_human_idx, recall_msg)
      except Exception as exc:
        logger.debug("Auto-recall failed (non-fatal): %s", exc)

    # ── Wind-down warning near recursion limit ───────────────────────
    # Count steps (ai + tool messages) since the last human message in
    # the ORIGINAL state — this approximates how many LangGraph node
    # executions have occurred in the current invoke/stream call.
    # At 75% of the limit, inject a system message asking the model to
    # wrap up.  This gives the model a chance to produce a final answer
    # instead of hitting the hard wall and crashing.
    try:
        _orig_msgs = state["messages"]
        _last_human = -1
        for _i in range(len(_orig_msgs) - 1, -1, -1):
            if _orig_msgs[_i].type == "human":
                _last_human = _i
                break
        if _last_human >= 0:
            _steps = sum(1 for _m in _orig_msgs[_last_human + 1:]
                         if _m.type in ("ai", "tool"))
            # Use the task limit when running in a background workflow,
            # chat limit otherwise.  is_background_workflow() is the
            # public API for checking the background flag.
            try:
                _is_bg = is_background_workflow()
            except Exception:
                _is_bg = False
            _limit = RECURSION_LIMIT_TASK if _is_bg else RECURSION_LIMIT_CHAT
            _threshold = int(_limit * 0.75)
            if _steps >= _threshold:
                from langchain_core.messages import SystemMessage as _WDMsg
                _wind_down = _WDMsg(
                    content=(
                        "[IMPORTANT: You are approaching the tool call limit "
                        f"({_steps} of {_limit} steps used). "
                        "Wrap up your current task NOW and provide a final "
                        "answer with what you have so far. Do NOT start new "
                        "tool calls unless absolutely critical.]"
                    )
                )
                trimmed.append(_wind_down)
    except Exception:
        pass  # Non-fatal — don't break the agent if this fails

    return {"llm_input_messages": trimmed}

# Cache compiled agent graphs keyed by frozenset of enabled tool names
_agent_cache: dict[frozenset[str], object] = {}

# Thread-local storage for misc flags; background flag uses ContextVar
# for proper propagation to LangGraph executor threads.
import threading as _threading
import contextvars as _contextvars
_tlocal = _threading.local()

# ContextVar for background workflow flag — MUST be ContextVar (not
# threading.local) because LangGraph runs tools in executor threads
# that inherit ContextVars but NOT threading.local storage.
_background_workflow_var: _contextvars.ContextVar[bool] = _contextvars.ContextVar(
    "background_workflow", default=False
)

# ContextVar for current_thread_id — unlike threading.local, this
# propagates to sync executor threads used by LangGraph for tools.
_current_thread_id_var: _contextvars.ContextVar[str] = _contextvars.ContextVar(
    "current_thread_id", default=""
)

# ContextVar for model override — propagates to tool executor threads so
# the contextual compressor uses the same model as the agent graph.
_model_override_var: _contextvars.ContextVar[str] = _contextvars.ContextVar(
    "model_override", default=""
)

# ContextVar for task safety mode — propagates to tool executor threads
# so self-gating tools (shell, gmail, etc.) can enforce per-task safety.
# Values: "block" | "approve" | "allow_all" | "" (not in a task)
_safety_mode_var: _contextvars.ContextVar[str] = _contextvars.ContextVar(
    "safety_mode", default=""
)


def get_safety_mode() -> str:
    """Return the active safety mode for the current execution context.

    Returns ``""`` when not running inside a background task."""
    return _safety_mode_var.get()


def is_background_workflow() -> bool:
    """Return True if code is running inside a background workflow.

    Used by self-gating tools (e.g. shell, gmail, browser) to block or
    gate destructive operations at runtime.  Uses ContextVar so the flag
    propagates to LangGraph executor threads."""
    return _background_workflow_var.get()

# ── Context summarization ────────────────────────────────────────────────────
_SUMMARY_THRESHOLD = 0.75   # trigger summarization at 75 % of context window
_PROTECTED_TURNS = 5         # keep the last N human messages (+ their replies) intact
_summary_cache: dict[str, dict] = {}  # thread_id → {"summary": str, "msg_count": int}

def _should_summarize(agent, config: dict, user_input: str) -> bool:
    """Return True if the *effective* context (accounting for any cached
    summary) plus the new user input would exceed the summarization
    threshold and there are enough messages to make summarization
    worthwhile.
    """
    max_tokens = get_context_size()
    threshold = int(max_tokens * _SUMMARY_THRESHOLD)
    try:
        state = agent.get_state(config)
        if not state or not state.values:
            return False
        msgs = state.values.get("messages", [])
        if not msgs:
            return False

        # Need at least PROTECTED_TURNS + 1 human messages to have
        # something to summarize
        human_count = sum(1 for m in msgs if m.type == "human")
        if human_count <= _PROTECTED_TURNS:
            return False

        # Compute *effective* size — if a summary cache exists, use
        # summary size + messages-after-split instead of the full raw
        # checkpoint.  This prevents re-triggering every turn after the
        # first summarization.
        thread_id = (config.get("configurable") or {}).get("thread_id", "")
        cached = _summary_cache.get(thread_id) if thread_id else None

        if cached and 0 < cached["msg_count"] < len(msgs):
            old_split = cached["msg_count"]
            # Effective = system prompt + summary text + messages after split
            sys_tokens = _message_tokens(msgs[0]) if msgs[0].type == "system" else 0
            summary_tokens = _count_tokens(cached["summary"]) + 30  # framing
            recent_tokens = sum(
                _message_tokens(m) for m in msgs[old_split:]
            )
            estimated_tokens = (sys_tokens + summary_tokens + recent_tokens
                                + _count_tokens(user_input)
                                + _INJECTION_OVERHEAD_TOKENS)
            if estimated_tokens <= threshold:
                return False

            # Over threshold — but only re-summarize if the gap between
            # the old split and the new split is substantial enough to
            # justify another LLM call.  Otherwise the protected window
            # itself is large (e.g. huge tool results) and re-summarizing
            # won't materially help.
            human_indices = [i for i, m in enumerate(msgs) if m.type == "human"]
            new_split = human_indices[-_PROTECTED_TURNS] if len(human_indices) > _PROTECTED_TURNS else old_split
            gap_tokens = sum(
                _message_tokens(m) for m in msgs[old_split:new_split]
            )
            _MIN_GAP_TOKENS = 600  # don't waste an LLM call for trivial gaps
            return gap_tokens >= _MIN_GAP_TOKENS
        else:
            estimated_tokens = sum(_message_tokens(m) for m in msgs)

        estimated_tokens += _count_tokens(user_input) + _INJECTION_OVERHEAD_TOKENS
        return estimated_tokens > threshold
    except Exception:
        logger.debug("_should_summarize check failed", exc_info=True)
        return False


def _do_summarize(agent, config: dict, model_override: str | None = None) -> None:
    """Summarize older messages and cache the result for the thread.

    The summary replaces the older portion of messages inside
    ``_pre_model_trim`` — the checkpoint is NOT modified, so the full
    conversation is always available in the UI and in the raw state.
    """
    thread_id = (config.get("configurable") or {}).get("thread_id", "")
    try:
        state = agent.get_state(config)
        if not state or not state.values:
            return
        msgs = state.values.get("messages", [])
        if not msgs:
            return

        # Find split point — protect the last N human messages
        human_indices = [i for i, m in enumerate(msgs) if m.type == "human"]
        if len(human_indices) <= _PROTECTED_TURNS:
            return
        split_idx = human_indices[-_PROTECTED_TURNS]

        # Collect messages to summarize.
        # On first summarization: all messages from start to split_idx.
        # On rolling re-summarization: only the GAP (old_split → new split)
        # since everything before old_split is already in the cached summary.
        first_content = 1 if msgs and msgs[0].type == "system" else 0
        existing_summary = _summary_cache.get(thread_id, {}).get("summary", "")
        old_split = _summary_cache.get(thread_id, {}).get("msg_count", 0)

        if existing_summary and 0 < old_split < split_idx:
            # Rolling: only feed the gap (already-summarized portion is in
            # existing_summary, not re-sent as raw messages).
            old_msgs = msgs[old_split:split_idx]
        else:
            # First time: everything from after system prompt to split.
            old_msgs = msgs[first_content:split_idx]

        if not old_msgs:
            return

        # Build a text representation for the summarizer
        parts: list[str] = []
        if existing_summary:
            parts.append(f"[Previous summary of even earlier messages]:\n{existing_summary}\n")

        for m in old_msgs:
            role = m.type.upper()
            content = _content_to_str(getattr(m, "content", ""))
            if not content:
                continue
            # Cap individual messages so the summarizer prompt stays manageable
            if len(content) > 3000:
                content = content[:3000] + " …[truncated]"
            # Skip tool messages verbatim — just note the tool name + short excerpt
            if m.type == "tool":
                name = getattr(m, "name", "tool")
                content = f"[Tool result from {name}]: {content[:600]}"
            parts.append(f"{role}: {content}")

        conversation_text = "\n".join(parts)

        # Call the LLM to produce a summary — use override model if set
        if model_override and model_override != get_current_model() and (is_model_local(model_override) or is_cloud_model(model_override)):
            llm = get_llm_for(model_override)
        else:
            llm = get_llm()
        summary_response = llm.invoke([
            {"role": "system", "content": SUMMARIZE_PROMPT},
            {"role": "human", "content": conversation_text},
        ])

        summary_text = _content_to_str(summary_response.content).strip()
        # Strip <think>…</think> blocks from thinking / reasoning models
        summary_text = _re.sub(r"<think>.*?</think>", "", summary_text, flags=_re.DOTALL)
        summary_text = _re.sub(r"</?think>", "", summary_text).strip()

        if summary_text:
            _summary_cache[thread_id] = {
                "summary": summary_text,
                "msg_count": split_idx,
            }
            logger.info(
                "Context summarized for thread %s — %d messages condensed "
                "(%d chars → %d chars)",
                thread_id, split_idx - first_content,
                len(conversation_text), len(summary_text),
            )
    except Exception:
        logger.warning("Context summarization failed (non-fatal)", exc_info=True)


def clear_summary_cache(thread_id: str | None = None) -> None:
    """Clear cached summaries — for a specific thread, or all threads."""
    if thread_id:
        _summary_cache.pop(thread_id, None)
    else:
        _summary_cache.clear()


# Human-readable labels for destructive tool operations
_DESTRUCTIVE_LABELS: dict[str, str] = {
    "workspace_file_delete": "Delete file",
    "workspace_move_file": "Move / rename file",
    "delete_calendar_event": "Delete calendar event",
    "move_calendar_event": "Move calendar event",
    "send_gmail_message": "Send email",
    "delete_memory": "Delete memory",
    "tracker_delete": "Delete tracker / entry",
    "task_delete": "Delete task",
}


def _enrich_description(tool_name: str, label: str, args_str: str, kwargs: dict) -> str:
    """Build a human-friendly description for the interrupt dialog."""
    if tool_name == "task_delete":
        try:
            from tasks import get_task
            tid = kwargs.get("task_id", "")
            task = get_task(tid) if tid else None
            if task:
                return f"{label}: {task['icon']} {task['name']}"
        except Exception:
            pass
    return f"{label}: {args_str}"


def _wrap_with_interrupt_gate(tool) -> None:
    """Mutate a LangChain tool in-place so that calling it triggers a
    LangGraph ``interrupt()`` before the real function runs.  The graph
    pauses, the UI shows a confirmation prompt, and the tool only executes
    if the user approves."""
    label = _DESTRUCTIVE_LABELS.get(tool.name, tool.name)

    if hasattr(tool, "func") and tool.func is not None:
        _orig = tool.func

        def _gated(*args, _fn=_orig, _label=label, _tname=tool.name, **kwargs):
            args_str = ", ".join(
                f"{k}={v!r}" for k, v in kwargs.items()
            )
            if args:
                args_str = repr(args[0]) if len(args) == 1 else repr(args)
                if kwargs:
                    args_str += ", " + ", ".join(f"{k}={v!r}" for k, v in kwargs.items())
            # In background workflows with block mode, refuse outright.
            # approve mode: fall through to interrupt() so the pipeline
            # can pause and let the user decide.
            if _background_workflow_var.get() and _safety_mode_var.get() != "approve":
                return (f"⚠️ BLOCKED: '{_label}' requires user confirmation "
                        "and cannot run in a background workflow. "
                        "Do NOT retry this tool. Inform the user that this "
                        "action was skipped and move on.")
            desc = _enrich_description(_tname, _label, args_str, kwargs)
            approval = interrupt({
                "tool": _tname,
                "label": _label,
                "description": desc,
                "args": kwargs or (args[0] if args else {}),
            })
            if not approval:
                return "Action cancelled by user."
            return _fn(*args, **kwargs)

        tool.func = _gated
    else:
        _orig = tool._run

        def _gated_run(*args, _fn=_orig, _label=label, _tname=tool.name, **kwargs):
            args_str = ", ".join(f"{k}={v!r}" for k, v in kwargs.items())
            if _background_workflow_var.get() and _safety_mode_var.get() != "approve":
                return (f"⚠️ BLOCKED: '{_label}' requires user confirmation "
                        "and cannot run in a background workflow. "
                        "Do NOT retry this tool. Inform the user that this "
                        "action was skipped and move on.")
            desc = _enrich_description(_tname, _label, args_str, kwargs)
            approval = interrupt({
                "tool": _tname,
                "label": _label,
                "description": desc,
                "args": kwargs or (args[0] if args else {}),
            })
            if not approval:
                return "Action cancelled by user."
            return _fn(*args, **kwargs)

        tool._run = _gated_run


def clear_agent_cache():
    """Clear the cached agent graphs so tools are rebuilt on next call."""
    _agent_cache.clear()
    _TOOL_DISPLAY_NAMES.clear()


def get_token_usage(config: dict | None = None, model_override: str | None = None) -> tuple[int, int]:
    """Return ``(used_tokens, max_tokens)`` for the current thread.

    Runs the same ``trim_messages`` logic as ``_pre_model_trim`` so the
    counter reflects what the LLM *actually* sees, not the full history.
    Returns ``(0, max_tokens)`` when there is no active thread.

    If *model_override* is given, uses that model's context cap instead
    of the global default.
    """
    max_tokens = get_context_size(model_override)
    if config is None:
        return 0, max_tokens
    try:
        agent = get_agent_graph()
        state = agent.get_state(config)
        if not state or not state.values:
            return 0, max_tokens
        msgs = state.values.get("messages", [])
        if not msgs:
            return 0, max_tokens

        # Account for cached summary — mirrors _pre_model_trim logic
        thread_id = (config.get("configurable") or {}).get("thread_id", "")
        if thread_id and thread_id in _summary_cache:
            cached = _summary_cache[thread_id]
            split = cached["msg_count"]
            if 0 < split < len(msgs):
                sys_msg = [msgs[0]] if msgs and msgs[0].type == "system" else []
                summary_tokens = _count_tokens(cached["summary"]) + 30
                recent_tokens = sum(
                    _message_tokens(m) for m in msgs[split:]
                )
                used = summary_tokens + recent_tokens + _INJECTION_OVERHEAD_TOKENS
                if sys_msg:
                    used += _message_tokens(sys_msg[0])
                return used, max_tokens

        # Mirror _pre_model_trim: trim, then count what remains
        budget = int(max_tokens * 0.85)
        trimmed = trim_messages(
            msgs,
            max_tokens=budget,
            token_counter=_count_message_list_tokens,
            strategy="last",
            start_on="human",
            include_system=True,
            allow_partial=False,
        )
        used = _count_message_list_tokens(trimmed) + _INJECTION_OVERHEAD_TOKENS
        return used, max_tokens
    except Exception:
        logger.debug("Token usage estimation failed", exc_info=True)
        return 0, max_tokens


def get_agent_graph(enabled_tool_names: list[str] | None = None,
                    model_override: str | None = None):
    """Build (or return cached) a ReAct agent graph for the given set of
    enabled tools.  The agent is rebuilt only when the tool set changes."""
    if enabled_tool_names is None:
        enabled_tool_names = [t.name for t in tool_registry.get_enabled_tools()]

    # Resolve the model to use
    if model_override and model_override != get_current_model():
        if is_model_local(model_override) or is_cloud_model(model_override):
            llm = get_llm_for(model_override)
            model_label = model_override
        else:
            logger.warning("Model override '%s' not available — falling back to default '%s'",
                           model_override, get_current_model())
            llm = get_llm()
            model_label = get_current_model()
    else:
        llm = get_llm()
        model_label = get_current_model()

    is_background = _background_workflow_var.get()
    _mode = _safety_mode_var.get() if is_background else ""
    cache_key = frozenset(enabled_tool_names) | frozenset({f"ctx:{get_context_size()}", f"model:{model_label}", f"bg:{is_background}", f"safety:{_mode}"})

    if cache_key not in _agent_cache:
        # Collect LangChain tool wrappers for enabled tools
        lc_tools = []
        destructive_names: set[str] = set()
        for name in enabled_tool_names:
            tool_obj = tool_registry.get_tool(name)
            if tool_obj is not None:
                lc_tools.extend(tool_obj.as_langchain_tools())
                destructive_names.update(tool_obj.destructive_tool_names)

        # Append tools from enabled plugins (totally separate registry)
        try:
            from plugins import registry as plugin_registry_mod
            lc_tools.extend(plugin_registry_mod.get_langchain_tools())
            destructive_names.update(plugin_registry_mod.get_destructive_names())
        except Exception as exc:
            logger.debug("Plugin tool injection skipped: %s", exc)

        if is_background:
            # Background tool gating — three modes:
            #  block:     strip all destructive tools (LLM can't call them)
            #  approve:   keep destructive tools but wrap with interrupt()
            #             so the pipeline pauses for user approval
            #  allow_all: keep everything ungated
            # run_command is NOT in destructive_names (shell self-gates
            # at runtime via classify_command), so it is always kept.
            if _mode == "block":
                lc_tools = [t for t in lc_tools
                            if t.name not in destructive_names]
            elif _mode == "approve":
                for t in lc_tools:
                    if t.name in destructive_names:
                        _wrap_with_interrupt_gate(t)
            # else: allow_all — keep everything, no gates
        else:
            # Interactive sessions: gate destructive tools with interrupt() —
            # the graph will pause, yield an "interrupt" event, and wait for
            # user approval before actually executing the tool.
            for t in lc_tools:
                if t.name in destructive_names:
                    _wrap_with_interrupt_gate(t)

        # Wrap every tool so exceptions are returned to the LLM as error
        # messages instead of crashing the stream.  LangChain's built-in
        # handle_tool_error only catches ToolException; external toolkit
        # tools (e.g. Calendar) may raise plain Exception.
        # NOTE: GraphInterrupt must NOT be caught — it's used by LangGraph
        # to implement the interrupt/resume flow.
        from langgraph.errors import GraphInterrupt

        for t in lc_tools:
            if hasattr(t, "func") and t.func is not None:
                # StructuredTool / Tool created via from_function
                _orig_func = t.func
                def _safe_func(*args, _fn=_orig_func, **kwargs):
                    try:
                        return _fn(*args, **kwargs)
                    except GraphInterrupt:
                        raise  # Must propagate for interrupt/resume flow
                    except Exception as exc:
                        logger.error("Tool %s raised an error: %s", _fn.__name__ if hasattr(_fn, '__name__') else '?', exc, exc_info=True)
                        return f"Tool error: {exc}"
                t.func = _safe_func
            else:
                # Toolkit tools that override _run directly
                _orig_run = t._run
                def _safe_run(*args, _fn=_orig_run, **kwargs):
                    try:
                        return _fn(*args, **kwargs)
                    except GraphInterrupt:
                        raise
                    except Exception as exc:
                        logger.error("Tool _run raised an error: %s", exc, exc_info=True)
                        return f"Tool error: {exc}"
                t._run = _safe_run

        if not lc_tools:
            # Agent without tools is pointless — fall back to plain LLM
            lc_tools = []

        agent = create_react_agent(
            model=llm,
            tools=lc_tools,
            prompt=AGENT_SYSTEM_PROMPT,
            pre_model_hook=_pre_model_trim,
            checkpointer=checkpointer,
            name="thoth_agent",
        )
        _agent_cache[cache_key] = agent

    return _agent_cache[cache_key]


def invoke_agent(user_input: str, enabled_tool_names: list[str], config: dict,
                 *, stop_event: threading.Event | None = None) -> str | dict:
    """Invoke the ReAct agent and return the final answer text.

    If *stop_event* is provided and becomes set, the function raises
    ``TaskStoppedError`` after the current node completes.  This gives
    ~5-20 cancellation points per agent step (LLM call, each tool call)
    without requiring full token-level streaming.

    Returns
    -------
    str
        The agent's final text response.
    dict
        If the graph was paused by an ``interrupt()`` call (e.g. shell
        tool approval gate), returns ``{"type": "interrupt", "interrupts": [...]}``.
    """
    _model_ov = (config.get("configurable") or {}).get("model_override")
    agent = get_agent_graph(enabled_tool_names, model_override=_model_ov)

    # Set thread-local so _pre_model_trim can find the summary cache
    _current_thread_id_var.set(
        (config.get("configurable") or {}).get("thread_id", "")
    )
    _model_override_var.set(_model_ov or "")
    set_active_model_override(_model_ov or "")

    # Summarize if context is above threshold
    if stop_event and stop_event.is_set():
        raise TaskStoppedError("Task stopped before execution")
    if _should_summarize(agent, config, user_input):
        _do_summarize(agent, config, model_override=_model_ov)
    if stop_event and stop_event.is_set():
        raise TaskStoppedError("Task stopped after summarization")

    # Use node-level streaming so we can check stop_event between nodes
    if stop_event is not None:
        import hashlib as _ia_hashlib
        _ia_recent_sigs: list[str] = []
        _ia_loop = False
        try:
            for _event in agent.stream(
                {"messages": [("human", user_input)]},
                config=config,
                stream_mode="updates",
            ):
                if stop_event.is_set():
                    raise TaskStoppedError("Task stopped during execution")
                # Loop detection — inspect tool calls in update events
                if isinstance(_event, dict):
                    for _node, _ndata in _event.items():
                        if not isinstance(_ndata, dict):
                            continue
                        for _m in _ndata.get("messages", []):
                            for _tc in getattr(_m, "tool_calls", []):
                                _a = _tc.get("args", {})
                                _sig = _tc["name"] + ":" + _ia_hashlib.md5(
                                    _json.dumps(_a, sort_keys=True, default=str).encode()
                                ).hexdigest()
                                if _ia_recent_sigs and _ia_recent_sigs[-1] == _sig:
                                    _ia_recent_sigs.append(_sig)
                                else:
                                    _ia_recent_sigs.clear()
                                    _ia_recent_sigs.append(_sig)
                                if len(_ia_recent_sigs) >= 4:
                                    _ia_loop = True
                if _ia_loop:
                    break
        except TaskStoppedError:
            raise
        except Exception as exc:
            exc_str = str(exc)
            if "tool_call" in exc_str and ("do not have a corresponding" in exc_str
                                            or "did not have response" in exc_str
                                            or "must be followed by tool" in exc_str):
                logger.warning("invoke_agent: orphaned tool calls — repairing")
                repair_orphaned_tool_calls(config=config, agent_graph=agent)
                for _event in agent.stream(
                    {"messages": [("human", user_input)]},
                    config=config,
                    stream_mode="updates",
                ):
                    if stop_event.is_set():
                        raise TaskStoppedError("Task stopped during retry")
            else:
                _err_msg = _friendly_api_error(exc_str)
                logger.error("invoke_agent API error: %s", exc_str)
                _notify_api_error(_err_msg)
                return _err_msg

        # Handle loop detection in task mode
        if _ia_loop:
            logger.warning("invoke_agent: loop detected — same tool+args called 4 times consecutively")
            try:
                repair_orphaned_tool_calls(config=config, agent_graph=agent)
            except Exception:
                pass
            _loop_msg = ("⚠️ I noticed I was repeating the same action without making progress, "
                         "so I stopped to avoid wasting resources.")
            _notify_api_error(_loop_msg)
            return _loop_msg

        # Read final state from checkpoint
        state = agent.get_state(config)

        # ── Interrupt detection ──────────────────────────────────────
        # If the graph paused due to an interrupt() call (e.g. shell
        # tool approval gate), return interrupt data instead of text.
        if state and state.next:
            all_interrupts: list[dict] = []
            for task in state.tasks:
                if hasattr(task, "interrupts") and task.interrupts:
                    for intr in task.interrupts:
                        item = dict(intr.value) if isinstance(intr.value, dict) else {"description": str(intr.value)}
                        item["__interrupt_id"] = intr.id
                        all_interrupts.append(item)
            if all_interrupts:
                return {"type": "interrupt", "interrupts": all_interrupts}

        if state and state.values:
            for msg in reversed(state.values.get("messages", [])):
                if hasattr(msg, "type") and msg.type == "ai" and msg.content:
                    text = _content_to_str(msg.content)
                    if text.strip():
                        return text
        return "I wasn't able to generate a response."

    # Original path (no stop_event) — simple invoke
    result = agent.invoke(
        {"messages": [("human", user_input)]},
        config=config,
    )
    # The agent returns messages; the last AI message is the answer
    messages = result.get("messages", [])
    for msg in reversed(messages):
        if hasattr(msg, "type") and msg.type == "ai" and msg.content:
            text = _content_to_str(msg.content)
            if text.strip():
                return text
    return "I wasn't able to generate a response."


import re as _re

# Map tool func names (search_xxx) back to display names
_TOOL_DISPLAY_NAMES: dict[str, str] = {}


def _resolve_tool_display_name(func_name: str) -> str:
    """Convert tool function name to display name using the registry.
    For multi-tool entries (e.g. filesystem), map sub-tool names back
    to the parent tool's display name."""
    if not _TOOL_DISPLAY_NAMES:
        for t in tool_registry.get_all_tools():
            _TOOL_DISPLAY_NAMES[t.name] = t.display_name
            # Also map sub-tool names for tools that return multiple
            try:
                for lc_tool in t.as_langchain_tools():
                    if lc_tool.name != t.name:
                        _TOOL_DISPLAY_NAMES[lc_tool.name] = t.display_name
            except Exception:
                pass  # tool not configured yet — sub-names added on rebuild
    return _TOOL_DISPLAY_NAMES.get(func_name, func_name)


def stream_agent(user_input: str, enabled_tool_names: list[str], config: dict,
                  *, stop_event: threading.Event | None = None):
    """Stream the agent response as structured events.

    Yields tuples of ``(event_type, payload)`` where *event_type* is one of:

    * ``"tool_call"``   – payload = tool display name (str)
    * ``"tool_done"``   – payload = tool display name (str)
    * ``"thinking"``    – payload = ``None`` (model is reasoning)
    * ``"token"``       – payload = token text (str)
    * ``"interrupt"``   – payload = interrupt data dict (graph is paused)
    * ``"summarizing"`` – payload = ``None`` (condensing older context)
    * ``"done"``        – payload = full answer text (str)
    """
    _model_ov = (config.get("configurable") or {}).get("model_override")
    agent = get_agent_graph(enabled_tool_names, model_override=_model_ov)

    # Set thread-local so _pre_model_trim can find the summary cache
    _current_thread_id_var.set(
        (config.get("configurable") or {}).get("thread_id", "")
    )
    _model_override_var.set(_model_ov or "")
    set_active_model_override(_model_ov or "")

    # ── Context summarization (runs before the main agent stream) ────
    if _should_summarize(agent, config, user_input):
        yield ("summarizing", None)
        _do_summarize(agent, config, model_override=_model_ov)

    yield from _stream_graph(agent, {"messages": [("human", user_input)]}, config,
                             stop_event=stop_event)


def repair_orphaned_tool_calls(enabled_tool_names: list[str] | None = None,
                               config: dict | None = None,
                               *, agent_graph=None) -> None:
    """Patch the checkpoint so every AIMessage tool_call has a ToolMessage.

    Called after stop-generation to prevent
    ``INVALID_CHAT_HISTORY`` errors on the next query.
    """
    if config is None:
        return
    try:
        agent = agent_graph or get_agent_graph(enabled_tool_names)
        state = agent.get_state(config)
        if not state or not state.values:
            return
        msgs = state.values.get("messages", [])
        if not msgs:
            return

        # Collect IDs of existing ToolMessages
        answered = {m.tool_call_id for m in msgs if m.type == "tool"}

        # Find orphaned tool_calls in AIMessages
        patches: list[ToolMessage] = []
        for m in msgs:
            for tc in getattr(m, "tool_calls", []):
                if tc.get("id") and tc["id"] not in answered:
                    patches.append(ToolMessage(
                        content="[Cancelled by user]",
                        name=tc["name"],
                        tool_call_id=tc["id"],
                    ))

        if patches:
            logger.warning("Repairing %d orphaned tool_call(s): %s",
                           len(patches),
                           [p.tool_call_id for p in patches])
            agent.update_state(config, {"messages": patches})
            # Add a visible stop marker so the conversation reloads correctly
            agent.update_state(config, {"messages": [
                AIMessage(content="\u23f9\ufe0f *[Stopped]*")
            ]})
            logger.warning("repair_orphaned_tool_calls: checkpoint patched successfully")
        else:
            logger.debug("repair_orphaned_tool_calls: no orphaned tool_calls in %d messages", len(msgs))
    except Exception:
        logger.warning("repair_orphaned_tool_calls failed", exc_info=True)


def resume_stream_agent(enabled_tool_names: list[str], config: dict, approved: bool,
                        *, interrupt_ids: list[str] | None = None,
                        stop_event: threading.Event | None = None):
    """Resume an interrupted agent graph after user approval/denial.

    Yields the same ``(event_type, payload)`` tuples as ``stream_agent``.
    """
    _model_ov = (config.get("configurable") or {}).get("model_override")
    agent = get_agent_graph(enabled_tool_names, model_override=_model_ov)
    if interrupt_ids and len(interrupt_ids) > 1:
        resume_val = {iid: approved for iid in interrupt_ids}
    else:
        resume_val = approved
    yield from _stream_graph(agent, Command(resume=resume_val), config,
                             stop_event=stop_event)


def resume_invoke_agent(enabled_tool_names: list[str], config: dict, approved: bool,
                        *, interrupt_ids: list[str] | None = None,
                        stop_event: threading.Event | None = None) -> str | dict:
    """Resume an interrupted agent graph (non-streaming, for tasks).

    Returns the final answer text, or an interrupt dict if the graph
    pauses again (e.g. a second tool call needing approval).
    """
    _model_ov = (config.get("configurable") or {}).get("model_override")
    agent = get_agent_graph(enabled_tool_names, model_override=_model_ov)

    _current_thread_id_var.set(
        (config.get("configurable") or {}).get("thread_id", "")
    )
    _model_override_var.set(_model_ov or "")
    set_active_model_override(_model_ov or "")

    if interrupt_ids and len(interrupt_ids) > 1:
        resume_val = {iid: approved for iid in interrupt_ids}
    else:
        resume_val = approved

    try:
        for _event in agent.stream(
            Command(resume=resume_val),
            config=config,
            stream_mode="updates",
        ):
            if stop_event and stop_event.is_set():
                raise TaskStoppedError("Task stopped during resume")
    except TaskStoppedError:
        raise
    except Exception as exc:
        exc_str = str(exc)
        _err_msg = _friendly_api_error(exc_str)
        logger.error("resume_invoke_agent error: %s", exc_str)
        return _err_msg

    # Check for another interrupt (agent may call a second dangerous tool)
    state = agent.get_state(config)
    if state and state.next:
        all_interrupts: list[dict] = []
        for task in state.tasks:
            if hasattr(task, "interrupts") and task.interrupts:
                for intr in task.interrupts:
                    item = dict(intr.value) if isinstance(intr.value, dict) else {"description": str(intr.value)}
                    item["__interrupt_id"] = intr.id
                    all_interrupts.append(item)
        if all_interrupts:
            return {"type": "interrupt", "interrupts": all_interrupts}

    # Extract final answer
    if state and state.values:
        for msg in reversed(state.values.get("messages", [])):
            if hasattr(msg, "type") and msg.type == "ai" and msg.content:
                text = _content_to_str(msg.content)
                if text.strip():
                    return text
    return "I wasn't able to generate a response."


def _stream_graph(agent, input_data, config: dict,
                  *, stop_event: threading.Event | None = None):
    """Shared streaming logic for both initial invocation and resume."""
    full_answer = []
    thinking_signalled = False
    _in_think = False           # True while inside a <think>…</think> block
    _seen_tool_calls: set[str] = set()

    # Loop detection: track consecutive identical tool call signatures.
    # If the same (name, args_hash) appears 4 times in a row, the model
    # is stuck — break early instead of burning through the recursion limit.
    import hashlib as _hashlib
    _LOOP_THRESHOLD = 4
    _recent_tool_sigs: list[str] = []   # last N signatures
    _loop_detected = False

    try:
        stream_iter = agent.stream(
            input_data,
            config=config,
            stream_mode=["messages", "updates"],
        )
    except Exception as exc:
        exc_str = str(exc)
        # Auto-repair orphaned tool calls and retry once
        if "tool_call" in exc_str and ("do not have a corresponding" in exc_str
                                        or "did not have response" in exc_str
                                        or "must be followed by tool" in exc_str):
            logger.warning("Orphaned tool calls detected — repairing checkpoint")
            try:
                repair_orphaned_tool_calls(config=config, agent_graph=agent)
                stream_iter = agent.stream(
                    input_data,
                    config=config,
                    stream_mode=["messages", "updates"],
                )
            except Exception as retry_exc:
                yield ("error", str(retry_exc))
                return
        elif "does not support tools" in exc_str or "status code: 400" in exc_str:
            yield ("error", f"{get_current_model()} does not support tool calling. "
                   "Please switch to a compatible model in Settings → Models.")
            return
        else:
            yield ("error", exc_str)
            return

    try:
      for event in stream_iter:
        # ── Stop-button cancellation ─────────────────────────────────────
        if stop_event and stop_event.is_set():
            break

        mode, data = event

        # ── updates: tool call / tool result events ──────────────────────────
        if mode == "updates":
            if not isinstance(data, dict):
                continue
            for node, ndata in data.items():
                if not isinstance(ndata, dict):
                    continue
                for m in ndata.get("messages", []):
                    # Tool call initiated by the agent
                    tc_list = getattr(m, "tool_calls", [])
                    if tc_list:
                        for tc in tc_list:
                            tc_id = tc.get("id", tc["name"])
                            if tc_id not in _seen_tool_calls:
                                _seen_tool_calls.add(tc_id)
                                yield ("tool_call", _resolve_tool_display_name(tc["name"]))

                            # Loop detection: hash (name, args) as signature
                            _args = tc.get("args", {})
                            _sig = tc["name"] + ":" + _hashlib.md5(
                                _json.dumps(_args, sort_keys=True, default=str).encode()
                            ).hexdigest()
                            if _recent_tool_sigs and _recent_tool_sigs[-1] == _sig:
                                _recent_tool_sigs.append(_sig)
                            else:
                                _recent_tool_sigs.clear()
                                _recent_tool_sigs.append(_sig)
                            if len(_recent_tool_sigs) >= _LOOP_THRESHOLD:
                                _loop_detected = True

                    # Tool result returned
                    if m.type == "tool":
                        yield ("tool_done", {
                            "name": _resolve_tool_display_name(m.name),
                            "raw_name": m.name,
                            "content": getattr(m, "content", ""),
                        })

            if _loop_detected:
                break

        # ── messages: token-level streaming ──────────────────────────────────
        elif mode == "messages":
            msg, meta = data

            # Only process AI message chunks from the agent node
            # (skip tool results, human msgs, and tools-node broadcasts)
            class_name = type(msg).__name__
            if class_name != "AIMessageChunk":
                continue
            if meta.get("langgraph_node") != "agent":
                continue

            # Skip chunks that are part of a tool-call decision
            if getattr(msg, "tool_calls", []) or getattr(msg, "tool_call_chunks", []):
                continue

            content = _content_to_str(msg.content)

            # ── Reasoning via additional_kwargs (LangChain standard) ─
            # All major providers (OpenAI, Ollama/DeepSeek, Groq, XAI)
            # surface reasoning tokens in additional_kwargs["reasoning_content"].
            # Extract them BEFORE checking content so the thinking bubble
            # works even when content is empty during the reasoning phase.
            _ak = getattr(msg, "additional_kwargs", None) or {}
            _reasoning = _ak.get("reasoning_content", "")
            if _reasoning:
                if not thinking_signalled:
                    thinking_signalled = True
                yield ("thinking_token", _reasoning)

            if not content:
                # Empty content = thinking phase (signal spinner if no
                # reasoning_content was yielded above)
                if not thinking_signalled:
                    thinking_signalled = True
                    yield ("thinking", None)
                continue

            # ── Stateful <think>…</think> separation ─────────────────
            # Tags may span multiple streaming chunks, so we track
            # whether we are currently inside a think block.  Think
            # content is yielded as ("thinking_token", text) so the UI
            # can display it, then collapse when the real answer starts.
            if _in_think:
                close_idx = content.find("</think>")
                if close_idx == -1:
                    # Still inside think block — yield as thinking
                    yield ("thinking_token", content)
                    continue
                # Found closing tag — split: before=thinking, after=real
                _in_think = False
                think_part = content[:close_idx]
                if think_part:
                    yield ("thinking_token", think_part)
                content = content[close_idx + len("</think>"):]
                if not content:
                    continue

            # Handle complete <think>…</think> blocks within a chunk
            parts = _re.split(r"<think>(.*?)</think>", content, flags=_re.DOTALL)
            # parts = [before, think_content, after, think_content2, after2, …]
            real_parts = []
            for i, part in enumerate(parts):
                if not part:
                    continue
                if i % 2 == 1:
                    # Odd index = captured think content
                    yield ("thinking_token", part)
                else:
                    real_parts.append(part)
            content = "".join(real_parts)

            # Check for an unclosed <think> that continues into next chunk
            open_idx = content.find("<think>")
            if open_idx != -1:
                _in_think = True
                trailing = content[open_idx + len("<think>"):]
                if trailing:
                    yield ("thinking_token", trailing)
                content = content[:open_idx]

            # Safety: remove any orphaned tags
            content = _re.sub(r"</?think>", "", content)

            if content:
                thinking_signalled = False
                full_answer.append(content)
                yield ("token", content)
    except Exception as exc:
        exc_str = str(exc)
        # Auto-repair orphaned tool calls and retry once
        if "tool_call" in exc_str and ("do not have a corresponding" in exc_str
                                        or "did not have response" in exc_str
                                        or "must be followed by tool" in exc_str):
            logger.warning("Orphaned tool calls during iteration — repairing checkpoint")
            try:
                repair_orphaned_tool_calls(config=config, agent_graph=agent)
                retry_iter = agent.stream(
                    input_data, config=config,
                    stream_mode=["messages", "updates"],
                )
                for event in retry_iter:
                    if stop_event and stop_event.is_set():
                        break
                    mode, data = event
                    if mode == "updates":
                        if not isinstance(data, dict):
                            continue
                        for node, ndata in data.items():
                            if not isinstance(ndata, dict):
                                continue
                            for m in ndata.get("messages", []):
                                tc_list = getattr(m, "tool_calls", [])
                                if tc_list:
                                    for tc in tc_list:
                                        yield ("tool_call", _resolve_tool_display_name(tc["name"]))
                                if m.type == "tool":
                                    yield ("tool_done", {
                                        "name": _resolve_tool_display_name(m.name),
                                        "raw_name": m.name,
                                        "content": getattr(m, "content", ""),
                                    })
                    elif mode == "messages":
                        msg, meta = data
                        if type(msg).__name__ != "AIMessageChunk":
                            continue
                        if meta.get("langgraph_node") != "agent":
                            continue
                        if getattr(msg, "tool_calls", []) or getattr(msg, "tool_call_chunks", []):
                            continue
                        content = _content_to_str(msg.content)
                        if content:
                            content = _re.sub(r"<think>.*?</think>", "", content, flags=_re.DOTALL)
                            content = _re.sub(r"</?think>", "", content)
                            if content:
                                full_answer.append(content)
                                yield ("token", content)
            except Exception as retry_exc:
                _rmsg = _friendly_api_error(str(retry_exc))
                _notify_api_error(_rmsg)
                yield ("error", _rmsg)
                return
        elif "does not support tools" in exc_str or "status code: 400" in exc_str:
            _err = _friendly_api_error(exc_str)
            _notify_api_error(_err)
            yield ("error", _err)
        else:
            _err = _friendly_api_error(exc_str)
            logger.error("_stream_graph API error: %s", exc_str)
            _notify_api_error(_err)
            yield ("error", _err)
        return

    # Handle loop detection — repair orphans and yield friendly error
    if _loop_detected:
        logger.warning("Loop detected: same tool+args called %d times consecutively", _LOOP_THRESHOLD)
        try:
            repair_orphaned_tool_calls(config=config, agent_graph=agent)
        except Exception:
            pass
        _loop_msg = ("⚠️ I noticed I was repeating the same action without making progress, "
                     "so I stopped. Here's what I have so far:")
        _notify_api_error(_loop_msg)
        if full_answer:
            yield ("done", "".join(full_answer) + "\n\n" + _loop_msg)
        else:
            yield ("error", _loop_msg)
        return

    # Check if the graph paused due to an interrupt (destructive tool gate)
    state = agent.get_state(config)
    if state and state.next:
        all_interrupts: list[dict] = []
        for task in state.tasks:
            if hasattr(task, "interrupts") and task.interrupts:
                for intr in task.interrupts:
                    item = dict(intr.value) if isinstance(intr.value, dict) else {"description": str(intr.value)}
                    item["__interrupt_id"] = intr.id
                    all_interrupts.append(item)
        if all_interrupts:
            yield ("interrupt", all_interrupts)
            return

    yield ("done", "".join(full_answer))

if __name__ == "__main__":
    config = pick_or_create_thread()
    print("Type your questions below. Type 'quit' to exit, 'switch' to change threads.\n")
    while True:
        user_input = input("You: ").strip()
        if not user_input:
            continue
        if user_input.lower() == "quit":
            break
        if user_input.lower() == "switch":
            config = pick_or_create_thread()
            continue

        enabled = [t.name for t in tool_registry.get_enabled_tools()]
        answer = invoke_agent(user_input, enabled, config)
        print(f"\nAssistant: {answer}\n")

