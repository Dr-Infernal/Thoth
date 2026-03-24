"""
Thoth – Telegram Channel Adapter
==================================
Long-polling Telegram bot that bridges messages to the Thoth agent.

Setup:
    1. Message @BotFather on Telegram → /newbot → copy the **Bot Token**
    2. Message @userinfobot (or send /start to your bot, check logs)
       to get your **Telegram User ID**
    3. Enter both in Settings → Channels

Required keys (stored via api_keys):
    TELEGRAM_BOT_TOKEN   – Bot token from @BotFather
    TELEGRAM_USER_ID     – Your numeric Telegram user ID (access control)
"""

from __future__ import annotations

import asyncio
import logging
import os
import re
import threading
from typing import Any

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, BotCommand
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
    ContextTypes,
)

import agent as agent_mod
from threads import _save_thread_meta, _list_threads
from tools import registry as tool_registry

log = logging.getLogger("thoth.telegram")

# ──────────────────────────────────────────────────────────────────────
# Constants
# ──────────────────────────────────────────────────────────────────────
MAX_TG_MESSAGE_LEN = 4096  # Telegram text message character limit

# Bot commands registered with BotFather
BOT_COMMANDS = [
    BotCommand("help", "Show available commands"),
    BotCommand("newthread", "Start a new conversation"),
    BotCommand("model", "Switch model (cloud/local)"),
    BotCommand("tools", "List enabled tools"),
    BotCommand("status", "Check bot status"),
]

# ──────────────────────────────────────────────────────────────────────
# Module-level state
# ──────────────────────────────────────────────────────────────────────
_app: Application | None = None         # Telegram Application instance
_running = False                        # Whether the polling loop is active
_bot_loop: asyncio.AbstractEventLoop | None = None  # Loop the bot was started on
_pending_interrupts: dict[int, dict] = {}  # {chat_id: interrupt_data}


# ──────────────────────────────────────────────────────────────────────
# Helpers — credentials
# ──────────────────────────────────────────────────────────────────────
def _get_bot_token() -> str:
    return os.environ.get("TELEGRAM_BOT_TOKEN", "")


def _get_allowed_user_id() -> int | None:
    """Return the authorised Telegram user ID, or None if not set."""
    raw = os.environ.get("TELEGRAM_USER_ID", "")
    if raw.strip().isdigit():
        return int(raw.strip())
    return None


def is_configured() -> bool:
    """Return True if bot token and user ID are both set."""
    return bool(_get_bot_token() and _get_allowed_user_id() is not None)


def is_running() -> bool:
    """Return True if the polling loop is currently active."""
    return _running


# ──────────────────────────────────────────────────────────────────────
# Access control
# ──────────────────────────────────────────────────────────────────────
def _is_authorised(update: Update) -> bool:
    """Check whether the message sender is the authorised user."""
    allowed = _get_allowed_user_id()
    if allowed is None:
        return False
    user_id = update.effective_user.id if update.effective_user else None
    return user_id == allowed


# ──────────────────────────────────────────────────────────────────────
# Thread management
# ──────────────────────────────────────────────────────────────────────
def _get_or_create_thread(chat_id: int) -> dict:
    """Get or create a LangGraph thread for a Telegram chat."""
    thread_id = f"tg_{chat_id}"

    existing = _list_threads()
    for tid, name, _, _, *rest in existing:
        if tid == thread_id:
            _save_thread_meta(tid, name)  # bump updated_at
            mo = rest[0] if rest else ""
            cfg = {"configurable": {"thread_id": tid}}
            if mo:
                cfg["configurable"]["model_override"] = mo
            return cfg

    name = f"✈️ Telegram – {chat_id}"
    _save_thread_meta(thread_id, name)
    return {"configurable": {"thread_id": thread_id}}


