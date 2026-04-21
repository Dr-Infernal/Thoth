"""Designer — publish self-contained HTML decks as static links."""

from __future__ import annotations

from datetime import datetime, timezone
import logging
import pathlib

from designer.export import build_html_export
from designer.state import DesignerProject
from designer.storage import DESIGNER_DIR, save_project
from tunnel import tunnel_manager

logger = logging.getLogger(__name__)

PUBLISHED_DIR = DESIGNER_DIR / "published"
APP_PORT = 8080


def ensure_published_dir() -> pathlib.Path:
    """Create and return the published deck directory."""
    PUBLISHED_DIR.mkdir(parents=True, exist_ok=True)
    return PUBLISHED_DIR


def resolve_publish_path(project: DesignerProject) -> pathlib.Path:
    """Return the stable static-file path for a published project."""
    return ensure_published_dir() / f"{project.id}.html"


def resolve_publish_base_url(ensure_public: bool = True) -> tuple[str, bool]:
    """Return the base URL for published links and whether it is public."""
    public_url = tunnel_manager.get_url(APP_PORT)
    if ensure_public and not public_url and tunnel_manager.is_available():
        try:
            public_url = tunnel_manager.start_tunnel(APP_PORT, label="designer publish")
        except Exception:
            logger.warning("Could not open a public tunnel for designer publishing", exc_info=True)
    if public_url:
        return public_url.rstrip("/"), True
    return f"http://127.0.0.1:{APP_PORT}", False


def publish_project(
    project: DesignerProject,
    pages: str | None = None,
    *,
    ensure_public: bool = True,
) -> dict:
    """Render a self-contained HTML deck and expose it through the app's static route."""
    html_bytes = build_html_export(project, pages)
    publish_path = resolve_publish_path(project)
    publish_path.write_bytes(html_bytes)

    base_url, is_public = resolve_publish_base_url(ensure_public=ensure_public)
    url = f"{base_url}/published/{publish_path.name}"

    project.publish_url = url
    project.published_at = datetime.now(timezone.utc).isoformat()
    save_project(project)

    return {
        "url": url,
        "path": str(publish_path),
        "public": is_public,
        "pages": pages or "all",
    }