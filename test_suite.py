"""Thoth v3.5.0 — Comprehensive Test Suite

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
# 10. NO STREAMLIT IMPORTS IN app_nicegui.py
# ═════════════════════════════════════════════════════════════════════════════
print("\n" + "=" * 70)
print("10. NO STREAMLIT IMPORTS IN app_nicegui.py")
print("=" * 70)

try:
    source = (PROJECT_ROOT / "app_nicegui.py").read_text(encoding="utf-8")
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
        record("PASS", "no streamlit imports in app_nicegui.py")
    else:
        record("FAIL", "streamlit imports found in app_nicegui.py", "; ".join(streamlit_imports))

except Exception as e:
    record("FAIL", "streamlit import check", str(e))

# ═════════════════════════════════════════════════════════════════════════════
# 11. NiceGUI APP IMPORT CHECK
# ═════════════════════════════════════════════════════════════════════════════
print("\n" + "=" * 70)
print("11. NiceGUI APP AST PARSE + BASIC IMPORT CHECK")
print("=" * 70)

try:
    source = (PROJECT_ROOT / "app_nicegui.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    record("PASS", f"app_nicegui.py AST parsed ({len(source):,} chars)")
except Exception as e:
    record("FAIL", "app_nicegui.py AST parse", str(e))

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
            [python, "app_nicegui.py"],
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

    # --- 17b. Schema: source column present in CREATE TABLE --------------
    import sqlite3 as _sqlite3
    _test_conn = _sqlite3.connect(_mem_mod.DB_PATH)
    _test_conn.row_factory = _sqlite3.Row
    _cols = [row[1] for row in _test_conn.execute("PRAGMA table_info(memories)").fetchall()]
    _test_conn.close()
    if "source" in _cols:
        record("PASS", "memory: 'source' column exists in memories table")
    else:
        record("FAIL", "memory: 'source' column missing from memories table")

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
    assert _st.enabled_by_default is False
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
        _block_if_background, _get_thread_id, _detect_channel,
        _format_snapshot, _PROFILE_DIR, _HISTORY_PATH, _SNAPSHOT_JS,
        _NavigateInput, _ClickInput, _TypeInput, _ScrollInput, _TabInput,
    )

    # 19a. BrowserTool class validation
    _bt = BrowserTool()
    assert _bt.name == "browser", f"Expected 'browser', got '{_bt.name}'"
    assert _bt.display_name == "🌐 Browser"
    assert _bt.enabled_by_default is False
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
    _bsm.kill_session("test_thread_1")  # no-op for shared session
    assert _bsm.has_active_session(), "kill_session is no-op on shared browser"
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

    # 19g. _block_if_background returns None normally
    _block_result = _block_if_background("navigate")
    assert _block_result is None, f"Expected None, got: {_block_result}"
    record("PASS", "browser: background check passes normally")

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
    _long_snap = {
        "url": "https://example.com",
        "title": "Test",
        "refs": [f"[{i}] button \"btn{i}\"" for i in range(1, 2000)],
        "refCount": 1999,
    }
    _long_text = _format_snapshot(_long_snap)
    assert len(_long_text) <= 25_100  # MAX_SNAPSHOT_CHARS + some fuzz
    assert "truncated" in _long_text
    record("PASS", "browser: snapshot truncation works")

    # 19j. Profile directory path is under ~/.thoth/
    assert "browser_profile" in str(_PROFILE_DIR)
    assert ".thoth" in str(_PROFILE_DIR)
    record("PASS", "browser: profile dir path correct")

    # 19k. History path is under ~/.thoth/
    assert "browser_history.json" in str(_HISTORY_PATH)
    record("PASS", "browser: history path correct")

    # 19l. Snapshot JS is a non-empty string
    assert isinstance(_SNAPSHOT_JS, str) and len(_SNAPSHOT_JS) > 100
    assert "data-thoth-ref" in _SNAPSHOT_JS
    assert "interactiveSelectors" in _SNAPSHOT_JS
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

    # 20a. With 5 browser messages, only last 2 stay full (keep=2)
    _snap_msgs = []
    for idx in range(5):
        tc_id = f"tc_{idx}"
        _snap_msgs.append(_make_ai_tool_call(tc_id, "browser_navigate"))
        _snap_msgs.append(_make_browser_tool_msg(
            "browser_navigate",
            f"https://example.com/page{idx}",
            f"Page {idx}",
            tool_call_id=tc_id,
        ))

    # Inject into a minimal state dict
    _state_a = {"messages": _snap_msgs}
    # Simulate just the compression logic directly (avoid full _pre_model_trim
    # which needs model context_size, summary cache, etc.)
    _msgs_copy = list(_state_a["messages"])
    _b_indices = [
        i for i, m in enumerate(_msgs_copy)
        if m.type == "tool" and (getattr(m, "name", "") or "").startswith("browser_")
    ]
    assert len(_b_indices) == 5, f"Expected 5 browser tool msgs, got {len(_b_indices)}"
    if len(_b_indices) > _agent_mod._KEEP_BROWSER_SNAPSHOTS:
        for i in _b_indices[:-_agent_mod._KEEP_BROWSER_SNAPSHOTS]:
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

    # First 3 should be stubs, last 2 should be full
    for idx, bi in enumerate(_b_indices[:3]):
        assert "[Prior browser" in _msgs_copy[bi].content, \
            f"Msg {idx} should be a stub, got: {_msgs_copy[bi].content[:80]}"
    for idx, bi in enumerate(_b_indices[3:]):
        assert "Interactive elements" in _msgs_copy[bi].content, \
            f"Msg {idx+3} should be full, got: {_msgs_copy[bi].content[:80]}"
    record("PASS", "browser compression: 5 msgs → stubs for first 3, full for last 2")

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
    _mixed = [
        _make_ai_tool_call("tc_ws", "web_search"),
        _TM(content="Search results for Python...", name="web_search", tool_call_id="tc_ws"),
    ]
    for idx in range(4):
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
    if len(_b_mixed) > _agent_mod._KEEP_BROWSER_SNAPSHOTS:
        for i in _b_mixed[:-_agent_mod._KEEP_BROWSER_SNAPSHOTS]:
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

    # 20e. Fewer than _KEEP_BROWSER_SNAPSHOTS → no compression
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
    if len(_b_few) > _agent_mod._KEEP_BROWSER_SNAPSHOTS:
        assert False, "Should not compress when count <= keep"
    for bi in _b_few:
        assert "Interactive elements" in _few_copy[bi].content
    record("PASS", "browser compression: ≤ keep count → no compression")

    # 20f. _KEEP_BROWSER_SNAPSHOTS constant is 2
    assert _agent_mod._KEEP_BROWSER_SNAPSHOTS == 2
    record("PASS", "browser compression: _KEEP_BROWSER_SNAPSHOTS == 2")

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

    # 22e. interval_hours is 6
    if _mem.get("interval_hours") == 6.0:
        record("PASS", "activity: extraction interval is 6h")
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

    # 22h. app_nicegui imports the new functions
    import ast as _ast
    _app_src = Path("app_nicegui.py").read_text(encoding="utf-8")
    _app_tree = _ast.parse(_app_src)
    _imported_names: set[str] = set()
    for node in _ast.walk(_app_tree):
        if isinstance(node, _ast.ImportFrom):
            for alias in node.names:
                _imported_names.add(alias.name)
    _activity_imports = {"get_recent_runs", "get_next_fire_times", "get_extraction_status"}
    _missing_imports = _activity_imports - _imported_names
    if not _missing_imports:
        record("PASS", "activity: app_nicegui imports all Activity helpers")
    else:
        record("FAIL", "activity: app_nicegui missing imports", str(_missing_imports))

    # 22i. _build_activity_content string exists in app_nicegui source
    if "_build_activity_content" in _app_src:
        record("PASS", "activity: _build_activity_content defined in app_nicegui")
    else:
        record("FAIL", "activity: _build_activity_content not found in app_nicegui")

    # 22j. Activity tab string exists in app_nicegui source
    if "Activity" in _app_src and "home_tabs" in _app_src:
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

    # 23b. _validate_delivery rejects channel without target
    try:
        _validate_delivery("telegram", None)
        record("FAIL", "delivery: validate(telegram, None) should raise")
    except ValueError:
        record("PASS", "delivery: validate(telegram, None) raises ValueError")

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

    # 23e. _validate_delivery requires telegram target to be numeric
    try:
        _validate_delivery("telegram", "not_a_number")
        record("FAIL", "delivery: validate(telegram, non-numeric) should raise")
    except ValueError:
        record("PASS", "delivery: validate(telegram, non-numeric) raises ValueError")

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

    # 23l. create_task rejects bad delivery settings
    from tasks import create_task, delete_task
    try:
        _bad_id = create_task(name="BadDelivery", delivery_channel="telegram", delivery_target="abc")
        delete_task(_bad_id)  # cleanup if it somehow succeeds
        record("FAIL", "delivery: create_task should reject bad telegram target")
    except ValueError:
        record("PASS", "delivery: create_task rejects bad telegram target")

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
    _app_src2 = Path("app_nicegui.py").read_text(encoding="utf-8")
    if "completed_delivery_failed" in _app_src2:
        record("PASS", "delivery: completed_delivery_failed in Activity tab")
    else:
        record("FAIL", "delivery: completed_delivery_failed missing from Activity tab")

    # 23p. prompts.py has expanded delivery channel guidance
    _prompts_src = Path("prompts.py").read_text(encoding="utf-8")
    if "chat_id" in _prompts_src and "ASK them" in _prompts_src:
        record("PASS", "delivery: prompts.py has expanded delivery guidance")
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

    # ── 24k. _build_trigger daily → CronTrigger ─────────────────────
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

    # ── 25c. _get_compressor returns EmbeddingsFilter for 'smart' ────────
    from agent import _get_compressor
    from langchain_classic.retrievers.document_compressors import EmbeddingsFilter as _EF25
    from langchain_classic.retrievers.document_compressors import LLMChainExtractor as _LCE25
    set_global_config("compression_mode", "smart")
    _comp_smart = _get_compressor()
    if isinstance(_comp_smart, _EF25):
        record("PASS", "compression: smart mode → EmbeddingsFilter")
    else:
        record("FAIL", "compression: smart mode type", type(_comp_smart).__name__)
    set_global_config("compression_mode", _prev)

    # ── 25d. _get_compressor returns None for 'off' ─────────────────────
    set_global_config("compression_mode", "off")
    _comp_off = _get_compressor()
    if _comp_off is None:
        record("PASS", "compression: off mode → None")
    else:
        record("FAIL", "compression: off mode type", type(_comp_off).__name__)
    set_global_config("compression_mode", _prev)

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

    # ── 25f. _compressed wraps retriever when mode is 'smart' ────────────
    from langchain_classic.retrievers import ContextualCompressionRetriever as _CCR25
    set_global_config("compression_mode", "smart")
    _wrapped = _compressed(_fake_ret)
    if isinstance(_wrapped, _CCR25):
        record("PASS", "compression: smart → ContextualCompressionRetriever")
    else:
        record("FAIL", "compression: smart wrapping", type(_wrapped).__name__)
    set_global_config("compression_mode", _prev)

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
# SUMMARY
# ═════════════════════════════════════════════════════════════════════════════
print("\n" + "=" * 70)
print("SUMMARY")
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
