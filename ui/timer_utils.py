"""Safe wrapper around ``nicegui.ui.timer``.

Background timers scheduled against per-client UI state can outlive
the client that owns them (e.g. when a tab is closed, when NiceGUI
replaces a container during rebuild, or when a client socket drops).
When the callback next fires, NiceGUI raises errors such as
``RuntimeError: parent slot has been deleted`` or ``client ... is
deleted``.  These floods are benign but noisy and, under heavy load,
cause event-loop stalls.

``safe_timer`` wraps the callback so the first such error
deactivates the timer instead of re-raising on every tick.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Callable

from nicegui import ui


logger = logging.getLogger("thoth.ui.timer")


_BENIGN_MARKERS = (
    "parent slot has been deleted",
    "slot has been deleted",
    "client has been deleted",
    "client is deleted",
    "element has been deleted",
    "has been deleted",
)


def _is_benign_dead_ui_error(exc: BaseException) -> bool:
    msg = str(exc).lower()
    return any(marker in msg for marker in _BENIGN_MARKERS)


def safe_timer(
    interval: float,
    callback: Callable[..., Any],
    *,
    once: bool = False,
    active: bool = True,
) -> ui.timer:
    """Create a ``ui.timer`` whose callback self-deactivates when the
    owning UI is gone.

    Drop-in replacement for ``ui.timer(interval, callback, ...)``.
    For one-shot timers (``once=True``) the wrapper is unnecessary but
    still safe — NiceGUI fires them exactly once anyway.
    """

    timer_ref: dict[str, ui.timer | None] = {"t": None}

    def _deactivate() -> None:
        t = timer_ref.get("t")
        if t is None:
            return
        try:
            t.deactivate()
        except Exception:
            pass

    async def _async_wrapper() -> None:
        try:
            result = callback()
            if asyncio.iscoroutine(result):
                await result
        except Exception as exc:
            if _is_benign_dead_ui_error(exc):
                logger.debug(
                    "safe_timer: deactivating after dead-UI error: %s", exc
                )
                _deactivate()
            else:
                logger.exception("safe_timer callback raised")

    def _sync_wrapper() -> None:
        try:
            callback()
        except Exception as exc:
            if _is_benign_dead_ui_error(exc):
                logger.debug(
                    "safe_timer: deactivating after dead-UI error: %s", exc
                )
                _deactivate()
            else:
                logger.exception("safe_timer callback raised")

    wrapper = _async_wrapper if asyncio.iscoroutinefunction(callback) else _sync_wrapper
    t = ui.timer(interval, wrapper, once=once, active=active)
    timer_ref["t"] = t
    return t
