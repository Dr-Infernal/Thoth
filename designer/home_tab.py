"""Designer — home screen gallery tab showing project cards."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Callable

from nicegui import ui

from designer.state import BrandConfig
from designer.storage import list_projects, load_project, delete_project, duplicate_project
from designer.thumbnail import compute_thumbnail_dimensions, render_static_page_thumbnail
from designer.ui_theme import dialog_card_style, style_destructive_button, style_ghost_button, style_primary_button

logger = logging.getLogger(__name__)


def build_designer_tab(
    *,
    on_open_project: Callable,
    on_refresh: Callable | None = None,
) -> None:
    """Render the Designer gallery inside a home-screen tab panel.

    Parameters
    ----------
    on_open_project : Callable[[DesignerProject], None]
        Called when the user clicks a project card or creates a new one.
    on_refresh : Callable | None
        Called to rebuild the whole home view (after delete, etc.).
    """
    with ui.scroll_area().classes("w-full h-full"):
        with ui.column().classes("w-full q-pa-sm gap-0"):
            # Header row
            with ui.row().classes("w-full items-center justify-between"):
                with ui.column().classes("gap-0"):
                    ui.label("🎨 Designer").classes("text-h5")
                    ui.label("Visual Designs & Presentations").classes(
                        "text-xs text-grey-6"
                    ).style("margin-top: -2px; letter-spacing: 0.3px;")

                with ui.row().classes("gap-2"):
                    def _new_design():
                        from designer.template_gallery import show_new_project_dialog
                        show_new_project_dialog(on_project_created=on_open_project)

                    new_design_btn = ui.button(
                        "New Design", icon="add",
                        on_click=_new_design,
                    )
                    style_primary_button(new_design_btn, compact=True)

            ui.separator().classes("q-my-sm")

            # Project cards grid
            projects = list_projects()

            if projects:
                with ui.element("div").classes("w-full").style(
                    "display: grid;"
                    "grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));"
                    "gap: 0.75rem;"
                ):
                    for proj_summary in projects:
                        _render_project_card(
                            proj_summary,
                            on_open=on_open_project,
                            on_refresh=on_refresh,
                        )
            else:
                with ui.column().classes("w-full items-center q-mt-lg"):
                    ui.icon("design_services", size="3rem").classes("text-grey-6")
                    ui.label(
                        "No design projects yet"
                    ).classes("text-grey-5 text-lg q-mt-sm")
                    ui.label(
                        "Click 'New Design' to start from a template or blank canvas."
                    ).classes("text-grey-6 text-sm")


def _render_project_card(
    summary: dict,
    *,
    on_open: Callable,
    on_refresh: Callable | None,
) -> None:
    """Render a single project card in the gallery grid."""
    proj_id = summary["id"]
    name = summary.get("name", "Untitled")
    page_count = summary.get("page_count", 0)
    ratio = summary.get("aspect_ratio", "16:9")
    updated = summary.get("updated_at", "")
    preview_project = load_project(proj_id)

    # Format date
    date_str = ""
    if updated:
        try:
            dt = datetime.fromisoformat(updated)
            date_str = dt.strftime("%b %d, %I:%M %p")
        except (ValueError, TypeError):
            date_str = updated[:10]

    def _open_this():
        project = preview_project or load_project(proj_id)
        if project:
            on_open(project)
        else:
            ui.notify("Project not found.", type="negative")

    with ui.card().classes("h-full").style(
        "padding: 0.75rem; cursor: pointer; transition: border-color 0.2s;"
    ).on("click", _open_this):
        preview_page = preview_project.pages[0] if preview_project and preview_project.pages else None
        preview_html = preview_page.html if preview_page else summary.get("preview_html", "")
        preview_title = preview_page.title if preview_page else summary.get("preview_title", name)
        brand_dict = summary.get("brand")
        brand = BrandConfig.from_dict(brand_dict) if brand_dict else None
        canvas_width = int(summary.get("canvas_width", 1920) or 1920)
        canvas_height = int(summary.get("canvas_height", 1080) or 1080)
        thumb_height = 80
        thumb_width, _ = compute_thumbnail_dimensions(canvas_width, canvas_height, thumb_height)

        with ui.element("div").classes("w-full flex justify-center q-mb-xs"):
            with ui.element("div").style(
                f"width: {thumb_width}px; height: {thumb_height}px; border-radius: 8px; "
                "overflow: hidden; position: relative; background: #0F172A; "
                "border: 1px solid rgba(255,255,255,0.08);"
            ):
                render_static_page_thumbnail(
                    frame_id=f"gallery-preview-{proj_id[:8]}",
                    page_html=preview_html,
                    brand=brand,
                    project=preview_project,
                    page_index=0,
                    canvas_width=canvas_width,
                    canvas_height=canvas_height,
                    preview_height=thumb_height,
                    empty_label=preview_title,
                )

        ui.label(name).classes("font-bold text-center w-full").style(
            "font-size: 0.85rem; line-height: 1.2; overflow: hidden; "
            "text-overflow: ellipsis; white-space: nowrap;"
        )

        info = f"{page_count} page{'s' if page_count != 1 else ''} · {ratio}"
        if date_str:
            info += f" · {date_str}"
        ui.label(info).classes("text-xs text-grey-6 text-center w-full")

        # Action buttons
        with ui.row().classes("w-full items-center justify-center gap-1").style(
            "margin-top: 4px;"
        ):
            def _dup(pid=proj_id):
                new_proj = duplicate_project(pid)
                if new_proj:
                    ui.notify(f"Duplicated as '{new_proj.name}'", type="positive")
                    if on_refresh:
                        on_refresh()

            ui.button(icon="content_copy").on(
                "click.stop", _dup
            ).props("flat dense round size=sm").tooltip("Duplicate")

            def _del(pid=proj_id, pname=name):
                with ui.dialog() as confirm_dlg, ui.card().style(dialog_card_style(min_width="300px")):
                    ui.label(f"Delete '{pname}'?").classes("font-bold")
                    ui.label("This cannot be undone.").classes("text-grey-6 text-xs")
                    with ui.row().classes("w-full justify-end mt-2"):
                        cancel_btn = ui.button("Cancel", on_click=confirm_dlg.close)
                        style_ghost_button(cancel_btn, compact=True)

                        def _confirm(d=confirm_dlg, p=pid):
                            delete_project(p)
                            d.close()
                            ui.notify("🗑️ Project deleted.", type="negative")
                            if on_refresh:
                                on_refresh()

                        delete_btn = ui.button("Delete", on_click=_confirm)
                        style_destructive_button(delete_btn, compact=True)
                confirm_dlg.open()

            ui.button(icon="delete").on(
                "click.stop", _del
            ).props("flat dense round size=sm").tooltip("Delete").style("color: #888;")
