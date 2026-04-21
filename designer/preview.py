"""Designer — interactive iframe preview engine with aspect-ratio container, zoom, and JS bridge."""

from __future__ import annotations

import base64
import json
import logging

from nicegui import ui

from designer.render_assets import resolve_project_image_sources
from designer.storage import load_asset_bytes
from designer.state import DesignerProject, BrandConfig
from designer.interaction import inject_bridge_js

logger = logging.getLogger(__name__)

# Zoom levels
ZOOM_LEVELS = {"Fit": None, "50%": 0.5, "75%": 0.75, "100%": 1.0}


def _build_brand_css(brand: BrandConfig) -> str:
    """Build the <style> block with :root CSS variables and @font-face for a brand."""
    from designer.fonts import get_all_fonts_css, get_fallback_stack
    families = [f for f in dict.fromkeys([brand.heading_font, brand.body_font]) if f]
    font_css = get_all_fonts_css(families)
    h_fallback = get_fallback_stack(brand.heading_font or "Inter")
    b_fallback = get_fallback_stack(brand.body_font or "Inter")
    return (
        f"<style>\n{font_css}\n"
        ":root {"
        f" --primary: {brand.primary_color};"
        f" --secondary: {brand.secondary_color};"
        f" --accent: {brand.accent_color};"
        f" --bg: {brand.bg_color};"
        f" --text: {brand.text_color};"
        f" --heading-font: '{brand.heading_font}', {h_fallback};"
        f" --body-font: '{brand.body_font}', {b_fallback};"
        " }\n</style>"
    )


