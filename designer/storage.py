"""Designer — project persistence to ~/.thoth/designer/projects/."""

from __future__ import annotations

import json
import logging
import os
import pathlib
import re
import shutil
import tempfile
import time
from typing import Optional

from designer.state import DesignerProject

logger = logging.getLogger(__name__)

DATA_DIR = pathlib.Path(os.environ.get("THOTH_DATA_DIR", pathlib.Path.home() / ".thoth"))
DESIGNER_DIR = DATA_DIR / "designer"
PROJECTS_DIR = DESIGNER_DIR / "projects"
REFERENCES_DIR = DESIGNER_DIR / "references"
ASSETS_DIR = DESIGNER_DIR / "assets"

_REPLACE_RETRIES = 5
_REPLACE_BACKOFF_SECONDS = 0.05
_REPLACE_RETRY_WINERRORS = {5, 32}
_MAX_PERSISTED_STEM_LENGTH = 64


def _ensure_dirs() -> None:
    PROJECTS_DIR.mkdir(parents=True, exist_ok=True)
    REFERENCES_DIR.mkdir(parents=True, exist_ok=True)
    ASSETS_DIR.mkdir(parents=True, exist_ok=True)


def _project_reference_dir(project_id: str) -> pathlib.Path:
    return REFERENCES_DIR / project_id


def _project_asset_dir(project_id: str) -> pathlib.Path:
    return ASSETS_DIR / project_id


def _sanitize_reference_stem(original_name: str) -> str:
    stem = pathlib.Path(original_name).stem or "reference"
    safe = re.sub(r"[^A-Za-z0-9._-]+", "-", stem).strip("-._")
    if len(safe) > _MAX_PERSISTED_STEM_LENGTH:
        safe = safe[:_MAX_PERSISTED_STEM_LENGTH].rstrip("-._")
    return safe or "reference"


def _sanitize_asset_stem(original_name: str) -> str:
    stem = pathlib.Path(original_name).stem or "asset"
    safe = re.sub(r"[^A-Za-z0-9._-]+", "-", stem).strip("-._")
    if len(safe) > _MAX_PERSISTED_STEM_LENGTH:
        safe = safe[:_MAX_PERSISTED_STEM_LENGTH].rstrip("-._")
    return safe or "asset"


def _cleanup_temp_file(path: pathlib.Path) -> None:
    try:
        path.unlink(missing_ok=True)
    except OSError:
        logger.debug("Failed to clean up temp file %s", path, exc_info=True)


def _reserve_temp_path(path: pathlib.Path) -> tuple[int, pathlib.Path]:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(
        prefix=f"{path.name}.",
        suffix=".tmp",
        dir=path.parent,
    )
    return fd, pathlib.Path(tmp_name)


def _replace_with_retry(tmp: pathlib.Path, dest: pathlib.Path) -> None:
    for attempt in range(_REPLACE_RETRIES):
        try:
            tmp.replace(dest)
            return
        except OSError as exc:
            if getattr(exc, "winerror", None) not in _REPLACE_RETRY_WINERRORS or attempt >= _REPLACE_RETRIES - 1:
                raise
            time.sleep(_REPLACE_BACKOFF_SECONDS * (attempt + 1))


def _write_bytes_atomic(path: pathlib.Path, data: bytes) -> None:
    fd: int | None = None
    tmp: pathlib.Path | None = None
    try:
        fd, tmp = _reserve_temp_path(path)
        with os.fdopen(fd, "wb") as f:
            fd = None
            f.write(data)
        _replace_with_retry(tmp, path)
    except Exception:
        logger.exception("Failed to write designer asset file %s", path)
        if tmp is not None:
            _cleanup_temp_file(tmp)
        raise
    finally:
        if fd is not None:
            os.close(fd)


def _write_json_atomic(path: pathlib.Path, payload: dict) -> None:
    fd: int | None = None
    tmp: pathlib.Path | None = None
    try:
        fd, tmp = _reserve_temp_path(path)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            fd = None
            json.dump(payload, f, ensure_ascii=False, indent=2)
        _replace_with_retry(tmp, path)
    except Exception:
        logger.exception("Failed to write designer JSON file %s", path)
        if tmp is not None:
            _cleanup_temp_file(tmp)
        raise
    finally:
        if fd is not None:
            os.close(fd)


def save_reference_bytes(project_id: str, reference_id: str, original_name: str, data: bytes) -> str:
    """Persist one project reference file and return its stored filename."""
    _ensure_dirs()
    ref_dir = _project_reference_dir(project_id)
    ref_dir.mkdir(parents=True, exist_ok=True)
    suffix = pathlib.Path(original_name).suffix.lower()[:16]
    stored_name = f"{reference_id}-{_sanitize_reference_stem(original_name)}{suffix}"
    _write_bytes_atomic(ref_dir / stored_name, data)
    return stored_name


def save_asset_bytes(project_id: str, asset_id: str, original_name: str, data: bytes) -> str:
    """Persist one project asset file and return its stored filename."""
    _ensure_dirs()
    asset_dir = _project_asset_dir(project_id)
    asset_dir.mkdir(parents=True, exist_ok=True)
    suffix = pathlib.Path(original_name).suffix.lower()[:16]
    stored_name = f"{asset_id}-{_sanitize_asset_stem(original_name)}{suffix}"
    _write_bytes_atomic(asset_dir / stored_name, data)
    return stored_name


