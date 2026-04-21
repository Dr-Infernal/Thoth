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
    from tasks import (
        list_tasks, update_task, run_task_background,
        get_running_tasks, get_running_task_thread, stop_task,
        _prepare_task_thread,
    )

    # ── Status bar (replaces old logo) ───────────────────────────────
    from ui.status_bar import build_status_bar
    _open = open_settings if open_settings else lambda tab: None
    build_status_bar(open_settings=_open)

    # ── Tab toggle ───────────────────────────────────────────────────
    with ui.tabs().classes("w-full shrink-0").props(
        "no-caps inline-label active-color=amber indicator-color=amber "
        "align=center"
    ).style("border-bottom: 1px solid rgba(255,255,255,0.08);") as home_tabs:
        tasks_tab = ui.tab("Workflows", icon="bolt")
        graph_tab = ui.tab("Knowledge", icon="psychology")
        activity_tab = ui.tab("Activity", icon="assessment")
        designer_tab = ui.tab("Designer", icon="design_services")

    # Choose initial tab (Designer after back / refresh, else Workflows)
    _tab_map = {"Workflows": tasks_tab, "Knowledge": graph_tab,
                "Activity": activity_tab, "Designer": designer_tab}
    _initial_tab = _tab_map.get(state.preferred_home_tab or "", tasks_tab)
    state.preferred_home_tab = None

    def _on_tab_change(e):
        if e.value == 'Knowledge':
            ui.run_javascript(
                'setTimeout(function() {'
                '  if (window.thothGraphRedraw) window.thothGraphRedraw();'
                '}, 50);'
            )

    with ui.tab_panels(home_tabs, value=_initial_tab, on_change=_on_tab_change).classes(
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
                    with ui.column().classes("gap-0"):
                        ui.label("⚡ Workflows").classes("text-h5")
                        ui.label("Background Agents").classes(
                            "text-xs text-grey-6"
                        ).style("margin-top: -2px; letter-spacing: 0.3px;")
                    ui.button("New Workflow", icon="add", on_click=lambda: show_task_dialog(
                        None, _refresh_home_tiles,
                    )).props("outline dense no-caps color=amber").style(
                        "font-weight: 600; font-size: 0.95rem;"
                    )

                if home_tasks:
                    with ui.element("div").classes("w-full").style(
                        "display: grid;"
                        "grid-template-columns: repeat(auto-fill, minmax(172px, 1fr));"
                        "gap: 0.75rem;"
                    ):
                        for tk in home_tasks:
                            _is_disabled = not tk.get("enabled", True)
                            card_style = "opacity: 0.45;" if _is_disabled else ""
                            with ui.card().classes("h-full").style(
                                f"padding: 0.75rem; {card_style}"
                            ):
                                # Icon in a subtle circular badge
                                with ui.element("div").classes("w-full flex justify-center q-mb-xs"):
                                    ui.element("div").style(
                                        "width: 40px; height: 40px; border-radius: 50%;"
                                        "background: rgba(255,255,255,0.06);"
                                        "display: flex; align-items: center; justify-content: center;"
                                        "font-size: 1.25rem;"
                                    ).props(f'innerHTML="{tk["icon"]}"')
                                ui.label(tk["name"]).classes("font-bold text-center w-full").style(
                                    "font-size: 0.85rem; line-height: 1.2;"
                                )
                                if tk.get("description"):
                                    ui.label(tk["description"]).classes(
                                        "text-xs text-grey-6 text-center w-full"
                                    ).style(
                                        "display: -webkit-box; -webkit-line-clamp: 2;"
                                        "-webkit-box-orient: vertical; overflow: hidden;"
                                    )
                                prompts = tk.get("prompts") or tk.get("steps") or []
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

                                with ui.row().classes("w-full items-center justify-between").style(
                                    "margin-top: 4px;"
                                ):
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

                                    def _delete_tk(t=tk):
                                        with ui.dialog() as dlg, ui.card().style(
                                            "min-width: 300px;"
                                        ):
                                            ui.label(
                                                f"Delete '{t['icon']} {t['name']}'?"
                                            ).classes("font-bold")
                                            ui.label(
                                                "This cannot be undone."
                                            ).classes("text-grey-6 text-xs")
                                            with ui.row().classes("w-full justify-end mt-2"):
                                                ui.button(
                                                    "Cancel", on_click=dlg.close,
                                                ).props("flat dense no-caps")
                                                def _confirm_delete(d=dlg, task=t):
                                                    from tasks import delete_task
                                                    delete_task(task["id"])
                                                    d.close()
                                                    ui.notify(
                                                        f"🗑️ '{task['name']}' deleted.",
                                                        type="negative",
                                                    )
                                                    _refresh_home_tiles()
                                                ui.button(
                                                    "Delete", on_click=_confirm_delete,
                                                ).props(
                                                    "flat dense no-caps color=red"
                                                )
                                        dlg.open()

                                    ui.button(icon="delete", on_click=_delete_tk).props(
                                        "flat dense round size=sm"
                                    ).tooltip("Delete").style("color: #888;")

                                    def _run_tk(t=tk):
                                        tid = _prepare_task_thread(t)
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
                    ui.label("No workflows yet — click + New Workflow to get started.").classes(
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

        # ── Designer panel ───────────────────────────────────────────
        with ui.tab_panel(designer_tab).classes("h-full").style("padding: 0;"):
            from designer.home_tab import build_designer_tab

            def _open_designer_project(project, initial_prompt: str | None = None):
                from threads import _save_thread_meta, _set_thread_project_id
                from designer.storage import save_project
                from memory_extraction import set_active_thread

                # Ensure project has its own thread
                if not project.thread_id:
                    import uuid as _uuid
                    tid = _uuid.uuid4().hex[:12]
                    _save_thread_meta(tid, f"🎨 {project.name}")
                    _set_thread_project_id(tid, project.id)
                    project.thread_id = tid
                    save_project(project)

                # Switch AppState to the project's thread
                prev = state.thread_id
                state.thread_id = project.thread_id
                state.thread_name = f"🎨 {project.name}"
                state.thread_model_override = ""
                # Load existing messages from LangGraph checkpoint
                from ui.helpers import load_thread_messages
                state.messages = load_thread_messages(project.thread_id)
                p.pending_files.clear()
                set_active_thread(project.thread_id, previous_id=prev)

                state.active_designer_project = project
                rebuild_main()
                rebuild_thread_list()

                if initial_prompt:
                    async def _start_initial_build() -> None:
                        await asyncio.sleep(0)
                        await send_message(initial_prompt)

                    asyncio.create_task(_start_initial_build())

            def _designer_refresh():
                state.preferred_home_tab = "Designer"
                rebuild_main()

            build_designer_tab(
                on_open_project=_open_designer_project,
                on_refresh=_designer_refresh,
            )


# ══════════════════════════════════════════════════════════════════════
# ACTIVITY CONTENT
# ══════════════════════════════════════════════════════════════════════

def _build_activity_content(container) -> None:
    """Render the Activity tab content inside *container*.

    Running tasks, approvals, upcoming schedule, and recent runs have
    moved to the Command Center (right drawer).  This tab now shows
    knowledge extraction and dream cycle status only.
    """
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
                    parts = []
                    if threads_n:
                        parts.append(f"{threads_n} thread(s) scanned")
                    if saved_n:
                        parts.append(f"{saved_n} entities saved")
                    if parts:
                        ui.label(" · ".join(parts)).classes("text-xs text-grey-6 q-ml-sm")
                except (ValueError, TypeError):
                    ui.label(f"Last run: {last_ext}").classes("text-sm q-ml-sm")
            else:
                ui.label("Not yet run — starts automatically.").classes("text-grey-6 text-sm q-ml-sm")

            # Extraction journal button
            from memory_extraction import get_extraction_journal as _get_ext_journal

            def _show_extraction_journal():
                _ext_entries = _get_ext_journal(limit=20)
                with ui.dialog() as dlg, ui.card().classes("w-full max-w-2xl").style("user-select: text;"):
                    ui.label("🧠 Extraction Journal").classes("text-h6")
                    ui.separator()
                    with ui.scroll_area().classes("w-full").style("max-height: 60vh"):
                        if not _ext_entries:
                            ui.label("No entries yet.").classes("text-grey-6")
                        for _ej in reversed(_ext_entries):
                            _ets = _ej.get("timestamp", "")
                            try:
                                _edt = datetime.fromisoformat(_ets)
                                _efmt = _edt.strftime("%b %d, %I:%M %p")
                            except (ValueError, TypeError):
                                _efmt = _ets
                            with ui.expansion(
                                f"{_efmt} — {_ej.get('summary', '')}",
                            ).classes("w-full"):
                                # Summary stats
                                _stats_parts = []
                                _cb = _ej.get("contradictions_blocked", 0)
                                if _cb:
                                    _stats_parts.append(f"{_cb} contradiction(s) blocked")
                                _lcs = _ej.get("low_confidence_skipped", 0)
                                if _lcs:
                                    _stats_parts.append(f"{_lcs} low-confidence skipped")
                                _ir = _ej.get("islands_repaired", 0)
                                if _ir:
                                    _stats_parts.append(f"{_ir} island(s) repaired")
                                if _stats_parts:
                                    ui.label(" · ".join(_stats_parts)).classes(
                                        "text-xs text-grey-5 q-mb-xs"
                                    )
                                _tdetails = _ej.get("thread_details", [])
                                if _tdetails:
                                    for _td in _tdetails:
                                        ui.label(
                                            f"  {_td.get('thread', '?')}: "
                                            f"extracted {_td.get('extracted', 0)}, "
                                            f"saved {_td.get('saved', 0)}"
                                        ).classes("text-xs q-ml-md")
                                _eerrs = _ej.get("errors", [])
                                if _eerrs:
                                    for _ee in _eerrs:
                                        ui.label(f"  Error: {_ee}").classes("text-xs text-negative q-ml-md")
                                if not _tdetails and not _eerrs:
                                    ui.label("No details available.").classes("text-xs text-grey-6")
                    with ui.row().classes("justify-end q-mt-sm"):
                        ui.button("Close", on_click=dlg.close).props("flat")
                dlg.open()

            ui.button("View Journal", on_click=_show_extraction_journal).props(
                "flat dense size=sm"
            ).classes("q-ml-sm text-xs")

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

                    def _show_dream_journal():
                        _entries = get_journal(limit=20)
                        with ui.dialog() as dlg, ui.card().classes("w-full max-w-2xl").style("user-select: text;"):
                            ui.label("🌙 Dream Cycle Journal").classes("text-h6")
                            ui.separator()
                            with ui.scroll_area().classes("w-full").style("max-height: 60vh"):
                                if not _entries:
                                    ui.label("No entries yet.").classes("text-grey-6")
                                for _je in reversed(_entries):
                                    _jts = _je.get("timestamp", "")
                                    try:
                                        _jdt = datetime.fromisoformat(_jts)
                                        _formatted_ts = _jdt.strftime("%b %d, %I:%M %p")
                                    except (ValueError, TypeError):
                                        _formatted_ts = _jts
                                    with ui.expansion(
                                        f"{_formatted_ts} — {_je.get('summary', '')}",
                                    ).classes("w-full"):
                                        # Merges
                                        _merges = _je.get("merges", [])
                                        if _merges:
                                            ui.label(f"Merges ({len(_merges)})").classes("text-bold text-sm")
                                            for _mg in _merges:
                                                ui.label(
                                                    f"  '{_mg.get('duplicate_subject', '?')}' → "
                                                    f"'{_mg.get('survivor_subject', '?')}' "
                                                    f"(score={_mg.get('score', '?')})"
                                                ).classes("text-xs q-ml-md")
                                        # Enrichments
                                        _enrichments = _je.get("enrichments", [])
                                        if _enrichments:
                                            ui.label(f"Enrichments ({len(_enrichments)})").classes("text-bold text-sm")
                                            for _en in _enrichments:
                                                ui.label(
                                                    f"  '{_en.get('subject', '?')}' "
                                                    f"({_en.get('old_length', '?')} → "
                                                    f"{_en.get('new_length', '?')} chars)"
                                                ).classes("text-xs q-ml-md")
                                                if _en.get("new_description"):
                                                    ui.label(
                                                        f"    → {_en['new_description'][:150]}…"
                                                    ).classes("text-xs text-grey-7 q-ml-lg")
                                        # Inferred Relations
                                        _inferred = _je.get("inferred_relations", [])
                                        if _inferred:
                                            ui.label(f"Inferred Relations ({len(_inferred)})").classes("text-bold text-sm")
                                            for _ir in _inferred:
                                                _conf = _ir.get("confidence", "?")
                                                _conf_str = f"{_conf:.2f}" if isinstance(_conf, (int, float)) else str(_conf)
                                                ui.label(
                                                    f"  {_ir.get('source_subject', '?')} "
                                                    f"--[{_ir.get('relation_type', '?')}]--> "
                                                    f"{_ir.get('target_subject', '?')} "
                                                    f"(conf={_conf_str})"
                                                ).classes("text-xs q-ml-md")
                                                if _ir.get("evidence"):
                                                    ui.label(
                                                        f'    Evidence: "{_ir["evidence"][:120]}…"'
                                                    ).classes("text-xs text-grey-7 q-ml-lg italic")
                                        # Errors
                                        _errs = _je.get("errors", [])
                                        if _errs:
                                            ui.label(f"Errors ({len(_errs)})").classes("text-bold text-sm text-negative")
                                            for _er in _errs:
                                                ui.label(f"  {_er}").classes("text-xs text-negative q-ml-md")
                                        if not _merges and not _enrichments and not _inferred:
                                            ui.label("No changes this cycle.").classes("text-xs text-grey-6")
                            with ui.row().classes("justify-end q-mt-sm"):
                                ui.button("Close", on_click=dlg.close).props("flat")
                        dlg.open()

                    ui.button("View Journal", on_click=_show_dream_journal).props(
                        "flat dense size=sm"
                    ).classes("q-ml-sm text-xs")
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

            # Recent Logs
            ui.separator().classes("q-my-sm")
            ui.label("📝 Recent Logs").classes("text-subtitle1 font-bold")

            from logging_config import read_recent_logs, get_current_log_path

            _log_container = ui.column().classes("w-full")

            def _render_logs():
                _log_container.clear()
                entries = read_recent_logs(15)
                with _log_container:
                    if not entries:
                        ui.label("No log entries yet.").classes("text-grey-6 text-sm q-ml-sm")
                        return
                    for entry in entries:
                        lvl = entry.get("level", "?")
                        ts = entry.get("ts", "")
                        msg = entry.get("msg", "")
                        # Colour by level
                        if lvl == "ERROR":
                            color = "text-negative"
                        elif lvl == "WARNING":
                            color = "text-warning"
                        elif lvl == "DEBUG":
                            color = "text-grey-7"
                        else:
                            color = "text-grey-5"
                        # Truncate long messages
                        display_msg = (msg[:120] + "…") if len(msg) > 120 else msg
                        ts_short = ts[11:19] if len(ts) >= 19 else ts
                        ui.label(
                            f"{ts_short} [{lvl}] {display_msg}"
                        ).classes(f"text-xs {color}").style(
                            "font-family: monospace; line-height: 1.4;"
                            " user-select: text; cursor: text;"
                        )

            _render_logs()

            with ui.row().classes("gap-2 q-ml-sm"):
                ui.button(icon="refresh", on_click=_render_logs).props(
                    "flat round size=xs"
                ).tooltip("Refresh logs")

                def _view_full_log():
                    full = read_recent_logs(200)
                    with ui.dialog() as dlg, ui.card().classes("w-full max-w-3xl").style(
                        "user-select: text; min-height: 80vh;"
                    ):
                        ui.label("📝 Log Viewer").classes("text-h6")
                        ui.separator()
                        log_path = get_current_log_path()
                        if log_path:
                            ui.label(str(log_path)).classes("text-xs text-grey-6")
                        with ui.scroll_area().classes("w-full flex-grow").style("min-height: 60vh;"):
                            for entry in full:
                                lvl = entry.get("level", "?")
                                ts = entry.get("ts", "")
                                msg = entry.get("msg", "")
                                logger_name = entry.get("logger", "")
                                if lvl == "ERROR":
                                    color = "text-negative"
                                elif lvl == "WARNING":
                                    color = "text-warning"
                                elif lvl == "DEBUG":
                                    color = "text-grey-7"
                                else:
                                    color = "text-grey-5"
                                line = f"{ts} [{lvl}] [{logger_name}] {msg}"
                                exc = entry.get("exc", "")
                                if exc:
                                    line += f"\n  {exc}"
                                ui.label(line).classes(
                                    f"text-xs {color}"
                                ).style("font-family: monospace; white-space: pre-wrap; line-height: 1.4;")
                        with ui.row().classes("justify-end q-mt-sm"):
                            ui.button("Close", on_click=dlg.close).props("flat")
                    dlg.open()

                ui.button("View Full Log", on_click=_view_full_log).props(
                    "flat dense size=sm no-caps"
                ).classes("text-xs")
