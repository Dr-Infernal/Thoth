"""Thoth UI — Streaming consumer, send-message, and interrupt-resume logic.

This module extracts the three heavyweight async inner functions from the
monolith:

* ``consume_generation``  — drain event queue and update the UI
* ``send_message``        — append user message, launch producer + consumer
* ``resume_after_interrupt`` — re-start the producer after an approval

Every function receives ``state``, ``p``, and named callbacks so no globals
leak in.
"""

from __future__ import annotations

import asyncio
import base64 as _b64
import logging
import queue
import re
import threading
import uuid
from datetime import datetime
from typing import Any, Callable

from nicegui import run, ui

from ui.state import AppState, GenerationState, P, _active_generations
from ui.constants import (
    SENTENCE_SPLIT,
    MAX_STREAM_SENTENCES,
    YT_URL_PATTERN,
)
from ui.render import autolink_urls

logger = logging.getLogger(__name__)


# ── Type alias for the callback bundle ───────────────────────────────
class _Callbacks:
    """Container for all cross-cutting callbacks.

    Every field *must* be set before ``send_message`` is called.
    """

    __slots__ = (
        "rebuild_main",
        "rebuild_thread_list",
        "show_interrupt",
        "update_token_counter",
        "add_chat_message",
        "add_terminal_entry",
        "render_text_with_embeds",
    )

    def __init__(self) -> None:
        for s in self.__slots__:
            setattr(self, s, None)


Callbacks = _Callbacks  # public alias for wiring in app


# ══════════════════════════════════════════════════════════════════════
# CONSUME GENERATION
# ══════════════════════════════════════════════════════════════════════