def _new_thread(chat_id: int) -> dict:
    """Force-create a brand-new thread for the given chat."""
    import uuid
    suffix = uuid.uuid4().hex[:6]
    thread_id = f"tg_{chat_id}_{suffix}"
    name = f"✈️ Telegram – {chat_id} ({suffix})"
    _save_thread_meta(thread_id, name)
    return {"configurable": {"thread_id": thread_id}}


# ──────────────────────────────────────────────────────────────────────
# Agent invocation (synchronous — runs in executor)
# ──────────────────────────────────────────────────────────────────────
def _grab_vision_capture() -> bytes | None:
    """Return the last captured image from the vision service, if any."""
    try:
        from tools.vision_tool import _get_vision_service
        svc = _get_vision_service()
        if svc and svc.last_capture:
            img = svc.last_capture
            svc.last_capture = None
            return img
    except Exception:
        pass
    return None


def _run_agent_sync(user_text: str, config: dict) -> tuple[str, dict | None, bytes | None]:
    """Run the agent synchronously, collecting the full response.

    Returns (answer_text, interrupt_data_or_None, captured_image_or_None).
    """
    enabled = [t.name for t in tool_registry.get_enabled_tools()]
    full_answer: list[str] = []
    tool_reports: list[str] = []
    interrupt_data: dict | None = None
    used_vision = False

    for event_type, payload in agent_mod.stream_agent(user_text, enabled, config):
        if event_type == "token":
            full_answer.append(payload)
        elif event_type == "tool_call":
            tool_reports.append(f"🔧 Using {payload}…")
        elif event_type == "tool_done":
            name = payload['name'] if isinstance(payload, dict) else payload
            tool_reports.append(f"✅ {name} done")
            if name in ("analyze_image", "👁️ Vision"):
                used_vision = True
        elif event_type == "interrupt":
            interrupt_data = payload
        elif event_type == "error":
            full_answer.append(f"⚠️ Error: {payload}")
        elif event_type == "done":
            if payload and not full_answer:
                full_answer.append(payload)

    answer = "".join(full_answer)
    if tool_reports and answer:
        answer = "\n".join(tool_reports) + "\n\n" + answer
    elif tool_reports:
        answer = "\n".join(tool_reports)

    captured = _grab_vision_capture() if used_vision else None
    return answer or "_(No response)_", interrupt_data, captured


def _resume_agent_sync(config: dict, approved: bool,
                       *, interrupt_ids: list[str] | None = None) -> tuple[str, dict | None, bytes | None]:
    """Resume a paused agent after interrupt approval/denial."""
    enabled = [t.name for t in tool_registry.get_enabled_tools()]
    full_answer: list[str] = []
    tool_reports: list[str] = []
    interrupt_data: dict | None = None
    used_vision = False

    for event_type, payload in agent_mod.resume_stream_agent(
        enabled, config, approved, interrupt_ids=interrupt_ids
    ):
        if event_type == "token":
            full_answer.append(payload)
        elif event_type == "tool_call":
            tool_reports.append(f"🔧 Using {payload}…")
        elif event_type == "tool_done":
            name = payload['name'] if isinstance(payload, dict) else payload
            tool_reports.append(f"✅ {name} done")
            if name in ("analyze_image", "👁️ Vision"):
                used_vision = True
        elif event_type == "interrupt":
            interrupt_data = payload
        elif event_type == "error":
            full_answer.append(f"⚠️ Error: {payload}")
        elif event_type == "done":
            if payload and not full_answer:
                full_answer.append(payload)

    answer = "".join(full_answer)
    if tool_reports and answer:
        answer = "\n".join(tool_reports) + "\n\n" + answer
    elif tool_reports:
        answer = "\n".join(tool_reports)

    captured = _grab_vision_capture() if used_vision else None
    return answer or "_(No response)_", interrupt_data, captured


