"""Tasks — scheduled and on-demand agent actions with optional channel delivery.

A *task* is a named action (one or more prompts) that can run manually,
on a recurring schedule, or once at a specific time.  Tasks subsume both
the old "workflow" concept (multi-step prompt chains) and the old "timer"
concept (notify-only one-shot reminders).

Key features beyond v2.2.0 workflows
-------------------------------------
* Cron expressions via APScheduler ``CronTrigger``
* One-shot ``at`` field (ISO datetime) for "remind me at 3 PM" style tasks
* ``notify_only`` flag — fire a desktop / channel notification without
  invoking the agent (replaces timer_tool)
* ``delivery_channel`` / ``delivery_target`` — send results to Telegram
  or Email in addition to the always-on desktop + in-app notification
* ``model_override`` — per-task model selection
* ``persistent_thread_id`` — opt-in to reuse the same conversation thread
  across runs

Storage: SQLite at ``~/.thoth/tasks.db``.
Migration: on first import, existing ``workflows.db`` data is migrated
automatically and the old file is kept as a backup.
"""

from __future__ import annotations

import json
import logging
import os
import pathlib
import shutil
import sqlite3
import threading
import uuid
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

# ── Persistence ──────────────────────────────────────────────────────────────
_DATA_DIR = pathlib.Path(
    os.environ.get("THOTH_DATA_DIR", pathlib.Path.home() / ".thoth")
)
_DATA_DIR.mkdir(parents=True, exist_ok=True)
_DB_PATH = str(_DATA_DIR / "tasks.db")
_OLD_WF_DB = str(_DATA_DIR / "workflows.db")


