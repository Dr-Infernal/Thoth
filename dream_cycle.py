"""Dream Cycle — nightly background knowledge refinement.

Runs during a configurable quiet window (default 1–5 AM local time) when
the system is idle.  Performs three safe, non-destructive operations:

1. **Duplicate merge** — entities with ≥0.93 semantic similarity AND same
   type are auto-merged.
2. **Description enrichment** — thin entities (<80 chars) that appear in
   multiple conversations get richer descriptions.
3. **Relationship inference** — entity pairs that co-occur in the same
   conversation but have no edge are evaluated for a connection.

All changes are tagged with ``source="dream_*"`` for traceability and
logged to a persistent dream journal (``~/.thoth/dream_journal.json``).

Architecture mirrors ``memory_extraction.py``: daemon thread, direct LLM
calls (no agent overhead), conservative thresholds, batch-capped.
"""

from __future__ import annotations

import json
import logging
import os
import pathlib
import re
import threading
import uuid
from datetime import datetime

logger = logging.getLogger(__name__)

# ── Configuration ────────────────────────────────────────────────────────────

_DATA_DIR = pathlib.Path(
    os.environ.get("THOTH_DATA_DIR", pathlib.Path.home() / ".thoth")
)
_DATA_DIR.mkdir(parents=True, exist_ok=True)

_CONFIG_FILE = _DATA_DIR / "dream_config.json"
_JOURNAL_FILE = _DATA_DIR / "dream_journal.json"

# Defaults
_DEFAULT_CONFIG = {
    "enabled": True,
    "window_start": 1,      # 1 AM local time
    "window_end": 5,         # 5 AM local time
    "merge_threshold": 0.93,
    "enrich_min_chars": 80,
    "infer_confidence": 0.7,
    "min_entities": 20,
    "batch_size": 50,
}

_JOURNAL_MAX_ENTRIES = 100
_CHECK_INTERVAL_S = 30 * 60  # Check every 30 minutes


def _load_config() -> dict:
    """Load dream cycle config, falling back to defaults."""
    cfg = dict(_DEFAULT_CONFIG)
    if _CONFIG_FILE.exists():
        try:
            stored = json.loads(_CONFIG_FILE.read_text())
            cfg.update(stored)
        except Exception:
            pass
    return cfg


def _save_config(cfg: dict) -> None:
    _CONFIG_FILE.write_text(json.dumps(cfg, indent=2))


def get_config() -> dict:
    """Public accessor for UI."""
    return _load_config()


def set_enabled(enabled: bool) -> None:
    cfg = _load_config()
    cfg["enabled"] = enabled
    _save_config(cfg)


def set_window(start: int, end: int) -> None:
    cfg = _load_config()
    cfg["window_start"] = start
    cfg["window_end"] = end
    _save_config(cfg)


def is_enabled() -> bool:
    return _load_config().get("enabled", True)


# ── Dream journal ────────────────────────────────────────────────────────────

def _load_journal() -> list[dict]:
    if _JOURNAL_FILE.exists():
        try:
            return json.loads(_JOURNAL_FILE.read_text())
        except Exception:
            pass
    return []


def _save_journal(entries: list[dict]) -> None:
    # Keep only the most recent entries
    entries = entries[-_JOURNAL_MAX_ENTRIES:]
    _JOURNAL_FILE.write_text(json.dumps(entries, indent=2))


def _append_journal(entry: dict) -> None:
    journal = _load_journal()
    journal.append(entry)
    _save_journal(journal)


def get_journal(limit: int = 10) -> list[dict]:
    """Return the most recent dream journal entries."""
    entries = _load_journal()
    return entries[-limit:]


def get_dream_status() -> dict:
    """Return dream cycle status for Activity panel."""
    cfg = _load_config()
    journal = _load_journal()
    last = journal[-1] if journal else None
    return {
        "enabled": cfg.get("enabled", True),
        "window": f"{cfg.get('window_start', 1)}:00 – {cfg.get('window_end', 5)}:00",
        "last_run": last.get("timestamp") if last else None,
        "last_summary": last.get("summary") if last else None,
    }


# ── Idle detection ───────────────────────────────────────────────────────────