async def consume_generation(
    gen: GenerationState,
    state: AppState,
    p: P,
    cb: _Callbacks,
) -> None:
    """Drain *gen.q* and update the UI.  Runs as an ``asyncio.Task``.

    When *gen.detached* is True (user switched to another thread), all UI
    writes are skipped but event accumulation continues so the response is
    ready when the user switches back.
    """
    from agent import get_agent_graph, repair_orphaned_tool_calls
    from langchain_core.messages import AIMessage

    _stopped_shown = False
    _drain_deadline = 0.0

    try:
      while True:
        # ── Stop handling ────────────────────────────────────────────
        if gen.stop_event.is_set() and not _stopped_shown:
            _stopped_shown = True
            gen.status = "stopped"
            _drain_deadline = asyncio.get_event_loop().time() + 30
            if not gen.detached:
                try:
                    if gen.thinking_label:
                        gen.thinking_label.delete()
                        gen.thinking_label = None
                    if gen.thinking_md:
                        gen.thinking_md.delete()
                        gen.thinking_md = None
                    if gen.assistant_md:
                        gen.assistant_md.set_visibility(True)
                        gen.accumulated += "\n\n\u23f9\ufe0f *[Stopped]*"
                        gen.assistant_md.set_content(gen.accumulated)
                except Exception:
                    pass
            if gen.tts_active:
                state.tts_service.stop()

        if _stopped_shown and asyncio.get_event_loop().time() > _drain_deadline:
            break

        try:
            event = gen.q.get_nowait()
        except queue.Empty:
            await asyncio.sleep(0.05)
            continue

        if event is None:
            break

        if _stopped_shown:
            continue

        event_type, payload = event
        _break_loop = False

        # ── First content transition ─────────────────────────────────
        if not gen.first_content and event_type in ("token", "done"):
            gen.first_content = True
            if not gen.detached:
                try:
                    if gen.thinking_label:
                        gen.thinking_label.delete()
                        gen.thinking_label = None
                    if gen.thinking_text and not gen.thinking_collapsed:
                        gen.thinking_collapsed = True
                        if gen.thinking_md:
                            gen.thinking_md.delete()
                            gen.thinking_md = None
                        if gen.tool_col:
                            with gen.tool_col:
                                with ui.expansion(
                                    "\U0001f4ad Thinking", icon="psychology"
                                ).classes("w-full"):
                                    ui.code(
                                        gen.thinking_text.strip()[:8_000]
                                    ).classes("w-full text-xs")
                    if gen.assistant_md:
                        gen.assistant_md.set_visibility(True)
                except Exception:
                    logger.error("Error rendering thinking collapse", exc_info=True)

        if event_type == "error":
            gen.status = "error"
            gen.error = payload
            gen.accumulated = f"\u26a0\ufe0f An error occurred: {payload}"
            if not gen.detached:
                try:
                    if gen.thinking_label:
                        gen.thinking_label.delete()
                    if gen.assistant_md:
                        gen.assistant_md.set_visibility(True)
                        gen.assistant_md.set_content(gen.accumulated)
                except Exception:
                    pass
            try:
                repair_orphaned_tool_calls(gen.enabled_tools, gen.config)
            except Exception:
                pass
            try:
                _agent = get_agent_graph()
                _agent.update_state(
                    gen.config,
                    {"messages": [AIMessage(content=gen.accumulated)]},
                )
            except Exception:
                logger.debug("Failed to persist error to checkpoint", exc_info=True)
            _break_loop = True

        elif event_type == "tool_call":
            if not gen.detached and gen.tool_col:
                try:
                    with gen.tool_col:
                        _pending_exp = ui.expansion(
                            f"\U0001f504 {payload}\u2026", icon="hourglass_empty"
                        ).classes("w-full")
                        _pending_exp._thoth_tool_name = payload
                except Exception:
                    pass

        elif event_type == "tool_done":
            _handle_tool_done(gen, state, p, payload, cb)

        elif event_type == "summarizing":
            if not gen.detached and gen.wrapper:
                try:
                    if gen.thinking_label:
                        gen.thinking_label.delete()
                        gen.thinking_label = None
                    with gen.wrapper:
                        gen.thinking_label = ui.html(
                            '<span class="thoth-typing" style="font-size:0.9rem; opacity:0.6;">'
                            '\U0001f4dd Summarizing conversation history<span class="dots">'
                            '<span>.</span><span>.</span><span>.</span></span></span>',
                            sanitize=False,
                        )
                except Exception:
                    pass

        elif event_type == "thinking":
            pass  # spinner already visible

        elif event_type == "thinking_token":
            gen.thinking_text += payload
            if not gen.detached:
                try:
                    if gen.thinking_label:
                        gen.thinking_label.delete()
                        gen.thinking_label = None
                    if gen.thinking_md is None and gen.wrapper:
                        with gen.wrapper:
                            gen.thinking_md = ui.markdown(
                                "", extras=["code-friendly", "fenced-code-blocks"]
                            ).classes("thoth-msg w-full").style(
                                "opacity: 0.55; font-size: 0.88rem; font-style: italic;"
                            )
                    if gen.thinking_md:
                        gen.thinking_md.set_content(gen.thinking_text)
                    if p.chat_scroll:
                        p.chat_scroll.scroll_to(percent=1.0)
                except Exception:
                    pass

        elif event_type == "token":
            gen.accumulated += payload
            if not gen.detached and gen.assistant_md:
                try:
                    gen.assistant_md.set_content(autolink_urls(gen.accumulated))
                    if p.chat_scroll:
                        p.chat_scroll.scroll_to(percent=1.0)
                except Exception:
                    pass

            # Streaming TTS (only when attached)
            if gen.tts_active:
                if "```" in payload:
                    gen.tts_in_code = not gen.tts_in_code
                if not gen.tts_in_code:
                    gen.tts_buffer += payload
                    sentences = SENTENCE_SPLIT.split(gen.tts_buffer)
                    if len(sentences) > 1:
                        for s in sentences[:-1]:
                            if gen.tts_spoken >= MAX_STREAM_SENTENCES:
                                break
                            state.tts_service.speak_streaming(s)
                            gen.tts_spoken += 1
                            if gen.tts_spoken >= MAX_STREAM_SENTENCES:
                                state.tts_service.flush_streaming(
                                    "The full response is shown in the app."
                                )
                                gen.tts_active = False
                        gen.tts_buffer = sentences[-1]

        elif event_type == "interrupt":
            gen.interrupt_data = payload
            gen.status = "interrupted"
            _break_loop = True

        elif event_type == "done":
            gen.accumulated = payload
            if not gen.detached:
                try:
                    if gen.thinking_label:
                        gen.thinking_label.delete()
                        gen.thinking_label = None
                    if gen.thinking_text and not gen.thinking_collapsed:
                        gen.thinking_collapsed = True
                        if gen.thinking_md:
                            gen.thinking_md.delete()
                            gen.thinking_md = None
                        if gen.tool_col:
                            with gen.tool_col:
                                with ui.expansion(
                                    "\U0001f4ad Thinking", icon="psychology"
                                ).classes("w-full"):
                                    ui.code(
                                        gen.thinking_text.strip()[:8_000]
                                    ).classes("w-full text-xs")
                    elif gen.thinking_md:
                        gen.thinking_md.delete()
                        gen.thinking_md = None
                    if gen.assistant_md:
                        gen.assistant_md.set_visibility(True)
                        gen.assistant_md.set_content(autolink_urls(gen.accumulated))
                except Exception:
                    pass

        if _break_loop:
            break

    except Exception:
        logger.error("Error in generation consumer", exc_info=True)

    # ── Finalise ─────────────────────────────────────────────────────
    if gen.status == "streaming":
        gen.status = "done"

    try:
        if not gen.detached:
            if gen.tts_active:
                state.tts_service.flush_streaming(gen.tts_buffer)

            if gen.accumulated and YT_URL_PATTERN.search(gen.accumulated):
                if gen.assistant_md:
                    gen.assistant_md.delete()
                    gen.assistant_md = None
                if gen.wrapper:
                    with gen.wrapper:
                        cb.render_text_with_embeds(gen.accumulated)

            try:
                ui.run_javascript(
                    "document.querySelectorAll('pre code').forEach(el => hljs.highlightElement(el));"
                )
            except RuntimeError:
                pass
    except Exception:
        logger.error("Error in post-stream finalization", exc_info=True)

    # Store assistant message
    if gen.accumulated:
        a_msg: dict = {"role": "assistant", "content": gen.accumulated}
        if gen.tool_results:
            a_msg["tool_results"] = gen.tool_results
        if gen.chart_data:
            a_msg["charts"] = gen.chart_data
        if gen.captured_images:
            a_msg["images"] = gen.captured_images
        if state.thread_id == gen.thread_id:
            state.messages.append(a_msg)

    # Cleanup
    _active_generations.pop(gen.thread_id, None)

    # Update UI if this is still the active thread
    if state.thread_id == gen.thread_id:
        if p.stop_btn:
            p.stop_btn.props('icon=stop')
            p.stop_btn.disable()
        if state.voice_enabled and not (state.tts_service and state.tts_service.enabled):
            state.voice_service.unmute()
        if p.chat_scroll:
            p.chat_scroll.scroll_to(percent=1.0)
        if gen.interrupt_data:
            state.pending_interrupt = gen.interrupt_data
            cb.show_interrupt(gen.interrupt_data)
        cb.update_token_counter()

    cb.rebuild_thread_list()


