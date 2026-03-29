import contextvars
import json
import logging
import os
import pathlib
import threading

try:
    import ollama as _ollama_mod
except ImportError:
    _ollama_mod = None  # type: ignore[assignment]

try:
    from langchain_ollama import ChatOllama
except ImportError:
    ChatOllama = None  # type: ignore[assignment,misc]

logger = logging.getLogger(__name__)

# ── Cloud provider URLs ─────────────────────────────────────────────────────
OPENAI_BASE_URL = "https://api.openai.com/v1"
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"

# ── Context-size heuristics (prefix-match, checked top-to-bottom) ───────────
# Used when the provider API doesn't expose context_length (e.g. OpenAI) and
# the model isn't in the OpenRouter cross-reference cache.  More-specific
# prefixes must come before shorter ones.  Covers OpenAI, Anthropic & Gemini.
_CONTEXT_HEURISTICS: list[tuple[str, int]] = [
    # ── OpenAI ────────────────────────────────────────────────────────
    ("gpt-4.1",       1_048_576),   # gpt-4.1 / mini / nano  — 1M
    ("gpt-4.5",       1_048_576),   # gpt-4.5 family          — 1M
    ("gpt-5",         1_048_576),   # gpt-5 / 5.4 etc         — 1M
    ("gpt-4o",          128_000),   # gpt-4o / 4o-mini        — 128K
    ("gpt-4-turbo",     128_000),   # gpt-4-turbo             — 128K
    ("gpt-4",             8_192),   # base gpt-4 (legacy)     — 8K
    ("gpt-3.5",          16_385),   # gpt-3.5-turbo           — 16K
    ("o1",              200_000),   # o1 / o1-mini / o1-pro   — 200K
    ("o3",              200_000),   # o3 / o3-mini / o3-pro   — 200K
    ("o4",              200_000),   # o4-mini etc              — 200K
    ("chatgpt-",        128_000),   # chatgpt- aliases        — 128K
    # ── Anthropic ─────────────────────────────────────────────────────
    ("claude-opus-4",  1_000_000),  # Opus 4.x                — 1M
    ("claude-sonnet-4",1_000_000),  # Sonnet 4.x              — 1M
    ("claude-haiku-4",   200_000),  # Haiku 4.x               — 200K
    ("claude-3-5",       200_000),  # Claude 3.5 family       — 200K
    ("claude-3",         200_000),  # Claude 3 family         — 200K
    ("claude-2",         100_000),  # Claude 2.x (legacy)     — 100K
    ("claude",           200_000),  # Catch-all Claude        — 200K
    # ── Google Gemini ─────────────────────────────────────────────────
    ("gemini-3",       1_048_576),  # Gemini 3.x              — 1M
    ("gemini-2.5",     1_048_576),  # Gemini 2.5 Flash/Pro    — 1M
    ("gemini-2.0",     1_048_576),  # Gemini 2.0              — 1M
    ("gemini-1.5-pro", 2_097_152),  # Gemini 1.5 Pro          — 2M
    ("gemini-1.5",     1_048_576),  # Gemini 1.5 Flash        — 1M
    ("gemini-1.0",        32_768),  # Legacy Gemini 1.0       — 32K
    ("gemini",         1_048_576),  # Catch-all Gemini        — 1M
]

_CLOUD_CONTEXT_FALLBACK = 256_000   # safe default for totally unknown models


def _estimate_context_heuristic(model_name: str) -> int:
    """Guess context size from the model name using prefix heuristics.

    Strips any ``provider/`` prefix (e.g. ``openai/gpt-4o`` → ``gpt-4o``)
    before matching.  Returns ``_CLOUD_CONTEXT_FALLBACK`` if nothing matches.
    """
    bare = model_name.split("/")[-1]          # strip provider/ slug
    for prefix, ctx in _CONTEXT_HEURISTICS:
        if bare.startswith(prefix):
            return ctx
    return _CLOUD_CONTEXT_FALLBACK

