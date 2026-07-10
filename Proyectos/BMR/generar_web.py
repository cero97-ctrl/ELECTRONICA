#!/usr/bin/env python3
"""Genera una página web interactiva del árbol genealógico familiar."""

import json
import os
from pathlib import Path

BASE_DIR = Path(__file__).parent
JSON_PATH = BASE_DIR / "arbol_familia.json"
OUT_DIR = BASE_DIR / "web"

HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Árbol Genealógico — Familia Marín Rojas</title>
<script src="https://d3js.org/d3.v7.min.js"></script>
<style>
* { margin: 0; padding: 0; box-sizing: border-box; }
body {
  font-family: 'Segoe UI', system-ui, sans-serif;
  background: linear-gradient(135deg, #f5f0e8 0%, #e8dcc8 100%);
  min-height: 100vh;
  overflow-x: hidden;
}
header {
  background: linear-gradient(135deg, #2d1b0e 0%, #5a3a1a 100%);
  color: #f5e6d0;
  padding: 1rem 2rem;
  text-align: center;
  box-shadow: 0 2px 12px rgba(0,0,0,0.3);
  position: relative;
  z-index: 10;
}
header h1 {
  font-size: 1.6rem;
  font-weight: 300;
  letter-spacing: 2px;
}
.header-row {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 1rem;
  margin-top: 0.5rem;
  flex-wrap: wrap;
}
#search-input {
  padding: 0.4rem 0.8rem;
  border: 1px solid #8b7355;
  border-radius: 6px;
  font-size: 0.85rem;
  background: rgba(255,255,255,0.15);
  color: #f5e6d0;
  outline: none;
  width: 220px;
  transition: background 0.2s;
}
#search-input::placeholder { color: #c4a882; }
#search-input:focus { background: rgba(255,255,255,0.25); }
#search-count {
  font-size: 0.8rem;
  opacity: 0.7;
  min-width: 60px;
  text-align: left;
}
#tree-container {
  width: 100%;
  min-height: calc(100vh - 100px);
  cursor: grab;
}
#tree-container:active { cursor: grabbing; }
svg {
  display: block;
  width: 100%;
  overflow: visible;
}

.node circle, .node polygon {
  stroke-width: 2px;
  cursor: pointer;
  transition: all 0.2s ease;
}
.node circle:hover, .node polygon:hover { filter: brightness(1.2); }
.node circle.selected, .node polygon.selected {
  stroke: #000 !important;
  stroke-width: 3px !important;
}
.node circle.matched, .node polygon.matched {
  stroke: #ffd700 !important;
  stroke-width: 3px !important;
  animation: pulse 1s ease-in-out infinite;
}
@keyframes pulse {
  0%, 100% { r: var(--r); }
  50% { r: calc(var(--r) + 3); }
}
.node circle.faded, .node polygon.faded {
  opacity: 0.15;
}
.node text {
  font-size: 13px;
  fill: #2d1b0e;
  font-weight: 500;
  pointer-events: none;
  text-shadow: 0 1px 2px rgba(255,255,255,0.8);
  transition: opacity 0.3s;
}
.node text.faded { opacity: 0.15; }
.node text.highlight { font-weight: 700; }
.node text.union-label {
  font-size: 11px;
  font-style: italic;
  fill: #8B5E3C;
}

.link {
  fill: none;
  stroke: #8b7355;
  stroke-width: 2px;
  opacity: 0.5;
  transition: opacity 0.3s;
}
.link.faded { opacity: 0.08; }
.link.active { opacity: 0.9; }
.link.dashed {
  stroke-dasharray: 6,4;
  stroke: #b8860b;
  opacity: 0.7;
}

.tooltip {
  position: absolute;
  background: rgba(45,27,14,0.9);
  color: #f5e6d0;
  padding: 0.5rem 1rem;
  border-radius: 6px;
  font-size: 0.85rem;
  pointer-events: none;
  opacity: 0;
  transition: opacity 0.2s ease;
  white-space: nowrap;
  z-index: 100;
}

