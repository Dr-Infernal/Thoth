"""Image generation tool — generate and edit images via OpenAI / OpenRouter.

The agent calls ``generate_image`` to create images from text prompts, or
``edit_image`` to modify an existing image (pasted, last generated, or from
a file path).  Generated images are rendered inline in the chat via the
``captured_images`` pipeline (same as vision / browser screenshots).

The user picks a provider+model combination in Settings → Models (e.g.
``openai/gpt-image-1.5``).  Only providers whose API key is configured
appear in the dropdown.
"""

from __future__ import annotations

import base64
import logging
from pathlib import Path
from typing import Optional

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

from tools.base import BaseTool
from tools import registry

logger = logging.getLogger(__name__)

# ── Available image generation models ────────────────────────────────────
IMAGE_GEN_MODELS = [
    {"id": "gpt-image-1.5", "label": "GPT Image 1.5 (Best quality)"},
    {"id": "gpt-image-1", "label": "GPT Image 1"},
    {"id": "gpt-image-1-mini", "label": "GPT Image 1 Mini (Cheapest)"},
]

# Provider definitions — only providers with an images API
_PROVIDERS = {
    "openai": {"key": "OPENAI_API_KEY", "label": "OpenAI", "emoji": "🟢"},
}

DEFAULT_MODEL = "openai/gpt-image-1.5"

IMAGE_SIZES = ["auto", "1024x1024", "1536x1024", "1024x1536"]
IMAGE_QUALITIES = ["auto", "low", "medium", "high"]

# ── Side-channel for generated images ────────────────────────────────────
# The streaming layer reads and clears this after generate/edit calls,
# same pattern as filesystem_tool._last_displayed_image.
_last_generated_image: str | None = None  # base64-encoded image data

# ── Attachment cache for pasted/attached images ──────────────────────────
# Populated by ui/streaming.py before agent invocation.
_image_cache: dict[str, bytes] = {}  # filename → raw bytes
_image_cache_thread_id: str | None = None  # thread that owns __last_generated__


def get_and_clear_last_image() -> str | None:
    """Return and clear the pending generated image, if any."""
    global _last_generated_image
    img = _last_generated_image
    _last_generated_image = None
    return img


# ── Provider resolution ──────────────────────────────────────────────────

def _parse_model_config(value: str) -> tuple[str, str]:
    """Parse a 'provider/model' config string → (provider, model_id).

    Falls back gracefully for bare model names (legacy configs).
    """
    if "/" in value:
        provider, model_id = value.split("/", 1)
        return provider, model_id
    # Legacy bare model name — default to openai
    return "openai", value


def get_available_image_models() -> dict[str, str]:
    """Return {config_value: display_label} for models whose provider key is set.

    Used by the Settings UI to populate the model dropdown.
    """
    from api_keys import get_key

    opts: dict[str, str] = {}
    for prov_id, prov in _PROVIDERS.items():
        if not get_key(prov["key"]):
            continue
        for m in IMAGE_GEN_MODELS:
            config_val = f"{prov_id}/{m['id']}"
            opts[config_val] = f"{prov['emoji']}  {m['label']}  ({prov['label']})"
    return opts


def _get_client():
    """Return (openai.OpenAI client, provider_label) based on the user's model selection."""
    from api_keys import get_key

    provider, _ = _parse_model_config(_get_configured_selection())
    prov_info = _PROVIDERS.get(provider)
    if not prov_info:
        raise RuntimeError(
            f"Unknown image generation provider '{provider}'. "
            "Please select a valid model in Settings → Models."
        )

    api_key = get_key(prov_info["key"])
    if not api_key:
        raise RuntimeError(
            f"No API key for {prov_info['label']}. "
            f"Please add your {prov_info['label']} API key in Settings → Cloud."
        )

    import openai
    return openai.OpenAI(api_key=api_key), prov_info["label"]


def _get_configured_selection() -> str:
    """Return the raw 'provider/model' string from tool config."""
    tool = registry.get_tool("image_gen")
    if tool:
        val = tool.get_config("model", DEFAULT_MODEL)
        if val:
            return val
    return DEFAULT_MODEL


def _get_configured_model() -> str:
    """Return just the model ID (e.g. 'gpt-image-1.5') from the stored config."""
    _, model_id = _parse_model_config(_get_configured_selection())
    return model_id


# ── Image resolution helpers ─────────────────────────────────────────────