# ── Tool-done sub-handler ────────────────────────────────────────────

def _handle_tool_done(
    gen: GenerationState,
    state: AppState,
    p: P,
    payload: Any,
    cb: _Callbacks,
) -> None:
    tool_name = payload["name"] if isinstance(payload, dict) else payload
    tool_content = payload.get("content", "") if isinstance(payload, dict) else ""

    # Chart detection
    if tool_content and tool_content.startswith("__CHART__:"):
        marker_end = tool_content.find("\n\n", 10)
        if marker_end == -1:
            fig_json = tool_content[10:]
            display_text = "Chart created"
        else:
            fig_json = tool_content[10:marker_end]
            display_text = tool_content[marker_end + 2:]
        gen.chart_data.append(fig_json)
        if not gen.detached and gen.tool_col:
            try:
                import plotly.io as _pio
                fig = _pio.from_json(fig_json)
                with gen.tool_col:
                    ui.plotly(fig).classes("w-full")
            except Exception:
                pass
        tool_content = display_text

    # Update the pending expansion or create a new one
    if not gen.detached and gen.tool_col:
        try:
            matched_exp = None
            for child in gen.tool_col:
                if hasattr(child, '_thoth_tool_name'):
                    matched_exp = child
            if matched_exp:
                matched_exp._props["icon"] = "check_circle"
                matched_exp._text = f"\u2705 {tool_name}"
                matched_exp.update()
                if tool_content:
                    display = tool_content[:5_000]
                    if len(tool_content) > 5_000:
                        display += "\n\n\u2026 (truncated)"
                    with matched_exp:
                        ui.code(display).classes("w-full text-xs")
                del matched_exp._thoth_tool_name
            else:
                with gen.tool_col:
                    with ui.expansion(f"\u2705 {tool_name}", icon="check_circle").classes("w-full"):
                        if tool_content:
                            display = tool_content[:5_000]
                            if len(tool_content) > 5_000:
                                display += "\n\n\u2026 (truncated)"
                            ui.code(display).classes("w-full text-xs")
        except Exception:
            pass

    gen.tool_results.append({"name": tool_name, "content": tool_content})

    # Shell command -> render in terminal panel
    raw_tool_name = payload.get("raw_name", "") if isinstance(payload, dict) else ""
    if not gen.detached and raw_tool_name == "run_command" and p.terminal_container is not None:
        try:
            _lines = (tool_content or "").split("\n")
            _cmd_line = _lines[0][2:] if _lines and _lines[0].startswith("$ ") else ""
            _info_line = _lines[-1] if _lines else ""
            _e_code = 0
            _dur = 0.0
            _cwd = ""
            _info_m = re.search(
                r"Exit code:\s*(-?\d+)\s*\|\s*Duration:\s*([\d.]+)s\s*\|\s*cwd:\s*(.*)",
                _info_line,
            )
            if _info_m:
                _e_code = int(_info_m.group(1))
                _dur = float(_info_m.group(2))
                _cwd = _info_m.group(3).strip()
            _output_lines = _lines[1:-1] if len(_lines) > 2 else []
            cb.add_terminal_entry({
                "command": _cmd_line,
                "output": "\n".join(_output_lines),
                "exit_code": _e_code,
                "duration": _dur,
                "cwd": _cwd,
            })
            if not getattr(p, "terminal_visible", False):
                p.terminal_visible = True
                if p.terminal_panel is not None:
                    p.terminal_panel.set_visibility(True)
                if hasattr(p, "terminal_chevron") and p.terminal_chevron:
                    p.terminal_chevron.props("icon=expand_less")
            if p.terminal_scroll:
                p.terminal_scroll.scroll_to(percent=1.0)
        except Exception:
            pass

    # Vision capture
    if tool_name in ("\U0001f441\ufe0f Vision", "analyze_image"):
        vsvc = state.vision_service
        if vsvc and vsvc.last_capture:
            b64_img = _b64.b64encode(vsvc.last_capture).decode("ascii")
            gen.captured_images.append(b64_img)
            if not gen.detached and gen.tool_col:
                try:
                    with gen.tool_col:
                        ui.image(f"data:image/jpeg;base64,{b64_img}").classes("w-80 rounded")
                except Exception:
                    pass
            vsvc.last_capture = None

    # Browser screenshot thumbnail
    if not gen.detached and raw_tool_name.startswith("browser_"):
        try:
            from tools.browser_tool import get_session_manager as _get_bsm
            _bsm = _get_bsm()
            if _bsm.has_active_session():
                _bs = _bsm.get_session()
                _screenshot_bytes = _bs.take_screenshot(thread_id=gen.thread_id)
                if _screenshot_bytes:
                    _b64_ss = _b64.b64encode(_screenshot_bytes).decode("ascii")
                    if gen.tool_col:
                        with gen.tool_col:
                            ui.image(f"data:image/png;base64,{_b64_ss}").classes(
                                "w-80 rounded"
                            ).style("border: 1px solid #333; margin-top: 4px;")
        except Exception:
            pass


