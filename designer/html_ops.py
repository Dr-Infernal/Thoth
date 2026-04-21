"""Designer HTML helpers for page summaries and asset-safe mutations."""

from __future__ import annotations

import copy
import json
import re
import uuid

from bs4 import BeautifulSoup, Tag

ASSET_ID_ATTR = "data-thoth-id"
ASSET_KIND_ATTR = "data-thoth-kind"
ASSET_LABEL_ATTR = "data-thoth-label"
ELEMENT_ID_ATTR = "data-thoth-element-id"
COMPONENT_NAME_ATTR = "data-thoth-component"
PUBLIC_ASSET_ID_ATTR = "data-asset-id"
_HEADING_TAGS = [f"h{i}" for i in range(1, 7)]
_STRUCTURAL_TAGS = {"section", "header", "footer", "nav", "main", "article", "aside"}
_SUMMARY_TARGET_TAGS = _STRUCTURAL_TAGS | {"div", "h1", "h2", "h3", "p", "button", "a", "ul", "ol", "blockquote"}
_DISALLOWED_MUTATION_TAGS = {"html", "head", "style", "script", "meta", "link", "title"}
_XPATH_PART_RE = re.compile(r"(?P<tag>[a-zA-Z0-9_-]+)(?:\[(?P<index>\d+)\])?")
_COMPONENT_CONTAINER_TAGS = {"main", "section", "article", "div"}
_COMPONENT_CONTAINER_STRONG_HINTS = (
    "chat-area",
    "detail-panel",
    "page-content",
    "page-body",
    "content-area",
    "content-body",
    "canvas-content",
    "canvas-body",
    "workspace-content",
    "workspace-body",
    "main-content",
    "slide-content",
    "story-content",
    "primary-content",
)
_COMPONENT_CONTAINER_HINTS = (
    "content",
    "canvas",
    "workspace",
    "stage",
    "detail",
    "chat",
    "body",
    "main",
    "story",
    "slide",
    "center",
    "column",
)
_COMPONENT_CONTAINER_AVOID_HINTS = (
    "sidebar",
    "nav",
    "header",
    "footer",
    "toolbar",
    "settings",
    "recent",
    "avatar",
    "logo",
    "input",
    "controls",
    "actions",
    "tabs",
    "filter",
    "search",
    "topbar",
    "right-panel",
    "left-panel",
    "badge",
)


def wrap_asset_fragment(
    fragment_html: str,
    asset_kind: str,
    *,
    label: str = "",
    asset_id: str = "",
) -> tuple[str, str]:
    """Wrap an inserted asset so later tools can target it safely."""

    resolved_id = asset_id or f"{asset_kind}-{uuid.uuid4().hex[:8]}"
    attrs = [
        f'id="{resolved_id}"',
        f'{ASSET_ID_ATTR}="{resolved_id}"',
        f'{PUBLIC_ASSET_ID_ATTR}="{resolved_id}"',
        f'{ASSET_KIND_ATTR}="{_escape_attr(asset_kind)}"',
    ]
    if label:
        attrs.append(f'{ASSET_LABEL_ATTR}="{_escape_attr(label)}"')
    wrapper = (
        "<div "
        + " ".join(attrs)
        + ' style="display:flex; flex-direction:column; align-items:center; '
          'gap:4px; margin:16px auto; max-width:100%;">'
        + fragment_html
        + "</div>"
    )
    return wrapper, resolved_id


