// Dependency-free SVG charts. Colours come from CSS variables so both themes work. Every data element can carry an explanation
// (see info.js): hovering shows a one-line summary, clicking opens the full explanation.
import { attachExplain, esc } from "./info.js";
export { esc };
const NS = "http://www.w3.org/2000/svg";
export const pct = (x, d = 0) => `${(x * 100).toFixed(d)}%`;
export const fmtMs = (ms) => (ms >= 1000 ? `${(ms / 1000).toFixed(ms >= 10000 ? 1 : 2)} s` : ms >= 10 ? `${ms.toFixed(0)} ms` : `${ms.toFixed(2)} ms`);

function el(tag, attrs = {}, kids = []) {
  const n = document.createElementNS(NS, tag);
  for (const [k, v] of Object.entries(attrs)) n.setAttribute(k, v);
  for (const c of [].concat(kids)) n.append(typeof c === "string" ? document.createTextNode(c) : c);
  return n;
}
const root = (w, h, label) => el("svg", { viewBox: `0 0 ${w} ${h}`, class: "chart", role: "img", "aria-label": label });
const wire = (node, explain) => { if (explain) attachExplain(node, explain); return node; };

export function groupedBars({ categories, keys, explain, label = "Grouped bar chart" }) {
  const W = 560, H = 270, L = 40, B = 34, T = 16, R = 8;
  const svg = root(W, H, label);
  for (const g of [0, 0.25, 0.5, 0.75, 1]) {
    const y = T + (H - T - B) * (1 - g);
    svg.append(el("line", { x1: L, x2: W - R, y1: y, y2: y, class: "grid-line" }), el("text", { x: L - 8, y: y + 4, "text-anchor": "end" }, pct(g)));
  }
  const gw = (W - L - R) / categories.length;
  categories.forEach((cat, i) => {
    const bw = Math.min(30, (gw - 20) / keys.length);
    keys.forEach((k, j) => {
      const v = cat.values[k] ?? 0, h = (H - T - B) * v;
      const x = L + gw * i + (gw - bw * keys.length - (keys.length - 1) * 4) / 2 + j * (bw + 4), y = H - B - h;
      svg.append(wire(el("rect", { x, y, width: bw, height: Math.max(h, 1.5), rx: 4, style: `fill:var(--${k})` }), explain?.(cat, k, v)));
      svg.append(el("text", { x: x + bw / 2, y: y - 5, "text-anchor": "middle", class: "strong", style: "font-size:10.5px" }, pct(v)));
    });
    svg.append(el("text", { x: L + gw * i + gw / 2, y: H - 12, "text-anchor": "middle", class: "axis-label" }, cat.label));
  });
  return svg;
}

export function radar({ axes, series, explain }) {
  const W = 340, H = 290, cx = W / 2, cy = H / 2 + 6, R = 98;
  const svg = root(W, H, "Radar chart of first-attempt success by task family");
  const pt = (i, v) => { const a = -Math.PI / 2 + (2 * Math.PI * i) / axes.length; return [cx + Math.cos(a) * R * v, cy + Math.sin(a) * R * v]; };
  for (const ring of [0.25, 0.5, 0.75, 1]) svg.append(el("polygon", { points: axes.map((_, i) => pt(i, ring).join(",")).join(" "), fill: "none", class: "grid-line" }));
  axes.forEach((name, i) => {
    const [x, y] = pt(i, 1), [lx, ly] = pt(i, 1.17);
    svg.append(el("line", { x1: cx, y1: cy, x2: x, y2: y, class: "grid-line" }), el("text", { x: lx, y: ly + 4, "text-anchor": Math.abs(lx - cx) < 10 ? "middle" : lx > cx ? "start" : "end" }, name));
  });
  for (const s of series) {
    svg.append(el("polygon", { points: s.values.map((v, i) => pt(i, v).join(",")).join(" "), style: `fill:var(--${s.key});fill-opacity:.12;stroke:var(--${s.key});stroke-width:2;stroke-linejoin:round` }));
    s.values.forEach((v, i) => { const [x, y] = pt(i, v); svg.append(wire(el("circle", { cx: x, cy: y, r: 4.5, style: `fill:var(--card);stroke:var(--${s.key});stroke-width:2` }), explain?.(axes[i], s.key, v))); });
  }
  return svg;
}

export function donut({ segments, centerTop, centerBottom, explain }) {
  const W = 230, H = 230, cx = 115, cy = 115, r = 82, sw = 26;
  const svg = root(W, H, "Donut chart of task outcomes");
  const total = segments.reduce((a, s) => a + s.value, 0) || 1;
  let a0 = -Math.PI / 2;
  for (const s of segments) {
    if (!s.value) continue;
    const span = (2 * Math.PI * s.value) / total, a1 = a0 + span - (segments.filter((x) => x.value).length > 1 ? 0.025 : 0.0001);
    const p = (a) => [cx + r * Math.cos(a), cy + r * Math.sin(a)], [x0, y0] = p(a0), [x1, y1] = p(a1);
    svg.append(wire(el("path", { d: `M${x0},${y0} A${r},${r} 0 ${a1 - a0 > Math.PI ? 1 : 0} 1 ${x1},${y1}`, fill: "none", "stroke-width": sw, style: `stroke:${s.color}` }), explain?.(s, total)));
    a0 += span;
  }
  svg.append(el("text", { x: cx, y: cy + 4, "text-anchor": "middle", class: "strong", style: "font-size:30px" }, centerTop), el("text", { x: cx, y: cy + 24, "text-anchor": "middle" }, centerBottom));
  return svg;
}