/* Detail Panel */
#detail-panel {
  position: fixed;
  top: 0;
  right: -380px;
  width: 360px;
  height: 100vh;
  background: rgba(45,27,14,0.95);
  color: #f5e6d0;
  padding: 2rem 1.5rem;
  box-shadow: -4px 0 20px rgba(0,0,0,0.5);
  transition: right 0.35s ease;
  z-index: 50;
  overflow-y: auto;
}
#detail-panel.open { right: 0; }
#detail-panel .close-btn {
  position: absolute;
  top: 1rem;
  right: 1rem;
  background: none;
  border: none;
  color: #c4a882;
  font-size: 1.5rem;
  cursor: pointer;
  transition: color 0.2s;
}
#detail-panel .close-btn:hover { color: #f5e6d0; }
#detail-panel h2 {
  font-size: 1.3rem;
  font-weight: 400;
  margin-bottom: 1.5rem;
  padding-bottom: 0.5rem;
  border-bottom: 1px solid rgba(245,230,208,0.2);
}
#detail-panel .detail-section {
  margin-bottom: 1.2rem;
}
#detail-panel .detail-section h3 {
  font-size: 0.8rem;
  text-transform: uppercase;
  letter-spacing: 1px;
  opacity: 0.6;
  margin-bottom: 0.4rem;
}
#detail-panel .detail-section ul {
  list-style: none;
  padding: 0;
}
#detail-panel .detail-section li {
  padding: 0.25rem 0;
  font-size: 0.95rem;
}
#detail-panel .detail-section li::before {
  content: '\2022';
  color: #8db600;
  margin-right: 0.5rem;
}
#detail-panel .no-children {
  font-size: 0.9rem;
  opacity: 0.5;
  font-style: italic;
}

.controls {
  position: fixed;
  bottom: 1.5rem;
  right: 1.5rem;
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
  z-index: 40;
}
.controls .row {
  display: flex;
  gap: 0.4rem;
}
.controls button {
  background: rgba(45,27,14,0.85);
  color: #f5e6d0;
  border: none;
  padding: 0.5rem 0.8rem;
  border-radius: 6px;
  cursor: pointer;
  font-size: 0.8rem;
  transition: background 0.2s;
  white-space: nowrap;
}
.controls button:hover { background: rgba(90,58,26,0.95); }
.controls button.icon-btn {
  width: 36px;
  padding: 0.5rem 0;
  font-size: 1.1rem;
  text-align: center;
}
#zoom-level {
  font-size: 0.75rem;
  opacity: 0.7;
  text-align: center;
  padding: 0.3rem 0;
}

/* Legend */
.legend {
  position: fixed;
  bottom: 1.5rem;
  left: 1.5rem;
  background: rgba(45,27,14,0.85);
  color: #f5e6d0;
  padding: 0.6rem 1rem;
  border-radius: 8px;
  font-size: 0.75rem;
  z-index: 40;
}
.legend-item {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  margin: 0.2rem 0;
}
.legend-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  border: 1px solid rgba(255,255,255,0.3);
  flex-shrink: 0;
}
.legend-diamond {
  width: 10px;
  height: 10px;
  transform: rotate(45deg);
  border: 1px solid rgba(255,255,255,0.3);
  flex-shrink: 0;
}

/* Responsive */
@media (max-width: 640px) {
  header h1 { font-size: 1.2rem; }
  #search-input { width: 160px; }
  #detail-panel { width: 300px; right: -320px; }
  .controls { bottom: 0.8rem; right: 0.8rem; }
  .controls button { font-size: 0.7rem; padding: 0.4rem 0.6rem; }
  .legend { display: none; }
}
</style>
</head>
<body>

<header>
  <h1>Árbol Genealógico — Familia Marín Rojas</h1>
  <div class="header-row">
    <input type="text" id="search-input" placeholder="Buscar persona..." autocomplete="off">
    <span id="search-count"></span>
  </div>
</header>

<div id="tree-container"></div>
<div class="tooltip" id="tooltip"></div>

<div id="detail-panel">
  <button class="close-btn" onclick="closeDetail()">&times;</button>
  <h2 id="detail-name"></h2>
  <div class="detail-section">
    <h3>Generación</h3>
    <p id="detail-generation"></p>
  </div>
  <div class="detail-section">
    <h3>Padre / Madre</h3>
    <p id="detail-parent"></p>
  </div>
  <div class="detail-section">
    <h3>Hermanos</h3>
    <ul id="detail-siblings"></ul>
  </div>
  <div class="detail-section">
    <h3>Nota</h3>
    <p id="detail-nota" style="font-style:italic;opacity:0.8"></p>
  </div>
  <div class="detail-section">
    <h3>Hijos</h3>
    <ul id="detail-children"></ul>
  </div>
