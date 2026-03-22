"""
Thoth – Telegram Tool
======================
Gives the agent the ability to send messages, photos, and documents
to the user's Telegram account during a conversation.

All sends go to the **configured TELEGRAM_USER_ID** — the same user
who set up the bot in Settings → Channels.  No chat-ID parameter is
exposed to the LLM; the bot is a personal-assistant channel, not a
broadcast system.

Sub-tools
---------
* **send_telegram_message** — send a text message
* **send_telegram_photo** — send a photo (local file path)
* **send_telegram_document** — send a document / file (local file path)
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Optional

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

from tools.base import BaseTool
from tools import registry

log = logging.getLogger("thoth.tools.telegram")

# All sub-tool names (all enabled whenever the tool toggle is on)
_ALL_OPS = ["send_telegram_message", "send_telegram_photo", "send_telegram_document"]


# ── Path resolution helper ───────────────────────────────────────────

def _resolve_file_path(file_path: str) -> str:
    """Resolve a potentially relative *file_path* to an absolute one.

    Search order:
    1. Already absolute and exists → use as-is
    2. Relative to filesystem tool's workspace_root
    3. Relative to tracker export directory (~/.thoth/tracker/exports/)
    4. Relative to cwd
    5. Nothing found → return original (caller reports the error)
    """
    p = Path(file_path)
    if p.is_absolute() and p.is_file():
        return str(p)

    # Try workspace root
    try:
        from tools import registry as _reg
        fs_tool = _reg.get_tool("filesystem")
        if fs_tool:
            ws_root = fs_tool.get_config("workspace_root", "")
            if ws_root:
                candidate = Path(ws_root) / p
                if candidate.is_file():
                    return str(candidate.resolve())
    except Exception:
        pass

    # Try tracker export directory
    try:
        _data_dir = Path(
            os.environ.get("THOTH_DATA_DIR", Path.home() / ".thoth")
        )
        tracker_exports = _data_dir / "tracker" / "exports"
        candidate = tracker_exports / p
        if candidate.is_file():
            return str(candidate.resolve())
    except Exception:
        pass

    # Try cwd
    candidate = Path.cwd() / p
    if candidate.is_file():
        return str(candidate.resolve())

    return file_path  # return original — let caller report error


# ── Pydantic input schemas ───────────────────────────────────────────

class _SendMessageInput(BaseModel):
    text: str = Field(description="The text message to send to the user via Telegram.")


class _SendPhotoInput(BaseModel):
    file_path: str = Field(description="Absolute path to the image file to send.")
    caption: Optional[str] = Field(
        default=None,
        description="Optional caption for the photo.",
    )


class _SendDocumentInput(BaseModel):
    file_path: str = Field(description="Absolute path to the file to send as a document.")
    caption: Optional[str] = Field(
        default=None,
        description="Optional caption for the document.",
    )


# ── Implementation functions ─────────────────────────────────────────

def _send_telegram_message(text: str) -> str:
    """Send a text message to the user via Telegram."""
    from channels.telegram import send_outbound, _get_allowed_user_id, is_running

    if not is_running():
        return "Error: Telegram bot is not running. Start it in Settings → Channels."

    user_id = _get_allowed_user_id()
    if user_id is None:
        return "Error: TELEGRAM_USER_ID is not configured. Set it in Settings → Channels."

    try:
        send_outbound(user_id, text)
        return f"Message sent to Telegram successfully ({len(text)} chars)."
    except Exception as exc:
        log.warning("send_telegram_message failed: %s", exc)
        return f"Error sending Telegram message: {exc}"


def _send_telegram_photo(file_path: str, caption: str | None = None) -> str:
    """Send a photo to the user via Telegram."""
    from channels.telegram import send_photo, _get_allowed_user_id, is_running

    if not is_running():
        return "Error: Telegram bot is not running. Start it in Settings → Channels."

    user_id = _get_allowed_user_id()
    if user_id is None:
        return "Error: TELEGRAM_USER_ID is not configured. Set it in Settings → Channels."

    resolved = _resolve_file_path(file_path)
    if not os.path.isfile(resolved):
        return f"Error: File not found: {file_path}"

    try:
        send_photo(user_id, resolved, caption=caption)
        basename = os.path.basename(resolved)
        return f"Photo '{basename}' sent to Telegram successfully."
    except Exception as exc:
        log.warning("send_telegram_photo failed: %s", exc)
        return f"Error sending Telegram photo: {exc}"


def _send_telegram_document(file_path: str, caption: str | None = None) -> str:
    """Send a document/file to the user via Telegram."""
    from channels.telegram import send_document, _get_allowed_user_id, is_running

    if not is_running():
        return "Error: Telegram bot is not running. Start it in Settings → Channels."

    user_id = _get_allowed_user_id()
    if user_id is None:
        return "Error: TELEGRAM_USER_ID is not configured. Set it in Settings → Channels."

    resolved = _resolve_file_path(file_path)
    if not os.path.isfile(resolved):
        return f"Error: File not found: {file_path}"

    try:
        send_document(user_id, resolved, caption=caption)
        basename = os.path.basename(resolved)
        return f"Document '{basename}' sent to Telegram successfully."
    except Exception as exc:
        log.warning("send_telegram_document failed: %s", exc)
        return f"Error sending Telegram document: {exc}"


# ── Tool class ───────────────────────────────────────────────────────

class TelegramTool(BaseTool):
    """Send messages, photos, and documents to the user via Telegram."""

    @property
    def name(self) -> str:
        return "telegram"

    @property
    def display_name(self) -> str:
        return "📱 Telegram"

    @property
    def description(self) -> str:
        return (
            "Send messages, photos, and documents to the user via Telegram. "
            "Use this when the user asks you to send something to their phone, "
            "push a notification, or forward a file via Telegram."
        )

    @property
    def enabled_by_default(self) -> bool:
        return False

    def as_langchain_tools(self) -> list:
        return [
            StructuredTool.from_function(
                func=_send_telegram_message,
                name="send_telegram_message",
                description=(
                    "Send a text message to the user via Telegram. "
                    "Use this to push information, summaries, reminders, "
                    "or any text content to the user's Telegram. "
                    "The message goes to the configured user automatically."
                ),
                args_schema=_SendMessageInput,
            ),
            StructuredTool.from_function(
                func=_send_telegram_photo,
                name="send_telegram_photo",
                description=(
                    "Send a photo/image to the user via Telegram. "
                    "Provide the absolute file path to a local image file "
                    "(PNG, JPG, etc.). Useful after creating a chart — "
                    "send the generated image directly to Telegram."
                ),
                args_schema=_SendPhotoInput,
            ),
            StructuredTool.from_function(
                func=_send_telegram_document,
                name="send_telegram_document",
                description=(
                    "Send a document/file to the user via Telegram. "
                    "Provide the absolute file path to any local file "
                    "(CSV, PDF, XLSX, etc.). Useful for sending exported "
                    "data, reports, or files the user requested."
                ),
                args_schema=_SendDocumentInput,
            ),
        ]

    def execute(self, query: str) -> str:
        return "Use send_telegram_message, send_telegram_photo, or send_telegram_document."


registry.register(TelegramTool())
