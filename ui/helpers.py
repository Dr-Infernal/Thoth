"""Thoth UI — helper functions (config, file processing, native pickers, exports).

All functions are pure or side-effect-light.  They operate on the
parameters they receive — no hidden globals except the on-disk config.
"""

from __future__ import annotations

import asyncio
import base64 as _b64
import io
import json
import logging
import os
import pathlib
import subprocess
import sys
from datetime import datetime
from typing import Any

from ui.constants import (
    IMAGE_EXTENSIONS,
    DATA_EXTENSIONS,
    TEXT_EXTENSIONS,
    CHARS_PER_TOKEN_APPROX,
)

from models import get_context_size
from vision import VisionService

logger = logging.getLogger(__name__)


# ═════════════════════════════════════════════════════════════════════════════
# APP CONFIG PERSISTENCE
# ═════════════════════════════════════════════════════════════════════════════

_APP_CONFIG_DIR = pathlib.Path(
    os.environ.get("THOTH_DATA_DIR", pathlib.Path.home() / ".thoth")
)
_APP_CONFIG_PATH = _APP_CONFIG_DIR / "app_config.json"


def load_app_config() -> dict:
    if _APP_CONFIG_PATH.exists():
        try:
            return json.loads(_APP_CONFIG_PATH.read_text())
        except Exception:
            logger.warning("Failed to load app config from %s", _APP_CONFIG_PATH, exc_info=True)
            return {}
    return {}


def save_app_config(cfg: dict) -> None:
    _APP_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    _APP_CONFIG_PATH.write_text(json.dumps(cfg, indent=2))


def is_first_run() -> bool:
    return not load_app_config().get("onboarding_seen", False)


def mark_onboarding_seen() -> None:
    cfg = load_app_config()
    cfg["onboarding_seen"] = True
    save_app_config(cfg)


def is_setup_complete() -> bool:
    """Check whether the first-launch setup wizard has been completed."""
    return load_app_config().get("setup_complete", False)


def mark_setup_complete() -> None:
    cfg = load_app_config()
    cfg["setup_complete"] = True
    save_app_config(cfg)


# ═════════════════════════════════════════════════════════════════════════════
# FILE PROCESSING
# ═════════════════════════════════════════════════════════════════════════════

def file_budget(model_name: str | None = None) -> int:
    """Dynamic char budget for attached files: 35 % of the model's context window.

    For 32K context →  ~28K chars (7K tokens)
    For 128K context → ~114K chars (28K tokens)
    Falls back to 40K chars if context size is unavailable.
    """
    try:
        ctx = get_context_size(model_name)
    except Exception:
        ctx = 32_768
    return int(ctx * 0.35 * CHARS_PER_TOKEN_APPROX)


def strip_file_context(content: str) -> str:
    """Replace verbose file-context blocks with compact badges for display."""
    if "[Attached " not in content:
        return content
    parts = content.split("\n\n")
    badges: list[str] = []
    user_parts: list[str] = []
    for part in parts:
        if part.startswith("[Attached "):
            header = part.split("\n", 1)[0]
            after_colon = header.split(": ", 1)[1] if ": " in header else header
            fname = after_colon.split(",")[0].split("]")[0].strip()
            badges.append(f"📎 {fname}")
        elif part.startswith(("[Trimmed ", "[Truncated ", "--- Page ")):
            continue
        elif part.lstrip().startswith(("[Trimmed ", "[Truncated ")):
            continue
        else:
            user_parts.append(part)
    result_parts: list[str] = []
    if badges:
        result_parts.append(", ".join(badges))
    if user_parts:
        result_parts.append("\n\n".join(user_parts))
    return "\n\n".join(result_parts) if result_parts else content