def summarize_page_html(page_html: str) -> dict:
    """Return a compact, structured summary of a page's current HTML."""

    soup = BeautifulSoup(page_html or "", "html.parser")
    root = soup.body or soup
    assets = []
    seen_asset_ids: set[str] = set()
    for block in _iter_asset_blocks(root):
        asset = _describe_asset(block)
        if asset is None:
            continue
        asset_id = asset.get("id", "")
        dedupe_key = asset_id or f"anon:{len(assets)}"
        if dedupe_key in seen_asset_ids:
            continue
        seen_asset_ids.add(dedupe_key)
        assets.append(asset)
        if len(assets) >= 12:
            break

    headings = [_clean_text(tag.get_text(" ", strip=True)) for tag in root.find_all(_HEADING_TAGS, limit=6)]
    text_preview = [
        _clean_text(tag.get_text(" ", strip=True))
        for tag in root.find_all(["p", "li", "blockquote"], limit=6)
        if _clean_text(tag.get_text(" ", strip=True))
    ]
    links = []
    for link in root.find_all("a", href=True, limit=4):
        links.append({
            "text": _clean_text(link.get_text(" ", strip=True)),
            "href": link.get("href", ""),
        })
    buttons = [
        _clean_text(button.get_text(" ", strip=True))
        for button in root.find_all("button", limit=4)
        if _clean_text(button.get_text(" ", strip=True))
    ]
    components = []
    for tag in root.find_all(attrs={COMPONENT_NAME_ATTR: True}, limit=12):
        selector_hint = build_selector_hint(tag, root)
        components.append({
            "component_name": tag.get(COMPONENT_NAME_ATTR, ""),
            "element_id": ensure_element_identifier(tag),
            "selector_hint": selector_hint,
            "text_preview": _clean_text(tag.get_text(" ", strip=True))[:120],
        })
    targetable_elements = []
    seen_selectors: set[str] = set()
    for tag in _iter_targetable_elements(root):
        selector_hint = build_selector_hint(tag, root)
        if not selector_hint or selector_hint in seen_selectors:
            continue
        seen_selectors.add(selector_hint)
        targetable_elements.append({
            "tag": tag.name,
            "element_id": tag.get(ELEMENT_ID_ATTR, ""),
            "id": tag.get("id", "") if tag.get(ASSET_ID_ATTR) is None else "",
            "classes": _class_list(tag)[:3],
            "text_preview": _clean_text(tag.get_text(" ", strip=True))[:120],
            "selector_hint": selector_hint,
        })
        if len(targetable_elements) >= 12:
            break
    return {
        "headings": headings,
        "text_preview": text_preview,
        "buttons": buttons,
        "links": links,
        "assets": assets,
        "components": components,
        "targetable_elements": targetable_elements,
        "element_counts": {
            "headings": len(root.find_all(_HEADING_TAGS)),
            "paragraphs": len(root.find_all("p")),
            "lists": len(root.find_all(["ul", "ol"])),
            "images": len(root.find_all("img")),
            "buttons": len(root.find_all("button")),
            "links": len(root.find_all("a")),
        },
    }


def move_asset_in_html(
    page_html: str,
    asset_ref: str,
    position: str,
    target_ref: str = "",
) -> tuple[str, str]:
    """Move an existing asset block within a page."""

    soup = BeautifulSoup(page_html or "", "html.parser")
    root = soup.body or soup
    asset_block = _find_asset_block(root, asset_ref)
    if asset_block is None:
        raise ValueError(f"Could not find image or asset '{asset_ref}'.")

    target_block = None
    normalized_position = position.strip().lower()
    if normalized_position in {"before", "after"}:
        if not target_ref:
            raise ValueError("target_ref is required when position is 'before' or 'after'.")
        target_block = _find_asset_block(root, target_ref)
        if target_block is None:
            raise ValueError(f"Could not find target asset '{target_ref}'.")
        if target_block is asset_block:
            raise ValueError("The source and target assets are the same.")

    movable = asset_block.extract()
    if normalized_position == "top":
        _insert_at_top(root, movable)
    elif normalized_position == "bottom":
        root.append(movable)
    elif normalized_position == "before" and target_block is not None:
        target_block.insert_before(movable)
    elif normalized_position == "after" and target_block is not None:
        target_block.insert_after(movable)
    else:
        raise ValueError("position must be one of: top, bottom, before, after.")

    return str(soup), _asset_identifier(movable)


def find_asset_identifier_in_html(page_html: str, asset_ref: str) -> str:
    """Resolve an asset reference to the stored asset identifier for a page."""

    soup = BeautifulSoup(page_html or "", "html.parser")
    root = soup.body or soup
    asset_block = _find_asset_block(root, asset_ref)
    if asset_block is None:
        raise ValueError(f"Could not find image or asset '{asset_ref}'.")
    return _asset_identifier(asset_block)


