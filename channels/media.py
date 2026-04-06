"""
Thoth – Shared Media Pipeline
================================
Common helpers for processing inbound media from any channel:

* **Voice notes** → transcribe via faster-whisper
* **Photos / images** → analyse via Vision service
* **Documents / files** → save to inbox directory

Every channel's inbound handler calls these instead of re-implementing
the same logic.
"""

from __future__ import annotations

import logging
import os
import pathlib
import tempfile
import time

log = logging.getLogger("thoth.channels.media")

_DATA_DIR = pathlib.Path(
    os.environ.get("THOTH_DATA_DIR", pathlib.Path.home() / ".thoth")
)
_INBOX_DIR = _DATA_DIR / "inbox"


# ── Voice → Text ─────────────────────────────────────────────────────

def transcribe_audio(data: bytes, file_ext: str = ".ogg") -> str:
    """Transcribe audio bytes to text via faster-whisper.

    Parameters
    ----------
    data : bytes
        Raw audio file contents (OGG/Opus, WebM, MP3, WAV, …).
    file_ext : str
        File extension hint so faster-whisper picks the right decoder.

    Returns
    -------
    str
        Transcribed text (empty string on failure).
    """
    from voice import get_voice_service

    svc = get_voice_service()
    svc._ensure_whisper()

    # Write to temp file — faster-whisper.transcribe() accepts paths
    # and internally uses ffmpeg to decode any format.
    with tempfile.NamedTemporaryFile(suffix=file_ext, delete=False) as tmp:
        tmp.write(data)
        tmp_path = tmp.name

    try:
        segs, _ = svc._whisper_model.transcribe(
            tmp_path, beam_size=5, language="en", vad_filter=True,
        )
        text = " ".join(s.text.strip() for s in segs).strip()
        log.info("Transcribed audio (%d bytes) → %d chars", len(data), len(text))
        return text
    except Exception as exc:
        log.error("Audio transcription failed: %s", exc)
        return ""
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass


# ── Photo → Analysis ─────────────────────────────────────────────────

def analyze_image(data: bytes,
                  question: str = "Describe this image in detail.") -> str:
    """Analyse image bytes via the Vision service.

    Returns the model's text description (empty on failure).
    """
    try:
        from vision import VisionService
        svc = VisionService()
        result = svc.analyze(data, question)
        log.info("Image analysis (%d bytes) → %d chars", len(data), len(result))
        return result
    except Exception as exc:
        log.error("Image analysis failed: %s", exc)
        return ""


# ── Document / File → Save & Extract ─────────────────────────────────

def save_inbound_file(data: bytes, filename: str) -> pathlib.Path:
    """Persist an inbound file to ``~/.thoth/inbox/``.

    Returns the absolute ``Path`` to the saved file.
    """
    _INBOX_DIR.mkdir(parents=True, exist_ok=True)

    # Prefix with timestamp to avoid collisions
    ts = int(time.time())
    safe_name = f"{ts}_{filename}"
    dest = _INBOX_DIR / safe_name
    dest.write_bytes(data)
    log.info("Saved inbound file: %s (%d bytes)", dest, len(data))
    return dest


# File-type sets (mirrors ui/constants.py — kept here to avoid UI dependency)
_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp"}
_DATA_EXTENSIONS = {".csv", ".tsv", ".xlsx", ".xls", ".json", ".jsonl"}
_TEXT_EXTENSIONS = {
    ".txt", ".md", ".py", ".js", ".ts", ".html", ".css", ".xml", ".yaml",
    ".yml", ".toml", ".ini", ".cfg", ".log", ".sh", ".bat", ".ps1", ".sql",
    ".r", ".java", ".c", ".cpp", ".h", ".cs", ".go", ".rs", ".rb", ".php",
    ".swift", ".kt", ".lua", ".pl",
}


def extract_document_text(data: bytes, filename: str,
                          max_chars: int = 80_000) -> str:
    """Extract readable text from a file's raw bytes.

    Supports PDF, plain-text / code, and tabular data files.
    Returns the extracted text, or an empty string if the file type is
    unsupported or extraction fails.
    """
    import io

    suffix = pathlib.Path(filename).suffix.lower()

    # ── PDF ───────────────────────────────────────────────────────────
    if suffix == ".pdf":
        try:
            from pypdf import PdfReader
            reader = PdfReader(io.BytesIO(data))
            pages: list[str] = []
            for i, page in enumerate(reader.pages):
                text = page.extract_text() or ""
                if text.strip():
                    pages.append(f"--- Page {i + 1} ---\n{text}")
                if sum(len(p) for p in pages) > max_chars:
                    pages.append(
                        f"[Truncated — {len(reader.pages)} pages total, "
                        f"showing first {i + 1}]"
                    )
                    break
            content = "\n".join(pages) if pages else ""
            if content:
                log.info("Extracted PDF text: %s (%d chars from %d pages)",
                         filename, len(content), len(reader.pages))
            return content
        except Exception as exc:
            log.error("PDF text extraction failed for %s: %s", filename, exc)
            return ""

    # ── Tabular data (CSV, Excel, JSON) ──────────────────────────────
    if suffix in _DATA_EXTENSIONS:
        try:
            from data_reader import read_data_file
            buf = io.BytesIO(data)
            summary = read_data_file(buf, name=filename, max_chars=max_chars)
            log.info("Extracted data file: %s (%d chars)", filename, len(summary))
            return summary
        except Exception as exc:
            log.error("Data file extraction failed for %s: %s", filename, exc)
            return ""

    # ── Plain text / code ────────────────────────────────────────────
    if suffix in _TEXT_EXTENSIONS:
        try:
            text = data.decode("utf-8", errors="replace")
            if len(text) > max_chars:
                text = text[:max_chars] + f"\n[Truncated — {len(data):,} bytes total]"
            log.info("Read text file: %s (%d chars)", filename, len(text))
            return text
        except Exception as exc:
            log.error("Text file read failed for %s: %s", filename, exc)
            return ""

    return ""
