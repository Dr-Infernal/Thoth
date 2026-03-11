"""Background memory extraction — scans past conversations for personal facts.

Runs at app startup and periodically (every ~6 hours) to catch memories
the agent missed during live conversation.  Uses the user's current LLM
model to extract personal facts, then deduplicates against existing
memories before saving.

Stores the last extraction timestamp so it only processes new/updated
threads since the previous run.
"""

from __future__ import annotations

import json
import logging
import pathlib
import os
import threading
from datetime import datetime

logger = logging.getLogger(__name__)

# ── Persistence ──────────────────────────────────────────────────────────────
_DATA_DIR = pathlib.Path(
    os.environ.get("THOTH_DATA_DIR", pathlib.Path.home() / ".thoth")
)
_DATA_DIR.mkdir(parents=True, exist_ok=True)
_STATE_FILE = _DATA_DIR / "memory_extraction_state.json"

_INTERVAL_S = 6 * 3600  # 6 hours


def _load_state() -> dict:
    if _STATE_FILE.exists():
        try:
            return json.loads(_STATE_FILE.read_text())
        except Exception:
            pass
    return {}


def _save_state(state: dict) -> None:
    _STATE_FILE.write_text(json.dumps(state, indent=2))


# ── Extraction prompt ────────────────────────────────────────────────────────

_EXTRACTION_PROMPT = """\
You are a memory extraction assistant. Read the conversation below between \
a user and an AI assistant. Extract ONLY personal facts about the user that \
are worth remembering long-term.

Look for:
- Names (user's name, family, friends, colleagues, pets)
- Relationships (spouse, partner, children, parents, boss)
- Preferences (likes, dislikes, habits, settings)
- Personal facts (job, location, hobbies, skills)
- Important dates (birthdays, anniversaries, deadlines)
- Places (home city, workplace, frequent locations)
- Projects (work projects, hobbies, goals)

Rules:
- ONLY extract facts the USER stated or implied about THEMSELVES
- Do NOT extract facts from tool results, web searches, or AI responses
- Do NOT extract transient requests ("search for X", "tell me about Y")
- Do NOT extract information the AI already knows from prior context
- Do NOT extract activity logs that are handled by the tracker tool. Skip
  any mentions of taking medication, symptoms (headaches, pain levels),
  exercise sessions, period tracking, mood logs, sleep logs, or other
  recurring tracked events. The tracker system stores these separately.
- Return a JSON array of objects with keys: category, subject, content
- category must be one of: person, preference, fact, event, place, project
- If there is NOTHING worth remembering, return an empty array: []

CONVERSATION:
{conversation}

Respond with ONLY a valid JSON array. No other text."""


# ── Core extraction logic ────────────────────────────────────────────────────

def _get_thread_messages(thread_id: str) -> list[dict]:
    """Load messages from a thread via the LangGraph checkpointer."""
    try:
        from agent import get_agent_graph
        from threads import checkpointer  # noqa: F811

        config = {"configurable": {"thread_id": thread_id}}
        agent = get_agent_graph()
        state = agent.get_state(config)
        if not state or not state.values:
            return []
        messages = state.values.get("messages", [])
        result = []
        for m in messages:
            role = "user" if m.type == "human" else ("assistant" if m.type == "ai" else None)
            content = getattr(m, "content", "") or ""
            if role and content.strip():
                result.append({"role": role, "content": content[:2000]})
        return result
    except Exception as exc:
        logger.debug("Could not load thread %s: %s", thread_id, exc)
        return []


def _format_conversation(messages: list[dict]) -> str:
    """Format messages into a readable conversation string."""
    lines = []
    for m in messages:
        prefix = "User" if m["role"] == "user" else "Assistant"
        lines.append(f"{prefix}: {m['content']}")
    return "\n".join(lines)


def _extract_from_conversation(conversation_text: str) -> list[dict]:
    """Call the LLM to extract personal facts from a conversation."""
    import re
    try:
        from models import get_current_model
        import ollama

        prompt = _EXTRACTION_PROMPT.format(conversation=conversation_text)
        response = ollama.chat(
            model=get_current_model(),
            messages=[{"role": "user", "content": prompt}],
            options={"temperature": 0.1, "num_ctx": 4096},
        )
        raw = response["message"]["content"].strip()

        # Strip <think>...</think> blocks from reasoning models
        raw = re.sub(r"<think>.*?</think>", "", raw, flags=re.DOTALL)
        raw = re.sub(r"</?think>", "", raw).strip()

        # Try to find JSON array in the response
        # Look for [...] pattern
        match = re.search(r"\[.*\]", raw, re.DOTALL)
        if not match:
            return []
        data = json.loads(match.group())
        if not isinstance(data, list):
            return []
        # Validate each entry
        valid = []
        for entry in data:
            if (
                isinstance(entry, dict)
                and entry.get("category")
                and entry.get("subject")
                and entry.get("content")
            ):
                valid.append(entry)
        return valid
    except Exception as exc:
        logger.warning("Memory extraction LLM call failed: %s", exc)
        return []