</div>

<div class="controls">
  <div class="row">
    <button class="icon-btn" onclick="zoomIn()" title="Acercar">+</button>
    <button class="icon-btn" onclick="zoomOut()" title="Alejar">&minus;</button>
    <button onclick="expandAll()">Expandir todo</button>
    <button onclick="collapseAll()">Colapsar todo</button>
    <button onclick="resetView()" title="Restablecer vista">Reset</button>
  </div>
  <div id="zoom-level">100%</div>
</div>

<div class="legend" id="legend"></div>

<script>
const treeData = TREE_DATA_PLACEHOLDER;

const container = document.getElementById('tree-container');
const tooltip = document.getElementById('tooltip');
const detailPanel = document.getElementById('detail-panel');
const searchInput = document.getElementById('search-input');
const searchCount = document.getElementById('search-count');
const legendEl = document.getElementById('legend');

const zoomBehavior = d3.zoom()
  .scaleExtent([0.3, 4])
  .on('zoom', (event) => {
    g.attr('transform', event.transform);
    document.getElementById('zoom-level').textContent = Math.round(event.transform.k * 100) + '%';
  });

const svg = d3.select('#tree-container')
  .append('svg')
  .attr('width', container.clientWidth || 1200)
  .attr('height', container.clientHeight || 1600)
  .call(zoomBehavior);

const g = svg.append('g').attr('transform', 'translate(80,60)');

const treeLayout = d3.tree().nodeSize([140, 220]);
const root = d3.hierarchy(treeData);

root.count();

let currentRoot = root;
let maxDepth = 0;
let selectedNode = null;
let allNodeData = [];

const GEN_COLORS = [
  '#8B4513', '#B85C2E', '#C97D4A', '#D49A6A',
  '#DDB58A', '#E8CCA8', '#d9d0c0'
];

function getColor(depth) {
  return GEN_COLORS[depth % GEN_COLORS.length];
}

function collapseDeep(node) {
  if (node.children) {
    node.children.forEach(c => collapseDeep(c));
    node._children = node.children;
    node.children = null;
  } else if (node._children) {
    node._children.forEach(c => collapseDeep(c));
  }
}

function collapseAll() {
  collapseDeep(currentRoot);
  update(currentRoot);
  closeDetail();
}

function expandAll() {
  currentRoot.each(n => {
    if (n._children) { n.children = n._children; n._children = null; }
  });
  update(currentRoot);
}

function resetView() {
  svg.transition().duration(500).call(
    zoomBehavior.transform,
    d3.zoomIdentity.translate(80, 60).scale(1)
  );
}

function zoomIn() {
  svg.transition().duration(300).call(zoomBehavior.scaleBy, 1.4);
}

function zoomOut() {
  svg.transition().duration(300).call(zoomBehavior.scaleBy, 0.7);
}

function closeDetail() {
  detailPanel.classList.remove('open');
  selectedNode = null;
  g.selectAll('circle.selected, polygon.selected').classed('selected', false);
}

function isUnion(d) { return d.data._tipo === 'union'; }

function showDetail(d) {
  selectedNode = d;
  document.getElementById('detail-name').textContent = d.data.name;
  document.getElementById('detail-generation').textContent = isUnion(d) ? 'Uni\u00f3n conyugal' : 'Generaci\u00f3n ' + d.depth;

  const parent = d.parent;
  document.getElementById('detail-parent').textContent = parent ? parent.data.name : '(Ra\u00edz)';

  const notaEl = document.getElementById('detail-nota');
  if (d.data._nota) {
    notaEl.textContent = d.data._nota;
    notaEl.style.display = 'block';
  } else {
    notaEl.style.display = 'none';
  }

  const siblings = parent ? parent.children.filter(c => c.data.name !== d.data.name) : [];
  const siblingsList = document.getElementById('detail-siblings');
  siblingsList.innerHTML = '';
  if (siblings.length === 0) {
    siblingsList.innerHTML = '<li class="no-children">(Ninguno)</li>';
  } else {
    siblings.forEach(s => {
      const li = document.createElement('li');
      li.textContent = s.data.name;
      siblingsList.appendChild(li);
    });
  }

  const kids = d.children || d._children || [];
  const childrenList = document.getElementById('detail-children');
  childrenList.innerHTML = '';
  if (kids.length === 0) {
    childrenList.innerHTML = '<li class="no-children">(Sin hijos registrados)</li>';
  } else {
    kids.forEach(k => {
      const li = document.createElement('li');
      li.textContent = k.data.name;
      childrenList.appendChild(li);
    });
  }

  detailPanel.classList.add('open');
}

