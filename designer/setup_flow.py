"""Designer setup-flow helpers.

Pure helpers used by the New Design dialog so creation logic can be tested
without relying on UI interactions.
"""

from __future__ import annotations

from designer.brand import get_all_presets
from designer.briefing import build_initial_design_request, project_has_build_brief
from designer.state import ASPECT_RATIOS, BrandConfig, DesignerPage, DesignerProject, ProjectBrief
from designer.templates import get_template


DEFAULT_PROJECT_NAME = "Untitled Design"
_INFERRED_OUTPUT_TYPES = {
    "pitch_deck": "pitch deck",
    "status_report": "status report",
    "marketing_one_pager": "marketing one-pager",
    "product_launch": "product launch presentation",
    "social_media": "social media set",
    "wireframe_kit": "wireframe kit",
}


def default_project_name_for_template(template_id: str) -> str:
    """Return the default name shown for a selected template."""

    tmpl = get_template(template_id) or get_template("blank_canvas")
    if tmpl and tmpl.id != "blank_canvas":
        return tmpl.name
    return DEFAULT_PROJECT_NAME


def infer_output_type_for_template(template_id: str) -> str:
    """Return the implied output type for non-blank templates."""

    tmpl = get_template(template_id) or get_template("blank_canvas")
    if tmpl is None or tmpl.id == "blank_canvas":
        return ""
    return _INFERRED_OUTPUT_TYPES.get(tmpl.id, tmpl.name.lower())


def resolve_project_brand(
    *,
    preset_name: str = "",
    extracted_brand: BrandConfig | None = None,
) -> BrandConfig:
    """Return the effective setup-time brand.

    URL-extracted brand wins over preset selection.
    """

    if extracted_brand is not None:
        return BrandConfig.from_dict(extracted_brand.to_dict())

    presets = get_all_presets()
    if preset_name and preset_name in presets:
        return BrandConfig.from_dict(presets[preset_name].to_dict())

    return BrandConfig()


def create_project_from_setup(
    template_id: str,
    *,
    aspect_ratio: str = "",
    project_name: str = "",
    brief: ProjectBrief | None = None,
    preset_name: str = "",
    extracted_brand: BrandConfig | None = None,
) -> DesignerProject:
    """Create a designer project from setup-dialog selections."""

    tmpl = get_template(template_id) or get_template("blank_canvas")
    if tmpl is None:
        raise ValueError("No template available for project creation.")

    ratio = aspect_ratio or tmpl.aspect_ratio
    canvas_width, canvas_height = ASPECT_RATIOS.get(ratio, (1920, 1080))
    pages = [
        DesignerPage(html=p["html"], title=p["title"], notes=p.get("notes", ""))
        for p in tmpl.pages
    ]

    brief_value = None
    if brief is not None and not brief.is_empty():
        brief_value = ProjectBrief.from_dict(brief.to_dict())

    name = project_name.strip() if project_name else ""
    if not name:
        name = default_project_name_for_template(tmpl.id)

    return DesignerProject(
        name=name,
        pages=pages,
        aspect_ratio=ratio,
        canvas_width=canvas_width,
        canvas_height=canvas_height,
        brand=resolve_project_brand(preset_name=preset_name, extracted_brand=extracted_brand),
        brief=brief_value,
        template_id=tmpl.id,
    )


def prepare_project_creation(
    template_id: str,
    *,
    aspect_ratio: str = "",
    project_name: str = "",
    brief: ProjectBrief | None = None,
    preset_name: str = "",
    extracted_brand: BrandConfig | None = None,
    auto_build: bool = False,
) -> tuple[DesignerProject, str | None]:
    """Return the newly created project plus an optional initial build prompt."""

    project = create_project_from_setup(
        template_id,
        aspect_ratio=aspect_ratio,
        project_name=project_name,
        brief=brief,
        preset_name=preset_name,
        extracted_brand=extracted_brand,
    )
    initial_prompt = None
    if auto_build and project_has_build_brief(project):
        initial_prompt = build_initial_design_request(project)
    return project, initial_prompt