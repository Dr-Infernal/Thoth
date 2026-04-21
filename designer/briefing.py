"""Designer project-brief helpers.

Builds the canonical initial user request used to generate the first draft
from a project's stored setup brief.
"""

from __future__ import annotations

from designer.state import DesignerProject, ProjectBrief


def project_has_build_brief(project: DesignerProject) -> bool:
    """Return True when the project has any stored setup brief content."""

    return bool(project.brief and not project.brief.is_empty())


def build_initial_design_request(project: DesignerProject) -> str:
    """Build the canonical first-draft request from the project's stored brief."""

    brief = project.brief or ProjectBrief()
    output_type = brief.output_type.strip() or "design"
    lines = [
        f"Create the first draft of this {output_type} using the current project as the starting point.",
    ]

    if project.template_id and project.template_id != "blank_canvas":
        lines.append(
            "Use the selected template as a starting structure, but replace placeholder content with real content tailored to the brief."
        )
    else:
        lines.append(
            "Turn the current blank starting point into a real first draft with complete content and layout."
        )

    if brief.build_description.strip():
        lines.append(f"What to build: {brief.build_description.strip()}")
    if brief.audience.strip():
        lines.append(f"Audience: {brief.audience.strip()}")
    if brief.tone.strip():
        lines.append(f"Tone: {brief.tone.strip()}")
    if brief.length.strip():
        lines.append(f"Desired length or scope: {brief.length.strip()}")
    if brief.reference_notes.strip():
        lines.append(f"Reference notes: {brief.reference_notes.strip()}")
    if brief.brand_preset.strip():
        lines.append(f"The project was set up with the brand preset '{brief.brand_preset.strip()}'.")
    if brief.brand_url.strip():
        lines.append(f"Brand source URL provided at setup: {brief.brand_url.strip()}")

    if project.brand is not None:
        lines.append("A brand is already configured on the project. Use it consistently across the design.")

    lines.append(
        "Produce a real, editable first draft the user can refine further, not a placeholder shell or generic outline."
    )
    return "\n".join(lines)