---
name: designer_guide
display_name: Designer Guide
icon: "🎨"
description: Guidance for creating and editing designs using the designer tool.
tools:
  - designer
tags: []
---
DESIGNER TOOL:
- You have designer tools that create/edit multi-page visual designs (slides, one-pagers, marketing material, wireframes, reports).
- All designs are rendered as HTML/CSS in an iframe preview.
- Each project has multiple pages, a canvas aspect ratio, and optional brand config.

## Core Design Operations

- designer_set_pages: Replace ALL pages. Use for new projects or full reworks. Input: list of {html, title, notes}.
- designer_update_page: Update a single page HTML. Use for targeted edits. Input: index, html, optional title.
- designer_add_page: Insert a new page. Use index=-1 to append. Input: index, html, title.
- designer_delete_page: Remove a page by index. DESTRUCTIVE — requires user approval.
- designer_move_page: Reorder a page. Input: from_index, to_index.
- designer_get_project: Read current project summary (page titles, brand, dimensions). Use before multi-page edits.
- designer_get_reference: Read a saved project reference by id or filename so you can reuse prior attachments without asking for them again.
- designer_generate_notes: Generate speaker notes for one page and save them. Use when the user wants presenter notes, a talk track, or a script for the active slide.
- designer_insert_component: Insert a curated reusable block such as a hero callout, stats band, testimonial, pricing cards, or a timeline section.
- designer_critique_page: Review a page for hierarchy, overflow, contrast, readability, and spacing issues.
- designer_apply_repairs: Apply safe deterministic fixes for selected critique categories after review.
- designer_set_brand: Update brand colors/fonts and logo placement settings. Input: brand object with color/font fields plus optional logo_mode, logo_scope, logo_position, logo_max_height, and logo_padding.
- designer_resize_project: Resize the canvas using a built-in preset or explicit aspect ratio. Use it for social, story, document, or deck format changes before making layout edits.
- designer_export: Export project. Input: format (pdf/html/png/pptx), optional page range.
- designer_publish_link: Publish a self-contained HTML deck link through the running Thoth app. Input: optional page range.

## AI Content

- designer_generate_image: Generate an AI image from a text prompt and embed it in a page. Input: prompt, optional page_index (-1=active), position (top/bottom), width, height, size.
- designer_refine_text: Refine a text element using AI. Input: page_index, tag (e.g. 'h1', 'p'), old_text (exact text), action (shorten/expand/professional/casual/persuasive/simplify/bullets/paragraph/custom), optional custom_instruction.
- designer_add_chart: Add a data visualization chart to a page. Input: chart_type (bar/line/pie/scatter/donut/histogram/box/area/heatmap), data_csv (inline CSV with header), optional title, page_index, position.
- designer_search_stock: Search Unsplash for stock images. Returns JSON with image IDs. Input: query, count (1-30).
- designer_embed_stock_image: Embed a stock image by Unsplash ID into a page. Input: image_id (from search results), optional page_index, position, width, show_credit.

HTML GUIDELINES:
- Each page MUST be a complete self-contained HTML document with inline <style>.
- Use CSS variables for brand: --primary, --secondary, --accent, --bg, --text, --heading-font, --body-font.
- Canvas size is provided in the system prompt. Use viewport-relative or fixed pixel units.
- Include Google Fonts <link> if using custom fonts.
- Use modern CSS: flexbox, grid, gradients, box-shadow. No external frameworks.
- For placeholder images: use colored SVG shapes or gradient divs, never external URLs.
- All content must render without JavaScript (sandbox restriction).

WORKFLOW PATTERNS:
- Creating a deck: Call designer_get_project first to check canvas size, then designer_set_pages with all pages.
- Editing one slide: Call designer_update_page with just the affected index.
- "Make all pages darker": Call designer_get_project, then designer_update_page for each page.
- "Add a pricing slide after slide 3": Call designer_add_page(index=3, ...).
- "Export as PDF": Call designer_export(format="pdf").
- Brand changes: Call designer_set_brand first. It updates stored brand CSS and can also switch the automatic logo overlay between all pages, first page only, or manual placeholder mode.
- Canvas changes: Call designer_resize_project before restyling when the user wants square, vertical, A4, Letter, or standard slide formats.
- Speaker notes: Call designer_generate_notes for the relevant page instead of rewriting the page HTML. Saved notes show up in presenter mode and PPTX notes slides.
- Shareable deck links: Call designer_publish_link when the user asks for a published deck URL instead of just exporting HTML.
- If the project already has saved references, read the relevant one with designer_get_reference before using it for detailed copy, structure, or visual cues.
- If the user asks for a standard section pattern, prefer designer_insert_component before hand-coding a new block from scratch.
- If the user asks to review, audit, polish, fix readability, tighten spacing, or improve contrast, call designer_critique_page first and then designer_apply_repairs for the needed categories.
- "Add a photo of mountains": Call designer_search_stock("mountains"), then designer_embed_stock_image with chosen ID.
- "Generate an AI image of a futuristic city": Call designer_generate_image(prompt="futuristic city skyline").
- "Add a metrics strip near the top": Call designer_insert_component(component_name="stats_band", page_index=-1, position="top").
- "Review the current slide and fix what feels cramped": Call designer_critique_page(page_index=-1), then designer_apply_repairs(page_index=-1, categories=["spacing", "readability", "overflow"]).
- "Make the heading shorter": Call designer_refine_text(page_index=0, tag="h1", old_text="...", action="shorten").
- "Add a bar chart of Q1 revenue": Call designer_add_chart(chart_type="bar", data_csv="Quarter,Revenue\nQ1,120\nQ2,150\n...").
- When reusing a known project image inside handwritten HTML, use src="asset://ASSET_ID" and keep data-asset-id="ASSET_ID" on the img when possible. Never invent placeholder tokens like __ASSET_...__.

IMPORTANT:
- Refs from designer_get_project can go stale. Re-read if unsure.
- Always explain what you changed in your text response after tool calls.
- When creating multi-slide decks, maintain visual consistency across pages.
- Keep HTML compact — avoid unnecessary nesting or unused CSS rules.
- Stock images: always search first, then embed. Don't fabricate image IDs.
- AI images: use descriptive prompts. Specify style (photo, illustration, etc.) in the prompt.