def _detect_mime(data: bytes) -> str:
    """Detect image MIME type from magic bytes.  Defaults to image/png."""
    if data[:4] == b"\xff\xd8\xff\xe0" or data[:4] == b"\xff\xd8\xff\xe1":
        return "image/jpeg"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    return "image/png"


def _resolve_image_source(image_source: str) -> bytes:
    """Resolve an image_source string to raw bytes.

    Priority:
      1. "last" → last generated image (from _last_generated_image backup)
      2. Key match in _image_cache → pasted/attached image
      3. File path on disk
    """
    # "last" — use the last generated image
    if image_source.strip().lower() == "last":
        last_b64 = _image_cache.get("__last_generated__")
        if last_b64:
            return last_b64
        raise ValueError(
            "No previously generated image available. "
            "Generate an image first, then use edit_image with image_source='last'."
        )

    # Check attachment cache (pasted images)
    if image_source in _image_cache:
        return _image_cache[image_source]

    # Partial filename match in cache
    for cached_name, cached_data in _image_cache.items():
        if cached_name != "__last_generated__" and image_source.lower() in cached_name.lower():
            return cached_data

    # File path on disk
    path = Path(image_source).expanduser()
    if path.exists() and path.is_file():
        return path.read_bytes()

    # Try workspace-relative
    tool = registry.get_tool("filesystem")
    if tool:
        ws_root = tool.get_config("workspace_root", "")
        if ws_root:
            ws_path = Path(ws_root) / image_source
            if ws_path.exists() and ws_path.is_file():
                return ws_path.read_bytes()

    raise ValueError(
        f"Could not find image '{image_source}'. "
        "Use 'last' for the last generated image, paste/attach an image, "
        "or provide a valid file path."
    )


# ── Core generation functions ────────────────────────────────────────────

def _generate_image(
    prompt: str,
    size: str = "auto",
    quality: str = "auto",
) -> str:
    """Generate an image from a text prompt."""
    global _last_generated_image

    client, provider = _get_client()
    model = _get_configured_model()

    kwargs: dict = {
        "model": model,
        "prompt": prompt,
        "n": 1,
        "size": size if size != "auto" else "1024x1024",
    }
    if quality != "auto":
        kwargs["quality"] = quality

    logger.info("generate_image: model=%s, size=%s, quality=%s, provider=%s",
                model, size, quality, provider)

    try:
        response = client.images.generate(**kwargs)
    except Exception as e:
        logger.error("Image generation failed: %s", e, exc_info=True)
        return f"Image generation failed: {e}"

    # Extract image data
    image_data = response.data[0]
    if hasattr(image_data, "b64_json") and image_data.b64_json:
        b64_str = image_data.b64_json
    elif hasattr(image_data, "url") and image_data.url:
        # Download the URL and convert to base64
        import urllib.request
        with urllib.request.urlopen(image_data.url) as resp:
            b64_str = base64.b64encode(resp.read()).decode("ascii")
    else:
        return "Image generation returned no image data."

    # Store in side-channel for UI rendering
    _last_generated_image = b64_str
    # Also store in cache for edit_image "last" reference
    _image_cache["__last_generated__"] = base64.b64decode(b64_str)

    revised_prompt = getattr(image_data, "revised_prompt", None)
    result = f"Image generated successfully. Model: {model} | Size: {kwargs['size']} | Provider: {provider}"
    if revised_prompt:
        result += f"\nRevised prompt: {revised_prompt}"
    return result


def _edit_image(
    prompt: str,
    image_source: str = "last",
    size: str = "auto",
    quality: str = "auto",
) -> str:
    """Edit an existing image using a text prompt."""
    global _last_generated_image

    # Resolve the source image to raw bytes
    try:
        image_bytes = _resolve_image_source(image_source)
    except ValueError as e:
        return str(e)

    client, provider = _get_client()
    model = _get_configured_model()

    # The GPT Image API requires image[] (list) with explicit MIME type;
    # raw bytes default to application/octet-stream which is rejected.
    mime = _detect_mime(image_bytes)
    image_file = ("image.png", image_bytes, mime)

    kwargs: dict = {
        "model": model,
        "prompt": prompt,
        "image": [image_file],
        "n": 1,
        "size": size if size != "auto" else "1024x1024",
    }

    logger.info("edit_image: model=%s, size=%s, source=%s, provider=%s",
                model, size, image_source, provider)

    try:
        response = client.images.edit(**kwargs)
    except Exception as e:
        logger.error("Image edit failed: %s", e, exc_info=True)
        return f"Image edit failed: {e}"

    # Extract image data
    image_data = response.data[0]
    if hasattr(image_data, "b64_json") and image_data.b64_json:
        b64_str = image_data.b64_json
    elif hasattr(image_data, "url") and image_data.url:
        import urllib.request
        with urllib.request.urlopen(image_data.url) as resp:
            b64_str = base64.b64encode(resp.read()).decode("ascii")
    else:
        return "Image edit returned no image data."

    # Store in side-channel for UI rendering
    _last_generated_image = b64_str
    _image_cache["__last_generated__"] = base64.b64decode(b64_str)

    revised_prompt = getattr(image_data, "revised_prompt", None)
    result = f"Image edited successfully. Model: {model} | Size: {kwargs['size']} | Provider: {provider}"
    if revised_prompt:
        result += f"\nRevised prompt: {revised_prompt}"
    return result


