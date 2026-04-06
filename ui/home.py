"""Thoth UI — Home screen (Tasks / Knowledge Graph / Activity tabs).

Extracted from the monolith's ``_build_home`` inner function.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime
from typing import Callable

from nicegui import run, ui

from ui.state import AppState, P
from ui.constants import welcome_message, EXAMPLE_PROMPTS

logger = logging.getLogger(__name__)


def build_home(
    state: AppState,
    p: P,
    *,
    rebuild_main: Callable,
    rebuild_thread_list: Callable,
    send_message: Callable,
    show_task_dialog: Callable,
    build_graph_panel: Callable,
    is_first_run: Callable,
    mark_onboarding_seen: Callable,
    open_settings: Callable | None = None,
) -> None:
    """Render the home screen with Tasks / Knowledge Graph / Activity tabs."""
    from models import is_cloud_model, get_current_model
    from tools import registry as tool_registry
    from threads import _save_thread_meta
    from tasks import (
        list_tasks, update_task, run_task_background,
        get_running_tasks, get_running_task_thread, stop_task,
        get_next_fire_times, get_recent_runs,
    )
    from memory_extraction import get_extraction_status

    # ── Status bar (replaces old logo) ───────────────────────────────
    from ui.status_bar import build_status_bar
    _open = open_settings if open_settings else lambda tab: None
    build_status_bar(open_settings=_open)

    # ── Tab toggle ───────────────────────────────────────────────────
    with ui.tabs().classes("w-full shrink-0").props(
        "no-caps inline-label active-color=amber indicator-color=amber "
        "align=center"
    ).style("border-bottom: 1px solid rgba(255,255,255,0.08);") as home_tabs:
        tasks_tab = ui.tab("Tasks", icon="bolt")
        graph_tab = ui.tab("Knowledge", icon="psychology")
        activity_tab = ui.tab("Activity", icon="assessment")

    def _on_tab_change(e):
        if e.value == 'Knowledge':
            ui.run_javascript(
                'setTimeout(function() {'
                '  if (window.thothGraphRedraw) window.thothGraphRedraw();'
                '}, 50);'
            )

    with ui.tab_panels(home_tabs, value=tasks_tab, on_change=_on_tab_change).classes(
        "w-full flex-grow"
    ).style("overflow: hidden;"):

        # ── Tasks panel ──────────────────────────────────────────────
        with ui.tab_panel(tasks_tab).classes("h-full").style("padding: 0;"):
            with ui.scroll_area().classes("w-full h-full"):

                if state.show_onboarding:
                    with ui.card().classes("w-full"):
                        with ui.row().classes("w-full justify-between items-center"):
                            ui.label("")
                            def _dismiss_help():
                                state.show_onboarding = False
                                mark_onboarding_seen()
                                rebuild_main()
                            ui.button(icon="close", on_click=_dismiss_help).props("flat dense round size=sm")
                        _cloud_ob = is_cloud_model(get_current_model())
                        ui.markdown(welcome_message(cloud=_cloud_ob), extras=['code-friendly', 'fenced-code-blocks', 'tables'])
                        ui.separator()
                        ui.label("💡 Try asking me something:").classes("font-bold")
                        with ui.row().classes("w-full flex-wrap gap-2"):
                            for prompt in EXAMPLE_PROMPTS:
                                def _try(pr=prompt):
                                    state.show_onboarding = False
                                    mark_onboarding_seen()
                                    asyncio.create_task(send_message(pr))
                                ui.button(prompt, on_click=_try).props("flat dense outline").style("text-transform: none;")
                    if is_first_run():
                        mark_onboarding_seen()
                else:
                    ui.html(
                        '<p style="text-align:center; font-size:1.1rem; opacity:0.6;">'
                        'Select a conversation from the sidebar or start a new one.</p>',
                        sanitize=False,
                    )

                # Task tiles
                home_tasks = list_tasks()

                def _refresh_home_tiles():
                    rebuild_main()

                ui.separator()
                with ui.row().classes("w-full items-center justify-between"):
                    ui.label("⚡ Tasks").classes("text-h5")
                    ui.button("New Task", icon="add", on_click=lambda: show_task_dialog(
                        None, _refresh_home_tiles,
                    )).props("outline dense no-caps color=amber").style(
                        "font-weight: 600; font-size: 0.95rem;"
                    )

                if home_tasks:
                    with ui.element("div").classes("w-full").style(
                        "display: grid;"
                        "grid-template-columns: repeat(auto-fill, minmax(192px, 1fr));"
                        "gap: 1rem;"
                    ):
                        for tk in home_tasks:
                            _is_disabled = not tk.get("enabled", True)
                            card_style = "opacity: 0.45;" if _is_disabled else ""
                            with ui.card().classes("h-full").style(card_style):
                                ui.label(tk["icon"]).classes("text-h3 text-center w-full")
                                ui.label(tk["name"]).classes("font-bold text-center w-full")
                                if tk.get("description"):
                                    ui.label(tk["description"]).classes(
                                        "text-xs text-grey-6 text-center w-full"
                                    )
                                prompts = tk.get("prompts") or []
                                info = f"{len(prompts)} step{'s' if len(prompts) != 1 else ''}"
                                if tk.get("last_run"):
                                    try:
                                        lr = datetime.fromisoformat(tk["last_run"])
                                        info += f" · Last: {lr.strftime('%b %d')}"
                                    except (ValueError, TypeError):
                                        pass
                                sched = tk.get("schedule") or ""
                                if sched.startswith("daily"):
                                    info += " · 📅 Daily"
                                elif sched.startswith("weekly"):
                                    info += " · 📅 Weekly"
                                elif sched.startswith("interval"):
                                    info += " · 🔁 Interval"
                                elif sched.startswith("cron"):
                                    info += " · ⏱️ Cron"
                                if tk.get("notify_only"):
                                    info = "🔔 Reminder"
                                    if sched:
                                        if sched.startswith("daily"):
                                            info += " · 📅 Daily"
                                        elif sched.startswith("weekly"):
                                            info += " · 📅 Weekly"
                                ui.label(info).classes("text-xs text-grey-6 text-center w-full")

                                with ui.row().classes("w-full items-center justify-between mt-1"):
                                    def _toggle_enabled(e, t=tk):
                                        update_task(t["id"], enabled=e.value)
                                        _refresh_home_tiles()

                                    ui.switch(
                                        "", value=tk.get("enabled", True),
                                        on_change=_toggle_enabled,
                                    ).props("dense").tooltip(
                                        "Enabled" if tk.get("enabled", True) else "Disabled"
                                    )

                                    def _edit(t=tk):
                                        show_task_dialog(t, _refresh_home_tiles)

                                    ui.button(icon="edit", on_click=_edit).props(
                                        "flat dense round size=sm"
                                    ).tooltip("Edit")

                                    def _run_tk(t=tk):
                                        tid = uuid.uuid4().hex[:12]
                                        t_name = (
                                            f"⚡ {t['name']} — "
                                            f"{datetime.now().strftime('%b %d, %I:%M %p')}"
                                        )
                                        _save_thread_meta(tid, t_name)
                                        if t.get("model_override"):
                                            from threads import _set_thread_model_override
                                            _set_thread_model_override(tid, t["model_override"])
                                        bg_tools = [
                                            tl.name for tl in tool_registry.get_enabled_tools()
                                        ]
                                        run_task_background(
                                            t["id"], tid, bg_tools,
                                            start_step=0, notification=True,
                                        )
                                        ui.notify(
                                            f"⚡ {t['name']} started — you'll be notified when done.",
                                            type="positive",
                                        )
                                        rebuild_thread_list()
                                        ui.timer(0.3, _refresh_home_tiles, once=True)

                                    _running_tid = get_running_task_thread(tk["id"])
                                    if _running_tid:
                                        def _stop_tk(tid=_running_tid, t=tk):
                                            stop_task(tid)
                                            ui.notify(f"⏹️ Stopping {t['name']}…", type="warning")
                                            _refresh_home_tiles()
                                        ui.button(icon="stop", on_click=_stop_tk).props(
                                            "round color=red size=sm"
                                        ).tooltip("Stop running task")
                                    else:
                                        run_btn = ui.button(icon="play_arrow", on_click=_run_tk).props(
                                            "round color=green size=sm"
                                        ).tooltip("Run now")
                                        if _is_disabled:
                                            run_btn.disable()
                else:
                    ui.label("No tasks yet — click + New Task to get started.").classes(
                        "text-grey-6 text-sm q-mt-sm"
                    )

        # ── Graph panel ───────────────────────────────────────────
        with ui.tab_panel(graph_tab).classes("h-full").style(
            "padding: 0; overflow: hidden; display: flex; flex-direction: column;"
        ):
            build_graph_panel()

        # ── Activity panel ───────────────────────────────────────────
        with ui.tab_panel(activity_tab).classes("h-full").style("padding: 0;"):
            activity_container = ui.column().classes("w-full h-full")
            with activity_container:
                _build_activity_content(activity_container)

    # Home screen input row
    with ui.row().classes("w-full items-end gap-2 shrink-0 py-2"):
        home_input = ui.input(placeholder="Ask anything to start a conversation…").classes(
            "flex-grow"
        ).props('outlined dense')

        async def _home_send():
            text = home_input.value
            if text and text.strip():
                home_input.value = ""
                await send_message(text)

        home_input.on("keydown.enter", _home_send)
        ui.button(icon="send", on_click=_home_send).props("color=primary round")


# ══════════════════════════════════════════════════════════════════════
# ACTIVITY CONTENT
# ══════════════════════════════════════════════════════════════════════

def _build_activity_content(container) -> None:
    """Render the Activity tab content inside *container*."""
    from tasks import (
        get_running_tasks, stop_task,
        get_next_fire_times, get_recent_runs,
    )
    from memory_extraction import get_extraction_status

    with ui.scroll_area().classes("w-full h-full"):
        with ui.column().classes("w-full q-pa-sm gap-0"):

            with ui.row().classes("w-full items-center justify-between"):
                ui.label("📋 Activity").classes("text-h5")
                def _refresh_activity():
                    container.clear()
                    with container:
                        _build_activity_content(container)
                ui.button(icon="refresh", on_click=_refresh_activity).props(
                    "flat round size=sm"
                ).tooltip("Refresh")

            # Running Now
            ui.separator().classes("q-my-sm")
            ui.label("▶ Running Now").classes("text-subtitle1 font-bold")
            running = get_running_tasks()
            if running:
                for _tid, info in running.items():
                    with ui.card().classes("w-full q-my-xs").style("padding: 0.6rem 0.8rem;"):
                        with ui.row().classes("w-full items-center no-wrap gap-2"):
                            ui.spinner("dots", size="1.2em", color="amber")
                            ui.label(info.get("name", "Task")).classes("font-bold")
                            ui.space()
                            step = info.get("step", 0)
                            total = info.get("total", 0)
                            if total > 0:
                                ui.label(f"Step {step}/{total}").classes("text-xs text-grey-6")
                                ui.linear_progress(value=step / total, show_value=False).classes("w-24").props("color=amber")
                            def _stop_from_activity(tid=_tid):
                                stop_task(tid)
                                ui.notify("⏹️ Stop signal sent.", type="warning")
                                container.clear()
                                with container:
                                    _build_activity_content(container)
                            ui.button(icon="stop", on_click=_stop_from_activity).props(
                                "round color=red size=xs"
                            ).tooltip("Stop task")
            else:
                ui.label("No tasks currently running.").classes("text-grey-6 text-sm q-ml-sm")

            # Upcoming
            ui.separator().classes("q-my-sm")
            ui.label("📅 Upcoming").classes("text-subtitle1 font-bold")
            upcoming = get_next_fire_times(8)
            if upcoming:
                for item in upcoming:
                    with ui.row().classes("w-full items-center no-wrap gap-2 q-py-xs"):
                        ui.label(item["task_icon"]).classes("text-lg")
                        ui.label(item["task_name"]).classes("font-bold")
                        ui.space()
                        try:
                            dt = datetime.fromisoformat(item["next_run"])
                            ui.label(dt.strftime("%b %d, %I:%M %p")).classes("text-xs text-grey-6")
                        except (ValueError, TypeError):
                            ui.label(item["next_run"]).classes("text-xs text-grey-6")
            else:
                ui.label("No upcoming scheduled tasks.").classes("text-grey-6 text-sm q-ml-sm")

            # Recent Runs
            ui.separator().classes("q-my-sm")
            ui.label("🕐 Recent Runs").classes("text-subtitle1 font-bold")
            recent = get_recent_runs(10)
            if recent:
                for r in recent:
                    status = r.get("status", "unknown")
                    if status == "completed":
                        s_icon, s_color = "check_circle", "positive"
                    elif status == "completed_delivery_failed":
                        s_icon, s_color = "warning", "warning"
                    elif status == "failed":
                        s_icon, s_color = "error", "negative"
                    elif status == "stopped":
                        s_icon, s_color = "stop_circle", "orange"
                    else:
                        s_icon, s_color = "pending", "grey-6"
                    with ui.column().classes("w-full gap-0 q-py-xs"):
                        with ui.row().classes("w-full items-center no-wrap gap-2"):
                            ui.label(r.get("task_icon", "⚡")).classes("text-lg")
                            ui.label(r.get("task_name", "?")).classes("font-bold")
                            ui.icon(s_icon).classes(f"text-{s_color}").props("size=xs")
                            ui.space()
                            started = r.get("started_at", "")
                            if started:
                                try:
                                    dt = datetime.fromisoformat(started)
                                    ui.label(dt.strftime("%b %d, %I:%M %p")).classes("text-xs text-grey-6")
                                except (ValueError, TypeError):
                                    pass
                        status_msg = r.get("status_message", "")
                        if status_msg:
                            msg_color = "warning" if "failed" in status else "grey-6"
                            ui.label(status_msg).classes(f"text-xs text-{msg_color} q-ml-lg")
            else:
                ui.label("No task runs yet.").classes("text-grey-6 text-sm q-ml-sm")

            # Knowledge Extraction
            ui.separator().classes("q-my-sm")
            ui.label("🧠 Knowledge Extraction").classes("text-subtitle1 font-bold")
            mem_status = get_extraction_status()
            last_ext = mem_status.get("last_extraction")
            if last_ext:
                try:
                    dt = datetime.fromisoformat(last_ext)
                    interval_h = int(mem_status.get("interval_hours", 6))
                    ui.label(
                        f"Last run: {dt.strftime('%b %d, %I:%M %p')} · Runs every {interval_h}h"
                    ).classes("text-sm q-ml-sm")
                    threads_n = mem_status.get("threads_scanned", 0)
                    saved_n = mem_status.get("entities_saved", 0)
                    islands_n = mem_status.get("islands_repaired", 0)
                    parts = []
                    if threads_n:
                        parts.append(f"{threads_n} thread(s) scanned")
                    if saved_n:
                        parts.append(f"{saved_n} entities saved")
                    if islands_n:
                        parts.append(f"{islands_n} island(s) repaired")
                    if parts:
                        ui.label(" · ".join(parts)).classes("text-xs text-grey-6 q-ml-sm")
                except (ValueError, TypeError):
                    ui.label(f"Last run: {last_ext}").classes("text-sm q-ml-sm")
            else:
                ui.label("Not yet run — starts automatically.").classes("text-grey-6 text-sm q-ml-sm")

            # Dream Cycle
            ui.separator().classes("q-my-sm")
            ui.label("🌙 Dream Cycle").classes("text-subtitle1 font-bold")
            from dream_cycle import get_dream_status, get_journal
            dream_status = get_dream_status()
            if dream_status.get("enabled"):
                ui.label(
                    f"Window: {dream_status.get('window', '1:00 – 5:00')}"
                ).classes("text-sm q-ml-sm")
                if dream_status.get("last_run"):
                    try:
                        dt = datetime.fromisoformat(dream_status["last_run"])
                        ui.label(
                            f"Last run: {dt.strftime('%b %d, %I:%M %p')} — "
                            f"{dream_status.get('last_summary', '')}"
                        ).classes("text-sm q-ml-sm")
                    except (ValueError, TypeError):
                        ui.label(f"Last run: {dream_status['last_run']}").classes("text-sm q-ml-sm")
                else:
                    ui.label("No dream cycles yet — runs during idle hours.").classes("text-grey-6 text-sm q-ml-sm")

                # Show recent journal entries
                journal = get_journal(limit=3)
                if journal:
                    for entry in reversed(journal):
                        ts = entry.get("timestamp", "")
                        summary = entry.get("summary", "")
                        if ts and summary:
                            try:
                                jdt = datetime.fromisoformat(ts)
                                ui.label(
                                    f"  {jdt.strftime('%b %d')} — {summary}"
                                ).classes("text-xs text-grey-6 q-ml-lg")
                            except (ValueError, TypeError):
                                pass
            else:
                ui.label("Disabled — enable in Settings → Knowledge.").classes("text-grey-6 text-sm q-ml-sm")

            # Channels
            ui.separator().classes("q-my-sm")
            ui.label("📡 Channels").classes("text-subtitle1 font-bold")
            from channels.telegram import is_configured as tg_ok, is_running as tg_on
            _any_channel = False
            if tg_ok():
                _any_channel = True
                dot = "🟢" if tg_on() else "🔴"
                lbl = "Running" if tg_on() else "Stopped"
                ui.label(f"{dot} Telegram — {lbl}").classes("text-sm q-ml-sm")
            if not _any_channel:
                ui.label("No channels configured.").classes("text-grey-6 text-sm q-ml-sm")