def process_attached_files(
    files: list[dict],
    vision_svc: VisionService | None,
    attached_data_cache: dict[str, bytes],
    model_name: str | None = None,
) -> tuple[str, list[str], list[str]]:
    """Process uploaded files and return (context_text, image_b64_list, warnings).

    *files* is a list of ``{"name": str, "data": bytes}`` dicts.
    """
    budget = file_budget(model_name)
    context_parts: list[str] = []
    images_b64: list[str] = []
    warnings: list[str] = []

    for f in files:
        name = f["name"]
        data = f["data"]
        suffix = pathlib.Path(name).suffix.lower()

        if suffix in IMAGE_EXTENSIONS:
            b64 = _b64.b64encode(data).decode("ascii")
            images_b64.append(b64)
            if vision_svc and vision_svc.enabled:
                description = vision_svc.analyze(
                    data, f"Describe this image in detail. The filename is '{name}'."
                )
                context_parts.append(f"[Attached image: {name}]\n{description}")
            else:
                context_parts.append(f"[Attached image: {name} — vision is disabled, cannot analyze]")

        elif suffix == ".pdf":
            try:
                from pypdf import PdfReader
                reader = PdfReader(io.BytesIO(data))
                pages = []
                for i, page in enumerate(reader.pages):
                    text = page.extract_text() or ""
                    if text.strip():
                        pages.append(f"--- Page {i+1} ---\n{text}")
                    if sum(len(p) for p in pages) > budget:
                        pages.append(f"[Truncated — {len(reader.pages)} pages total, showing first {i+1}]")
                        warnings.append(f"📎 {name}: truncated — {len(reader.pages)} pages total, only first {i+1} shown")
                        break
                content = "\n".join(pages) if pages else "(No extractable text found)"
                context_parts.append(f"[Attached PDF: {name}, {len(reader.pages)} pages]\n{content}")
            except Exception as exc:
                context_parts.append(f"[Attached PDF: {name} — failed to extract text: {exc}]")

        elif suffix in DATA_EXTENSIONS:
            try:
                from data_reader import read_data_file
                buf = io.BytesIO(data)
                summary = read_data_file(buf, name=name, max_chars=budget)
                context_parts.append(f"[Attached data file: {name}]\n{summary}")
                attached_data_cache[name] = data
            except Exception as exc:
                context_parts.append(f"[Attached data file: {name} — failed to parse: {exc}]")

        elif suffix in TEXT_EXTENSIONS:
            try:
                text = data.decode("utf-8", errors="replace")
                if len(text) > budget:
                    warnings.append(f"📎 {name}: truncated — showing first {budget:,} of {len(text):,} chars")
                    text = text[:budget] + f"\n[Truncated — {len(data)} bytes total]"
                context_parts.append(f"[Attached file: {name}]\n{text}")
            except Exception as exc:
                context_parts.append(f"[Attached file: {name} — failed to read: {exc}]")
        else:
            context_parts.append(f"[Attached file: {name} — unsupported file type '{suffix}']")

    # ── Total-budget cap: proportionally shrink if combined text > budget ──
    total_chars = sum(len(p) for p in context_parts)
    if total_chars > budget and len(context_parts) > 0:
        for idx, part in enumerate(context_parts):
            share = len(part) / total_chars
            cap = max(2_000, int(budget * share))
            if len(part) > cap:
                warnings.append(f"📎 Trimmed to fit context — showing first {cap:,} of {len(part):,} chars")
                context_parts[idx] = (
                    part[:cap]
                    + f"\n[Trimmed to fit — showing first {cap:,} of {len(part):,} chars]"
                )

    return "\n\n".join(context_parts), images_b64, warnings