def _is_idle() -> bool:
    """Check that no conversations are currently active."""
    try:
        from memory_extraction import _active_threads, _active_lock
        with _active_lock:
            return len(_active_threads) == 0
    except Exception:
        return True  # If we can't check, assume idle


def _in_dream_window() -> bool:
    """Check if current local time is within the dream window."""
    cfg = _load_config()
    hour = datetime.now().hour
    start = cfg.get("window_start", 1)
    end = cfg.get("window_end", 5)
    if start <= end:
        return start <= hour < end
    else:
        # Wraps midnight, e.g. 23:00 - 03:00
        return hour >= start or hour < end


def _already_ran_today() -> bool:
    """Check if a dream cycle already completed today."""
    journal = _load_journal()
    if not journal:
        return False
    last = journal[-1]
    try:
        last_dt = datetime.fromisoformat(last["timestamp"])
        return last_dt.date() == datetime.now().date()
    except (KeyError, ValueError):
        return False


def _should_dream() -> bool:
    """All conditions met for a dream cycle?"""
    if not is_enabled():
        return False
    if _already_ran_today():
        return False
    if not _in_dream_window():
        return False
    if not _is_idle():
        return False
    return True


# ── LLM helper ───────────────────────────────────────────────────────────────

def _llm_call(prompt: str) -> str:
    """Make a direct LLM call. Returns raw response text."""
    from models import get_current_model, get_llm_for
    from langchain_core.messages import HumanMessage

    llm = get_llm_for(get_current_model())
    response = llm.invoke([HumanMessage(content=prompt)])
    raw = response.content or ""
    if isinstance(raw, list):
        parts = []
        for block in raw:
            if isinstance(block, dict) and block.get("type") == "text":
                parts.append(block.get("text", ""))
            elif isinstance(block, str):
                parts.append(block)
        raw = "\n".join(parts)
    if not isinstance(raw, str):
        raw = str(raw) if raw else ""
    # Strip <think>...</think> blocks from reasoning models
    raw = re.sub(r"<think>.*?</think>", "", raw, flags=re.DOTALL)
    raw = re.sub(r"</?think>", "", raw).strip()
    return raw


# ── OP1: Duplicate merge ────────────────────────────────────────────────────

def _find_merge_candidates(batch: list[dict], threshold: float) -> list[tuple[dict, dict, float]]:
    """Find pairs of entities with high semantic similarity and same type.

    Returns list of (entity_a, entity_b, score) tuples, deduplicated so
    each entity appears at most once (highest-scoring pair wins).
    """
    import knowledge_graph as kg

    seen_ids: set[str] = set()
    candidates: list[tuple[dict, dict, float]] = []

    for entity in batch:
        eid = entity["id"]
        if eid in seen_ids:
            continue
        etype = entity.get("entity_type", "")
        search_text = kg._entity_text(entity)

        try:
            hits = kg.semantic_search(search_text, top_k=5, threshold=threshold)
        except Exception:
            continue

        for hit in hits:
            hid = hit["id"]
            if hid == eid or hid in seen_ids:
                continue
            if hit.get("entity_type", "") != etype:
                continue
            # Skip the "User" entity — never merge it
            if entity.get("subject", "").strip().lower() == "user":
                continue
            if hit.get("subject", "").strip().lower() == "user":
                continue

            score = hit.get("score", 0)

            # Subject-name guard: if normalized subjects differ
            # significantly, require much higher similarity to merge.
            subj_a = entity.get("subject", "").strip().lower()
            subj_b = hit.get("subject", "").strip().lower()
            if subj_a != subj_b:
                # Check if one is a substring of the other (e.g. "Bob" / "Bob Smith")
                is_substring = subj_a in subj_b or subj_b in subj_a
                if not is_substring:
                    # Different names — require 0.98+ or skip
                    if score < 0.98:
                        continue

            candidates.append((entity, hit, score))
            seen_ids.add(eid)
            seen_ids.add(hid)
            break  # One merge per entity per cycle

    return candidates