def _get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(_DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def _init_db() -> None:
    """Create the tasks and task_runs tables if they don't exist."""
    conn = _get_conn()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS tasks (
            id                  TEXT PRIMARY KEY,
            name                TEXT NOT NULL,
            description         TEXT DEFAULT '',
            icon                TEXT DEFAULT '⚡',
            prompts             TEXT NOT NULL,          -- JSON list of prompt strings
            schedule            TEXT,                   -- recurring: daily:HH:MM / weekly:DAY:HH:MM / interval:H / cron:EXPR
            at                  TEXT,                   -- one-shot ISO datetime (mutually exclusive with schedule)
            notify_only         INTEGER DEFAULT 0,      -- 1 = fire notification only, no agent invocation
            notify_label        TEXT DEFAULT '',         -- label for notify-only tasks (replaces timer label)
            enabled             INTEGER DEFAULT 1,
            last_run            TEXT,
            created_at          TEXT NOT NULL,
            sort_order          INTEGER DEFAULT 0,
            delivery_channel    TEXT,                   -- null / 'telegram' / 'email'
            delivery_target     TEXT,                   -- chat_id or email address
            model_override      TEXT,                   -- null = use global default model
            persistent_thread_id TEXT,                  -- null = fresh thread each run
            delete_after_run    INTEGER DEFAULT 0,      -- 1 = auto-delete after one-shot execution
            allowed_commands    TEXT DEFAULT '[]',      -- JSON list of allowed shell command prefixes for background runs
            allowed_recipients  TEXT DEFAULT '[]',      -- JSON list of allowed email recipients for background runs
            skills_override     TEXT                    -- JSON list of skill names (null = use global)
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS task_runs (
            id              TEXT PRIMARY KEY,
            task_id         TEXT NOT NULL,
            thread_id       TEXT NOT NULL,
            started_at      TEXT NOT NULL,
            finished_at     TEXT,
            status          TEXT DEFAULT 'running',     -- running / completed / failed / completed_delivery_failed
            status_message  TEXT DEFAULT '',             -- human-readable detail (delivery result, error reason)
            steps_total     INTEGER DEFAULT 0,
            steps_done      INTEGER DEFAULT 0,
            FOREIGN KEY (task_id) REFERENCES tasks(id) ON DELETE CASCADE
        )
    """)
    # Migrations for pre-existing databases
    # Migrations for tasks table
    for col, defn in [
        ("allowed_commands", "TEXT DEFAULT '[]'"),
        ("allowed_recipients", "TEXT DEFAULT '[]'"),
        ("model_override", "TEXT"),
        ("skills_override", "TEXT"),
    ]:
        try:
            conn.execute(f"ALTER TABLE tasks ADD COLUMN {col} {defn}")
            logger.info("Migrated tasks table: added '%s' column", col)
        except Exception:
            pass  # column already exists

    for col, defn in [
        ("status_message", "TEXT DEFAULT ''"),
        ("task_name", "TEXT DEFAULT ''"),
        ("task_icon", "TEXT DEFAULT ''"),
    ]:
        try:
            conn.execute(f"ALTER TABLE task_runs ADD COLUMN {col} {defn}")
            logger.info("Migrated task_runs table: added '%s' column", col)
        except Exception:
            pass  # column already exists
    conn.commit()
    conn.close()


def _migrate_from_workflows() -> None:
    """Migrate data from the old workflows.db to the new tasks.db.

    Runs once — only if workflows.db exists and a marker file has not been
    written yet.  The marker prevents re-migration when the user intentionally
    deletes tasks.db to get fresh defaults.
    """
    _MARKER = os.path.join(_DATA_DIR, ".workflows_migrated")
    if os.path.exists(_MARKER):
        return  # Already migrated in a prior run
    if not os.path.exists(_OLD_WF_DB):
        return

    conn = _get_conn()
    count = conn.execute("SELECT COUNT(*) FROM tasks").fetchone()[0]
    if count > 0:
        conn.close()
        # DB already has data (e.g. from a previous migration) — mark done
        open(_MARKER, "w").close()
        return

    try:
        old_conn = sqlite3.connect(_OLD_WF_DB, check_same_thread=False)
        old_conn.row_factory = sqlite3.Row

        # Check old schema exists
        tables = {r[0] for r in old_conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()}
        if "workflows" not in tables:
            old_conn.close()
            conn.close()
            return

        rows = old_conn.execute("SELECT * FROM workflows").fetchall()
        for row in rows:
            d = dict(row)
            conn.execute(
                "INSERT INTO tasks "
                "(id, name, description, icon, prompts, schedule, enabled, "
                "last_run, created_at, sort_order) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    d["id"], d["name"], d.get("description", ""),
                    d.get("icon", "⚡"), d["prompts"],
                    d.get("schedule"), d.get("enabled", 1),
                    d.get("last_run"), d["created_at"],
                    d.get("sort_order", 0),
                ),
            )

        # Migrate run history
        if "workflow_runs" in tables:
            runs = old_conn.execute("SELECT * FROM workflow_runs").fetchall()
            for run in runs:
                r = dict(run)
                conn.execute(
                    "INSERT INTO task_runs "
                    "(id, task_id, thread_id, started_at, finished_at, "
                    "status, steps_total, steps_done) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        r["id"], r["workflow_id"], r["thread_id"],
                        r["started_at"], r.get("finished_at"),
                        r.get("status", "completed"),
                        r.get("steps_total", 0), r.get("steps_done", 0),
                    ),
                )

        conn.commit()
        old_conn.close()
        # Mark migration done so we never re-migrate if the user deletes tasks.db
        open(_MARKER, "w").close()
        logger.info(
            "Migrated %d tasks from workflows.db → tasks.db", len(rows)
        )
    except Exception as exc:
        logger.warning("Workflow migration failed (non-fatal): %s", exc)
    finally:
        conn.close()


_init_db()
_migrate_from_workflows()


# ── Template Variables ───────────────────────────────────────────────────────

def expand_template_vars(prompt: str, task_id: str | None = None) -> str:
    """Replace ``{{variable}}`` placeholders with current values."""
    now = datetime.now()
    replacements = {
        "date": now.strftime("%B %d, %Y"),
        "day": now.strftime("%A"),
        "time": now.strftime("%I:%M %p"),
        "month": now.strftime("%B"),
        "year": str(now.year),
    }
    if task_id:
        replacements["task_id"] = task_id
    result = prompt
    for key, value in replacements.items():
        result = result.replace("{{" + key + "}}", value)
    return result


# ── CRUD ─────────────────────────────────────────────────────────────────────

def create_task(
    name: str,
    prompts: list[str] | None = None,
    description: str = "",
    icon: str = "⚡",
    schedule: str | None = None,
    at: str | None = None,
    notify_only: bool = False,
    notify_label: str = "",
    delivery_channel: str | None = None,
    delivery_target: str | None = None,
    model_override: str | None = None,
    persistent_thread_id: str | None = None,
    delete_after_run: bool = False,
    delay_minutes: float | None = None,
    skills_override: list[str] | None = None,
) -> str:
    """Create a new task and return its ID.

    *delay_minutes* is a convenience for quick timers: it computes
    ``at = now + N minutes`` and automatically sets ``delete_after_run``
    so the LLM never needs to compute an ISO datetime.

    Only ONE of *schedule*, *at*, *delay_minutes* may be provided.
    """
    # ── Mutual-exclusivity check ──────────────────────────────────────
    _set_count = sum(1 for v in (schedule, at, delay_minutes) if v)
    if _set_count > 1:
        raise ValueError(
            "Only one of schedule, at, or delay_minutes may be set."
        )

    # ── delay_minutes → at conversion ────────────────────────────────
    if delay_minutes is not None:
        if delay_minutes <= 0:
            raise ValueError("delay_minutes must be positive.")
        at = (datetime.now() + timedelta(minutes=delay_minutes)).isoformat()
        delete_after_run = True  # one-shot timers auto-delete

    # ── Validate delivery settings ────────────────────────────────────
    _validate_delivery(delivery_channel, delivery_target)

    task_id = uuid.uuid4().hex[:12]
    now = datetime.now().isoformat()
    if prompts is None:
        prompts = []
    conn = _get_conn()
    conn.execute(
        "INSERT INTO tasks "
        "(id, name, description, icon, prompts, schedule, at, notify_only, "
        "notify_label, delivery_channel, delivery_target, model_override, "
        "persistent_thread_id, delete_after_run, created_at, skills_override) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            task_id, name, description, icon, json.dumps(prompts),
            schedule, at, int(notify_only), notify_label,
            delivery_channel, delivery_target, model_override,
            persistent_thread_id, int(delete_after_run), now,
            json.dumps(skills_override) if skills_override else None,
        ),
    )
    conn.commit()
    conn.close()

    # Sync APScheduler job (no-op if scheduler not yet started)
    if _scheduler is not None:
        task = get_task(task_id)
        if task:
            _sync_job(task)

    return task_id


def get_task(task_id: str) -> dict | None:
    conn = _get_conn()
    row = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
    conn.close()
    if not row:
        return None
    return _row_to_dict(row)


def list_tasks() -> list[dict]:
    conn = _get_conn()
    rows = conn.execute(
        "SELECT * FROM tasks ORDER BY sort_order, created_at"
    ).fetchall()
    conn.close()
    return [_row_to_dict(r) for r in rows]


def update_task(task_id: str, **kwargs) -> None:
    """Update task fields.

    Accepted keys: name, description, icon, prompts (list[str]), schedule,
    at, notify_only, notify_label, enabled, sort_order, last_run,
    delivery_channel, delivery_target, model_override,
    persistent_thread_id, delete_after_run.
    """
    _ALLOWED = {
        "name", "description", "icon", "prompts", "schedule", "at",
        "notify_only", "notify_label", "enabled", "sort_order", "last_run",
        "delivery_channel", "delivery_target", "model_override",
        "persistent_thread_id", "delete_after_run",
        "allowed_commands", "allowed_recipients",
        "skills_override",
    }

    # ── Validate delivery if either field is being changed ───────────
    if "delivery_channel" in kwargs or "delivery_target" in kwargs:
        # Merge with existing values to get full picture
        task = get_task(task_id)
        if task:
            ch = kwargs.get("delivery_channel", task.get("delivery_channel"))
            tgt = kwargs.get("delivery_target", task.get("delivery_target"))
            _validate_delivery(ch, tgt)

    conn = _get_conn()
    for key, value in kwargs.items():
        if key not in _ALLOWED:
            continue
        if key in ("prompts", "allowed_commands", "allowed_recipients", "skills_override"):
            value = json.dumps(value)
        if key in ("notify_only", "delete_after_run"):
            value = int(value)
        conn.execute(
            f"UPDATE tasks SET {key} = ? WHERE id = ?",
            (value, task_id),
        )
    conn.commit()
    conn.close()

    # Re-sync APScheduler job if schedule-related fields changed
    _SCHEDULE_KEYS = {"schedule", "at", "enabled", "notify_only", "delete_after_run"}
    if _scheduler is not None and _SCHEDULE_KEYS & set(kwargs):
        task = get_task(task_id)
        if task:
            _sync_job(task)


def delete_task(task_id: str) -> None:
    _remove_job(task_id)
    conn = _get_conn()
    conn.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
    conn.commit()
    conn.close()


def duplicate_task(task_id: str) -> str | None:
    """Clone a task and return the new ID."""
    task = get_task(task_id)
    if not task:
        return None
    return create_task(
        name=f"{task['name']} (copy)",
        prompts=task["prompts"],
        description=task["description"],
        icon=task["icon"],
        schedule=None,  # don't copy schedule
        at=None,
        notify_only=task.get("notify_only", False),
        notify_label=task.get("notify_label", ""),
        delivery_channel=task.get("delivery_channel"),
        delivery_target=task.get("delivery_target"),
        model_override=task.get("model_override"),
        skills_override=task.get("skills_override"),
    )


def _row_to_dict(row: sqlite3.Row) -> dict:
    d = dict(row)
    d["prompts"] = json.loads(d["prompts"])
    d["notify_only"] = bool(d.get("notify_only", 0))
    d["delete_after_run"] = bool(d.get("delete_after_run", 0))
    d["enabled"] = bool(d.get("enabled", 1))
    d["allowed_commands"] = json.loads(d.get("allowed_commands") or "[]")
    d["allowed_recipients"] = json.loads(d.get("allowed_recipients") or "[]")
    raw_skills = d.get("skills_override")
    d["skills_override"] = json.loads(raw_skills) if raw_skills else None
    return d


# ── Run History ──────────────────────────────────────────────────────────────

def _record_run_start(task_id: str, thread_id: str, steps_total: int,
                      task_name: str = "", task_icon: str = "") -> str:
    run_id = uuid.uuid4().hex[:12]
    now = datetime.now().isoformat()
    conn = _get_conn()
    conn.execute(
        "INSERT INTO task_runs (id, task_id, thread_id, started_at, "
        "status, steps_total, steps_done, task_name, task_icon) "
        "VALUES (?, ?, ?, ?, 'running', ?, 0, ?, ?)",
        (run_id, task_id, thread_id, now, steps_total, task_name, task_icon),
    )
    conn.commit()
    conn.close()
    return run_id


def _update_run_progress(run_id: str, steps_done: int) -> None:
    conn = _get_conn()
    conn.execute(
        "UPDATE task_runs SET steps_done = ? WHERE id = ?",
        (steps_done, run_id),
    )
    conn.commit()
    conn.close()


def _finish_run(run_id: str, status: str = "completed",
                status_message: str = "") -> None:
    conn = _get_conn()
    conn.execute(
        "UPDATE task_runs SET status = ?, status_message = ?, finished_at = ? "
        "WHERE id = ?",
        (status, status_message, datetime.now().isoformat(), run_id),
    )
    conn.commit()
    conn.close()


def get_run_history(task_id: str, limit: int = 5) -> list[dict]:
    conn = _get_conn()
    rows = conn.execute(
        "SELECT * FROM task_runs WHERE task_id = ? "
        "ORDER BY started_at DESC LIMIT ?",
        (task_id, limit),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_recent_runs(limit: int = 10) -> list[dict]:
    """Return the most recent task runs across all tasks.

    Run rows carry their own ``task_name`` / ``task_icon`` so they remain
    visible in the Activity panel even after the parent task is deleted.
    """
    conn = _get_conn()
    rows = conn.execute(
        "SELECT r.id, r.task_id, r.thread_id, r.started_at, r.finished_at, "
        "r.status, r.status_message, r.steps_total, r.steps_done, "
        "COALESCE(NULLIF(r.task_name, ''), t.name, '(deleted)') AS task_name, "
        "COALESCE(NULLIF(r.task_icon, ''), t.icon, '⚡') AS task_icon "
        "FROM task_runs r LEFT JOIN tasks t ON r.task_id = t.id "
        "ORDER BY r.started_at DESC LIMIT ?",
        (limit,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_upcoming_tasks(limit: int = 5) -> list[dict]:
    """Return tasks that have a schedule or an ``at`` time, sorted by next run."""
    conn = _get_conn()
    rows = conn.execute(
        "SELECT * FROM tasks WHERE enabled = 1 "
        "AND (schedule IS NOT NULL OR at IS NOT NULL) "
        "ORDER BY COALESCE(at, '') DESC LIMIT ?",
        (limit,),
    ).fetchall()
    conn.close()
    return [_row_to_dict(r) for r in rows]


def get_next_fire_times(limit: int = 10) -> list[dict]:
    """Return upcoming scheduled task fire times from APScheduler."""
    if _scheduler is None:
        return []
    results = []
    for job in _scheduler.get_jobs():
        if not job.id.startswith("task_"):
            continue
        task_id = job.id[5:]  # strip "task_" prefix
        task = get_task(task_id)
        if not task:
            continue
        next_time = job.next_run_time
        if next_time is None:
            continue
        results.append({
            "task_id": task_id,
            "task_name": task["name"],
            "task_icon": task["icon"],
            "next_run": next_time.isoformat(),
            "schedule": task.get("schedule") or task.get("at") or "",
        })
    results.sort(key=lambda x: x["next_run"])
    return results[:limit]


# ── Background Execution Engine ──────────────────────────────────────────────

_active_runs: dict[str, dict] = {}  # thread_id -> {task_id, run_id, step, total, name}
_active_lock = threading.Lock()


def get_running_tasks() -> dict[str, dict]:
    """Return ``{thread_id: {task_id, run_id, step, total, name}}``
    for all in-flight task executions."""
    with _active_lock:
        return dict(_active_runs)


def stop_task(thread_id: str) -> bool:
    """Signal a running task to stop.  Returns True if found & signalled."""
    with _active_lock:
        info = _active_runs.get(thread_id)
        if info and "stop_event" in info:
            info["stop_event"].set()
            logger.info("stop_task: signalled stop for thread %s (task %s)",
                        thread_id, info.get("name", "?"))
            return True
    return False


def get_running_task_thread(task_id: str) -> str | None:
    """Return the thread_id of a currently-running task, or None."""
    with _active_lock:
        for tid, info in _active_runs.items():
            if info.get("task_id") == task_id:
                return tid
    return None


# Backward-compat alias used by app_nicegui sidebar
get_running_workflows = get_running_tasks


def _validate_delivery(channel: str | None, target: str | None) -> None:
    """Raise ``ValueError`` if delivery settings are invalid.

    Rules
    -----
    * If *channel* is set, *target* must also be set (and vice-versa).
    * ``telegram`` target must be parseable as ``int`` (chat ID).
    * ``email`` target must look like a bare email address (contains ``@``
      and at least one ``.`` after the ``@``).
    """
    if not channel and not target:
        return  # no delivery — valid
    if channel and not target and channel != "telegram":
        raise ValueError(
            f"delivery_channel is '{channel}' but delivery_target is empty."
        )
    if target and not channel:
        raise ValueError(
            "delivery_target is set but delivery_channel is empty."
        )
    if channel not in ("telegram", "email"):
        raise ValueError(
            f"delivery_channel must be 'telegram' or 'email', got '{channel}'."
        )
    if channel == "telegram":
        # Telegram always uses the configured TELEGRAM_USER_ID at delivery
        # time — no target field needed. Just verify the bot is configured.
        pass
    elif channel == "email":
        if "@" not in target or "." not in target.split("@", 1)[-1]:
            raise ValueError(
                f"Email delivery_target must be a valid email address, got '{target}'."
            )


def _deliver_to_channel(task: dict, text: str) -> tuple[str, str]:
    """Send task output to the configured delivery channel (if any).

    Returns
    -------
    tuple[str, str]
        ``("delivered", detail)`` on success,
        ``("delivery_failed", reason)`` on error,
        or ``("", "")`` if no delivery was configured.
    """
    channel = task.get("delivery_channel")
    target = task.get("delivery_target")
    if not channel:
        return "", ""
    try:
        if channel == "telegram":
            from channels.telegram import send_outbound, _get_allowed_user_id
            user_id = _get_allowed_user_id()
            if user_id is None:
                raise RuntimeError("TELEGRAM_USER_ID is not configured")
            prefix = f"📋 {task['name']}\n\n"
            send_outbound(user_id, prefix + text)
        elif channel == "email":
            if not target:
                raise ValueError("Email delivery_target is empty")
            from channels.email import send_outbound
            send_outbound(target, f"FromThoth: {task['name']}", text)
        logger.info(
            "Delivery to %s succeeded for task %s", channel, task["name"],
        )
        return "delivered", f"Delivered to {channel}"
    except Exception as exc:
        logger.warning(
            "Delivery to %s failed for task %s: %s",
            channel, task["name"], exc,
        )
        return "delivery_failed", f"{channel} delivery failed: {exc}"


def run_task_background(
    task_id: str,
    thread_id: str,
    enabled_tool_names: list[str],
    start_step: int = 0,
    notification: bool = True,
) -> None:
    """Execute a task in a background thread.

    For multi-step tasks each prompt is sent to the agent via
    ``invoke_agent`` sequentially.  For notify-only tasks, a desktop
    notification is fired immediately with no agent invocation.
    """
    task = get_task(task_id)
    if not task:
        return

    # ── Notify-only tasks (timer replacement) ────────────────────────
    if task.get("notify_only"):
        label = task.get("notify_label") or task["name"]
        from notifications import notify
        notify(
            title="⏰ Thoth Reminder",
            message=label,
            sound="timer",
            icon="⏰",
        )
        # Record run *before* delivery so Activity always has an entry
        run_id = _record_run_start(task_id, thread_id, 0,
                                   task_name=task["name"], task_icon=task["icon"])
        try:
            delivery_status, delivery_detail = _deliver_to_channel(
                task, f"⏰ Reminder: {label}",
            )
        except Exception as exc:
            logger.error("Notify-only delivery crashed for task %s: %s",
                         task["name"], exc)
            delivery_status = "delivery_failed"
            delivery_detail = f"{task.get('delivery_channel', '?')} delivery failed: {exc}"
        update_task(task_id, last_run=datetime.now().isoformat())
        final_status = ("completed_delivery_failed"
                        if delivery_status == "delivery_failed"
                        else "completed")
        _finish_run(run_id, final_status, status_message=delivery_detail)
        if delivery_status == "delivery_failed":
            notify(
                title="⚠️ Delivery Failed",
                message=f"{task['name']} — {delivery_detail}",
                sound="timer",
                icon="⚠️",
            )
        if task.get("delete_after_run"):
            delete_task(task_id)
        return

    # ── Multi-step prompt tasks ──────────────────────────────────────
    prompts = task["prompts"]
    if not prompts:
        return
    total = len(prompts)
    run_id = _record_run_start(task_id, thread_id, total,
                               task_name=task["name"], task_icon=task["icon"])

    def _run():
        from agent import invoke_agent, TaskStoppedError
        from threads import _save_thread_meta, _list_threads

        def _thread_exists(tid):
            return any(t[0] == tid for t in _list_threads())

        _stop_event = threading.Event()

        with _active_lock:
            _active_runs[thread_id] = {
                "task_id": task_id,
                "run_id": run_id,
                "step": start_step,
                "total": total,
                "name": task["name"],
                "stop_event": _stop_event,
            }

        last_response = ""
        stopped = False

        try:
            from agent import _background_workflow_var
            _background_workflow_var.set(True)

            from agent import RECURSION_LIMIT_TASK
            config = {
                "configurable": {"thread_id": thread_id},
                "recursion_limit": RECURSION_LIMIT_TASK,
            }

            # Model override
            if task.get("model_override"):
                config["configurable"]["model_override"] = task["model_override"]
                # Set on thread immediately so the UI shows the correct model
                # while the task is still running.
                from threads import _set_thread_model_override
                _set_thread_model_override(thread_id, task["model_override"])

            # Skills override — set on thread so the pre-model hook picks it up
            if task.get("skills_override") is not None:
                from threads import set_thread_skills_override
                set_thread_skills_override(thread_id, task["skills_override"])

            # Task-scoped permissions — propagate via ContextVars
            # so tools can check them at runtime.
            from agent import (
                _task_allowed_commands_var,
                _task_allowed_recipients_var,
            )
            _task_allowed_commands_var.set(
                task.get("allowed_commands") or []
            )
            _task_allowed_recipients_var.set(
                task.get("allowed_recipients") or []
            )

            for i in range(start_step, total):
                # ── Check stop before each step ──────────────────────
                if _stop_event.is_set():
                    stopped = True
                    logger.info("Task '%s' stopped before step %d/%d",
                                task["name"], i + 1, total)
                    break

                with _active_lock:
                    _active_runs[thread_id]["step"] = i

                prompt = expand_template_vars(prompts[i], task_id=task_id)

                try:
                    result = invoke_agent(prompt, enabled_tool_names, config,
                                         stop_event=_stop_event)
                    if result:
                        last_response = result
                except TaskStoppedError:
                    stopped = True
                    logger.info("Task '%s' stopped during step %d/%d",
                                task["name"], i + 1, total)
                    break
                except Exception as exc:
                    err_str = str(exc).lower()
                    # If the override model failed to load, fall back to the
                    # default model and retry this step once.
                    if (config["configurable"].get("model_override")
                            and ("model failed to load" in err_str
                                 or "status code: 500" in err_str)):
                        override = config["configurable"].pop("model_override")
                        logger.warning(
                            "Task %s step %d: override model '%s' failed to load — "
                            "retrying with default model. (%s)",
                            task["name"], i + 1, override, exc,
                        )
                        try:
                            result = invoke_agent(prompt, enabled_tool_names, config,
                                                 stop_event=_stop_event)
                            if result:
                                last_response = result
                        except TaskStoppedError:
                            stopped = True
                            logger.info("Task '%s' stopped during step %d/%d (retry)",
                                        task["name"], i + 1, total)
                            break
                        except Exception as retry_exc:
                            logger.error(
                                "Task %s step %d failed on retry with default model: %s",
                                task["name"], i + 1, retry_exc,
                            )
                    else:
                        logger.error(
                            "Task %s step %d failed: %s", task["name"], i + 1, exc
                        )
                    try:
                        from agent import repair_orphaned_tool_calls
                        repair_orphaned_tool_calls(enabled_tool_names, config)
                    except Exception:
                        pass

                _update_run_progress(run_id, i + 1)

            # ── Handle stopped task ────────────────────────────────────
            if stopped:
                # Repair any orphaned tool calls left mid-step
                try:
                    from agent import repair_orphaned_tool_calls
                    repair_orphaned_tool_calls(enabled_tool_names, config)
                except Exception:
                    pass
                _finish_run(run_id, "stopped")
                if _thread_exists(thread_id):
                    thread_name = (f"⚡ {task['name']} (stopped) — "
                                   f"{datetime.now().strftime('%b %d, %I:%M %p')}")
                    _save_thread_meta(thread_id, thread_name)
                if notification:
                    from notifications import notify
                    notify(
                        title="⏹️ Task Stopped",
                        message=f"{task['name']} was stopped.",
                        sound="workflow",
                        icon="⏹️",
                    )
                return  # skip delivery, skip delete_after_run

            # ── Determine final status ────────────────────────────────
            delivery_status, delivery_detail = "", ""
            if task.get("delivery_channel") and task.get("delivery_target"):
                deliver_text = last_response or f"✅ Task '{task['name']}' completed."
                delivery_status, delivery_detail = _deliver_to_channel(
                    task, deliver_text,
                )

            final_status = ("completed_delivery_failed"
                            if delivery_status == "delivery_failed"
                            else "completed")
            _finish_run(run_id, final_status, status_message=delivery_detail)
            update_task(task_id, last_run=datetime.now().isoformat())

            # Thread naming (skip if thread was deleted while running)
            if _thread_exists(thread_id):
                thread_name = f"⚡ {task['name']} — {datetime.now().strftime('%b %d, %I:%M %p')}"
                _save_thread_meta(thread_id, thread_name)

            # Desktop + in-app notification (always)
            if notification:
                from notifications import notify
                suffix = ""
                if delivery_status == "delivered":
                    suffix = f" → {delivery_detail}"
                elif delivery_status == "delivery_failed":
                    suffix = f" (⚠️ {delivery_detail})"
                notify(
                    title="⚡ Task Complete",
                    message=f"{task['name']} finished ({total} step{'s' if total != 1 else ''}).{suffix}",
                    sound="workflow",
                    icon="⚡",
                )
                if delivery_status == "delivery_failed":
                    notify(
                        title="⚠️ Delivery Failed",
                        message=f"{task['name']} — {delivery_detail}",
                        sound="timer",
                        icon="⚠️",
                    )

            # Auto-delete one-shot tasks
            if task.get("delete_after_run"):
                delete_task(task_id)

        except Exception as exc:
            logger.error("Task %s crashed: %s", task["name"], exc)
            _finish_run(run_id, "failed", status_message=str(exc))
        finally:
            with _active_lock:
                _active_runs.pop(thread_id, None)
            # Release the browser tab owned by this thread (if any)
            try:
                from tools.browser_tool import get_session_manager as _get_bsm
                _get_bsm().kill_session(thread_id)
            except Exception:
                pass

    t = threading.Thread(target=_run, daemon=True, name=f"task-{task_id}")
    t.start()


# ── Scheduler (APScheduler) ──────────────────────────────────────────────────
# Each enabled task gets a real APScheduler job with the appropriate trigger
# (CronTrigger, IntervalTrigger, DateTrigger).  Adding/updating/deleting a
# task automatically syncs the scheduler.

_scheduler: "BackgroundScheduler | None" = None
_scheduler_lock = threading.Lock()


def _get_scheduler():
    """Return the singleton BackgroundScheduler, creating it if needed."""
    global _scheduler
    if _scheduler is not None:
        return _scheduler
    with _scheduler_lock:
        if _scheduler is not None:
            return _scheduler
        from apscheduler.schedulers.background import BackgroundScheduler
        _scheduler = BackgroundScheduler(
            job_defaults={"coalesce": True, "max_instances": 1, "misfire_grace_time": 120},
        )
        _scheduler.start()
        logger.info("APScheduler BackgroundScheduler started")
    return _scheduler


def _parse_schedule(schedule: str | None) -> dict | None:
    """Parse schedule strings into a dict.

    Formats:
        "daily:HH:MM"             → run every day at HH:MM
        "weekly:DAY:HH:MM"        → run every week on DAY at HH:MM
        "interval:HOURS"           → run every N hours (float OK, e.g. 0.5 = 30 min)
        "interval_minutes:MINUTES" → run every N minutes
        "cron:EXPR"                → cron expression (5-field)
    """
    if not schedule:
        return None
    parts = schedule.split(":", 1)
    if len(parts) < 2:
        return None

    kind = parts[0].lower()
    rest = parts[1]

    try:
        if kind == "daily":
            sub = rest.split(":")
            if len(sub) >= 2:
                return {"kind": "daily", "hour": int(sub[0]), "minute": int(sub[1])}
        elif kind == "weekly":
            sub = rest.split(":")
            if len(sub) >= 3:
                raw_day = sub[0].lower()
                _FULL_TO_ABBR = {
                    "monday": "mon", "tuesday": "tue", "wednesday": "wed",
                    "thursday": "thu", "friday": "fri", "saturday": "sat",
                    "sunday": "sun",
                }
                day_abbr = _FULL_TO_ABBR.get(raw_day, raw_day)
                return {
                    "kind": "weekly",
                    "day": day_abbr,
                    "hour": int(sub[1]),
                    "minute": int(sub[2]),
                }
        elif kind == "interval":
            return {"kind": "interval", "hours": float(rest)}
        elif kind == "interval_minutes":
            return {"kind": "interval_minutes", "minutes": float(rest)}
        elif kind == "cron":
            return {"kind": "cron", "expr": rest.strip()}
    except (ValueError, IndexError):
        pass
    return None


_DAY_MAP = {
    "mon": 0, "tue": 1, "wed": 2, "thu": 3,
    "fri": 4, "sat": 5, "sun": 6,
    "monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3,
    "friday": 4, "saturday": 5, "sunday": 6,
}

# Reverse map: weekday int → 3-letter APScheduler day string
_DAY_TO_AP = {0: "mon", 1: "tue", 2: "wed", 3: "thu", 4: "fri", 5: "sat", 6: "sun"}


def _build_trigger(task: dict):
    """Build an APScheduler trigger from a task's schedule/at fields.

    Returns a trigger object or *None* if the task has no valid schedule.
    """
    # One-shot ``at`` tasks — fire once at a specific datetime
    at_str = task.get("at")
    if at_str:
        try:
            from apscheduler.triggers.date import DateTrigger
            at_dt = datetime.fromisoformat(at_str)
            # Only schedule if in the future
            if at_dt > datetime.now():
                return DateTrigger(run_date=at_dt)
            # Already past — check if it already fired
            lr = task.get("last_run")
            if lr:
                try:
                    if datetime.fromisoformat(lr) >= at_dt:
                        return None  # Already fired
                except (ValueError, TypeError):
                    pass
            # Past but never fired — fire immediately
            return DateTrigger(run_date=datetime.now() + timedelta(seconds=2))
        except (ValueError, TypeError):
            pass
        return None

    sched = _parse_schedule(task.get("schedule"))
    if not sched:
        return None

    kind = sched["kind"]

    if kind == "daily":
        from apscheduler.triggers.cron import CronTrigger
        return CronTrigger(hour=sched["hour"], minute=sched["minute"])

    elif kind == "weekly":
        from apscheduler.triggers.cron import CronTrigger
        day_int = _DAY_MAP.get(sched["day"])
        if day_int is None:
            return None
        ap_day = _DAY_TO_AP[day_int]
        return CronTrigger(day_of_week=ap_day, hour=sched["hour"], minute=sched["minute"])

    elif kind == "interval":
        from apscheduler.triggers.interval import IntervalTrigger
        hours = sched["hours"]
        if hours <= 0:
            return None
        return IntervalTrigger(hours=hours)

    elif kind == "interval_minutes":
        from apscheduler.triggers.interval import IntervalTrigger
        minutes = sched["minutes"]
        if minutes <= 0:
            return None
        return IntervalTrigger(minutes=int(minutes))

    elif kind == "cron":
        try:
            from apscheduler.triggers.cron import CronTrigger
            return CronTrigger.from_crontab(sched["expr"])
        except Exception:
            logger.warning("Invalid cron expression: %s", sched["expr"])
            return None

    return None


def _job_id(task_id: str) -> str:
    """Deterministic APScheduler job ID for a task."""
    return f"task_{task_id}"


def _on_task_fire(task_id: str) -> None:
    """Callback invoked by APScheduler when a task's trigger fires."""
    from tools import registry as tool_registry

    task = get_task(task_id)
    if not task:
        return
    if not task.get("enabled", True):
        return

    logger.info("Scheduler firing task: %s", task["name"])
    update_task(task_id, last_run=datetime.now().isoformat())

    thread_id = task.get("persistent_thread_id") or uuid.uuid4().hex[:12]
    enabled = [t.name for t in tool_registry.get_enabled_tools()]

    # Create thread_meta row BEFORE starting the background run so
    # (a) the thread appears in the sidebar immediately, and
    # (b) _thread_exists() returns True at completion, allowing the
    #     final rename/save.  Mirrors the manual-run handler in
    #     app_nicegui.py.
    from threads import _save_thread_meta
    thread_name = (
        f"\u26a1 {task['name']} — "
        f"{datetime.now().strftime('%b %d, %I:%M %p')}"
    )
    _save_thread_meta(thread_id, thread_name)

    if task.get("model_override"):
        from threads import _set_thread_model_override
        _set_thread_model_override(thread_id, task["model_override"])

    run_task_background(task_id, thread_id, enabled, notification=True)

    # Auto-remove one-shot `at` tasks after firing
    if task.get("at") and task.get("delete_after_run"):
        _remove_job(task_id)


def _sync_job(task: dict) -> None:
    """Add or update the APScheduler job for a single task."""
    scheduler = _get_scheduler()
    jid = _job_id(task["id"])

    if not task.get("enabled", True):
        # Disabled — remove job if it exists
        try:
            scheduler.remove_job(jid)
        except Exception:
            pass
        return

    trigger = _build_trigger(task)
    if trigger is None:
        # No valid schedule — remove any leftover job
        try:
            scheduler.remove_job(jid)
        except Exception:
            pass
        return

    # Add or replace the job
    scheduler.add_job(
        _on_task_fire,
        trigger=trigger,
        args=[task["id"]],
        id=jid,
        name=task["name"],
        replace_existing=True,
    )


def _remove_job(task_id: str) -> None:
    """Remove the APScheduler job for a task (if it exists)."""
    if _scheduler is None:
        return
    try:
        _scheduler.remove_job(_job_id(task_id))
    except Exception:
        pass


def sync_all_jobs() -> None:
    """(Re-)sync every task to the APScheduler job store."""
    tasks = list_tasks()
    for task in tasks:
        _sync_job(task)
    logger.info("Synced %d task(s) to APScheduler", len(tasks))


def start_task_scheduler() -> None:
    """Start the APScheduler and sync all task jobs (idempotent)."""
    _get_scheduler()
    sync_all_jobs()


# Backward-compat alias
start_workflow_scheduler = start_task_scheduler


# ── Global Retry Config ──────────────────────────────────────────────────────

_RETRY_CONFIG_PATH = str(_DATA_DIR / "task_config.json")


def get_retry_max() -> int:
    """Return the global max retries (default 1 = no retry)."""
    try:
        with open(_RETRY_CONFIG_PATH) as f:
            return json.load(f).get("retry_max", 1)
    except (FileNotFoundError, json.JSONDecodeError):
        return 1


def set_retry_max(value: int) -> None:
    """Save the global retry setting."""
    data = {}
    try:
        with open(_RETRY_CONFIG_PATH) as f:
            data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        pass
    data["retry_max"] = max(1, value)
    with open(_RETRY_CONFIG_PATH, "w") as f:
        json.dump(data, f, indent=2)


# ── Default Templates ────────────────────────────────────────────────────────

_DEFAULT_TASKS = [
    {
        "name": "Morning Briefing",
        "description": "News, weather, and today's calendar — delivered every morning",
        "icon": "🌅",
        "prompts": [
            "Give me a brief summary of the top 5 news stories today.",
            "What's the weather forecast for today and tomorrow?",
            "What events do I have on my calendar for {{date}}?",
            "Now combine everything above into a single morning briefing. "
            "Start with the weather, then calendar, then news headlines.",
        ],
        "schedule": "daily:08:00",
    },
    {
        "name": "Research Digest",
        "description": "Weekly AI research roundup with sources",
        "icon": "🔬",
        "prompts": [
            "Search the web for the latest developments in artificial intelligence this week. "
            "Find at least 5 notable stories, papers, or breakthroughs.",
            "Now summarize your findings into a well-structured weekly digest with bullet points "
            "and source citations for each item. Group by category (models, applications, policy).",
        ],
        "schedule": "weekly:fri:17:00",
    },
    {
        "name": "Inbox Zero",
        "description": "Check and triage unread emails",
        "icon": "📧",
        "prompts": [
            "Check my Gmail inbox for any unread or recent emails from today.",
            "Summarize each email in 1-2 sentences, grouped by priority "
            "(action required vs. informational). List the sender and subject for each.",
        ],
        "schedule": "daily:09:00",
    },
    {
        "name": "Weekly Review",
        "description": "Recap of the past week's events and priorities",
        "icon": "📋",
        "prompts": [
            "What events did I have on my calendar this past week (last 7 days)?",
            "Based on these events, write a short weekly review summarizing what I was busy "
            "with this week. Highlight any patterns and suggest priorities for next week.",
        ],
        "schedule": "weekly:sun:18:00",
    },
    {
        "name": "Stand-Up Reminder",
        "description": "Gentle reminder to stand up and stretch",
        "icon": "🧘",
        "notify_only": True,
        "notify_label": "Time to stand up and stretch! 🧘",
        "prompts": [],
        "schedule": "interval:2",
    },
]


def seed_default_tasks() -> None:
    """Insert default task templates on first-ever run only.

    Uses a marker file so that if the user deletes all tasks the defaults
    do NOT reappear on the next restart.
    """
    _MARKER = os.path.join(_DATA_DIR, ".tasks_seeded")
    if os.path.exists(_MARKER):
        return  # Already seeded in a prior run — user may have deleted them
    existing = list_tasks()
    if existing:
        # DB has tasks (e.g. migrated from workflows) — mark as seeded
        open(_MARKER, "w").close()
        return
    for t in _DEFAULT_TASKS:
        create_task(
            name=t["name"],
            prompts=t.get("prompts", []),
            description=t.get("description", ""),
            icon=t.get("icon", "⚡"),
            schedule=t.get("schedule"),
            notify_only=t.get("notify_only", False),
            notify_label=t.get("notify_label", ""),
        )
    open(_MARKER, "w").close()
    logger.info("Seeded %d default tasks", len(_DEFAULT_TASKS))


# Backward-compat aliases for app_nicegui.py transition
seed_default_workflows = seed_default_tasks
list_workflows = list_tasks
create_workflow = lambda name, prompts, description="", icon="⚡", schedule=None: create_task(
    name=name, prompts=prompts, description=description, icon=icon, schedule=schedule,
)
update_workflow = update_task
delete_workflow = delete_task
duplicate_workflow = duplicate_task
run_workflow_background = run_task_background
