"""Designer — full-screen editor layout with chat pane, preview, and navigator."""

from __future__ import annotations

import asyncio
import logging
from typing import Callable

from nicegui import events, run, ui

from designer.references import delete_project_reference, persist_project_references
from designer.render_assets import resolve_project_image_sources
from designer.state import DesignerProject
from designer.storage import save_project
from designer.briefing import build_initial_design_request, project_has_build_brief
from designer.preview import build_preview
from designer.page_navigator import build_page_navigator
from designer.interaction import patch_html_text
from designer.ui_theme import (
    dialog_card_style,
    style_ghost_button,
    style_primary_button,
    style_secondary_button,
    surface_style,
)

logger = logging.getLogger(__name__)


def build_designer_editor(
    project: DesignerProject,
    *,
    on_back: Callable,
    send_message: Callable,
    p=None,
    state=None,
    add_chat_message: Callable | None = None,
    browse_file: Callable | None = None,
    open_settings: Callable | None = None,
) -> None:
    """Render the full-screen designer editor.

    Parameters
    ----------
    project : DesignerProject
        The project to edit.
    on_back : Callable
        Called when user clicks the back button (returns to gallery).
    send_message : Callable
        ``async def send_message(text: str)`` — sends a chat message
        through the agent with designer context.
    p : P | None
        Per-client page element references.  When provided the editor
        wires its own chat widgets into ``p`` so the streaming system
        can render assistant messages.
    state : AppState | None
        Per-client application state.
    add_chat_message : Callable | None
        ``lambda msg: add_chat_message(msg, p, thread_id)`` for rendering.
    browse_file : Callable | None
        Native file browser (macOS).
    open_settings : Callable | None
        Opens the settings dialog (for "More models…").
    """
    from designer.session import (
        get_undo_stack,
        prepare_project_mutation,
        set_active_project,
    )
    set_active_project(project)

    def _repair_reference_images() -> None:
        repaired = 0
        for page in project.pages:
            resolved_html = resolve_project_image_sources(page.html, project)
            if resolved_html != page.html:
                page.html = resolved_html
                page.thumbnail_b64 = None
                repaired += 1
        if repaired:
            save_project(project)
            logger.info("Resolved persisted image references on %d page(s)", repaired)

    _repair_reference_images()

    # ── Interaction callbacks ─────────────────────────────────────
    _click_info: list[dict | None] = [None]
    _preview_ref: list[dict | None] = [None]
    _nav_ref: list[dict | None] = [None]
    _notes_title_ref: list[ui.label | None] = [None]
    _notes_status_ref: list[ui.label | None] = [None]
    _notes_input_ref: list[ui.textarea | None] = [None]
    _notes_generate_btn_ref: list[ui.button | None] = [None]
    _references_ref: list[ui.column | None] = [None]
    _existing_messages = state.messages if state is not None else []

    def _render_first_draft_cta() -> None:
        if not project_has_build_brief(project) or _existing_messages:
            return

        request_text = build_initial_design_request(project)
        description = ""
        if project.brief is not None:
            description = project.brief.build_description or project.brief.output_type

        with ui.card().classes("w-full q-ma-sm").style(
            surface_style(padding="16px", strong=True)
            + "background: linear-gradient(135deg, rgba(245,158,11,0.14), rgba(37,99,235,0.08));"
            + "border: 1px solid rgba(245,158,11,0.2);"
        ):
            ui.label("Ready to build the first draft").classes("font-bold")
            ui.label(
                description or "Use the saved setup brief to generate the first real draft."
            ).classes("text-xs text-grey-4")

            build_btn = ui.button("Build First Draft", icon="auto_awesome")
            style_primary_button(build_btn, compact=True)

            async def _run_first_draft() -> None:
                build_btn.disable()
                try:
                    await send_message(request_text)
                finally:
                    build_btn.enable()

            build_btn.on_click(lambda: asyncio.create_task(_run_first_draft()))

    def _on_element_click(detail: dict):
        """Handle click on an element in the preview iframe."""
        _click_info[0] = detail
        tag = detail.get("tag", "?")
        text = detail.get("text", "")[:40]
        logger.debug("Element clicked: <%s> %s", tag, text)

    def _on_text_edit(detail: dict):
        """Handle inline text edit from the preview iframe."""
        xpath = detail.get("xpath", "")
        tag = detail.get("tag", "")
        old_text = detail.get("oldText", "")
        new_text = detail.get("newText", "")
        if not old_text or not new_text or old_text == new_text:
            return

        idx = max(0, min(project.active_page, len(project.pages) - 1))
        page = project.pages[idx]

        prepare_project_mutation(project, f"inline_text_edit_page_{idx}")

        page.html = patch_html_text(page.html, xpath, tag, old_text, new_text)
        page.thumbnail_b64 = None
        save_project(project)
        _refresh_editor()
        logger.info("Inline text edit applied on page %d <%s>", idx, tag)

    def _refresh_references_panel() -> None:
        if _references_ref[0] is None:
            return
        _references_ref[0].clear()
        with _references_ref[0]:
            if not project.references:
                ui.label(
                    "No saved references yet. Files you attach here become reusable project references after send."
                ).classes("text-xs text-grey-5")
                return

            for reference in project.references:
                with ui.card().classes("w-full q-pa-sm").style(
                    "background: rgba(255,255,255,0.04); border: 1px solid rgba(255,255,255,0.08);"
                ):
                    with ui.row().classes("w-full items-start no-wrap").style("gap: 8px;"):
                        with ui.column().classes("flex-grow gap-0"):
                            ui.label(reference.name).classes("text-sm text-weight-medium")
                            meta = f"{reference.kind}"
                            if reference.suffix:
                                meta += f" · {reference.suffix}"
                            if reference.size_bytes:
                                meta += f" · {max(1, round(reference.size_bytes / 1024))} KB"
                            ui.label(meta).classes("text-xs text-grey-5")
                            if reference.summary:
                                ui.label(reference.summary).classes("text-xs text-grey-4").style(
                                    "white-space: normal; line-height: 1.35;"
                                )

                        def _remove_reference(ref_id=reference.id):
                            removed = delete_project_reference(project, ref_id)
                            if removed is None:
                                return
                            project.manual_edits.append(
                                f"User removed project reference {removed.name}."
                            )
                            save_project(project)
                            _refresh_references_panel()

                        ui.button(icon="delete", on_click=_remove_reference).props(
                            "flat dense round color=grey-6"
                        ).tooltip("Remove reference")

    def _active_page_state():
        if not project.pages:
            return None
        idx = max(0, min(project.active_page, len(project.pages) - 1))
        return idx, project.pages[idx]

    def _refresh_notes_panel() -> None:
        current = _active_page_state()
        if current is None:
            return
        idx, page = current
        if _notes_title_ref[0] is not None:
            _notes_title_ref[0].text = f"Speaker Notes · Page {idx + 1}: {page.title}"
            _notes_title_ref[0].update()
        if _notes_status_ref[0] is not None:
            _notes_status_ref[0].text = (
                f"{len(page.notes.split())} words saved"
                if page.notes.strip() else
                "No speaker notes yet"
            )
            _notes_status_ref[0].update()
        if _notes_input_ref[0] is not None and (_notes_input_ref[0].value or "") != (page.notes or ""):
            _notes_input_ref[0].value = page.notes or ""
            _notes_input_ref[0].update()

    def _save_notes(_e=None) -> None:
        current = _active_page_state()
        if current is None or _notes_input_ref[0] is None:
            return
        idx, page = current
        new_notes = (_notes_input_ref[0].value or "").strip()
        if new_notes == (page.notes or "").strip():
            _refresh_notes_panel()
            return
        prepare_project_mutation(project, f"edit_notes_page_{idx}")
        page.notes = new_notes
        project.manual_edits.append(
            f"User edited speaker notes for page {idx + 1} \"{page.title}\"."
        )
        save_project(project)
        _refresh_notes_panel()
        if _nav_ref[0]:
            _nav_ref[0]["refresh"]()

    async def _generate_notes_for_active_page() -> None:
        current = _active_page_state()
        if current is None:
            return
        idx, page = current
        if not page.html.strip():
            ui.notify("The active page has no content to summarize.", type="warning")
            return
        try:
            from designer.ai_content import generate_speaker_notes
            from designer.html_ops import summarize_page_html

            if _notes_generate_btn_ref[0] is not None:
                _notes_generate_btn_ref[0].disable()
            if _notes_status_ref[0] is not None:
                _notes_status_ref[0].text = "Generating speaker notes…"
                _notes_status_ref[0].update()
            summary = summarize_page_html(page.html)
            generated = await run.io_bound(generate_speaker_notes, page.title, summary, page.notes)
            generated = (generated or "").strip()
            if not generated:
                ui.notify("No speaker notes were generated.", type="warning")
                _refresh_notes_panel()
                return
            if generated == (page.notes or "").strip():
                ui.notify("Speaker notes are already up to date.", type="info")
                _refresh_notes_panel()
                return
            prepare_project_mutation(project, f"generate_notes_page_{idx}")
            page.notes = generated
            project.manual_edits.append(
                f"User generated speaker notes for page {idx + 1} \"{page.title}\"."
            )
            save_project(project)
            _refresh_notes_panel()
            if _nav_ref[0]:
                _nav_ref[0]["refresh"]()
            ui.notify("Speaker notes generated.", type="positive")
        except Exception as exc:
            logger.exception("Failed to generate speaker notes")
            ui.notify(f"Failed to generate speaker notes: {exc}", type="negative")
            _refresh_notes_panel()
        finally:
            if _notes_generate_btn_ref[0] is not None:
                _notes_generate_btn_ref[0].enable()

    # ── Header bar ────────────────────────────────────────────────────
    with ui.row().classes("w-full items-center shrink-0").style(
        "padding: 8px 16px; background: rgba(0,0,0,0.5); "
        "border-bottom: 1px solid rgba(255,255,255,0.08);"
    ):
        def _go_back():
            set_active_project(None)
            on_back()

        ui.button(icon="arrow_back", on_click=_go_back).props(
            "flat dense round"
        ).tooltip("Back to Gallery")

        # Editable project name
        name_input = ui.input(value=project.name).props(
            "dense borderless"
        ).classes("text-h6").style(
            "flex: 1; max-width: 400px; font-weight: 600;"
        )

        def _refresh_editor(*, force_preview: bool = False):
            try:
                name_input.value = project.name
                name_input.update()
            except RuntimeError:
                pass
            _refresh_notes_panel()
            if _preview_ref[0]:
                try:
                    _preview_ref[0]["refresh"](force=force_preview)
                except RuntimeError:
                    pass
            if _nav_ref[0]:
                try:
                    _nav_ref[0]["refresh"]()
                except RuntimeError:
                    pass

        def _rename(_e=None):
            new_name = name_input.value.strip() if name_input.value else ""
            if new_name and new_name != project.name:
                prepare_project_mutation(project, "rename_project")
                project.name = new_name
                save_project(project)
                # Keep the linked thread name in sync
                if project.thread_id:
                    from threads import _save_thread_meta
                    _save_thread_meta(project.thread_id, f"🎨 {new_name}")
                _refresh_editor()

        name_input.on("blur", _rename)
        name_input.on("keydown.enter", lambda e: name_input.run_method("blur"))

        ui.element("div").style("flex: 1;")  # spacer

        # Present button
        async def _show_presentation():
            from designer.presentation import show_presentation
            await show_presentation(project)

        ui.button(icon="play_arrow", on_click=_show_presentation).props(
            "outline dense round color=grey-6"
        ).tooltip("Present")

        # Brand button
        def _show_brand():
            from designer.brand_dialog import show_brand_dialog
            show_brand_dialog(project, on_apply=_refresh_editor)

        ui.button(icon="palette", on_click=_show_brand).props(
            "outline dense round color=grey-6"
        ).tooltip("Brand & Theme")

        # Curated block picker
        def _show_blocks():
            from designer.components import list_components, render_component_html
            from designer.html_ops import insert_component_in_html

            components = list_components()
            categories = []
            for component in components:
                if component.category not in categories:
                    categories.append(component.category)

            with ui.dialog() as dlg, ui.card().style(
                dialog_card_style(min_width="820px", max_width="980px", max_height="84vh")
            ):
                ui.label("Curated Blocks").classes("text-h6 text-weight-bold")
                ui.label(
                    "Insert reusable sections into the active page. These blocks are brand-aware and remain editable with the normal Designer tools."
                ).classes("text-sm text-grey-5 q-mb-sm")

                with ui.tabs().classes("w-full") as tabs:
                    for category in categories:
                        ui.tab(category, label=category)

                with ui.tab_panels(tabs, value=categories[0]).classes("w-full"):
                    for category in categories:
                        with ui.tab_panel(category):
                            with ui.grid(columns=2).classes("w-full gap-3"):
                                for component in [c for c in components if c.category == category]:
                                    with ui.card().classes("q-pa-md").style(
                                        "background: rgba(255,255,255,0.04); border: 1px solid rgba(255,255,255,0.08);"
                                    ):
                                        ui.label(component.label).classes("text-subtitle1 text-weight-medium")
                                        ui.label(component.description).classes("text-sm text-grey-5")
                                        if component.tags:
                                            with ui.row().classes("w-full flex-wrap gap-1 q-mt-sm"):
                                                for tag in component.tags:
                                                    ui.badge(tag, color="grey-8").props("outline")

                                        def _insert_curated_block(component_name=component.name):
                                            idx = max(0, min(project.active_page, len(project.pages) - 1))
                                            prepare_project_mutation(project, f"insert_component_{component_name}")
                                            page = project.pages[idx]
                                            component_html = render_component_html(component_name)
                                            page.html, element_id, selector_hint = insert_component_in_html(
                                                page.html,
                                                component_html,
                                                component_name,
                                            )
                                            page.thumbnail_b64 = None
                                            project.manual_edits.append(
                                                f"User inserted the {component_name} curated block on page {idx + 1}."
                                            )
                                            save_project(project)
                                            _refresh_editor(force_preview=True)
                                            logger.info(
                                                "Inserted curated block %s on page %d (%s / %s)",
                                                component_name,
                                                idx + 1,
                                                element_id,
                                                selector_hint,
                                            )
                                            dlg.close()

                                        insert_btn = ui.button(
                                            "Insert on current page",
                                            icon="add_box",
                                            on_click=_insert_curated_block,
                                        ).classes("q-mt-sm")
                                        style_secondary_button(insert_btn, compact=True)

                with ui.row().classes("w-full justify-end q-mt-sm"):
                    close_blocks_btn = ui.button("Close", on_click=dlg.close)
                    style_ghost_button(close_blocks_btn)

            dlg.open()

        ui.button(icon="view_quilt", on_click=_show_blocks).props(
            "outline dense round color=grey-6"
        ).tooltip("Curated Blocks")

        # Import button
        def _show_import():
            from designer.import_dialog import show_import_dialog
            show_import_dialog(project, on_done=_refresh_editor)

        ui.button(icon="upload_file", on_click=_show_import).props(
            "outline dense round color=grey-6"
        ).tooltip("Import PPTX / DOCX")

        # History button
        def _show_history():
            _open_history_dialog(project, on_restore=_refresh_editor)

        ui.button(icon="history", on_click=_show_history).props(
            "outline dense round color=grey-6"
        ).tooltip("Version History")

        # Review button
        def _show_review():
            from designer.critique import critique_page_html, apply_page_repairs

            _report: list[dict | None] = [None]
            with ui.dialog() as dlg, ui.card().style(
                dialog_card_style(min_width="620px", max_width="760px", max_height="84vh")
            ):
                ui.label("Page Review").classes("text-h6 text-weight-bold")
                summary_label = ui.label("").classes("text-sm text-grey-5 q-mb-sm")
                findings_col = ui.column().classes("w-full gap-2")

                def _render_report() -> None:
                    idx = max(0, min(project.active_page, len(project.pages) - 1))
                    page = project.pages[idx]
                    report = critique_page_html(page.html, project.canvas_width, project.canvas_height)
                    _report[0] = report
                    summary_label.text = f"Page {idx + 1}: {report['summary']} Score {report['score']}/100."
                    summary_label.update()
                    findings_col.clear()
                    with findings_col:
                        if not report["findings"]:
                            ui.label("No obvious issues detected on the active page.").classes("text-sm text-positive")
                        else:
                            for finding in report["findings"]:
                                with ui.card().classes("w-full q-pa-sm").style(
                                    "background: rgba(255,255,255,0.04); border: 1px solid rgba(255,255,255,0.08);"
                                ):
                                    with ui.row().classes("w-full items-center justify-between"):
                                        ui.label(finding["category"].title()).classes("text-sm text-weight-medium")
                                        ui.badge(finding["severity"], color="amber" if finding["severity"] != "high" else "negative")
                                    ui.label(finding["message"]).classes("text-sm")
                                    if finding.get("excerpt"):
                                        ui.label(finding["excerpt"]).classes("text-xs text-grey-5")
                                    ui.label(f"Suggested fix: {finding['suggested_fix']}").classes("text-xs text-grey-4")

                def _apply_safe_repairs() -> None:
                    if _report[0] is None:
                        _render_report()
                    if _report[0] is None or not _report[0]["findings"]:
                        ui.notify("No safe repairs are suggested for this page.")
                        return

                    categories = sorted({finding["category"] for finding in _report[0]["findings"]})
                    idx = max(0, min(project.active_page, len(project.pages) - 1))
                    page = project.pages[idx]
                    prepare_project_mutation(project, f"review_repairs_page_{idx}")
                    new_html, changes = apply_page_repairs(
                        page.html,
                        project.canvas_width,
                        project.canvas_height,
                        categories,
                    )
                    if not changes or new_html == page.html:
                        ui.notify("No safe repairs were applied.")
                        return

                    page.html = new_html
                    page.thumbnail_b64 = None
                    project.manual_edits.append(
                        f"User applied review repairs on page {idx + 1} for {', '.join(categories)}."
                    )
                    save_project(project)
                    _refresh_editor(force_preview=True)
                    _render_report()
                    ui.notify(f"Applied {len(changes)} safe repair(s).")

                _render_report()
                with ui.row().classes("w-full justify-end q-mt-sm"):
                    refresh_btn = ui.button("Refresh", on_click=_render_report)
                    style_ghost_button(refresh_btn)
                    apply_fixes_btn = ui.button("Apply Safe Fixes", on_click=_apply_safe_repairs)
                    style_primary_button(apply_fixes_btn)
                    close_review_btn = ui.button("Close", on_click=dlg.close)
                    style_ghost_button(close_review_btn)

            dlg.open()

        ui.button(icon="fact_check", on_click=_show_review).props(
            "outline dense round color=grey-6"
        ).tooltip("Review Active Page")

        # Undo / Redo
        def _undo():
            stack = get_undo_stack()
            if stack and stack.undo(project):
                project.manual_edits.append(
                    f"User pressed Undo. Now {len(project.pages)} pages."
                )
                save_project(project)
                _refresh_editor(force_preview=True)

        def _redo():
            stack = get_undo_stack()
            if stack and stack.redo(project):
                project.manual_edits.append(
                    f"User pressed Redo. Now {len(project.pages)} pages."
                )
                save_project(project)
                _refresh_editor(force_preview=True)

        def _handle_designer_shortcut(e):
            shortcut = (e.args or {}).get("shortcut")
            if shortcut == "redo":
                _redo()
            elif shortcut == "undo":
                _undo()

        ui.keyboard(repeating=False).on(
            "key",
            _handle_designer_shortcut,
            js_handler="""(e) => {
                const key = (e.key || '').toLowerCase();
                if (e.action !== 'keydown') return;
                if (!(e.ctrlKey || e.metaKey)) return;
                if (key !== 'z') return;
                emit({shortcut: e.shiftKey ? 'redo' : 'undo'});
                e.event.preventDefault();
            }""",
        )

        ui.button(icon="undo", on_click=_undo).props(
            "flat dense round color=grey-6"
        ).tooltip("Undo (Ctrl/Cmd+Z)")

        ui.button(icon="redo", on_click=_redo).props(
            "flat dense round color=grey-6"
        ).tooltip("Redo (Ctrl/Cmd+Shift+Z)")

        # Export button
        def _show_export():
            from designer.export_dialog import show_export_dialog
            show_export_dialog(project)

        def _show_share():
            from designer.share_dialog import show_share_dialog
            show_share_dialog(project)

        share_btn = ui.button("Share", icon="share", on_click=_show_share)
        style_secondary_button(share_btn, compact=True)

        export_btn = ui.button("Export", icon="download", on_click=_show_export)
        style_primary_button(export_btn, compact=True)

    # ── Main content: splitter (chat left, preview+nav right) ─────────
    with ui.splitter(value=35).classes("w-full flex-grow").style(
        "overflow: hidden;"
    ) as splitter:

        # ── Left pane: Chat ──────────────────────────────────────────
        with splitter.before:
            with ui.column().classes("w-full h-full").style(
                "background: rgba(0,0,0,0.3);"
            ):
                if state is not None and p is not None:
                    from ui.chat_components import (
                        build_chat_messages,
                        build_file_upload,
                        build_chat_input_bar,
                    )

                    _render_first_draft_cta()

                    async def _send_with_references(text: str) -> None:
                        pending_snapshot = [
                            {
                                "name": item.get("name", ""),
                                "data": bytes(item.get("data", b"")),
                            }
                            for item in p.pending_files
                            if item.get("name") and item.get("data")
                        ]
                        if pending_snapshot:
                            added_refs = await run.io_bound(
                                persist_project_references,
                                project,
                                pending_snapshot,
                                state.vision_service,
                                state.attached_data_cache,
                                state.thread_model_override or None,
                            )
                            if added_refs:
                                added_names = ", ".join(ref.name for ref in added_refs[:4])
                                if len(added_refs) > 4:
                                    added_names += ", ..."
                                project.manual_edits.append(
                                    f"User added {len(added_refs)} project reference(s): {added_names}."
                                )
                                save_project(project)
                                _refresh_references_panel()
                        await send_message(text)

                    # File upload (hidden widget + drag-drop + paste)
                    _hidden_upload = build_file_upload(p, state)

                    with ui.expansion("References", icon="collections_bookmark").classes(
                        "w-full shrink-0"
                    ).props("dense default-opened"):
                        with ui.row().classes("w-full items-center justify-between").style("gap: 8px;"):
                            with ui.column().classes("gap-0"):
                                ui.label("Project references").classes("text-sm text-weight-medium")
                                ui.label(
                                    "Use the normal attach flow below. Attached files are saved here after you send your next Designer message."
                                ).classes("text-xs text-grey-5")

                            async def _open_reference_upload() -> None:
                                await ui.run_javascript(
                                    f"document.getElementById('c{_hidden_upload.id}').querySelector('input[type=file]').click()"
                                )

                            ui.button("Add files", icon="attach_file").props(
                                "flat dense no-caps color=grey-6"
                            ).on_click(lambda: asyncio.create_task(_open_reference_upload()))

                        _references_ref[0] = ui.column().classes("w-full gap-2 q-mt-sm")
                        _refresh_references_panel()

                    # Render messages from the thread (state.messages)
                    _msgs = state.messages or []
                    build_chat_messages(
                        p, state,
                        messages=_msgs,
                        add_chat_message=add_chat_message,
                        placeholder_text="Describe what you want to create or change.",
                    )

                    # Full input bar (textarea, attach, voice, send, stop, model picker)
                    build_chat_input_bar(
                        p, state,
                        send_fn=_send_with_references,
                        hidden_upload=_hidden_upload,
                        browse_file=browse_file,
                        open_settings=open_settings,
                        show_model_picker=True,
                    )
                else:
                    # Fallback: minimal chat using the current thread messages when available.
                    _fallback_messages = state.messages if state is not None else []
                    _render_first_draft_cta()
                    with ui.scroll_area().classes("w-full flex-grow") as _fb_scroll:
                        _fb_container = ui.column().classes("w-full q-pa-sm gap-2")
                        if p is not None:
                            p.chat_container = _fb_container
                            p.chat_scroll = _fb_scroll
                        with _fb_container:
                            for msg in _fallback_messages:
                                _render_chat_bubble(msg)
                            if not _fallback_messages:
                                ui.label(
                                    "Describe what you want to create or change."
                                ).classes("text-grey-5 text-sm q-pa-md")

                    with ui.row().classes("w-full items-end shrink-0").style(
                        "padding: 8px; border-top: 1px solid rgba(255,255,255,0.08);"
                    ):
                        _fb_input = ui.textarea(
                            placeholder="Describe your design…"
                        ).props("dense outlined autogrow").classes("flex-grow").style(
                            "max-height: 120px;"
                        )

                        async def _fb_send():
                            text = _fb_input.value.strip()
                            if not text:
                                return
                            _fb_input.value = ""
                            await send_message(text)

                        fallback_send_btn = ui.button(icon="send", on_click=_fb_send)
                        style_primary_button(fallback_send_btn, compact=True, round=True)
                        _fb_input.on(
                            "keydown.enter",
                            lambda e: (
                                asyncio.create_task(_fb_send())
                                if not getattr(e, "args", {}).get("shiftKey", False)
                                else None
                            ),
                        )

        # ── Right pane: Preview + Navigator ──────────────────────────
        with splitter.after:
            with ui.column().classes("w-full h-full no-wrap").style("overflow: hidden; min-height: 0;"):
                # Preview area (takes most space)
                # Page navigator strip (built first, wired to preview below)
                def _on_nav_from_preview():
                    """Called by preview timer when page structure changes."""
                    if _nav_ref[0]:
                        _nav_ref[0]["refresh"]()

                with ui.element("div").classes("w-full").style(
                    "flex: 1 1 auto; min-height: 0; overflow: hidden;"
                ):
                    _preview_ref[0] = build_preview(
                        project,
                        on_element_click=_on_element_click,
                        on_text_edit=_on_text_edit,
                        on_undo_shortcut=_undo,
                        on_redo_shortcut=_redo,
                        on_navigate=_on_nav_from_preview,
                    )

                with ui.card().classes("w-full q-ma-sm q-mt-xs shrink-0").style(
                    "min-height: 220px; max-height: 34vh; overflow: hidden; "
                    "background: rgba(255,255,255,0.04); border: 1px solid rgba(255,255,255,0.08);"
                ):
                    with ui.column().classes("w-full h-full").style("gap: 8px; min-height: 0;"):
                        with ui.row().classes("w-full items-center justify-between"):
                            _notes_title_ref[0] = ui.label("Speaker Notes").classes("text-sm text-weight-medium")
                            _notes_status_ref[0] = ui.label("").classes("text-xs text-grey-5")
                            with ui.row().classes("items-center gap-1"):
                                ui.button(
                                    "Save",
                                    icon="save",
                                    on_click=_save_notes,
                                ).props("flat dense no-caps color=grey-6")
                                _notes_generate_btn_ref[0] = ui.button(
                                    "Generate Notes",
                                    icon="auto_awesome",
                                    on_click=_generate_notes_for_active_page,
                                )
                                style_primary_button(_notes_generate_btn_ref[0], compact=True)
                        ui.label(
                            "Notes are saved per page and appear in presenter mode and PPTX notes slides."
                        ).classes("text-xs text-grey-5")
                        _notes_input_ref[0] = ui.textarea(
                            placeholder="Add speaker notes for the active page…",
                        ).props(
                            'dense outlined input-style="min-height: 180px; max-height: 100%; overflow: auto;"'
                        ).classes("w-full").style("flex: 1 1 auto; min-height: 180px;")
                        _notes_input_ref[0].on("blur", _save_notes)
                        _refresh_notes_panel()

                def _on_page_change():
                    if _preview_ref[0]:
                        _preview_ref[0]["refresh"]()
                    _refresh_notes_panel()

                nav = build_page_navigator(
                    project,
                    on_page_change=_on_page_change,
                )
                _nav_ref[0] = nav


