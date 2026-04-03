"""Thoth UI — ``<head>`` HTML injection (CSS + JS).

Call ``inject_head_html()`` once per page load to add highlight.js,
vis-network, and custom Thoth styles/scripts.
"""

from __future__ import annotations

from nicegui import ui

HEAD_HTML = """\
<link rel="stylesheet"
      href="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/styles/atom-one-dark.min.css">
<script src="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/highlight.min.js"></script>
<script src="/static/vis-network.min.js"></script>
<script src="/static/mermaid.min.js"></script>
<script>mermaid.initialize({startOnLoad: false, theme: 'dark', securityLevel: 'strict'});</script>
<style>
    .thoth-msg pre { overflow-x: auto; max-width: 100%; }
    .thoth-msg a { color: #64b5f6; }
    .thoth-msg a:hover { text-decoration: underline; }
    .thoth-msg-row {
        display: flex;
        gap: 0.75rem;
        padding: 0.75rem 0.5rem;
        width: 100%;
        border-radius: 8px;
    }
    .thoth-msg-row-user {
        background: rgba(255, 255, 255, 0.04);
    }
    .thoth-avatar {
        width: 36px;
        height: 36px;
        min-width: 36px;
        border-radius: 50%;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 1.1rem;
        margin-top: 2px;
    }
    .thoth-avatar-user { background: #1976d2; color: white; }
    .thoth-avatar-bot { background: #37474f; color: gold !important; }
    .thoth-msg-header {
        display: flex !important;
        align-items: baseline;
        gap: 0.5rem;
    }
    .thoth-msg-name {
        font-weight: 600;
        font-size: 0.9rem;
        color: #e0e0e0;
    }
    /* Bot name = gold */
    .thoth-msg-row:not(.thoth-msg-row-user) .thoth-msg-name {
        color: gold !important;
    }
    .thoth-msg-stamp {
        font-size: 0.7rem;
        color: #888;
        margin-left: 0.5rem;
    }
    .thoth-msg-body {
        flex: 1;
        min-width: 0;
        overflow: hidden;
        /* Override Quasar QScrollArea's user-select: none */
        -webkit-user-select: text;
        user-select: text;
        cursor: default;
    }
    .thoth-msg-body .thoth-msg,
    .thoth-msg-body p,
    .thoth-msg-body li,
    .thoth-msg-body td,
    .thoth-msg-body th,
    .thoth-msg-body span:not(.thoth-msg-name):not(.thoth-msg-stamp) {
        cursor: text;
    }
    .thoth-msg-body .nicegui-code pre {
        white-space: pre-wrap;
        word-break: break-all;
    }
    .thoth-typing .dots span {
        animation: tblink 1.4s infinite both;
    }
    .thoth-typing .dots span:nth-child(2) { animation-delay: 0.2s; }
    .thoth-typing .dots span:nth-child(3) { animation-delay: 0.4s; }
    @keyframes tblink {
        0%, 80%, 100% { opacity: 0; }
        40% { opacity: 1; }
    }
    @keyframes thoth-spin { to { transform: rotate(360deg); } }
    .thoth-spin { animation: thoth-spin 1s linear infinite; }
    .mermaid-rendered { background: rgba(255,255,255,0.03); border-radius: 8px; padding: 12px; margin: 8px 0; overflow-x: auto; }
</style>
<script>
// Make all links in chat messages open in a new tab
document.addEventListener('click', function(e) {
    const a = e.target.closest('.thoth-msg a, .thoth-msg-body a');
    if (a && a.href && !a.href.startsWith('javascript:')) {
        a.target = '_blank';
        a.rel = 'noopener noreferrer';
    }
});

// ── pywebview-only right-click context menu ─────────────────────
(function() {
    if (!window.pywebview && !navigator.userAgent.includes('pywebview')) {
        // Normal browser — let native context menu work
        // Re-check after a short delay (pywebview may inject late)
        setTimeout(function() { if (!window.pywebview) return; initThothCtx(); }, 1500);
    } else {
        initThothCtx();
    }
    function initThothCtx() {
        var menu = document.createElement('div');
        menu.id = 'thoth-ctx-menu';
        menu.style.cssText = 'display:none; position:fixed; z-index:99999; '
            + 'background:#1e1e2e; border:1px solid #444; border-radius:6px; '
            + 'padding:4px 0; min-width:140px; box-shadow:0 4px 16px rgba(0,0,0,0.5); '
            + 'font-family:sans-serif; font-size:0.85rem; color:#ddd;';
        var items = [
            {label:'Cut', icon:'\u2702', cmd:'cut', needsSel:true, needsEdit:true},
            {label:'Copy', icon:'\u2398', cmd:'copy', needsSel:true},
            {label:'Paste', icon:'\u2399', cmd:'paste', needsEdit:true},
            {sep:true},
            {label:'Select All', icon:'\u2610', cmd:'selectAll'}
        ];
        items.forEach(function(it) {
            if (it.sep) {
                var hr = document.createElement('div');
                hr.style.cssText = 'height:1px; background:#444; margin:4px 0;';
                menu.appendChild(hr); return;
            }
            var btn = document.createElement('div');
            btn.textContent = it.icon + '  ' + it.label;
            btn.dataset.cmd = it.cmd;
            btn.dataset.needsSel = it.needsSel ? '1' : '';
            btn.dataset.needsEdit = it.needsEdit ? '1' : '';
            btn.style.cssText = 'padding:6px 16px; cursor:pointer; white-space:nowrap;';
            btn.onmouseenter = function() { btn.style.background = '#333'; };
            btn.onmouseleave = function() { btn.style.background = 'none'; };
            btn.onmousedown = function(e) {
                e.preventDefault();
                var cmd = btn.dataset.cmd;
                if (cmd === 'paste') {
                    navigator.clipboard.readText().then(function(t) {
                        var el = document.activeElement;
                        if (el && (el.tagName === 'INPUT' || el.tagName === 'TEXTAREA' || el.isContentEditable)) {
                            document.execCommand('insertText', false, t);
                        }
                    }).catch(function() {});
                } else {
                    document.execCommand(cmd);
                }
                menu.style.display = 'none';
            };
            menu.appendChild(btn);
        });
        document.body.appendChild(menu);

        document.addEventListener('contextmenu', function(e) {
            e.preventDefault();
            var sel = window.getSelection().toString();
            var el = e.target.closest('input, textarea, [contenteditable]');
            menu.querySelectorAll('[data-cmd]').forEach(function(b) {
                var show = true;
                if (b.dataset.needsSel && !sel) show = false;
                if (b.dataset.needsEdit && !el) show = false;
                b.style.display = show ? 'block' : 'none';
            });
            menu.style.left = Math.min(e.clientX, window.innerWidth - 160) + 'px';
            menu.style.top = Math.min(e.clientY, window.innerHeight - 200) + 'px';
            menu.style.display = 'block';
        });
        document.addEventListener('click', function() { menu.style.display = 'none'; });
        document.addEventListener('keydown', function(e) { if (e.key === 'Escape') menu.style.display = 'none'; });
    }
})();
</script>
"""


def inject_head_html() -> None:
    """Add the Thoth head HTML (CSS + JS) to the current page."""
    ui.add_head_html(HEAD_HTML)