# ──────────────────────────────────────────────────────────────────────
# Message splitting
# ──────────────────────────────────────────────────────────────────────
def _split_message(text: str, max_len: int = MAX_TG_MESSAGE_LEN) -> list[str]:
    """Split long text at paragraph or line boundaries."""
    if len(text) <= max_len:
        return [text]

    chunks: list[str] = []
    remaining = text

    while remaining:
        if len(remaining) <= max_len:
            chunks.append(remaining)
            break

        break_at = max_len
        para = remaining.rfind("\n\n", 0, max_len)
        if para > max_len // 2:
            break_at = para + 2
        else:
            line = remaining.rfind("\n", 0, max_len)
            if line > max_len // 2:
                break_at = line + 1
            else:
                space = remaining.rfind(" ", 0, max_len)
                if space > max_len // 2:
                    break_at = space + 1

        chunks.append(remaining[:break_at])
        remaining = remaining[break_at:]

    return chunks


# ──────────────────────────────────────────────────────────────────────
# Markdown → Telegram HTML converter
# ──────────────────────────────────────────────────────────────────────
def _md_to_html(text: str) -> str:
    """Convert common markdown to Telegram-compatible HTML.

    Handles: **bold**, *italic*, `code`, ```code blocks```,
    # headings → bold, and escapes <>&.
    """
    # Escape HTML entities first
    text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    # Fenced code blocks (``` ... ```)
    text = re.sub(r"```(?:\w*\n)?([\s\S]*?)```", r"<pre>\1</pre>", text)
    # Inline code (`...`)
    text = re.sub(r"`([^`]+)`", r"<code>\1</code>", text)
    # Bold (**...**)
    text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
    # Italic (*...*) — but not inside <b> tags
    text = re.sub(r"(?<!\w)\*([^*]+?)\*(?!\w)", r"<i>\1</i>", text)
    # Headings (# ... at start of line) → bold
    text = re.sub(r"^#{1,6}\s+(.+)$", r"<b>\1</b>", text, flags=re.MULTILINE)
    return text


def _escape_html(text: str) -> str:
    """Escape only the characters required by Telegram HTML."""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


# ──────────────────────────────────────────────────────────────────────
# Interrupt formatting
# ──────────────────────────────────────────────────────────────────────
def _format_interrupt(data) -> str:
    """Format interrupt data (single dict or list of dicts) as HTML."""
    items = data if isinstance(data, list) else [data]
    parts: list[str] = []

    for item in items:
        if not isinstance(item, dict):
            parts.append(_escape_html(str(item)))
            continue
        tool_name = item.get("tool", item.get("name", "Unknown tool"))
        desc = item.get("description", "")
        args = item.get("args", {})

        parts.append(f"⚠️ <b>{_escape_html(tool_name)}</b> needs your approval:")
        if desc:
            parts.append(f"<i>{_escape_html(desc)}</i>")
        elif args:
            for k, v in args.items():
                parts.append(f"• <b>{_escape_html(str(k))}</b>: {_escape_html(str(v))}")

    return "\n".join(parts)


def _extract_interrupt_ids(data) -> list[str] | None:
    """Extract __interrupt_id values from interrupt data for multi-interrupt resume."""
    items = data if isinstance(data, list) else [data]
    ids = [item.get("__interrupt_id") for item in items
           if isinstance(item, dict) and item.get("__interrupt_id")]
    return ids if len(ids) > 1 else None


# ──────────────────────────────────────────────────────────────────────
# Telegram handlers
# ──────────────────────────────────────────────────────────────────────
async def _cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /start command."""
    if not _is_authorised(update):
        await update.message.reply_text(
            f"⛔ Unauthorised. Your user ID is {update.effective_user.id}. "
            "Add this ID in Thoth → Settings → Channels to authorise."
        )
        return
    await _send_html(
        update.message,
        "𓁟 <b>Thoth</b> is connected!\n\n"
        "Send me any message and I'll respond using your configured agent.\n\n"
        "Commands:\n"
        "/newthread — Start a fresh conversation\n"
        "/model — Switch model (cloud/local)\n"
        "/tools — List enabled tools\n"
        "/status — Check connection status\n"
        "/help — Show this message",
    )


async def _cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /help command."""
    if not _is_authorised(update):
        return
    await _cmd_start(update, context)