def load_thread_messages(thread_id: str) -> list[dict]:
    """Rebuild the message list from the LangGraph checkpoint."""
    import re as _re
    from agent import get_agent_graph
    from langchain_core.messages import AIMessage

    config = {"configurable": {"thread_id": thread_id}}
    try:
        agent = get_agent_graph()
        snapshot = agent.get_state(config)
        if snapshot and snapshot.values and "messages" in snapshot.values:
            msgs: list[dict] = []
            pending_tool_results: list[dict] = []
            pending_charts: list[str] = []
            for m in snapshot.values["messages"]:
                if m.type == "tool":
                    tool_name = getattr(m, "name", "") or "tool"
                    tool_content = m.content if isinstance(m.content, str) else str(m.content)

                    # Extract chart JSON from __CHART__: markers
                    if tool_content and tool_content.startswith("__CHART__:"):
                        marker_end = tool_content.find("\n\n", 10)
                        if marker_end == -1:
                            fig_json = tool_content[10:]
                            display_text = "Chart created"
                        else:
                            fig_json = tool_content[10:marker_end]
                            display_text = tool_content[marker_end + 2:]
                        pending_charts.append(fig_json)
                        tool_content = display_text

                    pending_tool_results.append({
                        "name": tool_name,
                        "content": tool_content,
                    })
                elif m.type == "human" and m.content:
                    pending_tool_results.clear()
                    pending_charts.clear()
                    # Check for user-attached images (base64 in multimodal content)
                    user_images: list[str] = []
                    if isinstance(m.content, list):
                        text_parts = []
                        for part in m.content:
                            if isinstance(part, dict):
                                if part.get("type") == "text":
                                    text_parts.append(part["text"])
                                elif part.get("type") == "image_url":
                                    url = part.get("image_url", {}).get("url", "")
                                    if url.startswith("data:image"):
                                        b64 = url.split(",", 1)[1] if "," in url else ""
                                        if b64:
                                            user_images.append(b64)
                        content = "\n".join(text_parts)
                    else:
                        content = m.content
                    msg_dict: dict = {"role": "user", "content": strip_file_context(content)}
                    if user_images:
                        msg_dict["images"] = user_images
                    msgs.append(msg_dict)
                elif m.type == "ai" and m.content:
                    ai_content = m.content
                    if isinstance(ai_content, list):
                        text_parts = []
                        for block in ai_content:
                            if isinstance(block, dict) and block.get("type") == "text":
                                text_parts.append(block.get("text", ""))
                            elif isinstance(block, str):
                                text_parts.append(block)
                        ai_content = "\n".join(text_parts)
                    if not isinstance(ai_content, str) or not ai_content.strip():
                        continue

                    # ── Recover thinking / reasoning content ──────────
                    thinking = ""
                    ak = getattr(m, "additional_kwargs", None) or {}
                    if ak.get("reasoning_content"):
                        thinking = ak["reasoning_content"]
                    # Some models embed <think>…</think> in content
                    think_parts = _re.findall(
                        r"<think>(.*?)</think>", ai_content, flags=_re.DOTALL
                    )
                    if think_parts:
                        thinking = (thinking + "\n" + "\n".join(think_parts)).strip()
                        ai_content = _re.sub(
                            r"<think>.*?</think>", "", ai_content, flags=_re.DOTALL
                        ).strip()
                    if not ai_content:
                        continue

                    msg_dict = {"role": "assistant", "content": ai_content}
                    if thinking:
                        msg_dict["thinking"] = thinking
                    if pending_tool_results:
                        msg_dict["tool_results"] = list(pending_tool_results)
                        pending_tool_results = []
                    if pending_charts:
                        msg_dict["charts"] = list(pending_charts)
                        pending_charts = []
                    msgs.append(msg_dict)

            # Flush orphaned tool results that were never attached to a
            # final AI message (e.g. recursion limit hit mid-tool-loop).
            if pending_tool_results:
                msgs.append({
                    "role": "assistant",
                    "content": "⚠️ The assistant was interrupted before it could finish (tool limit reached). Here's what it was working on:",
                    "tool_results": list(pending_tool_results),
                })
            return msgs
    except Exception:
        pass
    return []


# ═════════════════════════════════════════════════════════════════════════════
# EXPORT HELPERS
# ═════════════════════════════════════════════════════════════════════════════

def export_as_markdown(thread_name: str, messages: list[dict]) -> str:
    lines = [f"# {thread_name}\n"]
    lines.append(f"*Exported from Thoth on {datetime.now().strftime('%Y-%m-%d %H:%M')}*\n")
    lines.append("---\n")
    for msg in messages:
        role = "🧑 User" if msg["role"] == "user" else "𓁟 Thoth"
        lines.append(f"### {role}\n")
        lines.append(msg["content"] + "\n")
    return "\n".join(lines)