# Prefixes considered chat-capable when filtering OpenAI /v1/models
_OPENAI_CHAT_PREFIXES = ("gpt-", "o1", "o3", "o4", "chatgpt-")
# Substrings that indicate a non-chat model — skip these
_OPENAI_SKIP_SUBSTRINGS = ("dall-e", "whisper", "tts", "embedding", "davinci",
                           "babbage", "moderation", "realtime", "audio",
                           "transcri", "search")

# ── Dynamic cloud model cache ───────────────────────────────────────────────
_cloud_model_cache: dict[str, dict] = {}   # model_id → {label, ctx, provider}
_cloud_cache_lock = threading.Lock()

# ── Context catalog (keyless OpenRouter public data) ────────────────────────
_context_catalog: dict[str, int] = {}      # model_id → context_length
_context_catalog_lock = threading.Lock()

# ── Trending Ollama models (fetched from ollama.com) ────────────────────────
_trending_ollama_cache: list[str] = []
_trending_fetched: bool = False

DEFAULT_MODEL = "qwen3:14b"
DEFAULT_CONTEXT_SIZE = 32768

CONTEXT_SIZE_OPTIONS = [4096, 8192, 16384, 32768, 65536, 131072, 262144]
CONTEXT_SIZE_LABELS = {4096: "4K", 8192: "8K", 16384: "16K", 32768: "32K",
                       65536: "64K", 131072: "128K", 262144: "256K"}

# ── Persistent settings file ────────────────────────────────────────────────
_DATA_DIR = pathlib.Path(os.environ.get("THOTH_DATA_DIR", pathlib.Path.home() / ".thoth"))
_SETTINGS_PATH = _DATA_DIR / "model_settings.json"
_CLOUD_CACHE_PATH = _DATA_DIR / "cloud_models_cache.json"
_CONTEXT_CATALOG_PATH = _DATA_DIR / "context_catalog_cache.json"


def _load_settings() -> dict:
    """Load persisted model settings, or return defaults."""
    try:
        if _SETTINGS_PATH.exists():
            return json.loads(_SETTINGS_PATH.read_text())
    except Exception:
        logger.warning("Failed to load model settings from %s", _SETTINGS_PATH, exc_info=True)
    return {}


def _save_settings(settings: dict):
    """Persist model settings to disk."""
    _DATA_DIR.mkdir(parents=True, exist_ok=True)
    _SETTINGS_PATH.write_text(json.dumps(settings, indent=2))


def _load_cloud_cache() -> dict:
    """Load persisted cloud model cache from disk."""
    try:
        if _CLOUD_CACHE_PATH.exists():
            data = json.loads(_CLOUD_CACHE_PATH.read_text())
            if isinstance(data, dict):
                return data
    except Exception:
        logger.warning("Failed to load cloud cache from %s", _CLOUD_CACHE_PATH, exc_info=True)
    return {}


def _save_cloud_cache():
    """Persist current cloud model cache to disk."""
    try:
        _DATA_DIR.mkdir(parents=True, exist_ok=True)
        with _cloud_cache_lock:
            _CLOUD_CACHE_PATH.write_text(json.dumps(_cloud_model_cache))
    except Exception:
        logger.warning("Failed to save cloud cache to %s", _CLOUD_CACHE_PATH, exc_info=True)


def _load_context_catalog() -> dict[str, int]:
    """Load persisted context catalog from disk."""
    try:
        if _CONTEXT_CATALOG_PATH.exists():
            data = json.loads(_CONTEXT_CATALOG_PATH.read_text())
            if isinstance(data, dict):
                return data
    except Exception:
        logger.warning("Failed to load context catalog from %s",
                       _CONTEXT_CATALOG_PATH, exc_info=True)
    return {}