async def _cmd_newthread(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /newthread — start a fresh conversation."""
    if not _is_authorised(update):
        return
    chat_id = update.effective_chat.id
    config = _new_thread(chat_id)
    # Store the new thread config so subsequent messages use it
    context.chat_data["thread_config"] = config
    # Clear any pending interrupts
    _pending_interrupts.pop(chat_id, None)
    await update.message.reply_text("🆕 Started a new conversation thread.")


async def _cmd_model(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /model — switch the model for this thread."""
    if not _is_authorised(update):
        return

    from models import (
        is_cloud_model, is_cloud_available, list_starred_cloud_models,
        get_current_model, get_cloud_provider,
    )
    from threads import _set_thread_model_override

    args = (update.message.text or "").split(maxsplit=1)
    if len(args) < 2:
        # Show current model + list available starred cloud models
        config = context.chat_data.get("thread_config") or {}
        current_ov = (config.get("configurable") or {}).get("model_override", "")
        _def = get_current_model()
        if current_ov:
            _prov = get_cloud_provider(current_ov)
            _tag = "☁️" if _prov else "🖥️"
            current_display = f"{_tag} {current_ov}"
        else:
            _prov = get_cloud_provider(_def)
            _tag = "☁️" if _prov else "🖥️"
            current_display = f"{_tag} {_def} (default)"
        lines = [f"<b>Current model:</b> {_escape_html(current_display)}\n"]
        starred = list_starred_cloud_models()
        if starred:
            lines.append("<b>Starred cloud models:</b>")
            for cid in starred:
                lines.append(f"• <code>{cid}</code>")
            lines.append("\nUsage: <code>/model gpt-4o</code>")
            lines.append("Reset to default: <code>/model default</code>")
        elif is_cloud_available():
            lines.append("No starred cloud models. Star models in Thoth → Settings → Cloud.")
        else:
            lines.append("⚠️ No cloud API keys configured.\nSet them in Thoth → Settings → Cloud.")
        await _send_html(update.message, "\n".join(lines))
        return

    model_id = args[1].strip()

    if model_id.lower() == "default":
        # Reset to global default
        config = context.chat_data.get("thread_config")
        if config:
            tid = (config.get("configurable") or {}).get("thread_id", "")
            config["configurable"]["model_override"] = ""
            _set_thread_model_override(tid, "")
            context.chat_data["thread_config"] = config
        await update.message.reply_text(f"✅ Switched to default: {get_current_model()}")
        return

    if not is_cloud_model(model_id):
        await update.message.reply_text(
            f"⚠️ Unknown cloud model: {model_id}\n"
            "Use /model to see available models."
        )
        return

    if not is_cloud_available():
        await update.message.reply_text("⚠️ No cloud API keys configured.")
        return

    # Set the model override
    config = context.chat_data.get("thread_config")
    if config is None:
        chat_id = update.effective_chat.id
        config = _get_or_create_thread(chat_id)
    tid = (config.get("configurable") or {}).get("thread_id", "")
    config["configurable"]["model_override"] = model_id
    _set_thread_model_override(tid, model_id)
    context.chat_data["thread_config"] = config

    await update.message.reply_text(f"☁️ Switched to {model_id}")


async def _cmd_tools(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /tools — list enabled tools."""
    if not _is_authorised(update):
        return
    enabled = tool_registry.get_enabled_tools()
    if not enabled:
        await update.message.reply_text("No tools are currently enabled.")
        return
    lines = ["🔧 <b>Enabled tools:</b>\n"]
    for t in enabled:
        lines.append(f"• {_escape_html(t.name)}")
    await _send_html(update.message, "\n".join(lines))


async def _cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /status — show connection status."""
    if not _is_authorised(update):
        return
    enabled_count = len(tool_registry.get_enabled_tools())
    await update.message.reply_text(
        f"✅ Thoth Telegram bot is running.\n"
        f"🔧 {enabled_count} tools enabled.\n"
        f"👤 Authorised user: {_get_allowed_user_id()}"
    )


async def _send_html(target, text: str, **kwargs) -> None:
    """Send a message as HTML, falling back to plain text on parse errors."""
    try:
        await target.reply_text(text, parse_mode="HTML", **kwargs)
    except Exception:
        # Strip HTML tags and send as plain text
        plain = re.sub(r"<[^>]+>", "", text).replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
        await target.reply_text(plain, **kwargs)


async def _send_html_msg(chat, text: str, **kwargs) -> None:
    """Send a message via chat.send_message as HTML with plain-text fallback."""
    try:
        await chat.send_message(text, parse_mode="HTML", **kwargs)
    except Exception:
        plain = re.sub(r"<[^>]+>", "", text).replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
        await chat.send_message(plain, **kwargs)


_THREAD_CORRUPT_PATTERNS = (
    "tool call.*without.*result",
    "tool_calls.*without.*tool_results",
    "tool_calls that do not have a corresponding",
    "tool_call_ids did not have response",
    "must be followed by tool messages",
    "expected.*tool.*message",
)


def _is_corrupt_thread_error(exc: Exception) -> bool:
    """Return True if the exception indicates a stuck/corrupt thread."""
    msg = str(exc).lower()
    return any(re.search(p, msg) for p in _THREAD_CORRUPT_PATTERNS)


async def _handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle incoming text messages — route to agent."""
    if not _is_authorised(update):
        await update.message.reply_text(
            f"⛔ Unauthorised. Your user ID is {update.effective_user.id}."
        )
        return

    chat_id = update.effective_chat.id
    text = update.message.text.strip()
    if not text:
        return

    # Block new messages while an interrupt is pending
    if chat_id in _pending_interrupts:
        await update.message.reply_text(
            "⏸️ There's a pending approval — please tap ✅ Approve or ❌ Deny first."
        )
        return

    # Get or create thread config (persisted in chat_data)
    config = context.chat_data.get("thread_config")
    if config is None:
        config = _get_or_create_thread(chat_id)
        context.chat_data["thread_config"] = config

    # Send typing indicator
    await update.effective_chat.send_action("typing")

    # Run agent in executor (blocking call)
    loop = asyncio.get_event_loop()
    try:
        answer, interrupt_data, captured_image = await loop.run_in_executor(
            None, _run_agent_sync, text, config
        )
    except Exception as exc:
        log.error("Agent error for chat %s: %s", chat_id, exc)
        # If thread is corrupt (stuck tool call), repair and retry
        if _is_corrupt_thread_error(exc):
            try:
                from agent import repair_orphaned_tool_calls
                await loop.run_in_executor(
                    None, repair_orphaned_tool_calls, None, config
                )
                log.info("Repaired orphaned tool calls for chat %s, retrying", chat_id)
                answer, interrupt_data, captured_image = await loop.run_in_executor(
                    None, _run_agent_sync, text, config
                )
            except Exception as retry_exc:
                log.error("Retry after repair failed for chat %s: %s", chat_id, retry_exc)
                # Repair failed — fall back to a fresh thread
                config = _new_thread(chat_id)
                context.chat_data["thread_config"] = config
                await update.message.reply_text(
                    "⚠️ The previous conversation had a stuck tool call and couldn't be repaired.\n"
                    "🆕 I've started a fresh thread — please resend your message."
                )
                return
        else:
            await update.message.reply_text(f"⚠️ Error: {exc}")
            return

    # Send captured vision image if available
    if captured_image:
        try:
            import io
            await update.effective_chat.send_photo(
                photo=io.BytesIO(captured_image), caption="📷 Captured image"
            )
        except Exception as exc:
            log.warning("Failed to send vision capture to Telegram: %s", exc)

    if interrupt_data:
        _pending_interrupts[chat_id] = {
            "data": interrupt_data,
            "config": config,
        }
        # Send interrupt with inline keyboard
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("✅ Approve", callback_data="interrupt_approve"),
                InlineKeyboardButton("❌ Deny", callback_data="interrupt_deny"),
            ]
        ])
        await _send_html(
            update.message,
            _format_interrupt(interrupt_data),
            reply_markup=keyboard,
        )
    else:
        # Send response as formatted HTML (split if needed)
        html = _md_to_html(answer)
        for chunk in _split_message(html):
            await _send_html(update.message, chunk)


async def _handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle inline keyboard button presses (interrupt approve/deny)."""
    query = update.callback_query
    await query.answer()  # Acknowledge the button press

    if not _is_authorised(update):
        return

    chat_id = update.effective_chat.id
    pending = _pending_interrupts.pop(chat_id, None)
    if pending is None:
        await query.edit_message_text("ℹ️ No pending approval to respond to.")
        return

    approved = query.data == "interrupt_approve"
    action = "Approved ✅" if approved else "Denied ❌"
    await query.edit_message_text(f"{action} — processing…")

    config = pending["config"]
    interrupt_ids = _extract_interrupt_ids(pending["data"])

    # Send typing indicator
    await update.effective_chat.send_action("typing")

    loop = asyncio.get_event_loop()
    try:
        answer, new_interrupt, captured_image = await loop.run_in_executor(
            None, lambda: _resume_agent_sync(config, approved, interrupt_ids=interrupt_ids),
        )
    except Exception as exc:
        log.error("Agent resume error: %s", exc)
        if _is_corrupt_thread_error(exc):
            new_config = _new_thread(chat_id)
            context.chat_data["thread_config"] = new_config
            await update.effective_chat.send_message(
                "⚠️ The conversation had a stuck tool call.\n"
                "🆕 Started a fresh thread — please resend your message."
            )
        else:
            await update.effective_chat.send_message(f"⚠️ Error: {exc}")
        return

    # Send captured vision image if available
    if captured_image:
        try:
            import io
            await update.effective_chat.send_photo(
                photo=io.BytesIO(captured_image), caption="📷 Captured image"
            )
        except Exception as exc:
            log.warning("Failed to send vision capture to Telegram: %s", exc)

    if new_interrupt:
        _pending_interrupts[chat_id] = {
            "data": new_interrupt,
            "config": config,
        }
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("✅ Approve", callback_data="interrupt_approve"),
                InlineKeyboardButton("❌ Deny", callback_data="interrupt_deny"),
            ]
        ])
        await _send_html_msg(
            update.effective_chat,
            _format_interrupt(new_interrupt),
            reply_markup=keyboard,
        )
    else:
        html = _md_to_html(answer)
        for chunk in _split_message(html):
            await _send_html_msg(update.effective_chat, chunk)


