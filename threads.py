from langgraph.checkpoint.sqlite import SqliteSaver
import logging
import sqlite3
import uuid
import os
import pathlib
import json
from datetime import datetime

logger = logging.getLogger(__name__)

# Store data in %APPDATA%/Thoth (writable even when app is in Program Files)
DATA_DIR = pathlib.Path(os.environ.get("THOTH_DATA_DIR", pathlib.Path.home() / ".thoth"))
DATA_DIR.mkdir(parents=True, exist_ok=True)

_THREAD_UI_DIR = DATA_DIR / "thread_ui"
_THREAD_UI_DIR.mkdir(parents=True, exist_ok=True)

_MEDIA_DIR = DATA_DIR / "media"
_MEDIA_DIR.mkdir(parents=True, exist_ok=True)

DB_PATH = str(DATA_DIR / "threads.db")

def _init_thread_db():
    """Create a metadata table to store thread names/timestamps."""
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.execute(
            "CREATE TABLE IF NOT EXISTS thread_meta "
            "(thread_id TEXT PRIMARY KEY, name TEXT, created_at TEXT, updated_at TEXT)"
        )
        # Migration: add model_override column if missing
        cols = {row[1] for row in conn.execute("PRAGMA table_info(thread_meta)").fetchall()}
        if "model_override" not in cols:
            conn.execute("ALTER TABLE thread_meta ADD COLUMN model_override TEXT DEFAULT ''")
        if "skills_override" not in cols:
            conn.execute("ALTER TABLE thread_meta ADD COLUMN skills_override TEXT DEFAULT ''")
        if "summary" not in cols:
            conn.execute("ALTER TABLE thread_meta ADD COLUMN summary TEXT DEFAULT ''")
        if "summary_msg_count" not in cols:
            conn.execute("ALTER TABLE thread_meta ADD COLUMN summary_msg_count INTEGER DEFAULT 0")
        conn.commit()
        conn.close()
        logger.debug("Thread database initialised at %s", DB_PATH)
    except Exception:
        logger.error("Failed to initialise thread database at %s", DB_PATH, exc_info=True)

def _list_threads():
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute(
        "SELECT thread_id, name, created_at, updated_at, COALESCE(model_override, '') "
        "FROM thread_meta ORDER BY updated_at DESC"
    ).fetchall()
    conn.close()
    return rows

def _thread_exists(thread_id: str) -> bool:
    """Return True if a thread_meta row exists for *thread_id*."""
    conn = sqlite3.connect(DB_PATH)
    row = conn.execute(
        "SELECT 1 FROM thread_meta WHERE thread_id = ?", (thread_id,)
    ).fetchone()
    conn.close()
    return row is not None

def _save_thread_meta(thread_id: str, name: str):
    now = datetime.now().isoformat()
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "INSERT INTO thread_meta (thread_id, name, created_at, updated_at) "
        "VALUES (?, ?, ?, ?) "
        "ON CONFLICT(thread_id) DO UPDATE SET name = ?, updated_at = ?",
        (thread_id, name, now, now, name, now),
    )
    conn.commit()
    conn.close()


def _thread_ui_media_path(thread_id: str) -> pathlib.Path:
    return _THREAD_UI_DIR / f"{thread_id}.media.json"


def _thread_media_dir(thread_id: str) -> pathlib.Path:
    """Return (and lazily create) the per-thread media directory."""
    d = _MEDIA_DIR / thread_id
    d.mkdir(parents=True, exist_ok=True)
    return d


def save_thread_media(thread_id: str, payload: dict) -> None:
    """Persist media sidecar (v2 — file paths, not base64)."""
    try:
        path = _thread_ui_media_path(thread_id)
        path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    except Exception:
        logger.warning("Failed to save thread media sidecar for %s", thread_id, exc_info=True)