def _save_context_catalog():
    """Persist current context catalog to disk."""
    try:
        _DATA_DIR.mkdir(parents=True, exist_ok=True)
        with _context_catalog_lock:
            _CONTEXT_CATALOG_PATH.write_text(json.dumps(_context_catalog))
    except Exception:
        logger.warning("Failed to save context catalog to %s",
                       _CONTEXT_CATALOG_PATH, exc_info=True)


# Initialise from saved settings (fall back to defaults for first run)
_saved = _load_settings()

# Load persisted cloud cache so is_cloud_model() works before refresh
_cloud_model_cache.update(_load_cloud_cache())

# Load persisted context catalog so context resolution works before live fetch
_context_catalog.update(_load_context_catalog())

POPULAR_MODELS = [
    # ── Qwen family ──────────────────────────────────────────────────────
    "qwen3:8b", "qwen3:14b", "qwen3:30b", "qwen3:32b", "qwen3:235b",
    "qwen3.5:9b", "qwen3.5:27b", "qwen3.5:35b", "qwen3.5:122b",
    "qwen3-coder:30b",
    # ── Llama family ─────────────────────────────────────────────────────
    "llama3.1:8b", "llama3.1:70b", "llama3.1:405b",
    "llama3.3:70b",
    "llama3-groq-tool-use:8b", "llama3-groq-tool-use:70b",
    # ── Mistral family ───────────────────────────────────────────────────
    "mistral:7b",
    "mistral-nemo:12b",
    "mistral-small:22b", "mistral-small:24b",
    "mistral-small3.1:24b",
    "mistral-small3.2:24b",
    "mistral-large:123b",
    "mixtral:8x7b", "mixtral:8x22b",
    "magistral:24b",
    "ministral-3:8b", "ministral-3:14b",
    # ── Other tool-capable models ────────────────────────────────────────
    "rnj-1:8b",
    "glm-4.7-flash:30b",
    "nemotron-3-nano:30b",
    "nemotron:70b",
    "devstral-small-2:24b",
    "devstral-2:123b",
    "olmo-3.1:32b",
    "lfm2:24b",
    "gpt-oss:20b", "gpt-oss:120b",
    "firefunction-v2:70b",
]

# Set of all model *family* prefixes known to support Ollama tool calling.
# Used to flag downloaded models NOT in this set with a ⚠️ warning.
_TOOL_COMPATIBLE_FAMILIES: set[str] = {
    m.split(":")[0] for m in POPULAR_MODELS
}

_current_model = _saved.get("model", DEFAULT_MODEL)
_num_ctx = _saved.get("context_size", DEFAULT_CONTEXT_SIZE)
_llm_instance = None
_model_max_ctx_cache: dict[str, int | None] = {}  # model_name → max context


def get_llm():
    """Return the current LLM instance, creating one if needed.

    If the default model is a cloud model, returns the appropriate
    ``ChatOpenAI`` instance.  Otherwise returns ``ChatOllama``.
    """
    global _llm_instance
    if _llm_instance is None:
        if is_cloud_model(_current_model):
            _llm_instance = _get_cloud_llm(_current_model)
        else:
            logger.info("Creating LLM instance: model=%s, num_ctx=%s", _current_model, _num_ctx)
            _llm_instance = ChatOllama(model=_current_model, num_ctx=_num_ctx)
    return _llm_instance


_override_llm_cache: dict[tuple[str, int], object] = {}  # model → ChatOllama or ChatOpenAI


def get_llm_for(model_name: str, num_ctx: int | None = None):
    """Return an LLM for a specific model (not the global singleton).

    For local (Ollama) models, returns a ``ChatOllama``.
    For cloud (OpenRouter) models, returns a ``ChatOpenAI`` pointed at
    the OpenRouter API.  Results are cached per (model, ctx) pair.
    """
    if is_cloud_model(model_name):
        return _get_cloud_llm(model_name)

    if num_ctx is None:
        model_max = get_model_max_context(model_name)
        if model_max is not None:
            num_ctx = min(model_max, _num_ctx)
        else:
            num_ctx = _num_ctx
    key = (model_name, num_ctx)
    if key not in _override_llm_cache:
        logger.info("Creating override LLM: model=%s, num_ctx=%s", model_name, num_ctx)
        _override_llm_cache[key] = ChatOllama(model=model_name, num_ctx=num_ctx)
    return _override_llm_cache[key]


