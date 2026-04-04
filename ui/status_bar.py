"""Thoth UI — status bar with avatar, health pills, and diagnosis button.

Replaces the old logo section on the home screen.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import pathlib
import time
from typing import Callable

from nicegui import run, ui

from ui.status_checks import CheckResult, run_all_checks, run_light_checks, HEAVY_CHECKS

logger = logging.getLogger(__name__)

_DATA_DIR = pathlib.Path(
    os.environ.get("THOTH_DATA_DIR", pathlib.Path.home() / ".thoth")
)
_USER_CONFIG_PATH = _DATA_DIR / "user_config.json"

# ═════════════════════════════════════════════════════════════════════════════
# AVATAR CONFIG
# ═════════════════════════════════════════════════════════════════════════════

_DEFAULT_EMOJI = "𓁟"
_DEFAULT_COLOR = "#FFD700"

_AVATAR_EMOJIS = [
    "𓁟", "🤖", "🧠", "🦊", "🐱", "🦉", "🐙", "🎭", "👾", "🌀",
    "💎", "🔮", "🪐", "⚡", "🌊", "🐉", "🦋", "🍀", "🎯", "🏔️",
    "🌸", "🦁", "🐺", "🐝", "🦅", "🎵", "🔥", "❄️", "☀️", "🌙",
]

_RING_COLORS = [
    "#FFD700", "#4caf50", "#2196f3", "#e91e63", "#9c27b0",
    "#ff5722", "#00bcd4", "#ff9800", "#8bc34a", "#607d8b",
    "#f44336", "#3f51b5", "#009688", "#cddc39", "#795548",
]


def _load_avatar_config() -> dict:
    """Load avatar preferences from user_config.json."""
    try:
        if _USER_CONFIG_PATH.exists():
            data = json.loads(_USER_CONFIG_PATH.read_text(encoding="utf-8"))
            return data.get("avatar", {})
    except (json.JSONDecodeError, OSError):
        pass
    return {}


def _save_avatar_config(avatar: dict) -> None:
    """Save avatar preferences to user_config.json."""
    try:
        _DATA_DIR.mkdir(parents=True, exist_ok=True)
        config = {}
        if _USER_CONFIG_PATH.exists():
            try:
                config = json.loads(_USER_CONFIG_PATH.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                pass
        config["avatar"] = avatar
        _USER_CONFIG_PATH.write_text(
            json.dumps(config, indent=2, ensure_ascii=False), encoding="utf-8"
        )
    except OSError as exc:
        logger.warning("Failed to save avatar config: %s", exc)


# ═════════════════════════════════════════════════════════════════════════════
# STATUS CACHE (module-level, avoids re-running heavy checks on every render)
# ═════════════════════════════════════════════════════════════════════════════

_status_cache: dict[str, CheckResult] = {}
_cache_time: float = 0.0
_CACHE_TTL = 300.0  # 5 minutes for heavy checks


def _get_cached_results() -> list[CheckResult]:
    """Return all check results, using cache for heavy checks."""
    global _status_cache, _cache_time

    now = time.time()
    results: list[CheckResult] = []

    # Always run light checks fresh (they're just reading booleans)
    for r in run_light_checks():
        _status_cache[r.name] = r

    # Heavy checks: use cache if fresh enough
    if now - _cache_time > _CACHE_TTL:
        for fn in HEAVY_CHECKS:
            try:
                r = fn()
                _status_cache[r.name] = r
            except Exception as exc:
                _status_cache[fn.__name__] = CheckResult(fn.__name__, "error", str(exc))
        _cache_time = now

    return list(_status_cache.values())


def _force_refresh() -> list[CheckResult]:
    """Force-refresh all checks (bypasses cache)."""
    global _status_cache, _cache_time
    all_results = run_all_checks()
    _status_cache = {r.name: r for r in all_results}
    _cache_time = time.time()
    return all_results


# ═════════════════════════════════════════════════════════════════════════════
# STATUS BAR UI
# ═════════════════════════════════════════════════════════════════════════════

# CSS for the animated avatar ring
_AVATAR_CSS = """
<style>
@keyframes thoth-avatar-pulse {
    0%   { box-shadow: 0 0 4px 1px var(--avatar-color); transform: rotate(0deg); }
    42%  { box-shadow: 0 0 4px 1px var(--avatar-color); transform: rotate(-1.2deg); }
    46%  { box-shadow: 0 0 20px 6px var(--avatar-color); transform: rotate(0.8deg); }
    52%  { box-shadow: 0 0 6px 2px var(--avatar-color); transform: rotate(-0.5deg); }
    56%  { box-shadow: 0 0 12px 3px var(--avatar-color); transform: rotate(0.3deg); }
    62%  { box-shadow: 0 0 4px 1px var(--avatar-color); transform: rotate(0deg); }
    100% { box-shadow: 0 0 4px 1px var(--avatar-color); transform: rotate(0.6deg); }
}
@keyframes thoth-ring-spin {
    0%   { transform: rotate(0deg); }
    100% { transform: rotate(360deg); }
}
@keyframes thoth-wave-scroll {
    0%   { transform: translateX(0) translateY(-50%); }
    100% { transform: translateX(-50%) translateY(-50%); }
}
.thoth-status-panel {
    background: rgba(30, 30, 30, 0.7);
    backdrop-filter: blur(12px);
    -webkit-backdrop-filter: blur(12px);
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 14px;
    padding: 0.55rem 0.9rem;
    margin: 0.4rem 0.3rem 0.15rem 0.3rem;
    position: relative;
    overflow: hidden;
}
.thoth-status-panel > * { position: relative; z-index: 1; }
.thoth-status-panel::before {
    content: "";
    position: absolute;
    top: 50%; left: 0;
    width: 200%; height: 140%;
    z-index: 0;
    opacity: 0.18;
    pointer-events: none;
    background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 600 100' preserveAspectRatio='none'%3E%3Cpath d='M0,50 L40,50 L50,50 L55,48 L60,55 L65,10 L70,90 L75,30 L80,50 L100,50 L140,50 L150,50 L155,48 L160,55 L165,10 L170,90 L175,30 L180,50 L200,50 L240,50 L250,50 L255,48 L260,55 L265,10 L270,90 L275,30 L280,50 L300,50 L340,50 L350,50 L355,48 L360,55 L365,10 L370,90 L375,30 L380,50 L400,50 L440,50 L450,50 L455,48 L460,55 L465,10 L470,90 L475,30 L480,50 L500,50 L540,50 L550,50 L555,48 L560,55 L565,10 L570,90 L575,30 L580,50 L600,50' fill='none' stroke='%234caf50' stroke-width='1' stroke-linejoin='round'/%3E%3C/svg%3E");
    background-repeat: repeat-x;
    background-size: 50% 100%;
    animation: thoth-wave-scroll 14s linear infinite;
}
.thoth-avatar {
    width: 58px; height: 58px;
    border-radius: 50%;
    display: flex; align-items: center; justify-content: center;
    font-size: 1.8rem;
    border: 2px solid transparent;
    animation: thoth-avatar-pulse 3s ease-in-out infinite;
    cursor: pointer;
    user-select: none;
    background: rgba(0,0,0,0.35);
    flex-shrink: 0;
    position: relative;
}
.thoth-avatar::after {
    content: "";
    position: absolute;
    inset: -3px;
    border-radius: 50%;
    padding: 2px;
    background: conic-gradient(
        from 0deg,
        transparent 0%,
        var(--avatar-color) 25%,
        transparent 50%,
        var(--avatar-color) 75%,
        transparent 100%
    );
    -webkit-mask: radial-gradient(farthest-side, transparent calc(100% - 2px), #fff calc(100% - 2px));
    mask: radial-gradient(farthest-side, transparent calc(100% - 2px), #fff calc(100% - 2px));
    animation: thoth-ring-spin 4s linear infinite;
    opacity: 0.7;
}
.thoth-avatar:hover { transform: scale(1.1); }
.status-pills-row {
    display: flex; flex-wrap: wrap; gap: 5px; align-items: center;
    justify-content: center;
}
.status-pill {
    display: inline-flex; align-items: center; gap: 5px;
    padding: 3px 10px;
    border-radius: 12px;
    font-size: 0.8rem;
    border: 1px solid rgba(255,255,255,0.1);
    cursor: pointer;
    transition: background 0.2s;
    white-space: nowrap;
}
.status-pill:hover { background: rgba(255,255,255,0.1); }
.status-pill .dot {
    width: 9px; height: 9px;
    border-radius: 50%;
    display: inline-block;
    flex-shrink: 0;
}
.status-pill.inactive { opacity: 0.4; font-size: 0.75rem; }
.thoth-diag-btn {
    width: 44px; height: 44px;
    border-radius: 50%;
    display: flex; align-items: center; justify-content: center;
    cursor: pointer;
    border: 1px solid rgba(255, 215, 0, 0.25);
    background: rgba(255, 215, 0, 0.08);
    color: #FFD700;
    font-size: 1.3rem;
    transition: background 0.2s, transform 0.2s;
    flex-shrink: 0;
}
.thoth-diag-btn:hover {
    background: rgba(255, 215, 0, 0.18);
    transform: scale(1.08);
}
@keyframes thoth-diag-spin {
    0%   { transform: rotate(0deg); }
    100% { transform: rotate(360deg); }
}
.thoth-diag-spinning .material-icons {
    animation: thoth-diag-spin 0.8s linear infinite;
}
@keyframes pulse-border {
    0%   { border-color: #FFA726; }
    50%  { border-color: #FF7043; }
    100% { border-color: #FFA726; }
}
</style>
"""



def build_status_bar(
    open_settings: Callable[[str], None],
) -> None:
    """Build the status bar that replaces the old logo section."""

    ui.html(_AVATAR_CSS, sanitize=False)

    # Load initial checks (cache-aware)
    results = _force_refresh()  # first render: full sweep
    result_map = {r.name: r for r in results}

    with ui.element("div").classes("thoth-status-panel w-full"):
      with ui.row().classes("w-full items-center no-wrap gap-3").style(
          "min-height: 60px;"
      ):

        # ── LEFT: Avatar ──────────────────────────────────────────
        avatar_cfg = _load_avatar_config()
        emoji = avatar_cfg.get("emoji", _DEFAULT_EMOJI)
        color = avatar_cfg.get("color", _DEFAULT_COLOR)

        avatar_el = ui.html(
            f'<div class="thoth-avatar" style="--avatar-color: {color};">' 
            f'{emoji}</div>',
            sanitize=False,
        )

        def _show_avatar_picker():
            """Open a small dialog to pick avatar emoji and color."""
            with ui.dialog() as dlg, ui.card().style("min-width: 280px;"):
                ui.label("Choose Avatar").classes("text-subtitle1 font-bold")
                ui.separator()

                current = _load_avatar_config()
                cur_emoji = current.get("emoji", _DEFAULT_EMOJI)
                cur_color = current.get("color", _DEFAULT_COLOR)

                # Emoji grid
                ui.label("Emoji").classes("text-xs text-grey-5 q-mt-sm")
                emoji_state = {"selected": cur_emoji}
                with ui.element("div").style(
                    "display: grid; grid-template-columns: repeat(6, 1fr); gap: 4px;"
                ):
                    for e in _AVATAR_EMOJIS:
                        def _pick_emoji(ev, em=e):
                            emoji_state["selected"] = em
                        btn = ui.button(e, on_click=_pick_emoji).props(
                            "flat dense padding=4px"
                        ).style("font-size: 1.2rem; min-width: 36px;")

                # Color picker
                ui.label("Ring Color").classes("text-xs text-grey-5 q-mt-sm")
                color_state = {"selected": cur_color}
                with ui.row().classes("gap-1 flex-wrap"):
                    for c in _RING_COLORS:
                        def _pick_color(ev, cl=c):
                            color_state["selected"] = cl
                        ui.button(on_click=_pick_color).style(
                            f"background: {c}; width: 28px; height: 28px; "
                            f"min-width: 28px; border-radius: 50%; padding: 0;"
                        ).props("flat dense")

                ui.separator()
                with ui.row().classes("w-full justify-end gap-2"):
                    ui.button("Cancel", on_click=dlg.close).props("flat dense")

                    def _save_and_close():
                        _save_avatar_config({
                            "emoji": emoji_state["selected"],
                            "color": color_state["selected"],
                        })
                        dlg.close()
                        avatar_el.set_content(
                            f'<div class="thoth-avatar" style="--avatar-color: {color_state["selected"]};">' 
                            f'{emoji_state["selected"]}</div>'
                        )
                    ui.button("Save", on_click=_save_and_close).props("dense color=amber")

            dlg.open()

        avatar_el.on("click", lambda: _show_avatar_picker())

        # ── CENTER: Status pills (two rows) ──────────────────────
        pills_container = ui.column().classes("flex-grow gap-1 items-center").style(
            "min-width: 0;"
        )

        def _render_pills(container, result_map: dict[str, CheckResult]):
            container.clear()
            with container:
                items = list(result_map.values())
                mid = (len(items) + 1) // 2  # even-ish split
                for row_items in (items[:mid], items[mid:]):
                    with ui.element("div").classes("status-pills-row"):
                        for r in row_items:
                            inactive_cls = " inactive" if r.status == "inactive" else ""

                            def _pill_click(tab=r.settings_tab, nm=r.name):
                                if tab:
                                    open_settings(tab)

                            pill_html = (
                                f'<span class="dot" style="background:{r.dot_color};"></span>'
                                f'{r.name}'
                            )
                            pill = ui.html(
                                f'<span class="status-pill{inactive_cls}">{pill_html}</span>',
                                sanitize=False,
                            ).tooltip(f"{r.name}: {r.status_label} — {r.detail}")

                            if r.settings_tab:
                                pill.on("click", _pill_click)

        _render_pills(pills_container, result_map)

        # ── RIGHT: Diagnosis button ───────────────────────────────
        async def _run_diagnosis():
            """Force-refresh and show full diagnosis dialog."""
            # Show spinner while checks run
            diag_btn_el.classes(add='thoth-diag-spinning')
            await asyncio.sleep(0.05)  # let UI update
            diag_results = _force_refresh()
            diag_btn_el.classes(remove='thoth-diag-spinning')
            elapsed = max(
                r.checked_at for r in diag_results
            ) - min(r.checked_at for r in diag_results) if diag_results else 0

            with ui.dialog() as dlg, ui.card().style(
                "min-width: 420px; max-width: 520px;"
            ):
                with ui.row().classes("w-full items-center justify-between"):
                    ui.label("🔍 System Diagnosis").classes("text-subtitle1 font-bold")
                    ui.button(icon="close", on_click=dlg.close).props("flat dense round size=sm")
                ui.separator()

                for r in diag_results:
                    with ui.expansion(
                        text=r.name,
                        icon=r.icon,
                    ).classes("w-full").props("dense") as exp:
                        exp.style(f"border-left: 3px solid {r.dot_color};")
                        with ui.row().classes("w-full items-center no-wrap gap-2"):
                            ui.html(
                                f'<span class="dot" style="background:{r.dot_color}; '
                                f'width:8px; height:8px; border-radius:50%; display:inline-block;"></span>',
                                sanitize=False,
                            )
                            ui.label(r.name).classes("font-bold")
                            ui.space()
                            ui.label(r.status_label).style(f"color: {r.dot_color};").classes("text-sm")
                        ui.label(r.detail).classes("text-xs text-grey-6 q-ml-md")

                ui.separator()
                with ui.row().classes("w-full items-center justify-between"):
                    ui.label(f"Checked {len(diag_results)} services").classes("text-xs text-grey-6")

                    def _copy_report():
                        lines = ["Thoth System Diagnosis", "=" * 40]
                        for r in diag_results:
                            icon = {"ok": "✅", "warn": "⚠️", "error": "❌", "inactive": "⬜"}.get(r.status, "?")
                            lines.append(f"{icon} {r.name}: {r.status_label} — {r.detail}")
                        report = "\n".join(lines)
                        ui.run_javascript(
                            f'navigator.clipboard.writeText({json.dumps(report)})'
                        )
                        ui.notify("Report copied to clipboard", type="positive")

                    with ui.row().classes("gap-2"):
                        ui.button("📋 Copy Report", on_click=_copy_report).props(
                            "flat dense no-caps"
                        )
                        ui.button("Close", on_click=dlg.close).props("dense")

            dlg.open()
            # Also refresh the pills behind the dialog
            new_map = {r.name: r for r in diag_results}
            _render_pills(pills_container, new_map)

        diag_btn_el = ui.html(
            '<div class="thoth-diag-btn" title="Run system diagnosis">'
            '<span class="material-icons" style="font-size:1.3rem;">health_and_safety</span>'
            '</div>',
            sanitize=False,
        ).on("click", lambda: _run_diagnosis())

      # ── EXTRACTION PROGRESS pill (below status row) ──────────────
      extraction_pill = ui.html("", sanitize=False)
      extraction_pill.set_visibility(False)
      extraction_pill.style("text-align: center; margin-top: 4px;")

      def _poll_extraction_status() -> None:
          """Timer callback — update extraction pill every 2 s."""
          try:
              from document_extraction import get_extraction_status, get_queue_length, stop_extraction as _stop_ext
          except ImportError:
              return
          status = get_extraction_status()
          if status is None:
              extraction_pill.set_visibility(False)
              return
          fname = status.get("file", "")
          prog = status.get("progress", 0)
          total = status.get("total", 0)
          ents = status.get("entities", 0)
          phase = status.get("phase", "map")
          queued = get_queue_length()
          pct = int(prog / total * 100) if total else 0
          bar = "█" * (pct // 10) + "░" * (10 - pct // 10)
          queue_txt = f" · +{queued} queued" if queued else ""
          phase_label = {"map": "summarizing", "reduce": "compiling", "extract": "extracting"}.get(phase, phase)
          extraction_pill.set_content(
              f'<span style="display:inline-flex; align-items:center; gap:6px; '
              f'border:1px solid #FFA726; border-radius:12px; padding:2px 10px; '
              f'font-size:0.75rem; color:#FFA726; animation:pulse-border 2s infinite;">'
              f'🧠 {fname} {bar} {prog}/{total} · {phase_label}{queue_txt}'
              f'<span id="extraction-stop-btn" style="cursor:pointer; margin-left:4px;" '
              f'title="Stop extraction">⏹</span>'
              f'</span>'
          )
          extraction_pill.set_visibility(True)

      ui.timer(2.0, _poll_extraction_status)

      # Wire the stop button via JavaScript delegation
      ui.run_javascript('''
          document.addEventListener("click", function(e) {
              if (e.target && e.target.id === "extraction-stop-btn") {
                  fetch("/_nicegui_api/extraction_stop", {method: "POST"}).catch(function(){});
              }
          });
      ''')

      # Use server-side click detection instead — simpler with NiceGUI
      extraction_pill.on("click", lambda: _handle_extraction_stop())

      def _handle_extraction_stop():
          try:
              from document_extraction import stop_extraction
              if stop_extraction():
                  ui.notify("⏹ Stopping extraction…", type="info")
          except ImportError:
              pass