def _merge_entities(entity_a: dict, entity_b: dict) -> dict | None:
    """Merge two entities, keeping the older one. Returns merge log entry."""
    import knowledge_graph as kg
    from prompts import DREAM_MERGE_PROMPT

    # Determine survivor (older by created_at)
    a_created = entity_a.get("created_at", "")
    b_created = entity_b.get("created_at", "")
    if a_created <= b_created:
        survivor, duplicate = entity_a, entity_b
    else:
        survivor, duplicate = entity_b, entity_a

    # LLM: synthesize best description from both
    prompt = DREAM_MERGE_PROMPT.format(
        entity_type=survivor.get("entity_type", ""),
        subject_a=survivor.get("subject", ""),
        description_a=survivor.get("description", ""),
        subject_b=duplicate.get("subject", ""),
        description_b=duplicate.get("description", ""),
    )

    try:
        merged_desc = _llm_call(prompt).strip()
        if not merged_desc or len(merged_desc) < 10:
            return None
    except Exception as exc:
        logger.warning("Dream merge LLM call failed: %s", exc)
        return None

    # Union aliases
    a_aliases = set(a.strip() for a in (survivor.get("aliases", "") or "").split(",") if a.strip())
    b_aliases = set(a.strip() for a in (duplicate.get("aliases", "") or "").split(",") if a.strip())
    # Add the duplicate's subject as an alias if different
    dup_subj = duplicate.get("subject", "").strip()
    surv_subj = survivor.get("subject", "").strip()
    if dup_subj.lower() != surv_subj.lower():
        b_aliases.add(dup_subj)
    merged_aliases = ", ".join(sorted(a_aliases | b_aliases))

    # Re-point all relations from duplicate to survivor
    try:
        dup_rels = kg.get_relations(duplicate["id"], direction="both")
        for rel in dup_rels:
            src = rel["source_id"]
            tgt = rel["target_id"]
            rtype = rel["relation_type"]
            # Determine new endpoints
            new_src = survivor["id"] if src == duplicate["id"] else src
            new_tgt = survivor["id"] if tgt == duplicate["id"] else tgt
            # Skip self-loops
            if new_src == new_tgt:
                continue
            # Add the relation to survivor (ignores duplicates via UNIQUE index)
            kg.add_relation(
                new_src, new_tgt, rtype,
                source="dream_merge",
                confidence=rel.get("confidence", 0.8),
            )
    except Exception as exc:
        logger.debug("Re-pointing relations failed: %s", exc)

    # Update survivor with merged description + aliases
    try:
        kg.update_entity(
            survivor["id"],
            merged_desc,
            aliases=merged_aliases if merged_aliases else None,
        )
    except Exception as exc:
        logger.warning("Dream merge update failed: %s", exc)
        return None

    # Delete the duplicate
    try:
        kg.delete_entity(duplicate["id"])
    except Exception as exc:
        logger.debug("Dream merge delete failed: %s", exc)

    return {
        "survivor_id": survivor["id"],
        "survivor_subject": surv_subj,
        "duplicate_id": duplicate["id"],
        "duplicate_subject": dup_subj,
        "merged_description": merged_desc[:200],
        "aliases": merged_aliases,
    }


# ── OP2: Description enrichment ─────────────────────────────────────────────

def _find_thin_entities(batch: list[dict], min_chars: int) -> list[dict]:
    """Find entities with descriptions shorter than min_chars."""
    return [e for e in batch if len(e.get("description", "") or "") < min_chars]


def _find_conversation_mentions(subject: str, aliases: str = "") -> list[str]:
    """Search conversations for sentence-level mentions of an entity.

    Instead of extracting raw character windows (which mix facts about
    different entities), this splits conversation text into sentences and
    only returns sentences that actually mention the target entity's name
    or aliases.  Returns up to 3 excerpts (one per conversation).
    """
    from threads import _list_threads
    from memory_extraction import _get_thread_messages, _format_conversation

    names = {subject.lower()}
    for alias in (aliases or "").split(","):
        alias = alias.strip()
        if alias:
            names.add(alias.lower())

    threads = _list_threads()
    if not threads:
        return []

    excerpts = []
    for tid, name, created, updated, *rest in threads:
        if len(excerpts) >= 3:
            break
        try:
            messages = _get_thread_messages(tid)
            if not messages:
                continue
            conv_text = _format_conversation(messages)
            conv_lower = conv_text.lower()
            if not any(n in conv_lower for n in names):
                continue

            # Split into sentences and keep only those mentioning the entity
            relevant = _extract_relevant_sentences(conv_text, names)
            if relevant:
                excerpts.append(relevant)
        except Exception:
            continue

    return excerpts


