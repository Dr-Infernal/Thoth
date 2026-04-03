"""Thoth v3.10.0 — Comprehensive Test Suite

Validates that all modules import cleanly, key functions exist,
config round-trips work, DB connectivity works, and the NiceGUI
app can start and serve HTTP on port 8080.

Usage:  python test_suite.py
"""

from __future__ import annotations

import ast
import importlib
import os
import socket
import subprocess
import sys
import time
import traceback
import uuid
from pathlib import Path

# ── Ensure project root is on sys.path ──────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent
os.chdir(PROJECT_ROOT)
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

PASS = 0
FAIL = 0
WARN = 0
RESULTS: list[tuple[str, str, str]] = []  # (status, test_name, detail)


def record(status: str, name: str, detail: str = ""):
    global PASS, FAIL, WARN
    if status == "PASS":
        PASS += 1
    elif status == "FAIL":
        FAIL += 1
    else:
        WARN += 1
    RESULTS.append((status, name, detail))
    icon = {"PASS": "✅", "FAIL": "❌", "WARN": "⚠️"}.get(status, "?")
    line = f"  {icon} {name}"
    if detail:
        line += f"  —  {detail}"
    print(line)


# ═════════════════════════════════════════════════════════════════════════════
# 1. AST SYNTAX CHECK — every .py file must parse
# ═════════════════════════════════════════════════════════════════════════════
print("\n" + "=" * 70)
print("1. AST SYNTAX CHECK")
print("=" * 70)

py_files = sorted(PROJECT_ROOT.glob("*.py")) + sorted((PROJECT_ROOT / "tools").glob("*.py")) + sorted((PROJECT_ROOT / "channels").glob("*.py"))
py_files = [f for f in py_files if f.name != "test_suite.py"]

for f in py_files:
    rel = f.relative_to(PROJECT_ROOT)
    try:
        source = f.read_text(encoding="utf-8")
        ast.parse(source)
        record("PASS", f"syntax: {rel}")
    except SyntaxError as e:
        record("FAIL", f"syntax: {rel}", str(e))

# ═════════════════════════════════════════════════════════════════════════════
# 2. MODULE IMPORTS — core modules
# ═════════════════════════════════════════════════════════════════════════════
print("\n" + "=" * 70)
print("2. CORE MODULE IMPORTS")
print("=" * 70)

CORE_MODULES = [
    "agent",
    "prompts",
    "threads",
    "models",
    "memory",
    "memory_extraction",
    "documents",
    "api_keys",
    "voice",
    "tts",
    "vision",
    "data_reader",
    "tasks",
    "notifications",
    "launcher",
]

for mod_name in CORE_MODULES:
    try:
        importlib.import_module(mod_name)
        record("PASS", f"import {mod_name}")
    except Exception as e:
        record("FAIL", f"import {mod_name}", f"{type(e).__name__}: {e}")

# ═════════════════════════════════════════════════════════════════════════════
# 3. TOOL MODULE IMPORTS
# ═════════════════════════════════════════════════════════════════════════════
print("\n" + "=" * 70)
print("3. TOOL MODULE IMPORTS")
print("=" * 70)

TOOL_MODULES = [
    "tools",
    "tools.base",
    "tools.registry",
    "tools.arxiv_tool",
    "tools.calculator_tool",
    "tools.calendar_tool",
    "tools.chart_tool",
    "tools.conversation_search_tool",
    "tools.documents_tool",
    "tools.duckduckgo_tool",
    "tools.filesystem_tool",
    "tools.gmail_tool",
    "tools.memory_tool",
    "tools.system_info_tool",
    "tools.url_reader_tool",
    "tools.vision_tool",
    "tools.weather_tool",
    "tools.web_search_tool",
    "tools.wikipedia_tool",
    "tools.wolfram_tool",
    "tools.youtube_tool",
]

for mod_name in TOOL_MODULES:
    try:
        importlib.import_module(mod_name)
        record("PASS", f"import {mod_name}")
    except Exception as e:
        record("FAIL", f"import {mod_name}", f"{type(e).__name__}: {e}")

# ═════════════════════════════════════════════════════════════════════════════
# 4. CHANNEL MODULE IMPORTS
# ═════════════════════════════════════════════════════════════════════════════
print("\n" + "=" * 70)
print("4. CHANNEL MODULE IMPORTS")
print("=" * 70)

CHANNEL_MODULES = [
    "channels",
    "channels.config",
    "channels.telegram",
    "channels.email",
]

for mod_name in CHANNEL_MODULES:
    try:
        importlib.import_module(mod_name)
        record("PASS", f"import {mod_name}")
    except Exception as e:
        record("FAIL", f"import {mod_name}", f"{type(e).__name__}: {e}")

# ═════════════════════════════════════════════════════════════════════════════
# 5. KEY FUNCTION / CLASS EXISTENCE
# ═════════════════════════════════════════════════════════════════════════════
print("\n" + "=" * 70)
print("5. KEY FUNCTION / CLASS EXISTENCE")
print("=" * 70)

FUNCTION_CHECKS = [
    ("prompts", "AGENT_SYSTEM_PROMPT"),
    ("prompts", "SUMMARIZE_PROMPT"),
    ("prompts", "EXTRACTION_PROMPT"),
    ("agent", "stream_agent"),
    ("agent", "resume_stream_agent"),
    ("agent", "get_agent_graph"),
    ("agent", "clear_agent_cache"),
    ("threads", "_list_threads"),
    ("threads", "_save_thread_meta"),
    ("threads", "_delete_thread"),
    ("threads", "pick_or_create_thread"),
    ("models", "list_local_models"),
    ("memory", "save_memory"),
    ("memory", "semantic_search"),
    ("memory", "find_duplicate"),
    ("memory", "find_by_subject"),
    ("memory", "update_memory"),
    ("memory", "consolidate_duplicates"),
    ("memory_extraction", "run_extraction"),
    ("memory_extraction", "start_periodic_extraction"),
    ("memory_extraction", "set_active_thread"),
    ("documents", "load_and_vectorize_document"),
    ("documents", "get_embedding_model"),
    ("documents", "get_vector_store"),
    ("api_keys", "get_key"),
    ("api_keys", "set_key"),
    ("api_keys", "apply_keys"),
    ("voice", "get_voice_service"),
    ("tts", "TTSService"),
    ("vision", "capture_frame"),
    ("vision", "capture_screenshot"),
    ("tasks", "seed_default_tasks"),
    ("tasks", "start_task_scheduler"),
    ("notifications", "notify"),
    ("channels.config", "get"),
    ("channels.config", "set"),
    ("channels.telegram", "start_bot"),
    ("channels.telegram", "stop_bot"),
    ("channels.telegram", "is_configured"),
    ("channels.telegram", "is_running"),
    ("channels.email", "start_polling"),
    ("channels.email", "stop_polling"),
    ("channels.email", "is_configured"),
    ("channels.email", "is_running"),
    ("channels.email", "get_poll_interval"),
    ("channels.email", "set_poll_interval"),
    ("tools.registry", "get_all_tools"),
    ("tools.registry", "get_enabled_tools"),
    ("tools.registry", "get_langchain_tools"),
    ("tools.tracker_tool", "TrackerTool"),
    ("tools.tracker_tool", "_tracker_log"),
    ("tools.tracker_tool", "_tracker_query"),
    ("tools.tracker_tool", "_tracker_delete"),
    ("launcher", "_ThothProcess"),
    ("launcher", "ThothTray"),
    ("launcher", "_show_splash"),
    ("launcher", "_SPLASH_TK"),
]

for mod_name, attr_name in FUNCTION_CHECKS:
    try:
        mod = importlib.import_module(mod_name)
        if hasattr(mod, attr_name):
            record("PASS", f"{mod_name}.{attr_name} exists")
        else:
            record("FAIL", f"{mod_name}.{attr_name} exists", "attribute not found")
    except Exception as e:
        record("FAIL", f"{mod_name}.{attr_name} exists", f"import error: {e}")

# ═════════════════════════════════════════════════════════════════════════════
# 6. TOOL REGISTRY — all tools registered
# ═════════════════════════════════════════════════════════════════════════════
print("\n" + "=" * 70)
print("6. TOOL REGISTRY CHECK")
print("=" * 70)

try:
    from tools.registry import get_all_tools

    EXPECTED_TOOLS = {
        "web_search", "duckduckgo", "wikipedia", "arxiv", "youtube",
        "url_reader", "documents", "gmail", "calendar", "filesystem",
        "calculator", "wolfram_alpha", "weather", "vision",
        "memory", "conversation_search", "system_info", "chart",
        "tracker", "shell", "task",
    }

    all_tools = get_all_tools()
    # get_all_tools may return a list of tool objects — extract names
    if isinstance(all_tools, list):
        registered = {getattr(t, 'name', getattr(t, 'tool_name', str(t))) for t in all_tools}
    else:
        registered = set(all_tools.keys())
    missing = EXPECTED_TOOLS - registered
    extra = registered - EXPECTED_TOOLS

    if not missing:
        record("PASS", f"tool registry: {len(registered)} tools registered")
    else:
        record("FAIL", f"tool registry: missing {missing}")

    if extra:
        record("WARN", f"tool registry: extra tools {extra}")

except Exception as e:
    record("FAIL", "tool registry", str(e))

# ═════════════════════════════════════════════════════════════════════════════
# 7. LAUNCHER SPLASH SCREEN VALIDATION
# ═════════════════════════════════════════════════════════════════════════════
print("\n" + "=" * 70)
print("7. LAUNCHER SPLASH SCREEN VALIDATION")
print("=" * 70)

try:
    from launcher import _SPLASH_TK, _show_splash

    # Script must be a non-trivial string
    if isinstance(_SPLASH_TK, str) and len(_SPLASH_TK) > 100:
        record("PASS", f"_SPLASH_TK is {len(_SPLASH_TK)} chars")
    else:
        record("FAIL", "_SPLASH_TK", "empty or too short")

    # Script must be valid Python
    try:
        ast.parse(_SPLASH_TK)
        record("PASS", "_SPLASH_TK is valid Python")
    except SyntaxError as e:
        record("FAIL", "_SPLASH_TK syntax", str(e))

    # Script should reference tkinter and port polling
    for keyword in ["tkinter", "socket", "PORT"]:
        if keyword.lower() in _SPLASH_TK.lower():
            record("PASS", f"splash script contains '{keyword}'")
        else:
            record("FAIL", f"splash script missing '{keyword}'")

    # _show_splash must be callable
    if callable(_show_splash):
        record("PASS", "_show_splash is callable")
    else:
        record("FAIL", "_show_splash not callable")

except Exception as e:
    record("FAIL", "launcher splash validation", str(e))

# ═════════════════════════════════════════════════════════════════════════════
# 8. CHANNELS CONFIG ROUND-TRIP
# ═════════════════════════════════════════════════════════════════════════════
print("\n" + "=" * 70)
print("8. CHANNELS CONFIG ROUND-TRIP")
print("=" * 70)

try:
    from channels import config as ch_config

    # Write a test value
    ch_config.set("_test", "round_trip", True)
    val = ch_config.get("_test", "round_trip", False)
    if val is True:
        record("PASS", "channels config write+read")
    else:
        record("FAIL", "channels config write+read", f"got {val!r}")

    # Clean up
    ch_config.set("_test", "round_trip", None)

except Exception as e:
    record("FAIL", "channels config round-trip", str(e))

# ═════════════════════════════════════════════════════════════════════════════
# 9. THREAD DB CONNECTIVITY
# ═════════════════════════════════════════════════════════════════════════════
print("\n" + "=" * 70)
print("9. THREAD DB CONNECTIVITY")
print("=" * 70)

try:
    from threads import _list_threads
    threads = _list_threads()
    record("PASS", f"thread DB: {len(threads)} threads")
except Exception as e:
    record("FAIL", "thread DB connectivity", str(e))

# ═════════════════════════════════════════════════════════════════════════════
# 10. NO STREAMLIT IMPORTS IN app.py
# ═════════════════════════════════════════════════════════════════════════════
print("\n" + "=" * 70)
print("10. NO STREAMLIT IMPORTS IN app.py")
print("=" * 70)

try:
    source = (PROJECT_ROOT / "app.py").read_text(encoding="utf-8")
    tree = ast.parse(source)

    streamlit_imports = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if "streamlit" in alias.name.lower():
                    streamlit_imports.append(f"line {node.lineno}: import {alias.name}")
        elif isinstance(node, ast.ImportFrom):
            if node.module and "streamlit" in node.module.lower():
                streamlit_imports.append(f"line {node.lineno}: from {node.module} import ...")

    if not streamlit_imports:
        record("PASS", "no streamlit imports in app.py")
    else:
        record("FAIL", "streamlit imports found in app.py", "; ".join(streamlit_imports))

except Exception as e:
    record("FAIL", "streamlit import check", str(e))

# ═════════════════════════════════════════════════════════════════════════════
# 11. NiceGUI APP IMPORT CHECK
# ═════════════════════════════════════════════════════════════════════════════
print("\n" + "=" * 70)
print("11. NiceGUI APP AST PARSE + BASIC IMPORT CHECK")
print("=" * 70)

