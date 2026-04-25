// Thoth Designer — interactive runtime bridge.
// Loaded inside the preview iframe and (at publish time) into the exported
// site bundle.  The agent writes declarative data-thoth-* attributes only;
// this file interprets them.  No user-authored JS runs here — see the
// sanitize_agent_html pipeline.
(function () {
    "use strict";
    if (window.__thothRuntime) return;
    window.__thothRuntime = true;

    var doc = document;
    var html = doc.documentElement;

    // ── Route table ────────────────────────────────────────────────
    // Pages are rendered as <section data-thoth-route="<id>"> blocks.
    // Optionally a <script type="application/json" id="__thoth_routes__">
    // payload carries {initial, order, labels}.
    var routesMeta = {initial: "", order: [], labels: {}};
    try {
        var meta = doc.getElementById("__thoth_routes__");
        if (meta) routesMeta = JSON.parse(meta.textContent || "{}") || routesMeta;
    } catch (e) { /* ignore */ }

    function getRouteSections() {
        // Only elements we explicitly marked as route hosts — never inner
        // agent-authored elements that happen to carry data-thoth-route.
        return Array.prototype.slice.call(
            doc.querySelectorAll("[data-thoth-route-host]")
        );
    }

    function getActiveRoute() {
        return html.getAttribute("data-thoth-active-route") || "";
    }

    function setActiveRoute(routeId, opts) {
        opts = opts || {};
        var sections = getRouteSections();
        if (!sections.length) return;
        var target = null;
        for (var i = 0; i < sections.length; i++) {
            if (sections[i].getAttribute("data-thoth-route") === routeId) {
                target = sections[i];
                break;
            }
        }
        if (!target) {
            // fall back to first available section
            target = sections[0];
            routeId = target.getAttribute("data-thoth-route") || routeId;
        }
        var transition = opts.transition ||
            target.getAttribute("data-thoth-transition") || "fade";
        html.setAttribute("data-thoth-active-route", routeId);
        html.setAttribute("data-thoth-transition", transition);
        for (var j = 0; j < sections.length; j++) {
            var s = sections[j];
            var isActive = s === target;
            s.toggleAttribute("data-thoth-route-active", isActive);
            s.setAttribute("aria-hidden", isActive ? "false" : "true");
        }
        post({type: "thoth:navigate", route: routeId, transition: transition});
    }

    function toggleState(key, opts) {
        if (!key) return;
        opts = opts || {};
        var current = (html.getAttribute("data-thoth-state") || "")
            .split(/\s+/).filter(Boolean);
        var idx = current.indexOf(key);
        var isOn;
        if (idx >= 0) { current.splice(idx, 1); isOn = false; }
        else { current.push(key); isOn = true; }
        if (current.length) html.setAttribute("data-thoth-state", current.join(" "));
        else html.removeAttribute("data-thoth-state");

        // Mirror the new on/off value onto the clicked control (if any)
        // and any other control that targets the same state key. This
        // lets a common pattern — `<button aria-pressed data-thoth-
        // action="toggle_state:foo">` styled via the [aria-pressed]
        // selector — visually update without any authored JS.
        var controls = doc.querySelectorAll(
            '[data-thoth-action="toggle_state:' + cssEscape(key) + '"]'
        );
        for (var i = 0; i < controls.length; i++) {
            var c = controls[i];
            if (c.hasAttribute("aria-pressed")) {
                c.setAttribute("aria-pressed", isOn ? "true" : "false");
            }
            // Always set data-thoth-active so stylesheets have a
            // consistent hook regardless of the source element's role.
            c.toggleAttribute("data-thoth-active", isOn);
        }

        post({type: "thoth:state", key: key, on: isOn});
    }

    function playMedia(assetId) {
        if (!assetId) return;
        var el = doc.querySelector(
            '[data-thoth-id="' + cssEscape(assetId) + '"] video,'
            + '[data-thoth-id="' + cssEscape(assetId) + '"] audio,'
            + 'video[data-thoth-id="' + cssEscape(assetId) + '"],'
            + 'audio[data-thoth-id="' + cssEscape(assetId) + '"]'
        );
        if (el && typeof el.play === "function") {
            try { el.play(); } catch (e) { /* autoplay denied */ }
        }
        post({type: "thoth:media", assetId: assetId});
    }

    function cssEscape(s) {
        return String(s).replace(/(["\\])/g, "\\$1");
    }

    function post(payload) {
        try {
            window.parent && window.parent.postMessage(
                Object.assign({source: "thoth-runtime"}, payload), "*"
            );
        } catch (e) { /* cross-origin in published bundle */ }
    }

    // ── Action dispatch ────────────────────────────────────────────
    function handleAction(actionStr, ev) {
        if (!actionStr) return false;
        var parts = actionStr.split(":");
        var verb = parts.shift();
        var arg = parts.join(":");
        if (verb === "navigate") {
            if (ev) ev.preventDefault();
            setActiveRoute(arg);
            return true;
        }
        if (verb === "toggle_state") {
            if (ev) ev.preventDefault();
            toggleState(arg);
            return true;
        }
        if (verb === "play_media") {
            if (ev) ev.preventDefault();
            playMedia(arg);
            return true;
        }
        return false;
    }

    doc.addEventListener("click", function (ev) {
        var t = ev.target;
        var anchor = null;
        while (t && t !== doc.body) {
            var action = t.getAttribute && t.getAttribute("data-thoth-action");
            if (action && handleAction(action, ev)) return;
            if (!anchor && t.tagName === "A") anchor = t;
            t = t.parentNode;
        }
        // Safety net: any <a> link inside the prototype that has no
        // data-thoth-action must not hijack the iframe. Without this
        // guard a CTA like <a href="/"> navigates the preview iframe
        // to whatever sits at the editor's origin (e.g. the Thoth app
        // itself — "inception"). External links still open in a new
        // tab. Internal/same-origin links are simply swallowed so the
        // prototype stays put; author should wire them with
        // data-thoth-action="navigate:<route>".
        if (anchor) {
            var href = anchor.getAttribute("href") || "";
            if (!href || href === "#" || href.charAt(0) === "#" ||
                href.indexOf("javascript:") === 0) {
                ev.preventDefault();
                return;
            }
            var isExternal = /^(https?:)?\/\//i.test(href) ||
                             /^(mailto:|tel:)/i.test(href);
            if (isExternal) {
                // Force external links to open in a new tab rather than
                // replace the preview iframe.
                anchor.setAttribute("target", "_blank");
                anchor.setAttribute("rel", "noopener noreferrer");
                return; // let the browser handle the new-tab open
            }
            // Same-origin relative link without a data-thoth-action —
            // block it so the iframe doesn't load the editor host.
            ev.preventDefault();
            post({type: "thoth:deadlink", href: href});
        }
    }, true);

    // Prototype forms should never navigate the iframe away. Without
    // an explicit data-thoth-action on the submit control we just
    // swallow the submit event and let the author wire interactivity.
    doc.addEventListener("submit", function (ev) {
        var form = ev.target;
        if (form && form.tagName === "FORM") {
            ev.preventDefault();
            post({type: "thoth:formsubmit",
                  action: form.getAttribute("action") || ""});
        }
    }, true);

    // ── Parent → child control (editor sync) ──────────────────────
    window.addEventListener("message", function (ev) {
        var data = ev.data || {};
        if (data.target !== "thoth-runtime") return;
        if (data.type === "navigate") setActiveRoute(data.route);
        else if (data.type === "toggle_state") toggleState(data.key);
        else if (data.type === "play_media") playMedia(data.assetId);
    });

    // ── Initial activation ─────────────────────────────────────────
    function boot() {
        var initial = routesMeta.initial;
        if (!initial) {
            var first = doc.querySelector("[data-thoth-route-host]");
            if (first) initial = first.getAttribute("data-thoth-route") || "";
        }
        if (initial) setActiveRoute(initial, {transition: "none"});
        post({type: "thoth:ready", route: getActiveRoute()});
    }
    if (doc.readyState === "loading") {
        doc.addEventListener("DOMContentLoaded", boot);
    } else {
        boot();
    }
})();