def get_model_max_context(model_name: str | None = None) -> int | None:
    """Query Ollama for the model's native max context length.

    For cloud models, returns the hardcoded context size from the catalog.
    Returns the context_length from model metadata, or *None* if it
    cannot be determined.  Results are cached per model name.
    """
    name = model_name or _current_model
    if is_cloud_model(name):
        return get_cloud_model_context(name)
    if name in _model_max_ctx_cache:
        return _model_max_ctx_cache[name]
    if not _ollama_mod:
        _model_max_ctx_cache[name] = None
        return None
    try:
        info = _ollama_mod.show(name)
        mi = info.modelinfo or {}
        arch = mi.get("general.architecture", "")
        ctx = mi.get(f"{arch}.context_length") if arch else None
        _model_max_ctx_cache[name] = int(ctx) if ctx is not None else None
    except Exception:
        logger.debug("Could not query max context for model %s", name, exc_info=True)
        _model_max_ctx_cache[name] = None
    return _model_max_ctx_cache[name]


def set_model(model_name: str):
    """Switch the active model.  Accepts both local Ollama and cloud model IDs.

    For local models: unloads the previous model from Ollama's VRAM.
    For cloud models: just updates the setting (no Ollama interaction).
    """
    global _current_model, _llm_instance
    if model_name != _current_model:
        logger.info("Switching model: %s → %s", _current_model, model_name)
        # Unload previous local model from Ollama memory
        if not is_cloud_model(_current_model) and _ollama_mod:
            try:
                _ollama_mod.generate(model=_current_model, prompt="", keep_alive=0)
            except Exception:
                logger.debug("Could not unload previous model %s", _current_model, exc_info=True)
    _current_model = model_name
    if is_cloud_model(model_name):
        _llm_instance = _get_cloud_llm(model_name)
    else:
        _llm_instance = ChatOllama(model=model_name, num_ctx=_num_ctx)
    _save_settings({"model": _current_model, "context_size": _num_ctx})


# Thread-local model override — allows agent.py to propagate the per-thread
# cloud model override so that get_context_size() (and everything downstream:
# get_tool_budget, _keep_browser_snapshots, tool budgets) automatically uses
# the correct context window without every caller needing an explicit argument.
_active_model_override: contextvars.ContextVar[str] = contextvars.ContextVar(
    "active_model_override", default=""
)


def set_active_model_override(name: str) -> None:
    """Set the thread-local model override (called by agent.py before execution)."""
    _active_model_override.set(name)


def get_context_size(model_name: str | None = None) -> int:
    """Return the *effective* context size for the given (or current) model.

    - **Cloud models** always use the model's full native context window.
      Cloud providers handle memory server-side and bill per-token, so
      there is no reason to artificially limit context.
    - **Local (Ollama) models** use ``min(user_setting, model_native_max)``
      because ``num_ctx`` directly controls VRAM usage.

    Resolution order for the model name:
    1. Explicit *model_name* argument.
    2. Thread-local ``_active_model_override`` (set by agent.py).
    3. Global ``_current_model``.
    """
    name = model_name or _active_model_override.get() or _current_model
    model_max = get_model_max_context(name)
    if is_cloud_model(name):
        # Cloud: use full native context (fallback via heuristic)
        return model_max if model_max is not None else _estimate_context_heuristic(name)
    # Local: respect user's VRAM-controlling setting
    if model_max is not None:
        return min(_num_ctx, model_max)
    return _num_ctx