def load_reference_bytes(project_id: str, stored_name: str) -> Optional[bytes]:
    """Load a persisted reference file by project id and stored filename."""
    path = _project_reference_dir(project_id) / stored_name
    if not path.exists():
        return None
    try:
        return path.read_bytes()
    except Exception:
        logger.exception("Failed to load designer reference %s for project %s", stored_name, project_id)
        return None


def load_asset_bytes(project_id: str, stored_name: str) -> Optional[bytes]:
    """Load a persisted asset file by project id and stored filename."""
    path = _project_asset_dir(project_id) / stored_name
    if not path.exists():
        return None
    try:
        return path.read_bytes()
    except Exception:
        logger.exception("Failed to load designer asset %s for project %s", stored_name, project_id)
        return None


def delete_reference_bytes(project_id: str, stored_name: str) -> bool:
    """Delete a persisted reference file. Returns True if removed."""
    path = _project_reference_dir(project_id) / stored_name
    if not path.exists():
        return False
    path.unlink()
    return True


def delete_asset_bytes(project_id: str, stored_name: str) -> bool:
    """Delete a persisted asset file. Returns True if removed."""
    path = _project_asset_dir(project_id) / stored_name
    if not path.exists():
        return False
    path.unlink()
    return True


def delete_project_references(project_id: str) -> bool:
    """Delete the entire persisted reference directory for a project."""
    ref_dir = _project_reference_dir(project_id)
    if not ref_dir.exists():
        return False
    shutil.rmtree(ref_dir, ignore_errors=True)
    return True


def delete_project_assets(project_id: str) -> bool:
    """Delete the entire persisted asset directory for a project."""
    asset_dir = _project_asset_dir(project_id)
    if not asset_dir.exists():
        return False
    shutil.rmtree(asset_dir, ignore_errors=True)
    return True


def save_project(project: DesignerProject) -> None:
    """Persist a project to disk as JSON."""
    _ensure_dirs()
    project.touch()
    path = PROJECTS_DIR / f"{project.id}.json"
    try:
        _write_json_atomic(path, project.to_dict())
    except Exception:
        logger.exception("Failed to save designer project %s", project.id)
        raise


def load_project(project_id: str) -> Optional[DesignerProject]:
    """Load a single project by ID. Returns None if not found."""
    _ensure_dirs()
    path = PROJECTS_DIR / f"{project_id}.json"
    if not path.exists():
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        project = DesignerProject.from_dict(data)
        try:
            from designer.render_assets import normalize_project_inline_assets

            if normalize_project_inline_assets(project):
                save_project(project)
        except Exception:
            logger.exception("Failed to normalize inline designer assets for project %s", project_id)
        return project
    except Exception:
        logger.exception("Failed to load designer project %s", project_id)
        return None


def list_projects() -> list[dict]:
    """Return lightweight summaries of all projects (newest first).

    Each dict has: id, name, page_count, aspect_ratio, updated_at, created_at,
    and enough first-page preview data for the gallery.
    """
    _ensure_dirs()
    summaries = []
    for p in PROJECTS_DIR.glob("*.json"):
        try:
            with open(p, "r", encoding="utf-8") as f:
                data = json.load(f)
            _pages = data.get("pages", [])
            _preview_page = _pages[0] if _pages else {}
            summaries.append({
                "id": data.get("id", p.stem),
                "name": data.get("name", "Untitled"),
                "page_count": len(_pages),
                "aspect_ratio": data.get("aspect_ratio", "16:9"),
                "canvas_width": data.get("canvas_width", 1920),
                "canvas_height": data.get("canvas_height", 1080),
                "brand": data.get("brand"),
                "preview_html": _preview_page.get("html", ""),
                "preview_title": _preview_page.get("title", "Untitled"),
                "updated_at": data.get("updated_at", ""),
                "created_at": data.get("created_at", ""),
            })
        except Exception:
            logger.warning("Skipping corrupt designer project: %s", p.name)
    summaries.sort(key=lambda s: s.get("updated_at", ""), reverse=True)
    return summaries


def delete_project(project_id: str) -> bool:
    """Delete a project file. Returns True if deleted."""
    path = PROJECTS_DIR / f"{project_id}.json"
    deleted = False
    if path.exists():
        path.unlink()
        deleted = True
    if delete_project_references(project_id):
        deleted = True
    if delete_project_assets(project_id):
        deleted = True
    return deleted


def duplicate_project(project_id: str, new_name: Optional[str] = None) -> Optional[DesignerProject]:
    """Duplicate an existing project with a new ID."""
    original = load_project(project_id)
    if not original:
        return None
    import uuid
    from datetime import datetime, timezone
    new_project = DesignerProject.from_dict(original.to_dict())
    new_project.id = str(uuid.uuid4())
    new_project.name = new_name or f"{original.name} (Copy)"
    new_project.created_at = datetime.now(timezone.utc).isoformat()
    new_project.updated_at = datetime.now(timezone.utc).isoformat()
    save_project(new_project)
    original_ref_dir = _project_reference_dir(project_id)
    if original_ref_dir.exists():
        shutil.copytree(original_ref_dir, _project_reference_dir(new_project.id), dirs_exist_ok=True)
    original_asset_dir = _project_asset_dir(project_id)
    if original_asset_dir.exists():
        shutil.copytree(original_asset_dir, _project_asset_dir(new_project.id), dirs_exist_ok=True)
    return new_project
