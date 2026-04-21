"""Designer — AI-powered content helpers.

Provides functions for:
- AI image generation → raw bytes or legacy base64 <img> helpers
- AI copy refinement → rewrite text elements with LLM
- Data-viz chart embedding → Plotly figure → static PNG helpers
"""

from __future__ import annotations

import base64
import io
import json
import logging
import re
import uuid
from typing import Optional

logger = logging.getLogger(__name__)


# ── AI Image Generation ──────────────────────────────────────────────────────

def generate_image_bytes(
    prompt: str,
    *,
    size: str = "auto",
) -> tuple[bytes, str]:
    """Generate an image and return raw bytes plus the detected MIME type."""

    try:
        from tools.image_gen_tool import _detect_mime, _generate_image, _resolve_image_source
    except ImportError as exc:
        raise ValueError("image generation tool is not available") from exc

    result = _generate_image(prompt, size=size)
    try:
        image_bytes = _resolve_image_source("last")
    except Exception as exc:
        raise ValueError(f"image generation returned no data. Result: {result}") from exc
    return image_bytes, _detect_mime(image_bytes)

def generate_image_html(
    prompt: str,
    width: int = 800,
    height: int = 500,
    position: str = "bottom",
    size: str = "auto",
) -> str:
    """Generate an image and return an <img> tag with base64 data.

    Parameters
    ----------
    prompt : str
        Text prompt for the image generator.
    width, height : int
        Display dimensions in the design (CSS pixels).
    position : str
        Ignored here (caller decides where to insert).
    size : str
        Passed to image generator ('auto', '1024x1024', etc.).

    Returns
    -------
    str
        An ``<img src="data:image/png;base64,...">`` HTML string,
        or an error message string starting with "Error:".
    """
    try:
        image_bytes, mime = generate_image_bytes(prompt, size=size)
    except ValueError as exc:
        return f"Error: {exc}"

    img_id = f"ai-img-{uuid.uuid4().hex[:8]}"
    b64 = base64.b64encode(image_bytes).decode()
    tag = (
        f'<img id="{img_id}" src="data:{mime};base64,{b64}" '
        f'alt="{_escape_attr(prompt)}" '
        f'style="width:{width}px; max-width:100%; height:auto; display:block; margin:16px auto;" />'
    )
    return tag


def insert_image_into_page(
    page_html: str,
    img_tag: str,
    position: str = "bottom",
) -> str:
    """Insert an <img> tag into page HTML at the given position.

    Parameters
    ----------
    position : str
        'top' → after <body>, 'bottom' → before </body>,
        'replace:SELECTOR' → replace first matching element (future).
    """
    if position == "top":
        # Insert right after <body...>
        m = re.search(r"(<body[^>]*>)", page_html, re.IGNORECASE)
        if m:
            idx = m.end()
            return page_html[:idx] + "\n" + img_tag + "\n" + page_html[idx:]
    # Default: before </body>
    m = re.search(r"(</body>)", page_html, re.IGNORECASE)
    if m:
        idx = m.start()
        return page_html[:idx] + "\n" + img_tag + "\n" + page_html[idx:]
    # Fallback: append
    return page_html + "\n" + img_tag


# ── AI Copy Refinement ───────────────────────────────────────────────────────

_REFINE_ACTIONS = {
    "shorten": "Make this text significantly shorter and more concise while keeping the key message.",
    "expand": "Expand this text with more detail, examples, or supporting points.",
    "professional": "Rewrite this text in a formal, professional tone.",
    "casual": "Rewrite this text in a friendly, casual, conversational tone.",
    "persuasive": "Rewrite this text to be more persuasive and compelling.",
    "simplify": "Simplify this text so a general audience can easily understand it.",
    "bullets": "Convert this text into a clean bulleted list.",
    "paragraph": "Convert this text into flowing paragraph form.",
}


def refine_text(
    text: str,
    action: str,
    custom_instruction: str = "",
) -> str:
    """Refine text using the configured LLM.

    Parameters
    ----------
    text : str
        The original text to refine.
    action : str
        One of the predefined actions or 'custom'.
    custom_instruction : str
        Used when action == 'custom'.

    Returns
    -------
    str
        The refined text, or the original on failure.
    """
    if action == "custom" and custom_instruction:
        instruction = custom_instruction
    else:
        instruction = _REFINE_ACTIONS.get(action, _REFINE_ACTIONS["professional"])

    system_prompt = (
        "You are a copywriting assistant for a visual design tool. "
        "Refine the given text according to the instruction. "
        "Return ONLY the refined text — no explanations, no quotes, no markdown formatting. "
        "Preserve the approximate structure (headings stay headings, lists stay lists) "
        "unless the instruction explicitly asks to change it."
    )
    user_prompt = f"INSTRUCTION: {instruction}\n\nTEXT TO REFINE:\n{text}"

    try:
        from models import get_llm
        from langchain_core.messages import SystemMessage, HumanMessage
        llm = get_llm()
        resp = llm.invoke([SystemMessage(content=system_prompt), HumanMessage(content=user_prompt)])
        refined = resp.content.strip() if resp and resp.content else text
        return refined if refined else text
    except Exception:
        logger.exception("AI copy refinement failed")
        return text