def get_tool_budget(fraction: float, *,
                    floor: int = 10_000, ceiling: int = 200_000) -> int:
    """Dynamic char budget for a tool result, scaled to the model's context.

    Returns a *character* limit suitable for string slicing.
    Assumes ~3 chars per token for the tokens-to-chars conversion.
    Clamped between *floor* and *ceiling* to prevent extremes.
    """
    ctx = get_context_size()
    return min(ceiling, max(floor, int(ctx * fraction * 3)))


def get_user_context_size() -> int:
    """Return the raw user-selected context size (before model capping)."""
    return _num_ctx


def set_context_size(size: int):
    """Change the context window size and recreate the LLM instance."""
    global _num_ctx, _llm_instance
    logger.info("Context size changed: %s → %s", _num_ctx, size)
    _num_ctx = size
    if is_cloud_model(_current_model):
        _llm_instance = _get_cloud_llm(_current_model)
    else:
        _llm_instance = ChatOllama(model=_current_model, num_ctx=_num_ctx)
    _save_settings({"model": _current_model, "context_size": _num_ctx})


def get_current_model() -> str:
    return _current_model


def _ollama_reachable(timeout: float = 1.0) -> bool:
    """Fast TCP probe to check if the Ollama server is listening."""
    import socket
    host = os.environ.get("OLLAMA_HOST", "127.0.0.1")
    port = 11434
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except (OSError, TimeoutError):
        return False


def list_local_models() -> list[str]:
    """Return names of models already downloaded in Ollama."""
    if not _ollama_mod or not _ollama_reachable():
        return []
    try:
        response = _ollama_mod.list()
        return sorted({m.model for m in response.models})
    except Exception:
        logger.debug("Could not list local Ollama models", exc_info=True)
        return []


def list_all_models() -> list[str]:
    """Return a combined, sorted list of local + popular + trending models."""
    local = list_local_models()
    return sorted(set(local + POPULAR_MODELS + _trending_ollama_cache))


def get_trending_models() -> list[str]:
    """Return the set of trending model names (for icon display)."""
    return list(_trending_ollama_cache)


def fetch_trending_ollama_models() -> list[str]:
    """Fetch trending models from ollama.com/api/tags.

    Returns a list of model name strings.  Safe to call from any thread.
    Results are cached in-memory for the session.
    """
    global _trending_ollama_cache, _trending_fetched
    if _trending_fetched:
        return _trending_ollama_cache
    try:
        import httpx
        resp = httpx.get("https://ollama.com/api/tags", timeout=10)
        resp.raise_for_status()
        data = resp.json().get("models", [])
        names = [m.get("name", "") for m in data if m.get("name")]
        _trending_ollama_cache = names
        _trending_fetched = True
        logger.info("Fetched %d trending Ollama models", len(names))
        return names
    except Exception as exc:
        logger.debug("Could not fetch trending Ollama models: %s", exc)
        _trending_fetched = True  # don't retry on failure
        return []


def is_model_local(model_name: str) -> bool:
    """Check whether a model is already downloaded."""
    local = list_local_models()
    return any(
        model_name == m
        or f"{model_name}:latest" == m
        or model_name == m.split(":")[0]
        for m in local
    )


def _looks_like_cloud_model(model_name: str) -> bool:
    """Heuristic: return True if *model_name* looks like a cloud model.

    Only used as a last-resort fallback when the persisted cache is empty
    AND the in-memory cache hasn't been populated yet.
    """
    if "/" in model_name:                       # OpenRouter format: provider/model
        return True
    if any(model_name.startswith(p) for p in _OPENAI_CHAT_PREFIXES):
        # Exclude known Ollama models that happen to share a prefix
        family = model_name.split(":")[0]
        if family in _TOOL_COMPATIBLE_FAMILIES:
            return False
        return True
    return False


def is_cloud_model(model_name: str) -> bool:
    """Return True if *model_name* is a known cloud model.

    Uses the persisted cache (loaded from disk at startup).  Falls back
    to the heuristic only when the cache has never been populated.
    """
    return model_name in _cloud_model_cache