def replace_asset_in_html(
    page_html: str,
    asset_ref: str,
    replacement_fragment_html: str,
    asset_kind: str,
    *,
    label: str = "",
) -> tuple[str, str]:
    """Replace an asset block while preserving its public identifier."""

    soup = BeautifulSoup(page_html or "", "html.parser")
    root = soup.body or soup
    asset_block = _find_asset_block(root, asset_ref)
    if asset_block is None:
        raise ValueError(f"Could not find image or asset '{asset_ref}'.")

    asset_id = _asset_identifier(asset_block)
    wrapped_html, resolved_id = wrap_asset_fragment(
        replacement_fragment_html,
        asset_kind,
        label=label,
        asset_id=asset_id,
    )
    replacement_soup = BeautifulSoup(wrapped_html, "html.parser")
    replacement_block = _first_tag(replacement_soup)
    if replacement_block is None:
        raise ValueError("Replacement fragment did not produce a valid HTML element.")

    asset_block.replace_with(replacement_block)
    return str(soup), resolved_id


def move_element_in_html(
    page_html: str,
    *,
    selector: str = "",
    element_ref: str = "",
    xpath: str = "",
    position: str = "bottom",
    target_selector: str = "",
    target_ref: str = "",
    target_xpath: str = "",
) -> tuple[str, str, str]:
    """Move a general DOM element within a page."""

    soup = BeautifulSoup(page_html or "", "html.parser")
    root = soup.body or soup
    element = _resolve_target_element(soup, selector=selector, element_ref=element_ref, xpath=xpath)
    if element is None:
        raise ValueError("Could not find the requested element.")
    _validate_mutable_tag(element, action="move", allow_body=False)

    normalized_position = position.strip().lower()
    if normalized_position in {"before", "after"}:
        target = _resolve_target_element(
            soup,
            selector=target_selector,
            element_ref=target_ref,
            xpath=target_xpath,
        )
        if target is None:
            raise ValueError("Could not find the target element for move.")
        if target is element:
            raise ValueError("The source and target elements are the same.")
        _validate_mutable_tag(target, action="move target", allow_body=False)
    else:
        target = None

    movable = element.extract()
    element_id = ensure_element_identifier(movable)
    _insert_element(root, movable, normalized_position, target)
    return str(soup), element_id, build_selector_hint(movable, root)


def duplicate_element_in_html(
    page_html: str,
    *,
    selector: str = "",
    element_ref: str = "",
    xpath: str = "",
    position: str = "after",
    target_selector: str = "",
    target_ref: str = "",
    target_xpath: str = "",
) -> tuple[str, str, str]:
    """Duplicate a DOM element and insert the copy within a page."""

    soup = BeautifulSoup(page_html or "", "html.parser")
    root = soup.body or soup
    element = _resolve_target_element(soup, selector=selector, element_ref=element_ref, xpath=xpath)
    if element is None:
        raise ValueError("Could not find the requested element.")
    _validate_mutable_tag(element, action="duplicate", allow_body=False)

    normalized_position = position.strip().lower()
    if normalized_position in {"before", "after"}:
        target = _resolve_target_element(
            soup,
            selector=target_selector,
            element_ref=target_ref,
            xpath=target_xpath,
        ) if (target_selector or target_ref or target_xpath) else element
        if target is None:
            raise ValueError("Could not find the target element for duplication.")
        _validate_mutable_tag(target, action="duplicate target", allow_body=False)
    else:
        target = None

    duplicate = copy.copy(element)
    _reassign_internal_identifiers(duplicate)
    element_id = ensure_element_identifier(duplicate)
    _insert_element(root, duplicate, normalized_position, target)
    return str(soup), element_id, build_selector_hint(duplicate, root)


def restyle_element_in_html(
    page_html: str,
    *,
    selector: str = "",
    element_ref: str = "",
    xpath: str = "",
    style_updates: str = "",
    add_classes: str = "",
    remove_classes: str = "",
) -> tuple[str, str, str]:
    """Apply inline style and class changes to a DOM element."""

    if not style_updates.strip() and not add_classes.strip() and not remove_classes.strip():
        raise ValueError("No style or class changes were provided.")

    soup = BeautifulSoup(page_html or "", "html.parser")
    root = soup.body or soup
    element = _resolve_target_element(soup, selector=selector, element_ref=element_ref, xpath=xpath)
    if element is None:
        raise ValueError("Could not find the requested element.")
    _validate_mutable_tag(element, action="restyle", allow_body=True)

    element_id = ensure_element_identifier(element)
    changed = False

    style_map = _parse_inline_style(element.get("style", ""))
    updates = _parse_style_updates(style_updates)
    for prop, value in updates.items():
        if not value:
            if prop in style_map:
                style_map.pop(prop, None)
                changed = True
            continue
        if style_map.get(prop) != value:
            style_map[prop] = value
            changed = True

    if style_map:
        serialized_style = _serialize_inline_style(style_map)
        if element.get("style", "") != serialized_style:
            element["style"] = serialized_style
            changed = True
    elif element.has_attr("style"):
        del element["style"]
        changed = True

    class_names = _class_list(element)
    initial_class_names = list(class_names)
    for class_name in _split_class_tokens(add_classes):
        if class_name not in class_names:
            class_names.append(class_name)
    for class_name in _split_class_tokens(remove_classes):
        if class_name in class_names:
            class_names.remove(class_name)
    if class_names != initial_class_names:
        if class_names:
            element["class"] = class_names
        elif element.has_attr("class"):
            del element["class"]
        changed = True

    if not changed:
        raise ValueError("The requested restyle did not change the element.")

    return str(soup), element_id, build_selector_hint(element, root)