def refine_text_in_html(
    page_html: str,
    tag: str,
    old_text: str,
    action: str,
    custom_instruction: str = "",
) -> tuple[str, str]:
    """Refine a text element in-place within page HTML.

    Returns (new_html, refined_text).
    """
    refined = refine_text(old_text, action, custom_instruction)
    if refined == old_text:
        return page_html, old_text

    from designer.interaction import patch_html_text
    new_html = patch_html_text(page_html, "", tag, old_text, refined)
    return new_html, refined


def generate_speaker_notes(
    page_title: str,
    page_summary: dict,
    existing_notes: str = "",
) -> str:
    """Generate concise presenter notes for a single slide."""

    system_prompt = (
        "You write speaker notes for a presentation slide. "
        "Return plain text only. No markdown bullets, no XML, no commentary. "
        "Write concise notes a presenter can read while speaking: the core message, "
        "the important supporting detail, and a short transition if it is obvious."
    )
    user_prompt = (
        f"SLIDE TITLE: {page_title or 'Untitled'}\n\n"
        f"SLIDE SUMMARY JSON:\n{json.dumps(page_summary, indent=2)}\n\n"
        f"EXISTING NOTES:\n{existing_notes or '(none)'}\n\n"
        "Write 3-6 short speaker-note lines for this slide."
    )

    try:
        from models import get_llm
        from langchain_core.messages import HumanMessage, SystemMessage

        llm = get_llm()
        resp = llm.invoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt),
        ])
        notes = resp.content.strip() if resp and resp.content else ""
        return notes or existing_notes
    except Exception:
        logger.exception("Speaker note generation failed")
        return existing_notes or ""


# ── Data-Viz Chart Embedding ─────────────────────────────────────────────────

def build_chart_png(
    chart_type: str,
    data_csv: str,
    title: str = "",
    colors: Optional[list[str]] = None,
    width: int = 800,
    height: int = 500,
) -> bytes:
    """Build a Plotly chart from CSV data and return PNG bytes.

    Parameters
    ----------
    chart_type : str
        Any supported chart type (bar, line, pie, scatter, etc.).
    data_csv : str
        Inline CSV data (header row + data rows).
    title : str
        Chart title.
    colors : list[str] | None
        Custom color sequence (brand colors).
    width, height : int
        Output image dimensions in pixels.

    Returns
    -------
    bytes
        PNG image bytes.
    """
    import pandas as pd

    df = pd.read_csv(io.StringIO(data_csv))
    if df.empty:
        raise ValueError("CSV data is empty.")

    from tools.chart_tool import _build_figure
    fig = _build_figure(df, chart_type, x=None, y=None, color=None, title=title)

    if colors:
        fig.update_layout(colorway=colors)

    # Use kaleido for static export
    png_bytes = fig.to_image(format="png", width=width, height=height, scale=2)
    return png_bytes


def build_chart_interactive_html(
    chart_type: str,
    data_csv: str,
    title: str = "",
    colors: Optional[list[str]] = None,
    width: int = 800,
    height: int = 500,
) -> str:
    """Build a Plotly chart and return an HTML <div> with inline Plotly.js.

    This produces an interactive chart for the live preview.
    """
    import pandas as pd
    import plotly.io as pio

    df = pd.read_csv(io.StringIO(data_csv))
    if df.empty:
        raise ValueError("CSV data is empty.")

    from tools.chart_tool import _build_figure
    fig = _build_figure(df, chart_type, x=None, y=None, color=None, title=title)

    if colors:
        fig.update_layout(colorway=colors)

    fig.update_layout(width=width, height=height)

    chart_id = f"chart-{uuid.uuid4().hex[:8]}"
    html = pio.to_html(fig, full_html=False, include_plotlyjs="cdn", div_id=chart_id)
    return html


def chart_to_img_tag(
    chart_type: str,
    data_csv: str,
    title: str = "",
    colors: Optional[list[str]] = None,
    width: int = 800,
    height: int = 500,
) -> str:
    """Build a chart and return a static <img> tag with base64 PNG."""
    png_bytes = build_chart_png(chart_type, data_csv, title, colors, width, height)
    b64 = base64.b64encode(png_bytes).decode()
    safe_title = _escape_attr(title or chart_type)
    return (
        f'<img src="data:image/png;base64,{b64}" '
        f'alt="{safe_title}" '
        f'style="width:{width}px; max-width:100%; height:auto; display:block; margin:16px auto;" />'
    )


# ── Helpers ──────────────────────────────────────────────────────────────────

def _escape_attr(s: str) -> str:
    """Escape a string for use in an HTML attribute."""
    return s.replace("&", "&amp;").replace('"', "&quot;").replace("<", "&lt;").replace(">", "&gt;")