def get_cloud_provider(model_name: str) -> str | None:
    """Return ``'openai'``, ``'openrouter'``, or ``None``."""
    info = _cloud_model_cache.get(model_name)
    return info["provider"] if info else None


# ── Provider emoji mapping ───────────────────────────────────────────────────
_PROVIDER_EMOJI: dict[str | None, str] = {
    "openai": "🟢",
    "openrouter": "🌐",
    "anthropic": "🔶",
    "google": "💎",
    None: "☁️",  # fallback for unknown cloud
}


def get_provider_emoji(model_name: str) -> str:
    """Return a provider-specific emoji for a model.

    Local models get 🖥️, cloud models get a provider-specific icon.
    """
    if not is_cloud_model(model_name):
        return "🖥️"
    prov = get_cloud_provider(model_name)
    return _PROVIDER_EMOJI.get(prov, _PROVIDER_EMOJI[None])


def is_cloud_available() -> bool:
    """Return True if any cloud API key is configured."""
    from api_keys import get_key
    return bool(get_key("OPENAI_API_KEY") or get_key("OPENROUTER_API_KEY"))


def is_openai_available() -> bool:
    """Return True if an OpenAI API key is configured."""
    from api_keys import get_key
    return bool(get_key("OPENAI_API_KEY"))


def is_openrouter_available() -> bool:
    """Return True if an OpenRouter API key is configured."""
    from api_keys import get_key
    return bool(get_key("OPENROUTER_API_KEY"))


def list_cloud_models(provider: str | None = None) -> list[str]:
    """Return cached cloud model IDs, optionally filtered by provider."""
    if provider:
        return [m for m, info in _cloud_model_cache.items() if info["provider"] == provider]
    return list(_cloud_model_cache.keys())


def list_starred_cloud_models() -> list[str]:
    """Return cloud models the user has starred (for the thread picker)."""
    from api_keys import get_cloud_config
    starred = set(get_cloud_config().get("starred_models", []))
    return [m for m in _cloud_model_cache if m in starred]


def star_cloud_model(model_id: str) -> None:
    """Add a model to the starred list."""
    from api_keys import get_cloud_config, set_cloud_config
    starred = list(get_cloud_config().get("starred_models", []))
    if model_id not in starred:
        starred.append(model_id)
        set_cloud_config("starred_models", starred)


def unstar_cloud_model(model_id: str) -> None:
    """Remove a model from the starred list."""
    from api_keys import get_cloud_config, set_cloud_config
    starred = list(get_cloud_config().get("starred_models", []))
    if model_id in starred:
        starred.remove(model_id)
        set_cloud_config("starred_models", starred)


def get_cloud_model_context(model_name: str) -> int:
    """Return the context window size for a cloud model.

    Resolution order:
    1. Cached value (from OpenRouter API or previous fetch).
    2. Context catalog (public OpenRouter data, no key needed).
    3. Prefix-based heuristic covering OpenAI / Anthropic / Gemini.
    4. Safe fallback (256K).
    """
    info = _cloud_model_cache.get(model_name)
    if info:
        return info["ctx"]
    return _catalog_or_heuristic(model_name)


def list_cloud_vision_models() -> list[str]:
    """Return cloud model IDs that support vision / image input."""
    return [m for m, info in _cloud_model_cache.items() if info.get("vision")]


def is_cloud_vision_model(model_name: str) -> bool:
    """Return True if *model_name* is a cloud model with vision support."""
    info = _cloud_model_cache.get(model_name)
    return bool(info and info.get("vision"))