# ══════════════════════════════════════════════════════════════════════
# SEND MESSAGE
# ══════════════════════════════════════════════════════════════════════

async def send_message(
    text: str,
    *,
    state: AppState,
    p: P,
    cb: _Callbacks,
    voice_mode: bool = False,
) -> None:
    """Send a message and stream the agent response."""
    from agent import stream_agent, repair_orphaned_tool_calls, RECURSION_LIMIT_CHAT
    from threads import _save_thread_meta
    from tools import registry as tool_registry
    from ui.helpers import process_attached_files

    if not text.strip() and not p.pending_files:
        return
    if state.thread_id and state.thread_id in _active_generations:
        return

    # Ensure a thread exists
    if state.thread_id is None:
        tid = uuid.uuid4().hex[:12]
        name = text[:50]
        _save_thread_meta(tid, name)
        state.thread_id = tid
        state.thread_name = name
        state.messages = []
        state.show_onboarding = False
        cb.rebuild_main()
        cb.rebuild_thread_list()

    gen_thread_id = state.thread_id

    # ── Process attached files ───────────────────────────────────────
    file_context = ""
    user_images: list[str] = []
    file_warnings: list[str] = []
    file_names: list[str] = [f["name"] for f in p.pending_files] if p.pending_files else []
    if p.pending_files:
        # Use the effective model for file budget calculation
        _effective_model = state.thread_model_override or None
        try:
            file_context, user_images, file_warnings = await run.io_bound(
                process_attached_files, list(p.pending_files), state.vision_service,
                state.attached_data_cache, _effective_model,
            )
        except Exception as exc:
            logger.error("process_attached_files failed: %s", exc, exc_info=True)
            ui.notify(f"Failed to process attached files: {exc}", type="negative",
                      position="top", close_button=True, timeout=10000)
        p.pending_files.clear()
        if p.file_chips_row:
            p.file_chips_row.clear()
        for fw in file_warnings:
            ui.notify(fw, type="warning", position="top", close_button=True, timeout=8000)

    # ── Build agent input ────────────────────────────────────────────
    agent_input = text
    if file_context:
        agent_input = f"{file_context}\n\n{text}" if text else file_context
    logger.info("send_message: file_names=%s, file_context_len=%d, agent_input_len=%d",
                file_names, len(file_context), len(agent_input))

    if file_names:
        badge_text = ", ".join(f"\U0001f4ce {n}" for n in file_names)
        display_content = f"{badge_text}\n\n{text}" if text.strip() else badge_text
    else:
        display_content = text

    # ── Append user message ──────────────────────────────────────────
    user_msg: dict = {"role": "user", "content": display_content}
    if user_images:
        user_msg["images"] = user_images
    state.messages.append(user_msg)
    cb.add_chat_message(user_msg)

    # Auto-name thread
    if state.thread_name and (
        state.thread_name.startswith("Thread ")
        or state.thread_name.startswith("\U0001f4bb Thread ")
    ):
        state.thread_name = f"\U0001f4bb {display_content[:50]}"
        _save_thread_meta(state.thread_id, state.thread_name)
        cb.rebuild_thread_list()
        if p.chat_header_label:
            p.chat_header_label.set_text(f"\U0001f4ac {state.thread_name}")
    else:
        _save_thread_meta(state.thread_id, state.thread_name)

    # ── Build config ─────────────────────────────────────────────────
    # Sync attachment cache to chart tool so it can read attached data files
    from tools.chart_tool import _attachment_cache as _chart_cache
    _chart_cache.clear()
    _chart_cache.update(state.attached_data_cache)

    _thread_mo = state.thread_model_override or ""
    config = {
        "configurable": {
            "thread_id": gen_thread_id,
            **({"model_override": _thread_mo} if _thread_mo else {}),
        },
        "recursion_limit": RECURSION_LIMIT_CHAT,
    }
    enabled_tools = [t.name for t in tool_registry.get_enabled_tools()]

    if voice_mode:
        agent_input = (
            "[Voice input \u2014 the user is speaking to you via microphone "
            "and your response will be read aloud. Keep responses concise "
            "and conversational.]\n\n" + agent_input
        )

    # ── Create generation state ──────────────────────────────────────
    stop_ev = threading.Event()
    gen = GenerationState(
        thread_id=gen_thread_id,
        q=queue.Queue(),
        stop_event=stop_ev,
        config=config,
        enabled_tools=enabled_tools,
        voice_mode=voice_mode,
        tts_active=voice_mode and state.tts_service.enabled,
    )
    _active_generations[gen_thread_id] = gen

    if p.stop_btn:
        p.stop_btn.enable()

    # ── Prepare assistant message placeholder ────────────────────────
    _build_assistant_placeholder(gen, p)

    if p.chat_scroll:
        p.chat_scroll.scroll_to(percent=1.0)

    # ── Start producer thread ────────────────────────────────────────
    def _sync_stream():
        try:
            for ev in stream_agent(agent_input, enabled_tools, config,
                                   stop_event=stop_ev):
                if stop_ev.is_set():
                    break
                gen.q.put(ev)
        except Exception as exc:
            if not stop_ev.is_set():
                gen.q.put(("error", str(exc)))
        finally:
            if stop_ev.is_set():
                try:
                    repair_orphaned_tool_calls(enabled_tools, config)
                except Exception:
                    pass
            gen.q.put(None)

    threading.Thread(target=_sync_stream, daemon=True).start()

    asyncio.create_task(consume_generation(gen, state, p, cb))
    cb.rebuild_thread_list()


