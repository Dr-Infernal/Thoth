"""Thoth UI — Chat screen (thread conversation view).

Extracted from the monolith's ``_build_chat`` inner function.
"""

from __future__ import annotations

import asyncio
import logging
import os
import pathlib
import sys
from datetime import datetime
from typing import Callable

from nicegui import events, run, ui

from ui.state import AppState, P, _active_generations
from ui.constants import ALLOWED_UPLOAD_SUFFIXES, welcome_message, EXAMPLE_PROMPTS
from ui.render import render_image_with_save

logger = logging.getLogger(__name__)


def build_chat(
    state: AppState,
    p: P,
    *,
    rebuild_main: Callable,
    rebuild_thread_list: Callable,
    send_message: Callable,
    open_settings: Callable,
    open_export: Callable,
    show_interrupt: Callable,
    add_chat_message: Callable,
    add_terminal_entry: Callable,
    browse_file: Callable,
) -> None:
    """Render the full chat view for the current thread."""
    from agent import clear_agent_cache, get_token_usage
    from models import (
        get_current_model, is_cloud_model, get_provider_emoji,
        list_local_models, list_starred_cloud_models, get_cloud_provider,
        get_model_max_context, get_user_context_size, CONTEXT_SIZE_LABELS,
    )
    from threads import (
        _save_thread_meta, _set_thread_model_override,
        get_thread_skills_override, set_thread_skills_override,
    )
    from tasks import get_running_tasks, stop_task
    from tools import registry as tool_registry
    from ui.helpers import persist_thread_image_state

    # ── Header ───────────────────────────────────────────────────────
    running_wfs = get_running_tasks()
    bg = running_wfs.get(state.thread_id)

    with ui.row().classes("w-full items-center shrink-0"):
        if bg:
            ui.html(
                f"<h3>⚡ {bg['name']} "
                f"<span style='font-size:0.8rem; opacity:0.7;'>"
                f"Running — Step {bg['step']+1}/{bg['total']}</span></h3>",
                sanitize=False,
            )
            def _stop_task_from_header(tid=state.thread_id):
                stop_task(tid)
                ui.notify("⏹️ Stop signal sent — task will stop after current step.", type="warning")
                rebuild_main()
            ui.button(icon="stop", on_click=_stop_task_from_header).props(
                "round color=red size=sm"
            ).tooltip("Stop task")
        else:
            p.chat_header_label = ui.label(f"💬 {state.thread_name}").classes("text-h5 flex-grow")

            # ── Model picker ─────────────────────────────────────────
            _cur_mo = state.thread_model_override or ""
            _model_display = _cur_mo if _cur_mo else get_current_model()

            _cur_default = get_current_model()
            _prefix = get_provider_emoji(_cur_default)
            _default_opt = f"{_prefix} {_cur_default} (default)"
            _picker_opts = [_default_opt]
            for cid in list_starred_cloud_models():
                if cid != _cur_default:
                    _picker_opts.append(f"{get_provider_emoji(cid)} {cid}")
            for lid in list_local_models():
                if lid != _cur_default:
                    _picker_opts.append(f"🖥️ {lid}")

            _MORE_MODELS_SENTINEL = "⚙️ More models…"
            _picker_opts.append(_MORE_MODELS_SENTINEL)

            if _cur_mo and is_cloud_model(_cur_mo):
                _picker_val = f"{get_provider_emoji(_cur_mo)} {_cur_mo}"
            elif _cur_mo and not is_cloud_model(_cur_mo) and _cur_mo != _cur_default:
                _picker_val = f"🖥️ {_cur_mo}"
            else:
                _picker_val = _default_opt

            async def _on_model_pick(e):
                val = e.value
                if val == _MORE_MODELS_SENTINEL:
                    e.sender.set_value(_picker_val)
                    open_settings("Cloud")
                    return
                if val.endswith(" (default)"):
                    state.thread_model_override = ""
                    _set_thread_model_override(state.thread_id, "")
                    _switched_label = "default"
                elif " " in val:
                    model_id = val.split(" ", 1)[1]
                    state.thread_model_override = model_id
                    _set_thread_model_override(state.thread_id, model_id)
                    _switched_label = model_id
                else:
                    state.thread_model_override = ""
                    _set_thread_model_override(state.thread_id, "")
                    _switched_label = "default"
                clear_agent_cache()
                _eff = state.thread_model_override or get_current_model()
                if _switched_label == "default":
                    ui.notify(f"Switched to default model ({_eff})", type="info")
                else:
                    ui.notify(f"Switched to {_switched_label}", type="info")
                _mmax = await run.io_bound(lambda: get_model_max_context(_eff))
                _uval = get_user_context_size()
                if _mmax is not None and _uval > _mmax:
                    _ml = CONTEXT_SIZE_LABELS.get(_mmax, f"{_mmax:,}")
                    _ul = CONTEXT_SIZE_LABELS.get(_uval, f"{_uval:,}")
                    ui.notify(
                        f"Context capped: {_eff} max is {_ml} (you selected {_ul}). "
                        f"Trimming will use {_ml}.",
                        type="warning", close_button=True, timeout=8000,
                    )
                rebuild_main()

            ui.select(
                options=_picker_opts, value=_picker_val,
                on_change=_on_model_pick,
            ).props('dense borderless use-input input-debounce=300').classes("text-sm").style(
                "min-width: 200px; max-width: 320px;"
            ).tooltip("Select model for this thread")

            # ── Per-thread skills override ───────────────────────────
            import skills as _skills_mod
            _skills_mod.load_skills()
            _enabled_sk = _skills_mod.get_enabled_skills()
            if _enabled_sk:
                _thread_sk_override = get_thread_skills_override(state.thread_id)
                _enabled_names = set(sk.name for sk in _enabled_sk)
                _active_sk_names = (
                    set(_thread_sk_override) & _enabled_names
                    if _thread_sk_override is not None
                    else set(_enabled_names)
                )
                _sk_count = len(_active_sk_names)
                _sk_label = (
                    f"✨ {_sk_count} skill{'s' if _sk_count != 1 else ''}"
                    if _sk_count > 0
                    else "✨ No skills"
                )
                _sk_btn = ui.button(_sk_label).props("flat dense no-caps size=sm").classes("text-sm").style("min-width: 100px;")
                with _sk_btn:
                    with ui.menu().classes("q-pa-sm"):
                        ui.label("Skills for this thread").classes("text-xs text-grey-5 q-mb-xs")

                        def _update_sk_label():
                            _cur = get_thread_skills_override(state.thread_id)
                            _en = set(sk.name for sk in _skills_mod.get_enabled_skills())
                            _act = set(_cur) & _en if _cur is not None else _en
                            n = len(_act)
                            _sk_btn.text = f"✨ {n} skill{'s' if n != 1 else ''}" if n > 0 else "✨ No skills"

                        def _on_sk_toggle(name, val):
                            _cur = get_thread_skills_override(state.thread_id)
                            if _cur is None:
                                _cur = list(_enabled_names)
                            names_set = set(_cur)
                            if val:
                                names_set.add(name)
                            else:
                                names_set.discard(name)
                            set_thread_skills_override(state.thread_id, list(names_set))
                            clear_agent_cache()
                            _update_sk_label()

                        async def _reset_skills():
                            set_thread_skills_override(state.thread_id, None)
                            clear_agent_cache()
                            _update_sk_label()
                            for _cbn, _cbw in _sk_cbs.items():
                                _cbw.value = True

                        _sk_cbs = {}
                        with ui.column().classes("gap-0"):
                            for _sk in _enabled_sk:
                                _cb = ui.checkbox(
                                    f"{_sk.icon} {_sk.display_name}",
                                    value=_sk.name in _active_sk_names,
                                    on_change=lambda e, n=_sk.name: _on_sk_toggle(n, e.value),
                                ).classes("text-sm")
                                _sk_cbs[_sk.name] = _cb
                        ui.separator()
                        ui.button("Reset to global", icon="restart_alt",
                                  on_click=lambda: asyncio.create_task(_reset_skills())).props("flat dense size=sm")

        if state.messages:
            ui.button(icon="download", on_click=open_export).props("flat round").tooltip("Export")

    # ── Cloud/local model banner ─────────────────────────────────────
    _active_model = state.thread_model_override or get_current_model()
    _is_active_cloud = is_cloud_model(_active_model)
    if _is_active_cloud:
        _prov = get_cloud_provider(_active_model) or "cloud"
        _prov_label = "OpenAI" if _prov == "openai" else "OpenRouter" if _prov == "openrouter" else "cloud"
        with ui.row().classes("w-full items-center gap-2 q-px-sm q-py-xs").style(
            "background: rgba(255, 152, 0, 0.08); border-radius: 8px; border: 1px solid rgba(255, 152, 0, 0.25);"
        ):
            ui.icon("cloud", color="orange").style("font-size: 1.1rem;")
            ui.label(f"Using {_active_model} via {_prov_label} — data is sent to the cloud").classes("text-orange text-sm")
    else:
        with ui.row().classes("w-full items-center gap-2 q-px-sm q-py-xs").style(
            "background: rgba(76, 175, 80, 0.08); border-radius: 8px; border: 1px solid rgba(76, 175, 80, 0.25);"
        ):
            ui.icon("lock", color="green").style("font-size: 1.1rem;")
            ui.label(f"Using {_active_model} via Ollama — complete privacy").classes("text-green text-sm")

    # ── Scrollable message area ──────────────────────────────────────
    _scroll_bg = (
        "background: rgba(255, 152, 0, 0.03);"
        if _is_active_cloud
        else "background: rgba(76, 175, 80, 0.03);"
    )
    p.chat_scroll = ui.scroll_area().classes("w-full flex-grow").style(_scroll_bg)
    with p.chat_scroll:
        p.chat_container = ui.column().classes("w-full gap-2")

    # Render existing messages
    _reattach_gen = _active_generations.get(state.thread_id)
    _has_active_gen = (_reattach_gen and _reattach_gen.detached and _reattach_gen.status == "streaming")
    _has_running_task = state.thread_id in get_running_tasks()
    _msgs_to_render = state.messages
    if ((_has_active_gen or _has_running_task)
            and _msgs_to_render
            and _msgs_to_render[-1].get("content", "").startswith(
                "\u26a0\ufe0f The assistant was interrupted")):
        _msgs_to_render = _msgs_to_render[:-1]
    for msg in _msgs_to_render:
        add_chat_message(msg)

    # ── Reattach to running generation ───────────────────────────────
    if _reattach_gen and _reattach_gen.detached and _reattach_gen.status == "streaming":
        with p.chat_container:
            with ui.element("div").classes("thoth-msg-row"):
                ui.html('<div class="thoth-avatar thoth-avatar-bot">\U00013041</div>', sanitize=False)
                with ui.column().classes("thoth-msg-body gap-1") as _ra_wrapper:
                    ui.html(
                        '<div class="thoth-msg-header">'
                        '<span class="thoth-msg-name">Thoth</span>'
                        f'<span class="thoth-msg-stamp">{datetime.now().strftime("%H:%M")}</span>'
                        '</div>',
                        sanitize=False,
                    )
                    _reattach_gen.tool_col = ui.column().classes("w-full gap-1")
                    for _tr in _reattach_gen.tool_results:
                        with _reattach_gen.tool_col:
                            with ui.expansion(f"\u2705 {_tr['name']}", icon="check_circle").classes("w-full"):
                                if _tr.get('content'):
                                    _disp = _tr['content'][:5_000]
                                    if len(_tr['content']) > 5_000:
                                        _disp += "\n\n\u2026 (truncated)"
                                    ui.code(_disp).classes("w-full text-xs")
                    for _cj in _reattach_gen.chart_data:
                        try:
                            import plotly.io as _pio
                            _fig = _pio.from_json(_cj)
                            with _reattach_gen.tool_col:
                                ui.plotly(_fig).classes("w-full")
                        except Exception:
                            logger.debug("Chart rendering failed during reattach", exc_info=True)
                    for _img in _reattach_gen.captured_images:
                        try:
                            with _reattach_gen.tool_col:
                                render_image_with_save(_img)
                        except Exception:
                            logger.debug("Image rendering failed during reattach", exc_info=True)
                    _reattach_gen.assistant_md = ui.markdown(
                        _reattach_gen.accumulated,
                        extras=['code-friendly', 'fenced-code-blocks', 'tables'],
                    ).classes("thoth-msg w-full")
                    _reattach_gen.wrapper = _ra_wrapper
                    _reattach_gen.thinking_label = None
                    _reattach_gen.thinking_md = None
        _reattach_gen.detached = False
        if p.stop_btn:
            p.stop_btn.enable()
    elif _reattach_gen and _reattach_gen.status in ("done", "error", "stopped", "interrupted"):
        if _reattach_gen.accumulated:
            a_msg: dict = {"role": "assistant", "content": _reattach_gen.accumulated}
            if _reattach_gen.tool_results:
                a_msg["tool_results"] = _reattach_gen.tool_results
            if _reattach_gen.chart_data:
                a_msg["charts"] = _reattach_gen.chart_data
            if _reattach_gen.captured_images:
                a_msg["images"] = _reattach_gen.captured_images
            state.messages.append(a_msg)
            persist_thread_image_state(state.thread_id, state.messages)
            add_chat_message(a_msg)
        _active_generations.pop(state.thread_id, None)

    # Onboarding
    if state.show_onboarding:
        with p.chat_container:
            with ui.element("div").classes("thoth-msg-row"):
                ui.html('<div class="thoth-avatar thoth-avatar-bot">𓁟</div>', sanitize=False)
                with ui.column().classes("thoth-msg-body gap-1"):
                    ui.html(
                        '<div class="thoth-msg-header">'
                        '<span class="thoth-msg-name">Thoth</span>'
                        '</div>',
                        sanitize=False,
                    )
                    _cloud_ob2 = is_cloud_model(_active_model)
                    ui.markdown(welcome_message(cloud=_cloud_ob2), extras=['code-friendly', 'fenced-code-blocks', 'tables'])
                    with ui.row().classes("flex-wrap gap-2"):
                        for prompt in EXAMPLE_PROMPTS:
                            def _try_inline(pr=prompt):
                                state.show_onboarding = False
                                asyncio.create_task(send_message(pr))
                            ui.button(prompt, on_click=_try_inline).props("flat dense outline").style("text-transform:none;")

                    def _dismiss():
                        state.show_onboarding = False
                        rebuild_main()
                    ui.button("✕ Dismiss", on_click=_dismiss).props("flat dense")

    # Interrupt UI
    if state.pending_interrupt:
        show_interrupt(state.pending_interrupt)

    if p.chat_scroll:
        p.chat_scroll.scroll_to(percent=1.0)

    # ── Terminal toggle bar + panel ──────────────────────────────────
    p.terminal_visible = False
    p.terminal_toggle_bar = None

    if tool_registry.is_enabled("shell"):
        def _toggle_terminal():
            p.terminal_visible = not getattr(p, "terminal_visible", False)
            if p.terminal_panel is not None:
                p.terminal_panel.set_visibility(p.terminal_visible)
                if p.terminal_visible and p.terminal_scroll:
                    p.terminal_scroll.scroll_to(percent=1.0)
            if p.terminal_toggle_bar is not None:
                _chevron = "expand_more" if p.terminal_visible else "expand_less"
                p.terminal_chevron.props(f"icon={_chevron}")

        p.terminal_toggle_bar = ui.row().classes(
            "w-full items-center px-3 cursor-pointer"
        ).style(
            "height: 28px; background: #1a1a2e; border-top: 1px solid #333; gap: 6px;"
        )
        p.terminal_toggle_bar.on("click", lambda: _toggle_terminal())

        def _clear_terminal():
            from tools.shell_tool import clear_shell_history
            if state.thread_id:
                clear_shell_history(state.thread_id)
            if p.terminal_container:
                p.terminal_container.clear()

        with p.terminal_toggle_bar:
            ui.icon("terminal").classes("text-grey-5").style("font-size: 14px;")
            ui.label("Terminal").classes("text-xs font-bold text-grey-5 flex-grow")
            ui.button(icon="delete_sweep", on_click=_clear_terminal).props(
                "flat round dense size=xs"
            ).classes("text-grey-5").tooltip("Clear terminal history")
            p.terminal_chevron = ui.button(icon="expand_less").props(
                "flat round dense size=xs"
            ).classes("text-grey-5")
            p.terminal_chevron.on("click.stop", lambda: _toggle_terminal())

    p.terminal_panel = ui.column().classes("w-full shrink-0").style("max-height: 250px;")
    p.terminal_panel.set_visibility(False)
    p.terminal_scroll = None
    p.terminal_container = None

    with p.terminal_panel:
        p.terminal_scroll = ui.scroll_area().classes("w-full flex-grow").style(
            "max-height: 230px; background: #0d1117;"
        )
        with p.terminal_scroll:
            p.terminal_container = ui.column().classes("w-full gap-0 px-2 py-1")

    # Render shell history
    if state.thread_id:
        from tools.shell_tool import get_shell_history
        _history = get_shell_history(state.thread_id)
        for entry in _history:
            add_terminal_entry(entry)
        if _history and p.terminal_panel is not None:
            p.terminal_visible = True
            p.terminal_panel.set_visibility(True)
            if hasattr(p, "terminal_chevron") and p.terminal_chevron:
                p.terminal_chevron.props("icon=expand_less")
        if p.terminal_scroll:
            p.terminal_scroll.scroll_to(percent=1.0)

    # ── File chips ───────────────────────────────────────────────────
    p.file_chips_row = ui.row().classes("w-full flex-wrap gap-1")

    async def _on_upload(e: events.UploadEventArguments):
        data = await e.file.read()
        name = e.file.name
        p.pending_files.append({"name": name, "data": data})
        if hasattr(e, 'sender') and hasattr(e.sender, 'reset'):
            e.sender.reset()
        with p.file_chips_row:
            idx = len(p.pending_files) - 1
            def _remove(i=idx, badge=None):
                if i < len(p.pending_files):
                    p.pending_files.pop(i)
                if badge:
                    badge.delete()
            b = ui.badge(f"📎 {name} ✕", color="grey-8").props("outline")
            b.on("click", lambda b=b, i=idx: _remove(i, b))
            b.style("cursor: pointer;")

    _hidden_upload = ui.upload(on_upload=_on_upload, auto_upload=True, multiple=True).classes("hidden")

    # Drag-and-drop (singleton listener — reads dynamic upload ID)
    ui.run_javascript(f'''
        (() => {{
            window._thothUploadId = {_hidden_upload.id};
            if (window._thothDragInstalled) return;
            window._thothDragInstalled = true;
            const body = document.body;
            let overlay = null;
            let dragTimer = null;
            function showOverlay() {{
                if (overlay) return;
                overlay = document.createElement("div");
                overlay.style.cssText = "position:fixed;inset:0;z-index:9999;" +
                    "background:rgba(30,136,229,0.15);border:3px dashed #1e88e5;" +
                    "display:flex;align-items:center;justify-content:center;pointer-events:none;";
                overlay.innerHTML = '<div style="color:#1e88e5;font-size:1.5rem;font-weight:600;">Drop files here</div>';
                document.body.appendChild(overlay);
            }}
            function hideOverlay() {{
                if (overlay) {{ overlay.remove(); overlay = null; }}
                if (dragTimer) {{ clearTimeout(dragTimer); dragTimer = null; }}
            }}
            body.addEventListener("dragover", (e) => {{
                e.preventDefault(); showOverlay();
                // Safety: auto-hide after 300ms of no dragover events
                if (dragTimer) clearTimeout(dragTimer);
                dragTimer = setTimeout(hideOverlay, 300);
            }});
            body.addEventListener("dragleave", (e) => {{
                if (e.relatedTarget === null || !body.contains(e.relatedTarget)) hideOverlay();
            }});
            // Use capture phase so we hide overlay even if Quasar QUploader stops propagation
            document.addEventListener("drop", (e) => {{
                hideOverlay();
                // Only intercept drops outside Quasar uploaders (let them handle their own)
                const inUploader = e.target.closest && e.target.closest('.q-uploader');
                if (inUploader) return;
                e.preventDefault();
                const files = e.dataTransfer?.files;
                if (!files || files.length === 0) return;
                const vue = getElement(window._thothUploadId);
                if (vue && vue.$refs.qRef) vue.$refs.qRef.addFiles(files);
            }}, true);
        }})();
    ''')

    # Clipboard image paste (singleton listener — reads dynamic upload ID)
    ui.run_javascript(f'''
        (() => {{
            window._thothUploadId = {_hidden_upload.id};
            if (window._thothPasteInstalled) return;
            window._thothPasteInstalled = true;
            document.addEventListener("paste", (e) => {{
                const items = e.clipboardData?.items;
                if (!items) return;
                const imageFiles = [];
                for (const item of items) {{
                    if (item.type.startsWith("image/")) {{
                        const file = item.getAsFile();
                        if (file) {{
                            const ext = file.type.split("/")[1] || "png";
                            const ts = Date.now();
                            const named = new File([file], "pasted_image_" + ts + "." + ext, {{type: file.type}});
                            imageFiles.push(named);
                        }}
                    }}
                }}
                if (imageFiles.length === 0) return;
                e.preventDefault();
                const vue = getElement(window._thothUploadId);
                if (vue && vue.$refs.qRef) vue.$refs.qRef.addFiles(imageFiles);
            }});
        }})();
    ''')

    # ── Chat input + attach + send + stop ────────────────────────────
    async def _on_attach():
        if sys.platform == "darwin" and os.environ.get("THOTH_NATIVE") == "1":
            path = await browse_file(
                title="Attach file",
                filetypes=[("Supported files", " ".join(f"*.{e}" for e in ALLOWED_UPLOAD_SUFFIXES))],
            )
            if path and os.path.isfile(path):
                name = os.path.basename(path)
                data = await run.io_bound(pathlib.Path(path).read_bytes)
                p.pending_files.append({"name": name, "data": data})
                with p.file_chips_row:
                    idx = len(p.pending_files) - 1
                    def _remove(i=idx, badge=None):
                        if i < len(p.pending_files):
                            p.pending_files.pop(i)
                        if badge:
                            badge.delete()
                    b = ui.badge(f"📎 {name} ✕", color="grey-8").props("outline")
                    b.on("click", lambda b=b, i=idx: _remove(i, b))
                    b.style("cursor: pointer;")
        else:
            await ui.run_javascript(
                f"document.getElementById('c{_hidden_upload.id}').querySelector('input[type=file]').click()"
            )

    with ui.row().classes("w-full items-end gap-2 shrink-0"):
        ui.button(icon="attach_file", on_click=_on_attach).props("flat round dense").tooltip("Attach files")

        p.chat_input = ui.input(placeholder="Ask anything…").classes("flex-grow").props("outlined dense")

        async def _on_send():
            text = p.chat_input.value
            if text and text.strip():
                p.chat_input.value = ""
                await send_message(text)
            elif p.pending_files:
                p.chat_input.value = ""
                await send_message("")

        p.chat_input.on("keydown.enter", _on_send)
        ui.button(icon="send", on_click=_on_send).props("color=primary round")

        def _on_stop():
            gen = _active_generations.get(state.thread_id)
            if gen:
                gen.stop_event.set()
            tts = state.tts_service
            if tts and tts.enabled:
                tts.stop()
                if state.voice_service and state.voice_service.is_running:
                    state.voice_service.unmute()
            if p.stop_btn:
                p.stop_btn.props('icon=hourglass_top')

        p.stop_btn = ui.button(icon="stop", on_click=_on_stop).props("round").tooltip("Stop generation")
        _has_active = state.thread_id in _active_generations
        if not _has_active:
            p.stop_btn.disable()

    # ── Voice bar ────────────────────────────────────────────────────
    with ui.row().classes("w-full items-center shrink-0 gap-2 py-1"):
        def _toggle_voice(e):
            state.voice_enabled = e.value
            if e.value:
                state.voice_service.start()
            else:
                state.voice_service.stop()
        p.voice_switch = ui.switch("🎤 Voice", value=state.voice_enabled, on_change=_toggle_voice)
        p.voice_status_label = ui.label("").classes("text-xs text-grey-6")