def _escape_attr(value: str) -> str:
    return (
        value.replace("&", "&amp;")
        .replace('"', "&quot;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def _brand_has_logo(brand: BrandConfig) -> bool:
    return bool((brand.logo_asset_id or "").strip() or brand.logo_b64)


def _logo_data_uri(project: DesignerProject | None, brand: BrandConfig) -> str:
    if project is not None and brand.logo_asset_id:
        asset = next((item for item in project.assets if item.id == brand.logo_asset_id), None)
        if asset is not None and asset.stored_name:
            data = load_asset_bytes(project.id, asset.stored_name)
            if data:
                mime = (
                    asset.mime_type
                    or brand.logo_mime_type
                    or "image/png"
                ).strip() or "image/png"
                encoded = base64.b64encode(data).decode("ascii")
                return f"data:{mime};base64,{encoded}"
    if brand.logo_b64:
        mime = (brand.logo_mime_type or "image/png").strip() or "image/png"
        return f"data:{mime};base64,{brand.logo_b64}"
    return ""


def _logo_should_render_on_page(brand: BrandConfig, page_index: int | None) -> bool:
    if not _brand_has_logo(brand):
        return False
    scope = (brand.logo_scope or "all").lower()
    idx = 0 if page_index is None else page_index
    if scope == "first":
        return idx == 0
    return True


def _logo_corner_style(brand: BrandConfig) -> str:
    padding = max(int(getattr(brand, "logo_padding", 24) or 24), 0)
    position = (brand.logo_position or "top_right").lower()
    corners = {
        "top_left": f"top:{padding}px;left:{padding}px;",
        "top_right": f"top:{padding}px;right:{padding}px;",
        "bottom_left": f"bottom:{padding}px;left:{padding}px;",
        "bottom_right": f"bottom:{padding}px;right:{padding}px;",
    }
    return corners.get(position, corners["top_right"])


def _build_logo_img(project: DesignerProject | None, brand: BrandConfig, *, max_width: str = "100%") -> str:
    max_height = max(int(getattr(brand, "logo_max_height", 72) or 72), 24)
    alt = _escape_attr(brand.logo_filename or "Brand logo")
    logo_uri = _logo_data_uri(project, brand)
    if not logo_uri:
        return ""
    return (
        f'<img src="{logo_uri}" '
        f'alt="{alt}" '
        f'style="display:block;width:auto;height:auto;max-height:{max_height}px;'
        f'max-width:{max_width};object-fit:contain;" />'
    )


def _build_logo_overlay(project: DesignerProject | None, brand: BrandConfig) -> str:
    max_width = f"calc(100% - {max(int(getattr(brand, 'logo_padding', 24) or 24), 0) * 2}px)"
    image_html = _build_logo_img(project, brand, max_width=max_width)
    if not image_html:
        return ""
    return (
        f'<div data-thoth-brand-logo="auto" aria-hidden="true" '
        f'style="position:absolute;{_logo_corner_style(brand)}'
        f'z-index:2147483000;pointer-events:none;">'
        f'{image_html}'
        f'</div>'
    )


def inject_brand_variables(
    html: str,
    brand: BrandConfig | None,
    *,
    project: DesignerProject | None = None,
    page_index: int | None = None,
) -> str:
    """Inject brand CSS at render time.

    Always appends at the END of <head> (before </head>) so that CSS cascade
    makes brand variables win over any earlier :root in template styles.
    Also replaces ``<!-- BRAND_LOGO -->`` markers with the actual logo ``<img>``.
    This is render-time only — safe to call repeatedly, never stored.
    """
    if not brand:
        return html
    css = _build_brand_css(brand)
    if "</head>" in html:
        html = html.replace("</head>", f"{css}</head>", 1)
    elif "<head>" in html:
        html = html.replace("<head>", f"<head>{css}", 1)
    else:
        html = css + html

    has_logo_placeholder = "<!-- BRAND_LOGO" in html
    if _brand_has_logo(brand) and has_logo_placeholder:
        logo_html = _build_logo_img(project, brand)
        if logo_html:
            html = html.replace("<!-- BRAND_LOGO -->", logo_html)

    if (
        _brand_has_logo(brand)
        and (brand.logo_mode or "auto").lower() != "manual"
        and not has_logo_placeholder
        and _logo_should_render_on_page(brand, page_index)
    ):
        overlay = _build_logo_overlay(project, brand)
        if overlay and "</body>" in html:
            html = html.replace("</body>", f"{overlay}</body>", 1)
        elif overlay:
            html += overlay
    return html


def render_page_html(
    project: DesignerProject,
    page_html: str,
    *,
    page_index: int | None = None,
) -> str:
    """Render one page with resolved image references and brand variables applied."""

    resolved_html = resolve_project_image_sources(page_html, project)
    return inject_brand_variables(resolved_html, project.brand, project=project, page_index=page_index)


import re as _re

# Matches a standalone brand <style> block (produced by _build_brand_css)
_BRAND_STYLE_RE = _re.compile(
    r'<style>\s*(?:/\*[^*]*\*/\s*)?(?:@font-face[^}]*}\s*)*:root\s*\{[^}]*--primary:[^}]*\}\s*</style>',
    _re.DOTALL,
)

# Matches :root { ... --primary: ... } within ANY context (e.g. inside
# a larger <style> block from templates that also has body/card rules)
_ROOT_VARS_RE = _re.compile(
    r':root\s*\{[^}]*--primary:[^}]*\}',
    _re.DOTALL,
)


def _build_root_block(brand: BrandConfig) -> str:
    """Build just the :root { ... } CSS declaration (no <style> wrapper)."""
    from designer.fonts import get_fallback_stack
    h_fallback = get_fallback_stack(brand.heading_font)
    b_fallback = get_fallback_stack(brand.body_font)
    return (
        ":root {"
        f" --primary: {brand.primary_color};"
        f" --secondary: {brand.secondary_color};"
        f" --accent: {brand.accent_color};"
        f" --bg: {brand.bg_color};"
        f" --text: {brand.text_color};"
        f" --heading-font: '{brand.heading_font}', {h_fallback};"
        f" --body-font: '{brand.body_font}', {b_fallback};"
        " }"
    )


def update_brand_in_html(html: str, brand: BrandConfig) -> str:
    """Replace the existing brand CSS in stored page HTML.

    Tries three strategies in order:
    1. Replace a standalone brand <style> block (from _build_brand_css).
    2. Replace the :root { ... } declaration inside a larger <style> block
       (e.g. from templates that also contain body/card rules).
    3. Inject a full brand <style> block at the end of <head>.
    """
    css = _build_brand_css(brand)

    # Strategy 1: standalone brand <style> block
    new_html, n = _BRAND_STYLE_RE.subn(css, html, count=1)
    if n:
        return new_html

    # Strategy 2: :root block inside a larger <style> (template pages)
    root_block = _build_root_block(brand)
    new_html, n = _ROOT_VARS_RE.subn(root_block, html, count=1)
    if n:
        return new_html

    # Strategy 3: no existing block — inject at end of <head>
    if "</head>" in html:
        return html.replace("</head>", f"{css}</head>", 1)
    if "<head>" in html:
        return html.replace("<head>", f"<head>{css}", 1)
    return css + html


def build_preview(project: DesignerProject, *,
                   on_element_click=None, on_text_edit=None,
                   on_undo_shortcut=None, on_redo_shortcut=None,
                   on_navigate=None) -> dict:
    """Build the preview panel returning a dict with refresh_fn and zoom control.

    Returns ``{"refresh": callable, "container": ui.element}``.

    Parameters
    ----------
    on_element_click : callable, optional
        Called with element info dict when user clicks an element in the preview.
    on_text_edit : callable, optional
        Called with edit detail dict when user finishes inline text editing.
    on_undo_shortcut : callable, optional
        Called when the preview iframe forwards a designer undo shortcut.
    on_redo_shortcut : callable, optional
        Called when the preview iframe forwards a designer redo shortcut.
    on_navigate : callable, optional
        Called when the page structure or active page changes (e.g. agent added
        or deleted a page).  The page navigator uses this to re-render.
    """
    _last_html: list[str | None] = [None]
    _last_structure: list[tuple[int, int, int, int]] = [
        (len(project.pages), project.active_page,
         project.canvas_width, project.canvas_height)
    ]
    _iframe_id = f"designer-preview-{project.id[:8]}"
    _zoom_value: list[str] = ["Fit"]
    _interactive: bool = on_element_click is not None or on_text_edit is not None

    with ui.column().classes("w-full h-full").style("position: relative;") as container:
        # Zoom controls bar
        with ui.row().classes("w-full items-center justify-end gap-2").style(
            "padding: 4px 8px; background: rgba(0,0,0,0.3); border-radius: 8px 8px 0 0;"
        ):
            ui.label("Zoom:").classes("text-xs text-grey-5")
            for label in ZOOM_LEVELS:
                def _set_zoom(lbl=label):
                    _zoom_value[0] = lbl
                    _apply_zoom()
                ui.button(label, on_click=_set_zoom).props(
                    "flat dense no-caps size=xs"
                ).style("font-size: 0.7rem;")

        # Aspect-ratio container
        ratio = project.canvas_width / project.canvas_height
        _sandbox = "allow-same-origin allow-scripts" if _interactive else "allow-same-origin"
        with ui.element("div").classes("w-full flex-grow").style(
            "display: flex; align-items: center; justify-content: center;"
            "overflow: hidden; background: #111;"
        ) as _ratio_wrap:
            # Sized wrapper — JS will set width/height to the scaled dims
            _wrapper_id = f"designer-wrapper-{project.id[:8]}"
            ui.html(
                f'<div id="{_wrapper_id}" style="position: relative; overflow: hidden;">'
                f'<iframe id="{_iframe_id}" '
                f'sandbox="{_sandbox}" '
                f'style="border: none; background: white; '
                f'width: {project.canvas_width}px; height: {project.canvas_height}px; '
                f'transform-origin: top left; position: absolute; top: 0; left: 0;" '
                f'></iframe></div>',
                sanitize=False,
            )

    def _apply_zoom():
        zoom = ZOOM_LEVELS.get(_zoom_value[0])
        if zoom is None:
            # Fit: scale iframe and size wrapper to match
            js = f'''
                (function() {{
                    var iframe = document.getElementById("{_iframe_id}");
                    var wrapper = document.getElementById("{_wrapper_id}");
                    if (!iframe || !wrapper) return;
                    var container = wrapper.closest(".flex-grow");
                    if (!container) return;
                    var pw = container.clientWidth;
                    var ph = container.clientHeight;
                    var scale = Math.min(pw / {project.canvas_width}, ph / {project.canvas_height});
                    iframe.style.transform = "scale(" + scale + ")";
                    wrapper.style.width = Math.ceil({project.canvas_width} * scale) + "px";
                    wrapper.style.height = Math.ceil({project.canvas_height} * scale) + "px";
                }})();
            '''
        else:
            js = f'''
                (function() {{
                    var iframe = document.getElementById("{_iframe_id}");
                    var wrapper = document.getElementById("{_wrapper_id}");
                    if (!iframe) return;
                    iframe.style.transform = "scale({zoom})";
                    if (wrapper) {{
                        wrapper.style.width = Math.ceil({project.canvas_width} * {zoom}) + "px";
                        wrapper.style.height = Math.ceil({project.canvas_height} * {zoom}) + "px";
                    }}
                }})();
            '''
        ui.run_javascript(js)

    def _refresh(force: bool = False):
        """Refresh the preview iframe with current page HTML.

        When ``force`` is true, bypass the HTML cache guard and hard-reload the
        iframe srcdoc. This is used after undo/redo style state restores where
        the preview DOM may have diverged from the stored page HTML.
        """
        if not project.pages:
            return
        # Detect structural changes (page added/deleted/navigated/resized)
        cur_structure = (len(project.pages), project.active_page,
                         project.canvas_width, project.canvas_height)
        structure_changed = cur_structure != _last_structure[0]
        dims_changed = (cur_structure[2] != _last_structure[0][2] or
                        cur_structure[3] != _last_structure[0][3])
        if structure_changed:
            _last_structure[0] = cur_structure
            if on_navigate:
                on_navigate()
        # If canvas dimensions changed, resize the iframe element
        if dims_changed:
            cw, ch = project.canvas_width, project.canvas_height
            ui.run_javascript(f'''
                (function() {{
                    var iframe = document.getElementById("{_iframe_id}");
                    if (iframe) {{
                        iframe.style.width = "{cw}px";
                        iframe.style.height = "{ch}px";
                    }}
                }})();
            ''')
        idx = max(0, min(project.active_page, len(project.pages) - 1))
        page = project.pages[idx]
        html = render_page_html(project, page.html, page_index=idx)
        # Inject interaction bridge JS when interactive mode is on
        if _interactive:
            html = inject_bridge_js(html)
        if not force and html == _last_html[0] and not structure_changed:
            return
        safe_html = json.dumps(html)
        if force:
            js = f'''
                (function() {{
                    var iframe = document.getElementById("{_iframe_id}");
                    if (!iframe) return;
                    var replacement = iframe.cloneNode(false);
                    iframe.replaceWith(replacement);
                    replacement.srcdoc = {safe_html};
                }})();
            '''
        else:
            js = f'''
                (function() {{
                    var iframe = document.getElementById("{_iframe_id}");
                    if (iframe) iframe.srcdoc = {safe_html};
                }})();
            '''
        ui.run_javascript(js)
        _last_html[0] = html
        # Re-apply zoom after content change
        _apply_zoom()

    # Initial render + poll timer
    _refresh()

    def _safe_refresh():
        try:
            _refresh()
        except RuntimeError:
            pass  # parent slot deleted — page navigated away
    ui.timer(0.5, _safe_refresh)

    # Register parent-side message listener for interactive bridge
    if _interactive:
        _setup_message_listener(
            on_element_click=on_element_click,
            on_text_edit=on_text_edit,
            on_undo_shortcut=on_undo_shortcut,
            on_redo_shortcut=on_redo_shortcut,
        )

    return {
        "refresh": _refresh,
        "force_refresh": lambda: _refresh(force=True),
        "container": container,
    }


def _setup_message_listener(
    *,
    on_element_click=None,
    on_text_edit=None,
    on_undo_shortcut=None,
    on_redo_shortcut=None,
):
    """Register a window.message listener that forwards iframe events to Python."""
    # Use a hidden NiceGUI element to receive events from JS
    bridge = ui.element("div").style("display:none;")

    def _handle_bridge_event(e):
        data = e.args or {}
        msg_type = data.get("msgType", "")
        detail = data.get("detail", {})
        if msg_type == "element-click" and on_element_click:
            on_element_click(detail)
        elif msg_type == "text-edit" and on_text_edit:
            on_text_edit(detail)
        elif msg_type == "designer-undo-shortcut" and on_undo_shortcut:
            on_undo_shortcut()
        elif msg_type == "designer-redo-shortcut" and on_redo_shortcut:
            on_redo_shortcut()

    bridge.on("bridge_msg", _handle_bridge_event)

    # Register JS listener that forwards postMessage events to the bridge element
    js = f"""
    (function() {{
        window.__thothDesignerBridgeId = {bridge.id};
        if (window.__thothDesignerListener) return;
        window.__thothDesignerListener = true;

        window.addEventListener('message', function(e) {{
            var data = e.data;
            if (!data || !data.type) return;
            if (data.type === 'element-click' || data.type === 'text-edit' ||
                data.type === 'edit-start' || data.type === 'edit-cancel' ||
                data.type === 'designer-undo-shortcut' || data.type === 'designer-redo-shortcut') {{
                var bridge = getElement(window.__thothDesignerBridgeId);
                if (!bridge) return;
                var bridgeEvent = new Event('bridge_msg', {{ bubbles: true }});
                bridgeEvent.msgType = data.type;
                bridgeEvent.detail = data.detail || {{}};
                bridge.dispatchEvent(bridgeEvent);
            }}
        }});
    }})();
    """
    ui.run_javascript(js)