# ══════════════════════════════════════════════════════════════════════
# RESUME AFTER INTERRUPT
# ══════════════════════════════════════════════════════════════════════

async def resume_after_interrupt(
    approved: bool,
    *,
    state: AppState,
    p: P,
    cb: _Callbacks,
) -> None:
    from agent import resume_stream_agent, repair_orphaned_tool_calls, RECURSION_LIMIT_CHAT
    from tools import registry as tool_registry

    pending = state.pending_interrupt
    interrupt_ids = None
    if isinstance(pending, list) and len(pending) > 1:
        interrupt_ids = [
            item.get("__interrupt_id")
            for item in pending
            if isinstance(item, dict) and item.get("__interrupt_id")
        ]
    state.pending_interrupt = None

    gen_thread_id = state.thread_id

    _thread_mo = state.thread_model_override or ""
    config = {
        "configurable": {
            "thread_id": gen_thread_id,
            **({"model_override": _thread_mo} if _thread_mo else {}),
        },
        "recursion_limit": RECURSION_LIMIT_CHAT,
    }
    enabled_tools = [t.name for t in tool_registry.get_enabled_tools()]

    stop_ev = threading.Event()
    gen = GenerationState(
        thread_id=gen_thread_id,
        q=queue.Queue(),
        stop_event=stop_ev,
        config=config,
        enabled_tools=enabled_tools,
    )
    _active_generations[gen_thread_id] = gen

    if p.stop_btn:
        p.stop_btn.enable()

    _build_assistant_placeholder(gen, p)

    if p.chat_scroll:
        p.chat_scroll.scroll_to(percent=1.0)

    # ── Start producer thread ────────────────────────────────────────
    def _sync_resume():
        try:
            for ev in resume_stream_agent(
                enabled_tools, config, approved,
                interrupt_ids=interrupt_ids,
                stop_event=stop_ev,
            ):
                if stop_ev.is_set():
                    break
                gen.q.put(ev)
        except Exception as exc:
            if not stop_ev.is_set():
                gen.q.put(("error", str(exc)))
        finally:
            if stop_ev.is_set():
                try:
                    repair_orphaned_tool_calls(enabled_tools, config)
                except Exception:
                    pass
            gen.q.put(None)

    threading.Thread(target=_sync_resume, daemon=True).start()

    asyncio.create_task(consume_generation(gen, state, p, cb))
    cb.rebuild_thread_list()