function update(source) {
  const treeData = treeLayout(currentRoot);
  const nodes = treeData.descendants();
  const links = treeData.links();
  allNodeData = nodes;

  maxDepth = d3.max(nodes, n => n.depth);

  const treeHeight = (maxDepth + 1) * 220 + 120;
  svg.attr('height', Math.max(treeHeight, 800));

  // Update legend
  legendEl.innerHTML = '<div class="legend-item"><span class="legend-diamond" style="background:#c49a6c"></span> Uni\u00f3n</div>';
  legendEl.innerHTML += '<div class="legend-item"><span class="legend-dot" style="background:#ffd700;border-color:#ffd700"></span> Buscado</div>';
  for (let d = 0; d <= maxDepth; d++) {
    const label = d === 0 ? 'Ra\u00edz' : 'Gen ' + d;
    legendEl.innerHTML += '<div class="legend-item"><span class="legend-dot" style="background:' + getColor(d) + '"></span> ' + label + '</div>';
  }

  // ---- LINKS ----
  const link = g.selectAll('path.link')
    .data(links, d => d.target.data.name);

  link.exit().remove();

  const linkEnter = link.enter().append('path')
    .attr('class', d => 'link' + (d.target.data._tipo === 'union' ? ' dashed' : ''))
    .attr('d', d => {
      const o = { x: source.x0 || source.x, y: source.y0 || source.y };
      return `M${o.y},${o.x}C${o.y},${(o.x + d.target.x)/2} ${d.target.y},${(o.x + d.target.x)/2} ${d.target.y},${d.target.x}`;
    });

  link.merge(linkEnter)
    .transition().duration(400)
    .attr('d', d => {
      return `M${d.source.y},${d.source.x}C${d.source.y},${(d.source.x + d.target.x)/2} ${d.target.y},${(d.source.x + d.target.x)/2} ${d.target.y},${d.target.x}`;
    });

  // ---- NODES ----
  const node = g.selectAll('g.node')
    .data(nodes, d => d.data.name);

  node.exit().remove();

  const nodeEnter = node.enter().append('g')
    .attr('class', 'node')
    .attr('transform', d => `translate(${source.y0 || source.y},${source.x0 || source.x})`)
    .on('click', (event, d) => {
      event.stopPropagation();
      if (isUnion(d)) {
        toggleChildren(d);
        update(source);
        showDetail(d);
        g.selectAll('circle.selected, polygon.selected').classed('selected', false);
        d3.select(this).select('polygon').classed('selected', true);
        return;
      }
      if (d._children || d.children) {
        toggleChildren(d);
        update(source);
      }
      showDetail(d);
      g.selectAll('circle.selected, polygon.selected').classed('selected', false);
      d3.select(this).select('circle').classed('selected', true);
    })
    .on('mouseover', (event, d) => {
      tooltip.style.opacity = 1;
      tooltip.style.left = (event.pageX + 12) + 'px';
      tooltip.style.top = (event.pageY - 10) + 'px';
      let tip = d.data.name;
      if (d.data._nota) tip += ' \u2014 ' + d.data._nota;
      const hasKids = d.children?.length > 0 || d._children?.length > 0;
      if (hasKids) tip += ' (' + (d.children?.length || d._children?.length) + ' hijos)';
      tooltip.textContent = tip;
    })
    .on('mousemove', (event) => {
      tooltip.style.left = (event.pageX + 12) + 'px';
      tooltip.style.top = (event.pageY - 10) + 'px';
    })
    .on('mouseout', () => {
      tooltip.style.opacity = 0;
    });

  nodeEnter.each(function(d) {
    const el = d3.select(this);
    if (isUnion(d)) {
      const size = 8;
      el.append('polygon')
        .attr('points', `0,${-size} ${size},0 0,${size} ${-size},0`)
        .style('fill', '#c49a6c')
        .style('stroke', '#8B5E3C');
    } else {
      el.append('circle')
        .attr('r', 0)
        .style('fill', d => getColor(d.depth))
        .style('stroke', d => d3.color(getColor(d.depth)).darker(0.5));
    }
  });

  nodeEnter.append('text')
    .attr('dy', d => {
      if (isUnion(d)) return -16;
      return d.children || d._children ? -18 : 4;
    })
    .attr('x', 0)
    .attr('text-anchor', 'middle')
    .attr('class', d => d.depth === 0 ? 'highlight' : (isUnion(d) ? 'union-label' : ''));

  const nodeMerge = nodeEnter.merge(node);

  nodeMerge.transition().duration(400)
    .attr('transform', d => `translate(${d.y},${d.x})`);

  nodeMerge.select('circle')
    .transition().duration(400)
    .attr('r', d => {
      if (d.depth === 0) return 10;
      if (d.children || d._children) return 7;
      return 5;
    })
    .style('fill', d => getColor(d.depth))
    .style('stroke', d => d3.color(getColor(d.depth)).darker(0.5))
    .attr('class', '');

  nodeMerge.select('polygon')
    .transition().duration(400)
    .attr('points', '0,-9 9,0 0,9 -9,0');

  nodeMerge.select('text')
    .text(d => d.data.name);

  // Re-apply search filter if active
  const query = searchInput.value.trim().toLowerCase();
  if (query) applySearch(query);

  nodes.forEach(d => {
    d.x0 = d.x;
    d.y0 = d.y;
  });
}