def _get_cloud_llm(model_name: str):
    """Return a cached ChatOpenAI for an OpenAI-direct or OpenRouter model."""
    from langchain_openai import ChatOpenAI
    from api_keys import get_key

    provider = get_cloud_provider(model_name)
    if provider == "openai":
        api_key = get_key("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OpenAI API key not configured. Set it in Settings → Cloud.")
        base_url = None  # use default OpenAI endpoint
        headers = {}
    else:
        # OpenRouter (or fallback for unknown)
        api_key = get_key("OPENROUTER_API_KEY")
        if not api_key:
            raise ValueError("OpenRouter API key not configured. Set it in Settings → Cloud.")
        base_url = OPENROUTER_BASE_URL
        headers = {"HTTP-Referer": "https://github.com/hermes-thoth/thoth"}

    ctx = get_cloud_model_context(model_name)
    key = (model_name, ctx)
    if key not in _override_llm_cache:
        logger.info("Creating cloud LLM: model=%s via %s", model_name, provider or "openrouter")
        kwargs: dict = dict(model=model_name, api_key=api_key)
        if base_url:
            kwargs["base_url"] = base_url
        if headers:
            kwargs["default_headers"] = headers
        _override_llm_cache[key] = ChatOpenAI(**kwargs)
    return _override_llm_cache[key]


# ── Dynamic model fetching ──────────────────────────────────────────────────


def fetch_context_catalog() -> int:
    """Fetch the public OpenRouter model catalog (no API key needed).

    Populates ``_context_catalog`` with ``model_id → context_length``
    for every model OpenRouter lists.  Returns the number of entries.
    Safe to call from background threads.
    """
    import httpx

    try:
        resp = httpx.get(f"{OPENROUTER_BASE_URL}/models", timeout=15)
        resp.raise_for_status()
        data = resp.json().get("data", [])
    except Exception as exc:
        logger.warning("Failed to fetch context catalog: %s", exc)
        return 0

    count = 0
    with _context_catalog_lock:
        _context_catalog.clear()
        for m in data:
            mid = m.get("id", "")
            ctx = m.get("context_length")
            if mid and ctx and isinstance(ctx, int) and ctx > 0:
                _context_catalog[mid] = ctx
                count += 1
    _save_context_catalog()
    logger.info("Context catalog: %d models indexed", count)
    return count


def validate_openrouter_key(api_key: str) -> bool:
    """Validate an OpenRouter API key by hitting the auth endpoint.

    Returns True if the key is accepted, False otherwise.
    """
    import httpx

    try:
        resp = httpx.get(
            f"{OPENROUTER_BASE_URL}/auth/key",
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=10,
        )
        return resp.status_code == 200
    except Exception:
        return False


def _catalog_or_heuristic(model_id: str) -> int:
    """Resolve context size for any model via catalog → heuristic → fallback.

    Checks ``_context_catalog`` first (public OpenRouter data, covers all
    providers).  Falls back to prefix heuristic, then ``_CLOUD_CONTEXT_FALLBACK``.
    """
    # Try exact match in catalog (e.g. "openai/gpt-4o")
    with _context_catalog_lock:
        cat_val = _context_catalog.get(f"openai/{model_id}")
        if cat_val:
            return cat_val
        # Also try bare ID for OpenRouter-style keys
        cat_val = _context_catalog.get(model_id)
        if cat_val:
            return cat_val
    return _estimate_context_heuristic(model_id)


