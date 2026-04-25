"""Thoth UI — sidebar (left drawer) with thread list.

Builds the sidebar drawer, home/new buttons, thread listing, and
settings/help buttons.  All navigation is handled via callbacks so
the module stays decoupled from the main page layout.
"""

from __future__ import annotations

import base64
import logging
import uuid
from datetime import datetime
from typing import Any, Callable

from nicegui import run, ui
from ui.timer_utils import safe_timer

from ui.state import AppState, P, _active_generations
from ui.constants import SIDEBAR_MAX_THREADS

logger = logging.getLogger(__name__)

# Module-level so filter choice survives rebuild_main() re-renders.
_SIDEBAR_FILTER: str = "all"  # one of: "all", "chat", "designer", "workflow"
_MODAL_FILTER: str = "all"
# ═════════════════════════════════════════════════════════════════════════════
# SIDEBAR AVATAR — CSS
# ═════════════════════════════════════════════════════════════════════════════

_SIDEBAR_AVATAR_CSS = """
<style>
/* ── Base avatar ─────────────────────────────────────────────────── */
.sb-avatar {
    width: 150px; height: 150px;
    border-radius: 50%;
    display: flex; align-items: center; justify-content: center;
    font-size: 4.5rem;
    color: gold;
    border: 2px solid transparent;
    cursor: pointer;
    user-select: none;
    background: rgba(0,0,0,0.35);
    flex-shrink: 0;
    position: relative;
    transition: box-shadow 0.5s ease, transform 0.15s ease;
    overflow: hidden;
}
.sb-avatar img {
    width: 100%; height: 100%;
    object-fit: cover;
    border-radius: 50%;
}
.sb-avatar:hover { transform: scale(1.06); }

/* spinning conic-gradient ring */
.sb-avatar::after {
    content: "";
    position: absolute;
    inset: -5px;
    border-radius: 50%;
    padding: 4px;
    background: conic-gradient(
        from 0deg,
        transparent 0%,
        var(--av-color) 25%,
        transparent 50%,
        var(--av-color) 75%,
        transparent 100%
    );
    -webkit-mask: radial-gradient(farthest-side, transparent calc(100% - 3px), #fff calc(100% - 3px));
    mask: radial-gradient(farthest-side, transparent calc(100% - 3px), #fff calc(100% - 3px));
    animation: sb-ring-spin 4s linear infinite;
    opacity: 0.7;
    transition: opacity 0.4s ease;
}

/* ── Ring spin ────────────────────────────────────────────────────── */
@keyframes sb-ring-spin {
    0%   { transform: rotate(0deg); }
    100% { transform: rotate(360deg); }
}

/* ── Idle: gentle pulse ──────────────────────────────────────────── */
@keyframes sb-pulse-idle {
    0%   { box-shadow: 0 0 6px 2px var(--av-color); }
    50%  { box-shadow: 0 0 14px 4px var(--av-color); }
    100% { box-shadow: 0 0 6px 2px var(--av-color); }
}
.sb-avatar.sb-idle {
    animation: sb-pulse-idle 3s ease-in-out infinite;
}
.sb-avatar.sb-idle::after {
    animation: sb-ring-spin 4s linear infinite;
}

/* ── Streaming: fast spin + bright glow ──────────────────────────── */
@keyframes sb-pulse-stream {
    0%   { box-shadow: 0 0 8px 3px var(--av-color); }
    50%  { box-shadow: 0 0 24px 8px var(--av-color); }
    100% { box-shadow: 0 0 8px 3px var(--av-color); }
}
.sb-avatar.sb-streaming {
    animation: sb-pulse-stream 1.2s ease-in-out infinite;
}
.sb-avatar.sb-streaming::after {
    animation: sb-ring-spin 1.5s linear infinite;
    opacity: 1;
}

/* ── Error: red shake ────────────────────────────────────────────── */
@keyframes sb-shake {
    0%, 100% { transform: translateX(0); }
    10%  { transform: translateX(-4px); }
    20%  { transform: translateX(4px); }
    30%  { transform: translateX(-3px); }
    40%  { transform: translateX(3px); }
    50%  { transform: translateX(-2px); }
    60%  { transform: translateX(2px); }
    70%  { transform: translateX(0); }
}
.sb-avatar.sb-error {
    --av-color: #f44336;
    animation: sb-shake 0.6s ease-in-out;
    box-shadow: 0 0 18px 5px #f44336;
}
.sb-avatar.sb-error::after {
    animation: sb-ring-spin 1s linear infinite;
    opacity: 1;
}

/* ── Voice: cyan breathing ───────────────────────────────────────── */
@keyframes sb-breathe {
    0%, 100% { box-shadow: 0 0 6px 2px #00bcd4; transform: scale(1); }
    50%      { box-shadow: 0 0 20px 6px #00bcd4; transform: scale(1.03); }
}
.sb-avatar.sb-voice {
    --av-color: #00bcd4;
    animation: sb-breathe 2s ease-in-out infinite;
}

/* ── Task running: green ring + bounce ───────────────────────────── */
@keyframes sb-bounce {
    0%, 100% { transform: translateY(0); }
    50%      { transform: translateY(-3px); }
}
.sb-avatar.sb-task {
    --av-color: #4caf50;
    animation: sb-bounce 1.8s ease-in-out infinite;
    box-shadow: 0 0 10px 3px #4caf50;
}
.sb-avatar.sb-task::after {
    animation: sb-ring-spin 2s linear infinite;
    opacity: 1;
}

/* ── Approval pending: amber throb ───────────────────────────────── */
@keyframes sb-throb {
    0%, 100% { box-shadow: 0 0 6px 2px #FFA726; transform: scale(1); }
    50%      { box-shadow: 0 0 22px 8px #FF7043; transform: scale(1.05); }
}
.sb-avatar.sb-approval {
    --av-color: #FFA726;
    animation: sb-throb 1.4s ease-in-out infinite;
}
.sb-avatar.sb-approval::after {
    animation: sb-ring-spin 1.8s linear infinite;
    opacity: 1;
}

/* ── Done: green flash (transient) ───────────────────────────────── */
@keyframes sb-flash {
    0%   { box-shadow: 0 0 8px 3px #4caf50; transform: scale(1); }
    40%  { box-shadow: 0 0 30px 10px #4caf50; transform: scale(1.12); }
    100% { box-shadow: 0 0 8px 3px var(--av-color); transform: scale(1); }
}
.sb-avatar.sb-done {
    animation: sb-flash 1.5s ease-out forwards;
}

/* ── TTS speaking: purple wiggle ─────────────────────────────────── */
@keyframes sb-wiggle {
    0%, 100% { transform: rotate(0deg); }
    15%  { transform: rotate(-3deg); }
    30%  { transform: rotate(3deg); }
    45%  { transform: rotate(-2deg); }
    60%  { transform: rotate(2deg); }
    75%  { transform: rotate(-1deg); }
    90%  { transform: rotate(1deg); }
}
.sb-avatar.sb-tts {
    --av-color: #9c27b0;
    animation: sb-wiggle 0.8s ease-in-out infinite;
    box-shadow: 0 0 12px 4px #9c27b0;
}
.sb-avatar.sb-tts::after {
    animation: sb-ring-spin 1.2s linear infinite;
    opacity: 1;
}

/* ── State label ─────────────────────────────────────────────────── */
.sb-state-label {
    font-size: 0.7rem;
    letter-spacing: 0.5px;
    text-transform: uppercase;
    opacity: 0.7;
    transition: color 0.4s ease, opacity 0.3s ease;
    text-align: center;
    min-height: 1em;
}
</style>
"""