def _extract_relevant_sentences(text: str, names: set[str], max_chars: int = 500) -> str:
    """Extract sentences from *text* that mention any name in *names*.

    Splits on sentence boundaries (`.!?` followed by whitespace or newline)
    and on conversation turn boundaries (`User:` / `Assistant:`).  Returns
    only the sentences that contain at least one of the target names,
    concatenated and capped at *max_chars*.
    """
    # Split on sentence-ending punctuation or conversation turn markers
    parts = re.split(r'(?<=[.!?])\s+|(?=\b(?:User|Assistant):)', text)
    kept: list[str] = []
    total = 0
    for part in parts:
        part = part.strip()
        if not part:
            continue
        part_lower = part.lower()
        if any(n in part_lower for n in names):
            kept.append(part)
            total += len(part)
            if total >= max_chars:
                break
    return " ".join(kept)


def _collect_other_subjects(entity_id: str, all_entities: list[dict] | None = None) -> set[str]:
    """Build a set of lowercased subject names for all entities EXCEPT *entity_id*.

    Used by the post-enrichment validator to detect cross-entity fact-bleed.
    """
    if all_entities is None:
        import knowledge_graph as kg
        all_entities = kg.list_entities(limit=100_000)

    others: set[str] = set()
    for e in all_entities:
        if e["id"] == entity_id:
            continue
        subj = (e.get("subject", "") or "").strip().lower()
        if subj and len(subj) >= 3 and subj != "user":
            others.add(subj)
        for alias in (e.get("aliases", "") or "").split(","):
            alias = alias.strip().lower()
            if alias and len(alias) >= 3 and alias != "user":
                others.add(alias)
    return others


def _validate_enrichment(
    enriched: str,
    entity: dict,
    other_subjects: set[str],
) -> bool:
    """Return True if *enriched* passes cross-entity contamination check.

    Scans the enriched description for mentions of other known entity
    subjects.  Subjects that already appear in the entity's known
    relationships are allowed (e.g. "Diana works with Bob" is fine if
    Diana→Bob is an existing relation).  Everything else is contamination.
    """
    import knowledge_graph as kg

    enriched_lower = enriched.lower()
    entity_subject = (entity.get("subject", "") or "").strip().lower()

    # Collect peer subjects from existing relationships — these are allowed
    allowed: set[str] = set()
    try:
        rels = kg.get_relations(entity["id"], direction="both")
        for r in rels:
            peer = (r.get("peer_subject", "") or "").strip().lower()
            if peer:
                allowed.add(peer)
    except Exception:
        pass

    for subj in other_subjects:
        if subj == entity_subject:
            continue
        if subj in allowed:
            continue
        # Use word-boundary check to avoid false positives on substrings
        if re.search(r'\b' + re.escape(subj) + r'\b', enriched_lower):
            logger.info(
                "Dream enrich REJECTED for '%s': mentions unrelated entity '%s'",
                entity.get("subject", ""), subj,
            )
            return False
    return True