# ── Pydantic input schemas ───────────────────────────────────────────────

class _GenerateImageInput(BaseModel):
    prompt: str = Field(
        description=(
            "A detailed description of the image to generate. Be specific "
            "about style, composition, colors, and subject matter. "
            "Example: 'A watercolor painting of a sunset over mountains "
            "with warm orange and purple tones'"
        )
    )
    size: str = Field(
        default="auto",
        description=(
            "Image dimensions. Options: 'auto' (default 1024x1024), "
            "'1024x1024' (square), '1536x1024' (landscape), "
            "'1024x1536' (portrait)."
        ),
    )
    quality: str = Field(
        default="auto",
        description=(
            "Image quality. Options: 'auto' (default), 'low' (fastest), "
            "'medium', 'high' (best quality, slower)."
        ),
    )


class _EditImageInput(BaseModel):
    prompt: str = Field(
        description=(
            "What to change in the image. Be specific about the edit. "
            "Example: 'Add a red hat to the cat', 'Remove the background', "
            "'Make it look more realistic'"
        )
    )
    image_source: str = Field(
        default="last",
        description=(
            "Where to get the image to edit. Use 'last' for the last "
            "generated image (default). Use the filename for an attached/"
            "pasted image (e.g. 'photo.jpg'). Or use a file path on disk."
        ),
    )
    size: str = Field(
        default="auto",
        description=(
            "Output image dimensions. Options: 'auto' (same as original), "
            "'1024x1024' (square), '1536x1024' (landscape), "
            "'1024x1536' (portrait)."
        ),
    )
    quality: str = Field(
        default="auto",
        description=(
            "Image quality. Options: 'auto' (default), 'low' (fastest), "
            "'medium', 'high' (best quality, slower)."
        ),
    )


# ── Tool registration ───────────────────────────────────────────────────

class ImageGenTool(BaseTool):

    @property
    def name(self) -> str:
        return "image_gen"

    @property
    def display_name(self) -> str:
        return "🎨 Image Generation"

    @property
    def description(self) -> str:
        return (
            "Generate images from text descriptions and edit existing images. "
            "Creates images using AI models (GPT Image). Requires an OpenAI "
            "or OpenRouter API key."
        )

    @property
    def enabled_by_default(self) -> bool:
        # Only enable if a cloud key is available
        from models import is_cloud_available
        return is_cloud_available()

    @property
    def config_schema(self) -> dict[str, dict]:
        # The model selector is rendered directly in the Models tab
        # (settings.py) using get_available_image_models(), not via
        # the generic config_schema renderer.
        return {}

    def as_langchain_tools(self) -> list:
        return [
            StructuredTool.from_function(
                func=_generate_image,
                name="generate_image",
                description=(
                    "Generate an image from a text description. Use this "
                    "when the user asks you to create, draw, design, or "
                    "generate any kind of image, illustration, artwork, "
                    "diagram, logo, or visual content. Provide a detailed "
                    "prompt describing the desired image."
                ),
                args_schema=_GenerateImageInput,
            ),
            StructuredTool.from_function(
                func=_edit_image,
                name="edit_image",
                description=(
                    "Edit or modify an existing image using a text prompt. "
                    "Use 'last' to edit the most recently generated image, "
                    "or specify a filename for a pasted/attached image, or "
                    "a file path. Use this when the user wants to change, "
                    "modify, adjust, or transform an existing image."
                ),
                args_schema=_EditImageInput,
            ),
        ]

    def execute(self, query: str) -> str:
        return _generate_image(prompt=query)


registry.register(ImageGenTool())