function toggleChildren(d) {
  if (d.children) {
    collapseDeep(d);
  } else if (d._children) {
    d.children = d._children;
    d._children = null;
  }
}

// Search
function applySearch(query) {
  const hasQuery = query.length > 0;
  const matches = [];
  g.selectAll('g.node').each(function(d) {
    const shape = d3.select(this).select('circle, polygon');
    const text = d3.select(this).select('text');
    const matched = d.data.name.toLowerCase().includes(query) || (isUnion(d) && d.data.name.replace('Con ', '').toLowerCase().includes(query));
    shape.classed('matched', matched && hasQuery);
    shape.classed('faded', hasQuery && !matched);
    const r = shape.attr('r');
    if (r) shape.style('--r', r);
    text.classed('faded', hasQuery && !matched);
    if (matched && hasQuery) matches.push(d.data.name);
  });
  g.selectAll('path.link').classed('faded', hasQuery);
  searchCount.textContent = hasQuery ? matches.length + ' resultado(s)' : '';
}

searchInput.addEventListener('input', () => {
  const query = searchInput.value.trim().toLowerCase();
  applySearch(query);
});

searchInput.addEventListener('keydown', (e) => {
  if (e.key === 'Escape') {
    searchInput.value = '';
    applySearch('');
    searchInput.blur();
  }
});

// Click on background to deselect
svg.on('click', () => {
  closeDetail();
});

// Initialize positions
currentRoot.x0 = 0;
currentRoot.y0 = 0;
currentRoot.descendants().forEach((d, i) => {
  d.x0 = d.x || 0;
  d.y0 = d.y || 0;
});

// Start collapsed: only root visible, progressive expansion
collapseDeep(currentRoot);
update(currentRoot);

// Center root in viewport
const cx = container.clientWidth / 2;
const cy = container.clientHeight / 2;
svg.call(zoomBehavior.transform, d3.zoomIdentity.translate(cx - currentRoot.y, cy - currentRoot.x));

// Resize handler
window.addEventListener('resize', () => {
  svg.attr('width', container.clientWidth || 1200);
});
</script>
</body>
</html>"""

def main():
    if not JSON_PATH.exists():
        print(f"[ERROR] No se encuentra {JSON_PATH}")
        return 1

    with open(JSON_PATH, 'r', encoding='utf-8') as f:
        data = json.load(f)

    os.makedirs(OUT_DIR, exist_ok=True)

    tree_json = json.dumps(data, ensure_ascii=False)
    html = HTML_TEMPLATE.replace('TREE_DATA_PLACEHOLDER', tree_json)

    out_path = OUT_DIR / "index.html"
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write(html)

    print(f"[OK] Página generada: {out_path} ({os.path.getsize(out_path):,} bytes)")
    return 0

if __name__ == "__main__":
    exit(main())
