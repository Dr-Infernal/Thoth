"""Thoth UI — knowledge-graph explorer panel.

Self-contained vis-network graph builder.  Can be called from any
NiceGUI parent context.
"""

from __future__ import annotations


def build_graph_panel() -> None:
    """Interactive knowledge graph explorer using vis-network.

    Imports ``knowledge_graph`` lazily — the panel simply shows an empty
    placeholder when no entities exist yet.
    """
    import json as _json

    from nicegui import ui

    import knowledge_graph as kg

    data = kg.graph_to_vis_json()
    stats = data["stats"]

    if stats["total_entities"] == 0:
        with ui.column().classes("w-full h-full items-center justify-center"):
            ui.icon("hub").classes("text-grey-6").style("font-size: 4rem; opacity: 0.4;")
            ui.label(
                "Your memory map will appear here as Thoth learns about you."
            ).classes("text-grey-6 text-center q-mt-md").style("max-width: 360px;")
        return

    nodes_json = _json.dumps(data["nodes"])
    edges_json = _json.dumps(data["edges"])
    center_id = _json.dumps(data["center"])
    type_colors = _json.dumps(kg._VIS_TYPE_COLORS)

    # ── Controls bar ─────────────────────────────────────────────────
    with ui.row().classes("w-full items-center gap-2 q-px-sm q-py-xs shrink-0").style(
        "border-bottom: 1px solid rgba(255,255,255,0.08);"
    ):
        ui.html(
            '<input id="graph-search" type="text" placeholder="Search entities…" '
            'style="background: #1e1e2e; border: 1px solid #444; border-radius: 6px; '
            'padding: 4px 10px; color: #eee; font-size: 0.85rem; width: 200px; '
            'outline: none;" />',
            sanitize=False,
        )
        ui.html(
            '<div id="graph-type-filters" style="display:flex; gap:4px; flex-wrap:wrap;"></div>',
            sanitize=False,
        )
        ui.html('<div style="flex-grow:1;"></div>', sanitize=False)
        ui.html(
            f'<span id="graph-stats-label" style="font-size:0.75rem; color:#9E9E9E;">'
            f'{stats["shown_nodes"]} memories · {stats["shown_edges"]} connections'
            f'</span>',
            sanitize=False,
        )
        ui.html(
            '<button id="graph-fit-btn" title="Fit to view" '
            'style="background:none; border:1px solid #555; border-radius:4px; '
            'color:#ccc; padding:2px 8px; cursor:pointer; font-size:0.8rem;">'
            '⊞ Fit</button>',
            sanitize=False,
        )
        ui.html(
            '<label style="display:flex; align-items:center; gap:4px; font-size:0.8rem; color:#ccc; cursor:pointer;">'
            '<input type="checkbox" id="graph-full-toggle" checked '
            'style="accent-color:#FFD54F;" /> Full map</label>',
            sanitize=False,
        )

    # ── vis-network canvas + overlay detail card ─────────────────────
    ui.html(
        '<div style="position:relative; width:100%; height:100%;">'
        '<div id="graph-container" style="width:100%; height:100%; background:#121212;"></div>'
        '<div id="graph-detail" style="display:none; position:absolute; bottom:8px; right:12px; '
        'padding:8px 12px; background:rgba(26,26,46,0.95); border:1px solid rgba(255,255,255,0.1); '
        'border-radius:8px; font-size:0.85rem; color:#ccc; max-height:140px; max-width:380px; '
        'overflow-y:auto; z-index:10; backdrop-filter:blur(6px); box-sizing:border-box;"></div>'
        '</div>',
        sanitize=False,
    ).style("flex:1; min-height:0; width:100%;")

    # ── vis-network JS logic ─────────────────────────────────────────
    _graph_js = (
        '(function() {'
        '  clearTimeout(window._thothGraphBootTimer || 0);'
        '  if (window._thothGraph) {'
        '    try { window._thothGraph.network && window._thothGraph.network.destroy(); } catch(e) {}'
        '    window._thothGraph = null;'
        '  }'
        '  var G = window._thothGraph = {'
        '    allNodes: ' + nodes_json + ','
        '    allEdges: ' + edges_json + ','
        '    centerId: ' + center_id + ','
        '    typeColors: ' + type_colors + ','
        '    network: null,'
        '    currentNodes: null,'
        '    currentEdges: null,'
        '    activeFilters: new Set(),'
        '    isFullGraph: true,'
        '    searchDebounce: null'
        '  };'
        '  G.currentNodes = G.allNodes;'
        '  G.currentEdges = G.allEdges;'
        '  G.createNetwork = function(nodes, edges, focusId) {'
        '    var container = document.getElementById("graph-container");'
        '    if (!container) return;'
        '    var data = { nodes: new vis.DataSet(nodes), edges: new vis.DataSet(edges) };'
        '    var options = {'
        '      physics: {'
        '        solver: "forceAtlas2Based",'
        '        forceAtlas2Based: { gravitationalConstant: -40, centralGravity: 0.005,'
        '          springLength: 120, springConstant: 0.06, damping: 0.4 },'
        '        stabilization: { iterations: 150, fit: true }'
        '      },'
        '      nodes: { shape: "dot", borderWidth: 1, borderWidthSelected: 3, font: { size: 12 } },'
        '      edges: { smooth: { type: "continuous" }, width: 1, selectionWidth: 2,'
        '        font: { color: "transparent", strokeColor: "transparent", size: 11 } },'
        '      interaction: { hover: true, tooltipDelay: 200, hideEdgesOnDrag: true, multiselect: false }'
        '    };'
        '    if (G.network) { try { G.network.destroy(); } catch(e) {} }'
        '    G.network = new vis.Network(container, data, options);'
        '    G.network.on("hoverEdge", function(p) {'
        '      data.edges.update({ id: p.edge, font: { color: "#ccc", strokeColor: "#222" } });'
        '    });'
        '    G.network.on("blurEdge", function(p) {'
        '      data.edges.update({ id: p.edge, font: { color: "transparent", strokeColor: "transparent" } });'
        '    });'
        '    G.network.once("stabilizationIterationsDone", function() {'
        '      if (focusId) { G.network.focus(focusId, { scale: 1.0, animation: true }); }'
        '      else { G.network.fit({ animation: true }); }'
        '    });'
        '    G.network.on("click", function(params) {'
        '      var detail = document.getElementById("graph-detail");'
        '      if (!detail) return;'
        '      if (params.nodes.length === 0) { detail.style.display = "none"; return; }'
        '      var nid = params.nodes[0];'
        '      var node = nodes.find(function(n) { return n.id === nid; });'
        '      if (!node) { detail.style.display = "none"; return; }'
        '      var rels = edges.filter(function(e) { return e.from === nid || e.to === nid; });'
        '      var relHtml = "";'
        '      if (rels.length > 0) {'
        '        var relItems = rels.slice(0, 10).map(function(e) {'
        '          var other = e.from === nid'
        '            ? nodes.find(function(n) { return n.id === e.to; })'
        '            : nodes.find(function(n) { return n.id === e.from; });'
        '          var dir = e.from === nid ? "\u2192" : "\u2190";'
        '          return "<span style=\\"color:#888;\\">" + dir + "</span> "'
        '            + "<b>" + (e.label || "related") + "</b> "'
        '            + (other ? other.label : "?");'
        '        }).join("<br>");'
        '        relHtml = "<div style=\\"margin-top:4px;\\">" + relItems'
        '          + (rels.length > 10 ? "<br><i>\u2026and " + (rels.length - 10) + " more</i>" : "")'
        '          + "</div>";'
        '      }'
        '      var aliases = node._aliases ? "<div style=\\"color:#999; font-size:0.8rem;\\">Aliases: " + node._aliases + "</div>" : "";'
        '      var tags = node._tags ? "<div style=\\"color:#999; font-size:0.8rem;\\">Tags: " + node._tags + "</div>" : "";'
        '      detail.innerHTML ='
        '        "<div style=\\"display:flex; align-items:center; gap:8px;\\">"'
        '        + "<span style=\\"background:" + node.color + "; width:10px; height:10px;"'
        '        + " border-radius:50%; display:inline-block;\\"></span>"'
        '        + "<b style=\\"color:#eee; font-size:1rem;\\">" + node.label + "</b>"'
        '        + "<span style=\\"color:#888; font-size:0.8rem;\\">(" + (node._type || "?") + ")</span>"'
        '        + "<span style=\\"color:#666; font-size:0.75rem; margin-left:auto;\\">"'
        '        + node._degree + " connections</span>"'
        '        + "</div>"'
        '        + (node._description ? "<div style=\\"margin-top:4px; color:#bbb;\\">" + node._description + "</div>" : "")'
        '        + aliases + tags + relHtml;'
        '      detail.style.display = "block";'
        '    });'
        '    G.network.on("doubleClick", function(params) {'
        '      if (params.nodes.length === 0) return;'
        '      G.refocusOnNode(params.nodes[0]);'
        '    });'
        '    return G.network;'
        '  };'
        '  G.refocusOnNode = function(nodeId) {'
        '    var hops = 2, visited = new Set([nodeId]), frontier = [nodeId];'
        '    for (var h = 0; h < hops; h++) {'
        '      var next = [];'
        '      for (var fi = 0; fi < frontier.length; fi++) {'
        '        var fid = frontier[fi];'
        '        for (var ei = 0; ei < G.allEdges.length; ei++) {'
        '          var e = G.allEdges[ei];'
        '          if (e.from === fid && !visited.has(e.to)) { visited.add(e.to); next.push(e.to); }'
        '          if (e.to === fid && !visited.has(e.from)) { visited.add(e.from); next.push(e.from); }'
        '        }'
        '      }'
        '      frontier = next;'
        '    }'
        '    var subNodes = G.allNodes.filter(function(n) { return visited.has(n.id); });'
        '    var subEdges = G.allEdges.filter(function(e) { return visited.has(e.from) && visited.has(e.to); });'
        '    G.currentNodes = subNodes; G.currentEdges = subEdges; G.isFullGraph = false;'
        '    var toggle = document.getElementById("graph-full-toggle");'
        '    if (toggle) toggle.checked = false;'
        '    G.updateStatsLabel(subNodes.length, subEdges.length);'
        '    G.createNetwork(subNodes, subEdges, nodeId);'
        '  };'
        '  G.buildFilterPills = function() {'
        '    var container = document.getElementById("graph-type-filters");'
        '    if (!container) return;'
        '    var typeSet = new Set(G.allNodes.map(function(n) { return n._type; }));'
        '    var types = Array.from(typeSet).sort();'
        '    container.innerHTML = "";'
        '    for (var i = 0; i < types.length; i++) {'
        '      (function(t) {'
        '        var color = G.typeColors[t] || "#B0BEC5";'
        '        var pill = document.createElement("button");'
        '        pill.textContent = t; pill.dataset.type = t;'
        '        pill.style.cssText = "border:1px solid " + color + "; background:none;"'
        '          + " border-radius:12px; padding:1px 8px; font-size:0.72rem;"'
        '          + " color:" + color + "; cursor:pointer; transition:all 0.2s;";'
        '        pill.onclick = function() {'
        '          if (G.activeFilters.has(t)) {'
        '            G.activeFilters.delete(t); pill.style.background = "none"; pill.style.color = color;'
        '          } else {'
        '            G.activeFilters.add(t); pill.style.background = color; pill.style.color = "#121212";'
        '          }'
        '          G.applyFilters();'
        '        };'
        '        container.appendChild(pill);'
        '      })(types[i]);'
        '    }'
        '  };'
        '  G.applyFilters = function() {'
        '    var searchVal = (document.getElementById("graph-search") || {}).value || "";'
        '    searchVal = searchVal.toLowerCase();'
        '    var filtered = G.allNodes;'
        '    if (G.activeFilters.size > 0) {'
        '      filtered = filtered.filter(function(n) { return G.activeFilters.has(n._type); });'
        '    }'
        '    if (searchVal) {'
        '      filtered = filtered.filter(function(n) {'
        '        return n.label.toLowerCase().indexOf(searchVal) >= 0'
        '          || (n._description || "").toLowerCase().indexOf(searchVal) >= 0'
        '          || (n._aliases || "").toLowerCase().indexOf(searchVal) >= 0'
        '          || (n._tags || "").toLowerCase().indexOf(searchVal) >= 0;'
        '      });'
        '    }'
        '    var nodeIds = new Set(filtered.map(function(n) { return n.id; }));'
        '    var filteredEdges = G.allEdges.filter(function(e) { return nodeIds.has(e.from) && nodeIds.has(e.to); });'
        '    G.currentNodes = filtered; G.currentEdges = filteredEdges;'
        '    G.updateStatsLabel(filtered.length, filteredEdges.length);'
        '    G.createNetwork(filtered, filteredEdges, null);'
        '  };'
        '  G.updateStatsLabel = function(nodeCount, edgeCount) {'
        '    var el = document.getElementById("graph-stats-label");'
        '    if (el) el.textContent = nodeCount + " memories \u00b7 " + edgeCount + " connections";'
        '  };'
        '  G.wireControls = function() {'
        '    G.buildFilterPills();'
        '    var searchInput = document.getElementById("graph-search");'
        '    if (searchInput) {'
        '      searchInput.oninput = function() {'
        '        clearTimeout(G.searchDebounce);'
        '        G.searchDebounce = setTimeout(function() { G.applyFilters(); }, 300);'
        '      };'
        '    }'
        '    var fitBtn = document.getElementById("graph-fit-btn");'
        '    if (fitBtn) {'
        '      fitBtn.onclick = function() { if (G.network) G.network.fit({ animation: true }); };'
        '    }'
        '    var fullToggle = document.getElementById("graph-full-toggle");'
        '    if (fullToggle) {'
        '      fullToggle.onchange = function() {'
        '        if (fullToggle.checked) {'
        '          G.isFullGraph = true; G.currentNodes = G.allNodes; G.currentEdges = G.allEdges;'
        '          G.activeFilters.clear();'
        '          var si = document.getElementById("graph-search"); if (si) si.value = "";'
        '          document.querySelectorAll("#graph-type-filters button").forEach(function(b) {'
        '            var c = G.typeColors[b.dataset.type] || "#B0BEC5";'
        '            b.style.background = "none"; b.style.color = c;'
        '          });'
        '          G.updateStatsLabel(G.allNodes.length, G.allEdges.length);'
        '          G.createNetwork(G.allNodes, G.allEdges, G.centerId);'
        '        }'
        '      };'
        '    }'
        '  };'
        '  function boot() {'
        '    if (typeof vis === "undefined" || !document.getElementById("graph-container")) {'
        '      window._thothGraphBootTimer = setTimeout(boot, 100);'
        '      return;'
        '    }'
        '    G.wireControls();'
        '    G.createNetwork(G.allNodes, G.allEdges, G.centerId);'
        '    window.thothGraphRedraw = function() {'
        '      if (!document.getElementById("graph-container")) return;'
        '      G.wireControls();'
        '      G.createNetwork(G.currentNodes, G.currentEdges, null);'
        '    };'
        '  }'
        '  boot();'
        '})();'
    )
    ui.run_javascript(_graph_js)