def _dedup_and_save(extracted: list[dict]) -> int:
    """Save extracted memories, deduplicating against existing ones.

    If a new memory is very similar (cosine > 0.85) to an existing one,
    update the existing memory instead of creating a duplicate.
    Returns the number of new/updated memories.
    """
    from memory import save_memory, semantic_search, update_memory, VALID_CATEGORIES

    saved_count = 0
    for entry in extracted:
        category = entry["category"].lower().strip()
        if category not in VALID_CATEGORIES:
            continue
        subject = entry["subject"].strip()
        content = entry["content"].strip()
        if not subject or not content:
            continue

        # Check for duplicates using semantic similarity
        search_text = f"{category} {subject} {content}"
        try:
            existing = semantic_search(search_text, top_k=3, threshold=0.85)
        except Exception:
            existing = []

        if existing:
            # Very similar memory exists — update if the new content is longer/richer
            best = existing[0]
            if len(content) > len(best.get("content", "")):
                try:
                    update_memory(best["id"], content)
                    saved_count += 1
                    logger.info("Updated memory %s: %s", best["id"], subject)
                except Exception as exc:
                    logger.debug("Failed to update memory: %s", exc)
        else:
            # No close match — save as new
            try:
                save_memory(category, subject, content)
                saved_count += 1
                logger.info("Auto-saved memory: [%s] %s", category, subject)
            except Exception as exc:
                logger.debug("Failed to save memory: %s", exc)

    return saved_count


# ── Public API ───────────────────────────────────────────────────────────────

def run_extraction(on_status=None) -> int:
    """Scan threads updated since last extraction and extract memories.

    Parameters
    ----------
    on_status : callable, optional
        Called with status strings for UI feedback, e.g. ``on_status("Processing 3 threads…")``.

    Returns
    -------
    int
        Number of new/updated memories saved.
    """
    from threads import _list_threads

    state = _load_state()
    last_run = state.get("last_extraction", "2000-01-01T00:00:00")

    threads = _list_threads()
    if not threads:
        if on_status:
            on_status("No conversations to process")
        state["last_extraction"] = datetime.now().isoformat()
        _save_state(state)
        return 0

    # Find threads updated since last extraction
    new_threads = []
    for tid, name, created, updated in threads:
        if updated and updated > last_run:
            new_threads.append((tid, name))

    if not new_threads:
        if on_status:
            on_status("No new conversations since last extraction")
        state["last_extraction"] = datetime.now().isoformat()
        _save_state(state)
        return 0

    if on_status:
        on_status(f"Scanning {len(new_threads)} conversation(s) for memories…")

    total_saved = 0
    for tid, name in new_threads:
        messages = _get_thread_messages(tid)
        # Only process threads with user messages
        user_msgs = [m for m in messages if m["role"] == "user"]
        if not user_msgs:
            continue

        # Build conversation text (cap at ~6000 chars to fit in context)
        conv_text = _format_conversation(messages)
        if len(conv_text) > 6000:
            conv_text = conv_text[:6000] + "\n[... truncated]"

        if on_status:
            on_status(f"Extracting memories from: {name}")

        extracted = _extract_from_conversation(conv_text)
        if extracted:
            count = _dedup_and_save(extracted)
            total_saved += count
            logger.info("Thread '%s': extracted %d, saved %d", name, len(extracted), count)

    state["last_extraction"] = datetime.now().isoformat()
    _save_state(state)

    if on_status:
        if total_saved:
            on_status(f"Extracted {total_saved} new memory(s)")
        else:
            on_status("No new memories found")

    return total_saved


# ── Background timer ─────────────────────────────────────────────────────────

_timer_thread: threading.Thread | None = None
_timer_stop = threading.Event()


def start_periodic_extraction() -> None:
    """Start a daemon thread that runs extraction every 6 hours."""
    global _timer_thread
    if _timer_thread is not None and _timer_thread.is_alive():
        return

    _timer_stop.clear()

    def _loop():
        while not _timer_stop.wait(timeout=_INTERVAL_S):
            logger.info("Periodic memory extraction starting…")
            try:
                count = run_extraction()
                logger.info("Periodic extraction complete: %d memories", count)
            except Exception as exc:
                logger.warning("Periodic extraction failed: %s", exc)

    _timer_thread = threading.Thread(target=_loop, daemon=True, name="thoth-mem-extract")
    _timer_thread.start()
    logger.info("Periodic memory extraction scheduled every %d hours", _INTERVAL_S // 3600)


def stop_periodic_extraction() -> None:
    """Signal the periodic extraction thread to stop."""
    _timer_stop.set()
