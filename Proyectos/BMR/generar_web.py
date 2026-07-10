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
  padding: 1.5rem 2rem;
  text-align: center;
  box-shadow: 0 2px 12px rgba(0,0,0,0.3);
}
header h1 {
  font-size: 1.8rem;
  font-weight: 300;
  letter-spacing: 2px;
}
header p {
  font-size: 0.9rem;
  opacity: 0.7;
  margin-top: 0.3rem;
}
#tree-container {
  width: 100%;
  min-height: calc(100vh - 100px);
  overflow: auto;
  cursor: grab;
}
#tree-container:active { cursor: grabbing; }
svg { display: block; margin: 0 auto; }
.node circle {
  fill: #8b5e3c;
  stroke: #5a3a1a;
  stroke-width: 2px;
  cursor: pointer;
  transition: r 0.2s ease, fill 0.2s ease;
}
.node circle:hover {
  fill: #c49a6c;
}
.node circle.has-children {
  fill: #6b8e23;
  stroke: #4a6e12;
}
.node circle.has-children:hover {
  fill: #8db600;
}
.node text {
  font-size: 13px;
  fill: #2d1b0e;
  font-weight: 500;
  pointer-events: none;
  text-shadow: 0 1px 2px rgba(255,255,255,0.8);
}
.node text.highlight {
  font-weight: 700;
  fill: #6b8e23;
}
.link {
  fill: none;
  stroke: #8b7355;
  stroke-width: 2px;
  opacity: 0.6;
}
.link.active {
  stroke: #6b8e23;
  stroke-width: 2.5px;
  opacity: 0.9;
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
}
.controls {
  position: fixed;
  bottom: 1.5rem;
  right: 1.5rem;
  display: flex;
  gap: 0.5rem;
}
.controls button {
  background: rgba(45,27,14,0.85);
  color: #f5e6d0;
  border: none;
  padding: 0.6rem 1rem;
  border-radius: 8px;
  cursor: pointer;
  font-size: 0.8rem;
  transition: background 0.2s;
}
.controls button:hover {
  background: rgba(90,58,26,0.95);
}
</style>
</head>
<body>

<header>
  <h1>🌳 Árbol Genealógico — Familia Marín Rojas</h1>
  <p>Haz clic en un nodo con hijos para expandir/colapsar · Arrastra el fondo para navegar</p>
</header>

<div id="tree-container"></div>
<div class="tooltip" id="tooltip"></div>

<div class="controls">
  <button onclick="expandAll()">Expandir todo</button>
  <button onclick="resetView()">Restablecer vista</button>
</div>

<script>
const treeData = TREE_DATA_PLACEHOLDER;

const container = document.getElementById('tree-container');
const tooltip = document.getElementById('tooltip');

const width = container.clientWidth || 1200;
const height = container.clientHeight || 1600;

const svg = d3.select('#tree-container')
  .append('svg')
  .attr('width', width)
  .attr('height', height)
  .call(d3.zoom().on('zoom', (event) => {
    g.attr('transform', event.transform);
  }));

const g = svg.append('g').attr('transform', 'translate(80,60)');

const treeLayout = d3.tree().nodeSize([140, 220]);
const root = d3.hierarchy(treeData);

// Count total descendants for initial sizing
root.count();

let currentRoot = root;
let maxDepth = 0;

// Collapse all children of the root (show only root initially)
function collapseAllChildren(node) {
  if (node.children) {
    node.children.forEach(c => {
      c._children = c.children;
      c.children = null;
    });
  }
}

function collapse(node) {
  if (node._children) {
    node.children = node._children;
    node._children = null;
  }
}

function expand(node) {
  if (node._children) {
    node.children = node._children;
    node._children = null;
    node.children.forEach(expand);
  }
}

function expandAll() {
  currentRoot.each(n => {
    if (n._children) { n.children = n._children; n._children = null; }
  });
  update(currentRoot);
}

function resetView() {
  svg.transition().duration(500).call(
    d3.zoom().transform,
    d3.zoomIdentity.translate(80, 60).scale(1)
  );
}

function update(source) {
  const treeData = treeLayout(currentRoot);
  const nodes = treeData.descendants();
  const links = treeData.links();

  // Calculate depth for coloring
  maxDepth = d3.max(nodes, n => n.depth);

  // Update tree height based on content
  const treeHeight = (maxDepth + 1) * 220 + 120;
  const treeWidth = (nodes.length > 10 ? nodes.length : 10) * 70 + 160;
  svg.attr('height', Math.max(treeHeight, 800));
  svg.attr('width', Math.max(treeWidth, 1200));

  // ---- LINKS ----
  const link = g.selectAll('path.link')
    .data(links, d => d.target.data.name);

  link.exit().remove();

  const linkEnter = link.enter().append('path')
    .attr('class', 'link')
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
      if (d._children || d.children) {
        toggleChildren(d);
        update(source);
      }
    })
    .on('mouseover', (event, d) => {
      tooltip.style.opacity = 1;
      tooltip.style.left = (event.pageX + 12) + 'px';
      tooltip.style.top = (event.pageY - 10) + 'px';
      const hasKids = d.children?.length > 0 || d._children?.length > 0;
      tooltip.textContent = d.data.name + (hasKids ? ` (${d.children?.length || d._children?.length} hijos)` : '');
    })
    .on('mousemove', (event) => {
      tooltip.style.left = (event.pageX + 12) + 'px';
      tooltip.style.top = (event.pageY - 10) + 'px';
    })
    .on('mouseout', () => {
      tooltip.style.opacity = 0;
    });

  nodeEnter.append('circle')
    .attr('r', 0)
    .attr('class', d => d.children || d._children ? 'has-children' : '');

  nodeEnter.append('text')
    .attr('dy', d => d.children || d._children ? -18 : 4)
    .attr('x', 0)
    .attr('text-anchor', 'middle')
    .attr('class', d => d.depth === 0 ? 'highlight' : '');

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
    .attr('class', d => d.children || d._children ? 'has-children' : '');

  nodeMerge.select('text')
    .text(d => d.data.name);

  // Store old positions
  nodes.forEach(d => {
    d.x0 = d.x;
    d.y0 = d.y;
  });
}

function toggleChildren(d) {
  if (d.children) {
    d._children = d.children;
    d.children = null;
  } else if (d._children) {
    d.children = d._children;
    d._children = null;
  }
}

// Initialize positions
currentRoot.x0 = 0;
currentRoot.y0 = 0;
currentRoot.descendants().forEach((d, i) => {
  d.x0 = d.x || 0;
  d.y0 = d.y || 0;
});

collapseAllChildren(currentRoot);
update(currentRoot);

// Resize handler
window.addEventListener('resize', () => {
  const w = container.clientWidth || 1200;
  svg.attr('width', Math.max(w, 800));
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