def load_thread_media(thread_id: str) -> dict | None:
    """Load media sidecar for a thread (if any)."""
    try:
        path = _thread_ui_media_path(thread_id)
        if not path.exists():
            return None
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else None
    except Exception:
        logger.warning("Failed to load thread media sidecar for %s", thread_id, exc_info=True)
        return None


def save_media_file(thread_id: str, filename: str, data: bytes) -> pathlib.Path:
    """Write raw media bytes to the per-thread media directory.

    Returns the absolute path to the saved file.
    """
    d = _thread_media_dir(thread_id)
    dest = d / filename
    dest.write_bytes(data)
    return dest


def load_media_file(thread_id: str, filename: str) -> bytes | None:
    """Read a media file from the per-thread media directory."""
    path = _MEDIA_DIR / thread_id / filename
    if path.exists():
        try:
            return path.read_bytes()
        except Exception:
            logger.warning("Failed to read media file %s", path, exc_info=True)
    return None


def _next_media_filename(thread_id: str, prefix: str, ext: str) -> str:
    """Generate the next sequential filename like gen_001.png, cap_002.png."""
    d = _MEDIA_DIR / thread_id
    if not d.exists():
        return f"{prefix}_001.{ext}"
    existing = [f.name for f in d.iterdir() if f.name.startswith(prefix + "_")]
    if not existing:
        return f"{prefix}_001.{ext}"
    nums = []
    for name in existing:
        parts = name.split("_", 1)
        if len(parts) == 2:
            num_part = parts[1].split(".")[0]
            try:
                nums.append(int(num_part))
            except ValueError:
                pass
    next_num = max(nums, default=0) + 1
    return f"{prefix}_{next_num:03d}.{ext}"

_init_thread_db()

def _delete_thread(thread_id: str):
    """Remove a thread's metadata, checkpoints, and writes from the database."""
    conn = sqlite3.connect(DB_PATH)
    conn.execute("DELETE FROM thread_meta WHERE thread_id = ?", (thread_id,))
    # Purge LangGraph checkpoint data to prevent zombie threads
    # Tables are created by LangGraph at runtime — may not exist yet
    try:
        conn.execute("DELETE FROM checkpoints WHERE thread_id = ?", (thread_id,))
        conn.execute("DELETE FROM writes WHERE thread_id = ?", (thread_id,))
    except sqlite3.OperationalError:
        pass
    conn.commit()
    conn.close()
    # Clear any cached summary for this thread
    try:
        from agent import clear_summary_cache
        clear_summary_cache(thread_id)
    except Exception:
        pass
    # Clean up media sidecar and non-persistent media files
    try:
        sidecar = _thread_ui_media_path(thread_id)
        media_dir = _MEDIA_DIR / thread_id
        # Read sidecar to find which files to keep (persist=true)
        persist_files: set[str] = set()
        if sidecar.exists():
            try:
                payload = json.loads(sidecar.read_text(encoding="utf-8"))
                for entry in payload.get("entries", []):
                    for item in entry.get("media", []):
                        if item.get("persist"):
                            persist_files.add(item.get("path", ""))
            except Exception:
                logger.debug("Failed to parse media sidecar during delete", exc_info=True)
            sidecar.unlink(missing_ok=True)
        # Delete non-persistent files; leave persistent ones
        if media_dir.exists():
            for f in list(media_dir.iterdir()):
                if f.name not in persist_files:
                    try:
                        f.unlink()
                    except Exception:
                        logger.debug("Failed to delete media file %s", f, exc_info=True)
            # Remove dir only if empty
            try:
                if not any(media_dir.iterdir()):
                    media_dir.rmdir()
            except Exception:
                pass
    except Exception:
        logger.warning("Failed to clean up media for thread %s", thread_id, exc_info=True)
    # Also clean up legacy sidecar if present
    try:
        legacy = _THREAD_UI_DIR / f"{thread_id}.images.json"
        legacy.unlink(missing_ok=True)
    except Exception:
        pass