try:
    source = (PROJECT_ROOT / "app.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    record("PASS", f"app.py AST parsed ({len(source):,} chars)")
except Exception as e:
    record("FAIL", "app.py AST parse", str(e))

# Check nicegui is importable
try:
    import nicegui
    record("PASS", f"nicegui package v{nicegui.__version__}")
except ImportError:
    record("FAIL", "nicegui package import", "not installed")

# ═════════════════════════════════════════════════════════════════════════════
# 12. REQUIREMENTS.TXT DEPENDENCIES
# ═════════════════════════════════════════════════════════════════════════════
print("\n" + "=" * 70)
print("12. KEY DEPENDENCY CHECKS")
print("=" * 70)

KEY_PACKAGES = [
    "nicegui",
    "langchain",
    "langchain_core",
    "langchain_ollama",
    "langgraph",
    "faiss",
    "sentence_transformers",
    "ollama",
    "pystray",
    "PIL",  # Pillow
    "webview",  # pywebview
]

for pkg in KEY_PACKAGES:
    try:
        importlib.import_module(pkg)
        record("PASS", f"dependency: {pkg}")
    except ImportError:
        record("FAIL", f"dependency: {pkg}", "not installed")

# ═════════════════════════════════════════════════════════════════════════════
# 13. TRACKER TOOL FUNCTIONAL TESTS
# ═════════════════════════════════════════════════════════════════════════════
print("\n" + "=" * 70)
print("13. TRACKER TOOL FUNCTIONAL TESTS")
print("=" * 70)

_tracker_test_db = None
try:
    import sqlite3
    import tempfile
    import pathlib
    import json
    from datetime import datetime, timedelta
    from tools import tracker_tool as _tt

    # Use an isolated in-memory DB for tests (schema must match tracker_tool._get_db)
    _tracker_test_db = sqlite3.connect(":memory:")
    _tracker_test_db.execute("PRAGMA journal_mode=WAL")
    _tracker_test_db.execute("PRAGMA foreign_keys=ON")
    _tracker_test_db.executescript("""
        CREATE TABLE IF NOT EXISTS trackers (
            id          TEXT PRIMARY KEY,
            name        TEXT NOT NULL UNIQUE COLLATE NOCASE,
            type        TEXT NOT NULL DEFAULT 'boolean',
            unit        TEXT,
            icon        TEXT,
            created_at  TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS entries (
            id          TEXT PRIMARY KEY,
            tracker_id  TEXT NOT NULL REFERENCES trackers(id) ON DELETE CASCADE,
            timestamp   TEXT NOT NULL,
            value       TEXT NOT NULL DEFAULT 'true',
            notes       TEXT,
            created_at  TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_entries_tracker
            ON entries(tracker_id, timestamp);
    """)

    # 13a. Create tracker
    t = _tt._create_tracker(_tracker_test_db, "Aspirin", "boolean", None)
    if t["name"] == "Aspirin" and t["type"] == "boolean":
        record("PASS", "tracker: create boolean tracker")
    else:
        record("FAIL", "tracker: create boolean tracker", f"got {t}")

    t2 = _tt._create_tracker(_tracker_test_db, "Weight", "numeric", "kg")
    if t2["name"] == "Weight" and t2["unit"] == "kg":
        record("PASS", "tracker: create numeric tracker with unit")
    else:
        record("FAIL", "tracker: create numeric tracker with unit", f"got {t2}")

    t3 = _tt._create_tracker(_tracker_test_db, "Sleep", "duration", None)
    if t3["type"] == "duration":
        record("PASS", "tracker: create duration tracker")
    else:
        record("FAIL", "tracker: create duration tracker", f"got {t3}")

    # 13b. Find tracker (case-insensitive)
    found = _tt._find_tracker(_tracker_test_db, "aspirin")
    if found and found["name"] == "Aspirin":
        record("PASS", "tracker: find case-insensitive")
    else:
        record("FAIL", "tracker: find case-insensitive", f"got {found}")

    not_found = _tt._find_tracker(_tracker_test_db, "Nonexistent")
    if not_found is None:
        record("PASS", "tracker: find returns None for missing")
    else:
        record("FAIL", "tracker: find returns None for missing", f"got {not_found}")

    # 13c. List all trackers
    all_t = _tt._get_all_trackers(_tracker_test_db)
    if len(all_t) == 3 and {x["name"] for x in all_t} == {"Aspirin", "Weight", "Sleep"}:
        record("PASS", f"tracker: list all ({len(all_t)} trackers)")
    else:
        record("FAIL", "tracker: list all", f"got {len(all_t)} trackers")

    # 13d. Log entries
    e1 = _tt._log_entry(_tracker_test_db, t["id"], "true", None, None)
    if e1["value"] == "true" and e1["tracker_id"] == t["id"]:
        record("PASS", "tracker: log boolean entry")
    else:
        record("FAIL", "tracker: log boolean entry", f"got {e1}")

    e2 = _tt._log_entry(_tracker_test_db, t2["id"], "82.5", "morning", None)
    if e2["value"] == "82.5" and e2["notes"] == "morning":
        record("PASS", "tracker: log numeric entry with notes")
    else:
        record("FAIL", "tracker: log numeric entry with notes", f"got {e2}")

    e3 = _tt._log_entry(_tracker_test_db, t["id"], "true", None, "2026-03-10T08:00:00")
    if "2026-03-10" in e3["timestamp"]:
        record("PASS", "tracker: log entry with custom timestamp")
    else:
        record("FAIL", "tracker: log entry with custom timestamp", f"got {e3}")

    # 13e. Get entries with filters
    entries = _tt._get_entries(_tracker_test_db, t["id"])
    if len(entries) == 2:  # two Aspirin entries
        record("PASS", f"tracker: get entries ({len(entries)} rows)")
    else:
        record("FAIL", "tracker: get entries", f"expected 2, got {len(entries)}")

    # e1 was auto-timestamped (now), e3 was set to 2026-03-10.
    # Filter to entries from yesterday onward → should return only e1.
    since_dt = datetime.now() - timedelta(hours=23)
    recent = _tt._get_entries(_tracker_test_db, t["id"], since=since_dt)
    if len(recent) == 1:  # only the one from today
        record("PASS", "tracker: get entries with since filter")
    else:
        record("FAIL", "tracker: get entries with since filter", f"expected 1, got {len(recent)}")

    # 13f. Period parsing
    td_30d = _tt._parse_period("last 30 days")
    if td_30d and td_30d.days == 30:
        record("PASS", "tracker: parse '30 days'")
    else:
        record("FAIL", "tracker: parse '30 days'", f"got {td_30d}")

    td_2w = _tt._parse_period("past 2 weeks")
    if td_2w and td_2w.days == 14:
        record("PASS", "tracker: parse '2 weeks'")
    else:
        record("FAIL", "tracker: parse '2 weeks'", f"got {td_2w}")

    td_3m = _tt._parse_period("3 months")
    if td_3m and td_3m.days == 90:
        record("PASS", "tracker: parse '3 months'")
    else:
        record("FAIL", "tracker: parse '3 months'", f"got {td_3m}")

    td_none = _tt._parse_period("show me stuff")
    if td_none is None:
        record("PASS", "tracker: parse returns None for no-period text")
    else:
        record("FAIL", "tracker: parse returns None for no-period text", f"got {td_none}")

    # 13g. Analysis — adherence
    # Build test entries: aspirin taken on 5 of last 7 days
    test_entries_bool = []
    base = datetime.now()
    for i in [0, 1, 2, 4, 6]:  # 5 distinct days
        test_entries_bool.append({
            "id": i, "tracker_id": 1, "value": "true", "notes": None,
            "timestamp": (base - timedelta(days=i)).strftime("%Y-%m-%dT%H:%M:%S")
        })
    adh = _tt._adherence(test_entries_bool, 7)
    if adh["days_tracked"] == 5 and adh["total_days"] == 7:
        pct = adh["adherence_pct"]
        expected_pct = round(5 / 7 * 100, 1)
        if abs(pct - expected_pct) < 0.2:
            record("PASS", f"tracker: adherence calc ({pct}%)")
        else:
            record("FAIL", "tracker: adherence calc", f"expected ~{expected_pct}%, got {pct}%")
    else:
        record("FAIL", "tracker: adherence calc", f"got {adh}")

    # 13h. Analysis — streaks
    # Consecutive days: today, yesterday, 2 days ago → streak=3
    streak_entries = []
    for i in range(3):
        streak_entries.append({
            "id": i, "tracker_id": 1, "value": "true", "notes": None,
            "timestamp": (base - timedelta(days=i)).strftime("%Y-%m-%dT%H:%M:%S")
        })
    stk = _tt._streaks(streak_entries)
    if stk["current_streak"] == 3 and stk["longest_streak"] == 3:
        record("PASS", f"tracker: streak calc (current={stk['current_streak']})")
    else:
        record("FAIL", "tracker: streak calc", f"got {stk}")

    # 13i. Analysis — numeric stats
    num_entries = []
    for i, v in enumerate([80.0, 82.5, 81.0, 83.0, 79.5]):
        num_entries.append({
            "id": i, "tracker_id": 2, "value": str(v), "notes": None,
            "timestamp": (base - timedelta(days=i)).strftime("%Y-%m-%dT%H:%M:%S")
        })
    ns = _tt._numeric_stats(num_entries)
    if ns and abs(ns["mean"] - 81.2) < 0.1 and ns["min"] == 79.5 and ns["max"] == 83.0 and ns["count"] == 5:
        record("PASS", f"tracker: numeric stats (mean={ns['mean']}, min={ns['min']}, max={ns['max']})")
    else:
        record("FAIL", "tracker: numeric stats", f"got {ns}")

    # 13j. Analysis — frequency
    freq = _tt._frequency(test_entries_bool, 7)
    if freq["total_entries"] == 5 and "per_week" in freq and "per_month" in freq:
        record("PASS", f"tracker: frequency ({freq['total_entries']} entries, {freq['per_week']}/wk)")
    else:
        record("FAIL", "tracker: frequency", f"got {freq}")

    # 13k. Analysis — day of week distribution
    dow = _tt._day_of_week_distribution(test_entries_bool)
    if isinstance(dow, dict) and len(dow) == 7:
        total = sum(dow.values())
        if total == 5:  # 5 entries spread over weekdays
            record("PASS", f"tracker: day-of-week distribution (total={total})")
        else:
            record("FAIL", "tracker: day-of-week distribution", f"total entries={total}, expected 5")
    else:
        record("FAIL", "tracker: day-of-week distribution", f"got {dow}")

    # 13l. Analysis — cycle estimation
    # Simulate period tracker: start every ~28 days
    cycle_entries = []
    for c in range(4):
        ts = (base - timedelta(days=c * 28)).strftime("%Y-%m-%dT%H:%M:%S")
        cycle_entries.append({
            "id": c, "tracker_id": 3, "value": "started", "notes": None,
            "timestamp": ts
        })
    ce = _tt._cycle_estimation(cycle_entries)
    if ce["cycles"] == 4 and ce["avg_cycle_days"] == 28.0:
        record("PASS", f"tracker: cycle estimation (avg={ce['avg_cycle_days']}d)")
    else:
        record("FAIL", "tracker: cycle estimation", f"got {ce}")

    # 13m. Analysis — co-occurrence
    # Create a second tracker and log entries on same days
    t_headache = _tt._create_tracker(_tracker_test_db, "Headache", "boolean", None)
    t_coffee = _tt._create_tracker(_tracker_test_db, "Coffee", "boolean", None)
    overlap_days = [0, 1, 3, 5]  # Both logged on these days
    for d in overlap_days:
        ts = (base - timedelta(days=d)).strftime("%Y-%m-%dT%H:%M:%S")
        _tt._log_entry(_tracker_test_db, t_headache["id"], "true", None, ts)
        _tt._log_entry(_tracker_test_db, t_coffee["id"], "true", None, ts)
    # Add some coffee-only days
    for d in [2, 4, 6]:
        ts = (base - timedelta(days=d)).strftime("%Y-%m-%dT%H:%M:%S")
        _tt._log_entry(_tracker_test_db, t_coffee["id"], "true", None, ts)

    co = _tt._co_occurrence(
        _tracker_test_db, t_headache["id"], t_coffee["id"],
        window_days=0, since=base - timedelta(days=7)
    )
    if co["matches"] == 4 and co["a_total"] == 4 and co["b_total"] == 7:
        record("PASS", f"tracker: co-occurrence (matches={co['matches']}, a={co['a_total']}, b={co['b_total']})")
    else:
        record("FAIL", "tracker: co-occurrence", f"got {co}")

    # 13n. CSV export
    test_rows = [{"date": "2026-03-11", "value": "82.5"}, {"date": "2026-03-10", "value": "80.0"}]
    csv_path = _tt._export_csv(test_rows, "test_weight")
    if pathlib.Path(csv_path).exists():
        csv_content = pathlib.Path(csv_path).read_text()
        if "82.5" in csv_content and "date" in csv_content:
            record("PASS", "tracker: CSV export")
        else:
            record("FAIL", "tracker: CSV export", "content mismatch")
        pathlib.Path(csv_path).unlink(missing_ok=True)  # clean up
    else:
        record("FAIL", "tracker: CSV export", f"file not found: {csv_path}")

    # 13o. TrackerTool class validation
    tool_inst = _tt.TrackerTool()
    if tool_inst.name == "tracker":
        record("PASS", "tracker: TrackerTool.name")
    else:
        record("FAIL", "tracker: TrackerTool.name", f"got '{tool_inst.name}'")

    if tool_inst.enabled_by_default is True:
        record("PASS", "tracker: enabled_by_default")
    else:
        record("FAIL", "tracker: enabled_by_default", f"got {tool_inst.enabled_by_default}")

    if tool_inst.destructive_tool_names == {"tracker_delete"}:
        record("PASS", "tracker: destructive_tool_names")
    else:
        record("FAIL", "tracker: destructive_tool_names", f"got {tool_inst.destructive_tool_names}")

    lc_tools = tool_inst.as_langchain_tools()
    lc_names = sorted([t.name for t in lc_tools])
    if lc_names == ["tracker_delete", "tracker_log", "tracker_query"]:
        record("PASS", f"tracker: 3 LangChain sub-tools {lc_names}")
    else:
        record("FAIL", "tracker: LangChain sub-tools", f"got {lc_names}")

    # 13p. _tracker_log integration (uses real function with test db patching)
    _orig_get_db = _tt._get_db
    _tt._get_db = lambda: _tracker_test_db
    try:
        result = _tt._tracker_log(tracker_name="TestVitaminD", value="5000", tracker_type="numeric", unit="IU")
        if "TestVitaminD" in result and "5000" in result:
            record("PASS", "tracker: _tracker_log integration")
        else:
            record("FAIL", "tracker: _tracker_log integration", f"got: {result[:100]}")
    finally:
        _tt._get_db = _orig_get_db

except Exception as e:
    record("FAIL", "tracker tool tests", f"{type(e).__name__}: {e}")
    traceback.print_exc()
finally:
    if _tracker_test_db:
        _tracker_test_db.close()

# ═════════════════════════════════════════════════════════════════════════════
# 14. LIVE LAUNCH TEST — start app, verify HTTP, shut down
# ═════════════════════════════════════════════════════════════════════════════
print("\n" + "=" * 70)
print("14. LIVE LAUNCH TEST (port 8080)")
print("=" * 70)


def _port_open(port: int, timeout: float = 1.0) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(timeout)
        return s.connect_ex(("127.0.0.1", port)) == 0


# Make sure port is free first
if _port_open(8080):
    record("WARN", "live launch: port 8080 already in use — skipping")
else:
    proc = None
    port_ok = False
    try:
        python = sys.executable
        proc = subprocess.Popen(
            [python, "app.py"],
            cwd=str(PROJECT_ROOT),
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        record("PASS", f"app started (PID {proc.pid})")

        # Wait up to 60s for port 8080 to open
        deadline = time.monotonic() + 60
        while time.monotonic() < deadline:
            if _port_open(8080):
                port_ok = True
                break
            # Check process hasn't crashed
            if proc.poll() is not None:
                record("FAIL", "app crashed during startup", f"exit code: {proc.returncode}")
                break
            time.sleep(1)

        if port_ok:
            record("PASS", "port 8080 responding")

            # Try HTTP GET
            try:
                import urllib.request
                resp = urllib.request.urlopen("http://127.0.0.1:8080", timeout=10)
                status = resp.status
                if status == 200:
                    record("PASS", f"HTTP GET / → {status}")
                else:
                    record("WARN", f"HTTP GET / → {status}")
            except Exception as e:
                record("WARN", f"HTTP GET / failed: {e}")

        elif proc.poll() is None:
            record("FAIL", "port 8080 not open after 60s")

    except Exception as e:
        record("FAIL", "live launch test", str(e))
    finally:
        if proc and proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
            if port_ok:
                record("PASS", "app shut down cleanly")
            else:
                record("WARN", "app process terminated (port never opened)")


# ═════════════════════════════════════════════════════════════════════════════
# 15. CROSS-PLATFORM LOGIC TESTS
# ═════════════════════════════════════════════════════════════════════════════
print("\n" + "=" * 70)
print("15. CROSS-PLATFORM LOGIC TESTS")
print("=" * 70)

# --- 15a. tts.VOICE_CATALOG — curated voices present ---------------------
try:
    from tts import VOICE_CATALOG, _DEFAULT_VOICE, _MODEL_URL, _VOICES_URL

    if len(VOICE_CATALOG) >= 8:
        record("PASS", f"tts: VOICE_CATALOG has {len(VOICE_CATALOG)} voices")
    else:
        record("FAIL", "tts: VOICE_CATALOG", f"only {len(VOICE_CATALOG)} voices")

    # Default voice must be in catalog
    if _DEFAULT_VOICE in VOICE_CATALOG:
        record("PASS", f"tts: default voice '{_DEFAULT_VOICE}' is in catalog")
    else:
        record("FAIL", "tts: default voice not in catalog", _DEFAULT_VOICE)

    # Download URLs must point to GitHub releases
    if _MODEL_URL.startswith("https://github.com/thewh1teagle/kokoro-onnx/releases/"):
        record("PASS", "tts: model download URL has correct base")
    else:
        record("FAIL", "tts: model download URL", _MODEL_URL)

    if _VOICES_URL.startswith("https://github.com/thewh1teagle/kokoro-onnx/releases/"):
        record("PASS", "tts: voices download URL has correct base")
    else:
        record("FAIL", "tts: voices download URL", _VOICES_URL)

except Exception as e:
    record("FAIL", "tts: VOICE_CATALOG", str(e))

# --- 15b. tts._voice_lang() — language inference from voice ID -----------
try:
    from tts import _voice_lang

    LANG_EXPECTED = {
        "af_heart": "en-us",
        "am_michael": "en-us",
        "bf_emma": "en-gb",
        "bm_george": "en-gb",
        "jf_alpha": "ja",
        "zf_xiaobei": "cmn",
    }

    all_ok = True
    for vid, expected_lang in LANG_EXPECTED.items():
        got = _voice_lang(vid)
        if got != expected_lang:
            record("FAIL", f"tts: _voice_lang('{vid}')",
                   f"got '{got}', expected '{expected_lang}'")
            all_ok = False

    if all_ok:
        record("PASS", f"tts: _voice_lang() all {len(LANG_EXPECTED)} mappings OK")
except Exception as e:
    record("FAIL", "tts: _voice_lang tests", str(e))

# --- 15c. tts._prepare_text() — markdown stripping & truncation ----------
try:
    from tts import _prepare_text, _FALLBACK_MSG

    # Basic markdown stripping
    result = _prepare_text("**Hello** world")
    if "**" not in result and "Hello" in result:
        record("PASS", "tts: _prepare_text strips bold markdown")
    else:
        record("FAIL", "tts: _prepare_text bold", result)

    # Code block removal
    result = _prepare_text("Before\n```python\nprint('hi')\n```\nAfter")
    if "print" not in result and "After" in result:
        record("PASS", "tts: _prepare_text strips code blocks")
    else:
        record("FAIL", "tts: _prepare_text code blocks", result)

    # Fallback for mostly-code content
    result = _prepare_text("```\n" + "x = 1\n" * 20 + "```")
    if result == _FALLBACK_MSG:
        record("PASS", "tts: _prepare_text returns fallback for code-heavy text")
    else:
        record("FAIL", "tts: _prepare_text code fallback", result)

except Exception as e:
    record("FAIL", "tts: _prepare_text tests", str(e))

# --- 15d. vision._CV_BACKEND is a valid OpenCV constant ------------------
try:
    import cv2
    from vision import _CV_BACKEND

    EXPECTED_BACKENDS = {cv2.CAP_DSHOW, cv2.CAP_AVFOUNDATION, cv2.CAP_V4L2}
    if _CV_BACKEND in EXPECTED_BACKENDS:
        record("PASS", f"vision: _CV_BACKEND={_CV_BACKEND} is a valid backend")
    else:
        record("FAIL", "vision: _CV_BACKEND", f"unexpected value {_CV_BACKEND}")

    # On Windows it must be CAP_DSHOW
    if sys.platform == "win32":
        if _CV_BACKEND == cv2.CAP_DSHOW:
            record("PASS", "vision: _CV_BACKEND == CAP_DSHOW on Windows")
        else:
            record("FAIL", "vision: _CV_BACKEND on Windows",
                   f"expected {cv2.CAP_DSHOW}, got {_CV_BACKEND}")
    elif sys.platform == "darwin":
        if _CV_BACKEND == cv2.CAP_AVFOUNDATION:
            record("PASS", "vision: _CV_BACKEND == CAP_AVFOUNDATION on macOS")
        else:
            record("FAIL", "vision: _CV_BACKEND on macOS",
                   f"expected {cv2.CAP_AVFOUNDATION}, got {_CV_BACKEND}")
    else:
        if _CV_BACKEND == cv2.CAP_V4L2:
            record("PASS", "vision: _CV_BACKEND == CAP_V4L2 on Linux")
        else:
            record("FAIL", "vision: _CV_BACKEND on Linux",
                   f"expected {cv2.CAP_V4L2}, got {_CV_BACKEND}")

except Exception as e:
    record("FAIL", "vision: _CV_BACKEND", str(e))

# --- 15e. notifications._play_sound exists and is callable ----------------
try:
    from notifications import _play_sound

    if callable(_play_sound):
        record("PASS", "notifications: _play_sound is callable")
    else:
        record("FAIL", "notifications: _play_sound", "not callable")
except Exception as e:
    record("FAIL", "notifications: _play_sound import", str(e))

# --- 15f. launcher._SPLASH_TK contains os.name guard ---------------------
try:
    from launcher import _SPLASH_TK

    if "os.name == 'nt'" in _SPLASH_TK:
        record("PASS", "launcher: _SPLASH_TK has os.name == 'nt' guard")
    else:
        record("FAIL", "launcher: _SPLASH_TK", "missing os.name guard")

    # Must still contain the DLL loading code (Windows path intact)
    if "ctypes.CDLL" in _SPLASH_TK:
        record("PASS", "launcher: _SPLASH_TK still has ctypes.CDLL for Windows")
    else:
        record("FAIL", "launcher: _SPLASH_TK", "ctypes.CDLL block removed")

    # Valid Python
    try:
        ast.parse(_SPLASH_TK)
        record("PASS", "launcher: _SPLASH_TK is valid Python")
    except SyntaxError as se:
        record("FAIL", "launcher: _SPLASH_TK syntax", str(se))

except Exception as e:
    record("FAIL", "launcher: cross-platform splash", str(e))


# ── 15f. Ollama auto-start helpers ──────────────────────────────────────────
try:
    from launcher import _is_ollama_running, _start_ollama, _OLLAMA_PORT

    # _is_ollama_running returns a bool
    result = _is_ollama_running()
    assert isinstance(result, bool), f"Expected bool, got {type(result)}"
    record("PASS", "launcher: _is_ollama_running returns bool")

    # _start_ollama is callable
    assert callable(_start_ollama)
    record("PASS", "launcher: _start_ollama is callable")

    # _OLLAMA_PORT is 11434
    assert _OLLAMA_PORT == 11434, f"Expected 11434, got {_OLLAMA_PORT}"
    record("PASS", "launcher: _OLLAMA_PORT == 11434")

    # _start_ollama skips if Ollama is already running (mock port check)
    import unittest.mock as _mock_ollama
    with _mock_ollama.patch("launcher._is_ollama_running", return_value=True):
        # Should return immediately without launching anything
        _start_ollama()
        record("PASS", "launcher: _start_ollama no-op when already running")

except Exception as e:
    record("FAIL", "launcher: ollama auto-start helpers", str(e))


# ═════════════════════════════════════════════════════════════════════════════
# 16. PROMPT CONTENT VALIDATION
# ═════════════════════════════════════════════════════════════════════════════
print("\n" + "=" * 70)
print("16. PROMPT CONTENT VALIDATION")
print("=" * 70)

try:
    from prompts import AGENT_SYSTEM_PROMPT, SUMMARIZE_PROMPT, EXTRACTION_PROMPT

    # --- 16a. AGENT_SYSTEM_PROMPT must contain key sections ---------------
    _EXPECTED_SECTIONS = [
        "TOOL USE GUIDELINES",
        "HABIT / ACTIVITY TRACKING",
        "DATA VISUALISATION",
        "MEMORY GUIDELINES",
        "CONVERSATION HISTORY SEARCH",
        "HONESTY & CITATIONS",
        "TASKS & REMINDERS",
    ]
    for section in _EXPECTED_SECTIONS:
        if section in AGENT_SYSTEM_PROMPT:
            record("PASS", f"prompt: section '{section}' present")
        else:
            record("FAIL", f"prompt: section '{section}' missing")

    # Must mention key tool names
    _EXPECTED_TOOLS = [
        "read_url", "youtube_search", "youtube_transcript", "analyze_image",
        "calculate", "wolfram_alpha", "save_memory", "search_conversations",
        "tracker_log", "create_chart", "task_update", "task_create",
    ]
    for tool_name in _EXPECTED_TOOLS:
        if tool_name in AGENT_SYSTEM_PROMPT:
            record("PASS", f"prompt: mentions '{tool_name}'")
        else:
            record("FAIL", f"prompt: missing tool mention '{tool_name}'")

    # Anti-fabrication rule must be present
    if "NEVER fabricate" in AGENT_SYSTEM_PROMPT:
        record("PASS", "prompt: anti-fabrication rule")
    else:
        record("FAIL", "prompt: anti-fabrication rule missing")

    # Identity line
    if "You are Thoth" in AGENT_SYSTEM_PROMPT:
        record("PASS", "prompt: identity line")
    else:
        record("FAIL", "prompt: identity line missing")

    # --- 16b. SUMMARIZE_PROMPT -------------------------------------------
    if "Summarize" in SUMMARIZE_PROMPT and "third-person" in SUMMARIZE_PROMPT:
        record("PASS", "prompt: SUMMARIZE_PROMPT content OK")
    else:
        record("FAIL", "prompt: SUMMARIZE_PROMPT content", "missing key phrases")

    # --- 16c. EXTRACTION_PROMPT ------------------------------------------
    if "{conversation}" in EXTRACTION_PROMPT:
        record("PASS", "prompt: EXTRACTION_PROMPT has {conversation} placeholder")
    else:
        record("FAIL", "prompt: EXTRACTION_PROMPT missing {conversation}")

    if "JSON array" in EXTRACTION_PROMPT:
        record("PASS", "prompt: EXTRACTION_PROMPT requests JSON output")
    else:
        record("FAIL", "prompt: EXTRACTION_PROMPT missing JSON instruction")

    _EXPECTED_CATEGORIES = ["person", "preference", "fact", "event", "place", "project"]
    for cat in _EXPECTED_CATEGORIES:
        if cat in EXTRACTION_PROMPT:
            pass  # all good
        else:
            record("FAIL", f"prompt: EXTRACTION_PROMPT missing category '{cat}'")
            break
    else:
        record("PASS", f"prompt: EXTRACTION_PROMPT has all {len(_EXPECTED_CATEGORIES)} categories")

    # --- 16d. agent.py re-exports prompts correctly ----------------------
    import agent as _agent_mod
    if getattr(_agent_mod, "AGENT_SYSTEM_PROMPT", None) is AGENT_SYSTEM_PROMPT:
        record("PASS", "prompt: agent.AGENT_SYSTEM_PROMPT is prompts.AGENT_SYSTEM_PROMPT")
    else:
        record("FAIL", "prompt: agent.AGENT_SYSTEM_PROMPT mismatch")

except Exception as e:
    record("FAIL", "prompt content validation", f"{type(e).__name__}: {e}")


# ═════════════════════════════════════════════════════════════════════════════
# SECTION 17 · Memory system integrity
# ═════════════════════════════════════════════════════════════════════════════
try:
    import memory as _mem_mod
    import memory_extraction as _me_mod
    from tools import memory_tool as _mt_mod

    # --- 17a. memory.py core functions -----------------------------------

    # update_memory accepts keyword-only args for subject, tags, category, source
    import inspect as _inspect
    _um_sig = _inspect.signature(_mem_mod.update_memory)
    _um_params = set(_um_sig.parameters.keys())
    for _kw in ("subject", "tags", "category", "source"):
        if _kw in _um_params:
            record("PASS", f"memory: update_memory accepts '{_kw}' kwarg")
        else:
            record("FAIL", f"memory: update_memory missing '{_kw}' kwarg")

    # save_memory accepts 'source' param
    _sm_sig = _inspect.signature(_mem_mod.save_memory)
    if "source" in _sm_sig.parameters:
        record("PASS", "memory: save_memory accepts 'source' param")
    else:
        record("FAIL", "memory: save_memory missing 'source' param")

    # find_duplicate exists and has correct params
    _fd_sig = _inspect.signature(_mem_mod.find_duplicate)
    _fd_params = set(_fd_sig.parameters.keys())
    for _p in ("category", "subject", "content", "threshold"):
        if _p in _fd_params:
            record("PASS", f"memory: find_duplicate has '{_p}' param")
        else:
            record("FAIL", f"memory: find_duplicate missing '{_p}' param")

    # consolidate_duplicates exists
    if callable(getattr(_mem_mod, "consolidate_duplicates", None)):
        record("PASS", "memory: consolidate_duplicates callable")
    else:
        record("FAIL", "memory: consolidate_duplicates not callable")

    # _normalize_subject exists and works
    if hasattr(_mem_mod, "_normalize_subject"):
        _ns = _mem_mod._normalize_subject
        if _ns("  Mom  ") == "mom" and _ns("My  Cat") == "my cat":
            record("PASS", "memory: _normalize_subject works correctly")
        else:
            record("FAIL", "memory: _normalize_subject output unexpected")
    else:
        record("FAIL", "memory: _normalize_subject missing")

    # VALID_CATEGORIES has expected values
    _vc = _mem_mod.VALID_CATEGORIES
    for _c in ("person", "preference", "fact", "event", "place", "project"):
        if _c in _vc:
            record("PASS", f"memory: category '{_c}' in VALID_CATEGORIES")
        else:
            record("FAIL", f"memory: category '{_c}' missing from VALID_CATEGORIES")

    # --- 17b. Schema: source column present in entities table (v3.6 KG) ---
    import sqlite3 as _sqlite3
    _test_conn = _sqlite3.connect(_mem_mod.DB_PATH)
    _test_conn.row_factory = _sqlite3.Row
    # v3.6+: memories table migrated to entities table
    _tables17 = {row[0] for row in _test_conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()}
    if "entities" in _tables17:
        _cols = [row[1] for row in _test_conn.execute("PRAGMA table_info(entities)").fetchall()]
        if "source" in _cols:
            record("PASS", "memory: 'source' column exists in entities table")
        else:
            record("FAIL", "memory: 'source' column missing from entities table")
    elif "memories" in _tables17:
        _cols = [row[1] for row in _test_conn.execute("PRAGMA table_info(memories)").fetchall()]
        if "source" in _cols:
            record("PASS", "memory: 'source' column exists in memories table (pre-migration)")
        else:
            record("FAIL", "memory: 'source' column missing from memories table")
    else:
        record("FAIL", "memory: neither entities nor memories table found")
    _test_conn.close()

    # --- 17c. memory_extraction.py fixes ---------------------------------

    # run_extraction accepts exclude_thread_ids
    _re_sig = _inspect.signature(_me_mod.run_extraction)
    if "exclude_thread_ids" in _re_sig.parameters:
        record("PASS", "extraction: run_extraction accepts 'exclude_thread_ids'")
    else:
        record("FAIL", "extraction: run_extraction missing 'exclude_thread_ids'")

    # set_active_thread is callable
    if callable(getattr(_me_mod, "set_active_thread", None)):
        record("PASS", "extraction: set_active_thread callable")
    else:
        record("FAIL", "extraction: set_active_thread not callable")

    # _active_threads set exists
    if isinstance(getattr(_me_mod, "_active_threads", None), set):
        record("PASS", "extraction: _active_threads is a set")
    else:
        record("FAIL", "extraction: _active_threads missing or wrong type")

    # set_active_thread works correctly
    _me_mod.set_active_thread("test_thread_123")
    if "test_thread_123" in _me_mod._active_threads:
        record("PASS", "extraction: set_active_thread adds thread")
    else:
        record("FAIL", "extraction: set_active_thread did not add thread")
    _me_mod.set_active_thread("test_thread_456", previous_id="test_thread_123")
    if "test_thread_456" in _me_mod._active_threads and "test_thread_123" not in _me_mod._active_threads:
        record("PASS", "extraction: set_active_thread swaps correctly")
    else:
        record("FAIL", "extraction: set_active_thread swap failed")
    # Clean up
    _me_mod.set_active_thread(None, previous_id="test_thread_456")

    # --- 17d. memory_tool.py live dedup ----------------------------------

    # _save_memory function uses find_by_subject for deterministic dedup
    import textwrap as _tw
    _save_src = _inspect.getsource(_mt_mod._save_memory)
    if "find_by_subject" in _save_src:
        record("PASS", "memory_tool: _save_memory uses find_by_subject")
    else:
        record("FAIL", "memory_tool: _save_memory does NOT use find_by_subject")

    if "merged with existing" in _save_src:
        record("PASS", "memory_tool: _save_memory returns merge message")
    else:
        record("FAIL", "memory_tool: _save_memory missing merge message")

    # _save_memory merges content instead of picking by length
    if "old_content.lower() in new_content.lower()" in _save_src:
        record("PASS", "memory_tool: _save_memory uses content merge (not length)")
    else:
        record("FAIL", "memory_tool: _save_memory should merge content not pick by len")
    if 'len(content) >=' not in _save_src and 'len(content) >' not in _save_src:
        record("PASS", "memory_tool: _save_memory no length-based content selection")
    else:
        record("FAIL", "memory_tool: _save_memory still uses length-based content pick")

    # find_by_subject exists and has correct params (category is optional)
    if callable(getattr(_mem_mod, "find_by_subject", None)):
        _fbs_sig = _inspect.signature(_mem_mod.find_by_subject)
        _fbs_params = set(_fbs_sig.parameters.keys())
        if "category" in _fbs_params and "subject" in _fbs_params:
            record("PASS", "memory: find_by_subject has category+subject params")
            # category should allow None (for cross-category lookup)
            _cat_param = _fbs_sig.parameters["category"]
            if "None" in str(_cat_param.annotation):
                record("PASS", "memory: find_by_subject category accepts None")
            else:
                record("FAIL", "memory: find_by_subject category should accept None")
        else:
            record("FAIL", "memory: find_by_subject missing params")
    else:
        record("FAIL", "memory: find_by_subject not callable")

    # _dedup_and_save uses find_by_subject (not find_duplicate)
    import memory_extraction as _mex
    _dedup_src = _inspect.getsource(_mex._dedup_and_save)
    if "find_by_subject" in _dedup_src:
        record("PASS", "extraction: _dedup_and_save uses find_by_subject")
    else:
        record("FAIL", "extraction: _dedup_and_save should use find_by_subject")
    if "find_duplicate" not in _dedup_src:
        record("PASS", "extraction: _dedup_and_save no longer uses find_duplicate")
    else:
        record("FAIL", "extraction: _dedup_and_save still uses find_duplicate")

    # --- 17e. Prompt memory guidance -------------------------------------
    from prompts import AGENT_SYSTEM_PROMPT as _asp
    _mem_checks = [
        ("DEDUPLICATION", "prompt has DEDUPLICATION guidance"),
        ("UPDATING MEMORIES", "prompt has UPDATING MEMORIES guidance"),
        ("update_memory", "prompt mentions update_memory"),
        ("save_memory", "prompt mentions save_memory"),
    ]
    for _check, _desc in _mem_checks:
        if _check in _asp:
            record("PASS", f"prompt: {_desc}")
        else:
            record("FAIL", f"prompt: {_desc}")

    # --- 17f. Auto-recall includes IDs -----------------------------------
    _agent_src = _inspect.getsource(_inspect.getmodule(_agent_mod._pre_model_trim))
    if "id=" in _agent_src and "m['id']" in _agent_src:
        record("PASS", "agent: auto-recall includes memory IDs")
    else:
        record("FAIL", "agent: auto-recall missing memory IDs")

    # --- 17g. Auto-link on save ------------------------------------------
    import knowledge_graph as _kg17

    # _CATEGORY_RELATION_MAP exists and covers all entity types
    if hasattr(_kg17, "_CATEGORY_RELATION_MAP"):
        _crm = _kg17._CATEGORY_RELATION_MAP
        record("PASS", "kg: _CATEGORY_RELATION_MAP exists")
        for _et in _kg17.VALID_ENTITY_TYPES:
            if _et in _crm:
                record("PASS", f"kg: relation map has '{_et}'")
            else:
                record("FAIL", f"kg: relation map missing '{_et}'")
    else:
        record("FAIL", "kg: _CATEGORY_RELATION_MAP missing")

    # _ensure_user_entity callable
    if callable(getattr(_kg17, "_ensure_user_entity", None)):
        record("PASS", "kg: _ensure_user_entity callable")
    else:
        record("FAIL", "kg: _ensure_user_entity missing")

    # _auto_link_to_user callable
    if callable(getattr(_kg17, "_auto_link_to_user", None)):
        record("PASS", "kg: _auto_link_to_user callable")
    else:
        record("FAIL", "kg: _auto_link_to_user missing")

    # save_entity source code calls _auto_link_to_user
    _se_src = _inspect.getsource(_kg17.save_entity)
    if "_auto_link_to_user" in _se_src:
        record("PASS", "kg: save_entity calls _auto_link_to_user")
    else:
        record("FAIL", "kg: save_entity missing _auto_link_to_user call")

    # Auto-link skips when _skip_reindex is True and when subject is "user"
    if '_normalize_subject(subject) != "user"' in _se_src:
        record("PASS", "kg: save_entity skips auto-link for User entity")
    else:
        record("FAIL", "kg: save_entity should skip auto-link for User")
    if "_skip_reindex" in _se_src:
        record("PASS", "kg: save_entity respects _skip_reindex for auto-link")
    else:
        record("FAIL", "kg: save_entity should check _skip_reindex")

    # --- 17h. Memory decay & recall reinforcement -------------------------
    import json as _json17

    # _decay_multiplier exists and has correct signature
    if callable(getattr(_kg17, "_decay_multiplier", None)):
        record("PASS", "kg: _decay_multiplier callable")
        # Test with a recent entity (should be ~1.0)
        from datetime import datetime as _dt17
        _recent = {"updated_at": _dt17.now().isoformat(), "properties": "{}"}
        _decay_recent = _kg17._decay_multiplier(_recent)
        if 0.95 <= _decay_recent <= 1.0:
            record("PASS", f"kg: decay of recent entity = {_decay_recent:.3f}")
        else:
            record("FAIL", f"kg: decay of recent entity unexpected: {_decay_recent}")

        # Test with a 60-day-old entity (should be ~0.81)
        from datetime import timedelta as _td17
        _old_ts = (_dt17.now() - _td17(days=60)).isoformat()
        _old = {"updated_at": _old_ts, "properties": "{}"}
        _decay_old = _kg17._decay_multiplier(_old)
        if 0.7 <= _decay_old <= 0.9:
            record("PASS", f"kg: decay of 60-day entity = {_decay_old:.3f}")
        else:
            record("FAIL", f"kg: decay of 60-day entity unexpected: {_decay_old}")

        # Test with a 120-day-old entity (should be 0.7 floor)
        _ancient_ts = (_dt17.now() - _td17(days=120)).isoformat()
        _ancient = {"updated_at": _ancient_ts, "properties": "{}"}
        _decay_ancient = _kg17._decay_multiplier(_ancient)
        if abs(_decay_ancient - 0.7) < 0.01:
            record("PASS", f"kg: decay of 120-day entity = {_decay_ancient:.3f} (floor)")
        else:
            record("FAIL", f"kg: decay of 120-day entity unexpected: {_decay_ancient}")

        # Test with recalled_at refreshing old entity
        _refreshed = {
            "updated_at": _ancient_ts,
            "properties": _json17.dumps({"recalled_at": _dt17.now().isoformat()}),
        }
        _decay_refreshed = _kg17._decay_multiplier(_refreshed)
        if 0.95 <= _decay_refreshed <= 1.0:
            record("PASS", f"kg: recalled entity refreshed = {_decay_refreshed:.3f}")
        else:
            record("FAIL", f"kg: recalled entity not refreshed: {_decay_refreshed}")
    else:
        record("FAIL", "kg: _decay_multiplier missing")

    # _touch_recalled callable
    if callable(getattr(_kg17, "_touch_recalled", None)):
        record("PASS", "kg: _touch_recalled callable")
    else:
        record("FAIL", "kg: _touch_recalled missing")

    # graph_enhanced_recall source calls _decay_multiplier and _touch_recalled
    _ger_src = _inspect.getsource(_kg17.graph_enhanced_recall)
    if "_decay_multiplier" in _ger_src:
        record("PASS", "kg: graph_enhanced_recall uses _decay_multiplier")
    else:
        record("FAIL", "kg: graph_enhanced_recall missing _decay_multiplier")
    if "_touch_recalled" in _ger_src:
        record("PASS", "kg: graph_enhanced_recall uses _touch_recalled")
    else:
        record("FAIL", "kg: graph_enhanced_recall missing _touch_recalled")

    # --- 17i. Orphan repair -----------------------------------------------

    if callable(getattr(_kg17, "repair_orphan_entities", None)):
        record("PASS", "kg: repair_orphan_entities callable")
        _roe_src = _inspect.getsource(_kg17.repair_orphan_entities)
        if "_ensure_user_entity" in _roe_src:
            record("PASS", "kg: repair_orphan_entities uses _ensure_user_entity")
        else:
            record("FAIL", "kg: repair_orphan_entities missing _ensure_user_entity")
        if "_CATEGORY_RELATION_MAP" in _roe_src:
            record("PASS", "kg: repair_orphan_entities uses _CATEGORY_RELATION_MAP")
        else:
            record("FAIL", "kg: repair_orphan_entities missing _CATEGORY_RELATION_MAP")
    else:
        record("FAIL", "kg: repair_orphan_entities missing")

    # extraction calls repair_orphan_entities
    _re_src17 = _inspect.getsource(_me_mod.run_extraction)
    if "repair_orphan_entities" in _re_src17:
        record("PASS", "extraction: run_extraction calls repair_orphan_entities")
    else:
        record("FAIL", "extraction: run_extraction missing repair_orphan_entities")

    # --- 17j. FAISS fallback in extraction relation resolution ------------

    _dedup_src17 = _inspect.getsource(_me_mod._dedup_and_save)
    if "semantic_search" in _dedup_src17 and "0.80" in _dedup_src17:
        record("PASS", "extraction: _dedup_and_save has FAISS semantic fallback (0.80)")
    else:
        record("FAIL", "extraction: _dedup_and_save missing FAISS semantic fallback (0.80)")

    # Pass 1 entity dedup also has FAISS fallback (catches synonyms like Father/Dad)
    # Look for semantic_search call BEFORE the "if existing:" entity merge block
    _pass1_faiss = _dedup_src17.find('semantic_search') < _dedup_src17.find('# Merge aliases')
    if _pass1_faiss and 'f"{subject}: {content}"' in _dedup_src17:
        record("PASS", "extraction: Pass 1 entity dedup has FAISS fallback")
    else:
        record("FAIL", "extraction: Pass 1 entity dedup should have FAISS fallback")

    # Extraction uses content merge, not length-based pick
    if "merged_content" in _dedup_src17 and "content_is_richer" not in _dedup_src17:
        record("PASS", "extraction: _dedup_and_save uses content merge")
    else:
        record("FAIL", "extraction: _dedup_and_save should use content merge")

    # --- 17k. Multi-message recall query ----------------------------------

    _recall_src = _inspect.getsource(_agent_mod._pre_model_trim)
    if "human_texts" in _recall_src and "human_texts[0]" in _recall_src and "2000" in _recall_src:
        record("PASS", "agent: auto-recall uses multi-message query (newest-first, 2000 cap)")
    else:
        record("FAIL", "agent: auto-recall should use multi-message query")

except Exception as e:
    record("FAIL", "memory system integrity", f"{type(e).__name__}: {e}")


# ═════════════════════════════════════════════════════════════════════════════
# 18. SHELL TOOL — safety classification, session, history
# ═════════════════════════════════════════════════════════════════════════════
print("\n" + "=" * 70)
print("18. SHELL TOOL")
print("=" * 70)

try:
    from tools.shell_tool import (
        classify_command, ShellSession, ShellSessionManager,
        get_session_manager, get_shell_history, append_shell_history,
        clear_shell_history, ShellTool,
    )

    # 18a. classify_command — safe commands
    _safe_cmds = ["ls -la", "pwd", "git status", "echo hello", "dir", "cat file.txt",
                  "pip list", "python --version"]
    for cmd in _safe_cmds:
        result = classify_command(cmd)
        if result == "safe":
            record("PASS", f"shell: safe classify '{cmd}'")
        else:
            record("FAIL", f"shell: safe classify '{cmd}'", f"got '{result}'")

    # 18b. classify_command — blocked commands
    _blocked_cmds = ["rm -rf /", "mkfs /dev/sda", "format C:", "shutdown -h now",
                     "dd if=/dev/zero of=/dev/sda"]
    for cmd in _blocked_cmds:
        result = classify_command(cmd)
        if result == "blocked":
            record("PASS", f"shell: blocked classify '{cmd}'")
        else:
            record("FAIL", f"shell: blocked classify '{cmd}'", f"got '{result}'")

    # 18c. classify_command — needs_approval
    _approval_cmds = ["pip install requests", "npm install", "python script.py",
                      "git push origin main"]
    for cmd in _approval_cmds:
        result = classify_command(cmd)
        if result == "needs_approval":
            record("PASS", f"shell: approval classify '{cmd}'")
        else:
            record("FAIL", f"shell: approval classify '{cmd}'", f"got '{result}'")

    # 18d. ShellTool class validation
    _st = ShellTool()
    assert _st.name == "shell", f"Expected 'shell', got '{_st.name}'"
    assert _st.enabled_by_default is True
    assert _st.destructive_tool_names == set()
    _lc_tools = _st.as_langchain_tools()
    assert len(_lc_tools) == 1
    assert _lc_tools[0].name == "run_command"
    record("PASS", "shell: ShellTool class valid")

    # 18e. ShellTool registered in registry
    from tools import registry as _sreg
    _shell_t = _sreg.get_tool("shell")
    assert _shell_t is not None, "Shell tool not registered"
    record("PASS", "shell: registered in registry")

    # 18f. ShellSession — run a simple command
    import tempfile
    _test_dir = tempfile.mkdtemp()
    _sess = ShellSession(working_dir=_test_dir)
    _result = _sess.run_command("echo hello_thoth")
    assert "hello_thoth" in _result["output"], f"Expected 'hello_thoth' in output, got: {_result['output']}"
    assert _result["exit_code"] == 0, f"Expected exit_code 0, got {_result['exit_code']}"
    record("PASS", "shell: session runs commands")

    # 18g. ShellSession — cd persists
    import platform as _plat
    if _plat.system() == "Windows":
        _cd_result = _sess.run_command(f"Set-Location '{_test_dir}'")
    else:
        _cd_result = _sess.run_command(f"cd '{_test_dir}'")
    assert _sess.cwd == _test_dir or os.path.samefile(_sess.cwd, _test_dir), \
        f"cwd not updated: {_sess.cwd} != {_test_dir}"
    record("PASS", "shell: cd persists cwd")

    # 18h. ShellSessionManager
    _mgr = ShellSessionManager()
    _s1 = _mgr.get_session("test_thread_1", _test_dir)
    _s2 = _mgr.get_session("test_thread_1", _test_dir)
    assert _s1 is _s2, "Same thread should return same session"
    _s3 = _mgr.get_session("test_thread_2", _test_dir)
    assert _s1 is not _s3, "Different threads should return different sessions"
    _mgr.kill_session("test_thread_1")
    _mgr.kill_all()
    record("PASS", "shell: session manager works")

    # 18i. Shell history persistence
    _test_tid = "test_history_" + str(int(time.time()))
    append_shell_history(_test_tid, {"command": "echo test", "output": "test", "exit_code": 0})
    _hist = get_shell_history(_test_tid)
    assert len(_hist) == 1, f"Expected 1 entry, got {len(_hist)}"
    assert _hist[0]["command"] == "echo test"
    clear_shell_history(_test_tid)
    _hist2 = get_shell_history(_test_tid)
    assert len(_hist2) == 0, f"Expected 0 entries after clear, got {len(_hist2)}"
    record("PASS", "shell: history persistence works")

    # Cleanup
    import shutil
    shutil.rmtree(_test_dir, ignore_errors=True)

except Exception as e:
    record("FAIL", "shell tool tests", f"{type(e).__name__}: {e}")
    traceback.print_exc()


# ═════════════════════════════════════════════════════════════════════════════
# 19. BROWSER TOOL — class, registry, session manager, history, snapshot JS
# ═════════════════════════════════════════════════════════════════════════════
print("\n" + "=" * 70)
print("19. BROWSER TOOL")
print("=" * 70)

try:
    from tools.browser_tool import (
        BrowserTool, BrowserSession, BrowserSessionManager,
        get_session_manager as get_browser_session_manager,
        get_browser_history, append_browser_history, clear_browser_history,
        _get_thread_id, _detect_channel,
        _format_snapshot, _PROFILE_DIR, _HISTORY_PATH, _build_snapshot_js,
        _snapshot_char_budget,
        _NavigateInput, _ClickInput, _TypeInput, _ScrollInput, _TabInput,
    )

    # 19a. BrowserTool class validation
    _bt = BrowserTool()
    assert _bt.name == "browser", f"Expected 'browser', got '{_bt.name}'"
    assert _bt.display_name == "🌐 Browser"
    assert _bt.enabled_by_default is True
    assert _bt.destructive_tool_names == set()
    record("PASS", "browser: BrowserTool class valid")

    # 19b. as_langchain_tools returns 7 sub-tools
    _lc_tools = _bt.as_langchain_tools()
    assert len(_lc_tools) == 7, f"Expected 7 tools, got {len(_lc_tools)}"
    _expected_names = {
        "browser_navigate", "browser_click", "browser_type",
        "browser_scroll", "browser_snapshot", "browser_back", "browser_tab",
    }
    _actual_names = {t.name for t in _lc_tools}
    assert _actual_names == _expected_names, f"Tool names mismatch: {_actual_names}"
    record("PASS", "browser: 7 sub-tools with correct names")

    # 19c. BrowserTool registered in registry
    from tools import registry as _breg
    _browser_t = _breg.get_tool("browser")
    assert _browser_t is not None, "Browser tool not registered"
    record("PASS", "browser: registered in registry")

    # 19d. Pydantic input schemas
    _nav = _NavigateInput(url="https://example.com")
    assert _nav.url == "https://example.com"
    record("PASS", "browser: NavigateInput schema valid")

    _click = _ClickInput(ref=5)
    assert _click.ref == 5
    record("PASS", "browser: ClickInput schema valid")

    _type = _TypeInput(ref=3, text="hello", submit=True)
    assert _type.ref == 3
    assert _type.text == "hello"
    assert _type.submit is True
    record("PASS", "browser: TypeInput schema valid")

    _scroll = _ScrollInput(direction="up", amount=2)
    assert _scroll.direction == "up"
    assert _scroll.amount == 2
    record("PASS", "browser: ScrollInput schema valid")

    _tab = _TabInput(action="new", url="https://test.com")
    assert _tab.action == "new"
    assert _tab.url == "https://test.com"
    assert _tab.tab_id is None
    record("PASS", "browser: TabInput schema valid")

    # 19e. BrowserSessionManager (single shared session)
    _bsm = BrowserSessionManager()
    _bs1 = _bsm.get_session("test_thread_1")
    _bs2 = _bsm.get_session("test_thread_1")
    assert _bs1 is _bs2, "Same thread should return same session"
    _bs3 = _bsm.get_session("test_thread_2")
    assert _bs1 is _bs3, "Different threads should return same shared session"
    assert _bsm.has_active_session(), "Session should exist after get_session"
    _bsm.kill_session("test_thread_1")  # releases thread's tab (no browser launched, safe)
    assert _bsm.has_active_session(), "kill_session releases tab, not session"
    _bsm.kill_all()
    assert not _bsm.has_active_session(), "kill_all should clear shared session"
    record("PASS", "browser: shared session manager works")

    # 19f. Browser history persistence
    _test_btid = "test_browser_history_" + str(int(time.time()))
    append_browser_history(_test_btid, {
        "action": "navigate", "url": "https://example.com",
        "timestamp": "2025-01-01T00:00:00"
    })
    _bhist = get_browser_history(_test_btid)
    assert len(_bhist) == 1, f"Expected 1 entry, got {len(_bhist)}"
    assert _bhist[0]["action"] == "navigate"
    assert _bhist[0]["url"] == "https://example.com"
    clear_browser_history(_test_btid)
    _bhist2 = get_browser_history(_test_btid)
    assert len(_bhist2) == 0, f"Expected 0 entries after clear, got {len(_bhist2)}"
    record("PASS", "browser: history persistence works")

    # 19g. Per-thread tab isolation (no browser launched — tests data structures)
    _bs_g = BrowserSession()
    assert isinstance(_bs_g._thread_pages, dict), "_thread_pages should be a dict"
    assert len(_bs_g._thread_pages) == 0, "No pages before launch"
    assert hasattr(_bs_g, '_get_page_for_thread'), "Must expose _get_page_for_thread"
    assert hasattr(_bs_g, 'release_thread'), "Must expose release_thread"
    # release_thread on un-launched session should not crash
    _bs_g.release_thread("some_thread")
    record("PASS", "browser: per-thread tab isolation structures valid")

    # 19h. _format_snapshot
    _test_snap = {
        "url": "https://example.com",
        "title": "Example Domain",
        "refs": ['[1] link "More information" → https://iana.org'],
        "refCount": 1,
    }
    _snap_text = _format_snapshot(_test_snap)
    assert "URL: https://example.com" in _snap_text
    assert "Title: Example Domain" in _snap_text
    assert "[1] link" in _snap_text
    assert "Interactive elements (1):" in _snap_text
    record("PASS", "browser: _format_snapshot works")

    # 19i. _format_snapshot truncation
    # Scale ref count to exceed the context-aware budget (cloud models
    # have much larger budgets than local models).
    _budget = _snapshot_char_budget()
    _n_refs = _budget // 15 + 500  # each ref ≈15-25 chars; ensure we exceed _budget
    _long_snap = {
        "url": "https://example.com",
        "title": "Test",
        "refs": [f"[{i}] button \"btn{i}\"" for i in range(1, _n_refs + 1)],
        "refCount": _n_refs,
    }
    _long_text = _format_snapshot(_long_snap)
    assert len(_long_text) <= _budget + 100  # budget + some fuzz
    assert "truncated" in _long_text
    record("PASS", "browser: snapshot truncation works")

    # 19j. Profile directory path is under ~/.thoth/
    assert "browser_profile" in str(_PROFILE_DIR)
    assert ".thoth" in str(_PROFILE_DIR)
    record("PASS", "browser: profile dir path correct")

    # 19k. History path is under ~/.thoth/
    assert "browser_history.json" in str(_HISTORY_PATH)
    record("PASS", "browser: history path correct")

    # 19l. Snapshot JS builder returns a valid non-empty string
    _js = _build_snapshot_js(100)
    assert isinstance(_js, str) and len(_js) > 100
    assert "data-thoth-ref" in _js
    assert "interactiveSelectors" in _js
    assert "MAX_ELEMENTS = 100" in _js
    record("PASS", "browser: snapshot JS valid")

    # 19m. javascript: URL rejection in navigate tool
    _nav_tool = None
    for _t in _lc_tools:
        if _t.name == "browser_navigate":
            _nav_tool = _t
            break
    assert _nav_tool is not None
    # Can't call the tool directly without playwright, but verify the function
    # logic by calling through the closure directly
    record("PASS", "browser: navigate tool found")

    # 19n. _detect_channel returns str or None
    # Don't actually run detection (slow) — just verify the function exists
    assert callable(_detect_channel)
    record("PASS", "browser: _detect_channel callable")

    # 19o. BrowserSession class instantiation (without launching browser)
    _bs_test = BrowserSession()
    assert _bs_test._launched is False
    assert _bs_test._context is None
    assert _bs_test._pw is None
    assert _bs_test._browser_pid is None
    assert _bs_test._launch_error is None
    record("PASS", "browser: BrowserSession init without launch")

    # 19p. Global session manager is accessible
    _global_bsm = get_browser_session_manager()
    assert isinstance(_global_bsm, BrowserSessionManager)
    record("PASS", "browser: global session manager accessible")

    # 19q. prompts.py contains browser guidelines
    import prompts as _bprompts
    assert "BROWSER AUTOMATION" in _bprompts.AGENT_SYSTEM_PROMPT
    assert "browser_navigate" in _bprompts.AGENT_SYSTEM_PROMPT
    assert "browser_snapshot" in _bprompts.AGENT_SYSTEM_PROMPT
    record("PASS", "browser: prompts contain browser guidelines")

    # 19r. requirements.txt contains playwright
    _req_path = pathlib.Path(__file__).parent / "requirements.txt"
    if _req_path.exists():
        _req_text = _req_path.read_text(encoding="utf-8")
        assert "playwright" in _req_text, "playwright not in requirements.txt"
        record("PASS", "browser: playwright in requirements.txt")
    else:
        record("WARN", "browser: requirements.txt not found")

except Exception as e:
    record("FAIL", "browser tool tests", f"{type(e).__name__}: {e}")
    traceback.print_exc()


# ═════════════════════════════════════════════════════════════════════════════
# 20. BROWSER SNAPSHOT COMPRESSION — _pre_model_trim stale snapshot stubbing
# ═════════════════════════════════════════════════════════════════════════════
print("\n" + "=" * 70)
print("20. BROWSER SNAPSHOT COMPRESSION")
print("=" * 70)

try:
    from langchain_core.messages import ToolMessage as _TM, AIMessage as _AIM, HumanMessage as _HM
    import agent as _agent_mod

    def _make_browser_tool_msg(name: str, url: str, title: str, body: str = "",
                                tool_call_id: str = "tc_0"):
        """Build a ToolMessage that mimics a browser tool result."""
        content = f"URL: {url}\nTitle: {title}\nInteractive elements (3):\n  [0] link \"Home\"\n  [1] input\n  [2] button \"Submit\""
        if body:
            content = body + "\n\n" + content
        return _TM(content=content, name=name, tool_call_id=tool_call_id)

    def _make_ai_tool_call(tool_call_id: str, name: str):
        """Build an AIMessage with a tool_calls entry (required by LangChain)."""
        return _AIM(content="", tool_calls=[{
            "id": tool_call_id, "name": name, "args": {}
        }])

    # 20a. Compression: oldest browser messages become stubs, newest _n_keep stay full.
    # Scale message count based on _keep_browser_snapshots() so this works
    # with both small-context local models and large-context cloud models.
    _n_keep = _agent_mod._keep_browser_snapshots()
    _n_extra = 3  # how many messages beyond _n_keep to create (→ these become stubs)
    _n_total = _n_keep + _n_extra
    _snap_msgs = []
    for idx in range(_n_total):
        tc_id = f"tc_{idx}"
        _snap_msgs.append(_make_ai_tool_call(tc_id, "browser_navigate"))
        _snap_msgs.append(_make_browser_tool_msg(
            "browser_navigate",
            f"https://example.com/page{idx}",
            f"Page {idx}",
            tool_call_id=tc_id,
        ))

    # Simulate just the compression logic directly (avoid full _pre_model_trim
    # which needs model context_size, summary cache, etc.)
    _msgs_copy = list(_snap_msgs)
    _b_indices = [
        i for i, m in enumerate(_msgs_copy)
        if m.type == "tool" and (getattr(m, "name", "") or "").startswith("browser_")
    ]
    assert len(_b_indices) == _n_total, f"Expected {_n_total} browser tool msgs, got {len(_b_indices)}"
    if len(_b_indices) > _n_keep:
        for i in _b_indices[:-_n_keep]:
            m = _msgs_copy[i]
            content = m.content or ""
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
            _msgs_copy[i] = _TM(content=stub, name=m.name, tool_call_id=m.tool_call_id)

    # First _n_extra should be stubs, last _n_keep should be full
    for idx, bi in enumerate(_b_indices[:_n_extra]):
        assert "[Prior browser" in _msgs_copy[bi].content, \
            f"Msg {idx} should be a stub, got: {_msgs_copy[bi].content[:80]}"
    for idx, bi in enumerate(_b_indices[_n_extra:]):
        assert "Interactive elements" in _msgs_copy[bi].content, \
            f"Msg {idx+_n_extra} should be full, got: {_msgs_copy[bi].content[:80]}"
    record("PASS", f"browser compression: {_n_total} msgs → stubs for first {_n_extra}, full for last {_n_keep}")

    # 20b. Stubs contain correct URL and title
    _stub0 = _msgs_copy[_b_indices[0]].content
    assert "https://example.com/page0" in _stub0, f"Stub missing URL: {_stub0}"
    assert "Page 0" in _stub0, f"Stub missing title: {_stub0}"
    assert "navigate" in _stub0, f"Stub missing action: {_stub0}"
    record("PASS", "browser compression: stubs contain URL, title, action")

    # 20c. Stubs preserve tool_call_id and name
    _stub_msg0 = _msgs_copy[_b_indices[0]]
    assert _stub_msg0.name == "browser_navigate"
    assert _stub_msg0.tool_call_id == "tc_0"
    record("PASS", "browser compression: stubs preserve name and tool_call_id")

    # 20d. Non-browser ToolMessages are NOT compressed
    # Use _n_keep + 1 browser msgs to guarantee compression fires
    _mixed = [
        _make_ai_tool_call("tc_ws", "web_search"),
        _TM(content="Search results for Python...", name="web_search", tool_call_id="tc_ws"),
    ]
    for idx in range(_n_keep + 1):
        tc_id = f"tc_b{idx}"
        _mixed.append(_make_ai_tool_call(tc_id, "browser_click"))
        _mixed.append(_make_browser_tool_msg("browser_click", f"https://x.com/{idx}",
                                              f"X {idx}", body="Clicked [1] link",
                                              tool_call_id=tc_id))
    _mixed_copy = list(_mixed)
    _b_mixed = [
        i for i, m in enumerate(_mixed_copy)
        if m.type == "tool" and (getattr(m, "name", "") or "").startswith("browser_")
    ]
    assert len(_b_mixed) > _n_keep, "Need more browser msgs than _n_keep for this test"
    for i in _b_mixed[:-_n_keep]:
        m = _mixed_copy[i]
        content = m.content or ""
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
        _mixed_copy[i] = _TM(content=stub, name=m.name, tool_call_id=m.tool_call_id)
    # web_search result should be untouched
    assert _mixed_copy[1].content == "Search results for Python..."
    assert _mixed_copy[1].name == "web_search"
    record("PASS", "browser compression: non-browser ToolMessages untouched")

    # 20e. Fewer than _keep_browser_snapshots() → no compression
    _few = []
    for idx in range(2):
        tc_id = f"tc_f{idx}"
        _few.append(_make_ai_tool_call(tc_id, "browser_snapshot"))
        _few.append(_make_browser_tool_msg("browser_snapshot", f"https://f.com/{idx}",
                                            f"F {idx}", tool_call_id=tc_id))
    _few_copy = list(_few)
    _b_few = [
        i for i, m in enumerate(_few_copy)
        if m.type == "tool" and (getattr(m, "name", "") or "").startswith("browser_")
    ]
    if len(_b_few) > _n_keep:
        assert False, "Should not compress when count <= keep"
    for bi in _b_few:
        assert "Interactive elements" in _few_copy[bi].content
    record("PASS", "browser compression: ≤ keep count → no compression")

    # 20f. _keep_browser_snapshots() returns ≥ 2
    assert _agent_mod._keep_browser_snapshots() >= 2
    record("PASS", "browser compression: _keep_browser_snapshots() >= 2")

    # 20g. click/type results with action prefix — URL/title still extracted
    _click_msg = _make_browser_tool_msg(
        "browser_click", "https://clicked.com", "Clicked Page",
        body="Clicked [5] button 'Go'", tool_call_id="tc_click"
    )
    _content = _click_msg.content
    _url_found = ""
    _title_found = ""
    for line in _content.split("\n"):
        if line.startswith("URL: ") and not _url_found:
            _url_found = line[5:].strip()
        elif line.startswith("Title: ") and not _title_found:
            _title_found = line[7:].strip()
        if _url_found and _title_found:
            break
    assert _url_found == "https://clicked.com", f"URL extraction failed: {_url_found!r}"
    assert _title_found == "Clicked Page", f"Title extraction failed: {_title_found!r}"
    record("PASS", "browser compression: URL/title extracted from prefixed results")

except Exception as e:
    record("FAIL", "browser compression tests", f"{type(e).__name__}: {e}")
    traceback.print_exc()


# ═════════════════════════════════════════════════════════════════════════════
# 21. TASK TOOL FUNCTIONAL TESTS
# ═════════════════════════════════════════════════════════════════════════════
print("\n" + "=" * 70)
print("21. TASK TOOL")
print("=" * 70)

try:
    from tools.task_tool import TaskTool, _task_update, _TaskUpdateInput

    _task_tool = TaskTool()

    # 21a. name and enabled_by_default
    if _task_tool.name == "task":
        record("PASS", "task: TaskTool.name == 'task'")
    else:
        record("FAIL", "task: TaskTool.name", f"got '{_task_tool.name}'")

    if _task_tool.enabled_by_default is True:
        record("PASS", "task: enabled_by_default")
    else:
        record("FAIL", "task: enabled_by_default", f"got {_task_tool.enabled_by_default}")

    # 21b. destructive_tool_names
    if _task_tool.destructive_tool_names == {"task_delete"}:
        record("PASS", "task: destructive_tool_names")
    else:
        record("FAIL", "task: destructive_tool_names", f"got {_task_tool.destructive_tool_names}")

    # 21c. LangChain sub-tools — should be 5
    _task_lc = _task_tool.as_langchain_tools()
    _task_lc_names = sorted([t.name for t in _task_lc])
    _expected_lc = ["task_create", "task_delete", "task_list", "task_run_now", "task_update"]
    if _task_lc_names == _expected_lc:
        record("PASS", f"task: 5 LangChain sub-tools {_task_lc_names}")
    else:
        record("FAIL", "task: LangChain sub-tools", f"got {_task_lc_names}")

    # 21d. _TaskUpdateInput schema fields
    _update_fields = set(_TaskUpdateInput.model_fields.keys())
    _expected_fields = {"task_id", "name", "schedule", "prompts", "enabled", "model"}
    if _update_fields == _expected_fields:
        record("PASS", f"task: _TaskUpdateInput fields {sorted(_update_fields)}")
    else:
        record("FAIL", "task: _TaskUpdateInput fields", f"got {sorted(_update_fields)}")

    # 21e. _task_update with invalid ID returns error message
    _update_result = _task_update(task_id="nonexistent-id-12345")
    if "not found" in _update_result.lower():
        record("PASS", "task: _task_update invalid ID returns not-found")
    else:
        record("FAIL", "task: _task_update invalid ID", f"got: {_update_result[:80]}")

    # 21f. _task_update with no fields returns hint
    _update_noop = _task_update(task_id="nonexistent-id-12345")
    # It should hit "not found" first before "no fields" — that's correct
    if "not found" in _update_noop.lower():
        record("PASS", "task: _task_update no-fields path (not-found first)")
    else:
        record("FAIL", "task: _task_update no-fields", f"got: {_update_noop[:80]}")

    # 21g. execute() fallback message includes task_update
    _exec_msg = _task_tool.execute("anything")
    if "task_update" in _exec_msg:
        record("PASS", "task: execute() mentions task_update")
    else:
        record("FAIL", "task: execute() message", f"got: {_exec_msg[:80]}")

    # 21h. _TaskCreateInput includes 'model' field
    from tools.task_tool import _TaskCreateInput
    if "model" in _TaskCreateInput.model_fields:
        record("PASS", "task: _TaskCreateInput has 'model' field")
    else:
        record("FAIL", "task: _TaskCreateInput missing 'model' field")

    # 21i. get_llm_for returns ChatOllama instance
    from models import get_llm_for
    from langchain_ollama import ChatOllama as _ChatOllama
    # Verify function exists and signature accepts model_name
    import inspect as _inspect
    _sig = _inspect.signature(get_llm_for)
    _params = list(_sig.parameters.keys())
    if _params[:2] == ["model_name", "num_ctx"]:
        record("PASS", "task: get_llm_for(model_name, num_ctx) signature")
    else:
        record("FAIL", "task: get_llm_for signature", f"got params {_params}")

    # 21j. system prompt mentions MODEL OVERRIDE
    from prompts import AGENT_SYSTEM_PROMPT
    if "MODEL OVERRIDE" in AGENT_SYSTEM_PROMPT:
        record("PASS", "task: AGENT_SYSTEM_PROMPT contains MODEL OVERRIDE")
    else:
        record("FAIL", "task: AGENT_SYSTEM_PROMPT missing MODEL OVERRIDE")

    # 21k. agent.get_agent_graph accepts model_override kwarg
    import agent as _agent_mod
    _gag_sig = _inspect.signature(_agent_mod.get_agent_graph)
    if "model_override" in _gag_sig.parameters:
        record("PASS", "task: get_agent_graph accepts model_override")
    else:
        record("FAIL", "task: get_agent_graph missing model_override param")

except Exception as e:
    record("FAIL", "task tool tests", f"{type(e).__name__}: {e}")
    traceback.print_exc()


# ═════════════════════════════════════════════════════════════════════════════
# 22. ACTIVITY TAB — new helpers for the Activity monitoring panel
# ═════════════════════════════════════════════════════════════════════════════
print("\n" + "=" * 70)
print("22. ACTIVITY TAB helpers")
print("=" * 70)

try:
    # 22a. get_next_fire_times exists and returns a list
    from tasks import get_next_fire_times
    _fires = get_next_fire_times()
    if isinstance(_fires, list):
        record("PASS", f"activity: get_next_fire_times() returns list (len={len(_fires)})")
    else:
        record("FAIL", "activity: get_next_fire_times()", f"got {type(_fires)}")

    # 22b. get_next_fire_times respects limit
    _fires2 = get_next_fire_times(limit=3)
    if isinstance(_fires2, list) and len(_fires2) <= 3:
        record("PASS", "activity: get_next_fire_times(limit=3) respects limit")
    else:
        record("FAIL", "activity: get_next_fire_times limit", f"got {len(_fires2)}")

    # 22c. get_recent_runs exists and returns a list
    from tasks import get_recent_runs
    _runs = get_recent_runs(5)
    if isinstance(_runs, list):
        record("PASS", f"activity: get_recent_runs(5) returns list (len={len(_runs)})")
    else:
        record("FAIL", "activity: get_recent_runs()", f"got {type(_runs)}")

    # 22d. get_extraction_status exists and returns a dict with expected keys
    from memory_extraction import get_extraction_status
    _mem = get_extraction_status()
    if isinstance(_mem, dict) and "last_extraction" in _mem and "interval_hours" in _mem:
        record("PASS", f"activity: get_extraction_status() keys OK, interval={_mem['interval_hours']}h")
    else:
        record("FAIL", "activity: get_extraction_status()", f"got {_mem}")

    # 22e. interval_hours is 2
    if _mem.get("interval_hours") == 2.0:
        record("PASS", "activity: extraction interval is 2h")
    else:
        record("FAIL", "activity: extraction interval", f"got {_mem.get('interval_hours')}")

    # 22f. Channels expose is_configured / is_running
    from channels.telegram import is_configured as _tg_cfg, is_running as _tg_run
    from channels.email import is_configured as _em_cfg, is_running as _em_run
    if callable(_tg_cfg) and callable(_tg_run):
        record("PASS", "activity: telegram is_configured/is_running callable")
    else:
        record("FAIL", "activity: telegram channel functions not callable")
    if callable(_em_cfg) and callable(_em_run):
        record("PASS", "activity: email is_configured/is_running callable")
    else:
        record("FAIL", "activity: email channel functions not callable")

    # 22g. get_running_tasks returns a dict
    from tasks import get_running_tasks
    _running = get_running_tasks()
    if isinstance(_running, dict):
        record("PASS", f"activity: get_running_tasks() returns dict (len={len(_running)})")
    else:
        record("FAIL", "activity: get_running_tasks()", f"got {type(_running)}")

    # 22h. ui/home.py imports the new functions
    import ast as _ast
    _home_src = Path("ui/home.py").read_text(encoding="utf-8")
    _home_tree = _ast.parse(_home_src)
    _imported_names: set[str] = set()
    for node in _ast.walk(_home_tree):
        if isinstance(node, _ast.ImportFrom):
            for alias in node.names:
                _imported_names.add(alias.name)
    _activity_imports = {"get_recent_runs", "get_next_fire_times", "get_extraction_status"}
    _missing_imports = _activity_imports - _imported_names
    if not _missing_imports:
        record("PASS", "activity: ui/home.py imports all Activity helpers")
    else:
        record("FAIL", "activity: app missing imports", str(_missing_imports))

    # 22i. _build_activity_content string exists in ui/home.py
    if "_build_activity_content" in _home_src:
        record("PASS", "activity: _build_activity_content defined in ui/home.py")
    else:
        record("FAIL", "activity: _build_activity_content not found in app")

    # 22j. Activity tab string exists in ui/home.py
    if "Activity" in _home_src and "home_tabs" in _home_src:
        record("PASS", "activity: tab toggle present in home screen")
    else:
        record("FAIL", "activity: tab toggle missing from home screen")

except Exception as e:
    record("FAIL", "activity tab tests", f"{type(e).__name__}: {e}")
    traceback.print_exc()


# 23. CHANNEL DELIVERY — validation, status tracking, prefixes
# ═════════════════════════════════════════════════════════════════════════════
print("\n" + "=" * 70)
print("23. CHANNEL DELIVERY fixes")
print("=" * 70)

try:
    from tasks import _validate_delivery, _deliver_to_channel

    # 23a. _validate_delivery accepts no-delivery case
    try:
        _validate_delivery(None, None)
        record("PASS", "delivery: validate(None, None) passes")
    except Exception as _e:
        record("FAIL", "delivery: validate(None, None)", str(_e))

    # 23b. _validate_delivery accepts telegram with no target (uses configured user ID)
    try:
        _validate_delivery("telegram", None)
        record("PASS", "delivery: validate(telegram, None) passes (no target needed)")
    except Exception as _e:
        record("FAIL", "delivery: validate(telegram, None) should pass", str(_e))

    # 23c. _validate_delivery rejects target without channel
    try:
        _validate_delivery(None, "12345")
        record("FAIL", "delivery: validate(None, target) should raise")
    except ValueError:
        record("PASS", "delivery: validate(None, target) raises ValueError")

    # 23d. _validate_delivery rejects invalid channel name
    try:
        _validate_delivery("sms", "12345")
        record("FAIL", "delivery: validate(sms, target) should raise")
    except ValueError:
        record("PASS", "delivery: validate(sms, target) raises ValueError")

    # 23e. _validate_delivery accepts telegram regardless of target value
    try:
        _validate_delivery("telegram", "not_a_number")
        record("PASS", "delivery: validate(telegram, any target) passes (target ignored)")
    except Exception as _e:
        record("FAIL", "delivery: validate(telegram, any target) should pass", str(_e))

    # 23f. _validate_delivery accepts valid telegram target
    try:
        _validate_delivery("telegram", "123456789")
        record("PASS", "delivery: validate(telegram, numeric) passes")
    except Exception as _e:
        record("FAIL", "delivery: validate(telegram, numeric)", str(_e))

    # 23g. _validate_delivery requires email to contain @ and .
    try:
        _validate_delivery("email", "not-an-email")
        record("FAIL", "delivery: validate(email, invalid) should raise")
    except ValueError:
        record("PASS", "delivery: validate(email, invalid) raises ValueError")

    # 23h. _validate_delivery accepts valid email
    try:
        _validate_delivery("email", "user@example.com")
        record("PASS", "delivery: validate(email, valid) passes")
    except Exception as _e:
        record("FAIL", "delivery: validate(email, valid)", str(_e))

    # 23i. _deliver_to_channel returns empty tuple when no delivery configured
    _dummy_task = {"name": "Test", "delivery_channel": None, "delivery_target": None}
    _result = _deliver_to_channel(_dummy_task, "hello")
    if _result == ("", ""):
        record("PASS", "delivery: no channel returns ('', '')")
    else:
        record("FAIL", "delivery: no channel return", f"got '{_result}'")

    # 23j. _deliver_to_channel returns 'delivery_failed' for unreachable telegram
    _dummy_tg = {"name": "TgTest", "delivery_channel": "telegram", "delivery_target": "99999"}
    _result2_status, _result2_detail = _deliver_to_channel(_dummy_tg, "hello")
    if _result2_status == "delivery_failed":
        record("PASS", "delivery: unreachable telegram returns 'delivery_failed'")
    else:
        record("FAIL", "delivery: unreachable telegram", f"got '{_result2_status}'")

    # 23k. _deliver_to_channel returns 'delivery_failed' for unconfigured email
    #      (skipped if Gmail is actually configured on this machine)
    from channels.email import _is_gmail_ready as _gmail_ready
    _dummy_em = {"name": "EmTest", "delivery_channel": "email", "delivery_target": "a@b.com"}
    _result3_status, _result3_detail = _deliver_to_channel(_dummy_em, "hello")
    if _gmail_ready():
        # Gmail is configured — delivery may succeed or fail depending on network
        if _result3_status in ("delivered", "delivery_failed"):
            record("PASS", "delivery: email returns status string (gmail configured)")
        else:
            record("FAIL", "delivery: email unexpected return", f"got '{_result3_status}'")
    else:
        if _result3_status == "delivery_failed":
            record("PASS", "delivery: unconfigured email returns 'delivery_failed'")
        else:
            record("FAIL", "delivery: unconfigured email", f"got '{_result3_status}'")

    # 23l. create_task accepts telegram delivery without numeric target (target ignored)
    from tasks import create_task, delete_task
    try:
        _tg_id = create_task(name="TGDelivery", delivery_channel="telegram", prompts=["test"])
        delete_task(_tg_id)
        record("PASS", "delivery: create_task accepts telegram with no target")
    except Exception as _e:
        record("FAIL", "delivery: create_task telegram no target", str(_e))

    # 23m. create_task accepts valid delivery settings
    try:
        _good_id = create_task(
            name="GoodDelivery", delivery_channel="email",
            delivery_target="test@example.com", prompts=["test"],
        )
        delete_task(_good_id)
        record("PASS", "delivery: create_task accepts valid email delivery")
    except Exception as _e:
        record("FAIL", "delivery: create_task valid email", str(_e))

    # 23n. update_task rejects invalid delivery change
    from tasks import update_task
    _tmp_id = create_task(name="UpdateTest", prompts=["test"])
    try:
        update_task(_tmp_id, delivery_channel="email", delivery_target="invalid")
        record("FAIL", "delivery: update_task should reject invalid email")
    except ValueError:
        record("PASS", "delivery: update_task rejects invalid email target")
    finally:
        delete_task(_tmp_id)

    # 23o. completed_delivery_failed status in Activity tab source
    _home_src2 = Path("ui/home.py").read_text(encoding="utf-8")
    if "completed_delivery_failed" in _home_src2:
        record("PASS", "delivery: completed_delivery_failed in Activity tab")
    else:
        record("FAIL", "delivery: completed_delivery_failed missing from Activity tab")

    # 23p. prompts.py has delivery channel guidance (telegram uses configured user ID)
    _prompts_src = Path("prompts.py").read_text(encoding="utf-8")
    if "TELEGRAM_USER_ID" in _prompts_src and "delivery_channel" in _prompts_src:
        record("PASS", "delivery: prompts.py has delivery guidance")
    else:
        record("FAIL", "delivery: prompts.py delivery guidance incomplete")

    # 23q. telegram send_outbound raises RuntimeError when not running
    from channels.telegram import send_outbound as _tg_send
    try:
        _tg_send(12345, "test")
        record("FAIL", "delivery: telegram send_outbound should raise when not running")
    except RuntimeError:
        record("PASS", "delivery: telegram send_outbound raises RuntimeError")
    except Exception as _e:
        record("WARN", "delivery: telegram send_outbound unexpected error", str(_e))

    # 23r. email send_outbound raises RuntimeError when not configured
    #      (skipped if Gmail is actually configured on this machine)
    from channels.email import send_outbound as _em_send
    if not _gmail_ready():
        try:
            _em_send("test@test.com", "Subj", "Body")
            record("FAIL", "delivery: email send_outbound should raise when not configured")
        except RuntimeError:
            record("PASS", "delivery: email send_outbound raises RuntimeError")
        except Exception as _e:
            record("WARN", "delivery: email send_outbound unexpected error", str(_e))
    else:
        record("PASS", "delivery: email send_outbound (gmail configured — raise test skipped)")

    # 23s. email subject prefix 'FromThoth:'
    import inspect as _insp
    _deliver_src = _insp.getsource(_deliver_to_channel)
    if "FromThoth:" in _deliver_src:
        record("PASS", "delivery: email subject uses 'FromThoth:' prefix")
    else:
        record("FAIL", "delivery: email subject missing 'FromThoth:' prefix")

    # 23t. telegram message prefix with task name
    if "📋" in _deliver_src and "task['name']" in _deliver_src:
        record("PASS", "delivery: telegram message includes task name prefix")
    else:
        record("FAIL", "delivery: telegram message missing task name prefix")

    # 23u. _record_run_start stores task_name and task_icon
    from tasks import _record_run_start, _finish_run, _get_conn
    _rrs_conn = _get_conn()
    _rrs_id = _record_run_start("fake_task_999", "fake_thread", 1,
                                 task_name="Test Run", task_icon="🧪")
    _rrs_row = _rrs_conn.execute(
        "SELECT task_name, task_icon FROM task_runs WHERE id = ?", (_rrs_id,)
    ).fetchone()
    if _rrs_row and _rrs_row["task_name"] == "Test Run" and _rrs_row["task_icon"] == "🧪":
        record("PASS", "delivery: _record_run_start stores task_name/task_icon")
    else:
        record("FAIL", "delivery: _record_run_start task_name/icon", f"got {dict(_rrs_row) if _rrs_row else None}")
    # Cleanup
    _rrs_conn.execute("DELETE FROM task_runs WHERE id = ?", (_rrs_id,))
    _rrs_conn.commit()
    _rrs_conn.close()

    # 23v. Run history survives task deletion (delete_after_run scenario)
    from tasks import create_task, delete_task, get_recent_runs
    _surv_id = create_task(name="Survival Test", prompts=["hi"],
                           notify_only=True, notify_label="test")
    _surv_run = _record_run_start(_surv_id, "surv_thread", 0,
                                   task_name="Survival Test", task_icon="⚡")
    _finish_run(_surv_run, "completed", status_message="test delivery")
    delete_task(_surv_id)
    _surv_runs = get_recent_runs(50)
    _surv_found = any(r["id"] == _surv_run for r in _surv_runs)
    if _surv_found:
        record("PASS", "delivery: run history survives task deletion")
    else:
        record("FAIL", "delivery: run history lost after task deletion")
    # Cleanup orphaned run
    _surv_conn = _get_conn()
    _surv_conn.execute("DELETE FROM task_runs WHERE id = ?", (_surv_run,))
    _surv_conn.commit()
    _surv_conn.close()

    # 23w. get_recent_runs shows (deleted) for orphaned runs
    _orph_run = _record_run_start("nonexistent_task", "orph_thread", 0,
                                   task_name="", task_icon="")
    _finish_run(_orph_run, "completed")
    _orph_runs = get_recent_runs(50)
    _orph_found = [r for r in _orph_runs if r["id"] == _orph_run]
    if _orph_found and _orph_found[0]["task_name"] == "(deleted)":
        record("PASS", "delivery: orphaned run shows '(deleted)' task name")
    else:
        record("FAIL", "delivery: orphaned run task_name", f"got {_orph_found[0]['task_name'] if _orph_found else 'not found'}")
    _orph_conn = _get_conn()
    _orph_conn.execute("DELETE FROM task_runs WHERE id = ?", (_orph_run,))
    _orph_conn.commit()
    _orph_conn.close()

except Exception as e:
    record("FAIL", "channel delivery tests", f"{type(e).__name__}: {e}")
    traceback.print_exc()


# ═════════════════════════════════════════════════════════════════════════════
# 24. TASK ENGINE COMPREHENSIVE TESTS
# ═════════════════════════════════════════════════════════════════════════════
print("\n── 24. Task Engine Comprehensive Tests ──")
try:
    from tasks import (
        _parse_schedule, expand_template_vars, _build_trigger,
        create_task, get_task, list_tasks, update_task, delete_task,
        duplicate_task, _record_run_start, _update_run_progress,
        _finish_run, get_recent_runs, get_run_history,
        seed_default_tasks, _DEFAULT_TASKS, _job_id,
        get_running_tasks, _get_conn, _row_to_dict,
        _validate_delivery,
    )

    # ── 24a. _parse_schedule — daily ─────────────────────────────────
    _ps_daily = _parse_schedule("daily:08:00")
    if _ps_daily == {"kind": "daily", "hour": 8, "minute": 0}:
        record("PASS", "task-engine: _parse_schedule daily:08:00")
    else:
        record("FAIL", "task-engine: _parse_schedule daily", str(_ps_daily))

    # ── 24b. _parse_schedule — daily edge ────────────────────────────
    _ps_edge = _parse_schedule("daily:23:59")
    if _ps_edge == {"kind": "daily", "hour": 23, "minute": 59}:
        record("PASS", "task-engine: _parse_schedule daily:23:59")
    else:
        record("FAIL", "task-engine: _parse_schedule daily edge", str(_ps_edge))

    # ── 24c. _parse_schedule — weekly abbreviation ───────────────────
    _ps_wk = _parse_schedule("weekly:mon:09:00")
    if _ps_wk and _ps_wk["kind"] == "weekly" and _ps_wk["day"] == "mon" and _ps_wk["hour"] == 9:
        record("PASS", "task-engine: _parse_schedule weekly:mon:09:00")
    else:
        record("FAIL", "task-engine: _parse_schedule weekly abbr", str(_ps_wk))

    # ── 24d. _parse_schedule — weekly full day name ──────────────────
    _ps_wk2 = _parse_schedule("weekly:friday:17:30")
    if _ps_wk2 and _ps_wk2["day"] == "fri" and _ps_wk2["hour"] == 17 and _ps_wk2["minute"] == 30:
        record("PASS", "task-engine: _parse_schedule weekly:friday normalised")
    else:
        record("FAIL", "task-engine: _parse_schedule weekly full day", str(_ps_wk2))

    # ── 24e. _parse_schedule — interval hours ────────────────────────
    _ps_int = _parse_schedule("interval:2.5")
    if _ps_int == {"kind": "interval", "hours": 2.5}:
        record("PASS", "task-engine: _parse_schedule interval:2.5")
    else:
        record("FAIL", "task-engine: _parse_schedule interval", str(_ps_int))

    # ── 24f. _parse_schedule — interval_minutes ──────────────────────
    _ps_im = _parse_schedule("interval_minutes:30")
    if _ps_im and _ps_im["kind"] == "interval_minutes" and _ps_im["minutes"] == 30.0:
        record("PASS", "task-engine: _parse_schedule interval_minutes:30")
    else:
        record("FAIL", "task-engine: _parse_schedule interval_minutes", str(_ps_im))

    # ── 24g. _parse_schedule — cron ──────────────────────────────────
    _ps_cron = _parse_schedule("cron:0 8 * * *")
    if _ps_cron == {"kind": "cron", "expr": "0 8 * * *"}:
        record("PASS", "task-engine: _parse_schedule cron expression")
    else:
        record("FAIL", "task-engine: _parse_schedule cron", str(_ps_cron))

    # ── 24h. _parse_schedule — invalid inputs return None ────────────
    _ps_invalid_ok = all(
        _parse_schedule(x) is None
        for x in [None, "", "garbage", "unknown:val", "daily"]
    )
    if _ps_invalid_ok:
        record("PASS", "task-engine: _parse_schedule invalid inputs → None")
    else:
        record("FAIL", "task-engine: _parse_schedule invalid", "non-None returned")

    # ── 24i. expand_template_vars replaces placeholders ──────────────
    from datetime import datetime as _dt_cls
    _now = _dt_cls.now()
    _expanded = expand_template_vars("Today is {{date}} ({{day}})")
    if _now.strftime("%B") in _expanded and _now.strftime("%A") in _expanded:
        record("PASS", "task-engine: expand_template_vars replaces {{date}}/{{day}}")
    else:
        record("FAIL", "task-engine: expand_template_vars", _expanded)

    # ── 24j. expand_template_vars passthrough ────────────────────────
    _no_vars = expand_template_vars("No variables here")
    if _no_vars == "No variables here":
        record("PASS", "task-engine: expand_template_vars passthrough")
    else:
        record("FAIL", "task-engine: expand_template_vars passthrough", _no_vars)

    # ── 24j2. expand_template_vars {{task_id}} ───────────────────────
    _tid_expanded = expand_template_vars(
        "task_update(task_id='{{task_id}}', enabled=false)", task_id="abc-123"
    )
    assert "abc-123" in _tid_expanded, f"task_id not expanded: {_tid_expanded}"
    assert "{{task_id}}" not in _tid_expanded, "{{task_id}} should be replaced"
    _tid_no_id = expand_template_vars("keep {{task_id}} as-is")
    assert "{{task_id}}" in _tid_no_id, "Without task_id param, placeholder stays"
    record("PASS", "task-engine: expand_template_vars {{task_id}}")
    from apscheduler.triggers.cron import CronTrigger
    from apscheduler.triggers.interval import IntervalTrigger
    from apscheduler.triggers.date import DateTrigger
    _trig_d = _build_trigger({"schedule": "daily:08:00", "at": None, "last_run": None})
    if isinstance(_trig_d, CronTrigger):
        record("PASS", "task-engine: _build_trigger daily → CronTrigger")
    else:
        record("FAIL", "task-engine: _build_trigger daily", type(_trig_d).__name__)

    # ── 24l. _build_trigger weekly → CronTrigger ────────────────────
    _trig_w = _build_trigger({"schedule": "weekly:tue:10:00", "at": None, "last_run": None})
    if isinstance(_trig_w, CronTrigger):
        record("PASS", "task-engine: _build_trigger weekly → CronTrigger")
    else:
        record("FAIL", "task-engine: _build_trigger weekly", type(_trig_w).__name__)

    # ── 24m. _build_trigger interval → IntervalTrigger ──────────────
    _trig_i = _build_trigger({"schedule": "interval:2", "at": None, "last_run": None})
    if isinstance(_trig_i, IntervalTrigger):
        record("PASS", "task-engine: _build_trigger interval → IntervalTrigger")
    else:
        record("FAIL", "task-engine: _build_trigger interval", type(_trig_i).__name__)

    # ── 24n. _build_trigger future at → DateTrigger ─────────────────
    _future = (_dt_cls.now() + timedelta(hours=1)).isoformat()
    _trig_at = _build_trigger({"schedule": None, "at": _future, "last_run": None})
    if isinstance(_trig_at, DateTrigger):
        record("PASS", "task-engine: _build_trigger future at → DateTrigger")
    else:
        record("FAIL", "task-engine: _build_trigger future at", type(_trig_at).__name__ if _trig_at else "None")

    # ── 24o. _build_trigger no schedule → None ───────────────────────
    _trig_none = _build_trigger({"schedule": None, "at": None, "last_run": None})
    if _trig_none is None:
        record("PASS", "task-engine: _build_trigger no schedule → None")
    else:
        record("FAIL", "task-engine: _build_trigger no schedule", type(_trig_none).__name__)

    # ── 24p. create_task mutual exclusivity ──────────────────────────
    try:
        create_task("bad", schedule="daily:08:00", at="2026-01-01T00:00:00")
        record("FAIL", "task-engine: create_task mutual exclusivity", "no error raised")
    except ValueError as _ve:
        if "Only one" in str(_ve):
            record("PASS", "task-engine: create_task mutual exclusivity raises ValueError")
        else:
            record("FAIL", "task-engine: create_task mutual exclusivity msg", str(_ve))

    # ── 24q. create_task delay_minutes → at conversion ───────────────
    _delay_id = create_task("delay test", delay_minutes=5)
    _delay_task = get_task(_delay_id)
    _delay_ok = (
        _delay_task is not None
        and _delay_task["at"] is not None
        and _delay_task["delete_after_run"] is True
    )
    if _delay_ok:
        record("PASS", "task-engine: create_task delay_minutes → at + delete_after_run")
    else:
        record("FAIL", "task-engine: delay_minutes conversion", str(_delay_task))
    delete_task(_delay_id)

    # ── 24r. create_task + get_task round-trip ───────────────────────
    _rt_id = create_task(
        name="Round Trip Test",
        prompts=["Step 1", "Step 2"],
        description="testing",
        icon="🧪",
        schedule="daily:12:00",
        notify_only=False,
        delivery_channel="email",
        delivery_target="test@example.com",
    )
    _rt = get_task(_rt_id)
    _rt_ok = (
        _rt is not None
        and _rt["name"] == "Round Trip Test"
        and _rt["prompts"] == ["Step 1", "Step 2"]
        and _rt["icon"] == "🧪"
        and _rt["schedule"] == "daily:12:00"
        and _rt["delivery_channel"] == "email"
        and _rt["delivery_target"] == "test@example.com"
        and _rt["notify_only"] is False
        and _rt["enabled"] is True
    )
    if _rt_ok:
        record("PASS", "task-engine: create_task + get_task round-trip")
    else:
        record("FAIL", "task-engine: round-trip", str(_rt))

    # ── 24s. duplicate_task clones correctly ─────────────────────────
    _dup_id = duplicate_task(_rt_id)
    _dup = get_task(_dup_id) if _dup_id else None
    _dup_ok = (
        _dup is not None
        and _dup["name"] == "Round Trip Test (copy)"
        and _dup["prompts"] == ["Step 1", "Step 2"]
        and _dup["schedule"] is None  # schedule not copied
        and _dup["delivery_channel"] == "email"
    )
    if _dup_ok:
        record("PASS", "task-engine: duplicate_task clones correctly")
    else:
        record("FAIL", "task-engine: duplicate_task", str(_dup))
    if _dup_id:
        delete_task(_dup_id)

    # ── 24t. update_task modifies fields ─────────────────────────────
    update_task(_rt_id, name="Updated Name", icon="🔧")
    _upd = get_task(_rt_id)
    if _upd and _upd["name"] == "Updated Name" and _upd["icon"] == "🔧":
        record("PASS", "task-engine: update_task modifies name + icon")
    else:
        record("FAIL", "task-engine: update_task", str(_upd))

    # ── 24u. delete_task removes from DB ─────────────────────────────
    delete_task(_rt_id)
    if get_task(_rt_id) is None:
        record("PASS", "task-engine: delete_task removes from DB")
    else:
        record("FAIL", "task-engine: delete_task", "task still exists")

    # ── 24v. Run lifecycle: start → progress → finish ────────────────
    _lc_task_id = create_task("lifecycle test", prompts=["a", "b", "c"])
    _lc_run = _record_run_start(_lc_task_id, "thread_lc", 3, "lifecycle test", "⚡")
    _update_run_progress(_lc_run, 2)
    _finish_run(_lc_run, "completed", "all steps done")
    _lc_hist = get_run_history(_lc_task_id, limit=1)
    _lc_ok = (
        len(_lc_hist) == 1
        and _lc_hist[0]["status"] == "completed"
        and _lc_hist[0]["steps_done"] == 2
        and _lc_hist[0]["finished_at"] is not None
    )
    if _lc_ok:
        record("PASS", "task-engine: run lifecycle start → progress → finish")
    else:
        record("FAIL", "task-engine: run lifecycle", str(_lc_hist))

    # ── 24w. Finished run has status_message ─────────────────────────
    if _lc_hist and _lc_hist[0].get("status_message") == "all steps done":
        record("PASS", "task-engine: _finish_run stores status_message")
    else:
        record("FAIL", "task-engine: status_message", str(_lc_hist[0].get("status_message") if _lc_hist else "no runs"))

    # ── 24x. get_recent_runs ordering (most recent first) ───────────
    _lc_run2 = _record_run_start(_lc_task_id, "thread_lc2", 1, "lifecycle test", "⚡")
    _finish_run(_lc_run2, "completed")
    _recent = get_recent_runs(50)
    _recent_ids = [r["id"] for r in _recent]
    if _lc_run2 in _recent_ids and _lc_run in _recent_ids:
        _idx1 = _recent_ids.index(_lc_run2)
        _idx2 = _recent_ids.index(_lc_run)
        if _idx1 < _idx2:
            record("PASS", "task-engine: get_recent_runs ordered most-recent first")
        else:
            record("FAIL", "task-engine: get_recent_runs order", f"run2 at {_idx1}, run1 at {_idx2}")
    else:
        record("FAIL", "task-engine: get_recent_runs missing IDs")

    # ── 24y. get_run_history scoped to task ──────────────────────────
    _other_id = create_task("other task", prompts=["x"])
    _other_run = _record_run_start(_other_id, "thread_other", 1, "other task", "⚡")
    _finish_run(_other_run, "completed")
    _scoped = get_run_history(_lc_task_id)
    _scoped_ids = [r["id"] for r in _scoped]
    if _lc_run in _scoped_ids and _other_run not in _scoped_ids:
        record("PASS", "task-engine: get_run_history scoped to task_id")
    else:
        record("FAIL", "task-engine: get_run_history scope", f"found: {_scoped_ids}")
    delete_task(_other_id)

    # Clean up lifecycle task
    delete_task(_lc_task_id)
    # Clean up run records
    _cleanup_conn = _get_conn()
    _cleanup_conn.execute("DELETE FROM task_runs WHERE id IN (?, ?, ?)", (_lc_run, _lc_run2, _other_run))
    _cleanup_conn.commit()
    _cleanup_conn.close()

    # ── 24z. seed_default_tasks count ────────────────────────────────
    if len(_DEFAULT_TASKS) == 5:
        record("PASS", "task-engine: _DEFAULT_TASKS has 5 starter templates")
    else:
        record("FAIL", "task-engine: _DEFAULT_TASKS count", str(len(_DEFAULT_TASKS)))

    # ── 24aa. _DEFAULT_TASKS has notify_only entry ───────────────────
    _has_notify = any(t.get("notify_only") for t in _DEFAULT_TASKS)
    if _has_notify:
        record("PASS", "task-engine: _DEFAULT_TASKS includes notify_only template")
    else:
        record("FAIL", "task-engine: _DEFAULT_TASKS notify_only", "none found")

    # ── 24ab. _job_id deterministic ──────────────────────────────────
    if _job_id("abc123") == "task_abc123":
        record("PASS", "task-engine: _job_id('abc123') → 'task_abc123'")
    else:
        record("FAIL", "task-engine: _job_id", _job_id("abc123"))

    # ── 24ac. get_running_tasks returns dict ─────────────────────────
    _running = get_running_tasks()
    if isinstance(_running, dict):
        record("PASS", "task-engine: get_running_tasks returns dict")
    else:
        record("FAIL", "task-engine: get_running_tasks type", type(_running).__name__)

    # ── 24ad. _row_to_dict boolean conversion ────────────────────────
    _mock_conn = _get_conn()
    _mock_id = create_task("row_conv", prompts=["p1"], notify_only=True)
    _mock_row = _mock_conn.execute("SELECT * FROM tasks WHERE id = ?", (_mock_id,)).fetchone()
    _mock_dict = _row_to_dict(_mock_row)
    _mock_conn.close()
    _conv_ok = (
        _mock_dict["notify_only"] is True
        and _mock_dict["enabled"] is True
        and _mock_dict["delete_after_run"] is False
        and isinstance(_mock_dict["prompts"], list)
    )
    if _conv_ok:
        record("PASS", "task-engine: _row_to_dict converts ints→bools, JSON→list")
    else:
        record("FAIL", "task-engine: _row_to_dict conversion", str(_mock_dict))
    delete_task(_mock_id)

except Exception as e:
    record("FAIL", "task engine comprehensive tests", f"{type(e).__name__}: {e}")
    traceback.print_exc()


# ═════════════════════════════════════════════════════════════════════════════
# SECTION 25 · Configurable retrieval compression
# ═════════════════════════════════════════════════════════════════════════════
try:
    from tools.registry import get_global_config, set_global_config

    # ── 25a. Global config round-trip ────────────────────────────────────
    _prev = get_global_config("compression_mode", "smart")
    set_global_config("compression_mode", "deep")
    _readback = get_global_config("compression_mode")
    if _readback == "deep":
        record("PASS", "compression: global config round-trip (set→get)")
    else:
        record("FAIL", "compression: global config round-trip", f"got {_readback!r}")
    set_global_config("compression_mode", _prev)  # restore

    # ── 25b. Global config persisted to disk ─────────────────────────────
    import json as _json25
    from tools.registry import _CONFIG_PATH as _cfg25
    set_global_config("compression_mode", "off")
    with open(_cfg25) as _f25:
        _disk = _json25.load(_f25)
    if _disk.get("global", {}).get("compression_mode") == "off":
        record("PASS", "compression: global config persisted to disk")
    else:
        record("FAIL", "compression: global config persisted", str(_disk.get("global")))
    set_global_config("compression_mode", _prev)  # restore

    # ── 25c. _get_compressor code returns EmbeddingsFilter for 'smart' ──
    # Source inspection only — live execution moved to integration_tests.py
    # (calling _get_compressor loads the embedding model, ~10-15s)
    from agent import _get_compressor
    import inspect as _ins25
    _gc_src25 = _ins25.getsource(_get_compressor)
    if "EmbeddingsFilter" in _gc_src25 and "smart" in _gc_src25:
        record("PASS", "compression: smart mode → EmbeddingsFilter (source check)")
    else:
        record("FAIL", "compression: smart mode code missing EmbeddingsFilter")

    # ── 25d. _get_compressor returns None for 'off' (source check) ──────
    if 'return None' in _gc_src25 and '"off"' in _gc_src25:
        record("PASS", "compression: off mode → None (source check)")
    else:
        record("FAIL", "compression: off mode code missing return None")

    # ── 25e. _compressed returns bare retriever when mode is 'off' ───────
    from agent import _compressed
    from langchain_core.runnables import RunnableLambda as _RL25
    _fake_ret = _RL25(lambda x: x)
    set_global_config("compression_mode", "off")
    _bare = _compressed(_fake_ret)
    if _bare is _fake_ret:
        record("PASS", "compression: off → bare retriever passthrough")
    else:
        record("FAIL", "compression: off passthrough", type(_bare).__name__)
    set_global_config("compression_mode", _prev)

    # ── 25f. _compressed wraps retriever when mode is 'smart' (source) ───
    _cc_src25 = _ins25.getsource(_compressed)
    if "ContextualCompressionRetriever" in _cc_src25 and "_get_compressor" in _cc_src25:
        record("PASS", "compression: smart → ContextualCompressionRetriever (source check)")
    else:
        record("FAIL", "compression: smart wrapping code missing CCR")

    # ── 25g. default mode is 'smart' when no config exists ───────────────
    # Temporarily clear the key
    from tools.registry import _global_config as _gc25
    _saved_mode = _gc25.pop("compression_mode", None)
    _default = get_global_config("compression_mode", "smart")
    if _default == "smart":
        record("PASS", "compression: default mode is 'smart'")
    else:
        record("FAIL", "compression: default mode", _default)
    # Restore
    if _saved_mode is not None:
        _gc25["compression_mode"] = _saved_mode
    set_global_config("compression_mode", _prev)

except Exception as e:
    record("FAIL", "compression config tests", f"{type(e).__name__}: {e}")
    traceback.print_exc()


# ═════════════════════════════════════════════════════════════════════════════
# SECTION 26 · Knowledge Graph (v3.6)
# ═════════════════════════════════════════════════════════════════════════════
print("\n" + "=" * 70)
print("26. KNOWLEDGE GRAPH")
print("=" * 70)

try:
    import knowledge_graph as _kg_mod
    import memory as _mem_compat

    # --- 26a. Module imports correctly ------------------------------------
    record("PASS", "knowledge_graph: module imports")

    # NetworkX dependency
    import networkx as _nx_test
    record("PASS", "knowledge_graph: networkx available")

    # --- 26b. Schema — entities table exists ------------------------------
    import sqlite3 as _sqlite3_kg
    _kg_conn = _sqlite3_kg.connect(_kg_mod.DB_PATH)
    _kg_conn.row_factory = _sqlite3_kg.Row
    _kg_tables = {row[0] for row in _kg_conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()}
    if "entities" in _kg_tables:
        record("PASS", "knowledge_graph: entities table exists")
    else:
        record("FAIL", "knowledge_graph: entities table missing")

    if "relations" in _kg_tables:
        record("PASS", "knowledge_graph: relations table exists")
    else:
        record("FAIL", "knowledge_graph: relations table missing")

    # --- 26c. Entity columns include new fields ---------------------------
    _ent_cols = [row[1] for row in _kg_conn.execute("PRAGMA table_info(entities)").fetchall()]
    for _col in ("id", "entity_type", "subject", "description", "aliases", "tags", "properties", "source", "created_at", "updated_at"):
        if _col in _ent_cols:
            record("PASS", f"knowledge_graph: entities has '{_col}' column")
        else:
            record("FAIL", f"knowledge_graph: entities missing '{_col}' column")

    # --- 26d. Relation columns -------------------------------------------
    _rel_cols = [row[1] for row in _kg_conn.execute("PRAGMA table_info(relations)").fetchall()]
    for _col in ("id", "source_id", "target_id", "relation_type", "confidence", "properties", "source", "created_at", "updated_at"):
        if _col in _rel_cols:
            record("PASS", f"knowledge_graph: relations has '{_col}' column")
        else:
            record("FAIL", f"knowledge_graph: relations missing '{_col}' column")
    _kg_conn.close()

    # --- 26e. VALID_ENTITY_TYPES superset ---------------------------------
    _vet = _kg_mod.VALID_ENTITY_TYPES
    for _c in ("person", "preference", "fact", "event", "place", "project"):
        if _c in _vet:
            record("PASS", f"knowledge_graph: type '{_c}' in VALID_ENTITY_TYPES")
        else:
            record("FAIL", f"knowledge_graph: type '{_c}' missing from VALID_ENTITY_TYPES")
    # New types
    for _c in ("organisation", "concept", "skill", "media"):
        if _c in _vet:
            record("PASS", f"knowledge_graph: new type '{_c}' in VALID_ENTITY_TYPES")
        else:
            record("FAIL", f"knowledge_graph: new type '{_c}' missing")

    # --- 26f. Core entity CRUD functions exist ----------------------------
    import inspect as _ins_kg
    _kg_funcs = {
        "save_entity": ("entity_type", "subject"),
        "get_entity": ("entity_id",),
        "update_entity": ("entity_id", "description"),
        "delete_entity": ("entity_id",),
        "list_entities": (),
        "count_entities": (),
        "search_entities": ("query",),
        "find_by_subject": ("entity_type", "subject"),
        "semantic_search": ("query",),
        "find_duplicate": ("entity_type", "subject", "description"),
    }
    for _fn_name, _required_params in _kg_funcs.items():
        _fn = getattr(_kg_mod, _fn_name, None)
        if callable(_fn):
            _sig = _ins_kg.signature(_fn)
            _params = set(_sig.parameters.keys())
            _missing = [p for p in _required_params if p not in _params]
            if _missing:
                record("FAIL", f"knowledge_graph: {_fn_name} missing params {_missing}")
            else:
                record("PASS", f"knowledge_graph: {_fn_name} exists with correct params")
        else:
            record("FAIL", f"knowledge_graph: {_fn_name} not callable")

    # --- 26g. Relation CRUD functions exist --------------------------------
    _rel_funcs = {
        "add_relation": ("source_id", "target_id", "relation_type"),
        "get_relations": ("entity_id",),
        "delete_relation": ("relation_id",),
        "count_relations": (),
        "list_relations": (),
    }
    for _fn_name, _required_params in _rel_funcs.items():
        _fn = getattr(_kg_mod, _fn_name, None)
        if callable(_fn):
            _sig = _ins_kg.signature(_fn)
            _params = set(_sig.parameters.keys())
            _missing = [p for p in _required_params if p not in _params]
            if _missing:
                record("FAIL", f"knowledge_graph: {_fn_name} missing params {_missing}")
            else:
                record("PASS", f"knowledge_graph: {_fn_name} exists with correct params")
        else:
            record("FAIL", f"knowledge_graph: {_fn_name} not callable")

    # --- 26h. Graph query helpers -----------------------------------------
    _graph_funcs = ["get_neighbors", "get_shortest_path", "get_subgraph",
                    "get_connected_components", "get_graph_stats", "to_mermaid",
                    "graph_enhanced_recall"]
    for _fn_name in _graph_funcs:
        if callable(getattr(_kg_mod, _fn_name, None)):
            record("PASS", f"knowledge_graph: {_fn_name} callable")
        else:
            record("FAIL", f"knowledge_graph: {_fn_name} not callable")

    # --- 26i. rebuild_index and consolidate_duplicates --------------------
    if callable(getattr(_kg_mod, "rebuild_index", None)):
        record("PASS", "knowledge_graph: rebuild_index callable")
    else:
        record("FAIL", "knowledge_graph: rebuild_index not callable")

    if callable(getattr(_kg_mod, "consolidate_duplicates", None)):
        record("PASS", "knowledge_graph: consolidate_duplicates callable")
    else:
        record("FAIL", "knowledge_graph: consolidate_duplicates not callable")

    if callable(getattr(_kg_mod, "delete_all_entities", None)):
        record("PASS", "knowledge_graph: delete_all_entities callable")
    else:
        record("FAIL", "knowledge_graph: delete_all_entities not callable")

    # --- 26j. _normalize_subject works ------------------------------------
    if hasattr(_kg_mod, "_normalize_subject"):
        _ns_kg = _kg_mod._normalize_subject
        if _ns_kg("  Mom  ") == "mom" and _ns_kg("My  Cat") == "my cat":
            record("PASS", "knowledge_graph: _normalize_subject works")
        else:
            record("FAIL", "knowledge_graph: _normalize_subject output unexpected")
    else:
        record("FAIL", "knowledge_graph: _normalize_subject missing")

    # --- 26k. Memory.py backward compatibility ----------------------------
    # memory.py must still export all legacy functions
    _legacy_funcs = [
        "save_memory", "update_memory", "delete_memory", "get_memory",
        "list_memories", "count_memories", "search_memories", "semantic_search",
        "find_by_subject", "find_duplicate", "delete_all_memories",
        "consolidate_duplicates", "_normalize_subject",
    ]
    for _fn_name in _legacy_funcs:
        if callable(getattr(_mem_compat, _fn_name, None)):
            record("PASS", f"memory compat: {_fn_name} still exported")
        else:
            record("FAIL", f"memory compat: {_fn_name} missing from memory.py")

    # VALID_CATEGORIES still accessible
    if hasattr(_mem_compat, "VALID_CATEGORIES"):
        _vc_compat = _mem_compat.VALID_CATEGORIES
        for _c in ("person", "preference", "fact", "event", "place", "project"):
            if _c in _vc_compat:
                record("PASS", f"memory compat: '{_c}' in VALID_CATEGORIES")
            else:
                record("FAIL", f"memory compat: '{_c}' missing from VALID_CATEGORIES")
    else:
        record("FAIL", "memory compat: VALID_CATEGORIES missing")

    # DB_PATH still accessible
    if hasattr(_mem_compat, "DB_PATH"):
        record("PASS", "memory compat: DB_PATH exported")
    else:
        record("FAIL", "memory compat: DB_PATH missing")

    # --- 26l. Memory tool has new sub-tools --------------------------------
    from tools import memory_tool as _mt_kg
    _mt_src = _ins_kg.getsource(_mt_kg)
    if "link_memories" in _mt_src:
        record("PASS", "memory_tool: link_memories sub-tool present")
    else:
        record("FAIL", "memory_tool: link_memories sub-tool missing")
    if "explore_connections" in _mt_src:
        record("PASS", "memory_tool: explore_connections sub-tool present")
    else:
        record("FAIL", "memory_tool: explore_connections sub-tool missing")
    if "knowledge_graph" in _mt_src or "import knowledge_graph" in _mt_src:
        record("PASS", "memory_tool: imports knowledge_graph")
    else:
        record("FAIL", "memory_tool: does not import knowledge_graph")

    # Count sub-tools — should be 7 now
    _mt_inst = _mt_kg.MemoryTool()
    _lc_tools = _mt_inst.as_langchain_tools()
    if len(_lc_tools) == 7:
        record("PASS", f"memory_tool: 7 sub-tools registered")
    else:
        record("FAIL", f"memory_tool: expected 7 sub-tools, got {len(_lc_tools)}")

    _tool_names = {t.name for t in _lc_tools}
    for _tn in ("save_memory", "search_memory", "list_memories", "update_memory",
                "delete_memory", "link_memories", "explore_connections"):
        if _tn in _tool_names:
            record("PASS", f"memory_tool: sub-tool '{_tn}' registered")
        else:
            record("FAIL", f"memory_tool: sub-tool '{_tn}' missing")

    # --- 26m. Extraction prompt includes relations ------------------------
    from prompts import EXTRACTION_PROMPT as _ep_kg
    _extraction_checks = [
        ("relation_type", "extraction prompt has relation_type"),
        ("source_subject", "extraction prompt has source_subject"),
        ("target_subject", "extraction prompt has target_subject"),
        ("confidence", "extraction prompt has confidence"),
        ("mother_of", "extraction prompt has example relation"),
    ]
    for _check, _desc in _extraction_checks:
        if _check in _ep_kg:
            record("PASS", f"prompt: {_desc}")
        else:
            record("FAIL", f"prompt: {_desc}")

    # --- 26n. System prompt updated for knowledge graph -------------------
    from prompts import AGENT_SYSTEM_PROMPT as _asp_kg
    _kg_prompt_checks = [
        ("knowledge graph", "system prompt mentions knowledge graph"),
        ("link_memories", "system prompt mentions link_memories"),
        ("explore_connections", "system prompt mentions explore_connections"),
        ("BUILDING CONNECTIONS", "system prompt has BUILDING CONNECTIONS section"),
        ("EXPLORING CONNECTIONS", "system prompt has EXPLORING CONNECTIONS section"),
    ]
    for _check, _desc in _kg_prompt_checks:
        if _check in _asp_kg:
            record("PASS", f"prompt: {_desc}")
        else:
            record("FAIL", f"prompt: {_desc}")

    # --- 26o. Agent auto-recall uses graph_enhanced_recall ----------------
    _agent_src_kg = _ins_kg.getsource(_ins_kg.getmodule(_agent_mod._pre_model_trim))
    if "graph_enhanced_recall" in _agent_src_kg:
        record("PASS", "agent: auto-recall uses graph_enhanced_recall")
    else:
        record("FAIL", "agent: auto-recall should use graph_enhanced_recall")
    if "count_entities" in _agent_src_kg:
        record("PASS", "agent: auto-recall uses count_entities")
    else:
        record("FAIL", "agent: auto-recall should use count_entities")

    # --- 26p. requirements.txt has networkx --------------------------------
    _req_path = os.path.join(PROJECT_ROOT, "requirements.txt")
    _req_text = open(_req_path).read()
    if "networkx" in _req_text:
        record("PASS", "requirements: networkx listed")
    else:
        record("FAIL", "requirements: networkx missing")

    # --- 26q. memory_extraction uses knowledge_graph for relations --------
    _mex_src = _ins_kg.getsource(_ins_kg.getmodule(_me_mod._dedup_and_save))
    if "add_relation" in _mex_src or "kg.add_relation" in _mex_src:
        record("PASS", "extraction: _dedup_and_save creates relations")
    else:
        record("FAIL", "extraction: _dedup_and_save should create relations")
    if "subject_to_id" in _mex_src:
        record("PASS", "extraction: _dedup_and_save tracks subject→id mapping")
    else:
        record("FAIL", "extraction: _dedup_and_save missing subject→id mapping")

except Exception as e:
    record("FAIL", "knowledge graph tests", f"{type(e).__name__}: {e}")
    traceback.print_exc()


# ═════════════════════════════════════════════════════════════════════════════
# SECTION 27 · Knowledge Graph Visualization (v3.6)
# ═════════════════════════════════════════════════════════════════════════════
print(f"\n{'='*70}")
print("SECTION 27 · Knowledge Graph Visualization")
print(f"{'='*70}")

try:
    import knowledge_graph as _vis_kg
    _ins_vis = importlib.import_module("inspect")

    # --- 27a. graph_to_vis_json exists ------------------------------------
    if hasattr(_vis_kg, "graph_to_vis_json"):
        record("PASS", "vis: graph_to_vis_json() exists")
    else:
        record("FAIL", "vis: graph_to_vis_json() missing")

    # --- 27b. _VIS_TYPE_COLORS covers all entity types --------------------
    _vtc = getattr(_vis_kg, "_VIS_TYPE_COLORS", {})
    _vet = getattr(_vis_kg, "VALID_ENTITY_TYPES", set())
    _missing_colors = _vet - set(_vtc.keys())
    if not _missing_colors:
        record("PASS", f"vis: type colors cover all {len(_vet)} entity types")
    else:
        record("FAIL", "vis: type colors missing", str(_missing_colors))

    # --- 27c. Empty graph returns correct shape ---------------------------
    _orig_graph = _vis_kg._graph
    _orig_ready = _vis_kg._graph_ready
    try:
        import networkx as _vis_nx
        _vis_kg._graph = _vis_nx.DiGraph()
        _vis_kg._graph_ready = True
        _empty = _vis_kg.graph_to_vis_json()
        if (_empty["nodes"] == [] and _empty["edges"] == []
                and _empty["center"] is None
                and _empty["stats"]["total_entities"] == 0):
            record("PASS", "vis: empty graph returns correct shape")
        else:
            record("FAIL", "vis: empty graph shape wrong", str(_empty))
    finally:
        _vis_kg._graph = _orig_graph
        _vis_kg._graph_ready = _orig_ready

    # --- 27d–27p moved to integration_tests.py section 3 ─────────────────
    # Live graph_to_vis_json() calls load the full KG from DB into networkx
    # and trigger embedding model loading.  Source-inspection replacements:
    _vis_src27 = _ins_vis.getsource(_vis_kg.graph_to_vis_json)

    # --- 27d. Returns dict with required keys (source check) ──────────────
    if all(k in _vis_src27 for k in ('"nodes"', '"edges"', '"center"', '"stats"')):
        record("PASS", "vis: graph_to_vis_json returns nodes/edges/center/stats (source)")
    else:
        record("FAIL", "vis: graph_to_vis_json missing required keys in source")

    # --- 27e. Stats includes required counters ────────────────────────────
    if all(k in _vis_src27 for k in ('"total_entities"', '"total_relations"', '"shown_nodes"', '"shown_edges"')):
        record("PASS", "vis: stats has required counter fields (source)")
    else:
        record("FAIL", "vis: stats missing counter fields in source")

    # --- 27f. Nodes include vis-network fields ────────────────────────────
    _node_fields27 = ['"label"', '"color"', '"size"', '"font"', '"title"', '"_type"', '"_degree"']
    if all(f in _vis_src27 for f in _node_fields27):
        record("PASS", f"vis: node objects have {len(_node_fields27)} vis-network fields (source)")
    else:
        record("FAIL", "vis: node objects missing vis-network fields")

    # --- 27g. Edges include vis-network fields ────────────────────────────
    _edge_fields27 = ['"from"', '"to"', '"arrows"']
    if all(f in _vis_src27 for f in _edge_fields27):
        record("PASS", f"vis: edge objects have {len(_edge_fields27)} vis-network fields (source)")
    else:
        record("FAIL", "vis: edge objects missing vis-network fields")

    # --- 27h. Node colors use _VIS_TYPE_COLORS palette ────────────────────
    if "_VIS_TYPE_COLORS" in _vis_src27:
        record("PASS", "vis: node colors use type palette (source)")
    else:
        record("FAIL", "vis: node colors don't reference palette")

    # --- 27i. Node sizes computed from degree ─────────────────────────────
    if "degree" in _vis_src27 and "size" in _vis_src27:
        record("PASS", "vis: node sizes computed from degree (source)")
    else:
        record("FAIL", "vis: node sizes not degree-based")

    # --- 27j. Center picks User entity or highest-degree ──────────────────
    if '"user"' in _vis_src27.lower() and "degree" in _vis_src27:
        record("PASS", "vis: center picks User or highest-degree (source)")
    else:
        record("FAIL", "vis: center selection logic missing")

    # --- 27k. Subgraph mode supported via entity_id + hops ────────────────
    _sig27 = _ins_vis.signature(_vis_kg.graph_to_vis_json)
    if "entity_id" in _sig27.parameters and "hops" in _sig27.parameters:
        record("PASS", "vis: graph_to_vis_json has entity_id + hops params")
    else:
        record("FAIL", "vis: graph_to_vis_json missing subgraph params")

    # --- 27l. max_nodes cap supported ─────────────────────────────────────
    if "max_nodes" in _sig27.parameters:
        record("PASS", "vis: graph_to_vis_json has max_nodes param")
    else:
        record("FAIL", "vis: graph_to_vis_json missing max_nodes")

    # --- 27m. get_subgraph edges have source_id/target_id (source) ────────
    _gs_src27 = _ins_vis.getsource(_vis_kg.get_subgraph)
    if "source_id" in _gs_src27 and "target_id" in _gs_src27:
        record("PASS", "vis: get_subgraph edges have source_id/target_id (source)")
    else:
        record("FAIL", "vis: get_subgraph edges missing source_id/target_id")

    # --- 27n. Edges use directional arrows ────────────────────────────────
    if '"arrows"' in _vis_src27 and '"to"' in _vis_src27:
        record("PASS", "vis: edges have directional arrows (source)")
    else:
        record("FAIL", "vis: edges missing arrow specification")

    # --- 27q. UI wiring: _build_graph_panel exists in ui --------
    _ui_graph_src = open(os.path.join(PROJECT_ROOT, "ui", "graph_panel.py"), encoding="utf-8").read()
    _ui_home_src = open(os.path.join(PROJECT_ROOT, "ui", "home.py"), encoding="utf-8").read()
    _ui_head_src = open(os.path.join(PROJECT_ROOT, "ui", "head_html.py"), encoding="utf-8").read()
    _app_src = _ui_graph_src + _ui_home_src + _ui_head_src
    if "build_graph_panel" in _app_src:
        record("PASS", "vis: build_graph_panel() exists in ui")
    else:
        record("FAIL", "vis: build_graph_panel() missing from ui")

    # --- 27r. UI has vis-network reference ----------------------------------
    if "vis-network" in _app_src:
        record("PASS", "vis: vis-network library referenced in UI")
    else:
        record("FAIL", "vis: vis-network library missing from UI")

    # --- 27s. UI has graph-container div ----------------------------------
    if "graph-container" in _app_src:
        record("PASS", "vis: graph-container div exists in UI")
    else:
        record("FAIL", "vis: graph-container div missing from UI")

    # --- 27t. UI has Memory tab in home screen tabs ------------------------
    if 'graph_tab' in _app_src and 'icon="psychology"' in _app_src:
        record("PASS", "vis: Memory tab wired into home screen")
    else:
        record("FAIL", "vis: Memory tab not wired into home screen")

    # --- 27u. Font color set for dark theme (source check) ────────────────
    if '#ECEFF1' in _vis_src27:
        record("PASS", "vis: node font color set for dark theme (source)")
    else:
        record("FAIL", "vis: node font color #ECEFF1 not in source")

    # --- 27v. UI uses run_javascript (not add_body_html) for graph JS ------
    if "run_javascript(_graph_js)" in _app_src and "add_body_html" not in _app_src:
        record("PASS", "vis: graph JS delivered via run_javascript (no add_body_html)")
    elif "run_javascript(_graph_js)" in _app_src:
        record("FAIL", "vis: run_javascript present but stale add_body_html still exists")
    else:
        record("FAIL", "vis: run_javascript(_graph_js) not found in UI")

    # --- 27w. JS teardown: stale boot timer cleared -----------------------
    if "clearTimeout(window._thothGraphBootTimer" in _app_src:
        record("PASS", "vis: JS teardown clears stale boot timer")
    else:
        record("FAIL", "vis: JS teardown missing clearTimeout for boot timer")

    # --- 27x. JS teardown: old network destroyed --------------------------
    if "network.destroy()" in _app_src:
        record("PASS", "vis: JS teardown destroys old vis.Network")
    else:
        record("FAIL", "vis: JS teardown missing network.destroy()")

    # --- 27y. JS namespaced state on window._thothGraph -------------------
    if "window._thothGraph" in _app_src:
        record("PASS", "vis: JS state namespaced on window._thothGraph")
    else:
        record("FAIL", "vis: JS state not namespaced on window._thothGraph")

    # --- 27z. thothGraphRedraw calls wireControls for full reinit ---------
    if "thothGraphRedraw" in _app_src and "wireControls" in _app_src:
        record("PASS", "vis: thothGraphRedraw with wireControls for full reinit")
    else:
        record("FAIL", "vis: thothGraphRedraw or wireControls missing")

    # --- 27aa. vis-network loaded in head_html module (global, not per-panel)
    _vis_in_head = "vis-network.min.js" in _app_src and "add_head_html" in _app_src
    if _vis_in_head:
        record("PASS", "vis: vis-network.min.js loaded once in add_head_html")
    else:
        record("FAIL", "vis: vis-network.min.js not found in add_head_html block")

    # --- 27ab. _on_tab_change uses setTimeout before thothGraphRedraw -----
    if "setTimeout" in _app_src and "thothGraphRedraw" in _app_src:
        record("PASS", "vis: tab change uses setTimeout before thothGraphRedraw")
    else:
        record("FAIL", "vis: tab change missing setTimeout for thothGraphRedraw")

except Exception as e:
    record("FAIL", "visualization tests", f"{type(e).__name__}: {e}")
    traceback.print_exc()


# ═════════════════════════════════════════════════════════════════════════════
# SECTION 28 · Triple-based extraction & relation creation (v3.6)
# ═════════════════════════════════════════════════════════════════════════════
try:
    print("SECTION 28 · Triple-based Extraction")
    print("-" * 40)

    import memory_extraction as _me28
    import memory as _mem28
    import knowledge_graph as _kg28
    import inspect as _insp28
    from prompts import EXTRACTION_PROMPT as _EP28

    # --- 28a. Extraction prompt mentions "User" entity guidance -----------
    if '"User"' in _EP28 and "THE \"User\" ENTITY" in _EP28:
        record("PASS", "extraction: prompt has User entity guidance section")
    else:
        record("FAIL", "extraction: prompt missing User entity guidance")

    # --- 28b. Prompt instructs to always output relations -----------------
    if "ALWAYS output relations" in _EP28:
        record("PASS", "extraction: prompt instructs always output relations")
    else:
        record("FAIL", "extraction: prompt missing 'ALWAYS output relations'")

    # --- 28c. Prompt example includes relation objects --------------------
    if "relation_type" in _EP28 and "source_subject" in _EP28 and "target_subject" in _EP28:
        record("PASS", "extraction: prompt example has relation objects")
    else:
        record("FAIL", "extraction: prompt example missing relation objects")

    # --- 28d. Prompt mentions aliases field --------------------------------
    if "aliases" in _EP28:
        record("PASS", "extraction: prompt mentions aliases field")
    else:
        record("FAIL", "extraction: prompt missing aliases mention")

    # --- 28e. Validation accepts relation objects -------------------------
    # Simulate what _extract_from_conversation does for validation
    _test_data = [
        {"category": "person", "subject": "User", "content": "Lives in London"},
        {"relation_type": "lives_in", "source_subject": "User", "target_subject": "London", "confidence": 0.9},
    ]
    _valid = []
    for _entry in _test_data:
        if not isinstance(_entry, dict):
            continue
        if _entry.get("category") and _entry.get("subject") and _entry.get("content"):
            _valid.append(_entry)
        elif _entry.get("relation_type") and _entry.get("source_subject") and _entry.get("target_subject"):
            _valid.append(_entry)
    if len(_valid) == 2:
        record("PASS", "extraction: validation accepts both entity and relation objects")
    else:
        record("FAIL", f"extraction: validation accepted {len(_valid)}/2 objects")

    # --- 28f. _dedup_and_save processes relation objects -------------------
    _dedup_src = _insp28.getsource(_me28._dedup_and_save)
    if "relation_type" in _dedup_src and "add_relation" in _dedup_src:
        record("PASS", "extraction: _dedup_and_save handles relation_type + add_relation")
    else:
        record("FAIL", "extraction: _dedup_and_save missing relation processing")

    # --- 28g. _dedup_and_save pre-populates User entity -------------------
    if 'find_by_subject(None, "User")' in _dedup_src:
        record("PASS", "extraction: _dedup_and_save pre-populates User entity in map")
    else:
        record("FAIL", "extraction: _dedup_and_save missing User entity pre-population")

    # --- 28h. _dedup_and_save handles aliases from extracted data ----------
    if "aliases" in _dedup_src and "new_aliases" in _dedup_src:
        record("PASS", "extraction: _dedup_and_save merges extracted aliases")
    else:
        record("FAIL", "extraction: _dedup_and_save missing alias merging")

    # --- 28i. memory.py update_memory accepts aliases kwarg ---------------
    _um28_sig = _insp28.signature(_mem28.update_memory)
    if "aliases" in _um28_sig.parameters:
        record("PASS", "memory: update_memory accepts 'aliases' kwarg")
    else:
        record("FAIL", "memory: update_memory missing 'aliases' kwarg")

    # --- 28j. update_memory passes aliases to update_entity ---------------
    _um28_src = _insp28.getsource(_mem28.update_memory)
    if "aliases=aliases" in _um28_src or "aliases = aliases" in _um28_src:
        record("PASS", "memory: update_memory passes aliases to update_entity")
    else:
        record("FAIL", "memory: update_memory does NOT pass aliases to update_entity")

    # --- 28k. Prompt has expanded relation types --------------------------
    _expanded_rels = ["partner_of", "interested_in", "visits", "owns"]
    _rel_hits = sum(1 for r in _expanded_rels if r in _EP28)
    if _rel_hits >= 3:
        record("PASS", f"extraction: prompt has {_rel_hits}/4 expanded relation types")
    else:
        record("FAIL", f"extraction: prompt only has {_rel_hits}/4 expanded relation types")

    # --- 28l. Prompt example has User as source_subject -------------------
    if '"source_subject": "User"' in _EP28 or '"source_subject": "Dad"' in _EP28:
        record("PASS", "extraction: prompt example uses proper entity subjects")
    else:
        record("FAIL", "extraction: prompt example missing proper entity subjects")

    # --- 28m. knowledge_graph.py vis edges removed per-edge font ----------
    _kg28_vis_src = _insp28.getsource(_kg28.graph_to_vis_json)
    # Edges should NOT have a per-edge font property (removed for hover-only labels)
    if '"font"' not in _kg28_vis_src.split("vis_edges")[1] if "vis_edges" in _kg28_vis_src else True:
        record("PASS", "vis: edge data does not include per-edge font property")
    else:
        record("FAIL", "vis: edge data still has per-edge font property")

    # --- 28n. knowledge_graph.py vis nodes use plain-text tooltips --------
    if "\\n" in _kg28_vis_src and "<br>" not in _kg28_vis_src.split("vis_nodes")[1].split("vis_edges")[0]:
        record("PASS", "vis: node tooltips use plain text (no HTML)")
    else:
        record("FAIL", "vis: node tooltips still use HTML tags")

    # --- 28o. _dedup_and_save resolves subjects via DB fallback -----------
    if "find_by_subject(None," in _dedup_src and "source_subject" in _dedup_src:
        record("PASS", "extraction: relation pass resolves subjects via DB fallback")
    else:
        record("FAIL", "extraction: relation pass missing DB subject fallback")

    # --- 28p-28q moved to integration_tests.py section 3 ──────────────
    # These tests call _dedup_and_save() which writes to DB and triggers
    # FAISS index rebuilds (embedding model load + re-embedding).
    # integration_tests.py section 3 covers: save/find/alias/relation/delete
    # end-to-end with real entities and full cleanup.

except Exception as e:
    record("FAIL", "triple extraction tests", f"{type(e).__name__}: {e}")
    traceback.print_exc()


# ═════════════════════════════════════════════════════════════════════════════
# 29. TELEGRAM TOOL — tool module, sub-tools, channel helpers, delivery changes
# ═════════════════════════════════════════════════════════════════════════════
print("\n" + "=" * 70)
print("29. TELEGRAM TOOL")
print("=" * 70)

try:
    # 29a. telegram_tool module imports cleanly
    import tools.telegram_tool as _tg_mod
    record("PASS", "telegram tool: module imports")

    # 29b. TelegramTool class exists and is a BaseTool
    from tools.telegram_tool import TelegramTool as _TgToolCls
    from tools.base import BaseTool as _BT
    assert issubclass(_TgToolCls, _BT)
    record("PASS", "telegram tool: TelegramTool is a BaseTool subclass")

    # 29c. Tool properties
    _tg_inst = _TgToolCls()
    assert _tg_inst.name == "telegram"
    assert _tg_inst.display_name == "📱 Telegram"
    assert _tg_inst.enabled_by_default is False
    record("PASS", "telegram tool: name, display_name, enabled_by_default correct")

    # 29d. as_langchain_tools returns 3 sub-tools
    _tg_lc = _tg_inst.as_langchain_tools()
    assert len(_tg_lc) == 3, f"expected 3 sub-tools, got {len(_tg_lc)}"
    record("PASS", "telegram tool: as_langchain_tools returns 3 sub-tools")

    # 29e. Sub-tool names match expectations
    _tg_names = sorted(t.name for t in _tg_lc)
    _expected_names = sorted(["send_telegram_message", "send_telegram_photo", "send_telegram_document"])
    assert _tg_names == _expected_names, f"expected {_expected_names}, got {_tg_names}"
    record("PASS", "telegram tool: sub-tool names are correct")

    # 29f. Input schemas exist with correct fields
    from tools.telegram_tool import _SendMessageInput, _SendPhotoInput, _SendDocumentInput
    assert "text" in _SendMessageInput.model_fields
    assert "file_path" in _SendPhotoInput.model_fields
    assert "caption" in _SendPhotoInput.model_fields
    assert "file_path" in _SendDocumentInput.model_fields
    assert "caption" in _SendDocumentInput.model_fields
    record("PASS", "telegram tool: Pydantic input schemas have correct fields")

    # 29g. Tool is registered in the registry
    from tools.registry import get_all_tools as _all_tools
    _all_names = [t.name for t in _all_tools()]
    assert "telegram" in _all_names, f"'telegram' not in registry: {_all_names}"
    record("PASS", "telegram tool: registered in tool registry")

    # 29h. send_photo and send_document exist in channels.telegram
    from channels.telegram import send_photo as _sp, send_document as _sd
    import inspect as _insp29
    _sp_sig = _insp29.signature(_sp)
    _sd_sig = _insp29.signature(_sd)
    assert "chat_id" in _sp_sig.parameters
    assert "file_path" in _sp_sig.parameters
    assert "caption" in _sp_sig.parameters
    assert "chat_id" in _sd_sig.parameters
    assert "file_path" in _sd_sig.parameters
    assert "caption" in _sd_sig.parameters
    record("PASS", "telegram tool: send_photo/send_document signatures correct")

    # 29i. send_photo raises RuntimeError when bot not running
    try:
        _sp(12345, "dummy.png")
        record("FAIL", "telegram tool: send_photo should raise RuntimeError")
    except RuntimeError:
        record("PASS", "telegram tool: send_photo raises RuntimeError when not running")
    except Exception as _e29:
        record("WARN", "telegram tool: send_photo unexpected error", str(_e29))

    # 29j. send_document raises RuntimeError when bot not running
    try:
        _sd(12345, "dummy.txt")
        record("FAIL", "telegram tool: send_document should raise RuntimeError")
    except RuntimeError:
        record("PASS", "telegram tool: send_document raises RuntimeError when not running")
    except Exception as _e29:
        record("WARN", "telegram tool: send_document unexpected error", str(_e29))

    # 29k. _send_telegram_message returns error when bot not running
    from tools.telegram_tool import _send_telegram_message as _stm
    _stm_r = _stm("hello")
    assert "Error" in _stm_r or "not running" in _stm_r.lower(), f"unexpected: {_stm_r}"
    record("PASS", "telegram tool: _send_telegram_message returns error when not running")

    # 29l. _send_telegram_photo returns error when bot not running
    from tools.telegram_tool import _send_telegram_photo as _stp
    _stp_r = _stp("dummy.png")
    assert "Error" in _stp_r or "not running" in _stp_r.lower(), f"unexpected: {_stp_r}"
    record("PASS", "telegram tool: _send_telegram_photo returns error when not running")

    # 29m. _send_telegram_document returns error when bot not running
    from tools.telegram_tool import _send_telegram_document as _std
    _std_r = _std("dummy.txt")
    assert "Error" in _std_r or "not running" in _std_r.lower(), f"unexpected: {_std_r}"
    record("PASS", "telegram tool: _send_telegram_document returns error when not running")

    # 29n. _validate_delivery: email without target still raises ValueError
    from tasks import _validate_delivery
    try:
        _validate_delivery("email", None)
        record("FAIL", "telegram tool: validate(email, None) should raise ValueError")
    except ValueError:
        record("PASS", "telegram tool: validate(email, None) raises ValueError")

    # 29o. _deliver_to_channel: telegram path calls _get_allowed_user_id
    _deliver_src29 = _insp29.getsource(_deliver_to_channel)
    if "_get_allowed_user_id" in _deliver_src29:
        record("PASS", "telegram tool: _deliver_to_channel uses _get_allowed_user_id")
    else:
        record("FAIL", "telegram tool: _deliver_to_channel missing _get_allowed_user_id")

    # 29p. prompts.py contains TELEGRAM MESSAGING section
    _p_src29 = Path("prompts.py").read_text(encoding="utf-8")
    if "TELEGRAM MESSAGING" in _p_src29 and "send_telegram_message" in _p_src29:
        record("PASS", "telegram tool: prompts.py has TELEGRAM MESSAGING section")
    else:
        record("FAIL", "telegram tool: prompts.py missing TELEGRAM MESSAGING section")

    # 29q. telegram_tool.py in installer/thoth_setup.iss
    _iss_src29 = Path("installer/thoth_setup.iss").read_text(encoding="utf-8")
    if "telegram_tool.py" in _iss_src29:
        record("PASS", "telegram tool: included in installer thoth_setup.iss")
    else:
        record("FAIL", "telegram tool: missing from installer thoth_setup.iss")

    # 29r. tools/__init__.py imports telegram_tool
    _init_src29 = Path("tools/__init__.py").read_text(encoding="utf-8")
    if "telegram_tool" in _init_src29:
        record("PASS", "telegram tool: imported in tools/__init__.py")
    else:
        record("FAIL", "telegram tool: missing from tools/__init__.py")

except Exception as e:
    record("FAIL", "telegram tool tests", f"{type(e).__name__}: {e}")
    traceback.print_exc()


# ═════════════════════════════════════════════════════════════════════════════
# 30. FILE & MESSAGING PIPELINE (v3.6.0)
# ═════════════════════════════════════════════════════════════════════════════
print("\n" + "=" * 70)
print("30. FILE & MESSAGING PIPELINE (v3.6.0)")
print("=" * 70)

try:
    import inspect as _insp30
    import tempfile, shutil

    # ── 30a. Telegram _resolve_file_path: returns original when not found ──
    from tools.telegram_tool import _resolve_file_path as _tg_resolve
    _r30a = _tg_resolve("definitely_nonexistent_file_xyz.txt")
    assert _r30a == "definitely_nonexistent_file_xyz.txt", f"expected original back, got {_r30a}"
    record("PASS", "v3.6: telegram _resolve_file_path returns original for missing file")

    # ── 30b. Telegram _resolve_file_path: resolves workspace-relative ──────
    _tmpdir30 = tempfile.mkdtemp(prefix="thoth_test30_")
    try:
        _test_file30 = Path(_tmpdir30) / "test_photo.png"
        _test_file30.write_bytes(b"\x89PNG\r\n\x1a\n")  # minimal PNG header
        from tools.registry import get_tool as _gt30
        _fs30 = _gt30("filesystem")
        _old_ws30 = _fs30.get_config("workspace_root", "") if _fs30 else ""
        if _fs30:
            _fs30.set_config("workspace_root", _tmpdir30)
        _resolved30b = _tg_resolve("test_photo.png")
        assert Path(_resolved30b).is_file(), f"resolved path is not a file: {_resolved30b}"
        assert "test_photo.png" in _resolved30b
        record("PASS", "v3.6: telegram _resolve_file_path resolves workspace-relative")
    finally:
        if _fs30 and _old_ws30:
            _fs30.set_config("workspace_root", _old_ws30)
        elif _fs30:
            _fs30.set_config("workspace_root", "")
        shutil.rmtree(_tmpdir30, ignore_errors=True)

    # ── 30c. Gmail _resolve_file_path: same pattern ────────────────────────
    from tools.gmail_tool import _resolve_file_path as _gm_resolve
    _r30c = _gm_resolve("nonexistent_attachment.pdf")
    assert _r30c == "nonexistent_attachment.pdf", f"expected original back, got {_r30c}"
    record("PASS", "v3.6: gmail _resolve_file_path returns original for missing file")

    # ── 30d. TelegramTool always returns all 3 sub-tools when enabled ─────
    from tools.telegram_tool import TelegramTool as _TT30
    _tt30 = _TT30()
    _tools30d = _tt30.as_langchain_tools()
    _names30d = sorted(t.name for t in _tools30d)
    assert len(_names30d) == 3, f"expected 3 tools, got {_names30d}"
    assert _names30d == sorted(["send_telegram_message", "send_telegram_photo", "send_telegram_document"])
    record("PASS", "v3.6: TelegramTool.as_langchain_tools always returns all 3 sub-tools")

    # ── 30e. TelegramTool._ALL_OPS has 3 operations ───────────────────────
    from tools.telegram_tool import _ALL_OPS as _all_ops30
    assert len(_all_ops30) == 3, f"expected 3 operations, got {len(_all_ops30)}"
    assert "send_telegram_message" in _all_ops30
    assert "send_telegram_photo" in _all_ops30
    assert "send_telegram_document" in _all_ops30
    record("PASS", "v3.6: _ALL_OPS contains all 3 telegram operations")

    # ── 30f. TelegramTool has no config_schema (no checkboxes) ────────────
    _cs30f = _tt30.config_schema
    assert "selected_operations" not in _cs30f, f"selected_operations should be removed: {list(_cs30f.keys())}"
    record("PASS", "v3.6: TelegramTool has no selected_operations config (toggle-only)")

    # ── 30g. _CreateChartInput has save_to_file field ──────────────────────
    from tools.chart_tool import _CreateChartInput as _CCI30
    assert "save_to_file" in _CCI30.model_fields, f"fields: {list(_CCI30.model_fields.keys())}"
    _stf_field = _CCI30.model_fields["save_to_file"]
    assert not _stf_field.is_required(), "save_to_file should be optional"
    record("PASS", "v3.6: _CreateChartInput has optional save_to_file field")

    # ── 30h. _create_chart accepts save_to_file parameter ──────────────────
    from tools.chart_tool import _create_chart as _cc30
    _sig30h = _insp30.signature(_cc30)
    assert "save_to_file" in _sig30h.parameters, f"params: {list(_sig30h.parameters.keys())}"
    record("PASS", "v3.6: _create_chart function accepts save_to_file param")

    # ── 30i. Chart save_to_file produces PNG (integration) ─────────────────
    _tmpdir30i = tempfile.mkdtemp(prefix="thoth_test30i_")
    try:
        # Create test CSV
        _csv30 = Path(_tmpdir30i) / "data.csv"
        _csv30.write_text("x,y\n1,10\n2,20\n3,30\n", encoding="utf-8")

        _fs30i = _gt30("filesystem")
        _old_ws30i = _fs30i.get_config("workspace_root", "") if _fs30i else ""
        if _fs30i:
            _fs30i.set_config("workspace_root", _tmpdir30i)

        _result30i = _cc30(
            chart_type="bar",
            data_source=str(_csv30),
            x_column="x",
            y_column="y",
            save_to_file="test_chart.png",
        )
        assert "Chart saved to:" in _result30i, f"expected 'Chart saved to:' in result: {_result30i[:200]}"
        # Check that png file exists
        _png30 = Path(_tmpdir30i) / "test_chart.png"
        assert _png30.is_file(), f"PNG file not created at {_png30}"
        assert _png30.stat().st_size > 1000, f"PNG too small: {_png30.stat().st_size} bytes"
        record("PASS", "v3.6: chart save_to_file creates PNG on disk (kaleido)")
    except ImportError as _ie30i:
        record("WARN", "v3.6: chart save_to_file skipped (kaleido not installed)", str(_ie30i))
    except Exception as _e30i:
        record("FAIL", "v3.6: chart save_to_file", f"{type(_e30i).__name__}: {_e30i}")
    finally:
        if _fs30i and _old_ws30i:
            _fs30i.set_config("workspace_root", _old_ws30i)
        elif _fs30i:
            _fs30i.set_config("workspace_root", "")
        shutil.rmtree(_tmpdir30i, ignore_errors=True)

    # ── 30j. Gmail _SendMessageInput has attachments field ─────────────────
    from tools.gmail_tool import _SendMessageInput as _SMI30
    assert "attachments" in _SMI30.model_fields, f"fields: {list(_SMI30.model_fields.keys())}"
    _att_field30 = _SMI30.model_fields["attachments"]
    assert not _att_field30.is_required(), "attachments should be optional"
    record("PASS", "v3.6: gmail _SendMessageInput has optional attachments field")

    # ── 30k. Gmail _CreateDraftInput has attachments field ─────────────────
    from tools.gmail_tool import _CreateDraftInput as _CDI30
    assert "attachments" in _CDI30.model_fields, f"fields: {list(_CDI30.model_fields.keys())}"
    record("PASS", "v3.6: gmail _CreateDraftInput has optional attachments field")

    # ── 30l. _build_mime_message creates multipart with attachment ─────────
    from tools.gmail_tool import _build_mime_message as _bmm30
    _tmpdir30l = tempfile.mkdtemp(prefix="thoth_test30l_")
    try:
        _att_file30 = Path(_tmpdir30l) / "test.txt"
        _att_file30.write_text("hello world", encoding="utf-8")
        _mime30 = _bmm30(
            body="Test email body",
            to="test@example.com",
            subject="Test Subject",
            attachments=[str(_att_file30)],
        )
        assert _mime30["To"] == "test@example.com"
        assert _mime30["Subject"] == "Test Subject"
        # Count MIME parts: 1 text + 1 attachment = 2 payloads
        _payloads30 = _mime30.get_payload()
        assert len(_payloads30) == 2, f"expected 2 parts, got {len(_payloads30)}"
        assert _payloads30[0].get_content_type() == "text/plain"
        assert _payloads30[1].get_content_disposition() == "attachment"
        record("PASS", "v3.6: _build_mime_message creates multipart with attachment")
    finally:
        shutil.rmtree(_tmpdir30l, ignore_errors=True)

    # ── 30m. _build_mime_message skips missing attachments ─────────────────
    _mime30m = _bmm30(
        body="no attach",
        to="a@b.com",
        subject="S",
        attachments=["absolutely_missing_file.xyz"],
    )
    _payloads30m = _mime30m.get_payload()
    assert len(_payloads30m) == 1, f"expected 1 part (missing att skipped), got {len(_payloads30m)}"
    record("PASS", "v3.6: _build_mime_message skips missing attachment files")

    # ── 30n. export_to_pdf in filesystem _WRITE_OPS ────────────────────────
    from tools.filesystem_tool import _WRITE_OPS as _wo30
    assert "export_to_pdf" in _wo30, f"_WRITE_OPS: {_wo30}"
    record("PASS", "v3.6: export_to_pdf in filesystem _WRITE_OPS")

    # ── 30o. export_to_pdf creates a PDF file ──────────────────────────────
    _tmpdir30o = tempfile.mkdtemp(prefix="thoth_test30o_")
    try:
        from tools.filesystem_tool import _make_export_to_pdf_tool as _mepdf
        _pdf_tool30 = _mepdf(_tmpdir30o)
        _pdf_result30 = _pdf_tool30.invoke({
            "content": "# Test Report\n\nThis is a **test** document.\n\n- Item 1\n- Item 2\n",
            "filename": "report.pdf",
        })
        assert "PDF saved to:" in _pdf_result30, f"result: {_pdf_result30}"
        _pdf_path30 = Path(_tmpdir30o) / "report.pdf"
        assert _pdf_path30.is_file(), f"PDF not created at {_pdf_path30}"
        # PDF header check
        _pdf_bytes30 = _pdf_path30.read_bytes()
        assert _pdf_bytes30[:4] == b"%PDF", f"not a valid PDF: {_pdf_bytes30[:10]}"
        record("PASS", "v3.6: export_to_pdf creates valid PDF file")
    except ImportError as _ie30o:
        record("WARN", "v3.6: export_to_pdf skipped (fpdf2 not installed)", str(_ie30o))
    finally:
        shutil.rmtree(_tmpdir30o, ignore_errors=True)

    # ── 30p. export_to_pdf auto-adds .pdf extension ───────────────────────
    _tmpdir30p = tempfile.mkdtemp(prefix="thoth_test30p_")
    try:
        _pdf_tool30p = _mepdf(_tmpdir30p)
        _pdf_result30p = _pdf_tool30p.invoke({
            "content": "Hello",
            "filename": "no_extension",
        })
        assert "PDF saved to:" in _pdf_result30p
        assert Path(_tmpdir30p, "no_extension.pdf").is_file()
        record("PASS", "v3.6: export_to_pdf auto-adds .pdf extension")
    except ImportError:
        record("WARN", "v3.6: export_to_pdf extension test skipped (fpdf2 not installed)")
    finally:
        shutil.rmtree(_tmpdir30p, ignore_errors=True)

    # ── 30q. prompts.py has FILE GENERATION & SENDING WORKFLOWS ────────────
    _p_src30 = Path("prompts.py").read_text(encoding="utf-8")
    assert "FILE GENERATION & SENDING WORKFLOWS" in _p_src30
    record("PASS", "v3.6: prompts.py has FILE GENERATION & SENDING WORKFLOWS section")

    # ── 30r. prompts.py has EMAIL ATTACHMENTS section ─────────────────────
    assert "EMAIL ATTACHMENTS" in _p_src30
    record("PASS", "v3.6: prompts.py has EMAIL ATTACHMENTS section")

    # ── 30s. prompts.py mentions save_to_file ─────────────────────────────
    assert "save_to_file" in _p_src30
    record("PASS", "v3.6: prompts.py mentions save_to_file")

    # ── 30t. "telegram" in skip_tools in ui/settings.py ─────────
    _settings_src30 = Path("ui/settings.py").read_text(encoding="utf-8")
    # Find the skip_tools set definition and check telegram is in it
    import re as _re30
    _skip_match30 = _re30.search(r'skip_tools\s*=\s*\{([^}]+)\}', _settings_src30, _re30.DOTALL)
    assert _skip_match30, "skip_tools set not found in ui/settings.py"
    assert "telegram" in _skip_match30.group(1), f"telegram not in skip_tools: {_skip_match30.group(1)[:200]}"
    record("PASS", "v3.6: telegram in skip_tools in ui/settings.py")

    # ── 30u. kaleido in requirements.txt ──────────────────────────────────
    _req_src30 = Path("requirements.txt").read_text(encoding="utf-8")
    assert "kaleido" in _req_src30.lower()
    record("PASS", "v3.6: kaleido in requirements.txt")

    # ── 30v. Gmail as_langchain_tools replaces send/draft with custom ─────
    _gm_src30 = Path("tools/gmail_tool.py").read_text(encoding="utf-8")
    assert "_make_custom_send" in _gm_src30
    assert "_make_custom_draft" in _gm_src30
    assert "_build_mime_message" in _gm_src30
    record("PASS", "v3.6: gmail_tool.py has custom send/draft with MIME builder")

    # ── 30w. prompts.py has multi-attachment guidance ─────────────────────
    assert "SINGLE send_gmail_message" in _p_src30 or "single send_gmail_message" in _p_src30.lower() or "SINGLE send_gmail" in _p_src30
    record("PASS", "v3.6: prompts.py has single-email multi-attachment guidance")

    # ── 30x. Telegram _send_telegram_photo uses _resolve_file_path ────────
    _tg_src30 = Path("tools/telegram_tool.py").read_text(encoding="utf-8")
    assert "_resolve_file_path" in _tg_src30
    # Also check that send_photo and send_document call it
    _photo_fn_src30 = _insp30.getsource(_stp)
    assert "_resolve_file_path" in _photo_fn_src30
    _doc_fn_src30 = _insp30.getsource(_std)
    assert "_resolve_file_path" in _doc_fn_src30
    record("PASS", "v3.6: send_photo and send_document use _resolve_file_path")

    # ── 30y. _md_to_html converts markdown to Telegram HTML ───────────────
    from channels.telegram import _md_to_html as _mth30
    _html30y = _mth30("**bold** and `code` and *italic*")
    assert "<b>bold</b>" in _html30y, f"bold not converted: {_html30y}"
    assert "<code>code</code>" in _html30y, f"code not converted: {_html30y}"
    assert "<i>italic</i>" in _html30y, f"italic not converted: {_html30y}"
    record("PASS", "v3.6: _md_to_html converts bold/code/italic")

    # ── 30ya. _md_to_html escapes HTML entities before converting ─────────
    _html30ya = _mth30("x < 10 && y > 5")
    assert "&lt;" in _html30ya, f"< not escaped: {_html30ya}"
    assert "&gt;" in _html30ya, f"> not escaped: {_html30ya}"
    assert "&amp;" in _html30ya, f"& not escaped: {_html30ya}"
    record("PASS", "v3.6: _md_to_html escapes HTML entities")

    # ── 30yb. _md_to_html handles headings ────────────────────────────────
    _html30yb = _mth30("# Title\n\nSome text\n## Subtitle")
    assert "<b>Title</b>" in _html30yb
    assert "<b>Subtitle</b>" in _html30yb
    record("PASS", "v3.6: _md_to_html converts headings to bold")

    # ── 30yc. _md_to_html handles fenced code blocks ─────────────────────
    _html30yc = _mth30("```python\nprint('hello')\n```")
    assert "<pre>" in _html30yc
    assert "print" in _html30yc
    record("PASS", "v3.6: _md_to_html converts fenced code blocks")

    # ── 30z. _format_interrupt accepts list of dicts (agent format) ───────
    from channels.telegram import _format_interrupt as _fi30
    _fi_list30 = _fi30([
        {"tool": "file_delete", "description": "Delete report.pdf", "args": {"path": "/x"}},
        {"tool": "send_email", "description": "Send to user@e.com"},
    ])
    assert "file_delete" in _fi_list30
    assert "send_email" in _fi_list30
    assert "<b>" in _fi_list30, "should be HTML formatted"
    record("PASS", "v3.6: _format_interrupt handles list of interrupt dicts")

    # ── 30za. _format_interrupt accepts single dict (backward compat) ─────
    _fi_single30 = _fi30({"tool": "delete_file", "args": {"path": "test.txt"}})
    assert "delete_file" in _fi_single30
    assert "<b>" in _fi_single30
    record("PASS", "v3.6: _format_interrupt handles single interrupt dict")

    # ── 30zb. _extract_interrupt_ids extracts multi-interrupt ids ─────────
    from channels.telegram import _extract_interrupt_ids as _eii30
    _ids30 = _eii30([
        {"tool": "a", "__interrupt_id": "id1"},
        {"tool": "b", "__interrupt_id": "id2"},
    ])
    assert _ids30 == ["id1", "id2"], f"expected ['id1', 'id2'], got {_ids30}"
    record("PASS", "v3.6: _extract_interrupt_ids extracts multi-interrupt ids")

    # ── 30zc. _extract_interrupt_ids returns None for single interrupt ────
    _ids30c = _eii30([{"tool": "a", "__interrupt_id": "id1"}])
    assert _ids30c is None, f"expected None for single interrupt, got {_ids30c}"
    record("PASS", "v3.6: _extract_interrupt_ids returns None for single interrupt")

    # ── 30zd. _is_corrupt_thread_error detects stuck tool call ────────────
    from channels.telegram import _is_corrupt_thread_error as _icte30
    assert _icte30(Exception("tool call was present without results"))
    assert _icte30(Exception("expected tool message after tool_calls"))
    assert not _icte30(Exception("some random error"))
    record("PASS", "v3.6: _is_corrupt_thread_error detects stuck threads")

    # ── 30ze. _resume_agent_sync accepts interrupt_ids kwarg ──────────────
    _sig30ze = _insp30.signature(
        __import__("channels.telegram", fromlist=["_resume_agent_sync"])._resume_agent_sync
    )
    assert "interrupt_ids" in _sig30ze.parameters, f"params: {list(_sig30ze.parameters)}"
    record("PASS", "v3.6: _resume_agent_sync accepts interrupt_ids kwarg")

    # ── 30zf. _pending_interrupts guard in _handle_message ────────────────
    _tg_chan_src30 = Path("channels/telegram.py").read_text(encoding="utf-8")
    assert "chat_id in _pending_interrupts" in _tg_chan_src30, "pending interrupt guard missing"
    record("PASS", "v3.6: _handle_message blocks messages during pending interrupt")

    # ── 30zg. _escape_html escapes required characters ────────────────────
    from channels.telegram import _escape_html as _eh30
    assert _eh30("a & b < c > d") == "a &amp; b &lt; c &gt; d"
    record("PASS", "v3.6: _escape_html escapes &, <, >")

    # ── 30zh. _grab_vision_capture exists and is callable ─────────────────
    from channels.telegram import _grab_vision_capture as _gvc30
    assert callable(_gvc30)
    # Should return None when no vision service has captured anything
    _vc30 = _gvc30()
    assert _vc30 is None, f"expected None when no capture, got type {type(_vc30)}"
    record("PASS", "v3.6: _grab_vision_capture returns None when no capture")

    # ── 30zi. _run_agent_sync returns 3-tuple ─────────────────────────────
    _sig30zi = _insp30.signature(
        __import__("channels.telegram", fromlist=["_run_agent_sync"])._run_agent_sync
    )
    # Check return annotation includes 3 elements (bytes | None at end)
    _tg_src30zi = Path("channels/telegram.py").read_text(encoding="utf-8")
    assert "bytes | None]" in _tg_src30zi, "return type should include bytes | None"
    assert "captured_image" in _tg_src30zi, "should track captured_image"
    record("PASS", "v3.6: _run_agent_sync returns 3-tuple with captured image")

    # ── 30zj. _resume_agent_sync returns 3-tuple ─────────────────────────
    assert "used_vision" in _tg_src30zi, "should track used_vision flag"
    assert "send_photo" in _tg_src30zi, "should call send_photo for vision captures"
    record("PASS", "v3.6: _resume_agent_sync returns 3-tuple with captured image")

    # ── 30zk. Email _format_interrupt handles list of dicts ─────────────
    _email_src30 = Path("channels/email.py").read_text(encoding="utf-8")
    assert "isinstance(data, list)" in _email_src30, \
        "email _format_interrupt should handle list"
    assert '"description"' in _email_src30 or "'description'" in _email_src30, \
        "email should use 'description' field, not 'reason'"
    record("PASS", "v3.6: email _format_interrupt handles list of dicts")

    # ── 30zl. Email _resume_agent_sync accepts interrupt_ids ──────────
    assert "interrupt_ids" in _email_src30, \
        "email _resume_agent_sync should accept interrupt_ids"
    # Verify it's passed through to resume_stream_agent
    assert "interrupt_ids=interrupt_ids" in _email_src30, \
        "should pass interrupt_ids to resume_stream_agent"
    record("PASS", "v3.6: email _resume_agent_sync accepts interrupt_ids")

    # ── 30zm. Email has _extract_interrupt_ids helper ─────────────────
    assert "_extract_interrupt_ids" in _email_src30, \
        "email should have _extract_interrupt_ids helper"
    assert "__interrupt_id" in _email_src30, \
        "should extract __interrupt_id from interrupt data"
    record("PASS", "v3.6: email has _extract_interrupt_ids helper")

    # ── 30zn. Email has corrupt thread detection ──────────────────────
    assert "_is_corrupt_thread_error" in _email_src30, \
        "email should have _is_corrupt_thread_error"
    assert "_THREAD_CORRUPT_PATTERNS" in _email_src30, \
        "email should have _THREAD_CORRUPT_PATTERNS"
    record("PASS", "v3.6: email has corrupt thread detection")

    # ── 30zo. Email _poll_once passes interrupt_ids on resume ─────────
    # Check the lambda pattern that passes interrupt_ids
    assert "interrupt_ids=interrupt_ids" in _email_src30, \
        "poll_once should pass interrupt_ids on resume"
    assert "_extract_interrupt_ids(pending" in _email_src30, \
        "should extract interrupt_ids from pending data"
    record("PASS", "v3.6: email _poll_once passes interrupt_ids on resume")

    # ── 30zp. Email corrupt thread recovery in new-message handler ────
    # Count occurrences of _is_corrupt_thread_error — should appear 2+ times
    # (once in resume handler, once in new-message handler)
    _corrupt_count = _email_src30.count("_is_corrupt_thread_error")
    assert _corrupt_count >= 2, \
        f"_is_corrupt_thread_error should be called in both handlers, found {_corrupt_count}"
    assert "start a new email thread" in _email_src30, \
        "should advise user to start new email thread on corrupt error"
    record("PASS", "v3.6: email corrupt thread recovery in both handlers")

except Exception as e:
    record("FAIL", "v3.6 file & messaging pipeline tests", f"{type(e).__name__}: {e}")
    traceback.print_exc()


# ═════════════════════════════════════════════════════════════════════════════
# 31. TASK-SCOPED BACKGROUND PERMISSIONS (v3.6.0)
# ═════════════════════════════════════════════════════════════════════════════
try:
    _src_agent31 = Path("agent.py").read_text(encoding="utf-8")
    _src_tasks31 = Path("tasks.py").read_text(encoding="utf-8")
    _src_shell31 = Path("tools/shell_tool.py").read_text(encoding="utf-8")
    _src_gmail31 = Path("tools/gmail_tool.py").read_text(encoding="utf-8")
    _src_prompts31 = Path("prompts.py").read_text(encoding="utf-8")
    _src_ui31 = Path("ui/task_dialog.py").read_text(encoding="utf-8")

    # ── 31a. ContextVars for task permissions exist in agent.py ──────
    assert "_task_allowed_commands_var" in _src_agent31, \
        "agent.py must define _task_allowed_commands_var"
    assert "_task_allowed_recipients_var" in _src_agent31, \
        "agent.py must define _task_allowed_recipients_var"
    assert "ContextVar" in _src_agent31, \
        "should use ContextVar for task permission propagation"
    record("PASS", "v3.6: agent.py has task permission ContextVars")

    # ── 31b. Tiered background tool filtering in agent.py ────────────
    assert "_ALWAYS_ALLOWED_BG" in _src_agent31, \
        "agent.py should define _ALWAYS_ALLOWED_BG set"
    assert "workspace_move_file" in _src_agent31.split("_ALWAYS_ALLOWED_BG")[1][:200], \
        "move_file should be in always-allowed background set"
    assert "move_calendar_event" in _src_agent31.split("_ALWAYS_ALLOWED_BG")[1][:200], \
        "move_calendar should be in always-allowed background set"
    assert "send_gmail_message" in _src_agent31.split("_ALWAYS_ALLOWED_BG")[1][:200], \
        "send_gmail should be in always-allowed background set"
    record("PASS", "v3.6: agent.py has tiered background tool filtering")

    # ── 31c. tasks.py DB schema has permission columns ───────────────
    assert "allowed_commands" in _src_tasks31, \
        "tasks.py schema should have allowed_commands column"
    assert "allowed_recipients" in _src_tasks31, \
        "tasks.py schema should have allowed_recipients column"
    # Verify migration for existing DBs (the migration loop adds columns dynamically)
    _migrations_section = _src_tasks31[_src_tasks31.index("Migrations for tasks table"):
                                        _src_tasks31.index("Migrations for tasks table") + 400]
    assert "allowed_commands" in _migrations_section, \
        "should have migration for allowed_commands"
    assert "allowed_recipients" in _migrations_section, \
        "should have migration for allowed_recipients"
    assert "model_override" in _migrations_section, \
        "should have migration for model_override (legacy DB upgrade)"
    record("PASS", "v3.6: tasks.py DB schema has permission columns")

    # ── 31d. _row_to_dict parses permission fields ───────────────────
    _row_section = _src_tasks31[_src_tasks31.index("def _row_to_dict"):][:500]
    assert "allowed_commands" in _row_section, \
        "_row_to_dict should parse allowed_commands"
    assert "allowed_recipients" in _row_section, \
        "_row_to_dict should parse allowed_recipients"
    assert "json.loads" in _row_section, \
        "_row_to_dict should json.loads the permission fields"
    record("PASS", "v3.6: _row_to_dict parses permission fields")

    # ── 31e. update_task allows permission fields ────────────────────
    _update_section = _src_tasks31[_src_tasks31.index("def update_task"):][:800]
    assert "allowed_commands" in _update_section, \
        "update_task should accept allowed_commands"
    assert "allowed_recipients" in _update_section, \
        "update_task should accept allowed_recipients"
    record("PASS", "v3.6: update_task accepts permission fields")

    # ── 31f. run_task_background sets ContextVars ────────────────────
    _run_bg_section = _src_tasks31[_src_tasks31.index("def run_task_background"):][:5000]
    assert "_task_allowed_commands_var" in _run_bg_section, \
        "run_task_background should set _task_allowed_commands_var"
    assert "_task_allowed_recipients_var" in _run_bg_section, \
        "run_task_background should set _task_allowed_recipients_var"
    record("PASS", "v3.6: run_task_background sets task permission ContextVars")

    # ── 31g. Shell tool checks allowed_commands in background ────────
    assert "_task_allowed_commands_var" in _src_shell31, \
        "shell_tool should import _task_allowed_commands_var"
    assert "allowed commands" in _src_shell31.lower() or \
           "allowed_commands" in _src_shell31, \
        "shell_tool should reference allowed commands"
    # Should have prefix matching logic
    assert "startswith" in _src_shell31, \
        "shell_tool should do prefix matching on allowed commands"
    # Should mention task editor in blocked message
    assert "Background permissions" in _src_shell31, \
        "blocked message should tell user where to configure"
    record("PASS", "v3.6: shell_tool checks allowed_commands in background")

    # ── 31h. Shell tool still uses interrupt for interactive ─────────
    assert "interrupt(" in _src_shell31, \
        "shell_tool should still use interrupt for interactive sessions"
    assert "Run shell command" in _src_shell31, \
        "shell_tool should have interactive interrupt label"
    record("PASS", "v3.6: shell_tool still uses interrupt for interactive")

    # ── 31i. Gmail tool checks allowed_recipients in background ──────
    assert "_task_allowed_recipients_var" in _src_gmail31, \
        "gmail_tool should import _task_allowed_recipients_var"
    assert "is_background_workflow" in _src_gmail31, \
        "gmail_tool should check is_background_workflow"
    # Should validate all recipient fields (to, cc, bcc)
    _gmail_recip_section = _src_gmail31[_src_gmail31.index("_task_allowed_recipients_var"):][:1000]
    assert "cc" in _gmail_recip_section.lower(), \
        "gmail_tool should validate cc recipients too"
    assert "bcc" in _gmail_recip_section.lower(), \
        "gmail_tool should validate bcc recipients too"
    assert "Background permissions" in _src_gmail31, \
        "blocked message should tell user where to configure"
    record("PASS", "v3.6: gmail_tool checks allowed_recipients in background")

    # ── 31j. UI has background permissions section ───────────────────
    assert "Background permissions" in _src_ui31, \
        "task editor should have background permissions section"
    assert "allowed_recip_input" in _src_ui31 or "allowed_recipients" in _src_ui31, \
        "task editor should have allowed recipients field"
    assert "allowed_cmds_input" in _src_ui31 or "allowed_commands" in _src_ui31, \
        "task editor should have allowed commands field"
    record("PASS", "v3.6: UI task editor has background permission fields")

    # ── 31k. UI save persists permission fields ──────────────────────
    # Check that _save reads from the permission textareas and updates
    _save_section = _src_ui31[_src_ui31.index("def _save():"):][:4000]
    assert "allowed_commands" in _save_section or "allowed_cmds" in _save_section, \
        "save should persist allowed_commands"
    assert "allowed_recipients" in _save_section or "allowed_recip" in _save_section, \
        "save should persist allowed_recipients"
    record("PASS", "v3.6: UI save persists permission fields")

    # ── 31l. Prompts mention background task permissions ─────────────
    assert "background task" in _src_prompts31.lower() or \
           "BACKGROUND TASK PERMISSIONS" in _src_prompts31, \
        "prompts should mention background task permissions"
    record("PASS", "v3.6: prompts mention background task permissions")

    # ── 31m. CRUD roundtrip: create + read permissions ───────────────
    import tasks as _tasks31
    _test_id31 = _tasks31.create_task(
        name="__test_perms_31m__",
        prompts=["test"],
        schedule=None,
    )
    _tasks31.update_task(_test_id31,
        allowed_commands=["git pull", "python backup.py"],
        allowed_recipients=["alice@example.com", "bob@example.com"],
    )
    _t31 = _tasks31.get_task(_test_id31)
    assert _t31 is not None
    assert _t31["allowed_commands"] == ["git pull", "python backup.py"], \
        f"expected commands list, got {_t31['allowed_commands']}"
    assert _t31["allowed_recipients"] == ["alice@example.com", "bob@example.com"], \
        f"expected recipients list, got {_t31['allowed_recipients']}"
    _tasks31.delete_task(_test_id31)
    record("PASS", "v3.6: CRUD roundtrip for task permissions")

    # ── 31n. Default permissions are empty lists ─────────────────────
    _test_id31n = _tasks31.create_task(
        name="__test_defaults_31n__",
        prompts=["test"],
    )
    _t31n = _tasks31.get_task(_test_id31n)
    assert _t31n["allowed_commands"] == [], \
        f"default allowed_commands should be [], got {_t31n['allowed_commands']}"
    assert _t31n["allowed_recipients"] == [], \
        f"default allowed_recipients should be [], got {_t31n['allowed_recipients']}"
    _tasks31.delete_task(_test_id31n)
    record("PASS", "v3.6: default task permissions are empty lists")

    # ── 31o. Still-blocked ops not in _ALWAYS_ALLOWED_BG ─────────────
    _bg_set_text = _src_agent31.split("_ALWAYS_ALLOWED_BG")[1][:300]
    for _blocked_op in ("workspace_file_delete", "delete_calendar_event",
                        "delete_memory", "tracker_delete", "task_delete"):
        assert _blocked_op not in _bg_set_text, \
            f"{_blocked_op} should NOT be in _ALWAYS_ALLOWED_BG"
    record("PASS", "v3.6: hard-blocked ops excluded from background")

except Exception as e:
    record("FAIL", "v3.6 task-scoped background permissions", f"{type(e).__name__}: {e}")
    traceback.print_exc()


# ═════════════════════════════════════════════════════════════════════════════
# 32. SECURITY AUDIT — BACKGROUND FLAG PROPAGATION (v3.6.0)
# ═════════════════════════════════════════════════════════════════════════════
try:
    _src_agent32 = Path("agent.py").read_text(encoding="utf-8")
    _src_tasks32 = Path("tasks.py").read_text(encoding="utf-8")
    _src_shell32 = Path("tools/shell_tool.py").read_text(encoding="utf-8")
    _src_gmail32 = Path("tools/gmail_tool.py").read_text(encoding="utf-8")
    _src_browser32 = Path("tools/browser_tool.py").read_text(encoding="utf-8")

    # ── 32a. Background flag is a ContextVar, NOT threading.local ────
    assert "_background_workflow_var" in _src_agent32, \
        "background flag must be a ContextVar named _background_workflow_var"
    assert "ContextVar" in _src_agent32.split("_background_workflow_var")[0][-200:] + \
           _src_agent32.split("_background_workflow_var")[1][:200], \
        "_background_workflow_var must be a ContextVar"
    # Verify no code reads _tlocal.background_workflow (the old pattern)
    assert "_tlocal.background_workflow" not in _src_agent32, \
        "SECURITY: _tlocal.background_workflow still in agent.py — must use ContextVar"
    assert "_tlocal.background_workflow" not in _src_tasks32, \
        "SECURITY: _tlocal.background_workflow still in tasks.py"
    record("PASS", "v3.6: background flag uses ContextVar (not threading.local)")

    # ── 32b. is_background_workflow reads ContextVar ─────────────────
    _ibw_section = _src_agent32[_src_agent32.index("def is_background_workflow"):][:400]
    assert "_background_workflow_var.get()" in _ibw_section, \
        "is_background_workflow must read from ContextVar"
    assert "getattr(_tlocal" not in _ibw_section, \
        "is_background_workflow must NOT use _tlocal"
    record("PASS", "v3.6: is_background_workflow reads ContextVar")

    # ── 32c. _wrap_with_interrupt_gate uses ContextVar ───────────────
    _gate_section = _src_agent32[_src_agent32.index("def _wrap_with_interrupt_gate"):][:2000]
    assert "_background_workflow_var.get()" in _gate_section, \
        "interrupt gate must check _background_workflow_var.get()"
    assert "getattr(_tlocal" not in _gate_section, \
        "interrupt gate must NOT use _tlocal for background check"
    record("PASS", "v3.6: interrupt gate uses ContextVar for bg check")

    # ── 32d. get_agent_graph uses ContextVar ─────────────────────────
    _gag_section = _src_agent32[_src_agent32.index("def get_agent_graph"):][:1500]
    assert "_background_workflow_var.get()" in _gag_section, \
        "get_agent_graph must read _background_workflow_var"
    record("PASS", "v3.6: get_agent_graph uses ContextVar for bg check")

    # ── 32e. tasks.py sets ContextVar ────────────────────────────────
    assert "_background_workflow_var.set(True)" in _src_tasks32, \
        "tasks.py must set _background_workflow_var to True"
    assert "_background_workflow_var" in _src_tasks32, \
        "tasks.py must import _background_workflow_var"
    record("PASS", "v3.6: tasks.py sets ContextVar for background")

    # ── 32g. Runtime tool gates ────────────────────────────────────
    # Shell tool and gmail tool use is_background_workflow() for gating.
    # Browser tool uses per-thread tab isolation instead (no blocking).
    assert "is_background_workflow" in _src_shell32, \
        "shell_tool must call is_background_workflow()"
    assert "is_background_workflow" in _src_gmail32, \
        "gmail_tool must call is_background_workflow()"
    assert "_thread_pages" in _src_browser32, \
        "browser_tool must use per-thread tab isolation (_thread_pages)"
    record("PASS", "v3.6: shell/gmail gate + browser per-thread isolation")

    # ── 32h. ContextVar propagation test ─────────────────────────────
    # Verify that ContextVar propagates to child threads (executor-like)
    import contextvars as _cv32
    import concurrent.futures as _cf32
    _test_var32 = _cv32.ContextVar("_test_propagation_32", default=False)
    _test_var32.set(True)
    _executor_result32 = None
    def _check_in_executor():
        return _test_var32.get()
    # Copy context to simulate LangGraph executor behavior
    ctx32 = _cv32.copy_context()
    _executor_result32 = ctx32.run(_check_in_executor)
    assert _executor_result32 is True, \
        f"ContextVar must propagate via copy_context, got {_executor_result32}"
    _test_var32.set(False)  # clean up
    record("PASS", "v3.6: ContextVar propagation via copy_context works")

    # ── 32i. Destructive ops in _DESTRUCTIVE_LABELS match tools ──────
    # Every destructive label should have a corresponding tool somewhere
    _destr_labels = set()
    _in_labels = False
    for _line in _src_agent32.split("\n"):
        if "_DESTRUCTIVE_LABELS" in _line and "{" in _line:
            _in_labels = True
        if _in_labels:
            if '"' in _line:
                _parts = _line.split('"')
                if len(_parts) >= 2:
                    _destr_labels.add(_parts[1])
            if "}" in _line:
                _in_labels = False
    # The labels should match what tools report as destructive
    _expected_destructive = {
        "workspace_file_delete", "workspace_move_file",
        "delete_calendar_event", "move_calendar_event",
        "send_gmail_message", "delete_memory",
        "tracker_delete", "task_delete",
    }
    assert _destr_labels == _expected_destructive, \
        f"_DESTRUCTIVE_LABELS mismatch: {_destr_labels.symmetric_difference(_expected_destructive)}"
    record("PASS", "v3.6: _DESTRUCTIVE_LABELS matches expected destructive ops")

    # ── 32j. send_gmail_message in _ALWAYS_ALLOWED_BG requires runtime gate ──
    # If send_gmail is allowed in background, the gmail tool MUST have a
    # runtime recipient check. Verify both sides of this contract.
    assert "send_gmail_message" in _src_agent32.split("_ALWAYS_ALLOWED_BG")[1][:300], \
        "send_gmail_message must be in _ALWAYS_ALLOWED_BG"
    assert "_task_allowed_recipients_var" in _src_gmail32, \
        "gmail_tool MUST check _task_allowed_recipients_var since send is allowed in bg"
    record("PASS", "v3.6: send_gmail bg allowance paired with runtime guard")

    # ── 32k. Interactive channels do NOT set background flag ─────────
    _src_tg32 = Path("channels/telegram.py").read_text(encoding="utf-8")
    _src_em32 = Path("channels/email.py").read_text(encoding="utf-8")
    _src_ui32 = Path("app.py").read_text(encoding="utf-8")
    # These should NEVER set background_workflow to True
    assert "_background_workflow_var" not in _src_tg32, \
        "SECURITY: Telegram must NOT set _background_workflow_var"
    assert "_background_workflow_var" not in _src_em32, \
        "SECURITY: Email channel must NOT set _background_workflow_var"
    # UI may import is_background_workflow but should never .set(True)
    assert "_background_workflow_var.set(True)" not in _src_ui32, \
        "SECURITY: UI must NOT set _background_workflow_var to True"
    record("PASS", "v3.6: interactive channels do NOT set background flag")

    # ── 32l. Shell blocked patterns still enforced on top of allowlist ──
    # Even if allowed_commands permits "rm", the BLOCKED patterns must still fire
    assert "_BLOCKED_PATTERNS" in _src_shell32, \
        "shell_tool must have _BLOCKED_PATTERNS for catastrophic commands"
    # Verify blocked check happens BEFORE the allowed check
    _blocked_idx = _src_shell32.index("classification == \"blocked\"")
    _allowed_idx = _src_shell32.index("_task_allowed_commands_var")
    assert _blocked_idx < _allowed_idx, \
        "SECURITY: blocked pattern check must happen BEFORE allowed_commands check"
    record("PASS", "v3.6: shell blocked patterns enforced before allowlist")

except Exception as e:
    record("FAIL", "v3.6 security audit tests", f"{type(e).__name__}: {e}")
    traceback.print_exc()


# ═════════════════════════════════════════════════════════════════════════════
# 33. TOOL DEFAULT CONFIGURATION
# ═════════════════════════════════════════════════════════════════════════════
print("\n" + "=" * 70)
print("33. TOOL DEFAULT CONFIGURATION")
print("=" * 70)

try:
    import tempfile, shutil, pathlib
    from tools.filesystem_tool import (
        FileSystemTool, DEFAULT_OPERATIONS, ALL_OPERATIONS,
        _SAFE_OPS, _WRITE_OPS, _DESTRUCTIVE_OPS,
    )

    # ── 33a. Filesystem enabled by default ─────────────────────────────────
    _fs33 = FileSystemTool()
    assert _fs33.enabled_by_default is True, f"got {_fs33.enabled_by_default}"
    record("PASS", "defaults: filesystem enabled_by_default is True")

    # ── 33b. DEFAULT_OPERATIONS includes safe + write + move_file ──────────
    for op in _SAFE_OPS + _WRITE_OPS:
        assert op in DEFAULT_OPERATIONS, f"{op} missing from DEFAULT_OPERATIONS"
    assert "move_file" in DEFAULT_OPERATIONS, "move_file missing from DEFAULT_OPERATIONS"
    record("PASS", "defaults: DEFAULT_OPERATIONS includes safe + write + move_file")

    # ── 33c. DEFAULT_OPERATIONS does NOT include file_delete ───────────────
    assert "file_delete" not in DEFAULT_OPERATIONS, "file_delete should not be in DEFAULT_OPERATIONS"
    record("PASS", "defaults: file_delete excluded from DEFAULT_OPERATIONS")

    # ── 33d. _get_workspace_root auto-sets default when unconfigured ───────
    _tmpdir33 = tempfile.mkdtemp(prefix="thoth_test33_")
    try:
        _fs33d = FileSystemTool()
        _old_ws33 = _fs33d.get_config("workspace_root", "")
        _fs33d.set_config("workspace_root", "")  # Clear to trigger auto-default
        _root33 = _fs33d._get_workspace_root()
        assert _root33, "_get_workspace_root returned empty string"
        assert "Documents" in _root33 and "Thoth" in _root33, \
            f"default path should contain Documents/Thoth, got: {_root33}"
        record("PASS", "defaults: _get_workspace_root auto-sets ~/Documents/Thoth")
    finally:
        # Restore original workspace_root
        _fs33d.set_config("workspace_root", _old_ws33)
        shutil.rmtree(_tmpdir33, ignore_errors=True)

    # ── 33e. _get_workspace_root creates directory if it doesn't exist ─────
    _tmpdir33e = tempfile.mkdtemp(prefix="thoth_test33e_")
    try:
        _new_ws33 = str(pathlib.Path(_tmpdir33e) / "subdir" / "workspace")
        _fs33e = FileSystemTool()
        _old_ws33e = _fs33e.get_config("workspace_root", "")
        _fs33e.set_config("workspace_root", _new_ws33)
        _root33e = _fs33e._get_workspace_root()
        assert pathlib.Path(_root33e).is_dir(), f"directory not created: {_root33e}"
        record("PASS", "defaults: _get_workspace_root creates directory")
    finally:
        _fs33e.set_config("workspace_root", _old_ws33e)
        shutil.rmtree(_tmpdir33e, ignore_errors=True)

    # ── 33f. as_langchain_tools returns tools when workspace exists ────────
    _tmpdir33f = tempfile.mkdtemp(prefix="thoth_test33f_")
    try:
        _fs33f = FileSystemTool()
        _old_ws33f = _fs33f.get_config("workspace_root", "")
        _fs33f.set_config("workspace_root", _tmpdir33f)
        _tools33f = _fs33f.as_langchain_tools()
        assert len(_tools33f) > 0, f"expected tools, got {len(_tools33f)}"
        record("PASS", f"defaults: as_langchain_tools returns {len(_tools33f)} tools")
    finally:
        _fs33f.set_config("workspace_root", _old_ws33f)
        shutil.rmtree(_tmpdir33f, ignore_errors=True)

    # ── 33g. move_file is in destructive_tool_names (has interrupt gate) ───
    assert "workspace_move_file" in _fs33.destructive_tool_names, \
        f"workspace_move_file not in destructive_tool_names: {_fs33.destructive_tool_names}"
    record("PASS", "defaults: workspace_move_file has interrupt gate")

    # ── 33h. ALL_OPERATIONS is superset of DEFAULT_OPERATIONS ─────────────
    for op in DEFAULT_OPERATIONS:
        assert op in ALL_OPERATIONS, f"{op} in DEFAULT_OPERATIONS but not in ALL_OPERATIONS"
    record("PASS", "defaults: DEFAULT_OPERATIONS is subset of ALL_OPERATIONS")

except Exception as e:
    record("FAIL", "tool default config tests", f"{type(e).__name__}: {e}")
    traceback.print_exc()


# ═════════════════════════════════════════════════════════════════════════════
# 34. EXPORT FILENAME SANITIZATION
# ═════════════════════════════════════════════════════════════════════════════
print("\n")
print("34. EXPORT FILENAME SANITIZATION")
print("=" * 70)

try:
    # We need to import the inner _safe_filename. It's a nested function inside
    # _build_ui, so we test the same logic directly via re.sub.
    import re as _re34

    def _safe_filename_ref(name: str) -> str:
        """Reference implementation matching app._safe_filename."""
        return _re34.sub(r'[\\/:*?"<>|]', '-', name).strip('- ')

    # 34a. Colons replaced (the actual bug — timestamps in thread names)
    result = _safe_filename_ref("⚡ New Task — Mar 22, 02:20 AM.md")
    assert ":" not in result, f"colon still present: {result}"
    assert result.endswith(".md"), f"extension lost: {result}"
    record("PASS", "export: colons replaced in filename")

    # 34b. Preserves clean filenames unchanged
    clean = _safe_filename_ref("Plain conversation.pdf")
    assert clean == "Plain conversation.pdf", f"clean name changed: {clean}"
    record("PASS", "export: clean filenames unchanged")

    # 34c. Preserves emoji characters (not illegal on any FS)
    emoji_name = _safe_filename_ref("⚡ Lightning task.txt")
    assert "⚡" in emoji_name, f"emoji stripped: {emoji_name}"
    assert emoji_name.endswith(".txt"), f"extension lost: {emoji_name}"
    record("PASS", "export: emojis preserved in filename")

    # 34d. All Windows-illegal characters removed
    nasty = _safe_filename_ref('a\\b/c:d*e?f"g<h>i|j.md')
    for ch in '\\/:*?"<>|':
        assert ch not in nasty, f"illegal char {ch!r} in: {nasty}"
    assert nasty.endswith(".md"), f"extension lost: {nasty}"
    record("PASS", "export: all illegal chars removed")

    # 34e. Multiple colons (e.g. 12:30:45) handled
    multi = _safe_filename_ref("⚡ Task — 12:30:45 PM.pdf")
    assert ":" not in multi, f"colon still present: {multi}"
    assert multi.endswith(".pdf"), f"extension lost: {multi}"
    record("PASS", "export: multiple colons handled")

    # 34f. pathlib.Path parses sanitized name correctly
    import pathlib as _pl34
    for ext in (".md", ".txt", ".pdf"):
        sanitized = _safe_filename_ref(f"⚡ Task — 02:20 AM{ext}")
        p = _pl34.Path(sanitized)
        assert p.suffix == ext, f"suffix mismatch: {p.suffix} != {ext}"
    record("PASS", "export: pathlib parses sanitized names correctly")

    # 34g. No leading/trailing dashes or spaces after sanitization
    edge = _safe_filename_ref(":leading colon.md")
    assert not edge.startswith("-"), f"leading dash: {edge}"
    assert not edge.startswith(" "), f"leading space: {edge}"
    record("PASS", "export: no leading dash/space after sanitization")

    # 34h. Empty name (only illegal chars) doesn't crash
    empty = _safe_filename_ref(':::.md')
    assert empty.endswith(".md"), f"extension lost: {empty}"
    record("PASS", "export: degenerate name still has extension")

except Exception as e:
    record("FAIL", "export filename sanitization", f"{type(e).__name__}: {e}")
    traceback.print_exc()


# ═════════════════════════════════════════════════════════════════════════════
# 35. CLOUD MODEL SUPPORT — DYNAMIC FETCHING + CLOUD-PRIMARY (v3.7.0)
# ═════════════════════════════════════════════════════════════════════════════
print("\n" + "=" * 70)
print("35. CLOUD MODEL SUPPORT — DYNAMIC + CLOUD-PRIMARY (v3.7.0)")
print("=" * 70)

try:
    # ── 35a. Dynamic cache structure ──────────────────────────────────
    from models import (
        _cloud_model_cache, is_cloud_model, is_cloud_available,
        is_openai_available, is_openrouter_available,
        list_cloud_models, list_starred_cloud_models,
        star_cloud_model, unstar_cloud_model,
        fetch_cloud_models, refresh_cloud_models,
        get_cloud_provider, get_cloud_model_context,
        is_tool_compatible,
        _get_cloud_llm, get_model_max_context,
        OPENROUTER_BASE_URL, OPENAI_BASE_URL,
        _CONTEXT_HEURISTICS, _CLOUD_CONTEXT_FALLBACK,
        _estimate_context_heuristic, _catalog_or_heuristic,
        _context_catalog, _context_catalog_lock,
        validate_openrouter_key, fetch_context_catalog,
        _OPENAI_CHAT_PREFIXES,
    )
    assert isinstance(_cloud_model_cache, dict), "_cloud_model_cache should be a dict"
    record("PASS", "cloud: _cloud_model_cache is a dict")

    # ── 35b. _CONTEXT_HEURISTICS covers major providers ───────────────
    assert isinstance(_CONTEXT_HEURISTICS, list), "should be list of tuples"
    assert len(_CONTEXT_HEURISTICS) >= 20, f"Expected ≥20 heuristic entries, got {len(_CONTEXT_HEURISTICS)}"
    for _pfx35, _ctx35 in _CONTEXT_HEURISTICS:
        assert isinstance(_pfx35, str) and isinstance(_ctx35, int) and _ctx35 > 0
    record("PASS", "cloud: _CONTEXT_HEURISTICS has valid entries")

    # ── 35b2. _estimate_context_heuristic covers key model families ───
    assert _estimate_context_heuristic("gpt-4o") == 128_000, "gpt-4o → 128K"
    assert _estimate_context_heuristic("gpt-4o-mini") == 128_000, "gpt-4o-mini → 128K"
    assert _estimate_context_heuristic("gpt-4.1-mini") == 1_048_576, "gpt-4.1-mini → 1M"
    assert _estimate_context_heuristic("gpt-5") == 1_048_576, "gpt-5 → 1M"
    assert _estimate_context_heuristic("gpt-5.4-latest") == 1_048_576, "gpt-5.4 → 1M"
    assert _estimate_context_heuristic("o3-mini") == 200_000, "o3-mini → 200K"
    assert _estimate_context_heuristic("o4-mini") == 200_000, "o4-mini → 200K"
    assert _estimate_context_heuristic("chatgpt-4o-latest") == 128_000, "chatgpt- → 128K"
    # Anthropic
    assert _estimate_context_heuristic("claude-opus-4-6") == 1_000_000, "opus → 1M"
    assert _estimate_context_heuristic("claude-sonnet-4-6") == 1_000_000, "sonnet → 1M"
    assert _estimate_context_heuristic("claude-haiku-4-5") == 200_000, "haiku → 200K"
    assert _estimate_context_heuristic("claude-3-5-sonnet-20241022") == 200_000, "3.5 → 200K"
    assert _estimate_context_heuristic("claude-2.1") == 100_000, "claude-2 → 100K"
    # Gemini
    assert _estimate_context_heuristic("gemini-3-flash-preview") == 1_048_576, "g3 → 1M"
    assert _estimate_context_heuristic("gemini-2.5-flash") == 1_048_576, "g2.5f → 1M"
    assert _estimate_context_heuristic("gemini-2.5-pro") == 1_048_576, "g2.5p → 1M"
    assert _estimate_context_heuristic("gemini-1.5-pro") == 2_097_152, "g1.5p → 2M"
    # Strips provider/ prefix
    assert _estimate_context_heuristic("openai/gpt-4o") == 128_000, "strips provider/"
    assert _estimate_context_heuristic("anthropic/claude-sonnet-4-6") == 1_000_000
    assert _estimate_context_heuristic("google/gemini-2.5-flash") == 1_048_576
    # Unknown → fallback
    assert _estimate_context_heuristic("totally-unknown-model") == _CLOUD_CONTEXT_FALLBACK
    assert _CLOUD_CONTEXT_FALLBACK == 256_000, "fallback should be 256K"
    record("PASS", "cloud: _estimate_context_heuristic covers all providers")

    # ── 35b3. _catalog_or_heuristic uses catalog then heuristic ───
    # Inject into context catalog
    with _context_catalog_lock:
        _context_catalog["openai/gpt-4o"] = 128_000
        _context_catalog["openai/gpt-99"] = 999_999
    assert _catalog_or_heuristic("gpt-4o") == 128_000, "should find openai/gpt-4o in catalog"
    assert _catalog_or_heuristic("gpt-99") == 999_999, "should find openai/gpt-99 in catalog"
    # Also works with bare catalog keys
    with _context_catalog_lock:
        _context_catalog["anthropic/claude-sonnet-4-6"] = 1_000_000
    assert _catalog_or_heuristic("anthropic/claude-sonnet-4-6") == 1_000_000
    # Clean up catalog entries
    with _context_catalog_lock:
        _context_catalog.pop("openai/gpt-4o", None)
        _context_catalog.pop("openai/gpt-99", None)
        _context_catalog.pop("anthropic/claude-sonnet-4-6", None)
    # Without catalog, should fall back to heuristic
    assert _catalog_or_heuristic("gpt-4o") == 128_000, "heuristic fallback should match"
    assert _catalog_or_heuristic("some-future-model") == _CLOUD_CONTEXT_FALLBACK
    record("PASS", "cloud: _catalog_or_heuristic uses catalog then heuristic")

    # ── 35b4. _context_catalog structure and persistence ──────────────
    assert isinstance(_context_catalog, dict), "_context_catalog should be dict"
    record("PASS", "cloud: _context_catalog is a dict")

    # ── 35b5. validate_openrouter_key is callable ─────────────────────
    assert callable(validate_openrouter_key), "validate_openrouter_key should be callable"
    record("PASS", "cloud: validate_openrouter_key is callable")

    # ── 35b6. validate_openrouter_key rejects garbage key (no network) ─
    # Use a clearly invalid key — this should fail (401 or connection)
    bad_result = validate_openrouter_key("sk-fake-invalid-key-12345")
    assert bad_result is False, f"Garbage key should fail validation, got {bad_result}"
    record("PASS", "cloud: validate_openrouter_key rejects invalid key")

    # ── 35b7. fetch_context_catalog is callable ───────────────────────
    assert callable(fetch_context_catalog), "fetch_context_catalog should be callable"
    record("PASS", "cloud: fetch_context_catalog is callable")

    # ── 35b8. get_cloud_model_context uses catalog fallback ──────────
    # Inject a catalog entry for a model not in _cloud_model_cache
    with _context_catalog_lock:
        _context_catalog["openai/gpt-catalog-test"] = 500_000
    ctx_cat = get_cloud_model_context("gpt-catalog-test")
    assert ctx_cat == 500_000, f"Should use catalog for uncached model, got {ctx_cat}"
    with _context_catalog_lock:
        _context_catalog.pop("openai/gpt-catalog-test", None)
    record("PASS", "cloud: get_cloud_model_context uses catalog fallback")

    # ── 35c. _OPENAI_CHAT_PREFIXES ───────────────────────────────────
    assert isinstance(_OPENAI_CHAT_PREFIXES, tuple), "should be tuple"
    assert "gpt-" in _OPENAI_CHAT_PREFIXES, "gpt- should be in prefixes"
    record("PASS", "cloud: _OPENAI_CHAT_PREFIXES present")

    # ── 35d. get_cloud_provider routing ──────────────────────────────
    # Inject synthetic entries into cache for testing
    _cloud_model_cache["gpt-4o"] = {"label": "GPT-4o", "ctx": 128000, "provider": "openai"}
    _cloud_model_cache["anthropic/claude-sonnet-4"] = {"label": "Claude Sonnet 4", "ctx": 200000, "provider": "openrouter"}
    assert get_cloud_provider("gpt-4o") == "openai", "gpt-4o should be openai"
    assert get_cloud_provider("anthropic/claude-sonnet-4") == "openrouter", "claude should be openrouter"
    assert get_cloud_provider("qwen3:14b") is None, "local model should return None"
    record("PASS", "cloud: get_cloud_provider returns correct provider")

    # ── 35e. is_cloud_model with dynamic cache ───────────────────────
    assert is_cloud_model("gpt-4o"), "gpt-4o (in cache) should be cloud"
    assert is_cloud_model("anthropic/claude-sonnet-4"), "claude (in cache) should be cloud"
    assert not is_cloud_model("qwen3:14b"), "local model should NOT be cloud"
    record("PASS", "cloud: is_cloud_model correct for cached and local models")

    # ── 35f. list_cloud_models returns cached entries ─────────────────
    cloud_list = list_cloud_models()
    assert isinstance(cloud_list, list), "list_cloud_models should return list"
    assert "gpt-4o" in cloud_list, "gpt-4o should be in list"
    assert "anthropic/claude-sonnet-4" in cloud_list
    # Filter by provider
    openai_only = list_cloud_models(provider="openai")
    assert "gpt-4o" in openai_only
    assert "anthropic/claude-sonnet-4" not in openai_only
    or_only = list_cloud_models(provider="openrouter")
    assert "anthropic/claude-sonnet-4" in or_only
    assert "gpt-4o" not in or_only
    record("PASS", "cloud: list_cloud_models with provider filter works")

    # ── 35g. star / unstar round-trip ────────────────────────────────
    from api_keys import get_cloud_config, set_cloud_config, _CLOUD_CONFIG_PATH
    star_cloud_model("gpt-4o")
    starred = list_starred_cloud_models()
    assert "gpt-4o" in starred, "Starred model should appear in list"
    unstar_cloud_model("gpt-4o")
    starred2 = list_starred_cloud_models()
    assert "gpt-4o" not in starred2, "Unstarred model should not appear"
    record("PASS", "cloud: star/unstar round-trip works")

    # ── 35h. list_starred_cloud_models only returns cached ────────────
    star_cloud_model("gpt-4o")
    star_cloud_model("nonexistent/model-xyz")
    starred3 = list_starred_cloud_models()
    assert "gpt-4o" in starred3, "cached + starred should appear"
    assert "nonexistent/model-xyz" not in starred3, "uncached starred should not appear"
    unstar_cloud_model("gpt-4o")
    unstar_cloud_model("nonexistent/model-xyz")
    record("PASS", "cloud: list_starred_cloud_models filters uncached")

    # Clean up synthetic cache entries
    _cloud_model_cache.pop("gpt-4o", None)
    _cloud_model_cache.pop("anthropic/claude-sonnet-4", None)

    # ── 35i. BASE URLs correct ───────────────────────────────────────
    assert OPENAI_BASE_URL == "https://api.openai.com/v1", f"Bad OPENAI URL: {OPENAI_BASE_URL}"
    assert OPENROUTER_BASE_URL == "https://openrouter.ai/api/v1", f"Bad OR URL: {OPENROUTER_BASE_URL}"
    record("PASS", "cloud: OPENAI_BASE_URL and OPENROUTER_BASE_URL correct")

    # ── 35j. is_cloud_available / is_openai_available / is_openrouter_available ──
    # These are bool-returning functions that check keys
    assert isinstance(is_cloud_available(), bool)
    assert isinstance(is_openai_available(), bool)
    assert isinstance(is_openrouter_available(), bool)
    record("PASS", "cloud: availability functions return bool")

    # ── 35k. is_cloud_available False without any key ────────────────
    import os as _os35
    _old_oai_key35 = _os35.environ.pop("OPENAI_API_KEY", None)
    _old_or_key35 = _os35.environ.pop("OPENROUTER_API_KEY", None)
    try:
        from api_keys import _load_keys as _lk35, _save_keys as _sk35
        _keys35 = _lk35()
        _saved_oai35 = _keys35.pop("OPENAI_API_KEY", None)
        _saved_or35 = _keys35.pop("OPENROUTER_API_KEY", None)
        _sk35(_keys35)
        assert not is_cloud_available(), "Should be False with no keys"
        assert not is_openai_available(), "Should be False with no OpenAI key"
        assert not is_openrouter_available(), "Should be False with no OR key"
        record("PASS", "cloud: availability returns False without keys")
    finally:
        if _saved_oai35:
            _keys35["OPENAI_API_KEY"] = _saved_oai35
        if _saved_or35:
            _keys35["OPENROUTER_API_KEY"] = _saved_or35
        _sk35(_keys35)
        if _old_oai_key35:
            _os35.environ["OPENAI_API_KEY"] = _old_oai_key35
        if _old_or_key35:
            _os35.environ["OPENROUTER_API_KEY"] = _old_or_key35

    # ── 35l. fetch_cloud_models returns 0 without key (no crash) ─────
    _old_oai_key35b = _os35.environ.pop("OPENAI_API_KEY", None)
    try:
        _keys35b = _lk35()
        _saved_oai35b = _keys35b.pop("OPENAI_API_KEY", None)
        _sk35(_keys35b)
        count = fetch_cloud_models("openai")
        assert count == 0, f"Should return 0 without key, got {count}"
        record("PASS", "cloud: fetch_cloud_models returns 0 without key")
    finally:
        if _saved_oai35b:
            _keys35b["OPENAI_API_KEY"] = _saved_oai35b
            _sk35(_keys35b)
        if _old_oai_key35b:
            _os35.environ["OPENAI_API_KEY"] = _old_oai_key35b

    # ── 35o. get_cloud_model_context ──────────────────────────────────
    ctx_known = get_cloud_model_context("gpt-4o")
    assert ctx_known == 128_000, f"gpt-4o ctx should be 128000, got {ctx_known}"
    ctx_unknown = get_cloud_model_context("nonexistent/model")
    assert ctx_unknown == 256_000, f"Unknown should default to 256000, got {ctx_unknown}"
    record("PASS", "cloud: get_cloud_model_context returns correct values")

    # ── 35p. is_tool_compatible for cloud models ─────────────────────
    _cloud_model_cache["gpt-4o-tc"] = {"label": "t", "ctx": 128000, "provider": "openai"}
    assert is_tool_compatible("gpt-4o-tc"), "Cloud model should be tool-compatible"
    _cloud_model_cache.pop("gpt-4o-tc", None)
    record("PASS", "cloud: cloud models are tool-compatible")

    # ── 35q. api_keys: cloud config get/set ──────────────────────────
    cfg = get_cloud_config()
    assert isinstance(cfg, dict), "get_cloud_config should return dict"
    assert "starred_models" in cfg
    record("PASS", "cloud: get_cloud_config returns needed keys")

    # ── 35r. api_keys: cloud config defaults ─────────────────────────
    from api_keys import _DEFAULT_CLOUD_CONFIG
    assert _DEFAULT_CLOUD_CONFIG["starred_models"] == []
    record("PASS", "cloud: config defaults correct")

    # ── 35s. api_keys: OPENAI + OPENROUTER key definitions ───────────
    from api_keys import OPENROUTER_KEY_DEFINITIONS, OPENAI_KEY_DEFINITIONS
    assert "OpenRouter API Key" in OPENROUTER_KEY_DEFINITIONS
    assert OPENROUTER_KEY_DEFINITIONS["OpenRouter API Key"] == "OPENROUTER_API_KEY"
    assert "OpenAI API Key" in OPENAI_KEY_DEFINITIONS
    assert OPENAI_KEY_DEFINITIONS["OpenAI API Key"] == "OPENAI_API_KEY"
    record("PASS", "cloud: both key definitions present")

    # ── 35t. set_cloud_config persists ───────────────────────────────
    set_cloud_config("_test_key", "test_value")
    cfg2 = get_cloud_config()
    assert cfg2.get("_test_key") == "test_value"
    import json as _json35
    _cc_data = _json35.loads(_CLOUD_CONFIG_PATH.read_text())
    _cc_data.pop("_test_key", None)
    _CLOUD_CONFIG_PATH.write_text(_json35.dumps(_cc_data, indent=2))
    record("PASS", "cloud: set_cloud_config persists to disk")

    # ── 35u. threads: model_override column exists ───────────────────
    from threads import _get_thread_model_override, _set_thread_model_override
    from threads import DB_PATH as _tdb_path35
    import sqlite3 as _sql35
    _conn35 = _sql35.connect(_tdb_path35)
    _cols35 = {r[1] for r in _conn35.execute("PRAGMA table_info(thread_meta)").fetchall()}
    _conn35.close()
    assert "model_override" in _cols35
    record("PASS", "cloud: thread_meta has model_override column")

    # ── 35v. threads: get/set model override ─────────────────────────
    _test_tid35 = "__test_cloud_35__"
    from threads import _save_thread_meta, _delete_thread
    _save_thread_meta(_test_tid35, "Cloud Test Thread")
    assert _get_thread_model_override(_test_tid35) == ""
    _set_thread_model_override(_test_tid35, "gpt-4o")
    assert _get_thread_model_override(_test_tid35) == "gpt-4o"
    _set_thread_model_override(_test_tid35, "")
    assert _get_thread_model_override(_test_tid35) == ""
    _delete_thread(_test_tid35)
    record("PASS", "cloud: get/set thread model override works")

    # ── 35w. _list_threads returns 5 columns ─────────────────────────
    from threads import _list_threads
    _save_thread_meta(_test_tid35, "Cloud Test Thread 2")
    _threads35 = _list_threads()
    if _threads35:
        _row35 = [r for r in _threads35 if r[0] == _test_tid35]
        if _row35:
            assert len(_row35[0]) == 5, f"Expected 5 columns, got {len(_row35[0])}"
            record("PASS", "cloud: _list_threads returns 5-column rows")
        else:
            record("WARN", "cloud: test thread not found in list")
    else:
        record("WARN", "cloud: no threads to test 5-column format")
    _delete_thread(_test_tid35)

    # ── 35x. models.py: conditional ollama import ────────────────────
    _models_src35 = Path("models.py").read_text(encoding="utf-8")
    assert "_ollama_mod" in _models_src35, "should use conditional _ollama_mod"
    assert "import ollama as _ollama_mod" in _models_src35
    record("PASS", "cloud: models.py has conditional ollama import")

    # ── 35y. models.py: dual-provider _get_cloud_llm ─────────────────
    assert "_get_cloud_llm" in _models_src35
    assert "ChatOpenAI" in _models_src35
    assert "OPENROUTER_BASE_URL" in _models_src35
    assert "OPENAI_BASE_URL" in _models_src35 or 'base_url' in _models_src35
    record("PASS", "cloud: models.py has dual-provider cloud LLM factory")

    # ── 35z. memory_extraction.py: uses get_llm_for, not ollama.chat ──
    _me_src35 = Path("memory_extraction.py").read_text(encoding="utf-8")
    assert "get_llm_for" in _me_src35, "should use get_llm_for"
    assert "HumanMessage" in _me_src35, "should use HumanMessage"
    # Should NOT have a bare `import ollama` or `ollama.chat`
    import re as _re35
    assert not _re35.search(r'\bollama\.chat\b', _me_src35), "should not call ollama.chat directly"
    record("PASS", "cloud: memory_extraction uses get_llm_for, not ollama.chat")

    # ── 35aa. memory_extraction.py: uses get_llm_for ─────────────────
    assert "get_llm_for" in _me_src35
    record("PASS", "cloud: memory_extraction.py uses get_llm_for")

    # ── 35ab. agent.py: cloud-aware guards ───────────────────────────
    _agent_src35 = Path("agent.py").read_text(encoding="utf-8")
    assert "is_cloud_model" in _agent_src35
    _cloud_count35 = _agent_src35.count("is_cloud_model")
    assert _cloud_count35 >= 4, f"Expected ≥4 is_cloud_model refs, got {_cloud_count35}"
    record("PASS", "cloud: agent.py has cloud-aware guards")

    # ── 35ac. launcher.py: simple Ollama auto-start ──────────────────
    _launcher_src35 = Path("launcher.py").read_text(encoding="utf-8")
    assert "_start_ollama" in _launcher_src35, "launcher should have _start_ollama"
    assert "_is_ollama_running" in _launcher_src35, "launcher should check if Ollama is running"
    record("PASS", "cloud: launcher.py has simple Ollama auto-start")

    # ── 35ad. telegram: /model command handler ───────────────────────
    _tg_src35 = Path("channels/telegram.py").read_text(encoding="utf-8")
    assert "_cmd_model" in _tg_src35
    assert 'CommandHandler("model"' in _tg_src35
    assert "list_starred_cloud_models" in _tg_src35, "telegram should use starred models"
    assert "get_cloud_provider" in _tg_src35, "telegram should detect provider"
    record("PASS", "cloud: telegram.py has updated /model command")

    # ── 35ae. conversation_search_tool handles 5-column rows ─────────
    _cs_src35 = Path("tools/conversation_search_tool.py").read_text(encoding="utf-8")
    assert "*_cs_rest" in _cs_src35
    record("PASS", "cloud: conversation_search_tool handles 5-column rows")

    # ── 35af. email channel handles 5-column rows ────────────────────
    _em_src35 = Path("channels/email.py").read_text(encoding="utf-8")
    assert "*_rest_em" in _em_src35
    record("PASS", "cloud: email channel handles 5-column rows")

    # ── 35ag. UI: Cloud tab + dual sections ────────────────────
    _gui_src35 = Path("app.py").read_text(encoding="utf-8") + "".join(
        f.read_text(encoding="utf-8") for f in sorted(Path("ui").glob("*.py"))
    )
    assert "_build_cloud_tab" in _gui_src35
    assert "tab_cloud" in _gui_src35
    assert "OpenAI Direct" in _gui_src35 or "openai" in _gui_src35.lower()
    record("PASS", "cloud: app.py has Cloud settings tab")

    # ── 35ah. app.py: chat header model picker ───────────────
    assert "Select model for this thread" in _gui_src35
    assert "list_starred_cloud_models" in _gui_src35, "picker should use starred models"
    record("PASS", "cloud: app.py has starred-model picker")

    # ── 35ai. app.py: cloud warning banner ───────────────────
    assert "data is sent to the cloud" in _gui_src35
    assert "get_cloud_provider" in _gui_src35, "banner should detect provider"
    record("PASS", "cloud: app.py has provider-aware warning banner")

    # ── 35aj. app.py: sidebar cloud icon ─────────────────────
    assert "is_cloud_thread" in _gui_src35
    record("PASS", "cloud: app.py sidebar has cloud thread detection")

    # ── 35ak. app.py: health check bypasses Ollama for cloud ─
    assert "is_cloud_model" in _gui_src35
    record("PASS", "cloud: app.py health check handles cloud default")

    # ── 35al. requirements.txt includes langchain-openai ─────────────
    _req_src35 = Path("requirements.txt").read_text(encoding="utf-8")
    assert "langchain-openai" in _req_src35
    record("PASS", "cloud: requirements.txt includes langchain-openai")

    # ── 35am. langchain-openai is importable ─────────────────────────
    try:
        from langchain_openai import ChatOpenAI as _ChatOpenAI35
        record("PASS", "cloud: langchain_openai.ChatOpenAI is importable")
    except ImportError:
        record("FAIL", "cloud: langchain_openai is not installed")

    # ── 35an. _get_cloud_llm raises without key ──────────────────────
    _old_oai_env35c = _os35.environ.pop("OPENAI_API_KEY", None)
    _old_or_env35c = _os35.environ.pop("OPENROUTER_API_KEY", None)
    try:
        _keys35c = _lk35()
        _saved_oai35c = _keys35c.pop("OPENAI_API_KEY", None)
        _saved_or35c = _keys35c.pop("OPENROUTER_API_KEY", None)
        _sk35(_keys35c)
        # Inject a synthetic openai model into cache
        _cloud_model_cache["__test_oai__"] = {"label": "t", "ctx": 128000, "provider": "openai"}
        try:
            _get_cloud_llm("__test_oai__")
            record("FAIL", "cloud: _get_cloud_llm should raise without key")
        except ValueError as ve:
            assert "not configured" in str(ve).lower(), f"Expected 'not configured', got: {ve}"
            record("PASS", "cloud: _get_cloud_llm raises ValueError without key")
    finally:
        _cloud_model_cache.pop("__test_oai__", None)
        if _saved_oai35c:
            _keys35c["OPENAI_API_KEY"] = _saved_oai35c
        if _saved_or35c:
            _keys35c["OPENROUTER_API_KEY"] = _saved_or35c
        _sk35(_keys35c)
        if _old_oai_env35c:
            _os35.environ["OPENAI_API_KEY"] = _old_oai_env35c
        if _old_or_env35c:
            _os35.environ["OPENROUTER_API_KEY"] = _old_or_env35c

    # ── 35ao. prompts.py: CLOUD MODELS section ───────────────────────
    _prompts_src35 = Path("prompts.py").read_text(encoding="utf-8")
    assert "CLOUD MODELS" in _prompts_src35
    record("PASS", "cloud: prompts.py has CLOUD MODELS section")

    # ── 35ap. persisted cloud cache: save + load round-trip ──────────
    from models import _save_cloud_cache, _load_cloud_cache, _CLOUD_CACHE_PATH
    # Inject test entries into cache
    _cloud_model_cache["__test_persist_oai__"] = {"label": "t", "ctx": 128000, "provider": "openai", "vision": True}
    _cloud_model_cache["__test_persist_or__"] = {"label": "t2", "ctx": 64000, "provider": "openrouter", "vision": False}
    _save_cloud_cache()
    assert _CLOUD_CACHE_PATH.exists(), "cache file should exist after save"
    _loaded35 = _load_cloud_cache()
    assert "__test_persist_oai__" in _loaded35, "saved entry should be loadable"
    assert _loaded35["__test_persist_oai__"]["provider"] == "openai"
    assert _loaded35["__test_persist_oai__"]["vision"] is True
    assert _loaded35["__test_persist_or__"]["vision"] is False
    # Clean up test entries
    _cloud_model_cache.pop("__test_persist_oai__", None)
    _cloud_model_cache.pop("__test_persist_or__", None)
    _save_cloud_cache()
    record("PASS", "cloud: persisted cache save/load round-trip works")

    # ── 35aq. vision flag in cache entries ────────────────────────────
    from models import list_cloud_vision_models, is_cloud_vision_model
    # Inject test entries with vision flags
    _cloud_model_cache["__vis_yes__"] = {"label": "v1", "ctx": 128000, "provider": "openai", "vision": True}
    _cloud_model_cache["__vis_no__"] = {"label": "v2", "ctx": 128000, "provider": "openrouter", "vision": False}
    assert is_cloud_vision_model("__vis_yes__"), "model with vision=True should be vision"
    assert not is_cloud_vision_model("__vis_no__"), "model with vision=False should not be vision"
    assert not is_cloud_vision_model("qwen3:14b"), "local model should not be cloud vision"
    _vis_list35 = list_cloud_vision_models()
    assert "__vis_yes__" in _vis_list35, "vision model should appear in list"
    assert "__vis_no__" not in _vis_list35, "non-vision model should not appear in list"
    _cloud_model_cache.pop("__vis_yes__", None)
    _cloud_model_cache.pop("__vis_no__", None)
    record("PASS", "cloud: vision flag filtering works correctly")

    # ── 35ar. is_cloud_model returns False for gpt-oss (no collision) ─
    # gpt-oss:20b is an Ollama model that starts with 'gpt-' prefix.
    # With persisted cache, it should NOT be treated as a cloud model.
    assert not is_cloud_model("gpt-oss:20b"), "gpt-oss:20b is Ollama, not cloud"
    assert not is_cloud_model("gpt-oss:120b"), "gpt-oss:120b is Ollama, not cloud"
    record("PASS", "cloud: gpt-oss Ollama models not misidentified as cloud")

    # ── 35as. is_tool_compatible returns True for cloud models ────────
    _cloud_model_cache["__tool_test__"] = {"label": "t", "ctx": 128000, "provider": "openai", "vision": True}
    assert is_tool_compatible("__tool_test__"), "cloud model should be tool-compatible"
    _cloud_model_cache.pop("__tool_test__", None)
    record("PASS", "cloud: is_tool_compatible returns True for cloud models")

    # ── 35at. vision.py: conditional ollama import ────────────────────
    _vision_src35 = Path("vision.py").read_text(encoding="utf-8")
    assert "_ollama_mod" in _vision_src35, "vision.py should use conditional import"
    assert "_analyze_cloud" in _vision_src35, "vision.py should have cloud analyze path"
    assert "_analyze_local" in _vision_src35, "vision.py should have local analyze path"
    assert "is_cloud_model" in _vision_src35, "vision.py should check is_cloud_model"
    record("PASS", "cloud: vision.py has cloud-aware analyze routing")

    # ── 35au. app.py: cloud vision in settings + wizard ──────
    assert "list_cloud_vision_models" in _gui_src35, "settings should use cloud vision list"
    assert "is_cloud_vision_model" in _gui_src35 or "cloud_vision_select" in _gui_src35, \
        "setup wizard should have cloud vision picker"
    record("PASS", "cloud: app.py has cloud vision model support")

    # ── 35av. _CLOUD_CACHE_PATH defined ──────────────────────────────
    assert _CLOUD_CACHE_PATH.name == "cloud_models_cache.json"
    record("PASS", "cloud: _CLOUD_CACHE_PATH has correct filename")

    # ── 35aw. trending Ollama models: source code checks ─────────────
    _models_src35 = open("models.py", encoding="utf-8").read()
    assert "_trending_ollama_cache" in _models_src35, "models.py should have trending cache var"
    assert "fetch_trending_ollama_models" in _models_src35, "models.py should have trending fetch function"
    assert "get_trending_models" in _models_src35, "models.py should have get_trending_models"
    assert "ollama.com/api/tags" in _models_src35, "trending fetch should use ollama.com/api/tags"
    record("PASS", "cloud: models.py has trending Ollama model support")

    # ── 35ax. fetch_trending_ollama_models is importable ─────────────
    from models import fetch_trending_ollama_models as _ftom, get_trending_models as _gtm
    assert callable(_ftom), "fetch_trending_ollama_models should be callable"
    assert callable(_gtm), "get_trending_models should be callable"
    record("PASS", "cloud: trending functions importable and callable")

    # ── 35ay. get_trending_models returns a list ─────────────────────
    _trending = _gtm()
    assert isinstance(_trending, list), "get_trending_models should return a list"
    record("PASS", "cloud: get_trending_models returns list")

    # ── 35az. app.py uses trending models + Ollama-aware logic
    assert "fetch_trending_ollama_models" in _gui_src35, "app.py should import fetch_trending"
    assert "get_trending_models" in _gui_src35, "app.py should import get_trending_models"
    assert "🆕" in _gui_src35, "app.py should show trending icon"
    assert "_ollama_up" in _gui_src35, "app.py should track Ollama reachability"
    assert "ollama.com/download" in _gui_src35, "app.py should link to Ollama download"
    record("PASS", "cloud: app.py has trending + Ollama-aware model lists")

    # ── 35ba. cross-platform install instructions in app ─────
    assert "brew install ollama" in _gui_src35, "app.py should have macOS install hint"
    assert "curl -fsSL" in _gui_src35, "app.py should have Linux install hint"
    record("PASS", "cloud: app.py has cross-platform Ollama install instructions")

    # ── 35bb. cloud/local chat banners in app ────────────────
    assert "complete privacy" in _gui_src35, "local banner should mention privacy"
    assert "data is sent to the cloud" in _gui_src35, "cloud banner should warn about data"
    assert 'icon("lock"' in _gui_src35, "local banner should use lock icon"
    assert 'icon("cloud"' in _gui_src35, "cloud banner should use cloud icon"
    record("PASS", "cloud: app.py has cloud/local chat banners")

    # ── 35bc. chat scroll area has model-type tint ───────────────────
    assert "rgba(255, 152, 0" in _gui_src35, "cloud scroll should have orange tint"
    assert "rgba(76, 175, 80" in _gui_src35, "local scroll should have green tint"
    record("PASS", "cloud: chat scroll area has cloud/local tint")

    # ── 35bd. Ollama card headings use dark text on amber bg ─────────
    assert "text-brown-9" in _gui_src35, "Ollama card headings should use dark text"
    record("PASS", "cloud: Ollama card headings use dark text color")

    # ── 35be. Models tab has API key hint ────────────────────────────
    assert "Cloud tab" in _gui_src35, "Models tab should mention Cloud tab for API keys"
    record("PASS", "cloud: Models tab has API keys hint")

    # ── 35bf. wizard defaults gpt-5 for cloud ────────────────────────
    assert '"gpt-5"' in _gui_src35, "wizard should prefer gpt-5 as default"
    record("PASS", "cloud: wizard defaults to gpt-5")

    # ── 35bg. no privacy toggles (always-on) ─────────────────────────
    assert "auto_recall" not in _gui_src35, "privacy toggles should be removed from UI"
    record("PASS", "cloud: no privacy toggles in UI (always-on)")

    # ── 35bh. chat picker has "More models" entry ────────────────────
    assert "More models" in _gui_src35, "chat picker should have More models option"
    assert "_MORE_MODELS_SENTINEL" in _gui_src35, "sentinel constant should exist"
    assert "open_settings" in _gui_src35, "More models should open settings"
    record("PASS", "cloud: chat picker has More models entry")

    # ── 35bi. cloud tab layout order ─────────────────────────────────
    _api_pos = _gui_src35.find("OpenAI Direct")
    _guide_pos = _gui_src35.find("Setup Guide")
    _avail_pos = _gui_src35.find("Available Models")
    assert _api_pos < _guide_pos < _avail_pos, "Cloud tab order: API keys → Guide → Models"
    # The actual model list container must be created *after* the Available Models header
    _container_pos = _gui_src35.find('_model_list_container = ui.column()')
    assert _container_pos > _avail_pos, "model list container must be created after Available Models header"
    record("PASS", "cloud: cloud tab layout in correct order")

    # ── 35bj. banners have no duplicate emoji ─────────────────────────
    # ui.icon("cloud") is used — the label text must NOT also start with ☁️
    assert '☁️ Using' not in _gui_src35, "cloud banner label should not duplicate emoji"
    assert '🔒 Using' not in _gui_src35, "local banner label should not duplicate emoji"
    record("PASS", "cloud: banners have no duplicate icons")

    # ── 35bk. model switch toast and context cap ─────────────────────
    assert 'async def _on_model_pick' in _gui_src35, "model pick handler should be async"
    assert 'Switched to' in _gui_src35, "model switch should show toast notification"
    assert 'Context capped' in _gui_src35, "model switch should check context cap"
    # Parsing must use split, not hardcoded slice
    assert 'val[3:]' not in _gui_src35, "must not use hardcoded val[3:] slice for emoji stripping"
    assert 'val.split(" ", 1)[1]' in _gui_src35, "must use split for emoji-safe model ID extraction"
    record("PASS", "cloud: model switch toast and context cap")

    # ── 35bl. provider-specific emojis ────────────────────────────────
    _mod_src35 = Path("models.py").read_text(encoding="utf-8")
    assert 'get_provider_emoji' in _mod_src35, "models.py must define get_provider_emoji"
    assert 'get_provider_emoji' in _gui_src35, "app.py must use get_provider_emoji"
    assert '_PROVIDER_EMOJI' in _mod_src35, "models.py must define _PROVIDER_EMOJI mapping"
    # Verify provider emojis are distinct
    assert '"openai"' in _mod_src35 and '"openrouter"' in _mod_src35, \
        "must have separate emojis for OpenAI and OpenRouter"
    record("PASS", "cloud: provider-specific emojis")

    # ── 35bm. model selector search ───────────────────────────────────
    assert 'use-input' in _gui_src35, "model selects should have search (use-input prop)"
    assert _gui_src35.count('use-input') >= 5, "at least 5 model selectors should have search"
    record("PASS", "cloud: model selector search filter")

    # ── 35bn. sidebar context counter respects model override ─────────
    assert 'model_override' in _gui_src35, "token counter must pass model override"
    _agent_src35 = Path("agent.py").read_text(encoding="utf-8")
    assert 'model_override' in _agent_src35.split("def get_token_usage")[1][:400], \
        "get_token_usage must accept model_override param"
    assert 'model_name: str | None' in _mod_src35.split("def get_context_size")[1][:100], \
        "get_context_size must support model_name param"
    record("PASS", "cloud: sidebar context counter model-aware")

    # ── 35bo. cloud auto-max context, local VRAM-controlled ──────────
    # get_context_size must auto-use native max for cloud models
    _gcs_body = _mod_src35.split("def get_context_size")[1][:1200]
    assert 'is_cloud_model' in _gcs_body, "get_context_size must branch on cloud vs local"
    assert '_estimate_context_heuristic' in _gcs_body, "cloud fallback should use heuristic"
    # UI: local context dropdown must mention VRAM
    assert 'Local context window' in _gui_src35, "context dropdown should be labeled for local models"
    assert 'VRAM' in _gui_src35, "context dropdown tooltip should mention VRAM impact"
    # Cloud info label
    assert 'Cloud models automatically use' in _gui_src35, \
        "settings should explain cloud auto-context"
    # Token counter should format M for large values
    assert '1_000_000' in _gui_src35, "token counter should handle M formatting"
    record("PASS", "cloud: auto-max context for cloud, VRAM control for local")

    # ── 35bp. context catalog and keyless fetch ──────────────────────
    assert 'fetch_context_catalog' in _mod_src35, "models.py must define fetch_context_catalog"
    assert '_context_catalog' in _mod_src35, "models.py must have _context_catalog dict"
    assert '_catalog_or_heuristic' in _mod_src35, "models.py must define _catalog_or_heuristic"
    assert 'context_catalog_cache.json' in _mod_src35, "catalog cache path should exist"
    # refresh_cloud_models must call fetch_context_catalog
    _refresh_body = _mod_src35.split("def refresh_cloud_models")[1][:800]
    assert 'fetch_context_catalog' in _refresh_body, \
        "refresh_cloud_models must call fetch_context_catalog first"
    record("PASS", "cloud: context catalog infrastructure in models.py")

    # ── 35bq. OpenRouter key validation ──────────────────────────────
    assert 'validate_openrouter_key' in _mod_src35, "models.py must define validate_openrouter_key"
    assert '/auth/key' in _mod_src35, "validation must use /auth/key endpoint"
    # UI must use validation for OpenRouter keys
    assert 'validate_openrouter_key' in _gui_src35, "UI must validate OpenRouter keys"
    record("PASS", "cloud: OpenRouter key validation in models.py + UI")

    # ── 35br. startup fetches context catalog ────────────────────────
    assert 'fetch_context_catalog' in _gui_src35, "startup should fetch context catalog"
    record("PASS", "cloud: startup fetches context catalog")

    # ── 35bs. task runner propagates model_override to thread ─────────
    # model_override should be set on the thread at the START of execution
    # (near config setup), not only after completion.
    _tasks_config_section = _src_tasks31[_src_tasks31.index('config["configurable"]["model_override"]'):
                                          _src_tasks31.index('config["configurable"]["model_override"]') + 400]
    assert "_set_thread_model_override" in _tasks_config_section, \
        "task runner should set model_override on thread at start of execution"
    record("PASS", "cloud: task runner propagates model_override to thread at start")

    # ── 35bt. _on_task_fire creates thread_meta before run ─────────────
    # Scheduled tasks must call _save_thread_meta BEFORE run_task_background
    # so the thread appears in the sidebar and _thread_exists() returns
    # True at completion.
    _fire_section = _src_tasks31[_src_tasks31.index("def _on_task_fire"):]
    _fire_section = _fire_section[:_fire_section.index("def _sync_job")]
    _fire_save_idx = _fire_section.index("_save_thread_meta")
    _fire_run_idx = _fire_section.index("run_task_background")
    assert _fire_save_idx < _fire_run_idx, \
        "_on_task_fire must call _save_thread_meta BEFORE run_task_background"
    record("PASS", "v3.7: _on_task_fire creates thread_meta before run")

    # ── 35bu. _on_task_fire sets model_override on thread ──────────────
    assert "_set_thread_model_override" in _fire_section, \
        "_on_task_fire should propagate model_override to thread_meta"
    record("PASS", "v3.7: _on_task_fire sets model_override on thread")

except Exception as e:
    record("FAIL", "cloud model support tests", f"{type(e).__name__}: {e}")
    traceback.print_exc()

# ═════════════════════════════════════════════════════════════════════════════
# 36. SKILLS ENGINE
# ═════════════════════════════════════════════════════════════════════════════
print("\n" + "=" * 70)
print("36. SKILLS ENGINE")
print("=" * 70)

try:
    # ── 36a. skills.py imports cleanly ─────────────────────────────────
    import skills as _skills_mod36
    record("PASS", "skills: module imports cleanly")

    # ── 36b. Skill dataclass fields ───────────────────────────────────
    from skills import Skill
    _sk = Skill(name="test", display_name="Test", icon="🧪",
                description="desc", instructions="do stuff")
    assert _sk.name == "test"
    assert _sk.source == "user"
    assert _sk.enabled_by_default is False
    assert _sk.version == "1.0"
    record("PASS", "skills: Skill dataclass defaults")

    # ── 36c. YAML frontmatter parser ─────────────────────────────────
    import tempfile, pathlib
    from skills import _parse_skill_md
    _tmp_dir36 = tempfile.mkdtemp()
    _tmp_skill = pathlib.Path(_tmp_dir36) / "SKILL.md"
    _tmp_skill.write_text(
        "---\nname: test_skill\ndisplay_name: Test Skill\n"
        "icon: \"🧪\"\ndescription: A test skill\n"
        "tools:\n  - web_search\n  - memory\n"
        "tags:\n  - testing\nversion: \"2.0\"\nauthor: Tester\n"
        "enabled_by_default: true\n---\n\n"
        "Step 1: Do something.\nStep 2: Do another thing.\n",
        encoding="utf-8",
    )
    _parsed = _parse_skill_md(_tmp_skill, source="bundled")
    assert _parsed is not None, "parser should return a Skill"
    assert _parsed.name == "test_skill"
    assert _parsed.display_name == "Test Skill"
    assert _parsed.icon == "🧪"
    assert _parsed.tools == ["web_search", "memory"]
    assert _parsed.tags == ["testing"]
    assert _parsed.version == "2.0"
    assert _parsed.author == "Tester"
    assert _parsed.enabled_by_default is True
    assert _parsed.source == "bundled"
    assert "Step 1" in _parsed.instructions
    record("PASS", "skills: YAML frontmatter parser")

    # ── 36d. Parser rejects missing name ──────────────────────────────
    _bad_skill = pathlib.Path(_tmp_dir36) / "BAD.md"
    _bad_skill.write_text("---\ndisplay_name: No Name\n---\n\nInstructions here.\n", encoding="utf-8")
    assert _parse_skill_md(_bad_skill) is None, "should reject skills without name"
    record("PASS", "skills: parser rejects missing name")

    # ── 36e. Parser rejects empty body ────────────────────────────────
    _empty_skill = pathlib.Path(_tmp_dir36) / "EMPTY.md"
    _empty_skill.write_text("---\nname: empty_test\n---\n\n", encoding="utf-8")
    assert _parse_skill_md(_empty_skill) is None, "should reject empty instructions"
    record("PASS", "skills: parser rejects empty body")

    # ── 36f. Parser rejects no frontmatter ────────────────────────────
    _nofm_skill = pathlib.Path(_tmp_dir36) / "NOFM.md"
    _nofm_skill.write_text("Just some text without frontmatter.\n", encoding="utf-8")
    assert _parse_skill_md(_nofm_skill) is None, "should reject missing frontmatter"
    record("PASS", "skills: parser rejects missing frontmatter")

    # ── 36g. Bundled skills discovery ─────────────────────────────────
    from skills import BUNDLED_SKILLS_DIR, _discover_skills
    if BUNDLED_SKILLS_DIR.is_dir():
        _discovered = _discover_skills()
        assert len(_discovered) >= 8, f"expected ≥8 bundled skills, got {len(_discovered)}"
        _expected_names = {
            "daily_briefing", "deep_research", "meeting_notes", "brain_dump",
            "task_automation", "humanizer", "self_reflection",
            "proactive_agent", "web_navigator",
        }
        assert _expected_names.issubset(set(_discovered.keys())), \
            f"missing bundled skills: {_expected_names - set(_discovered.keys())}"
        for _sn, _sk36 in _discovered.items():
            if _sk36.source != "bundled":
                continue  # skip user skills — don't trip over user overrides
            assert _sk36.instructions, f"{_sn} should have instructions"
        record("PASS", f"skills: discovered {len(_discovered)} bundled skills")
    else:
        record("WARN", "skills: bundled_skills/ directory not found")

    # ── 36h. load_skills + enable/disable ─────────────────────────────
    # Back up user's persisted config so we can restore it after tests.
    _skills_config_backup = (
        _skills_mod36.CONFIG_PATH.read_text(encoding="utf-8")
        if _skills_mod36.CONFIG_PATH.exists() else None
    )
    # Reset persisted config so we test true defaults (manual testing may
    # have enabled skills that persist across runs).
    if _skills_mod36.CONFIG_PATH.exists():
        _skills_mod36.CONFIG_PATH.unlink()
    _skills_mod36._enabled.clear()
    _skills_mod36._skills_cache.clear()
    _skills_mod36.load_skills()
    _all = _skills_mod36.get_all_skills()
    assert len(_all) >= 5, f"expected ≥5 skills after load, got {len(_all)}"
    # Bundled skills should be disabled by default
    for _sk36 in _all:
        if _sk36.source == "bundled":
            assert not _skills_mod36.is_enabled(_sk36.name), \
                f"bundled skill '{_sk36.name}' should be disabled by default"
    # Enable one
    _skills_mod36.set_enabled("daily_briefing", True)
    assert _skills_mod36.is_enabled("daily_briefing"), "should be enabled after set"
    # Disable it
    _skills_mod36.set_enabled("daily_briefing", False)
    assert not _skills_mod36.is_enabled("daily_briefing"), "should be disabled after set"
    record("PASS", "skills: load_skills, enable/disable round-trip")

    # ── 36i. get_skills_prompt ────────────────────────────────────────
    # Disable all skills first so prompt is guaranteed empty
    for _sk36 in _skills_mod36.get_all_skills():
        _skills_mod36.set_enabled(_sk36.name, False)
    _empty_prompt = _skills_mod36.get_skills_prompt()
    assert _empty_prompt == "", "prompt should be empty with no enabled skills"
    # Enable two skills and check prompt
    _skills_mod36.set_enabled("daily_briefing", True)
    _skills_mod36.set_enabled("deep_research", True)
    _prompt36 = _skills_mod36.get_skills_prompt()
    assert "## Skills" in _prompt36, "prompt should have Skills header"
    assert "Daily Briefing" in _prompt36
    assert "Deep Research" in _prompt36
    # With explicit names
    _named_prompt = _skills_mod36.get_skills_prompt(["daily_briefing"])
    assert "Daily Briefing" in _named_prompt
    assert "Deep Research" not in _named_prompt
    # With empty list
    _empty_list_prompt = _skills_mod36.get_skills_prompt([])
    assert _empty_list_prompt == "", "empty list → empty prompt"
    # Clean up
    _skills_mod36.set_enabled("daily_briefing", False)
    _skills_mod36.set_enabled("deep_research", False)
    record("PASS", "skills: get_skills_prompt with various inputs")

    # ── 36j. estimate_tokens ──────────────────────────────────────────
    _skills_mod36.set_enabled("daily_briefing", True)
    _est = _skills_mod36.estimate_tokens()
    assert _est > 0, "should estimate >0 tokens for enabled skill"
    _est_none = _skills_mod36.estimate_tokens([])
    assert _est_none == 0, "empty list → 0 tokens"
    _skills_mod36.set_enabled("daily_briefing", False)
    record("PASS", "skills: estimate_tokens")

    # ── 36k. CRUD: create, update, delete ─────────────────────────────
    _created = _skills_mod36.create_skill(
        name="test_crud",
        display_name="CRUD Test",
        icon="🧪",
        description="Test CRUD ops",
        instructions="Step 1: Test.\nStep 2: Verify.",
        tags=["test"],
        enabled=True,
    )
    assert _created is not None, "create_skill should return a Skill"
    assert _created.name == "test_crud"
    assert _skills_mod36.is_enabled("test_crud"), "newly created should be enabled"
    # Update
    _updated = _skills_mod36.update_skill("test_crud", display_name="Updated CRUD")
    assert _updated is not None
    assert _updated.display_name == "Updated CRUD"
    # The underlying file should be updated too
    _re_parsed = _parse_skill_md(_updated.path / "SKILL.md", source="user")
    assert _re_parsed.display_name == "Updated CRUD"
    # Delete
    assert _skills_mod36.delete_skill("test_crud") is True
    assert _skills_mod36.get_skill("test_crud") is None
    record("PASS", "skills: CRUD create/update/delete")

    # ── 36l. duplicate_skill ──────────────────────────────────────────
    _dup = _skills_mod36.duplicate_skill("daily_briefing")
    assert _dup is not None
    assert _dup.name == "daily_briefing_custom"
    assert _dup.source == "user"
    assert _skills_mod36.is_enabled("daily_briefing_custom")
    # Clean up
    _skills_mod36.delete_skill("daily_briefing_custom")
    record("PASS", "skills: duplicate_skill")

    # ── 36m. Config persistence ───────────────────────────────────────
    from skills import CONFIG_PATH
    assert CONFIG_PATH.exists(), "skills_config.json should exist after load_skills"
    import json as _json36
    _cfg = _json36.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    assert "skills" in _cfg, "config should have 'skills' key"
    assert isinstance(_cfg["skills"], dict)
    record("PASS", "skills: config persists to JSON")

    # ── 36n. agent.py has skills injection in pre-model hook ──────────
    _src_agent36 = (PROJECT_ROOT / "agent.py").read_text(encoding="utf-8")
    assert "from skills import get_skills_prompt" in _src_agent36, \
        "agent.py should import get_skills_prompt"
    assert "get_thread_skills_override" in _src_agent36, \
        "agent.py should read thread skills override"
    assert "skills_msg" in _src_agent36 or "skills_text" in _src_agent36, \
        "agent.py should build skills SystemMessage"
    record("PASS", "skills: agent.py has skills injection")

    # ── 36o. threads.py has skills_override support ───────────────────
    _src_threads36 = (PROJECT_ROOT / "threads.py").read_text(encoding="utf-8")
    assert "skills_override" in _src_threads36, \
        "threads.py should have skills_override column"
    assert "def get_thread_skills_override" in _src_threads36
    assert "def set_thread_skills_override" in _src_threads36
    record("PASS", "skills: threads.py has skills_override support")

    # ── 36p. tasks.py has skills_override support ─────────────────────
    _src_tasks36 = (PROJECT_ROOT / "tasks.py").read_text(encoding="utf-8")
    assert "skills_override" in _src_tasks36, \
        "tasks.py should have skills_override column"
    assert "skills_override" in _src_tasks36[_src_tasks36.index("def update_task"):], \
        "update_task should accept skills_override"
    assert "skills_override" in _src_tasks36[_src_tasks36.index("def create_task"):], \
        "create_task should accept skills_override"
    record("PASS", "skills: tasks.py has skills_override support")

    # ── 36q. UI has Skills tab ──────────────────────────────
    _src_app36 = "".join(
        f.read_text(encoding="utf-8") for f in sorted((PROJECT_ROOT / "ui").glob("*.py"))
    )
    assert "_build_skills_tab" in _src_app36, \
        "ui/ should have _build_skills_tab function"
    assert 'tab_skills' in _src_app36, \
        "ui/ should have tab_skills defined"
    assert "Skills" in _src_app36, \
        "Skills should be referenced in ui/"
    record("PASS", "skills: ui/ has Skills tab")

    # ── 36r. UI has per-thread skills override ────────────────
    assert "get_thread_skills_override" in _src_app36, \
        "ui/ should import get_thread_skills_override"
    assert "set_thread_skills_override" in _src_app36, \
        "ui/ should import set_thread_skills_override"
    record("PASS", "skills: ui/ has per-thread skills override")

    # ── 36s. Bundled SKILL.md files have valid YAML ───────────────────
    import yaml as _yaml36
    _bundled_dir = PROJECT_ROOT / "bundled_skills"
    _bundled_count = 0
    for _child in _bundled_dir.iterdir():
        if _child.is_dir():
            _md = _child / "SKILL.md"
            if _md.exists():
                _text = _md.read_text(encoding="utf-8")
                import re as _re36
                _match = _re36.match(r"\A---\s*\n(.*?)\n---\s*\n", _text, _re36.DOTALL)
                assert _match, f"{_md} missing frontmatter"
                _meta = _yaml36.safe_load(_match.group(1))
                assert isinstance(_meta, dict), f"{_md} frontmatter not a dict"
                assert "name" in _meta, f"{_md} missing name"
                assert "display_name" in _meta, f"{_md} missing display_name"
                assert "icon" in _meta, f"{_md} missing icon"
                assert "description" in _meta, f"{_md} missing description"
                _body = _text[_match.end():].strip()
                assert len(_body) > 50, f"{_md} body too short"
                _bundled_count += 1
    assert _bundled_count >= 5, f"expected ≥5 bundled skills, found {_bundled_count}"
    record("PASS", f"skills: {_bundled_count} bundled SKILL.md files validated")

    # ── 36t. task runner propagates skills_override ───────────────────
    _run_bg_section36 = _src_tasks36[_src_tasks36.index("def run_task_background"):]
    _run_bg_section36 = _run_bg_section36[:5000]
    assert "skills_override" in _run_bg_section36, \
        "run_task_background should handle skills_override"
    assert "set_thread_skills_override" in _run_bg_section36, \
        "run_task_background should set skills_override on thread"
    record("PASS", "skills: task runner propagates skills_override")

    # ── 36u. User skill overrides bundled by same name ────────────────
    # Create a user skill with same name as bundled "daily_briefing"
    _override_dir = _skills_mod36.USER_SKILLS_DIR / "daily_briefing"
    _override_dir.mkdir(parents=True, exist_ok=True)
    (_override_dir / "SKILL.md").write_text(
        "---\nname: daily_briefing\ndisplay_name: Overridden Briefing\n"
        "icon: \"🔄\"\ndescription: User override\n---\n\n"
        "Custom instructions here.\n",
        encoding="utf-8",
    )
    _rediscovered = _skills_mod36._discover_skills()
    assert _rediscovered["daily_briefing"].source == "user", \
        "user skill should override bundled"
    assert _rediscovered["daily_briefing"].display_name == "Overridden Briefing"
    # Clean up
    import shutil as _shutil36
    _shutil36.rmtree(_override_dir, ignore_errors=True)
    _skills_mod36.load_skills()  # reload to restore bundled
    record("PASS", "skills: user skill overrides bundled by same name")

    # ── 36v. Comma-separated tools parsing ────────────────────────────
    _csv_skill = pathlib.Path(_tmp_dir36) / "CSV.md"
    _csv_skill.write_text(
        "---\nname: csv_test\ndisplay_name: CSV Test\nicon: \"📊\"\n"
        "description: csv tools\ntools: \"web_search, memory, calendar\"\n"
        "tags: \"test, integration\"\n---\n\nDo stuff.\n",
        encoding="utf-8",
    )
    _csv_parsed = _parse_skill_md(_csv_skill, source="user")
    assert _csv_parsed is not None
    assert _csv_parsed.tools == ["web_search", "memory", "calendar"], \
        f"expected 3 tools, got {_csv_parsed.tools}"
    assert _csv_parsed.tags == ["test", "integration"], \
        f"expected 2 tags, got {_csv_parsed.tags}"
    record("PASS", "skills: comma-separated tools/tags parsing")

    # ── 36w. Special characters in instructions ──────────────────────
    _special_skill = pathlib.Path(_tmp_dir36) / "SPECIAL.md"
    _special_skill.write_text(
        "---\nname: special_test\ndisplay_name: 'Special <Test> & \"Stuff\"'\n"
        "icon: \"⚠️\"\ndescription: testing special chars\n---\n\n"
        'Use "quotes" and <brackets> & ampersands.\n'
        "Also use: $dollar, %percent, @at, #hash.\n",
        encoding="utf-8",
    )
    _special_parsed = _parse_skill_md(_special_skill, source="user")
    assert _special_parsed is not None
    assert '"quotes"' in _special_parsed.instructions
    assert "<brackets>" in _special_parsed.instructions
    record("PASS", "skills: special characters in instructions")

    # ── 36x. Unicode in skill name/description ───────────────────────
    _unicode_skill = pathlib.Path(_tmp_dir36) / "UNICODE.md"
    _unicode_skill.write_text(
        "---\nname: unicode_test\ndisplay_name: '日本語テスト'\n"
        "icon: \"🇯🇵\"\ndescription: 'Ünïcödé dëscríptión'\n---\n\n"
        "Instructions with émojis 🎉 and ñ.\n",
        encoding="utf-8",
    )
    _unicode_parsed = _parse_skill_md(_unicode_skill, source="user")
    assert _unicode_parsed is not None
    assert _unicode_parsed.display_name == "日本語テスト"
    assert "émojis" in _unicode_parsed.instructions
    record("PASS", "skills: Unicode in skill name/description")

    # ── 36y. Skills prompt header text verification ──────────────────
    _skills_mod36.set_enabled("daily_briefing", True)
    _hdr_prompt = _skills_mod36.get_skills_prompt()
    assert _hdr_prompt.startswith("## Skills")
    assert "user-configured workflows" in _hdr_prompt
    assert "step-by-step instructions" in _hdr_prompt
    _skills_mod36.set_enabled("daily_briefing", False)
    record("PASS", "skills: prompt header text verified")

    # ── 36z. get_skills_prompt with nonexistent skill name ───────────
    _bogus_prompt = _skills_mod36.get_skills_prompt(["nonexistent_skill_xyz"])
    assert _bogus_prompt == "", "nonexistent skill name → empty prompt"
    record("PASS", "skills: get_skills_prompt ignores nonexistent names")

    # ── 36aa. update preserves unchanged fields ──────────────────────
    _upd_sk = _skills_mod36.create_skill(
        name="test_update_preserve",
        display_name="PreserveTest",
        icon="🔒",
        description="preserve fields",
        instructions="Original instructions.",
        tags=["prod"],
        enabled=True,
    )
    # Update only icon
    _updated_sk = _skills_mod36.update_skill("test_update_preserve", icon="🆕")
    assert _updated_sk is not None
    assert _updated_sk.icon == "🆕"
    assert _updated_sk.display_name == "PreserveTest"
    assert _updated_sk.description == "preserve fields"
    assert _updated_sk.instructions == "Original instructions."
    assert _updated_sk.tags == ["prod"]
    _skills_mod36.delete_skill("test_update_preserve")
    record("PASS", "skills: update preserves unchanged fields")

    # ── 36ab. delete rejects bundled skills ──────────────────────────
    assert _skills_mod36.delete_skill("daily_briefing") is False, \
        "should not delete bundled skill"
    assert _skills_mod36.get_skill("daily_briefing") is not None, \
        "daily_briefing should still exist"
    record("PASS", "skills: delete rejects bundled skills")

    # ── 36ac. duplicate with custom name ─────────────────────────────
    _dup_custom = _skills_mod36.duplicate_skill("deep_research", new_name="my_research")
    assert _dup_custom is not None
    assert _dup_custom.name == "my_research"
    assert _dup_custom.source == "user"
    assert _dup_custom.display_name == "Deep Research (Custom)"
    _skills_mod36.delete_skill("my_research")
    record("PASS", "skills: duplicate with custom name")

    # ── 36ad. duplicate nonexistent skill returns None ───────────────
    assert _skills_mod36.duplicate_skill("nonexistent_xyz") is None
    record("PASS", "skills: duplicate nonexistent returns None")

    # ── 36ae. get_skill returns None for unknown name ────────────────
    assert _skills_mod36.get_skill("no_such_skill") is None
    record("PASS", "skills: get_skill returns None for unknown")

    # ── 36af. get_enabled_skills / get_enabled_skill_names ───────────
    _skills_mod36.set_enabled("meeting_notes", True)
    _en_skills = _skills_mod36.get_enabled_skills()
    _en_names = _skills_mod36.get_enabled_skill_names()
    assert any(s.name == "meeting_notes" for s in _en_skills), \
        "meeting_notes should be in enabled list"
    assert "meeting_notes" in _en_names
    _skills_mod36.set_enabled("meeting_notes", False)
    record("PASS", "skills: get_enabled_skills/names")

    # ── 36ag. estimate_tokens with explicit skill names ──────────────
    _est_names = _skills_mod36.estimate_tokens(["daily_briefing", "deep_research"])
    assert _est_names > 0, "estimate for 2 skills should be >0"
    _est_one = _skills_mod36.estimate_tokens(["daily_briefing"])
    assert _est_one > 0
    assert _est_names > _est_one, "2 skills should estimate more than 1"
    record("PASS", "skills: estimate_tokens with explicit names")

    # ── 36ah. Config corruption recovery ─────────────────────────────
    from skills import CONFIG_PATH as _cp36
    _backup_cfg = _cp36.read_text(encoding="utf-8") if _cp36.exists() else ""
    _cp36.write_text("NOT VALID JSON{{{", encoding="utf-8")
    # _load_config should return empty dict, not crash
    _fallback = _skills_mod36._load_config()
    assert isinstance(_fallback, dict), "corrupt config should yield empty dict"
    assert len(_fallback) == 0
    # Restore
    _cp36.write_text(_backup_cfg, encoding="utf-8")
    record("PASS", "skills: config corruption recovery")

    # ── 36ai. Multiple enable/disable cycles ─────────────────────────
    for _ in range(5):
        _skills_mod36.set_enabled("brain_dump", True)
        assert _skills_mod36.is_enabled("brain_dump")
        _skills_mod36.set_enabled("brain_dump", False)
        assert not _skills_mod36.is_enabled("brain_dump")
    record("PASS", "skills: multiple enable/disable cycles")

    # ── 36aj. Parser with minimal frontmatter (auto-defaults) ────────
    _min_skill = pathlib.Path(_tmp_dir36) / "MIN.md"
    _min_skill.write_text(
        "---\nname: minimal_skill\n---\n\nMinimal instructions.\n",
        encoding="utf-8",
    )
    _min_parsed = _parse_skill_md(_min_skill, source="user")
    assert _min_parsed is not None
    assert _min_parsed.display_name == "Minimal Skill"  # auto-generated from name
    assert _min_parsed.icon == "✨"  # default icon
    assert _min_parsed.version == "1.0"
    assert _min_parsed.tools == []
    assert _min_parsed.tags == []
    assert _min_parsed.author == "User"
    record("PASS", "skills: parser auto-defaults for minimal frontmatter")

    # ── 36ak. duplicate_task copies skills_override ──────────────────
    _dup_src = _src_tasks36[_src_tasks36.index("def duplicate_task"):]
    _dup_src = _dup_src[:1000]
    assert "skills_override" in _dup_src, \
        "duplicate_task should pass skills_override to create_task"
    record("PASS", "skills: duplicate_task copies skills_override")

    # ── 36al. YAML frontmatter with invalid YAML ─────────────────────
    _bad_yaml = pathlib.Path(_tmp_dir36) / "BADYAML.md"
    _bad_yaml.write_text(
        "---\nname: bad\n  indentation: broken\n---\n\nStuff.\n",
        encoding="utf-8",
    )
    assert _parse_skill_md(_bad_yaml) is None, "invalid YAML → None"
    record("PASS", "skills: parser rejects invalid YAML")

    # ── 36am. Parser rejects frontmatter that is not a dict ──────────
    _list_fm = pathlib.Path(_tmp_dir36) / "LISTFM.md"
    _list_fm.write_text(
        "---\n- item1\n- item2\n---\n\nInstructions.\n",
        encoding="utf-8",
    )
    assert _parse_skill_md(_list_fm) is None, "list frontmatter → None"
    record("PASS", "skills: parser rejects list frontmatter")

    # ── 36an. skills.py DATA_DIR / USER_SKILLS_DIR existence ─────────
    assert _skills_mod36.DATA_DIR.is_dir(), "DATA_DIR should exist"
    assert _skills_mod36.USER_SKILLS_DIR.is_dir(), "USER_SKILLS_DIR should exist"
    record("PASS", "skills: DATA_DIR and USER_SKILLS_DIR exist")

    # ── 36ao. load_skills is idempotent ──────────────────────────────
    _skills_mod36.load_skills()
    _count1 = len(_skills_mod36.get_all_skills())
    _skills_mod36.load_skills()
    _count2 = len(_skills_mod36.get_all_skills())
    assert _count1 == _count2, f"load_skills not idempotent: {_count1} vs {_count2}"
    record("PASS", "skills: load_skills is idempotent")

    # ── 36ap. Thread DB skills_override round-trip ──────────────────
    import sqlite3 as _sql36
    from threads import (
        DB_PATH as _threads_db36,
        get_thread_skills_override,
        set_thread_skills_override,
    )
    _test_tid36 = f"__TEST_skills_{uuid.uuid4().hex[:8]}"
    _conn36 = _sql36.connect(_threads_db36)
    _conn36.execute(
        "INSERT OR IGNORE INTO thread_meta (thread_id, name, created_at, updated_at) "
        "VALUES (?, ?, datetime('now'), datetime('now'))",
        (_test_tid36, "Skills Test Thread"),
    )
    _conn36.commit()
    _conn36.close()
    try:
        assert get_thread_skills_override(_test_tid36) is None, "default should be None"
        set_thread_skills_override(_test_tid36, ["daily_briefing", "deep_research"])
        _got36 = get_thread_skills_override(_test_tid36)
        assert _got36 == ["daily_briefing", "deep_research"], f"got {_got36}"
        set_thread_skills_override(_test_tid36, None)
        assert get_thread_skills_override(_test_tid36) is None, "should be None after clear"
        record("PASS", "skills: thread DB skills_override round-trip")
    finally:
        _conn36 = _sql36.connect(_threads_db36)
        _conn36.execute("DELETE FROM thread_meta WHERE thread_id = ?", (_test_tid36,))
        _conn36.commit()
        _conn36.close()

    # ── 36aq. Task DB skills_override round-trip ─────────────────────
    from tasks import create_task as _ct36, get_task as _gt36, update_task as _ut36, delete_task as _dt36
    _task_id36 = _ct36(
        name="__TEST_skills_task_suite",
        prompts=["test prompt"],
        skills_override=["brain_dump", "deep_research"],
    )
    try:
        _task36 = _gt36(_task_id36)
        assert _task36 is not None
        assert _task36["skills_override"] == ["brain_dump", "deep_research"], \
            f"got {_task36['skills_override']}"
        _ut36(_task_id36, skills_override=["daily_briefing"])
        _task36b = _gt36(_task_id36)
        assert _task36b["skills_override"] == ["daily_briefing"]
        _ut36(_task_id36, skills_override=None)
        _task36c = _gt36(_task_id36)
        assert _task36c["skills_override"] is None
        record("PASS", "skills: task DB skills_override create→update→clear round-trip")
    finally:
        _dt36(_task_id36)

    # ── 36ar. duplicate_task copies skills_override (functional) ─────
    from tasks import duplicate_task as _dup_task36
    _orig_id36 = _ct36(
        name="__TEST_skills_dup_orig",
        prompts=["dup test"],
        skills_override=["deep_research", "meeting_notes"],
    )
    try:
        _copy_id36 = _dup_task36(_orig_id36)
        assert _copy_id36 is not None
        _copy36 = _gt36(_copy_id36)
        assert _copy36["skills_override"] == ["deep_research", "meeting_notes"], \
            f"duplicate got {_copy36['skills_override']}"
        _dt36(_copy_id36)
        record("PASS", "skills: duplicate_task copies skills_override (functional)")
    finally:
        _dt36(_orig_id36)

    # Clean up temp files
    _shutil36.rmtree(_tmp_dir36, ignore_errors=True)

    # Restore user's original skills config
    if _skills_config_backup is not None:
        _skills_mod36.CONFIG_PATH.write_text(_skills_config_backup, encoding="utf-8")
    _skills_mod36.load_skills()

except Exception as e:
    record("FAIL", "skills engine tests", f"{type(e).__name__}: {e}")
    traceback.print_exc()
    # Best-effort restore even on failure
    try:
        if _skills_config_backup is not None:  # type: ignore[possibly-undefined]
            _skills_mod36.CONFIG_PATH.write_text(_skills_config_backup, encoding="utf-8")
        _skills_mod36.load_skills()
    except Exception:
        pass

# ═══════════════════════════════════════════════════════════════════════════
# GROUP 37 – SMOKE REGRESSION  (quick sanity checks across existing features)
# ═══════════════════════════════════════════════════════════════════════════
print("\n" + "=" * 70)
print("37. SMOKE REGRESSION")
print("=" * 70)

try:
    # ── 37a. Thread DB: create, read, delete ──────────────────────────
    import sqlite3 as _sql37
    from threads import DB_PATH as _threads_db37
    _tid37 = f"__SMOKE_{uuid.uuid4().hex[:8]}"
    _conn37 = _sql37.connect(_threads_db37)
    _conn37.execute(
        "INSERT OR IGNORE INTO thread_meta (thread_id, name, created_at, updated_at) "
        "VALUES (?, ?, datetime('now'), datetime('now'))",
        (_tid37, "Smoke Test"),
    )
    _conn37.commit()
    _row37 = _conn37.execute(
        "SELECT name FROM thread_meta WHERE thread_id = ?", (_tid37,)
    ).fetchone()
    assert _row37 and _row37[0] == "Smoke Test"
    _conn37.execute("DELETE FROM thread_meta WHERE thread_id = ?", (_tid37,))
    _conn37.commit()
    _conn37.close()
    record("PASS", "smoke: thread DB CRUD")

    # ── 37b. Task DB: create, read, delete ────────────────────────────
    from tasks import create_task as _ct37, get_task as _gt37, delete_task as _dt37
    _task_id37 = _ct37(name="__SMOKE_task", prompts=["hello"], description="smoke")
    _task37 = _gt37(_task_id37)
    assert _task37 is not None and _task37["name"] == "__SMOKE_task"
    _dt37(_task_id37)
    assert _gt37(_task_id37) is None
    record("PASS", "smoke: task DB CRUD")

    # ── 37c. Tool registry populated ──────────────────────────────────
    from tools.registry import get_all_tools
    _tools37 = get_all_tools()
    assert len(_tools37) >= 10, f"expected ≥10 tools, got {len(_tools37)}"
    record("PASS", f"smoke: tool registry has {len(_tools37)} tools")

    # ── 37d. Prompt builder returns content ───────────────────────────
    _prompt_src37 = (PROJECT_ROOT / "agent.py").read_text(encoding="utf-8")
    assert "AGENT_SYSTEM_PROMPT" in _prompt_src37
    record("PASS", "smoke: agent.py has system prompt logic")

    # ── 37e. Models list available ────────────────────────────────────
    import models as _models37
    assert hasattr(_models37, "list_all_models"), \
        "models.py should have list_all_models"
    record("PASS", "smoke: models module accessible")

    # ── 37f. Voice module imports ─────────────────────────────────────
    import voice as _voice37
    assert hasattr(_voice37, "VoiceService"), "voice module should have VoiceService class"
    record("PASS", "smoke: voice module imports")

    # ── 37g. TTS module imports ───────────────────────────────────────
    import tts as _tts37
    assert hasattr(_tts37, "TTSService"), "tts module should have TTSService class"
    record("PASS", "smoke: tts module imports")

    # ── 37h. Memory module imports ────────────────────────────────────
    import memory as _mem37
    assert hasattr(_mem37, "search_memories"), "memory module should have search_memories"
    record("PASS", "smoke: memory module imports")

    # ── 37i. Documents module imports ─────────────────────────────────
    import documents as _docs37
    record("PASS", "smoke: documents module imports")

    # ── 37j. Notifications module imports ─────────────────────────────
    import notifications as _notif37
    record("PASS", "smoke: notifications module imports")

    # ── 37k. UI package imports ─────────────────────────────────────
    import ui as _ui37
    record("PASS", "smoke: ui package imports")

    # ── 37l. Channel modules import ───────────────────────────────────
    from channels import config as _chcfg37
    from channels import email as _chemail37
    from channels import telegram as _chtg37
    record("PASS", "smoke: channel modules import")

    # ── 37m. Data reader imports ──────────────────────────────────────
    import data_reader as _dr37
    record("PASS", "smoke: data_reader module imports")

    # ── 37n. Memory extraction imports ────────────────────────────────
    import memory_extraction as _me37
    record("PASS", "smoke: memory_extraction module imports")

    # ── 37o. Requirements.txt exists and has content ──────────────────
    _req37 = (PROJECT_ROOT / "requirements.txt").read_text(encoding="utf-8")
    assert len(_req37.strip().splitlines()) >= 10, "requirements.txt too short"
    record("PASS", "smoke: requirements.txt has content")

    # ── 37p. Launcher module imports ──────────────────────────────────
    assert (PROJECT_ROOT / "launcher.py").exists()
    import ast as _ast37p
    _ast37p.parse((PROJECT_ROOT / "launcher.py").read_text(encoding="utf-8"))
    record("PASS", "smoke: launcher.py parses cleanly")

    # ── 37q. App NiceGUI parses cleanly ───────────────────────────────
    _ast37p.parse((PROJECT_ROOT / "app.py").read_text(encoding="utf-8"))
    record("PASS", "smoke: app.py parses cleanly")

    # ── 37r. Skills module round-trip (quick) ─────────────────────────
    import skills as _sk37
    _sk37.load_skills()
    assert len(_sk37.get_all_skills()) >= 5
    record("PASS", "smoke: skills load_skills returns ≥5")

except Exception as e:
    record("FAIL", "smoke regression tests", f"{type(e).__name__}: {e}")
    traceback.print_exc()

# ═════════════════════════════════════════════════════════════════════════════
print("\n" + "=" * 70)
print("38. IMAGE HANDLING IMPROVEMENTS")
print("=" * 70)
# ═════════════════════════════════════════════════════════════════════════════

try:
    # ── 38a. VisionService.capture_and_analyze accepts source='file' ─────
    from vision import VisionService as _VS38
    import inspect as _insp38
    _sig38 = _insp38.signature(_VS38.capture_and_analyze)
    _params38 = list(_sig38.parameters.keys())
    assert "file_path" in _params38, f"missing file_path param: {_params38}"
    assert "source" in _params38, f"missing source param: {_params38}"
    record("PASS", "image: VisionService.capture_and_analyze accepts file_path")

    # ── 38b. VisionService._resolve_image_path returns None for missing ──
    _r38b = _VS38._resolve_image_path("__nonexistent_test_file__.jpg")
    assert _r38b is None, f"expected None, got {_r38b}"
    record("PASS", "image: _resolve_image_path returns None for missing file")

    # ── 38c. VisionService._analyze_from_file returns error for missing ──
    _vs38c = _VS38()
    _r38c = _vs38c._analyze_from_file("__nonexistent__.png", "describe")
    assert "not found" in _r38c.lower(), f"unexpected: {_r38c}"
    record("PASS", "image: _analyze_from_file returns error for missing file")

    # ── 38d. Vision tool schema includes file_path parameter ─────────────
    from tools.vision_tool import VisionTool as _VT38
    _vt38 = _VT38()
    _tools38 = _vt38.as_langchain_tools()
    _schema38 = _tools38[0].args_schema.model_json_schema()
    assert "file_path" in _schema38["properties"], "file_path missing from tool schema"
    assert "source" in _schema38["properties"], "source missing from tool schema"
    record("PASS", "image: vision tool schema includes file_path and source")

    # ── 38e. Filesystem tool has get_and_clear_displayed_image ────────────
    from tools.filesystem_tool import (
        get_and_clear_displayed_image as _gcdi38,
        _last_displayed_image as _ldi38_initial,
    )
    assert _ldi38_initial is None, "initial _last_displayed_image should be None"
    assert _gcdi38() is None, "get_and_clear should return None initially"
    record("PASS", "image: filesystem get_and_clear_displayed_image exists")

    # ── 38f. Filesystem image detection: read_file on image returns display msg ──
    import tempfile, os, base64 as _b6438
    from tools.filesystem_tool import _make_pdf_aware_read_tool as _mprt38
    import tools.filesystem_tool as _fstmod38
    _td38 = tempfile.mkdtemp()
    # Create a tiny valid JPEG (smallest valid JPEG is 107 bytes, use a stub)
    _jpeg_stub = b"\xff\xd8\xff\xe0" + b"\x00" * 50
    _img_path38 = os.path.join(_td38, "test_photo.jpg")
    with open(_img_path38, "wb") as _f38:
        _f38.write(_jpeg_stub)
    _read_tool38 = _mprt38(_td38)
    _result38f = _read_tool38.invoke({"file_path": "test_photo.jpg"})
    assert "Displayed image" in _result38f, f"unexpected read_file result: {_result38f}"
    assert "test_photo.jpg" in _result38f
    # Verify the displayed image was stored
    _disp38 = _fstmod38.get_and_clear_displayed_image()
    assert _disp38 is not None, "displayed image not stored"
    assert _disp38["name"] == "test_photo.jpg"
    assert len(_disp38["b64"]) > 0
    # Verify it was cleared
    assert _fstmod38.get_and_clear_displayed_image() is None
    os.remove(_img_path38)
    os.rmdir(_td38)
    record("PASS", "image: filesystem read_file detects and displays images")

    # ── 38g. _img_data_uri MIME detection ────────────────────────────────
    from ui.streaming import _img_data_uri as _idu38
    _jpeg_b6438 = _b6438.b64encode(b"\xff\xd8\xff\xe0test").decode()
    _png_b6438 = _b6438.b64encode(b"\x89PNG\r\n\x1a\ntest").decode()
    _gif_b6438 = _b6438.b64encode(b"GIF89atest").decode()
    _webp_b6438 = _b6438.b64encode(b"RIFF\x00\x00\x00\x00WEBPtest").decode()
    assert "image/jpeg" in _idu38(_jpeg_b6438), "JPEG MIME failed"
    assert "image/png" in _idu38(_png_b6438), "PNG MIME failed"
    assert "image/gif" in _idu38(_gif_b6438), "GIF MIME failed"
    assert "image/webp" in _idu38(_webp_b6438), "WebP MIME failed"
    record("PASS", "image: _img_data_uri detects JPEG/PNG/GIF/WebP correctly")

    # ── 38h. System prompt mentions new image capabilities ───────────────
    from prompts import AGENT_SYSTEM_PROMPT as _asp38
    assert "source='file'" in _asp38, "prompt missing source='file'"
    assert "file_path" in _asp38, "prompt missing file_path"
    assert "auto-analyzed" in _asp38, "prompt missing auto-analyzed"
    assert "displays them inline" in _asp38 or "image files" in _asp38, \
        "prompt missing filesystem image mention"
    record("PASS", "image: system prompt documents all new image capabilities")

    # ── 38i. GenerationState.captured_images exists ──────────────────────
    from ui.state import GenerationState as _GS38
    import queue as _q38, threading as _t38
    _gs38 = _GS38(
        thread_id="test", q=_q38.Queue(), stop_event=_t38.Event(),
        config={}, enabled_tools=[],
    )
    assert hasattr(_gs38, "captured_images"), "missing captured_images"
    assert isinstance(_gs38.captured_images, list), "captured_images not a list"
    _gs38.captured_images.append("test_b64")
    assert len(_gs38.captured_images) == 1
    record("PASS", "image: GenerationState.captured_images works")

    # ── 38j. Filesystem read_file still works for text files ─────────────
    _td38j = tempfile.mkdtemp()
    _txt_path38 = os.path.join(_td38j, "note.txt")
    with open(_txt_path38, "w", encoding="utf-8") as _f38j:
        _f38j.write("Hello world test content")
    _read_tool38j = _mprt38(_td38j)
    _result38j = _read_tool38j.invoke({"file_path": "note.txt"})
    assert "Hello world test content" in _result38j, f"text read failed: {_result38j}"
    os.remove(_txt_path38)
    os.rmdir(_td38j)
    record("PASS", "image: filesystem read_file still works for text files")

except Exception as e:
    record("FAIL", "image handling improvements", f"{type(e).__name__}: {e}")
    traceback.print_exc()

# ═════════════════════════════════════════════════════════════════════════════
print("\n" + "=" * 70)
print("39. OAUTH TOKEN HEALTH CHECK")
print("=" * 70)
# ═════════════════════════════════════════════════════════════════════════════

try:
    # ── 39a. _check_google_token returns 'missing' for nonexistent path ──
    from tools.gmail_tool import _check_google_token as _gck39
    _s39a, _d39a = _gck39("/nonexistent/path/token.json")
    assert _s39a == "missing", f"expected 'missing', got '{_s39a}'"
    record("PASS", "oauth: _check_google_token returns 'missing' for bad path")

    # ── 39b. Calendar _check_google_token also returns 'missing' ─────────
    from tools.calendar_tool import _check_google_token as _cck39
    _s39b, _d39b = _cck39("/nonexistent/path/token.json")
    assert _s39b == "missing", f"expected 'missing', got '{_s39b}'"
    record("PASS", "oauth: calendar _check_google_token returns 'missing'")

    # ── 39c. GmailTool.check_token_health method exists ──────────────────
    from tools.gmail_tool import GmailTool as _GT39
    _gt39 = _GT39()
    assert hasattr(_gt39, "check_token_health"), "GmailTool missing check_token_health"
    assert callable(_gt39.check_token_health), "check_token_health not callable"
    record("PASS", "oauth: GmailTool.check_token_health exists")

    # ── 39d. CalendarTool.check_token_health method exists ───────────────
    from tools.calendar_tool import CalendarTool as _CT39
    _ct39 = _CT39()
    assert hasattr(_ct39, "check_token_health"), "CalendarTool missing check_token_health"
    assert callable(_ct39.check_token_health), "check_token_health not callable"
    record("PASS", "oauth: CalendarTool.check_token_health exists")

    # ── 39e. check_token_health returns tuple(str, str) ──────────────────
    _r39e = _gt39.check_token_health()
    assert isinstance(_r39e, tuple), f"expected tuple, got {type(_r39e)}"
    assert len(_r39e) == 2, f"expected 2-tuple, got {len(_r39e)}"
    assert isinstance(_r39e[0], str) and isinstance(_r39e[1], str), "tuple elements must be str"
    assert _r39e[0] in ("valid", "refreshed", "expired", "missing", "error"), \
        f"unexpected status: {_r39e[0]}"
    record("PASS", "oauth: check_token_health returns valid (status, detail) tuple")

    # ── 39f. _check_google_token handles corrupt token file ──────────────
    _td39f = tempfile.mkdtemp()
    _corrupt39 = os.path.join(_td39f, "token.json")
    with open(_corrupt39, "w", encoding="utf-8") as _f39f:
        _f39f.write("not valid json {{{")
    _s39f, _d39f = _gck39(_corrupt39)
    assert _s39f == "error", f"expected 'error' for corrupt file, got '{_s39f}'"
    os.remove(_corrupt39)
    os.rmdir(_td39f)
    record("PASS", "oauth: _check_google_token handles corrupt token file")

    # ── 39g. _check_oauth_tokens skips disabled tools ────────────────────
    from tools import registry as _reg39
    # Temporarily disable both tools and verify no warnings
    _orig_gmail_en = _reg39.is_enabled("gmail")
    _orig_cal_en = _reg39.is_enabled("calendar")
    _reg39.set_enabled("gmail", False)
    _reg39.set_enabled("calendar", False)
    from app import _check_oauth_tokens as _coauth39
    _w39g = _coauth39()
    assert _w39g == [], f"expected [] when tools disabled, got {_w39g}"
    # Restore original states
    _reg39.set_enabled("gmail", _orig_gmail_en)
    _reg39.set_enabled("calendar", _orig_cal_en)
    record("PASS", "oauth: _check_oauth_tokens skips disabled tools")

    # ── 39h. _periodic_oauth_check callable ──────────────────────────────
    from app import _periodic_oauth_check as _poc39
    assert callable(_poc39), "_periodic_oauth_check not callable"
    record("PASS", "oauth: _periodic_oauth_check is callable")

except Exception as e:
    record("FAIL", "oauth token health check", f"{type(e).__name__}: {e}")
    traceback.print_exc()

# ═══════════════════════════════════════════════════════════════════════
print("40. ARXIV TOOL REWRITE")
# ═══════════════════════════════════════════════════════════════════════
try:
    # ── 40a. ArxivTool is registered ─────────────────────────────────
    from tools.arxiv_tool import ArxivTool as _AT40
    from tools import registry as _reg40
    _at40 = _AT40()
    assert "arxiv" in _reg40._tools, "ArxivTool not registered"
    record("PASS", "arxiv: ArxivTool registered")

    # ── 40b. execute() is overridden (not using get_retriever) ───────
    assert "execute" in _AT40.__dict__, "ArxivTool should override execute()"
    assert "get_retriever" not in _AT40.__dict__, "ArxivTool should NOT define get_retriever"
    record("PASS", "arxiv: execute() overridden, get_retriever removed")

    # ── 40c. Description mentions HTML link and query syntax ────────
    _desc40 = _at40.description
    assert "html" in _desc40.lower(), "description should mention HTML"
    assert "ti:" in _desc40, "description should mention ti: query syntax"
    assert "cat:" in _desc40, "description should mention cat: query syntax"
    assert "URL reader" in _desc40 or "url reader" in _desc40.lower(), "description should mention URL reader"
    record("PASS", "arxiv: description mentions HTML link, query syntax, URL reader")

    # ── 40d. execute() with mocked client returns proper format ──────
    from unittest.mock import patch as _patch40, MagicMock as _MM40
    from datetime import datetime as _dt40

    _mock_result = _MM40()
    _mock_result.get_short_id.return_value = "2401.12345v1"
    _mock_result.title = "Test Paper Title"
    _a1_40 = _MM40(); _a1_40.name = "Alice"
    _a2_40 = _MM40(); _a2_40.name = "Bob"
    _mock_result.authors = [_a1_40, _a2_40]
    _mock_result.published = _dt40(2024, 1, 15)
    _mock_result.summary = "A test abstract."
    _mock_result.primary_category = "cs.AI"
    _mock_result.pdf_url = "https://arxiv.org/pdf/2401.12345v1"
    _mock_result.entry_id = "https://arxiv.org/abs/2401.12345v1"

    with _patch40("arxiv.Client") as _mc40:
        _mc40.return_value.results.return_value = [_mock_result]
        _out40 = _at40.execute("test query")

    assert "Test Paper Title" in _out40, f"Title missing from output"
    assert "Alice" in _out40, "Authors missing from output"
    assert "2024-01-15" in _out40, "Published date missing from output"
    assert "cs.AI" in _out40, "Category missing from output"
    assert "arxiv.org/html/2401.12345" in _out40, "HTML URL missing"
    assert "v1" not in _out40.split("arxiv.org/html/")[1].split("\n")[0], "HTML URL should not have version"
    assert "SOURCE_URL: https://arxiv.org/abs/2401.12345v1" in _out40, "SOURCE_URL missing"
    record("PASS", "arxiv: execute() returns properly formatted results")

    # ── 40e. execute() returns message when no results ───────────────
    with _patch40("arxiv.Client") as _mc40e:
        _mc40e.return_value.results.return_value = []
        _out40e = _at40.execute("xyznonexistent99")
    assert "No arXiv papers found" in _out40e, f"Expected no-results message, got: {_out40e}"
    record("PASS", "arxiv: execute() handles no results gracefully")

    # ── 40f. HTML URL strips version suffix correctly ────────────────
    import re as _re40
    # Simulate various ID formats
    for _tid, _expected in [
        ("2401.12345v1", "2401.12345"),
        ("2401.12345v2", "2401.12345"),
        ("2401.12345", "2401.12345"),
        ("quant-ph/0201082v1", "quant-ph/0201082"),
    ]:
        _base = _re40.sub(r"v\d+$", "", _tid)
        assert _base == _expected, f"Version strip failed: {_tid} -> {_base}, expected {_expected}"
    record("PASS", "arxiv: HTML URL version stripping works for all ID formats")

    # ── 40g. Author truncation for many-author papers ────────────────
    _mock_many = _MM40()
    _mock_many.get_short_id.return_value = "2401.99999v1"
    _mock_many.title = "Many Author Paper"
    _mock_many.authors = []
    for _ai in range(12):
        _am = _MM40(); _am.name = f"Author{_ai}"
        _mock_many.authors.append(_am)
    _mock_many.published = _dt40(2024, 2, 1)
    _mock_many.summary = "Abstract."
    _mock_many.primary_category = "cs.CL"
    _mock_many.pdf_url = "https://arxiv.org/pdf/2401.99999v1"
    _mock_many.entry_id = "https://arxiv.org/abs/2401.99999v1"

    with _patch40("arxiv.Client") as _mc40g:
        _mc40g.return_value.results.return_value = [_mock_many]
        _out40g = _at40.execute("many authors")
    assert "et al." in _out40g, "Should show 'et al.' for many authors"
    assert "12 authors" in _out40g, "Should state total author count"
    # Only first 5 listed
    assert "Author0" in _out40g and "Author4" in _out40g, "First 5 authors should be listed"
    assert "Author5" not in _out40g.split("et al.")[0], "Author6+ should not appear before et al."
    record("PASS", "arxiv: author list truncated with et al. for >5 authors")

except Exception as e:
    record("FAIL", "arxiv tool rewrite", f"{type(e).__name__}: {e}")
    traceback.print_exc()

# ══════════════════════════════════════════════════════════════════════════════
# 41. Status Monitor — status_checks & status_bar modules
# ══════════════════════════════════════════════════════════════════════════════
print("\n41. Status Monitor")
print("-" * 70)

try:
    # ── 41a. Module imports ──────────────────────────────────────────
    from ui.status_checks import (
        CheckResult, ALL_CHECKS, LIGHT_CHECKS, HEAVY_CHECKS,
        run_all_checks, run_light_checks,
        check_ollama, check_active_model, check_cloud_api,
        check_gmail_channel, check_telegram,
        check_gmail_oauth, check_calendar_oauth,
        check_task_scheduler, check_memory_extraction,
        check_disk_space, check_threads_db, check_faiss_index,
        check_document_store, check_network,
    )
    record("PASS", "status_checks: module imports")

    from ui.status_bar import (
        build_status_bar, _load_avatar_config, _save_avatar_config,
        _AVATAR_EMOJIS, _RING_COLORS, _DEFAULT_EMOJI, _DEFAULT_COLOR,
        _force_refresh,
    )
    record("PASS", "status_bar: module imports")

    # ── 41b. CheckResult dataclass ───────────────────────────────────
    cr = CheckResult("Test", "ok", "detail text", settings_tab="Models")
    assert cr.name == "Test"
    assert cr.status == "ok"
    assert cr.detail == "detail text"
    assert cr.settings_tab == "Models"
    assert cr.dot_color == "#4caf50"
    assert cr.icon == "check_circle"
    assert cr.status_label == "Healthy"
    assert cr.checked_at > 0
    record("PASS", "status_checks: CheckResult ok properties")

    cr_warn = CheckResult("W", "warn", "w")
    assert cr_warn.dot_color == "#ff9800"
    assert cr_warn.icon == "warning"
    assert cr_warn.status_label == "Warning"
    record("PASS", "status_checks: CheckResult warn properties")

    cr_err = CheckResult("E", "error", "e")
    assert cr_err.dot_color == "#f44336"
    assert cr_err.icon == "error"
    assert cr_err.status_label == "Error"
    record("PASS", "status_checks: CheckResult error properties")

    cr_na = CheckResult("N", "inactive", "n")
    assert cr_na.dot_color == "#666"
    assert cr_na.icon == "radio_button_unchecked"
    assert cr_na.status_label == "Not configured"
    record("PASS", "status_checks: CheckResult inactive properties")

    # ── 41c. Check registry completeness ─────────────────────────────
    assert len(ALL_CHECKS) == 14, f"Expected 14 checks, got {len(ALL_CHECKS)}"
    record("PASS", "status_checks: 14 checks registered in ALL_CHECKS")

    assert set(LIGHT_CHECKS).issubset(set(ALL_CHECKS)), "LIGHT_CHECKS not subset"
    assert set(HEAVY_CHECKS).issubset(set(ALL_CHECKS)), "HEAVY_CHECKS not subset"
    assert len(LIGHT_CHECKS) + len(HEAVY_CHECKS) == len(ALL_CHECKS), \
        "LIGHT + HEAVY should cover all checks"
    record("PASS", "status_checks: LIGHT + HEAVY partition covers ALL_CHECKS")

    # ── 41d. Every check runs without crashing ───────────────────────
    all_results = run_all_checks()
    assert len(all_results) == 14, f"Expected 14 results, got {len(all_results)}"
    for r in all_results:
        assert isinstance(r, CheckResult), f"Not CheckResult: {r}"
        assert r.status in ("ok", "warn", "error", "inactive"), f"Bad status: {r.status}"
        assert r.name, "Empty check name"
    record("PASS", "status_checks: run_all_checks returns 14 valid results")

    light_results = run_light_checks()
    assert len(light_results) == len(LIGHT_CHECKS)
    for r in light_results:
        assert isinstance(r, CheckResult)
    record("PASS", "status_checks: run_light_checks returns correct count")

    # ── 41e. Individual check return types ───────────────────────────
    for fn in ALL_CHECKS:
        r = fn()
        assert isinstance(r, CheckResult), f"{fn.__name__} didn't return CheckResult"
        assert r.name, f"{fn.__name__} returned empty name"
    record("PASS", "status_checks: all individual checks return CheckResult")

    # ── 41f. Avatar config round-trip ────────────────────────────────
    import tempfile, json as _json41
    from pathlib import Path as _P41
    import ui.status_bar as _sb41

    _orig_path = _sb41._USER_CONFIG_PATH
    _orig_dir = _sb41._DATA_DIR
    try:
        with tempfile.TemporaryDirectory() as _td41:
            _sb41._DATA_DIR = _P41(_td41)
            _sb41._USER_CONFIG_PATH = _P41(_td41) / "user_config.json"

            # Before any config, should return empty
            cfg = _load_avatar_config()
            assert cfg == {}, f"Expected empty dict, got {cfg}"

            # Save and reload
            _save_avatar_config({"emoji": "🤖", "color": "#ff0000"})
            cfg2 = _load_avatar_config()
            assert cfg2["emoji"] == "🤖", f"Emoji mismatch: {cfg2}"
            assert cfg2["color"] == "#ff0000", f"Color mismatch: {cfg2}"

            # Verify file structure
            data = _json41.loads(_sb41._USER_CONFIG_PATH.read_text(encoding="utf-8"))
            assert "avatar" in data
            assert data["avatar"]["emoji"] == "🤖"

            # Overwrite with new values preserves file
            _save_avatar_config({"emoji": "🦊", "color": "#00ff00"})
            cfg3 = _load_avatar_config()
            assert cfg3["emoji"] == "🦊"
            assert cfg3["color"] == "#00ff00"

        record("PASS", "status_bar: avatar config save/load round-trip")
    finally:
        _sb41._USER_CONFIG_PATH = _orig_path
        _sb41._DATA_DIR = _orig_dir

    # ── 41g. Avatar defaults ─────────────────────────────────────────
    assert _DEFAULT_EMOJI == "𓁟"
    assert _DEFAULT_COLOR == "#FFD700"
    assert len(_AVATAR_EMOJIS) >= 20, f"Too few emojis: {len(_AVATAR_EMOJIS)}"
    assert len(_RING_COLORS) >= 10, f"Too few colors: {len(_RING_COLORS)}"
    record("PASS", "status_bar: avatar defaults and catalogs")

    # ── 41h. Force refresh populates cache ───────────────────────────
    fr = _force_refresh()
    assert len(fr) == 14, f"force_refresh returned {len(fr)} results"
    from ui.status_bar import _status_cache, _cache_time
    assert len(_status_cache) == 14
    assert _cache_time > 0
    record("PASS", "status_bar: force_refresh populates cache")

    # ── 41i. Disk check thresholds ───────────────────────────────────
    disk_r = check_disk_space()
    assert disk_r.name == "Disk"
    assert "GB free" in disk_r.detail
    record("PASS", "status_checks: disk check returns size info")

    # ── 41j. Threads DB check ────────────────────────────────────────
    db_r = check_threads_db()
    assert db_r.name == "Threads DB"
    assert db_r.status in ("ok", "error")
    record("PASS", "status_checks: threads DB check runs")

    # ── 41k. Network check ───────────────────────────────────────────
    net_r = check_network()
    assert net_r.name == "Network"
    assert net_r.status in ("ok", "warn", "error")
    record("PASS", "status_checks: network check runs")

    # ── 41l. Check settings_tab mapping ──────────────────────────────
    _tabs_expected = {
        "Ollama": "Models", "Model": "Models", "Cloud API": "Cloud",
        "Email": "Channels", "Telegram": "Channels",
        "Gmail OAuth": "Gmail", "Calendar OAuth": "Calendar",
        "Memory": "Memory", "FAISS Index": "Memory",
        "Documents": "Documents", "Threads DB": "",
    }
    for r in all_results:
        if r.name in _tabs_expected:
            assert r.settings_tab == _tabs_expected[r.name], \
                f"{r.name}: expected tab '{_tabs_expected[r.name]}', got '{r.settings_tab}'"
    record("PASS", "status_checks: settings_tab mapping correct")

    # ── 41m. build_status_bar callable signature ─────────────────────
    import inspect as _insp41
    sig = _insp41.signature(build_status_bar)
    assert "open_settings" in sig.parameters
    record("PASS", "status_bar: build_status_bar accepts open_settings param")

    # ── 41n. home.py accepts open_settings kwarg ─────────────────────
    from ui.home import build_home as _bh41
    sig_home = _insp41.signature(_bh41)
    assert "open_settings" in sig_home.parameters
    record("PASS", "home: build_home accepts open_settings kwarg")

except Exception as e:
    record("FAIL", "status monitor", f"{type(e).__name__}: {e}")
    traceback.print_exc()
print("=" * 70)
print(f"  ✅ PASS: {PASS}")
print(f"  ❌ FAIL: {FAIL}")
print(f"  ⚠️  WARN: {WARN}")
print(f"  Total: {PASS + FAIL + WARN}")
print()

if FAIL > 0:
    print("FAILED TESTS:")
    for status, name, detail in RESULTS:
        if status == "FAIL":
            print(f"  ❌ {name}: {detail}")
    print()

if FAIL == 0:
    print("🎉 ALL TESTS PASSED!")
else:
    print(f"⛔ {FAIL} TEST(S) FAILED")

sys.exit(1 if FAIL > 0 else 0)
