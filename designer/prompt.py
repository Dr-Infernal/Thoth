"""Designer — system prompt builder for designer mode.

Generates the context block injected into the agent's system prompt
when a designer project is active.
"""

from __future__ import annotations

from designer.components import list_components
from designer.state import DesignerProject


def build_designer_prompt(project: DesignerProject) -> str:
    """Build the designer—mode system prompt injection.

    Includes project metadata, brand config, page list, tool reference,
    and HTML generation guidelines.
    """
    # Brand info
    brand = project.brand
    if brand:
        has_logo = bool((brand.logo_asset_id or "").strip() or brand.logo_b64)
        brand_line = (
            f"Brand: primary={brand.primary_color}, secondary={brand.secondary_color}, "
            f"accent={brand.accent_color}, bg={brand.bg_color}, text={brand.text_color}\n"
            f"       heading_font={brand.heading_font}, body_font={brand.body_font}"
        )
        if has_logo:
            if (brand.logo_mode or "auto") == "manual":
                brand_line += "\n       logo: SET (manual placeholder mode)"
            else:
                scope_label = "all pages" if (brand.logo_scope or "all") == "all" else "first page only"
                brand_line += (
                    f"\n       logo: SET (auto overlay, {scope_label}, {brand.logo_position}, "
                    f"max_height={brand.logo_max_height}px)"
                )
        css_vars = (
            f"  :root {{ --primary: {brand.primary_color}; --secondary: {brand.secondary_color}; "
            f"--accent: {brand.accent_color};\n"
            f"          --bg: {brand.bg_color}; --text: {brand.text_color}; "
            f"--heading-font: {brand.heading_font}; --body-font: {brand.body_font}; }}"
        )
        fonts = f"{brand.heading_font}, {brand.body_font}"
    else:
        brand_line = "Brand: not set (suggest professional defaults)"
        css_vars = (
            "  :root { --primary: #2563EB; --secondary: #1E40AF; --accent: #F59E0B;\n"
            "          --bg: #0F172A; --text: #F8FAFC; --heading-font: Inter; --body-font: Inter; }"
        )
        fonts = "Inter"

    brief = project.brief
    if brief and not brief.is_empty():
        brief_lines = []
        if brief.output_type:
            brief_lines.append(f"  - Output type: {brief.output_type}")
        if brief.audience:
            brief_lines.append(f"  - Audience: {brief.audience}")
        if brief.tone:
            brief_lines.append(f"  - Tone: {brief.tone}")
        if brief.length:
            brief_lines.append(f"  - Desired length: {brief.length}")
        if brief.build_description:
            brief_lines.append(f"  - What to build: {brief.build_description}")
        if brief.reference_notes:
            brief_lines.append(f"  - References: {brief.reference_notes}")
        if brief.brand_preset:
            brief_lines.append(f"  - Brand preset selected at setup: {brief.brand_preset}")
        if brief.brand_url:
            brief_lines.append(f"  - Brand URL provided at setup: {brief.brand_url}")
        brief_block = "PROJECT BRIEF:\n" + "\n".join(brief_lines)
    else:
        brief_block = "PROJECT BRIEF: not set"

    if project.references:
        reference_lines = []
        for reference in project.references[:12]:
            ref_line = (
                f"  - {reference.id}: {reference.name} "
                f"[{reference.kind}, {reference.size_bytes} bytes]"
            )
            if reference.summary:
                ref_line += f" — {reference.summary}"
            if reference.warnings:
                ref_line += f" (warnings: {len(reference.warnings)})"
            reference_lines.append(ref_line)
        references_block = "AVAILABLE REFERENCES:\n" + "\n".join(reference_lines)
    else:
        references_block = "AVAILABLE REFERENCES: none saved yet"

    component_lines = [
        f"  - {component.name}: {component.description}"
        for component in list_components()
    ]
    components_block = "AVAILABLE CURATED BLOCKS:\n" + "\n".join(component_lines)

    # Page list
    page_lines = []
    for i, page in enumerate(project.pages):
        marker = " ← active" if i == project.active_page else ""
        notes_marker = " · notes" if page.notes.strip() else ""
        page_lines.append(f"  {i}: \"{page.title}\"{notes_marker}{marker}")
    pages_str = "\n".join(page_lines)

    # Manual edits log — actions the user took via the UI since the last turn
    edits = project.manual_edits
    if edits:
        edits_str = "\n".join(f"  • {e}" for e in edits)
        edits_block = (
            f"\nRECENT MANUAL EDITS (user changed the project via the UI):\n"
            f"{edits_str}\n"
        )
        # Clear after including — the LLM only needs to see them once
        project.manual_edits = []
    else:
        edits_block = ""

    logo_instruction = ""
    if brand and bool((brand.logo_asset_id or "").strip() or brand.logo_b64):
        if (brand.logo_mode or "auto") == "manual":
            logo_instruction = (
                f"- LOGO: The brand has a logo set and is in manual placeholder mode. Place the HTML comment <!-- BRAND_LOGO --> wherever "
                f"the logo should appear in the layout. It will be replaced with the actual <img> tag at render time.\n"
            )
        else:
            scope_label = "all pages" if (brand.logo_scope or "all") == "all" else "the first page only"
            position_label = (brand.logo_position or "top_right").replace("_", " ")
            logo_instruction = (
                f"- LOGO: The brand has a logo set and automatic logo placement is active. The logo is already overlaid on {scope_label} at the {position_label} corner. "
                f"Use <!-- BRAND_LOGO --> only when the user explicitly wants a custom in-layout logo placement instead of the automatic overlay.\n"
            )

    return (
        f"[DESIGNER MODE]\n"
        f"You are helping the user with a design project: \"{project.name}\"\n"
        f"Canvas: {project.canvas_width}×{project.canvas_height} ({project.aspect_ratio})\n"
        f"Published link: {project.publish_url or 'not published yet'}\n"
        f"{brand_line}\n"
        f"{brief_block}\n"
        f"{references_block}\n"
        f"{components_block}\n"
        f"Pages ({len(project.pages)} total):\n{pages_str}\n"
        f"Active page: {project.active_page}\n"
        f"{edits_block}\n"
        f"DESIGNER TOOLS AVAILABLE:\n"
        f"- designer_set_pages: Create/replace ALL pages. Use for new projects or major reworks.\n"
        f"- designer_update_page: Update ONE page. Use for edits to specific pages.\n"
        f"- designer_add_page: Insert a new page. Use index=-1 to append.\n"
        f"- designer_delete_page: Remove a page.\n"
        f"- designer_move_page: Reorder pages.\n"
        f"- designer_get_project: Read current project state, including page summaries and asset IDs.\n"
        f"- designer_get_page_html: Read the full stored HTML for one page before a full-page rewrite.\n"
        f"- designer_get_reference: Read the stored details for one project reference by id or filename.\n"
        f"- designer_generate_notes: Generate speaker notes for one page and save them into the project.\n"
        f"- designer_insert_component: Insert a curated reusable block such as a hero callout, stats band, testimonial, pricing cards, or timeline.\n"
        f"- designer_critique_page: Review the current page for hierarchy, overflow, contrast, readability, and spacing issues.\n"
        f"- designer_apply_repairs: Apply safe deterministic repairs for selected critique categories on the current page.\n"
        f"- designer_set_brand: Update brand colors/fonts.\n"
        f"- designer_resize_project: Resize the canvas for presentation, social, or document presets.\n"
        f"- designer_export: Export as PDF/HTML/PNG/PPTX.\n"
        f"- designer_publish_link: Publish a self-contained HTML deck link through Thoth.\n"
        f"- designer_generate_image: Generate an AI image from a text prompt and embed it.\n"
        f"- designer_insert_image: Insert an attached, pasted, generated, or local image into a page.\n"
        f"- designer_move_image: Move an existing inserted image or chart using its asset ID or label.\n"
        f"- designer_replace_image: Replace an existing inserted image or chart using its asset ID or label.\n"
        f"- designer_move_element: Move a section or element using a selector hint, CSS selector, element id, or xpath.\n"
        f"- designer_duplicate_element: Duplicate a section or element and get back a new element id/selector hint.\n"
        f"- designer_restyle_element: Update styles or classes on an existing section or element without rewriting the page.\n"
        f"- designer_refine_text: Refine text on a page (shorten/expand/professional/casual/etc.).\n"
        f"- designer_add_chart: Add a data visualization chart (bar/line/pie/scatter/etc.) to a page.\n"
        f"\n"
        f"HTML REQUIREMENTS:\n"
        f"- Each page must be a COMPLETE, self-contained HTML document with inline <style>.\n"
        f"- You MUST use these CSS variables in ALL your HTML — never hardcode colors or fonts:\n"
        f"{css_vars}\n"
        f"- Use var(--bg) for backgrounds, var(--text) for text, var(--primary)/var(--secondary)/"
        f"var(--accent) for colored elements, var(--heading-font) for headings, var(--body-font) for body text.\n"
        f"- IMPORTANT: Set body {{ background: var(--bg); color: var(--text); font-family: var(--body-font); }} "
        f"and h1,h2,h3,h4 {{ font-family: var(--heading-font); }} so pages always reflect the brand.\n"
        f"- Canvas is EXACTLY {project.canvas_width}×{project.canvas_height}px. "
        f"Set html,body {{ margin:0; width:{project.canvas_width}px; height:{project.canvas_height}px; overflow:hidden; }}. "
        f"ALL content must fit within these bounds — do NOT exceed the canvas height.\n"
        f"- Use absolute/fixed positioning or constrained flexbox/grid to keep content within bounds.\n"
        f"- Include Google Fonts <link> for: {fonts}.\n"
        f"- Use modern CSS: flexbox, grid, gradients. No frameworks needed.\n"
        f"- For placeholder images, use colored divs or SVG shapes, NOT external URLs.\n"
        f"{logo_instruction}"
        f"- All content must render without JavaScript (sandbox restriction).\n"
        f"\n"
        f"GUIDELINES:\n"
        f"- The page list above is ALWAYS the authoritative current state. The user can "
        f"add, delete, or reorder pages via the UI at any time — ignore stale page counts "
        f"from earlier tool results in this conversation.\n"
        f"- When user asks to \"create\" something, use designer_set_pages with all pages.\n"
        f"- When user asks for a specific change, prefer the smallest targeted tool that preserves the existing page.\n"
        f"- Before any full-page rewrite with designer_update_page, call designer_get_page_html for that page so you preserve existing layout and assets.\n"
        f"- Files attached in Designer are persisted as project references. Reuse them across turns and call designer_get_reference when you need the exact extracted content again.\n"
        f"- When the user asks for speaker notes, presenter notes, or a talk track for a page, use designer_generate_notes instead of rewriting the page HTML.\n"
        f"- When the user wants a social, story, document, or other canvas change, use designer_resize_project before reworking layout details.\n"
        f"- When the user wants a shareable link to the deck, use designer_publish_link instead of describing a manual export flow.\n"
        f"- When the user asks for a standard section pattern like metrics, feature cards, testimonials, pricing, or timeline steps, prefer designer_insert_component before writing a custom fragment from scratch.\n"
        f"- When the user asks for review, audit, polish, fix readability, fix contrast, or tighten spacing, call designer_critique_page first and then designer_apply_repairs only for the categories that matter.\n"
        f"- For attached, pasted, generated, or local images, use designer_insert_image instead of recreating the page HTML manually.\n"
        f"- For moving or replacing an existing image, stock photo, or chart, use designer_move_image or designer_replace_image with the asset IDs from designer_get_project.\n"
        f"- When you must reuse an existing project image in handwritten HTML, use src=\"asset://ASSET_ID\" and keep data-asset-id=\"ASSET_ID\" on the img when possible. Never invent placeholder tokens like __ASSET_...__.\n"
        f"- For moving, duplicating, or restyling a non-image section or element, use designer_move_element, designer_duplicate_element, or designer_restyle_element with selector hints from designer_get_project.\n"
        f"- If you need a more precise target than the summary provides, call designer_get_page_html and use a CSS selector such as body > section:nth-of-type(1) > div:nth-of-type(2).\n"
        f"- When user says \"make all pages...\", update each page individually.\n"
        f"- Always explain what you changed in your text response.\n"
        f"- If brand colors aren't set, suggest professional defaults.\n"
    )
