"""Tool registry — discovers, stores, and manages all retrieval tools.

Usage
-----
    from tools import registry

    for tool in registry.get_enabled_tools():
        results = tool.get_retriever().invoke(query)
"""

from __future__ import annotations

import json
import logging
import os
import pathlib
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from tools.base import BaseTool

logger = logging.getLogger(__name__)

# Persist enabled / disabled state alongside other Thoth data
DATA_DIR = pathlib.Path(os.environ.get("THOTH_DATA_DIR", pathlib.Path.home() / ".thoth"))
DATA_DIR.mkdir(parents=True, exist_ok=True)
_CONFIG_PATH = DATA_DIR / "tools_config.json"

# ── Internal storage ─────────────────────────────────────────────────────────────
_tools: dict[str, "BaseTool"] = {}          # name → tool instance
_enabled: dict[str, bool] = {}              # name → enabled flag (runtime cache)
_tool_configs: dict[str, dict] = {}         # name → {key: value} (tool-specific config)


# ── Config persistence ───────────────────────────────────────────────────────
def _load_config() -> dict:
    """Load the persisted config from disk."""
    if _CONFIG_PATH.exists():
        try:
            with open(_CONFIG_PATH, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            logger.warning("Failed to load tools config from %s", _CONFIG_PATH, exc_info=True)
            return {}
    return {}


def _save_config():
    """Persist the current enabled/disabled map and tool configs to disk."""
    with open(_CONFIG_PATH, "w") as f:
        json.dump({"tools": _enabled, "tool_configs": _tool_configs}, f, indent=2)


# ── Public API ───────────────────────────────────────────────────────────────
def register(tool: "BaseTool") -> None:
    """Register a tool instance.  Called by each tool module at import time."""
    logger.debug("Registering tool: %s", tool.name)
    _tools[tool.name] = tool
    # If the user already toggled this tool, honour that; otherwise use default
    saved = _load_config()
    # Support new format {"tools": {...}} and old flat format
    tools_map = saved.get("tools", saved) if isinstance(saved.get("tools"), dict) else saved
    if tool.name in tools_map:
        _enabled[tool.name] = tools_map[tool.name]
    else:
        _enabled[tool.name] = tool.enabled_by_default
    # Restore persisted tool-specific config
    saved_configs = saved.get("tool_configs", {})
    if tool.name in saved_configs:
        _tool_configs[tool.name] = saved_configs[tool.name]
        # Auto-migrate: if the schema adds new default operations that didn't
        # exist before, merge them in so existing users get new sub-tools.
        # We track which options were known at last save via _known_options.
        for key, spec in tool.config_schema.items():
            if spec.get("type") != "multicheck":
                continue
            known_key = f"_{key}_known"
            current_options = set(spec.get("options", []))
            previously_known = set(_tool_configs[tool.name].get(known_key, []))
            if previously_known:
                new_ops = current_options - previously_known
                default_ops = set(spec.get("default", []))
                to_add = new_ops & default_ops  # only auto-enable if in defaults
                if to_add and key in _tool_configs[tool.name]:
                    saved_ops = set(_tool_configs[tool.name][key])
                    _tool_configs[tool.name][key] = list(saved_ops | to_add)
                    logger.info("Auto-enabled new operations for %s: %s",
                                tool.name, to_add)
            # Always update the known set to current options
            _tool_configs[tool.name][known_key] = list(current_options)
    else:
        # Initialise from schema defaults
        _tool_configs.setdefault(tool.name, {})
        for key, spec in tool.config_schema.items():
            if key not in _tool_configs[tool.name]:
                _tool_configs[tool.name][key] = spec.get("default")


def get_all_tools() -> list["BaseTool"]:
    """Return all registered tools (enabled + disabled), sorted by name."""
    return [_tools[n] for n in sorted(_tools)]


def get_enabled_tools() -> list["BaseTool"]:
    """Return only the tools the user has enabled."""
    return [t for t in get_all_tools() if is_enabled(t.name)]


def is_enabled(name: str) -> bool:
    return _enabled.get(name, False)


def set_enabled(name: str, value: bool) -> None:
    logger.info("Tool '%s' %s", name, "enabled" if value else "disabled")
    _enabled[name] = value
    _save_config()
    _invalidate_agent_cache()
    # Also invalidate the task tool-inference keyword map
    try:
        from tasks import invalidate_keyword_map_cache
        invalidate_keyword_map_cache()
    except ImportError:
        pass


def get_tool(name: str) -> "BaseTool | None":
    return _tools.get(name)


def get_all_required_api_keys() -> dict[str, str]:
    """Aggregate ``required_api_keys`` from *all* registered tools.
    Returns ``{UI label: ENV_VAR_NAME}``.
    """
    keys: dict[str, str] = {}
    for tool in get_all_tools():
        keys.update(tool.required_api_keys)
    return keys


def get_tool_config(tool_name: str, key: str, default=None):
    """Read a persisted config value for a tool."""
    return _tool_configs.get(tool_name, {}).get(key, default)


def set_tool_config(tool_name: str, key: str, value):
    """Write a config value for a tool and persist."""
    _tool_configs.setdefault(tool_name, {})[key] = value
    _save_config()
    _invalidate_agent_cache()


def _invalidate_agent_cache():
    """Clear cached agent graphs when tool settings change."""
    try:
        from agent import clear_agent_cache
        clear_agent_cache()
    except ImportError:
        pass


# ── Global (non-tool-specific) config ────────────────────────────────────────
_global_config: dict = {}

def _load_global_config():
    """Bootstrap global config from the persisted file."""
    global _global_config
    saved = _load_config()
    _global_config = saved.get("global", {})

def get_global_config(key: str, default=None):
    """Read a global (non-tool-specific) config value."""
    if not _global_config:
        _load_global_config()
    return _global_config.get(key, default)

def set_global_config(key: str, value) -> None:
    """Write a global config value and persist."""
    _global_config[key] = value
    # Merge into the config file alongside tools and tool_configs
    saved = _load_config()
    saved["global"] = _global_config
    with open(_CONFIG_PATH, "w") as f:
        json.dump(saved, f, indent=2)
    _invalidate_agent_cache()


def get_langchain_tools() -> list:
    """Return LangChain-compatible tool wrappers for all enabled tools.
    Uses ``as_langchain_tools()`` (plural) so tools contributing multiple
    operations are handled correctly."""
    tools = []
    for t in get_enabled_tools():
        tools.extend(t.as_langchain_tools())
    return tools