def _enrich_entity(
    entity: dict,
    excerpts: list[str],
    other_subjects: set[str] | None = None,
) -> dict | None:
    """Enrich an entity's description using conversation context."""
    import knowledge_graph as kg
    from prompts import DREAM_ENRICH_PROMPT

    # Build relationship context so the LLM knows entity boundaries
    rel_lines = []
    try:
        rels = kg.get_relations(entity["id"])
        for r in rels[:10]:
            arrow = "→" if r["direction"] == "outgoing" else "←"
            rel_lines.append(f"  {arrow} {r['relation_type']} → {r['peer_subject']}")
    except Exception:
        pass
    relationships_text = "\n".join(rel_lines) if rel_lines else "(none known)"

    context = "\n---\n".join(excerpts[:3])
    prompt = DREAM_ENRICH_PROMPT.format(
        entity_type=entity.get("entity_type", ""),
        subject=entity.get("subject", ""),
        current_description=entity.get("description", ""),
        relationships=relationships_text,
        conversation_excerpts=context,
    )

    try:
        enriched = _llm_call(prompt).strip()
        if not enriched or len(enriched) < 10:
            return None
    except Exception as exc:
        logger.warning("Dream enrich LLM call failed: %s", exc)
        return None

    # Safety: new description must be at least as long as the old one
    old_desc = entity.get("description", "") or ""
    if len(enriched) < len(old_desc):
        return None

    # Layer 2: Cross-entity contamination check (deterministic)
    if other_subjects is not None:
        if not _validate_enrichment(enriched, entity, other_subjects):
            return None

    try:
        kg.update_entity(entity["id"], enriched)
    except Exception as exc:
        logger.warning("Dream enrich update failed: %s", exc)
        return None

    return {
        "entity_id": entity["id"],
        "subject": entity.get("subject", ""),
        "old_length": len(old_desc),
        "new_length": len(enriched),
    }


# ── OP3: Relationship inference ──────────────────────────────────────────────

def _find_cooccurring_pairs(batch: list[dict]) -> list[tuple[dict, dict, str]]:
    """Find entity pairs that co-occur in conversations but have no edge.

    Returns list of (entity_a, entity_b, conversation_excerpt) tuples.
    Limited to 1 pair per entity to keep batch size manageable.
    """
    import knowledge_graph as kg
    from threads import _list_threads
    from memory_extraction import _get_thread_messages, _format_conversation

    threads = _list_threads()
    if not threads:
        return []

    # Build entity lookup by subject/aliases (lowercased)
    entity_names: dict[str, dict] = {}
    for e in batch:
        subj = (e.get("subject", "") or "").strip().lower()
        if subj and subj != "user":
            entity_names[subj] = e
        for alias in (e.get("aliases", "") or "").split(","):
            alias = alias.strip().lower()
            if alias and alias != "user":
                entity_names[alias] = e

    pairs: list[tuple[dict, dict, str]] = []
    seen_pairs: set[tuple[str, str]] = set()
    used_ids: set[str] = set()

    for tid, name, created, updated, *rest in threads:
        if len(pairs) >= 25:  # Cap per cycle
            break
        try:
            messages = _get_thread_messages(tid)
            if not messages:
                continue
            conv_text = _format_conversation(messages)
            conv_lower = conv_text.lower()
        except Exception:
            continue

        # Find which entities from our batch appear in this conversation
        found_in_conv: list[dict] = []
        for name_str, entity in entity_names.items():
            if name_str in conv_lower and entity["id"] not in used_ids:
                if entity not in found_in_conv:
                    found_in_conv.append(entity)

        # Check pairs
        for i, ea in enumerate(found_in_conv):
            for eb in found_in_conv[i + 1:]:
                if ea["id"] == eb["id"]:
                    continue
                pair_key = tuple(sorted([ea["id"], eb["id"]]))
                if pair_key in seen_pairs:
                    continue

                # Check if they already have a relation
                try:
                    existing = kg.get_relations(ea["id"], direction="both")
                    peer_ids = {r.get("peer_id") for r in existing}
                    if eb["id"] in peer_ids:
                        seen_pairs.add(pair_key)
                        continue
                except Exception:
                    continue

                # Extract excerpt around co-occurrence
                for name_str in entity_names:
                    if entity_names[name_str]["id"] == ea["id"]:
                        idx = conv_lower.find(name_str)
                        if idx >= 0:
                            start = max(0, idx - 200)
                            end = min(len(conv_text), idx + 500)
                            excerpt = conv_text[start:end]
                            break
                else:
                    excerpt = conv_text[:500]

                pairs.append((ea, eb, excerpt))
                seen_pairs.add(pair_key)
                used_ids.add(ea["id"])
                used_ids.add(eb["id"])
                break  # One pair per entity
            if ea["id"] in used_ids:
                break

    return pairs


