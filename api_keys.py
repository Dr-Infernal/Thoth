import logging
import os
import json
import pathlib

logger = logging.getLogger(__name__)

# Store data in %APPDATA%/Thoth (writable even when app is in Program Files)
DATA_DIR = pathlib.Path(os.environ.get("THOTH_DATA_DIR", pathlib.Path.home() / ".thoth"))
DATA_DIR.mkdir(parents=True, exist_ok=True)

KEYS_PATH = DATA_DIR / "api_keys.json"

# All API keys the app can use – label shown in UI → env-var name
API_KEY_DEFINITIONS = {
    "Tavily": "TAVILY_API_KEY",
}

# Telegram Bot credentials – stored the same way but managed
# in the Channels settings tab rather than the API-Keys tab.
TELEGRAM_KEY_DEFINITIONS = {
    "Telegram Bot Token": "TELEGRAM_BOT_TOKEN",
    "Telegram User ID": "TELEGRAM_USER_ID",
}

# OpenRouter credentials – managed in the Cloud settings tab.
OPENROUTER_KEY_DEFINITIONS = {
    "OpenRouter API Key": "OPENROUTER_API_KEY",
}

# OpenAI direct API credentials – managed in the Cloud settings tab.
OPENAI_KEY_DEFINITIONS = {
    "OpenAI API Key": "OPENAI_API_KEY",
}

# Anthropic (Claude) API credentials – managed in the Cloud settings tab.
ANTHROPIC_KEY_DEFINITIONS = {
    "Anthropic API Key": "ANTHROPIC_API_KEY",
}

# Google AI (Gemini) API credentials – managed in the Cloud settings tab.
GOOGLE_KEY_DEFINITIONS = {
    "Google AI API Key": "GOOGLE_API_KEY",
}

# xAI (Grok) API credentials – managed in the Cloud settings tab.
XAI_KEY_DEFINITIONS = {
    "xAI API Key": "XAI_API_KEY",
}

# ── Cloud provider configuration ────────────────────────────────────────────
_CLOUD_CONFIG_PATH = DATA_DIR / "cloud_config.json"

_DEFAULT_CLOUD_CONFIG: dict[str, object] = {
    "starred_models": [],
}


def get_cloud_config() -> dict:
    """Return cloud privacy settings (fills in defaults for missing keys)."""
    cfg = dict(_DEFAULT_CLOUD_CONFIG)
    if _CLOUD_CONFIG_PATH.exists():
        try:
            with open(_CLOUD_CONFIG_PATH, "r") as f:
                stored = json.load(f)
            cfg.update(stored)
        except (json.JSONDecodeError, OSError):
            logger.warning("Failed to load cloud config from %s", _CLOUD_CONFIG_PATH, exc_info=True)
    return cfg


def set_cloud_config(key: str, value: object) -> None:
    """Update a single cloud config key and persist."""
    cfg = get_cloud_config()
    cfg[key] = value
    try:
        with open(_CLOUD_CONFIG_PATH, "w") as f:
            json.dump(cfg, f, indent=2)
    except OSError:
        logger.warning("Failed to save cloud config to %s", _CLOUD_CONFIG_PATH, exc_info=True)


def _load_keys() -> dict[str, str]:
    """Load saved keys from disk. Returns {env_var: value}."""
    if KEYS_PATH.exists():
        try:
            with open(KEYS_PATH, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            logger.warning("Failed to load API keys from %s", KEYS_PATH, exc_info=True)
            return {}
    return {}


def _save_keys(keys: dict[str, str]):
    """Persist keys to disk."""
    with open(KEYS_PATH, "w") as f:
        json.dump(keys, f, indent=2)


def get_key(env_var: str) -> str:
    """Return a key value (empty string if not set)."""
    return _load_keys().get(env_var, "")


def set_key(env_var: str, value: str):
    """Save a single key and push it into the environment."""
    keys = _load_keys()
    keys[env_var] = value
    _save_keys(keys)
    os.environ[env_var] = value


def apply_keys():
    """Load all saved keys into environment variables."""
    for env_var, value in _load_keys().items():
        if value:
            os.environ[env_var] = value