# ──────────────────────────────────────────────────────────────────────
# Lifecycle: start / stop the polling bot
# ──────────────────────────────────────────────────────────────────────
async def start_bot() -> bool:
    """Initialise and start the Telegram bot (long polling).

    Returns True on success, False if not configured or already running.
    """
    global _app, _running, _bot_loop

    if _running:
        log.info("Telegram bot is already running")
        return True

    if not is_configured():
        log.warning("Telegram bot not configured — skipping start")
        return False

    token = _get_bot_token()

    _app = Application.builder().token(token).build()

    # Register handlers
    _app.add_handler(CommandHandler("start", _cmd_start))
    _app.add_handler(CommandHandler("help", _cmd_help))
    _app.add_handler(CommandHandler("newthread", _cmd_newthread))
    _app.add_handler(CommandHandler("model", _cmd_model))
    _app.add_handler(CommandHandler("tools", _cmd_tools))
    _app.add_handler(CommandHandler("status", _cmd_status))
    _app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, _handle_message))
    _app.add_handler(CallbackQueryHandler(_handle_callback))

    # Register commands with BotFather for autocomplete
    try:
        await _app.bot.set_my_commands(BOT_COMMANDS)
    except Exception as exc:
        log.warning("Could not register bot commands: %s", exc)

    # Initialise and start polling
    await _app.initialize()
    await _app.start()
    await _app.updater.start_polling(drop_pending_updates=True)

    _bot_loop = asyncio.get_running_loop()
    _running = True
    log.info("Telegram bot started (polling)")
    return True