def build_sidebar(
    state: AppState,
    p: P,
    *,
    rebuild_main: Callable[[], None],
    open_settings: Callable[..., None],
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
    from threads import _list_threads, _save_thread_meta, _delete_thread, _get_thread_project_id
    from tasks import get_running_tasks, stop_task
    from models import is_cloud_model, get_current_model
    from memory_extraction import set_active_thread
    from agent import clear_summary_cache

    # Keep a reference the caller can use
    _rebuild_thread_list_ref: list[Callable[[], None]] = [lambda: None]

    with ui.left_drawer(value=True, fixed=True).style(
        "width: 280px;"
    ).classes("thoth-panel-card"):
        # Logo — always Thoth branding, independent of identity settings
        ui.html(
            '<div style="display:flex; align-items:center; gap:8px;">'
            '<span style="font-size:1.6rem; color:gold;">𓁟</span>'
            '<span style="font-size:1.25rem; font-weight:600; color:gold;'
            ' letter-spacing:0.5px;">Thoth</span></div>',
            sanitize=False,
        )
        ui.label("Personal AI Sovereignty").classes("text-xs text-grey-6").style(
            "margin-top: -2px;"
        )
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
                state.active_designer_project = None
                state.thread_id = None
                state.thread_name = None
                state.messages = []
                p.pending_files.clear()
                set_active_thread(None, previous_id=prev)
                rebuild_main()
                _rebuild_thread_list_ref[0]()

            _home_btn = ui.button("🏠 Home", on_click=_go_home).classes("flex-grow").props("flat")

            async def _new_thread():
                tid = uuid.uuid4().hex[:12]
                name = f"💻 Thread {datetime.now().strftime('%b %d, %H:%M')}"
                await run.io_bound(_save_thread_meta, tid, name)
                prev = state.thread_id
                prev_gen = _active_generations.get(prev) if prev else None
                if prev_gen and prev_gen.status == "streaming":
                    prev_gen.detached = True
                    if prev_gen.tts_active:
                        state.tts_service.stop()
                        prev_gen.tts_active = False
                state.active_designer_project = None
                state.thread_id = tid
                state.thread_name = name
                state.messages = []
                state.thread_model_override = ""
                p.pending_files.clear()
                set_active_thread(tid, previous_id=prev)
                rebuild_main()
                _rebuild_thread_list_ref[0]()

            ui.button("＋ New", on_click=_new_thread).classes("flex-grow").props("color=primary")

        with ui.column().classes("w-full gap-1 q-mt-sm thoth-inner-panel"):
            ui.label("Conversations").classes("text-subtitle2")
            # Filter pill row — rebuilt by _rebuild_thread_list so counts stay fresh.
            p.thread_filter_container = ui.row().classes(
                "w-full gap-1 items-center no-wrap q-mb-xs"
            ).style("flex-wrap: wrap;")
            p.thread_container = ui.column().classes("w-full gap-0")

        # ── Channel monitor panel ────────────────────────────────────
        _ch_icon_map = {
            "telegram": "send",
            "discord": "sports_esports",
            "slack": "tag",
            "sms": "textsms",
            "whatsapp": "forum",
        }

        def _fmt_ago(epoch: float | None) -> str:
            """Format seconds-since-epoch as a relative string."""
            if epoch is None:
                return ""
            import time as _t
            delta = int(_t.time() - epoch)
            if delta < 60:
                return "just now"
            if delta < 3600:
                return f"{delta // 60}m ago"
            if delta < 86400:
                return f"{delta // 3600}h ago"
            return f"{delta // 86400}d ago"

        with ui.column().classes("w-full gap-0 q-mt-sm thoth-inner-panel"):
            _ch_monitor_container = ui.column().classes("w-full gap-0")

        def _build_channel_monitor() -> None:
            from channels.registry import all_channels
            from channels.base import get_last_activity

            _ch_monitor_container.clear()
            channels = all_channels()
            if not channels:
                return

            with _ch_monitor_container:
                ui.label("Channels").classes("text-subtitle2")

                for ch in channels:
                    is_on = ch.is_running()
                    is_cfg = ch.is_configured()

                    if is_on:
                        dot_color = "#4caf50"
                        status_text = _fmt_ago(get_last_activity(ch.name)) or "Running"
                    elif is_cfg:
                        dot_color = "#ff9800"
                        status_text = "Stopped"
                    else:
                        dot_color = "#666"
                        status_text = "Off"

                    icon_name = _ch_icon_map.get(ch.name, "chat")

                    def _ch_click(e, _ch=ch):
                        open_settings("Channels")

                    with ui.row().classes(
                        "w-full items-center no-wrap cursor-pointer q-py-xs q-px-sm rounded"
                    ).style(
                        "min-height: 28px; gap: 6px;"
                        "transition: background 0.15s;"
                    ).on("click", _ch_click).on(
                        "mouseenter",
                        js_handler="(e) => e.currentTarget.style.background='rgba(255,255,255,0.06)'",
                    ).on(
                        "mouseleave",
                        js_handler="(e) => e.currentTarget.style.background='transparent'",
                    ):
                        # Status dot
                        ui.html(
                            f'<span style="display:inline-block;width:8px;height:8px;'
                            f'border-radius:50%;background:{dot_color};flex-shrink:0;"></span>',
                            sanitize=False,
                        )
                        # Channel icon
                        ui.icon(icon_name, size="xs").classes(
                            "text-grey-5" if not is_on else "text-primary"
                        ).style("font-size: 0.85rem;")
                        # Name
                        ui.label(ch.display_name).classes("ellipsis").style(
                            "font-size: 0.8rem; flex-grow: 1;"
                            + ("opacity: 0.45;" if not is_cfg else "")
                        )
                        # Activity / status
                        ui.label(status_text).classes("text-grey-6").style(
                            "font-size: 0.7rem; flex-shrink: 0;"
                        )

        _build_channel_monitor()
        safe_timer(5.0, _build_channel_monitor)

        # Spacer pushes bottom section down
        ui.space()

        # ── Reactive Avatar ──────────────────────────────────────────
        ui.html(_SIDEBAR_AVATAR_CSS, sanitize=False)

        from ui.status_bar import (
            _load_avatar_config, _save_avatar_config,
            _AVATAR_EMOJIS, _RING_COLORS, _DEFAULT_EMOJI, _DEFAULT_COLOR,
        )
        from tools import registry as _tool_reg
        from tasks import get_running_tasks as _get_running, get_pending_approvals as _get_approvals

        avatar_cfg = _load_avatar_config()
        _av_mode = avatar_cfg.get("mode", "emoji")
        _av_emoji = avatar_cfg.get("emoji", _DEFAULT_EMOJI)
        _av_color = avatar_cfg.get("color", _DEFAULT_COLOR)
        _av_image = avatar_cfg.get("image", "")

        # Build the avatar HTML
        def _avatar_html(mode: str, emoji: str, color: str, image: str, css_class: str = "sb-idle") -> str:
            if mode == "image" and image:
                inner = f'<img src="data:image/png;base64,{image}" alt="avatar" />'
            else:
                inner = emoji
            return (
                f'<div class="sb-avatar {css_class}" style="--av-color: {color};">'
                f'{inner}</div>'
            )

        with ui.column().classes("w-full items-center gap-2 q-mb-sm"):
            p.sidebar_avatar = ui.html(
                _avatar_html(_av_mode, _av_emoji, _av_color, _av_image),
                sanitize=False,
            )
            p.sidebar_avatar_label = ui.label("Idle").classes("sb-state-label text-grey-5")

        # ── State tracking for reactive animations ───────────────────
        _prev_state: dict = {"name": "idle", "done_until": 0.0}

        def _poll_avatar_state() -> None:
            """Poll reactive signals and swap CSS classes (every 1.5 s)."""
            import time as _time
            now = _time.time()
            cfg = _load_avatar_config()
            mode = cfg.get("mode", "emoji")
            emoji = cfg.get("emoji", _DEFAULT_EMOJI)
            color = cfg.get("color", _DEFAULT_COLOR)
            image = cfg.get("image", "")

            # Determine current state (priority: error > approval > streaming > tts > voice > task > done > idle)
            new_state = "idle"
            state_label = "Idle"
            state_color = "#9e9e9e"

            # Check active generations
            any_streaming = False
            any_error = False
            any_tts = False
            any_done = False
            for gen in _active_generations.values():
                if gen.status == "streaming":
                    any_streaming = True
                if gen.status == "error":
                    any_error = True
                if gen.tts_active:
                    any_tts = True

            # Check tasks & approvals
            try:
                running_tasks = _get_running()
                pending_approvals = _get_approvals()
            except Exception:
                running_tasks = {}
                pending_approvals = []

            # Priority resolution
            if any_error:
                new_state = "error"
                state_label = "Error"
                state_color = "#f44336"
            elif pending_approvals:
                new_state = "approval"
                state_label = "Needs Approval"
                state_color = "#FFA726"
            elif any_streaming:
                new_state = "streaming"
                state_label = "Generating"
                state_color = "#FFD700"
            elif any_tts:
                new_state = "tts"
                state_label = "Speaking"
                state_color = "#9c27b0"
            elif state.voice_enabled:
                new_state = "voice"
                state_label = "Listening"
                state_color = "#00bcd4"
            elif running_tasks:
                new_state = "task"
                state_label = "Workflows Running"
                state_color = "#4caf50"
            elif _prev_state.get("done_until", 0) > now:
                new_state = "done"
                state_label = "Done"
                state_color = "#4caf50"
            else:
                new_state = "idle"
                state_label = "Idle"
                state_color = "#9e9e9e"

            # Detect transition to done (streaming→not streaming)
            if _prev_state["name"] in ("streaming",) and new_state == "idle":
                new_state = "done"
                state_label = "Done"
                state_color = "#4caf50"
                _prev_state["done_until"] = now + 3.0  # show for 3 seconds

            css_class = f"sb-{new_state}"

            # Only update DOM if state changed
            if new_state != _prev_state["name"]:
                _prev_state["name"] = new_state
                if p.sidebar_avatar is not None:
                    p.sidebar_avatar.set_content(
                        _avatar_html(mode, emoji, color, image, css_class)
                    )
                if p.sidebar_avatar_label is not None:
                    p.sidebar_avatar_label.set_text(state_label)
                    p.sidebar_avatar_label.style(f"color: {state_color};")

        safe_timer(1.5, _poll_avatar_state)

        # ── Avatar picker dialog ─────────────────────────────────────
        def _show_avatar_picker():
            with ui.dialog() as dlg, ui.card().style("min-width: 340px; max-width: 420px;"):
                ui.label("Customize Avatar").classes("text-subtitle1 font-bold")
                ui.separator()

                current = _load_avatar_config()
                cur_mode = current.get("mode", "emoji")
                cur_emoji = current.get("emoji", _DEFAULT_EMOJI)
                cur_color = current.get("color", _DEFAULT_COLOR)
                cur_image = current.get("image", "")
                cur_prompt = current.get("image_prompt", "")

                pick_state: dict = {
                    "mode": cur_mode,
                    "emoji": cur_emoji,
                    "color": cur_color,
                    "image": cur_image,
                    "image_prompt": cur_prompt,
                }

                # ── Preview ──────────────────────────────────────────
                preview_html = _avatar_html(
                    pick_state["mode"], pick_state["emoji"],
                    pick_state["color"], pick_state["image"],
                )
                preview_el = ui.html(preview_html, sanitize=False).classes("q-mx-auto")

                def _refresh_preview():
                    preview_el.set_content(_avatar_html(
                        pick_state["mode"], pick_state["emoji"],
                        pick_state["color"], pick_state["image"],
                    ))

                ui.separator()

                # ── Emoji grid ───────────────────────────────────────
                ui.label("Pick Icon").classes("text-xs text-grey-5 q-mt-xs")
                with ui.element("div").style(
                    "display: grid; grid-template-columns: repeat(6, 1fr); gap: 4px;"
                ):
                    for e in _AVATAR_EMOJIS:
                        def _pick_emoji(ev, em=e):
                            pick_state["emoji"] = em
                            pick_state["mode"] = "emoji"
                            _refresh_preview()
                        ui.button(e, on_click=_pick_emoji).props(
                            "flat dense padding=4px"
                        ).style("font-size: 1.2rem; min-width: 36px;")

                # ── Ring color ───────────────────────────────────────
                ui.label("Ring Color").classes("text-xs text-grey-5 q-mt-sm")
                with ui.row().classes("gap-1 flex-wrap"):
                    for c in _RING_COLORS:
                        def _pick_color(ev, cl=c):
                            pick_state["color"] = cl
                            _refresh_preview()
                        ui.button(on_click=_pick_color).style(
                            f"background: {c}; width: 28px; height: 28px; "
                            f"min-width: 28px; border-radius: 50%; padding: 0;"
                        ).props("flat dense")

                # ── AI image generation ──────────────────────────────
                ui.separator()
                ui.label("AI-Generated Avatar").classes("text-xs text-grey-5 q-mt-xs")

                _img_tool = _tool_reg.get_tool("image_gen")
                _img_enabled = _img_tool is not None and _tool_reg.is_enabled("image_gen")

                if _img_enabled:
                    prompt_input = ui.input(
                        label="Describe your avatar…",
                        value=cur_prompt,
                    ).classes("w-full").props("dense outlined")
                    gen_status = ui.label("").classes("text-xs text-grey-5")

                    async def _generate_avatar():
                        prompt_val = prompt_input.value.strip()
                        if not prompt_val:
                            ui.notify("Enter a description first", type="warning")
                            return
                        gen_status.set_text("Generating…")
                        gen_btn.props(add="loading")
                        try:
                            from tools.image_gen_tool import _generate_image
                            result = await run.io_bound(
                                _generate_image,
                                f"A circular profile avatar icon: {prompt_val}. "
                                "Clean, centered, suitable as a small profile picture, "
                                "digital art style, no background.",
                                "1024x1024", "auto",
                            )
                            from tools.image_gen_tool import get_and_clear_last_image
                            b64 = get_and_clear_last_image()
                            if b64:
                                # Resize to 512x512 for crisp rendering
                                try:
                                    import io
                                    from PIL import Image
                                    raw = base64.b64decode(b64)
                                    img = Image.open(io.BytesIO(raw))
                                    img = img.resize((512, 512), Image.LANCZOS)
                                    buf = io.BytesIO()
                                    img.save(buf, format="PNG")
                                    b64 = base64.b64encode(buf.getvalue()).decode("ascii")
                                except ImportError:
                                    # PIL not available — store full-size
                                    pass
                                pick_state["image"] = b64
                                pick_state["image_prompt"] = prompt_val
                                pick_state["mode"] = "image"
                                _refresh_preview()
                                gen_status.set_text("Generated!")
                            else:
                                gen_status.set_text(f"Failed: {result}")
                        except Exception as exc:
                            gen_status.set_text(f"Error: {exc}")
                            logger.warning("Avatar generation failed: %s", exc)
                        finally:
                            gen_btn.props(remove="loading")

                    gen_btn = ui.button(
                        "🎨 Generate", on_click=_generate_avatar
                    ).classes("w-full q-mt-xs").props("dense no-caps color=deep-purple-8")
                else:
                    ui.input(
                        label="Image gen not enabled",
                    ).classes("w-full").props("dense outlined disable")
                    ui.label(
                        "Enable the Image Generation tool in Settings → Tools"
                    ).classes("text-xs text-grey-6")

                # ── Save / Cancel ────────────────────────────────────
                ui.separator()
                with ui.row().classes("w-full justify-end gap-2"):
                    ui.button("Cancel", on_click=dlg.close).props("flat dense")

                    def _save_and_close():
                        _save_avatar_config(pick_state)
                        dlg.close()
                        # Update sidebar avatar immediately
                        if p.sidebar_avatar is not None:
                            p.sidebar_avatar.set_content(
                                _avatar_html(
                                    pick_state["mode"], pick_state["emoji"],
                                    pick_state["color"], pick_state["image"],
                                    f"sb-{_prev_state['name']}",
                                )
                            )

                    ui.button("Save", on_click=_save_and_close).props("dense color=amber")

            dlg.open()

        if p.sidebar_avatar is not None:
            p.sidebar_avatar.on("click", lambda: _show_avatar_picker())

        # Help & Settings buttons
        with ui.row().classes("w-full justify-center items-center gap-1"):
            def _show_help():
                state.show_onboarding = True
                rebuild_main()

            ui.button("👋", on_click=_show_help).props("flat dense").style("font-size: 1.1rem;")
            ui.button(icon="settings", on_click=lambda: open_settings()).props(
                "flat dense round size=sm"
            ).classes("text-grey-5").style("font-size: 1.25rem;")
        from version import __version__ as _v
        ui.label(f"v{_v}").classes("text-xs text-grey-7 w-full text-center").style(
            "margin-top: -4px; letter-spacing: 0.3px; opacity: 0.5;"
        )

    # ── Thread list builder ──────────────────────────────────────────

    def _rebuild_thread_list() -> None:
        if p.thread_container is None:
            return
        p.thread_container.clear()
        if p.thread_filter_container is not None:
            p.thread_filter_container.clear()
        threads = _list_threads()
        running_tids = get_running_tasks()

        # Classify every thread once so pills + list share the same data.
        from threads import get_workflow_thread_ids
        workflow_tids = get_workflow_thread_ids()

        def _cat_of(pid: str, tid: str) -> str:
            if pid:
                return "designer"
            if tid in workflow_tids:
                return "workflow"
            return "chat"

        classified: list[tuple] = []
        counts = {"all": len(threads), "chat": 0, "designer": 0, "workflow": 0}
        for row in threads:
            tid = row[0]
            _pid = row[5] if len(row) > 5 else ""
            cat = _cat_of(_pid, tid)
            counts[cat] += 1
            classified.append((row, cat))

        # ── Filter pill row ─────────────────────────────────────────
        global _SIDEBAR_FILTER
        if p.thread_filter_container is not None and counts["all"] > 0:
            pills = [
                ("all", "All", counts["all"]),
                ("chat", "Chats", counts["chat"]),
                ("designer", "Designs", counts["designer"]),
                ("workflow", "Workflows", counts["workflow"]),
            ]
            with p.thread_filter_container:
                for key, label, n in pills:
                    # Hide empty buckets other than "All".
                    if key != "all" and n == 0:
                        continue
                    is_on = _SIDEBAR_FILTER == key

                    def _set_filter(k=key):
                        global _SIDEBAR_FILTER
                        _SIDEBAR_FILTER = k
                        _rebuild_thread_list()

                    btn = ui.button(
                        f"{label} {n}" if n else label,
                        on_click=_set_filter,
                    ).props(
                        "dense no-caps size=sm rounded "
                        + ("color=amber" if is_on else "flat color=grey-5")
                    ).style("font-size: 0.72rem; padding: 2px 8px;")
                    if is_on:
                        btn.classes("thoth-pill-active")

        # Apply filter
        if _SIDEBAR_FILTER != "all":
            classified = [c for c in classified if c[1] == _SIDEBAR_FILTER]

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
            if not classified:
                ui.label("No conversations yet." if _SIDEBAR_FILTER == "all"
                         else "Nothing in this filter.").classes(
                    "text-grey-6 text-sm q-px-sm"
                )
                return

            visible = classified[:SIDEBAR_MAX_THREADS]
            for row, _cat in visible:
                tid, name, created, updated, *_rest = row
                _thread_model_ov = _rest[0] if _rest else ""
                _thread_project_id = _rest[1] if len(_rest) > 1 else ""
                name = name or ""
                is_active = tid == state.thread_id
                is_running = tid in running_tids
                is_generating_tid = tid in _active_generations
                is_cloud_thread = is_cloud_model(_thread_model_ov or get_current_model())
                is_designer_thread = bool(_thread_project_id)

                async def _select(t=tid, n=name, mo=_thread_model_ov, pid=_thread_project_id):
                    prev = state.thread_id
                    prev_gen = _active_generations.get(prev) if prev else None
                    if prev_gen and prev_gen.status == "streaming":
                        prev_gen.detached = True
                        if prev_gen.tts_active:
                            state.tts_service.stop()
                            prev_gen.tts_active = False

                    async def _load_messages_cached(tid_: str) -> list[dict]:
                        cached = state.message_cache.get(tid_)
                        if cached is not None and tid_ not in state.message_cache_dirty:
                            return list(cached)
                        msgs = await run.io_bound(load_thread_messages, tid_)
                        state.message_cache[tid_] = list(msgs)
                        state.message_cache_dirty.discard(tid_)
                        return msgs

                    if pid:
                        # Designer thread — open the associated project
                        from designer.storage import load_project
                        proj = load_project(pid)
                        if proj:
                            state.thread_id = t
                            state.thread_name = n
                            state.thread_model_override = mo or ""
                            state.messages = await _load_messages_cached(t)
                            p.pending_files.clear()
                            set_active_thread(t, previous_id=prev)
                            state.active_designer_project = proj
                            rebuild_main()
                            _rebuild_thread_list_ref[0]()
                            return
                        # Project missing — fall through to normal thread behaviour

                    # Non-designer thread (or missing project) — close designer if open
                    state.active_designer_project = None
                    state.thread_id = t
                    state.thread_name = n
                    state.thread_model_override = mo or ""
                    state.messages = await _load_messages_cached(t)
                    p.pending_files.clear()
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
                    state.invalidate_thread_cache(t)
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
                        elif is_designer_thread:
                            _thr_icon = "brush"
                        elif is_cloud_thread:
                            _thr_icon = "cloud"
                        elif name.startswith("✈️"):
                            _thr_icon = "send"
                        elif name.startswith("📧"):
                            _thr_icon = "email"
                        elif name.startswith("⚡"):
                            _thr_icon = "electric_bolt"
                        elif name.startswith("�") or "WhatsApp" in name:
                            _thr_icon = "forum"
                        elif name.startswith("🎮") or "Discord" in name:
                            _thr_icon = "sports_esports"
                        elif name.startswith("�📱"):
                            _thr_icon = "textsms"
                        elif name.startswith("💬"):
                            _thr_icon = "chat"
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
                    from ui.bulk_select import BulkSelect, render_bulk_action_bar
                    from ui.confirm import confirm_destructive
                    from threads import delete_threads as _bulk_delete_threads

                    bulk = BulkSelect()

                    def _purge_external(t: str) -> None:
                        """Cleanup outside threads.py: session kills, history,
                        active generation stop, task stop. Safe on missing ids.
                        """
                        try:
                            gen = _active_generations.get(t)
                            if gen:
                                gen.stop_event.set()
                        except Exception:
                            pass
                        try:
                            stop_task(t)
                        except Exception:
                            pass
                        try:
                            clear_summary_cache(t)
                        except Exception:
                            pass
                        try:
                            from tools.shell_tool import (
                                get_session_manager, clear_shell_history,
                            )
                            get_session_manager().kill_session(t)
                            clear_shell_history(t)
                        except Exception:
                            pass
                        try:
                            from tools.browser_tool import (
                                get_session_manager as get_browser_session_manager,
                                clear_browser_history,
                            )
                            get_browser_session_manager().kill_session(t)
                            clear_browser_history(t)
                        except Exception:
                            pass

                    with ui.dialog() as dlg, ui.card().classes("w-96"):
                        with ui.row().classes("w-full items-center justify-between"):
                            ui.label("All Conversations").classes("text-h6")
                            select_btn = ui.button("Select").props(
                                "flat dense no-caps size=sm"
                            )

                        def _toggle_mode():
                            bulk.toggle_mode()
                            select_btn.text = "Done" if bulk.active else "Select"
                            _rebuild_dialog_list()

                        select_btn.on("click", _toggle_mode)

                        # Classify once for filter + pills
                        from threads import get_workflow_thread_ids as _gwf
                        _wf_tids = _gwf()

                        def _cat_modal(pid: str, tid: str) -> str:
                            if pid:
                                return "designer"
                            if tid in _wf_tids:
                                return "workflow"
                            return "chat"

                        _modal_counts = {"all": len(threads), "chat": 0,
                                         "designer": 0, "workflow": 0}
                        for _r in threads:
                            _pid = _r[5] if len(_r) > 5 else ""
                            _modal_counts[_cat_modal(_pid, _r[0])] += 1

                        filter_row = ui.row().classes(
                            "w-full gap-1 items-center q-mb-xs"
                        ).style("flex-wrap: wrap;")

                        def _render_modal_pills():
                            filter_row.clear()
                            global _MODAL_FILTER
                            pills = [
                                ("all", "All", _modal_counts["all"]),
                                ("chat", "Chats", _modal_counts["chat"]),
                                ("designer", "Designs",
                                 _modal_counts["designer"]),
                                ("workflow", "Workflows",
                                 _modal_counts["workflow"]),
                            ]
                            with filter_row:
                                for key, label, n in pills:
                                    if key != "all" and n == 0:
                                        continue
                                    is_on = _MODAL_FILTER == key

                                    def _set_mf(k=key):
                                        global _MODAL_FILTER
                                        _MODAL_FILTER = k
                                        _render_modal_pills()
                                        _rebuild_dialog_list()

                                    ui.button(
                                        f"{label} {n}" if n else label,
                                        on_click=_set_mf,
                                    ).props(
                                        "dense no-caps size=sm rounded "
                                        + ("color=amber" if is_on else "flat color=grey-5")
                                    ).style(
                                        "font-size: 0.72rem; padding: 2px 8px;"
                                    )

                        _render_modal_pills()

                        list_container = ui.column().classes("w-full gap-0")

                        def _rebuild_dialog_list() -> None:
                            list_container.clear()
                            # Filtered view of threads
                            _filtered = [
                                r for r in threads
                                if (_MODAL_FILTER == "all"
                                    or _cat_modal(r[5] if len(r) > 5 else "",
                                                  r[0]) == _MODAL_FILTER)
                            ]
                            with list_container:
                                if not _filtered:
                                    ui.label("Nothing in this filter.").classes(
                                        "text-grey-6 q-pa-md"
                                    )
                                    return
                                with ui.list().props("bordered separator").classes("w-full"):
                                    for row in _filtered:
                                        tid, name, created, updated, *_rest2 = row
                                        _mo2 = _rest2[0] if _rest2 else ""

                                        def _sel(t=tid, n=name, mo=_mo2):
                                            # In selection mode, clicking a row toggles selection
                                            if bulk.active:
                                                bulk.toggle_item(t)
                                                return
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
                                            _purge_external(t)
                                            _delete_thread(t)
                                            if state.thread_id == t:
                                                state.thread_id = None
                                                state.messages = []
                                            dlg.close()
                                            rebuild_main()
                                            _rebuild_thread_list_ref[0]()

                                        with ui.item(on_click=_sel).props("clickable"):
                                            if bulk.active:
                                                with ui.item_section().props("avatar").style("min-width: 28px;"):
                                                    cb = ui.checkbox(value=bulk.is_selected(tid))
                                                    cb.on(
                                                        "update:model-value",
                                                        lambda e, t=tid: bulk.toggle_item(
                                                            t, bool(e.args),
                                                        ),
                                                    )
                                                    cb.on(
                                                        "click",
                                                        js_handler="(e) => e.stopPropagation()",
                                                    )
                                            else:
                                                with ui.item_section().props("avatar").style("min-width: 28px;"):
                                                    ui.icon("chat_bubble_outline", size="xs")
                                            with ui.item_section():
                                                ui.item_label(name)
                                                if updated:
                                                    ui.item_label(_fmt_ts(updated)).props("caption")
                                            if not bulk.active:
                                                with ui.item_section().props("side"):
                                                    ui.button(
                                                        icon="delete_outline",
                                                        on_click=lambda e, t=tid: _del(t),
                                                    ).props(
                                                        "flat dense round size=xs color=grey-6"
                                                    ).on(
                                                        "click",
                                                        js_handler="(e) => e.stopPropagation()",
                                                    )

                        action_slot = ui.column().classes("w-full")

                        def _do_bulk_delete(ids: list[str]) -> None:
                            def _commit():
                                for t in ids:
                                    _purge_external(t)
                                deleted, failures = _bulk_delete_threads(ids)
                                if state.thread_id in ids:
                                    state.thread_id = None
                                    state.thread_name = None
                                    state.messages = []
                                msg = f"🗑️ Deleted {deleted} conversation{'s' if deleted != 1 else ''}."
                                if failures:
                                    msg += f" {len(failures)} failed."
                                ui.notify(msg, type="negative" if failures else "info")
                                dlg.close()
                                rebuild_main()
                                _rebuild_thread_list_ref[0]()

                            noun = "conversation" if len(ids) == 1 else "conversations"
                            confirm_destructive(
                                f"Delete {len(ids)} {noun}?",
                                body=(
                                    "This cannot be undone. Sessions, media, "
                                    "and history will be cleared."
                                ),
                                on_confirm=_commit,
                            )

                        with action_slot:
                            render_bulk_action_bar(
                                bulk,
                                on_delete=_do_bulk_delete,
                                label_singular="conversation",
                                label_plural="conversations",
                                on_clear=_rebuild_dialog_list,
                            )

                        ui.separator()
                        with ui.row().classes("w-full gap-2"):
                            def _delete_all():
                                # Respect current filter: only nuke what's visible.
                                all_ids = [
                                    r[0] for r in threads
                                    if (_MODAL_FILTER == "all"
                                        or _cat_modal(r[5] if len(r) > 5 else "",
                                                      r[0]) == _MODAL_FILTER)
                                ]
                                if not all_ids:
                                    ui.notify("Nothing to delete in this filter.",
                                              type="warning")
                                    return

                                def _commit():
                                    for t in all_ids:
                                        _purge_external(t)
                                    _bulk_delete_threads(all_ids)
                                    state.thread_id = None
                                    state.thread_name = None
                                    state.messages = []
                                    dlg.close()
                                    rebuild_main()
                                    _rebuild_thread_list_ref[0]()

                                scope = (
                                    "conversations"
                                    if _MODAL_FILTER == "all"
                                    else {
                                        "chat": "chats",
                                        "designer": "design conversations",
                                        "workflow": "workflow conversations",
                                    }[_MODAL_FILTER]
                                )
                                confirm_destructive(
                                    f"Delete all {len(all_ids)} {scope}?",
                                    body="This cannot be undone.",
                                    on_confirm=_commit,
                                )

                            ui.button("Delete all", icon="delete_sweep", on_click=_delete_all).props(
                                "flat color=negative"
                            ).classes("flex-grow")
                            ui.button("Close", on_click=dlg.close).props("flat").classes("flex-grow")

                        _rebuild_dialog_list()
                    dlg.open()

                ui.button(
                    f"Show all ({len(threads)})", on_click=_show_all
                ).classes("w-full q-mt-xs").props("flat dense size=sm")

    _rebuild_thread_list_ref[0] = _rebuild_thread_list
    _rebuild_thread_list()

    return _rebuild_thread_list
