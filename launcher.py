"""Thoth Launcher — system-tray process that manages the NiceGUI server.

Responsibilities:
    • Splash screen while the server starts (tkinter — no extra deps)
    • System-tray icon (green = running, grey = stopped)
    • Launch  ``python app_nicegui.py``  as a managed subprocess
    • Open the browser to http://localhost:8080
    • Detect an already-running instance and just open the browser
    • Graceful shutdown on Quit
"""

from __future__ import annotations

import atexit
import logging
import subprocess
import sys
import threading
import time
import webbrowser
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from PIL import Image as _PILImage

# ── Setup logging ────────────────────────────────────────────────────────────
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

# ── Constants ────────────────────────────────────────────────────────────────
_PORT = 8080
_URL = f"http://localhost:{_PORT}"
_STARTUP_GRACE = 15           # seconds to wait for NiceGUI before opening browser
_ICON_SIZE = 64               # px for generated tray icons


# ── Icon generation (Pillow, no external files) ──────────────────────────────

def _make_icon(colour: str) -> _PILImage.Image:
    """Create a solid circle icon with the given colour on a transparent bg."""
    from PIL import Image, ImageDraw

    img = Image.new("RGBA", (_ICON_SIZE, _ICON_SIZE), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    margin = 4
    draw.ellipse(
        [margin, margin, _ICON_SIZE - margin, _ICON_SIZE - margin],
        fill=colour,
    )
    return img


# Pre-generate the three state icons lazily
_icons: dict[str, _PILImage.Image] = {}


def _get_icon(state: str) -> _PILImage.Image:
    """Return the icon for a launcher state string."""
    colour_map = {
        "running":  "#22c55e",   # green
    }
    colour = colour_map.get(state, "#6b7280")  # grey fallback
    if colour not in _icons:
        _icons[colour] = _make_icon(colour)
    return _icons[colour]


# ── Port check ───────────────────────────────────────────────────────────────

def _is_port_in_use(port: int = _PORT) -> bool:
    """Return True if something is already listening on *port*."""
    import socket
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(1)
        return s.connect_ex(("127.0.0.1", port)) == 0


# ── NiceGUI subprocess management ───────────────────────────────────────────

class _ThothProcess:
    """Wraps the NiceGUI app subprocess."""

    def __init__(self) -> None:
        self._proc: subprocess.Popen | None = None

    def start(self, *, native: bool = True) -> None:
        """Launch ``python app_nicegui.py`` in the project directory.

        If *native* is True (default) the app opens in a pywebview
        native OS window instead of a browser tab.
        """
        app_dir = Path(__file__).resolve().parent
        app_py = app_dir / "app_nicegui.py"

        # Use the same Python that's running this launcher
        python = sys.executable

        cmd = [python, str(app_py)]
        if native:
            cmd.append("--native")

        self._proc = subprocess.Popen(
            cmd,
            cwd=str(app_dir),
            # On Windows, CREATE_NO_WINDOW prevents a visible console
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        logger.info("Thoth started (PID %s, native=%s)", self._proc.pid, native)

    def stop(self) -> None:
        """Terminate the NiceGUI process."""
        if self._proc is None:
            return
        try:
            self._proc.terminate()
            self._proc.wait(timeout=5)
        except Exception:
            try:
                self._proc.kill()
            except Exception:
                pass
        logger.info("Thoth stopped")
        self._proc = None

    @property
    def is_alive(self) -> bool:
        if self._proc is None:
            return False
        return self._proc.poll() is None


# ── Splash screen (tkinter — stdlib, runs as subprocess to avoid Tcl issues) ─

# Inline script executed via ``python -c``.  Avoids Tcl/thread crashes
# that occur when tkinter is used in the same process as pystray.
_SPLASH_SCRIPT = r'''
import tkinter as tk, socket, time, sys

PORT    = int(sys.argv[1])
TIMEOUT = float(sys.argv[2])
W, H    = 500, 300
BG      = "#1e1e1e"
GOLD    = "#FFD700"

def port_ready():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(0.3)
        s.connect(("127.0.0.1", PORT))
        s.close()
        return True
    except OSError:
        return False

root = tk.Tk()
root.overrideredirect(True)
root.attributes("-topmost", True)
root.configure(bg=BG)
sx, sy = root.winfo_screenwidth(), root.winfo_screenheight()
root.geometry(f"{W}x{H}+{(sx-W)//2}+{(sy-H)//2}")

tk.Label(root, text="\U0001305F", font=("Segoe UI Emoji", 64), fg=GOLD, bg=BG).pack(pady=(40,0))
tk.Label(root, text="Thoth", font=("Segoe UI", 28, "bold"), fg=GOLD, bg=BG).pack(pady=(0,10))
lbl = tk.Label(root, text="Loading.", font=("Segoe UI", 12), fg="#aaaaaa", bg=BG)
lbl.pack()

_start = time.monotonic()
_d = [0]

def _check():
    _d[0] = (_d[0] % 3) + 1
    lbl.configure(text="Loading" + "." * _d[0])
    if time.monotonic() - _start > TIMEOUT or port_ready():
        root.destroy()
        return
    root.after(500, _check)

root.after(500, _check)
root.mainloop()
'''


def _show_splash(port: int = _PORT, timeout: float = 60.0) -> subprocess.Popen:
    """Launch the splash screen in a child process and return the handle.

    The splash monitors *port* and closes itself once the server is
    listening (or *timeout* seconds elapse).  Because it runs in its own
    process, tkinter's Tcl layer is fully isolated from the main launcher.
    """
    return subprocess.Popen(
        [sys.executable, "-c", _SPLASH_SCRIPT, str(port), str(timeout)],
        # CREATE_NO_WINDOW prevents a console flash on Windows
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )


# ── Tray application ────────────────────────────────────────────────────────

class ThothTray:
    """System-tray icon that manages the NiceGUI server."""

    def __init__(self) -> None:
        import pystray

        self._server = _ThothProcess()
        self._owns_server = False          # True if *we* started it
        self._stop_event = threading.Event()

        menu = pystray.Menu(
            pystray.MenuItem("Open Thoth", self._on_open, default=True),
            pystray.MenuItem("Quit", self._on_quit),
        )
        self._icon = pystray.Icon(
            name="Thoth",
            icon=_get_icon("stopped"),
            title="Thoth — stopped",
            menu=menu,
        )

    # ── Menu callbacks ───────────────────────────────────────────────────

    def _on_open(self, icon=None, item=None) -> None:   # noqa: ARG002
        if self._owns_server:
            if not self._server.is_alive:
                # Native window was closed — restart the process to reopen it
                logger.info("Re-launching Thoth native window")
                self._server.start(native=True)
            # else: native window is already open, nothing to do
        else:
            # Someone else started the server (e.g. dev mode) — open browser
            webbrowser.open(_URL)

    def _on_quit(self, icon=None, item=None) -> None:    # noqa: ARG002
        logger.info("Quit requested")
        self._stop_event.set()
        if self._owns_server:
            self._server.stop()
        self._icon.stop()

    # ── Background poller ────────────────────────────────────────────────

    def _poll_loop(self) -> None:
        """Periodically check if the app is still alive and update icon."""
        _POLL_INTERVAL = 3.0  # seconds
        while not self._stop_event.is_set():
            if self._owns_server and self._server.is_alive:
                self._icon.icon = _get_icon("running")
                self._icon.title = "Thoth — running"
            elif not self._owns_server and _is_port_in_use(_PORT):
                self._icon.icon = _get_icon("running")
                self._icon.title = "Thoth — running"
            else:
                self._icon.icon = _get_icon("stopped")
                self._icon.title = "Thoth — stopped"

            self._stop_event.wait(_POLL_INTERVAL)

    # ── Entry point ──────────────────────────────────────────────────────

    def run(self) -> None:
        """Start the tray icon and (if needed) the NiceGUI server."""
        already_running = _is_port_in_use(_PORT)

        if already_running:
            logger.info("Thoth already running on port %s", _PORT)
        else:
            self._server.start()
            self._owns_server = True
            # Register cleanup in case launcher crashes
            atexit.register(self._server.stop)

            # Show splash screen while the server starts up
            _show_splash()

        # Start the status-polling thread
        poller = threading.Thread(target=self._poll_loop, daemon=True, name="tray-poll")
        poller.start()

        # In native mode, the pywebview window opens automatically.
        # Only open a browser if we didn't start the server (external instance).
        if already_running:
            webbrowser.open(_URL)

        # Blocking — runs the tray icon's event loop on the main thread
        logger.info("Thoth tray running  (Ctrl+C or Quit menu to exit)")
        self._icon.run()


# ── Main ─────────────────────────────────────────────────────────────────────

def main() -> None:
    try:
        tray = ThothTray()
        tray.run()
    except KeyboardInterrupt:
        logger.info("Interrupted — shutting down")


if __name__ == "__main__":
    main()