async def stop_bot() -> None:
    """Stop the Telegram bot gracefully."""
    global _app, _running, _bot_loop

    if not _running or _app is None:
        return

    try:
        await _app.updater.stop()
        await _app.stop()
        await _app.shutdown()
    except Exception as exc:
        log.warning("Error stopping Telegram bot: %s", exc)
    finally:
        _running = False
        _app = None
        _bot_loop = None
        log.info("Telegram bot stopped")


# ──────────────────────────────────────────────────────────────────────
# Outbound messages (called by the task engine)
# ──────────────────────────────────────────────────────────────────────
def send_outbound(chat_id: int, text: str) -> None:
    """Send a message to a Telegram chat from *outside* the handler context.

    Called synchronously by ``tasks._deliver_to_channel()``.
    The bot's httpx HTTP client is bound to the loop it was created on,
    so we schedule the send on that same loop via *run_coroutine_threadsafe*.
    """
    if not _running or _app is None:
        raise RuntimeError("Telegram bot is not running — cannot deliver message")
    if _bot_loop is None or not _bot_loop.is_running():
        raise RuntimeError("Telegram bot event loop is not available")

    async def _send():
        html = _md_to_html(text)
        for chunk in _split_message(html):
            try:
                await _app.bot.send_message(chat_id=chat_id, text=chunk, parse_mode="HTML")
            except Exception:
                plain = re.sub(r"<[^>]+>", "", chunk).replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
                await _app.bot.send_message(chat_id=chat_id, text=plain)

    future = asyncio.run_coroutine_threadsafe(_send(), _bot_loop)
    future.result(timeout=30)