def _infer_relation(entity_a: dict, entity_b: dict, excerpt: str, confidence: float) -> dict | None:
    """Ask the LLM if two entities are related, given conversation evidence."""
    import knowledge_graph as kg
    from prompts import DREAM_INFER_PROMPT

    prompt = DREAM_INFER_PROMPT.format(
        type_a=entity_a.get("entity_type", ""),
        subject_a=entity_a.get("subject", ""),
        description_a=entity_a.get("description", ""),
        type_b=entity_b.get("entity_type", ""),
        subject_b=entity_b.get("subject", ""),
        description_b=entity_b.get("description", ""),
        conversation_excerpt=excerpt[:1000],
    )

    try:
        raw = _llm_call(prompt)
    except Exception as exc:
        logger.warning("Dream infer LLM call failed: %s", exc)
        return None

    # Parse JSON response
    try:
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if not match:
            return None
        result = json.loads(match.group())
        if not result.get("has_relation"):
            return None
        rel_type = result.get("relation_type", "").strip().lower().replace(" ", "_")
        if not rel_type:
            return None
    except (json.JSONDecodeError, AttributeError):
        return None

    # Add the relation
    try:
        rel = kg.add_relation(
            entity_a["id"], entity_b["id"], rel_type,
            source="dream_infer",
            confidence=confidence,
        )
        if not rel:
            return None
    except Exception as exc:
        logger.debug("Dream infer add_relation failed: %s", exc)
        return None

    return {
        "source_id": entity_a["id"],
        "source_subject": entity_a.get("subject", ""),
        "target_id": entity_b["id"],
        "target_subject": entity_b.get("subject", ""),
        "relation_type": rel_type,
        "confidence": confidence,
    }


# ── Main dream cycle ────────────────────────────────────────────────────────

