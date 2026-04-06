"""
Thoth – Channel Base Class
============================
Abstract base for all messaging-channel adapters.

Every channel (Telegram, Slack, Discord, …) subclasses ``Channel`` and
declares its ``capabilities`` and ``config_fields``.  The registry and
settings UI read those declarations to auto-generate tooling, UI, and
task-delivery routing.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


# ── Capability flags ─────────────────────────────────────────────────

@dataclass
class ChannelCapabilities:
    """Feature flags describing what a channel adapter supports.

    Each flag is queried by the tool factory (outbound) and the media
    pipeline (inbound) to decide which features to wire up.
    """
    photo_in:       bool = False    # receive photos from user
    voice_in:       bool = False    # receive voice notes from user
    document_in:    bool = False    # receive files from user
    photo_out:      bool = False    # send photos to user
    document_out:   bool = False    # send files to user
    buttons:        bool = False    # interactive approval buttons
    streaming:      bool = False    # edit message as tokens arrive
    typing:         bool = False    # typing / "processing" indicator
    reactions:      bool = False    # emoji reactions for status
    slash_commands:  bool = False    # native slash / bot commands


# ── Config-field descriptor ──────────────────────────────────────────

@dataclass
class ConfigField:
    """Describes one user-configurable field rendered by the settings UI.

    Parameters
    ----------
    key : str
        Internal key (``"bot_token"``).
    label : str
        Human-readable label (``"Bot Token"``).
    field_type : str
        Widget type: ``"text"`` | ``"password"`` | ``"number"`` | ``"slider"``.
    storage : str
        Where the value lives: ``"env"`` → ``api_keys`` env vars,
        ``"config"`` → ``channels_config.json``.
    env_key : str | None
        Environment variable name when *storage* is ``"env"``.
    default : Any
        Default value used when nothing has been persisted yet.
    help_text : str
        Tooltip / description shown next to the field.
    slider_min : int
        Minimum for ``"slider"`` type.
    slider_max : int
        Maximum for ``"slider"`` type.
    slider_step : int
        Step for ``"slider"`` type.
    """
    key:         str
    label:       str
    field_type:  str            = "text"
    storage:     str            = "env"
    env_key:     str | None     = None
    default:     Any            = ""
    help_text:   str            = ""
    slider_min:  int            = 0
    slider_max:  int            = 100
    slider_step: int            = 1


# ── Channel ABC ──────────────────────────────────────────────────────

class Channel(ABC):
    """Abstract base class for a Thoth messaging-channel adapter.

    Subclasses **must** implement the abstract methods/properties.
    Optional outbound helpers (``send_photo``, ``send_document``, …) have
    default ``NotImplementedError`` stubs — override only those that
    the channel actually supports.
    """

    # ── Identity (must override) ─────────────────────────────────────

    @property
    @abstractmethod
    def name(self) -> str:
        """Internal unique identifier, e.g. ``"telegram"``."""
        ...

    @property
    @abstractmethod
    def display_name(self) -> str:
        """Human-readable label, e.g. ``"Telegram"``."""
        ...

    @property
    def icon(self) -> str:
        """Material-icon name used in the settings tab, e.g. ``"send"``."""
        return "chat"

    @property
    def setup_guide(self) -> str:
        """Markdown string rendered as a collapsible setup guide in settings."""
        return ""

    # ── Capabilities & config ────────────────────────────────────────

    @property
    def capabilities(self) -> ChannelCapabilities:
        """Return a ``ChannelCapabilities`` instance."""
        return ChannelCapabilities()

    @property
    def config_fields(self) -> list[ConfigField]:
        """Ordered list of user-configurable fields for settings UI."""
        return []

    # ── Lifecycle ────────────────────────────────────────────────────

    @abstractmethod
    async def start(self) -> bool:
        """Start the channel adapter.  Return ``True`` on success."""
        ...

    @abstractmethod
    async def stop(self) -> None:
        """Stop the channel adapter gracefully."""
        ...

    @abstractmethod
    def is_configured(self) -> bool:
        """Return ``True`` if all required credentials/config are present."""
        ...

    @abstractmethod
    def is_running(self) -> bool:
        """Return ``True`` if the adapter is actively listening."""
        ...

    # ── Outbound messaging ───────────────────────────────────────────

    @abstractmethod
    def send_message(self, target: str | int, text: str) -> None:
        """Send a text message.  Required for every channel."""
        ...

    def send_photo(self, target: str | int, file_path: str,
                   caption: str | None = None) -> None:
        """Send a photo.  Override if ``capabilities.photo_out`` is True."""
        raise NotImplementedError(f"{self.name} does not support send_photo")

    def send_document(self, target: str | int, file_path: str,
                      caption: str | None = None) -> None:
        """Send a document/file.  Override if ``capabilities.document_out``."""
        raise NotImplementedError(f"{self.name} does not support send_document")

    def send_approval_request(self, target: str | int,
                              interrupt_data: Any,
                              config: dict) -> None:
        """Send an approval prompt (buttons / interactive element)."""
        raise NotImplementedError(f"{self.name} does not support approval buttons")

    # ── Thread management ────────────────────────────────────────────

    def make_thread_id(self, external_id: str) -> str:
        """Derive a Thoth thread-id from a platform-specific ID.

        Default: ``f"{self.name}_{external_id}"``.
        """
        return f"{self.name}_{external_id}"

    # ── Extension hooks ──────────────────────────────────────────────

    def extra_tools(self) -> list:
        """Return additional LangChain tools beyond the auto-generated ones.

        Override to add channel-specific tools (e.g. thread replies).
        """
        return []

    def build_custom_ui(self, container) -> None:
        """Render additional custom widgets in the settings panel.

        Called *after* the template-generated config fields.
        """
        pass