def insert_component_in_html(
    page_html: str,
    component_html: str,
    component_name: str,
    *,
    position: str = "bottom",
    target_selector: str = "",
    target_ref: str = "",
    target_xpath: str = "",
) -> tuple[str, str, str]:
    """Insert a curated component fragment into a page and return its selectors."""

    soup = BeautifulSoup(page_html or "", "html.parser")
    root = soup.body or soup
    component_soup = BeautifulSoup(component_html or "", "html.parser")
    component = _first_tag(component_soup)
    if component is None:
        raise ValueError("Component HTML did not produce a valid root element.")

    component[COMPONENT_NAME_ATTR] = component_name
    for tag in [component, *list(component.find_all(True))]:
        if tag.name in _SUMMARY_TARGET_TAGS:
            ensure_element_identifier(tag)

    normalized_position = position.strip().lower()
    if normalized_position in {"before", "after"}:
        target = _resolve_target_element(
            soup,
            selector=target_selector,
            element_ref=target_ref,
            xpath=target_xpath,
        )
        if target is None:
            raise ValueError("Could not find the target element for component insertion.")
        _validate_mutable_tag(target, action="insert component near", allow_body=False)
        insert_root = root
    else:
        target = None
        insert_root = _resolve_component_insert_root(root)

    element_id = ensure_element_identifier(component)
    _insert_element(insert_root, component, normalized_position, target)
    return str(soup), element_id, build_selector_hint(component, root)


def build_selector_hint(tag: Tag, root: Tag | BeautifulSoup | None = None) -> str:
    """Build a CSS selector hint for a tag within the current document."""

    selector_hint = _stable_selector_for_tag(tag)
    if selector_hint:
        return selector_hint

    resolved_root = root or tag.find_parent("body") or tag
    segments = []
    current: Tag | None = tag
    while isinstance(current, Tag):
        component = _selector_component(current)
        if not component:
            break
        segments.append(component)
        if current is resolved_root or current.name == "body":
            break
        current = current.parent if isinstance(current.parent, Tag) else None
    return " > ".join(reversed(segments))


def ensure_element_identifier(tag: Tag) -> str:
    """Ensure a tag has an internal stable element identifier."""

    existing = tag.get(ELEMENT_ID_ATTR, "")
    if existing:
        return existing
    identifier = f"el-{uuid.uuid4().hex[:8]}"
    tag[ELEMENT_ID_ATTR] = identifier
    return identifier


def _iter_asset_blocks(root: Tag):
    for block in root.find_all(attrs={ASSET_ID_ATTR: True}):
        yield block
    for img in root.find_all("img"):
        if img.find_parent(attrs={ASSET_ID_ATTR: True}) is None:
            yield img


def _iter_targetable_elements(root: Tag):
    for tag in root.find_all(True):
        if _is_targetable_element(tag):
            yield tag