export function lines({ series, yMax = 1, xLabel, explain }) {
  const W = 560, H = 260, L = 40, B = 38, T = 14, R = 12;
  const svg = root(W, H, "Line chart of running first-attempt success");
  const xs = series.flatMap((s) => s.points.map((p) => p.x)), xMin = Math.min(...xs, 1), xMax = Math.max(...xs, 2);
  const X = (x) => L + ((W - L - R) * (x - xMin)) / (xMax - xMin || 1), Y = (y) => T + (H - T - B) * (1 - y / yMax);
  for (const g of [0, 0.25, 0.5, 0.75, 1]) svg.append(el("line", { x1: L, x2: W - R, y1: Y(g * yMax), y2: Y(g * yMax), class: "grid-line" }), el("text", { x: L - 8, y: Y(g * yMax) + 4, "text-anchor": "end" }, pct(g * yMax)));
  for (let x = xMin; x <= xMax; x++) svg.append(el("text", { x: X(x), y: H - 20, "text-anchor": "middle" }, String(x)));
  svg.append(el("text", { x: (L + W - R) / 2, y: H - 4, "text-anchor": "middle", class: "axis-label" }, xLabel));
  for (const s of series) {
    if (!s.points.length) continue;
    const d = s.points.map((p, i) => `${i ? "L" : "M"}${X(p.x)},${Y(p.y)}`).join(" ");
    svg.append(el("path", { d: `${d} L${X(s.points.at(-1).x)},${Y(0)} L${X(s.points[0].x)},${Y(0)} Z`, style: `fill:var(--${s.key});fill-opacity:.07` }), el("path", { d, fill: "none", "stroke-width": 2.5, "stroke-linejoin": "round", style: `stroke:var(--${s.key})` }));
    for (const p of s.points) svg.append(wire(el("circle", { cx: X(p.x), cy: Y(p.y), r: 4, style: `fill:var(--card);stroke:var(--${s.key});stroke-width:2` }), explain?.(s.key, p)));
  }
  return svg;
}

export function stackedH({ rows, parts, colors, format, explain }) {
  const rowH = 42, W = 540, L = 84, H = rows.length * rowH + 12;
  const svg = root(W, H, "Stacked bars of average time per processing step");
  const max = Math.max(...rows.map((r) => parts.reduce((a, p) => a + (r.values[p] || 0), 0)), 1);
  rows.forEach((r, i) => {
    const y = 8 + i * rowH, total = parts.reduce((a, p) => a + (r.values[p] || 0), 0);
    svg.append(el("text", { x: L - 10, y: y + 17, "text-anchor": "end", class: "strong" }, r.label));
    let x = L;
    for (const p of parts) {
      const w = ((W - L - 78) * (r.values[p] || 0)) / max;
      if (w <= 0) continue;
      svg.append(wire(el("rect", { x, y, width: Math.max(w, 2), height: 26, rx: 3, style: `fill:${colors[p]}` }), explain?.(r, p, r.values[p], total)));
      x += w;
    }
    svg.append(el("text", { x: x + 8, y: y + 18, class: "strong" }, format(total)));
  });
  return svg;
}

export function whisker({ items, domain }) {
  const rowH = 50, W = 380, L = 10, R = 10, H = items.length * rowH + 28;
  const svg = root(W, H, "Intervals of the difference between conditions");
  const [lo, hi] = domain, X = (v) => L + ((W - L - R) * (v - lo)) / (hi - lo);
  svg.append(el("line", { x1: X(0), x2: X(0), y1: 4, y2: H - 24, style: "stroke:var(--muted);stroke-dasharray:3 3" }));
  for (const t of [lo, 0, hi]) svg.append(el("text", { x: X(t), y: H - 8, "text-anchor": "middle" }, (t > 0 ? "+" : "") + (t * 100).toFixed(0) + " pts"));
  items.forEach((it, i) => {
    const y = 14 + i * rowH, good = it.lo > 0, bad = it.hi < 0, color = good ? "var(--ok)" : bad ? "var(--bad)" : "var(--muted)";
    svg.append(el("text", { x: L, y, class: "strong" }, it.label));
    const g = el("g", {}, [el("line", { x1: X(Math.max(lo, it.lo)), x2: X(Math.min(hi, it.hi)), y1: y + 18, y2: y + 18, "stroke-width": 5, "stroke-linecap": "round", style: `stroke:${color};opacity:.85` }), el("circle", { cx: X(it.mean), cy: y + 18, r: 6, style: `fill:${color}` })]);
    svg.append(wire(g, it.explain));
  });
  return svg;
}