def export_as_text(thread_name: str, messages: list[dict]) -> str:
    lines = [thread_name]
    lines.append(f"Exported from Thoth on {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    lines.append("=" * 60)
    lines.append("")
    for msg in messages:
        role = "User" if msg["role"] == "user" else "Thoth"
        lines.append(f"[{role}]")
        lines.append(msg["content"])
        lines.append("")
    return "\n".join(lines)


def export_as_pdf(thread_name: str, messages: list[dict]) -> bytes:
    """Convert messages to a PDF document. Returns PDF bytes."""
    from fpdf import FPDF

    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=20)
    pdf.add_page()

    def _safe(text: str) -> str:
        return text.encode("latin-1", errors="replace").decode("latin-1")

    # Title
    pdf.set_font("Helvetica", "B", 18)
    pdf.cell(0, 12, _safe(thread_name), new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(128, 128, 128)
    pdf.cell(0, 6, f"Exported from Thoth on {datetime.now().strftime('%Y-%m-%d %H:%M')}",
             new_x="LMARGIN", new_y="NEXT")
    pdf.set_text_color(0, 0, 0)
    pdf.ln(4)
    pdf.set_draw_color(200, 200, 200)
    pdf.line(10, pdf.get_y(), 200, pdf.get_y())
    pdf.ln(6)

    for msg in messages:
        role = "User" if msg["role"] == "user" else "Thoth"
        pdf.set_font("Helvetica", "B", 11)
        if msg["role"] == "user":
            pdf.set_text_color(50, 100, 200)
        else:
            pdf.set_text_color(200, 160, 0)
        pdf.cell(0, 8, role, new_x="LMARGIN", new_y="NEXT")
        pdf.set_text_color(0, 0, 0)

        pdf.set_font("Helvetica", "", 10)
        safe_text = _safe(msg["content"])
        pdf.multi_cell(0, 5, safe_text)
        pdf.ln(4)

    return bytes(pdf.output())


# ═════════════════════════════════════════════════════════════════════════════
# CROSS-PLATFORM NATIVE FILE PICKERS
# ═════════════════════════════════════════════════════════════════════════════

def _pick_folder_native(title: str, initial_dir: str) -> str | None:
    """Platform-native folder picker (no tkinter dependency on macOS/Linux)."""
    if sys.platform == "darwin":
        script = f'POSIX path of (choose folder with prompt "{title}"'
        if initial_dir and os.path.isdir(initial_dir):
            script += f' default location POSIX file "{initial_dir}"'
        script += ')'
        try:
            r = subprocess.run(["osascript", "-e", script],
                               capture_output=True, text=True, timeout=120)
            if r.returncode == 0 and r.stdout.strip():
                return r.stdout.strip().rstrip("/")
        except Exception:
            pass
        return None

    if sys.platform.startswith("linux"):
        for cmd in (
            ["zenity", "--file-selection", "--directory", f"--title={title}"],
            ["kdialog", "--getexistingdirectory", initial_dir or ".",
             "--title", title],
        ):
            try:
                r = subprocess.run(cmd, capture_output=True, text=True,
                                   timeout=120)
                if r.returncode == 0 and r.stdout.strip():
                    return r.stdout.strip()
            except FileNotFoundError:
                continue
            except Exception:
                pass

    # Windows / fallback: tkinter
    try:
        import tkinter as tk
        from tkinter import filedialog
        root = tk.Tk(); root.withdraw(); root.attributes("-topmost", True)
        result = filedialog.askdirectory(title=title,
                                         initialdir=initial_dir or None)
        root.destroy()
        return result or None
    except ImportError:
        return None


def _pick_file_native(
    title: str, initial_dir: str, filetypes: list[tuple[str, str]] | None,
) -> str | None:
    """Platform-native file picker (no tkinter dependency on macOS/Linux)."""
    if sys.platform == "darwin":
        script = f'POSIX path of (choose file with prompt "{title}"'
        if initial_dir and os.path.isdir(initial_dir):
            script += f' default location POSIX file "{initial_dir}"'
        if filetypes:
            exts = []
            for _, pattern in filetypes:
                for part in pattern.split(";"):
                    ext = part.strip().lstrip("*.").lower()
                    if ext:
                        exts.append(f'"{ext}"')
            if exts:
                script += f' of type {{{", ".join(exts)}}}'
        script += ')'
        try:
            r = subprocess.run(["osascript", "-e", script],
                               capture_output=True, text=True, timeout=120)
            if r.returncode == 0 and r.stdout.strip():
                return r.stdout.strip()
        except Exception:
            pass
        return None

    if sys.platform.startswith("linux"):
        filt = ""
        if filetypes:
            filt = " ".join(p for _, p in filetypes)
        for cmd in (
            ["zenity", "--file-selection", f"--title={title}"]
            + ([f"--file-filter={filt}"] if filt else []),
            ["kdialog", "--getopenfilename", initial_dir or ".",
             filt or "*", "--title", title],
        ):
            try:
                r = subprocess.run(cmd, capture_output=True, text=True,
                                   timeout=120)
                if r.returncode == 0 and r.stdout.strip():
                    return r.stdout.strip()
            except FileNotFoundError:
                continue
            except Exception:
                pass

    # Windows / fallback: tkinter
    try:
        import tkinter as tk
        from tkinter import filedialog
        root = tk.Tk(); root.withdraw(); root.attributes("-topmost", True)
        result = filedialog.askopenfilename(
            title=title, initialdir=initial_dir or None,
            filetypes=filetypes or [],
        )
        root.destroy()
        return result or None
    except ImportError:
        return None


async def browse_folder(title: str = "Select folder",
                        initial_dir: str = "") -> str | None:
    return await asyncio.to_thread(_pick_folder_native, title, initial_dir)


async def browse_file(
    title: str = "Select file",
    initial_dir: str = "",
    filetypes: list[tuple[str, str]] | None = None,
) -> str | None:
    return await asyncio.to_thread(_pick_file_native, title, initial_dir,
                                   filetypes)