def _render_chat_bubble(msg: dict) -> None:
    """Render a single chat message bubble."""
    role = msg.get("role", "user")
    content = msg.get("content", "")
    if role == "user":
        with ui.row().classes("w-full justify-end"):
            ui.label(content).classes("q-pa-sm").style(
                "background: rgba(37,99,235,0.2); border-radius: 12px 12px 0 12px; "
                "max-width: 85%; white-space: pre-wrap; word-break: break-word;"
            )
    else:
        with ui.row().classes("w-full"):
            ui.markdown(content).classes("q-pa-sm").style(
                "background: rgba(255,255,255,0.05); border-radius: 12px 12px 12px 0; "
                "max-width: 85%;"
            )


def _open_history_dialog(
    project: DesignerProject,
    on_restore: Callable[[], None] | None = None,
) -> None:
    """Open a dialog showing version history snapshots with restore buttons."""
    from designer.history import list_snapshots, restore_snapshot
    from designer.session import prepare_project_mutation
    from designer.storage import save_project
    from datetime import datetime

    with ui.dialog() as dlg, ui.card().style(
        dialog_card_style(min_width="450px", max_width="560px", max_height="80vh")
    ):
        ui.label("Version History").classes("text-h6 text-weight-bold q-mb-sm")
        snaps = list_snapshots(project.id)

        if not snaps:
            ui.label("No version history yet. History is saved automatically "
                     "before each change.").classes("text-grey-5 text-sm")
        else:
            ui.label(f"{len(snaps)} snapshot(s)").classes("text-grey-5 text-sm q-mb-sm")
            with ui.scroll_area().style("max-height: 400px;"):
                for snap in snaps:
                    ts = snap.get("timestamp", 0)
                    try:
                        dt = datetime.fromtimestamp(float(ts))
                        time_str = dt.strftime("%b %d, %H:%M:%S")
                    except (ValueError, OSError):
                        time_str = str(ts)
                    label = snap.get("label", "")
                    pages = snap.get("page_count", "?")

                    with ui.row().classes("w-full items-center gap-2").style(
                        "padding: 6px 8px; background: rgba(255,255,255,0.04);"
                        "border-radius: 6px; margin-bottom: 4px;"
                    ):
                        with ui.column().classes("flex-grow").style("gap: 0;"):
                            ui.label(time_str).classes("text-sm")
                            desc = f"{pages} pages"
                            if label:
                                desc += f" · {label}"
                            ui.label(desc).classes("text-xs text-grey-5")

                        def _restore(sid=snap["id"]):
                            prepare_project_mutation(project, f"restore_snapshot_{sid}")
                            if restore_snapshot(project, sid):
                                project.manual_edits.append(
                                    f"User restored version snapshot {sid}."
                                )
                                save_project(project)
                                if on_restore:
                                    on_restore(force_preview=True)
                            dlg.close()

                        restore_btn = ui.button("Restore", on_click=_restore)
                        style_secondary_button(restore_btn, compact=True)

        with ui.row().classes("w-full justify-end q-mt-md"):
            close_history_btn = ui.button("Close", on_click=dlg.close)
            style_ghost_button(close_history_btn)

    dlg.open()