def run_dream_cycle(on_status=None) -> dict:
    """Execute one dream cycle. Returns a summary dict.

    Parameters
    ----------
    on_status : callable, optional
        Called with status strings for UI/logging feedback.
    """
    import knowledge_graph as kg

    cycle_id = uuid.uuid4().hex[:8]
    start_time = datetime.now()
    cfg = _load_config()

    summary = {
        "cycle_id": cycle_id,
        "timestamp": start_time.isoformat(),
        "merges": [],
        "enrichments": [],
        "inferred_relations": [],
        "errors": [],
        "summary": "",
        "duration_s": 0,
    }

    def _status(msg: str):
        logger.info("Dream [%s]: %s", cycle_id, msg)
        if on_status:
            on_status(msg)

    # Check minimum entity count
    entity_count = kg.count_entities()
    if entity_count < cfg.get("min_entities", 20):
        _status(f"Skipped — only {entity_count} entities (min: {cfg.get('min_entities', 20)})")
        summary["summary"] = f"Skipped — {entity_count} entities below minimum"
        summary["duration_s"] = (datetime.now() - start_time).total_seconds()
        _append_journal(summary)
        return summary

    # Select batch
    batch_size = cfg.get("batch_size", 50)
    all_entities = kg.list_entities(limit=100_000)
    # Rotate through entities: use the ones least recently processed
    # Sort by updated_at ascending (oldest first) to prioritise stale entities
    all_entities.sort(key=lambda e: e.get("updated_at", ""))
    batch = all_entities[:batch_size]

    _status(f"Starting dream cycle — {len(batch)} entities (of {entity_count})")

    # Suppress per-entity FAISS rebuilds during batch operations
    kg._skip_reindex = True

    try:
        # ── OP1: Duplicate merge ─────────────────────────────────────
        _status("Phase 1: Scanning for duplicates…")
        merge_threshold = cfg.get("merge_threshold", 0.93)
        # Need FAISS index for similarity search — rebuild if needed
        kg._skip_reindex = False
        candidates = _find_merge_candidates(batch, merge_threshold)
        kg._skip_reindex = True

        for entity_a, entity_b, score in candidates:
            try:
                result = _merge_entities(entity_a, entity_b)
                if result:
                    result["score"] = round(score, 4)
                    summary["merges"].append(result)
                    _status(
                        f"Merged: '{result['duplicate_subject']}' → "
                        f"'{result['survivor_subject']}' ({score:.2f})"
                    )
            except Exception as exc:
                summary["errors"].append(f"Merge error: {exc}")

        # ── OP2: Description enrichment ──────────────────────────────
        _status("Phase 2: Enriching thin descriptions…")
        min_chars = cfg.get("enrich_min_chars", 80)
        thin = _find_thin_entities(batch, min_chars)

        # Pre-compute other subjects for cross-entity validation
        other_subjects = _collect_other_subjects("__none__", all_entities)

        for entity in thin[:20]:  # Cap enrichment per cycle
            # Skip entities that were just merged (may have been deleted)
            merged_ids = {m.get("duplicate_id") for m in summary["merges"]}
            if entity["id"] in merged_ids:
                continue

            excerpts = _find_conversation_mentions(
                entity.get("subject", ""),
                entity.get("aliases", ""),
            )
            if len(excerpts) < 2:
                continue  # Need 2+ conversations as evidence

            try:
                result = _enrich_entity(entity, excerpts, other_subjects)
                if result:
                    summary["enrichments"].append(result)
                    _status(
                        f"Enriched: '{result['subject']}' "
                        f"({result['old_length']} → {result['new_length']} chars)"
                    )
            except Exception as exc:
                summary["errors"].append(f"Enrich error: {exc}")

        # ── OP3: Relationship inference ──────────────────────────────
        _status("Phase 3: Inferring relationships…")
        infer_confidence = cfg.get("infer_confidence", 0.7)
        pairs = _find_cooccurring_pairs(batch)

        for entity_a, entity_b, excerpt in pairs[:15]:  # Cap inferences per cycle
            try:
                result = _infer_relation(entity_a, entity_b, excerpt, infer_confidence)
                if result:
                    summary["inferred_relations"].append(result)
                    _status(
                        f"Inferred: '{result['source_subject']}' "
                        f"--[{result['relation_type']}]--> "
                        f"'{result['target_subject']}'"
                    )
            except Exception as exc:
                summary["errors"].append(f"Infer error: {exc}")

    finally:
        # Restore normal indexing and rebuild once
        kg._skip_reindex = False
        try:
            kg.rebuild_index()
        except Exception as exc:
            summary["errors"].append(f"FAISS rebuild error: {exc}")
            logger.warning("Post-dream FAISS rebuild failed: %s", exc)

        # Rebuild wiki vault if enabled
        try:
            import wiki_vault
            if wiki_vault.is_enabled():
                wiki_vault.rebuild_vault()
        except Exception:
            pass

    # Compose summary text
    m = len(summary["merges"])
    e = len(summary["enrichments"])
    r = len(summary["inferred_relations"])
    errs = len(summary["errors"])
    duration = (datetime.now() - start_time).total_seconds()
    summary["duration_s"] = round(duration, 1)
    summary["summary"] = (
        f"{m} merge(s), {e} enrichment(s), {r} inference(s)"
        + (f", {errs} error(s)" if errs else "")
        + f" in {duration:.0f}s"
    )

    _status(f"Dream cycle complete — {summary['summary']}")
    _append_journal(summary)
    return summary


# ── Background daemon ────────────────────────────────────────────────────────

_dream_thread: threading.Thread | None = None
_dream_stop = threading.Event()


def start_dream_loop() -> None:
    """Start the daemon thread that checks for dream conditions."""
    global _dream_thread
    if _dream_thread is not None and _dream_thread.is_alive():
        return

    _dream_stop.clear()

    def _loop():
        while not _dream_stop.wait(timeout=_CHECK_INTERVAL_S):
            if not _should_dream():
                continue
            logger.info("Dream conditions met — starting dream cycle…")
            try:
                result = run_dream_cycle()
                logger.info("Dream cycle complete: %s", result.get("summary", ""))
            except Exception as exc:
                logger.warning("Dream cycle failed: %s", exc)

    _dream_thread = threading.Thread(target=_loop, daemon=True, name="thoth-dream-cycle")
    _dream_thread.start()
    logger.info(
        "Dream cycle daemon started — window %d:00–%d:00, checks every %d min",
        _load_config().get("window_start", 1),
        _load_config().get("window_end", 5),
        _CHECK_INTERVAL_S // 60,
    )


def stop_dream_loop() -> None:
    """Signal the dream loop thread to stop."""
    _dream_stop.set()