# ══════════════════════════════════════════════════════════════════════
# INTERRUPT DIALOG
# ══════════════════════════════════════════════════════════════════════

def build_interrupt_dialog(
    state: AppState,
    p: P,
    cb: _Callbacks,
) -> None:
    """Create the interrupt dialog and its show/close helpers.

    Attaches ``p.interrupt_dlg`` and returns the ``show_interrupt`` function
    for use as a callback.
    """
    p.interrupt_dlg = ui.dialog().props("persistent")

    def show_interrupt(data) -> None:
        p.interrupt_dlg.clear()
        items = data if isinstance(data, list) else [data]
        plural = len(items) > 1
        with p.interrupt_dlg, ui.card().classes("q-pa-none").style(
            "width: 520px; max-width: 90vw; border-radius: 16px; overflow: hidden;"
            "background: #1a1a2e; border: 1px solid #2a2a4a;"
        ):
            with ui.row().classes("w-full items-center q-pa-md").style(
                "background: linear-gradient(135deg, #2d1b00 0%, #1a1a2e 100%);"
                "border-bottom: 1px solid #3d2e00;"
            ):
                ui.icon("warning_amber", size="28px", color="amber")
                title = f"Confirm {len(items)} Actions" if plural else "Confirmation Required"
                ui.label(title).style(
                    "font-size: 1.15rem; font-weight: 700; color: #f0c040; margin-left: 8px;"
                )
            with ui.column().classes("w-full q-pa-lg"):
                subtitle = (
                    "The agent wants to perform the following actions:"
                    if plural else
                    "The agent wants to perform the following action:"
                )
                ui.label(subtitle).style(
                    "font-size: 0.85rem; color: #8888aa; margin-bottom: 8px;"
                )
                with ui.element("div").style(
                    "background: #12121e; border: 1px solid #2a2a4a; border-radius: 10px;"
                    "padding: 14px 16px; max-height: 260px; overflow-y: auto;"
                    "font-size: 0.9rem; color: #d0d0e0; line-height: 1.6;"
                    "word-wrap: break-word; white-space: pre-wrap;"
                ):
                    for i, item in enumerate(items):
                        desc = item.get("description", "Unknown action") if isinstance(item, dict) else str(item)
                        if plural:
                            ui.markdown(f"**{i + 1}.** {desc}", extras=['code-friendly', 'fenced-code-blocks', 'tables'])
                        else:
                            ui.markdown(desc, extras=['code-friendly', 'fenced-code-blocks', 'tables'])
            btn_label = f"Approve All ({len(items)})" if plural else "Approve"
            with ui.row().classes("w-full justify-end q-pa-md gap-3").style(
                "border-top: 1px solid #2a2a4a;"
            ):
                ui.button("Deny", on_click=lambda: _close_interrupt(False)).props(
                    "flat no-caps"
                ).style(
                    "color: #ff6b6b; font-weight: 600; font-size: 0.9rem;"
                    "padding: 8px 24px; border-radius: 8px;"
                )
                ui.button(btn_label, on_click=lambda: _close_interrupt(True)).props(
                    "unelevated no-caps"
                ).style(
                    "background: #2d8a4e; color: white; font-weight: 600;"
                    "font-size: 0.9rem; padding: 8px 28px; border-radius: 8px;"
                )
        p.interrupt_dlg.open()

    def _close_interrupt(approved: bool) -> None:
        p.interrupt_dlg.close()
        asyncio.create_task(resume_after_interrupt(approved, state=state, p=p, cb=cb))

    return show_interrupt  # type: ignore[return-value]