def _is_targetable_element(tag: Tag) -> bool:
    if tag.name not in _SUMMARY_TARGET_TAGS:
        return False
    if tag.name in _DISALLOWED_MUTATION_TAGS:
        return False
    if tag.has_attr(ASSET_ID_ATTR) or tag.find_parent(attrs={ASSET_ID_ATTR: True}) is not None:
        return False

    text_preview = _clean_text(tag.get_text(" ", strip=True))
    if tag.name in _STRUCTURAL_TAGS:
        return True
    if tag.name in {"h1", "h2", "h3", "button", "a", "ul", "ol", "blockquote"}:
        return bool(text_preview) or bool(tag.get("href"))
    if tag.name == "p":
        return bool(text_preview) and (len(text_preview) >= 20 or tag.has_attr(ELEMENT_ID_ATTR))
    if tag.name == "div":
        if tag.has_attr(ELEMENT_ID_ATTR) or tag.has_attr("id"):
            return True
        if tag.get("class") and tag.find(["h1", "h2", "h3", "button", "a", "ul", "ol", "img"]):
            return True
        return len(text_preview) >= 30
    return False


def _find_asset_block(root: Tag, asset_ref: str) -> Tag | None:
    ref = asset_ref.strip().lower()
    if not ref:
        return None

    exact_match = None
    partial_match = None
    for block in _iter_asset_blocks(root):
        values = [value.lower() for value in _asset_match_values(block)]
        if ref in values:
            exact_match = block
            break
        if partial_match is None and any(ref in value for value in values):
            partial_match = block
    return exact_match or partial_match


def _asset_match_values(block: Tag) -> list[str]:
    img = block if block.name == "img" else block.find("img")
    values = [
        block.get(ASSET_ID_ATTR, ""),
        block.get(PUBLIC_ASSET_ID_ATTR, ""),
        block.get("id", ""),
        block.get(ASSET_LABEL_ATTR, ""),
    ]
    if img is not None:
        values.extend([
            img.get(PUBLIC_ASSET_ID_ATTR, ""),
            img.get("id", ""),
            img.get("alt", ""),
            img.get("title", ""),
        ])
    text_hint = _clean_text(block.get_text(" ", strip=True))
    if text_hint:
        values.append(text_hint)
    return [value for value in values if value]


def _element_match_values(tag: Tag) -> list[str]:
    values = [
        tag.get(ELEMENT_ID_ATTR, ""),
        tag.get(ASSET_ID_ATTR, ""),
        tag.get("id", ""),
        " ".join(_class_list(tag)),
        _clean_text(tag.get_text(" ", strip=True))[:160],
    ]
    return [value for value in values if value]


def _describe_asset(block: Tag) -> dict | None:
    img = block if block.name == "img" else block.find("img")
    if img is None:
        return None
    label = block.get(ASSET_LABEL_ATTR) or img.get("alt", "") or _clean_text(block.get_text(" ", strip=True))
    return {
        "id": _asset_identifier(block),
        "kind": block.get(ASSET_KIND_ATTR) or _infer_asset_kind(block, img),
        "label": label[:120],
        "alt": img.get("alt", "")[:120],
        "src_type": _source_type(img.get("src", "")),
    }


def _infer_asset_kind(block: Tag, img: Tag) -> str:
    joined = " ".join([
        block.get("id", ""),
        img.get("id", ""),
        img.get("alt", ""),
        img.get("title", ""),
    ]).lower()
    if "chart" in joined or "plotly" in joined:
        return "chart"
    return "image"


def _source_type(src: str) -> str:
    if src.startswith("data:"):
        return "data-uri"
    if src.startswith("asset://") or src.startswith("asset:"):
        return "asset-ref"
    if src.startswith("http://") or src.startswith("https://"):
        return "remote"
    if src:
        return "local"
    return "missing"


def _asset_identifier(block: Tag) -> str:
    img = block if block.name == "img" else block.find("img")
    return (
        block.get(ASSET_ID_ATTR)
        or block.get(PUBLIC_ASSET_ID_ATTR)
        or block.get("id")
        or (img.get(PUBLIC_ASSET_ID_ATTR) if img is not None else "")
        or (img.get("id") if img is not None else "")
        or ""
    )


def _stable_selector_for_tag(tag: Tag) -> str:
    if tag.has_attr(ELEMENT_ID_ATTR):
        return f'[{ELEMENT_ID_ATTR}="{_escape_css_attr(tag[ELEMENT_ID_ATTR])}"]'
    if tag.has_attr(ASSET_ID_ATTR):
        return f'[{ASSET_ID_ATTR}="{_escape_css_attr(tag[ASSET_ID_ATTR])}"]'
    if tag.has_attr("id") and tag.get("id"):
        return f'[id="{_escape_css_attr(tag["id"])}"]'
    return ""


