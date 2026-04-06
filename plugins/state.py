"""Plugin state persistence — enable/disable, config, and secrets.

Stores all plugin state in ``~/.thoth/plugin_state.json``.
Secrets are stored separately in ``~/.thoth/plugin_secrets.json``
with restricted file permissions.

This module is the ONLY place plugin state is read/written.
"""

from __future__ import annotations

import json
import logging
import os
import pathlib
import stat
from typing import Any

logger = logging.getLogger(__name__)

DATA_DIR = pathlib.Path(os.environ.get("THOTH_DATA_DIR", pathlib.Path.home() / ".thoth"))
DATA_DIR.mkdir(parents=True, exist_ok=True)

_STATE_PATH = DATA_DIR / "plugin_state.json"
_SECRETS_PATH = DATA_DIR / "plugin_secrets.json"

# ── In-memory caches ─────────────────────────────────────────────────────────
_state: dict[str, Any] = {}     # {plugin_id: {"enabled": bool, "config": {...}}}
_secrets: dict[str, dict] = {}  # {plugin_id: {"KEY_NAME": "value"}}
_loaded = False


# ── State I/O ────────────────────────────────────────────────────────────────
def reload():
    """Force re-read of state from disk. Call before load_plugins()."""
    global _loaded
    _loaded = False
    _ensure_loaded()


def _ensure_loaded():
    global _state, _secrets, _loaded
    if _loaded:
        return
    _state = _read_json(_STATE_PATH)
    _secrets = _read_json(_SECRETS_PATH)
    _loaded = True


def _read_json(path: pathlib.Path) -> dict:
    if path.exists():
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                return data
        except (json.JSONDecodeError, OSError):
            logger.warning("Failed to read %s", path, exc_info=True)
    return {}


def _save_state():
    _write_json(_STATE_PATH, _state)


def _save_secrets():
    _write_json(_SECRETS_PATH, _secrets, restricted=True)


def _write_json(path: pathlib.Path, data: dict, restricted: bool = False):
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        if restricted and os.name != "nt":
            os.chmod(path, stat.S_IRUSR | stat.S_IWUSR)  # 0600
    except OSError:
        logger.warning("Failed to write %s", path, exc_info=True)


# ── Enabled State ────────────────────────────────────────────────────────────
def is_plugin_enabled(plugin_id: str) -> bool:
    _ensure_loaded()
    return _state.get(plugin_id, {}).get("enabled", True)  # auto-enable by default


def set_plugin_enabled(plugin_id: str, enabled: bool) -> None:
    _ensure_loaded()
    _state.setdefault(plugin_id, {})["enabled"] = enabled
    _save_state()
    _invalidate_agent_cache()
    logger.info("Plugin '%s' %s", plugin_id, "enabled" if enabled else "disabled")


# ── Configuration ────────────────────────────────────────────────────────────
def get_plugin_config(plugin_id: str, key: str, default: Any = None) -> Any:
    _ensure_loaded()
    return _state.get(plugin_id, {}).get("config", {}).get(key, default)


def set_plugin_config(plugin_id: str, key: str, value: Any) -> None:
    _ensure_loaded()
    _state.setdefault(plugin_id, {}).setdefault("config", {})[key] = value
    _save_state()


def get_all_plugin_config(plugin_id: str) -> dict:
    _ensure_loaded()
    return dict(_state.get(plugin_id, {}).get("config", {}))


# ── Secrets ──────────────────────────────────────────────────────────────────
def get_plugin_secret(plugin_id: str, key: str) -> str | None:
    _ensure_loaded()
    return _secrets.get(plugin_id, {}).get(key)


def set_plugin_secret(plugin_id: str, key: str, value: str) -> None:
    _ensure_loaded()
    _secrets.setdefault(plugin_id, {})[key] = value
    _save_secrets()


def get_all_plugin_secrets(plugin_id: str) -> dict[str, str]:
    _ensure_loaded()
    return dict(_secrets.get(plugin_id, {}))


# ── Cleanup ──────────────────────────────────────────────────────────────────
def remove_plugin_state(plugin_id: str) -> None:
    """Remove all state and secrets for a plugin (on uninstall)."""
    _ensure_loaded()
    _state.pop(plugin_id, None)
    _secrets.pop(plugin_id, None)
    _save_state()
    _save_secrets()
    _invalidate_agent_cache()


# ── Cache Invalidation ───────────────────────────────────────────────────────
def _invalidate_agent_cache():
    try:
        from agent import clear_agent_cache
        clear_agent_cache()
    except ImportError:
        pass


# ── Reset (for testing) ─────────────────────────────────────────────────────
def _reset():
    """Reset in-memory caches. For testing only."""
    global _state, _secrets, _loaded
    _state = {}
    _secrets = {}
    _loaded = False