def _get_thread_model_override(thread_id: str) -> str:
    """Return the model override for a thread (empty string if none)."""
    conn = sqlite3.connect(DB_PATH)
    row = conn.execute(
        "SELECT COALESCE(model_override, '') FROM thread_meta WHERE thread_id = ?",
        (thread_id,),
    ).fetchone()
    conn.close()
    return row[0] if row else ""


def _set_thread_model_override(thread_id: str, model_name: str) -> None:
    """Set or clear the model override for a thread."""
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "UPDATE thread_meta SET model_override = ? WHERE thread_id = ?",
        (model_name, thread_id),
    )
    conn.commit()
    conn.close()


def get_thread_skills_override(thread_id: str) -> list[str] | None:
    """Return per-thread skills override as a list of skill names, or None (use global)."""
    conn = sqlite3.connect(DB_PATH)
    row = conn.execute(
        "SELECT COALESCE(skills_override, '') FROM thread_meta WHERE thread_id = ?",
        (thread_id,),
    ).fetchone()
    conn.close()
    if not row or not row[0]:
        return None
    import json
    try:
        return json.loads(row[0])
    except (json.JSONDecodeError, TypeError):
        return None


def set_thread_skills_override(thread_id: str, skill_names: list[str] | None) -> None:
    """Set or clear the per-thread skills override. Pass None to revert to global."""
    import json
    value = json.dumps(skill_names) if skill_names is not None else ""
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "UPDATE thread_meta SET skills_override = ? WHERE thread_id = ?",
        (value, thread_id),
    )
    conn.commit()
    conn.close()


def save_thread_summary(thread_id: str, summary: str, msg_count: int) -> None:
    """Persist the context summary for a thread to the database."""
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "UPDATE thread_meta SET summary = ?, summary_msg_count = ? WHERE thread_id = ?",
        (summary, msg_count, thread_id),
    )
    conn.commit()
    conn.close()


def load_thread_summary(thread_id: str) -> dict | None:
    """Load the persisted summary for a thread, or None if none exists."""
    conn = sqlite3.connect(DB_PATH)
    row = conn.execute(
        "SELECT COALESCE(summary, ''), COALESCE(summary_msg_count, 0) "
        "FROM thread_meta WHERE thread_id = ?",
        (thread_id,),
    ).fetchone()
    conn.close()
    if not row or not row[0]:
        return None
    return {"summary": row[0], "msg_count": row[1]}


def clear_thread_summary(thread_id: str) -> None:
    """Clear the persisted summary for a thread."""
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "UPDATE thread_meta SET summary = '', summary_msg_count = 0 WHERE thread_id = ?",
        (thread_id,),
    )
    conn.commit()
    conn.close()


conn = sqlite3.connect(DB_PATH, check_same_thread=False)
checkpointer = SqliteSaver(conn)


def pick_or_create_thread() -> dict:
    """Interactive menu to resume an existing thread or start a new one."""
    threads = _list_threads()
    print("\n=== Thoth — Thread Manager ===")
    print("  [0] Start a new conversation")
    for idx, (tid, name, created, updated, *_pick_rest) in enumerate(threads, start=1):
        print(f"  [{idx}] {name}  (last used: {updated[:16]})")
    print()

    while True:
        choice = input("Select a thread number: ").strip()
        if choice == "0":
            thread_id = uuid.uuid4().hex[:12]
            name = input("Give this conversation a name: ").strip() or f"Thread-{thread_id[:6]}"
            _save_thread_meta(thread_id, name)
            print(f"\nStarted new thread: {name}\n")
            return {"configurable": {"thread_id": thread_id}}
        elif choice.isdigit() and 1 <= int(choice) <= len(threads):
            tid, name, _, _, *_pick_rest2 = threads[int(choice) - 1]
            _save_thread_meta(tid, name)  # bump updated_at
            print(f"\nResuming thread: {name}\n")
            return {"configurable": {"thread_id": tid}}
        else:
            print("Invalid choice, try again.")