def fetch_cloud_models(provider: str) -> int:
    """Fetch available models from *provider* ('openai' or 'openrouter').

    Populates ``_cloud_model_cache``.  Returns the number of models found.
    Safe to call from background threads.
    """
    import httpx
    from api_keys import get_key

    if provider == "openai":
        api_key = get_key("OPENAI_API_KEY")
        if not api_key:
            return 0
        url = f"{OPENAI_BASE_URL}/models"
        headers = {"Authorization": f"Bearer {api_key}"}
    elif provider == "openrouter":
        api_key = get_key("OPENROUTER_API_KEY")
        if not api_key:
            return 0
        url = f"{OPENROUTER_BASE_URL}/models"
        headers = {"Authorization": f"Bearer {api_key}"}
    else:
        return 0

    try:
        resp = httpx.get(url, headers=headers, timeout=15)
        resp.raise_for_status()
        data = resp.json().get("data", [])
    except Exception as exc:
        logger.warning("Failed to fetch %s models: %s", provider, exc)
        return 0

    count = 0
    with _cloud_cache_lock:
        if provider == "openai":
            for m in data:
                mid = m.get("id", "")
                if not any(mid.startswith(p) for p in _OPENAI_CHAT_PREFIXES):
                    continue
                if any(s in mid for s in _OPENAI_SKIP_SUBSTRINGS):
                    continue
                ctx = _catalog_or_heuristic(mid)
                _cloud_model_cache[mid] = {
                    "label": mid, "ctx": ctx, "provider": "openai",
                    "vision": True,   # all current OpenAI chat models are multimodal
                }
                count += 1
        else:  # openrouter
            for m in data:
                mid = m.get("id", "")
                name = m.get("name", mid)
                ctx = m.get("context_length", 128_000)
                # Only include models with a '/' (provider/model format)
                if "/" not in mid:
                    continue
                # Detect vision capability from architecture.modality
                modality = m.get("architecture", {}).get("modality", "")
                has_vision = "image" in modality
                _cloud_model_cache[mid] = {
                    "label": name, "ctx": ctx, "provider": "openrouter",
                    "vision": has_vision,
                }
                count += 1
    logger.info("Fetched %d %s models", count, provider)
    return count


def refresh_cloud_models() -> int:
    """Clear cache and re-fetch from all configured providers.

    Also refreshes the context catalog (keyless) for accurate context sizes.
    If the current default model was a cloud model that is no longer available
    (e.g. API key removed), falls back to a local model or the built-in default.
    """
    global _current_model, _llm_instance
    # Remember current model before clearing
    _prev_model = _current_model
    _was_cloud = _prev_model in _cloud_model_cache

    # Fetch context catalog first so OpenAI models get accurate sizes
    fetch_context_catalog()
    with _cloud_cache_lock:
        _cloud_model_cache.clear()
    total = 0
    total += fetch_cloud_models("openai")
    total += fetch_cloud_models("openrouter")
    _save_cloud_cache()

    # If the default was a cloud model that's now gone, fall back gracefully
    if _was_cloud and _prev_model not in _cloud_model_cache:
        local = list_local_models()
        fallback = local[0] if local else DEFAULT_MODEL
        logger.warning(
            "Default cloud model '%s' no longer available (API key removed?) "
            "— falling back to '%s'", _prev_model, fallback,
        )
        _current_model = fallback
        _llm_instance = None  # lazy-recreate on next get_llm()
        _save_settings({"model": _current_model, "context_size": _num_ctx})

    return total


def is_tool_compatible(model_name: str) -> bool:
    """Check whether a model is in the known tool-compatible set.

    All cloud models (fetched dynamically) support tool calling."""
    if is_cloud_model(model_name):
        return True
    family = model_name.split(":")[0]
    return family in _TOOL_COMPATIBLE_FAMILIES


def check_tool_support(model_name: str) -> bool:
    """Send a minimal tool-call request to verify the model supports tools.

    Returns True if the model accepts tools, False if it rejects them (400).
    """
    if not _ollama_mod:
        return False
    try:
        _ollama_mod.chat(
            model=model_name,
            messages=[{"role": "user", "content": "hi"}],
            tools=[{
                "type": "function",
                "function": {
                    "name": "_ping",
                    "description": "test",
                    "parameters": {"type": "object", "properties": {}},
                },
            }],
        )
        return True
    except Exception as exc:
        if "does not support tools" in str(exc) or "400" in str(exc):
            return False
        logger.debug("Tool support check for %s failed: %s", model_name, exc)
        return True  # Network or other error — don't block


def pull_model(model_name: str):
    """Download a model from Ollama. Yields progress dicts when streamed."""
    if not _ollama_mod:
        raise RuntimeError("Ollama is not installed")
    return _ollama_mod.pull(model_name, stream=True)