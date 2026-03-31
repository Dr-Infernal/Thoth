"""Thoth UI — sidebar (left drawer) with thread list.

Builds the sidebar drawer, home/new buttons, thread listing, and
settings/help buttons.  All navigation is handled via callbacks so
the module stays decoupled from the main page layout.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime
from typing import Callable

from nicegui import ui

from ui.state import AppState, P, _active_generations
from ui.constants import SIDEBAR_MAX_THREADS

logger = logging.getLogger(__name__)


def build_sidebar(
    state: AppState,
    p: P,
    *,
    rebuild_main: Callable[[], None],
    open_settings: Callable[[], None],
    load_thread_messages: Callable[[str], list[dict]],
) -> Callable[[], None]:
    """Build the left drawer and return ``rebuild_thread_list`` so the
    caller can invoke it when needed.

    Parameters
    ----------
    rebuild_main:
        Called to refresh the main content area after a navigation event.
    open_settings:
        Called when the user clicks the Settings button.
    load_thread_messages:
        ``load_thread_messages(thread_id) -> list[dict]`` used to hydrate
        a thread when the user clicks it.
    """
    from threads import _list_threads, _save_thread_meta, _delete_thread
    from tasks import get_running_tasks, stop_task
    from models import is_cloud_model, get_current_model
    from memory_extraction import set_active_thread
    from agent import clear_summary_cache

    # Keep a reference the caller can use
    _rebuild_thread_list_ref: list[Callable[[], None]] = [lambda: None]

    with ui.left_drawer(value=True, fixed=True).style("width: 280px"):
        # Logo
        ui.html('<h2 style="margin: 0; color: gold;">𓁟 Thoth</h2>', sanitize=False)
        ui.label("Personal AI Sovereignty").classes("text-xs text-grey-6")
        ui.separator()

        # Home + New buttons
        with ui.row().classes("w-full gap-2"):
            def _go_home():
                prev = state.thread_id
                prev_gen = _active_generations.get(prev) if prev else None
                if prev_gen and prev_gen.status == "streaming":
                    prev_gen.detached = True
                    if prev_gen.tts_active:
                        state.tts_service.stop()
                        prev_gen.tts_active = False
                state.thread_id = None
                state.thread_name = None
                state.messages = []
                set_active_thread(None, previous_id=prev)
                rebuild_main()
                _rebuild_thread_list_ref[0]()

            ui.button("🏠 Home", on_click=_go_home).classes("flex-grow").props("flat")

            def _new_thread():
                tid = uuid.uuid4().hex[:12]
                name = f"💻 Thread {datetime.now().strftime('%b %d, %H:%M')}"
                _save_thread_meta(tid, name)
                prev = state.thread_id
                prev_gen = _active_generations.get(prev) if prev else None
                if prev_gen and prev_gen.status == "streaming":
                    prev_gen.detached = True
                    if prev_gen.tts_active:
                        state.tts_service.stop()
                        prev_gen.tts_active = False
                state.thread_id = tid
                state.thread_name = name
                state.messages = []
                state.thread_model_override = ""
                set_active_thread(tid, previous_id=prev)
                rebuild_main()
                _rebuild_thread_list_ref[0]()

            ui.button("＋ New", on_click=_new_thread).classes("flex-grow").props("color=primary")

        ui.label("Conversations").classes("text-subtitle2 mt-2")
        p.thread_container = ui.column().classes("w-full gap-0")

        # Spacer pushes bottom section down
        ui.space()

        # Token counter
        p.token_label = ui.label("Context: 0K / 32K (0%)").classes("text-xs text-grey-6")
        p.token_bar = ui.linear_progress(value=0, show_value=False).style("height: 6px;")

        # Settings + Help
        with ui.row().classes("w-full gap-2"):
            ui.button("⚙️ Settings", on_click=open_settings).classes("flex-grow")

            def _show_help():
                state.show_onboarding = True
                rebuild_main()

            ui.button("👋", on_click=_show_help).props("flat dense")

    # ── Thread list builder ──────────────────────────────────────────

    def _rebuild_thread_list() -> None:
        if p.thread_container is None:
            return
        p.thread_container.clear()
        threads = _list_threads()
        running_tids = get_running_tasks()

        def _fmt_ts(iso_str: str) -> str:
            try:
                dt = datetime.fromisoformat(iso_str)
                try:
                    return dt.strftime("%b %d, %#I:%M %p")
                except ValueError:
                    return dt.strftime("%b %d, %-I:%M %p")
            except Exception:
                return iso_str[:16] if iso_str else ""

        with p.thread_container:
            if not threads:
                ui.label("No conversations yet.").classes("text-grey-6 text-sm q-px-sm")
                return

            visible = threads[:SIDEBAR_MAX_THREADS]
            for tid, name, created, updated, *_rest in visible:
                _thread_model_ov = _rest[0] if _rest else ""
                name = name or ""
                is_active = tid == state.thread_id
                is_running = tid in running_tids
                is_generating_tid = tid in _active_generations
                is_cloud_thread = is_cloud_model(_thread_model_ov or get_current_model())

                def _select(t=tid, n=name, mo=_thread_model_ov):
                    prev = state.thread_id
                    prev_gen = _active_generations.get(prev) if prev else None
                    if prev_gen and prev_gen.status == "streaming":
                        prev_gen.detached = True
                        if prev_gen.tts_active:
                            state.tts_service.stop()
                            prev_gen.tts_active = False
                    state.thread_id = t
                    state.thread_name = n
                    state.thread_model_override = mo or ""
                    state.messages = load_thread_messages(t)
                    set_active_thread(t, previous_id=prev)
                    rebuild_main()
                    _rebuild_thread_list_ref[0]()

                def _delete(t=tid):
                    _del_gen = _active_generations.get(t)
                    if _del_gen:
                        _del_gen.stop_event.set()
                    stop_task(t)
                    _delete_thread(t)
                    clear_summary_cache(t)
                    from tools.shell_tool import get_session_manager, clear_shell_history
                    get_session_manager().kill_session(t)
                    clear_shell_history(t)
                    from tools.browser_tool import (
                        get_session_manager as get_browser_session_manager,
                        clear_browser_history,
                    )
                    get_browser_session_manager().kill_session(t)
                    clear_browser_history(t)
                    set_active_thread(None, previous_id=t)
                    if state.thread_id == t:
                        state.thread_id = None
                        state.thread_name = None
                        state.messages = []
                        rebuild_main()
                    _rebuild_thread_list_ref[0]()

                with ui.item(on_click=_select).classes("w-full rounded").props(
                    "clickable" + (" active" if is_active else "")
                ).style("min-height: 40px; padding: 4px 8px;"):
                    with ui.item_section().props("avatar").style("min-width: 28px;"):
                        if is_generating_tid:
                            _thr_icon = "autorenew"
                        elif is_running:
                            _thr_icon = "hourglass_top"
                        elif is_cloud_thread:
                            _thr_icon = "cloud"
                        elif name.startswith("✈️"):
                            _thr_icon = "send"
                        elif name.startswith("📧"):
                            _thr_icon = "email"
                        elif name.startswith("⚡"):
                            _thr_icon = "electric_bolt"
                        else:
                            _thr_icon = "computer"
                        _icon_el = ui.icon(_thr_icon, size="xs").classes(
                            "text-primary" if is_active else "text-grey-6"
                        )
                        if is_generating_tid:
                            _icon_el.classes(add="thoth-spin")
                    with ui.item_section():
                        ui.item_label(name).classes("ellipsis").style(
                            "font-size: 0.85rem;" + ("font-weight: 600;" if is_active else "")
                        )
                        if updated:
                            ui.item_label(_fmt_ts(updated)).props("caption").classes("text-grey-7").style(
                                "font-size: 0.7rem;"
                            )
                    with ui.item_section().props("side"):
                        ui.button(
                            icon="delete_outline", on_click=lambda e, t=tid: _delete(t)
                        ).props("flat dense round size=xs color=grey-6").on(
                            "click", js_handler="(e) => e.stopPropagation()"
                        )

            if len(threads) > SIDEBAR_MAX_THREADS:
                def _show_all():
                    with ui.dialog() as dlg, ui.card().classes("w-96"):
                        ui.label("All Conversations").classes("text-h6")
                        with ui.list().props("bordered separator").classes("w-full"):
                            for tid, name, created, updated, *_rest2 in threads:
                                _mo2 = _rest2[0] if _rest2 else ""
                                def _sel(t=tid, n=name, mo=_mo2):
                                    prev = state.thread_id
                                    prev_gen = _active_generations.get(prev) if prev else None
                                    if prev_gen and prev_gen.status == "streaming":
                                        prev_gen.detached = True
                                        if prev_gen.tts_active:
                                            state.tts_service.stop()
                                            prev_gen.tts_active = False
                                    state.thread_id = t
                                    state.thread_name = n
                                    state.thread_model_override = mo or ""
                                    state.messages = load_thread_messages(t)
                                    dlg.close()
                                    rebuild_main()
                                    _rebuild_thread_list_ref[0]()

                                def _del(t=tid):
                                    _del_gen = _active_generations.get(t)
                                    if _del_gen:
                                        _del_gen.stop_event.set()
                                    stop_task(t)
                                    _delete_thread(t)
                                    clear_summary_cache(t)
                                    from tools.shell_tool import get_session_manager, clear_shell_history
                                    get_session_manager().kill_session(t)
                                    clear_shell_history(t)
                                    from tools.browser_tool import (
                                        get_session_manager as get_browser_session_manager,
                                        clear_browser_history,
                                    )
                                    get_browser_session_manager().kill_session(t)
                                    clear_browser_history(t)
                                    if state.thread_id == t:
                                        state.thread_id = None
                                        state.messages = []
                                    dlg.close()
                                    rebuild_main()
                                    _rebuild_thread_list_ref[0]()

                                with ui.item(on_click=_sel).props("clickable"):
                                    with ui.item_section().props("avatar").style("min-width: 28px;"):
                                        ui.icon("chat_bubble_outline", size="xs")
                                    with ui.item_section():
                                        ui.item_label(name)
                                        if updated:
                                            ui.item_label(_fmt_ts(updated)).props("caption")
                                    with ui.item_section().props("side"):
                                        ui.button(
                                            icon="delete_outline", on_click=lambda e, t=tid: _del(t),
                                        ).props("flat dense round size=xs color=grey-6").on(
                                            "click", js_handler="(e) => e.stopPropagation()"
                                        )
                        ui.separator()
                        with ui.row().classes("w-full gap-2"):
                            def _delete_all():
                                for t, *_ in threads:
                                    stop_task(t)
                                    _delete_thread(t)
                                clear_summary_cache()
                                from tools.shell_tool import get_session_manager, clear_shell_history
                                for t, *_ in threads:
                                    get_session_manager().kill_session(t)
                                    clear_shell_history(t)
                                state.thread_id = None
                                state.thread_name = None
                                state.messages = []
                                dlg.close()
                                rebuild_main()
                                _rebuild_thread_list_ref[0]()

                            ui.button("Delete all", icon="delete_sweep", on_click=_delete_all).props(
                                "flat color=negative"
                            ).classes("flex-grow")
                            ui.button("Close", on_click=dlg.close).props("flat").classes("flex-grow")
                    dlg.open()

                ui.button(
                    f"Show all ({len(threads)})", on_click=_show_all
                ).classes("w-full q-mt-xs").props("flat dense size=sm")

    _rebuild_thread_list_ref[0] = _rebuild_thread_list
    _rebuild_thread_list()

    return _rebuild_thread_list
