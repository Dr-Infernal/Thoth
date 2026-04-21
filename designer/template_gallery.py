"""Designer — template gallery modal for creating new projects."""

from __future__ import annotations

import logging
from typing import Callable

from nicegui import run, ui

from designer.brand import extract_brand_from_url, get_all_presets
from designer.setup_flow import (
    default_project_name_for_template,
    infer_output_type_for_template,
    prepare_project_creation,
    resolve_project_brand,
)
from designer.state import DesignerProject, ProjectBrief, ASPECT_RATIOS
from designer.storage import save_project
from designer.templates import get_templates, get_template, get_template_categories
from designer.ui_theme import (
    SECTION_LABEL_CLASSES,
    SECTION_LABEL_STYLE,
    dialog_card_style,
    style_choice_button,
    style_ghost_button,
    style_primary_button,
    style_secondary_button,
    surface_style,
)

logger = logging.getLogger(__name__)

_OUTPUT_TYPE_OPTIONS = [
    "Presentation",
    "Pitch deck",
    "One-pager",
    "Status report",
    "Landing page",
    "Social media set",
    "Wireframe kit",
]
_AUDIENCE_OPTIONS = [
    "Investors",
    "Customers",
    "Executives",
    "Internal team",
    "Partners",
    "Prospects",
]
_TONE_OPTIONS = [
    "Confident",
    "Modern",
    "Editorial",
    "Formal",
    "Bold",
    "Friendly",
]
_LENGTH_OPTIONS = [
    "3 slides",
    "5 slides",
    "10 slides",
    "1 page",
    "Short overview",
    "Detailed walkthrough",
]


def show_template_gallery(
    *,
    on_project_created: Callable[[DesignerProject], None],
) -> None:
    """Backward-compatible wrapper for the unified new-project dialog."""

    show_new_project_dialog(
        on_project_created=on_project_created,
        initial_template_id="blank_canvas",
    )


def show_blank_canvas_picker(
    *,
    on_project_created: Callable[[DesignerProject], None],
) -> None:
    """Backward-compatible wrapper for the unified new-project dialog."""

    show_new_project_dialog(
        on_project_created=on_project_created,
        initial_template_id="blank_canvas",
    )