# ══════════════════════════════════════════════════════════════════════
# HELPER – assistant placeholder
# ══════════════════════════════════════════════════════════════════════

def _build_assistant_placeholder(gen: GenerationState, p: P) -> None:
    """Build the streaming assistant message placeholder in the chat."""
    with p.chat_container:
        with ui.element("div").classes("thoth-msg-row"):
            ui.html(
                '<div class="thoth-avatar thoth-avatar-bot">\U00013041</div>',
                sanitize=False,
            )
            with ui.column().classes("thoth-msg-body gap-1") as _wrapper:
                ui.html(
                    '<div class="thoth-msg-header">'
                    '<span class="thoth-msg-name">Thoth</span>'
                    f'<span class="thoth-msg-stamp">{datetime.now().strftime("%H:%M")}</span>'
                    '</div>',
                    sanitize=False,
                )
                gen.tool_col = ui.column().classes("w-full gap-1")
                gen.thinking_label = ui.html(
                    '<span class="thoth-typing" style="font-size:0.9rem; opacity:0.6;">'
                    'Thoth is thinking<span class="dots">'
                    '<span>.</span><span>.</span><span>.</span></span></span>',
                    sanitize=False,
                )
                gen.assistant_md = ui.markdown(
                    "",
                    extras=['code-friendly', 'fenced-code-blocks', 'tables'],
                ).classes("thoth-msg w-full")
                gen.assistant_md.set_visibility(False)
                gen.wrapper = _wrapper
