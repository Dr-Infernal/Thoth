"""Thoth UI — constants, patterns and extension sets.

Pure data — no side-effects on import.
"""

from __future__ import annotations

import re

# ═════════════════════════════════════════════════════════════════════════════
# WELCOME / EXAMPLES
# ═════════════════════════════════════════════════════════════════════════════

_WELCOME_BODY = """\

---

🤖 **Agent** — I autonomously pick from 23 tools to answer your questions — search the web, read files, send emails, check your calendar, and more.

🧠 **Memory** — I build a personal knowledge graph from our conversations — people, places, preferences, and their connections — and remember across sessions.

🧩 **Skills** — 9 built-in instruction packs (Deep Research, Daily Briefing, Humanizer, and more). Enable them in Settings → Skills to shape how I respond.

⚡ **Tasks** — Create scheduled automations — daily briefings, email digests, research summaries — from the Tasks tab or just ask.

🌐 **Browser** — I can browse the web in a visible Chromium window — navigate, click, fill forms, and extract data. Logins persist across sessions.

🎤 **Voice** — Toggle the mic to talk hands-free. I can speak back too — all processed locally, never sent to the cloud.

👁️ **Vision** — I can see your webcam or screen and answer questions about what's there.

📄 **Documents** — Upload PDFs and files as a persistent knowledge base, or attach them directly in chat with 📎.

📬 **Channels** — Connect Telegram or Email so I can respond to messages even when the app window is closed.

---

⚙️ Head to **Settings** to connect accounts and explore options. Just type or speak — I'll figure out which tools to use.
"""


def welcome_message(cloud: bool = False) -> str:
    if cloud:
        header = (
            "👋 **Welcome to Thoth — your AI assistant.**\n\n"
            "Your model runs in the cloud, but your conversations, "
            "memories, and files are stored locally on your machine."
        )
    else:
        header = (
            "👋 **Welcome to Thoth — your private AI assistant.**\n\n"
            "Everything runs locally on your machine. Your conversations, "
            "memories, and files never leave your computer."
        )
    return header + _WELCOME_BODY


EXAMPLE_PROMPTS = [
    "What's the weather this week?",
    "Summarize the latest AI research papers",
    "What do you remember about me?",
    "Create a daily morning briefing task",
    "Read and summarize report.pdf from my workspace",
    "What am I looking at? (with camera)",
]

# ═════════════════════════════════════════════════════════════════════════════
# FILE / UPLOAD EXTENSIONS
# ═════════════════════════════════════════════════════════════════════════════

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp"}
DATA_EXTENSIONS = {".csv", ".tsv", ".xlsx", ".xls", ".json", ".jsonl"}
TEXT_EXTENSIONS = {
    ".txt", ".md", ".py", ".js", ".ts", ".html", ".css", ".xml", ".yaml",
    ".yml", ".toml", ".ini", ".cfg", ".log", ".sh", ".bat", ".ps1", ".sql",
    ".r", ".java", ".c", ".cpp", ".h", ".cs", ".go", ".rs", ".rb", ".php",
    ".swift", ".kt", ".lua", ".pl",
}
CHARS_PER_TOKEN_APPROX = 3  # used only for file-size char budgets

ALLOWED_UPLOAD_SUFFIXES = sorted(
    ext.lstrip(".") for ext in IMAGE_EXTENSIONS | TEXT_EXTENSIONS | DATA_EXTENSIONS | {".pdf"}
)

# ═════════════════════════════════════════════════════════════════════════════
# REGEX PATTERNS
# ═════════════════════════════════════════════════════════════════════════════

YT_URL_PATTERN = re.compile(
    r"https?://(?:www\.)?(?:youtube\.com/watch\?v=|youtu\.be/)([a-zA-Z0-9_-]{11})(?:[^\s)\]]*)"
)

SENTENCE_SPLIT = re.compile(r'(?<=[.!?])\s+')

# ═════════════════════════════════════════════════════════════════════════════
# UI CONSTANTS
# ═════════════════════════════════════════════════════════════════════════════

SIDEBAR_MAX_THREADS = 8
MAX_STREAM_SENTENCES = 3

ICON_OPTIONS = [
    "⚡", "📊", "📧", "📝", "🔍", "🗂️", "📰", "🧹", "💡", "🔔",
    "📅", "🌐", "🤖", "📋", "🛠️", "🎯", "📈", "🔄", "💬", "🧪",
]