def _selector_component(tag: Tag) -> str:
    if tag.name == "body":
        return "body"
    stable_selector = _stable_selector_for_tag(tag)
    if stable_selector:
        return stable_selector
    return f"{tag.name}:nth-of-type({_nth_of_type(tag)})"


def _nth_of_type(tag: Tag) -> int:
    index = 1
    sibling = tag.previous_sibling
    while sibling is not None:
        if isinstance(sibling, Tag) and sibling.name == tag.name:
            index += 1
        sibling = sibling.previous_sibling
    return index


def _resolve_target_element(
    soup: BeautifulSoup,
    *,
    selector: str = "",
    element_ref: str = "",
    xpath: str = "",
) -> Tag | None:
    if selector.strip():
        try:
            found = soup.select_one(selector)
        except Exception as exc:
            raise ValueError(f"Invalid CSS selector '{selector}': {exc}") from exc
        if found is not None:
            return found

    if xpath.strip():
        found = _find_tag_by_xpath(soup, xpath)
        if found is not None:
            return found

    ref = element_ref.strip().lower()
    if not ref:
        return None

    exact_match = None
    partial_match = None
    for tag in soup.find_all(True):
        values = [value.lower() for value in _element_match_values(tag)]
        if ref in values:
            exact_match = tag
            break
        if partial_match is None and any(ref in value for value in values):
            partial_match = tag
    return exact_match or partial_match


def _find_tag_by_xpath(soup: BeautifulSoup, xpath: str) -> Tag | None:
    if not xpath.startswith("/"):
        return None

    current: Tag | BeautifulSoup = soup
    for part in [segment for segment in xpath.split("/") if segment]:
        match = _XPATH_PART_RE.fullmatch(part)
        if match is None:
            return None
        tag_name = match.group("tag").lower()
        index = int(match.group("index") or "1") - 1
        children = [child for child in current.children if isinstance(child, Tag) and child.name == tag_name]
        if index < 0 or index >= len(children):
            return None
        current = children[index]
    return current if isinstance(current, Tag) else None


def _validate_mutable_tag(tag: Tag, *, action: str, allow_body: bool) -> None:
    if tag.name in _DISALLOWED_MUTATION_TAGS:
        raise ValueError(f"Cannot {action} the <{tag.name}> tag.")
    if tag.name == "body" and not allow_body:
        raise ValueError(f"Cannot {action} the <body> tag.")


def _resolve_component_insert_root(root: Tag | BeautifulSoup) -> Tag | BeautifulSoup:
    direct_children = [
        child for child in root.contents
        if isinstance(child, Tag) and child.name in _COMPONENT_CONTAINER_TAGS
    ]
    if getattr(root, "name", None) != "body":
        if len(direct_children) == 1:
            return direct_children[0]
        return root

    best_tag = None
    best_score = -1
    best_depth = -1
    for tag in root.find_all(_COMPONENT_CONTAINER_TAGS):
        score = _component_container_score(tag, root)
        if score <= 0:
            continue
        depth = _component_container_depth(tag, root)
        if score > best_score or (score == best_score and depth > best_depth):
            best_tag = tag
            best_score = score
            best_depth = depth

    if best_tag is not None:
        return best_tag
    if len(direct_children) == 1:
        return direct_children[0]
    return root


def _component_container_score(tag: Tag, root: Tag | BeautifulSoup) -> int:
    if tag.name not in _COMPONENT_CONTAINER_TAGS:
        return -1

    hint_blob = _component_hint_blob(tag)
    if _blob_contains_hint(hint_blob, _COMPONENT_CONTAINER_AVOID_HINTS):
        return -1

    ancestor = tag.parent
    while isinstance(ancestor, Tag) and ancestor is not root:
        if ancestor.name in {"aside", "nav", "header", "footer"}:
            return -1
        if _blob_contains_hint(_component_hint_blob(ancestor), _COMPONENT_CONTAINER_AVOID_HINTS):
            return -1
        ancestor = ancestor.parent

    score = 0
    if tag.name == "main":
        score += 120
    elif tag.name in {"section", "article"}:
        score += 45
    else:
        score += 25

    for hint in _COMPONENT_CONTAINER_STRONG_HINTS:
        if hint in hint_blob:
            score += 120
    for hint in _COMPONENT_CONTAINER_HINTS:
        if hint in hint_blob:
            score += 35

    direct_children = sum(1 for child in tag.children if isinstance(child, Tag))
    score += min(direct_children, 6) * 4
    score += min(len(_clean_text(tag.get_text(" ", strip=True))), 400) // 80
    if direct_children == 0:
        score -= 40
    return score