def send_photo(chat_id: int, file_path: str, *, caption: str | None = None) -> None:
    """Send a photo to a Telegram chat from *outside* the handler context.

    Parameters
    ----------
    chat_id : int
        Telegram chat / user ID.
    file_path : str
        Absolute path to a local image file (PNG, JPG, etc.).
    caption : str, optional
        Optional caption text displayed below the photo.
    """
    if not _running or _app is None:
        raise RuntimeError("Telegram bot is not running — cannot send photo")
    if _bot_loop is None or not _bot_loop.is_running():
        raise RuntimeError("Telegram bot event loop is not available")

    async def _send():
        with open(file_path, "rb") as f:
            await _app.bot.send_photo(chat_id=chat_id, photo=f, caption=caption)

    future = asyncio.run_coroutine_threadsafe(_send(), _bot_loop)
    future.result(timeout=60)


def send_document(chat_id: int, file_path: str, *, caption: str | None = None) -> None:
    """Send a document/file to a Telegram chat from *outside* the handler context.

    Parameters
    ----------
    chat_id : int
        Telegram chat / user ID.
    file_path : str
        Absolute path to the file to send.
    caption : str, optional
        Optional caption text displayed with the document.
    """
    if not _running or _app is None:
        raise RuntimeError("Telegram bot is not running — cannot send document")
    if _bot_loop is None or not _bot_loop.is_running():
        raise RuntimeError("Telegram bot event loop is not available")

    import os as _os
    filename = _os.path.basename(file_path)

    async def _send():
        with open(file_path, "rb") as f:
            await _app.bot.send_document(
                chat_id=chat_id, document=f, filename=filename, caption=caption,
            )

    future = asyncio.run_coroutine_threadsafe(_send(), _bot_loop)
    future.result(timeout=60)