def show_new_project_dialog(
    *,
    on_project_created: Callable,
    initial_template_id: str = "blank_canvas",
) -> None:
    """Open the unified Designer setup dialog."""

    templates = get_templates()
    categories = ["All", *get_template_categories()]
    presets = get_all_presets()
    selected_template_id = {
        "value": initial_template_id if get_template(initial_template_id) else "blank_canvas"
    }
    selected_category = {"value": "All"}
    selected_preset = {"value": "Default Dark"}
    extracted_brand = {"value": None}
    extraction_label = {"value": "Using preset brand."}
    current_effective_brand = {
        "value": resolve_project_brand(preset_name=selected_preset["value"])
    }
    last_default_name = {
        "value": default_project_name_for_template(selected_template_id["value"])
    }
    last_default_ratio = {
        "value": (get_template(selected_template_id["value"]) or get_template("blank_canvas")).aspect_ratio
    }

    def _selected_template():
        return get_template(selected_template_id["value"]) or get_template("blank_canvas")

    def _resolved_output_type(raw_value: str = "") -> str:
        if selected_template_id["value"] == "blank_canvas":
            return raw_value.strip()
        return infer_output_type_for_template(selected_template_id["value"])

    def _brand_preview_html(label: str) -> str:
        brand = current_effective_brand["value"]
        return (
            '<div style="padding:16px;border-radius:18px;border:1px solid rgba(148,163,184,0.14);'
            'background:linear-gradient(180deg, rgba(15,23,42,0.62), rgba(15,23,42,0.36));">'
            f'<div style="font-size:0.76rem;letter-spacing:0.1em;text-transform:uppercase;opacity:0.72;margin-bottom:10px;color:#94a3b8;">{label}</div>'
            '<div style="display:flex;gap:8px;margin-bottom:10px;">'
            f'<div style="width:30px;height:30px;border-radius:10px;background:{brand.primary_color};box-shadow:inset 0 1px 0 rgba(255,255,255,0.25);"></div>'
            f'<div style="width:30px;height:30px;border-radius:10px;background:{brand.secondary_color};box-shadow:inset 0 1px 0 rgba(255,255,255,0.25);"></div>'
            f'<div style="width:30px;height:30px;border-radius:10px;background:{brand.accent_color};box-shadow:inset 0 1px 0 rgba(255,255,255,0.25);"></div>'
            f'<div style="width:30px;height:30px;border-radius:10px;background:{brand.bg_color};border:1px solid rgba(255,255,255,0.12);"></div>'
            '</div>'
            f'<div style="font-size:0.84rem;opacity:0.9;color:#e2e8f0;">{brand.heading_font} / {brand.body_font}</div>'
            '</div>'
        )

    with ui.dialog().props("maximized") as dlg, ui.card().classes(
        "w-full h-full"
    ).style(dialog_card_style(max_width="1280px", height="calc(100vh - 48px)", padding="24px")):
        with ui.row().classes("w-full items-start justify-between"):
            with ui.column().classes("gap-0"):
                ui.label("New Design").classes("text-h5 text-weight-bold")
                ui.label("Choose a starting point, capture the brief, and optionally build the first draft immediately.").classes(
                    "text-sm text-grey-5"
                )
            close_btn = ui.button(icon="close", on_click=dlg.close).props("flat dense round")
            style_ghost_button(close_btn, compact=True)

        ui.separator().classes("q-my-sm")

        with ui.splitter(value=49).classes("w-full flex-grow").style("min-height: 0;") as splitter:
            with splitter.before:
                with ui.column().classes("w-full h-full gap-3 no-wrap").style("padding-right: 14px; min-height: 0;"):
                    with ui.card().classes("w-full").style(surface_style(padding="16px", strong=True)):
                        ui.label("Template library").classes(SECTION_LABEL_CLASSES).style(SECTION_LABEL_STYLE)
                        ui.label("Choose a structure that matches the work you need to produce.").classes(
                            "text-sm text-grey-4"
                        )
                    with ui.row().classes("w-full flex-wrap gap-2") as _category_row:
                        pass
                    with ui.scroll_area().classes("w-full flex-grow").style("min-height: 0;"):
                        _grid = ui.column().classes("w-full")

            with splitter.after:
                with ui.scroll_area().classes("w-full h-full").style("padding-left: 14px; min-height: 0;"):
                    with ui.column().classes("w-full gap-4"):
                        _summary = ui.column().classes("w-full gap-2")

                        with ui.card().classes("w-full").style(surface_style(padding="18px", strong=True)):
                            ui.label("Project basics").classes(SECTION_LABEL_CLASSES).style(SECTION_LABEL_STYLE)
                            ui.label("Name the project and lock in the canvas shape before you build.").classes(
                                "text-sm text-grey-5 q-mb-sm"
                            )
                            name_input = ui.input(
                                label="Project name",
                                value=default_project_name_for_template(selected_template_id["value"]),
                            ).props("dense outlined").classes("w-full")

                            ratio_select = ui.select(
                                {ratio: f"{ratio} · {dims[0]}×{dims[1]}" for ratio, dims in ASPECT_RATIOS.items()},
                                value=_selected_template().aspect_ratio,
                                label="Canvas ratio",
                            ).props("dense outlined").classes("w-full q-mt-sm")

                        with ui.card().classes("w-full").style(surface_style(padding="18px")):
                            ui.label("Build brief").classes(SECTION_LABEL_CLASSES).style(SECTION_LABEL_STYLE)
                            ui.label("The description is the only field you usually need. The rest just sharpen the first draft.").classes(
                                "text-sm text-grey-5 q-mb-sm"
                            )

                            build_input = ui.textarea(
                                label="What should the first draft create?",
                                placeholder="Describe the real first draft you want the AI to create.",
                            ).props('outlined autogrow input-style="min-height: 140px;"').classes("w-full")

                            with ui.row().classes("w-full gap-3 q-mt-sm"):
                                audience_input = ui.select(
                                    _AUDIENCE_OPTIONS,
                                    label="Audience (optional)",
                                    with_input=True,
                                    new_value_mode="add",
                                ).props("dense outlined").classes("col")
                                tone_input = ui.select(
                                    _TONE_OPTIONS,
                                    label="Tone (optional)",
                                    with_input=True,
                                    new_value_mode="add",
                                ).props("dense outlined").classes("col")

                            with ui.row().classes("w-full gap-3 q-mt-sm"):
                                length_input = ui.select(
                                    _LENGTH_OPTIONS,
                                    label="Length or scope (optional)",
                                    with_input=True,
                                    new_value_mode="add",
                                ).props("dense outlined").classes("col")
                                with ui.row().classes("col") as output_row:
                                    output_input = ui.select(
                                        _OUTPUT_TYPE_OPTIONS,
                                        label="Output type",
                                        with_input=True,
                                        new_value_mode="add",
                                    ).props("dense outlined").classes("w-full")

                            output_hint = ui.label("").classes("text-xs text-grey-5 q-mt-xs")

                            refs_input = ui.textarea(
                                label="Reference notes or URLs (optional)",
                                placeholder="Inspiration, constraints, talking points, links, or anything the first draft should respect.",
                            ).props('outlined autogrow input-style="min-height: 92px;"').classes("w-full q-mt-sm")

                        with ui.card().classes("w-full").style(surface_style(padding="18px")):
                            ui.label("Brand setup").classes(SECTION_LABEL_CLASSES).style(SECTION_LABEL_STYLE)
                            ui.label("Preset selection is immediate. URL extraction can override it when you want live brand data.").classes(
                                "text-sm text-grey-5 q-mb-sm"
                            )
                            preset_select = ui.select(
                                sorted(presets.keys()),
                                value=selected_preset["value"],
                                label="Brand preset",
                                on_change=lambda e: _on_preset_change(e),
                            ).props("dense outlined").classes("w-full")
                            brand_url_input = ui.input(
                                label="Brand URL",
                                placeholder="https://example.com",
                            ).props("dense outlined").classes("w-full q-mt-sm")

                            with ui.row().classes("w-full items-center gap-2 q-mt-sm"):
                                extract_btn = ui.button(
                                    "Extract Brand from URL",
                                    icon="language",
                                )
                                style_primary_button(extract_btn, compact=True)
                                clear_extract_btn = ui.button(
                                    "Use Preset Instead",
                                    icon="restart_alt",
                                )
                                style_secondary_button(clear_extract_btn, compact=True)

                            brand_status = ui.label(extraction_label["value"]).classes("text-xs text-grey-5 q-mt-sm")
                            brand_preview = ui.html(
                                _brand_preview_html(extraction_label["value"]),
                                sanitize=False,
                            ).classes("w-full q-mt-xs")

                        def _refresh_brand_preview() -> None:
                            current_effective_brand["value"] = resolve_project_brand(
                                preset_name=selected_preset["value"],
                                extracted_brand=extracted_brand["value"],
                            )
                            brand_status.text = extraction_label["value"]
                            brand_preview.set_content(_brand_preview_html(extraction_label["value"]))
                            clear_extract_btn.set_visibility(extracted_brand["value"] is not None)

                        def _on_preset_change(e) -> None:
                            selected_preset["value"] = e.value or "Default Dark"
                            if extracted_brand["value"] is None:
                                extraction_label["value"] = f"Using preset: {selected_preset['value']}"
                            _refresh_brand_preview()

                        extraction_label["value"] = f"Using preset: {selected_preset['value']}"
                        _refresh_brand_preview()

                        def _sync_template_dependent_fields() -> None:
                            tmpl = _selected_template()
                            next_default_name = default_project_name_for_template(tmpl.id)
                            current_name = (name_input.value or "").strip()
                            if not current_name or current_name == last_default_name["value"]:
                                name_input.value = next_default_name
                                name_input.update()
                            last_default_name["value"] = next_default_name

                            current_ratio = ratio_select.value or ""
                            if not current_ratio or current_ratio == last_default_ratio["value"]:
                                ratio_select.value = tmpl.aspect_ratio
                                ratio_select.update()
                            last_default_ratio["value"] = tmpl.aspect_ratio

                            if tmpl.id == "blank_canvas":
                                output_row.visible = True
                                output_row.update()
                                output_hint.text = "Choose the output type because Blank Canvas does not imply one."
                            else:
                                output_row.visible = False
                                output_row.update()
                                output_hint.text = (
                                    f"Output type will be saved as '{infer_output_type_for_template(tmpl.id)}' from the selected template."
                                )
                            output_hint.update()

                        async def _extract_brand() -> None:
                            url = (brand_url_input.value or "").strip()
                            if not url:
                                ui.notify("Enter a brand URL first.", type="warning")
                                return
                            if not url.startswith(("http://", "https://")):
                                url = "https://" + url
                            extract_btn.disable()
                            extract_btn.set_text("Extracting...")
                            try:
                                result = await run.io_bound(lambda: extract_brand_from_url(url))
                            finally:
                                extract_btn.enable()
                                extract_btn.set_text("Extract Brand from URL")
                            if result is None:
                                ui.notify("Could not extract a brand from that URL.", type="negative")
                                return
                            extracted_brand["value"] = result
                            extraction_label["value"] = f"Using extracted brand from {url}"
                            _refresh_brand_preview()
                            ui.notify("Brand extracted and ready for setup.", type="positive")

                        def _clear_extracted_brand() -> None:
                            extracted_brand["value"] = None
                            extraction_label["value"] = f"Using preset: {selected_preset['value']}"
                            _refresh_brand_preview()

                        extract_btn.on_click(_extract_brand)
                        clear_extract_btn.on_click(_clear_extracted_brand)
                        clear_extract_btn.set_visibility(False)
                        _sync_template_dependent_fields()

                        def _build_brief() -> ProjectBrief:
                            return ProjectBrief(
                                output_type=_resolved_output_type(output_input.value or ""),
                                audience=(audience_input.value or "").strip(),
                                tone=(tone_input.value or "").strip(),
                                length=(length_input.value or "").strip(),
                                build_description=(build_input.value or "").strip(),
                                brand_url=(brand_url_input.value or "").strip(),
                                brand_preset=selected_preset["value"],
                                reference_notes=(refs_input.value or "").strip(),
                            )

                        def _create(auto_build: bool = False) -> None:
                            brief = _build_brief()
                            if auto_build and not brief.build_description:
                                ui.notify(
                                    "Add a build description before creating the first draft.",
                                    type="warning",
                                )
                                return
                            project, initial_prompt = prepare_project_creation(
                                selected_template_id["value"],
                                aspect_ratio=ratio_select.value or _selected_template().aspect_ratio,
                                project_name=name_input.value or "",
                                brief=brief,
                                preset_name=selected_preset["value"],
                                extracted_brand=extracted_brand["value"],
                                auto_build=auto_build,
                            )
                            save_project(project)
                            dlg.close()
                            try:
                                on_project_created(project, initial_prompt)
                            except TypeError:
                                on_project_created(project)

                        with ui.row().classes("w-full justify-end gap-2 q-mt-md"):
                            cancel_btn = ui.button("Cancel", on_click=dlg.close)
                            style_ghost_button(cancel_btn)
                            create_only_btn = ui.button("Create Only", on_click=lambda: _create(False))
                            style_secondary_button(create_only_btn)
                            create_build_btn = ui.button("Create & Build First Draft", on_click=lambda: _create(True))
                            style_primary_button(create_build_btn)

        def _render_category_buttons() -> None:
            _category_row.clear()
            with _category_row:
                for cat in categories:
                    is_active = cat == selected_category["value"]

                    def _choose_category(category=cat):
                        selected_category["value"] = category
                        _render_category_buttons()
                        _render_template_grid()

                    category_btn = ui.button(cat, on_click=_choose_category)
                    style_choice_button(category_btn, active=is_active)

        def _render_template_summary() -> None:
            tmpl = _selected_template()
            _summary.clear()
            with _summary:
                with ui.card().classes("w-full").style(surface_style(padding="18px", strong=True)):
                    with ui.row().classes("w-full items-center justify-between"):
                        with ui.row().classes("items-center gap-2"):
                            ui.label(tmpl.icon).style("font-size: 1.5rem;")
                            with ui.column().classes("gap-0"):
                                ui.label(tmpl.name).classes("text-subtitle1 text-weight-bold")
                                ui.label(tmpl.description).classes("text-sm text-grey-5")
                        ui.badge(f"{len(tmpl.pages)} page{'s' if len(tmpl.pages) != 1 else ''}").props("outline").style(
                            "color: #f8fafc; border-color: rgba(148,163,184,0.24);"
                        )
                    with ui.row().classes("w-full gap-2 q-mt-sm"):
                        for meta in [tmpl.category, tmpl.aspect_ratio]:
                            ui.badge(meta).props("outline").style(
                                "color: #cbd5e1; border-color: rgba(148,163,184,0.2);"
                            )
                        if tmpl.id == "blank_canvas":
                            ui.badge("Custom output").props("outline").style(
                                "color: #fbbf24; border-color: rgba(245,158,11,0.3);"
                            )
                        else:
                            ui.badge(infer_output_type_for_template(tmpl.id)).props("outline").style(
                                "color: #fbbf24; border-color: rgba(245,158,11,0.3);"
                            )

        def _render_template_grid() -> None:
            filtered = templates
            if selected_category["value"] != "All":
                filtered = [t for t in templates if t.category == selected_category["value"]]

            _grid.clear()
            with _grid:
                with ui.element("div").classes("w-full").style(
                    "display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));"
                    " gap: 16px; padding: 8px 2px 12px;"
                ):
                    for tmpl in filtered:
                        is_selected = tmpl.id == selected_template_id["value"]
                        border = "1px solid rgba(245,158,11,0.45)" if is_selected else "1px solid rgba(148,163,184,0.12)"
                        background = (
                            "linear-gradient(180deg, rgba(30,41,59,0.95), rgba(15,23,42,0.88))"
                            if is_selected
                            else "linear-gradient(180deg, rgba(15,23,42,0.64), rgba(15,23,42,0.46))"
                        )
                        shadow = "0 18px 36px rgba(245,158,11,0.12)" if is_selected else "0 10px 24px rgba(2,6,23,0.18)"

                        def _select_template(template_id=tmpl.id):
                            selected_template_id["value"] = template_id
                            _sync_template_dependent_fields()
                            _render_template_summary()
                            _render_template_grid()

                        with ui.card().classes("h-full cursor-pointer q-pa-sm").style(
                            f"border:{border}; background:{background}; box-shadow:{shadow}; border-radius: 20px;"
                        ).on("click", lambda _, _fn=_select_template: _fn()):
                            with ui.column().classes("w-full gap-2"):
                                with ui.row().classes("w-full items-center justify-between"):
                                    ui.label(tmpl.icon).style("font-size: 1.45rem;")
                                    ui.badge(tmpl.category).props("outline").style(
                                        "color: #cbd5e1; border-color: rgba(148,163,184,0.18);"
                                    )
                                ui.label(tmpl.name).classes("text-subtitle2 text-weight-bold")
                                ui.label(tmpl.description).classes("text-sm text-grey-5")
                                with ui.row().classes("w-full items-center justify-between"):
                                    ui.label(f"{len(tmpl.pages)} page{'s' if len(tmpl.pages) != 1 else ''}").classes("text-xs text-grey-6")
                                    ui.label(tmpl.aspect_ratio).classes("text-xs text-grey-6")
                                if tmpl.id != "blank_canvas":
                                    ui.label(infer_output_type_for_template(tmpl.id)).classes("text-xs").style(
                                        "color: #fbbf24; font-weight: 600;"
                                    )

        _render_category_buttons()
        _render_template_summary()
        _render_template_grid()

    dlg.open()