def _component_container_depth(tag: Tag, root: Tag | BeautifulSoup) -> int:
    depth = 0
    current = tag.parent
    while current is not None and current is not root:
        if isinstance(current, Tag):
            depth += 1
        current = current.parent if isinstance(current, Tag) else None
    return depth


def _component_hint_blob(tag: Tag) -> str:
    return " ".join(filter(None, [tag.get("id", ""), *_class_list(tag)])).lower()


def _blob_contains_hint(blob: str, hints: tuple[str, ...]) -> bool:
    return any(hint in blob for hint in hints)


def _insert_element(root: Tag, node: Tag, position: str, target: Tag | None) -> None:
    if position == "top":
        _insert_at_top(root, node)
        return
    if position == "bottom":
        root.append(node)
        return
    if position == "before" and target is not None:
        target.insert_before(node)
        return
    if position == "after" and target is not None:
        target.insert_after(node)
        return
    raise ValueError("position must be one of: top, bottom, before, after.")


def _reassign_internal_identifiers(tag: Tag) -> None:
    for node in [tag, *list(tag.find_all(True))]:
        if node.has_attr(ELEMENT_ID_ATTR):
            node[ELEMENT_ID_ATTR] = f"el-{uuid.uuid4().hex[:8]}"
        if node.has_attr(ASSET_ID_ATTR):
            asset_kind = node.get(ASSET_KIND_ATTR, "asset")
            new_asset_id = f"{asset_kind}-{uuid.uuid4().hex[:8]}"
            node[ASSET_ID_ATTR] = new_asset_id
            node["id"] = new_asset_id


def _parse_style_updates(style_updates: str) -> dict[str, str]:
    raw = style_updates.strip()
    if not raw:
        return {}

    if raw.startswith("{"):
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid JSON style_updates: {exc}") from exc
        if not isinstance(parsed, dict):
            raise ValueError("style_updates JSON must be an object.")
        updates = {}
        for key, value in parsed.items():
            updates[_normalize_css_property(str(key))] = "" if value in {None, ""} else str(value).strip()
        return updates

    updates = {}
    for declaration in raw.split(";"):
        declaration = declaration.strip()
        if not declaration:
            continue
        if ":" not in declaration:
            raise ValueError("style_updates must be JSON or CSS declarations like 'padding: 24px;'.")
        key, value = declaration.split(":", 1)
        updates[_normalize_css_property(key)] = value.strip()
    return updates


def _parse_inline_style(style_attr: str) -> dict[str, str]:
    if not style_attr:
        return {}
    parsed = {}
    for declaration in style_attr.split(";"):
        declaration = declaration.strip()
        if not declaration or ":" not in declaration:
            continue
        key, value = declaration.split(":", 1)
        parsed[_normalize_css_property(key)] = value.strip()
    return parsed


def _serialize_inline_style(style_map: dict[str, str]) -> str:
    return "; ".join(f"{key}: {value}" for key, value in style_map.items() if value)


def _normalize_css_property(name: str) -> str:
    return name.strip().lower()


def _class_list(tag: Tag) -> list[str]:
    raw = tag.get("class", [])
    if isinstance(raw, list):
        return [str(value) for value in raw if str(value).strip()]
    if isinstance(raw, str):
        return [token for token in raw.split() if token]
    return []


def _split_class_tokens(value: str) -> list[str]:
    tokens = []
    for chunk in value.replace(",", " ").split():
        token = chunk.strip()
        if token and token not in tokens:
            tokens.append(token)
    return tokens


def _escape_css_attr(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def _insert_at_top(root: Tag, node: Tag) -> None:
    for child in root.contents:
        if isinstance(child, Tag):
            child.insert_before(node)
            return
        if str(child).strip():
            child.insert_before(node)
            return
    root.append(node)


def _first_tag(soup: BeautifulSoup) -> Tag | None:
    for child in soup.contents:
        if isinstance(child, Tag):
            return child
    return None


def _clean_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _escape_attr(value: str) -> str:
    return (
        value.replace("&", "&amp;")
        .replace('"', "&quot;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )