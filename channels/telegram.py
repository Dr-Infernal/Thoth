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
    for tid, name, _, _ in existing:
        if tid == thread_id:
            _save_thread_meta(tid, name)  # bump updated_at
            return {"configurable": {"thread_id": tid}}

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
def _run_agent_sync(user_text: str, config: dict) -> tuple[str, dict | None]:
    """Run the agent synchronously, collecting the full response.

    Returns (answer_text, interrupt_data_or_None).
    """
    enabled = [t.name for t in tool_registry.get_enabled_tools()]
    full_answer: list[str] = []
    tool_reports: list[str] = []
    interrupt_data: dict | None = None

    for event_type, payload in agent_mod.stream_agent(user_text, enabled, config):
        if event_type == "token":
            full_answer.append(payload)
        elif event_type == "tool_call":
            tool_reports.append(f"🔧 Using {payload}…")
        elif event_type == "tool_done":
            if isinstance(payload, dict):
                tool_reports.append(f"✅ {payload['name']} done")
            else:
                tool_reports.append(f"✅ {payload} done")
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

    return answer or "_(No response)_", interrupt_data


def _resume_agent_sync(config: dict, approved: bool) -> tuple[str, dict | None]:
    """Resume a paused agent after interrupt approval/denial."""
    enabled = [t.name for t in tool_registry.get_enabled_tools()]
    full_answer: list[str] = []
    tool_reports: list[str] = []
    interrupt_data: dict | None = None

    for event_type, payload in agent_mod.resume_stream_agent(enabled, config, approved):
        if event_type == "token":
            full_answer.append(payload)
        elif event_type == "tool_call":
            tool_reports.append(f"🔧 Using {payload}…")
        elif event_type == "tool_done":
            if isinstance(payload, dict):
                tool_reports.append(f"✅ {payload['name']} done")
            else:
                tool_reports.append(f"✅ {payload} done")
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

    return answer or "_(No response)_", interrupt_data


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
# Interrupt formatting
# ──────────────────────────────────────────────────────────────────────
def _format_interrupt(data: dict) -> str:
    """Format interrupt data into a readable Telegram message."""
    tool_name = data.get("tool", data.get("name", "Unknown tool"))
    reason = data.get("reason", "")
    args = data.get("args", {})

    parts = [f"⚠️ *{_escape_md(tool_name)}* needs your approval:\n"]
    if reason:
        parts.append(f"_{_escape_md(reason)}_\n")
    if args:
        for k, v in args.items():
            parts.append(f"• *{_escape_md(str(k))}*: {_escape_md(str(v))}")

    return "\n".join(parts)


def _escape_md(text: str) -> str:
    """Escape MarkdownV2 special characters."""
    special = r"_*[]()~`>#+-=|{}.!\\"
    result = []
    for ch in text:
        if ch in special:
            result.append(f"\\{ch}")
        else:
            result.append(ch)
    return "".join(result)


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
    await update.message.reply_text(
        "𓁟 *Thoth* is connected\\!\n\n"
        "Send me any message and I'll respond using your configured agent\\.\n\n"
        "Commands:\n"
        "/newthread — Start a fresh conversation\n"
        "/tools — List enabled tools\n"
        "/status — Check connection status\n"
        "/help — Show this message",
        parse_mode="MarkdownV2",
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


async def _cmd_tools(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /tools — list enabled tools."""
    if not _is_authorised(update):
        return
    enabled = tool_registry.get_enabled_tools()
    if not enabled:
        await update.message.reply_text("No tools are currently enabled.")
        return
    lines = ["🔧 *Enabled tools:*\n"]
    for t in enabled:
        desc = getattr(t, "description", "")[:60]
        lines.append(f"• {_escape_md(t.name)}")
    await update.message.reply_text("\n".join(lines), parse_mode="MarkdownV2")


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
        answer, interrupt_data = await loop.run_in_executor(
            None, _run_agent_sync, text, config
        )
    except Exception as exc:
        log.error("Agent error for chat %s: %s", chat_id, exc)
        await update.message.reply_text(f"⚠️ Error: {exc}")
        return

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
        await update.message.reply_text(
            _format_interrupt(interrupt_data),
            parse_mode="MarkdownV2",
            reply_markup=keyboard,
        )
    else:
        # Send response (split if needed)
        for chunk in _split_message(answer):
            await update.message.reply_text(chunk)


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

    # Send typing indicator
    await update.effective_chat.send_action("typing")

    loop = asyncio.get_event_loop()
    try:
        answer, new_interrupt = await loop.run_in_executor(
            None, _resume_agent_sync, config, approved
        )
    except Exception as exc:
        log.error("Agent resume error: %s", exc)
        await update.effective_chat.send_message(f"⚠️ Error: {exc}")
        return

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
        await update.effective_chat.send_message(
            _format_interrupt(new_interrupt),
            parse_mode="MarkdownV2",
            reply_markup=keyboard,
        )
    else:
        for chunk in _split_message(answer):
            await update.effective_chat.send_message(chunk)


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
        for chunk in _split_message(text):
            await _app.bot.send_message(chat_id=chat_id, text=chunk)

    future = asyncio.run_coroutine_threadsafe(_send(), _bot_loop)
    future.result(timeout=30)
