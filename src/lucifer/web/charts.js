// Tiny dependency-free SVG charts. Colours come from CSS variables so light and dark themes both work.
const NS = "http://www.w3.org/2000/svg";
export const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
export const pct = (x, d = 0) => `${(x * 100).toFixed(d)}%`;
export const fmtMs = (ms) => (ms >= 1000 ? `${(ms / 1000).toFixed(ms >= 10000 ? 1 : 2)} s` : ms >= 10 ? `${ms.toFixed(0)} ms` : `${ms.toFixed(2)} ms`);

function el(tag, attrs = {}, kids = []) {
  const n = document.createElementNS(NS, tag);
  for (const [k, v] of Object.entries(attrs)) n.setAttribute(k, v);
  for (const c of [].concat(kids)) n.append(typeof c === "string" ? document.createTextNode(c) : c);
  return n;
}
const root = (w, h, label) => el("svg", { viewBox: `0 0 ${w} ${h}`, class: "chart", role: "img", "aria-label": label });

const tip = () => document.getElementById("tip");
export function bindTip(node, html) {
  node.addEventListener("mousemove", (e) => {
    const t = tip();
    t.innerHTML = html;
    t.hidden = false;
    t.style.left = Math.min(window.innerWidth - 340, e.clientX + 14) + "px";
    t.style.top = e.clientY + 14 + "px";
  });
  node.addEventListener("mouseleave", () => (tip().hidden = true));
}

export function groupedBars({ categories, keys, colors, names }) {
  const W = 540, H = 250, L = 36, B = 30, T = 14, R = 8;
  const svg = root(W, H, "Grouped bar chart of first-try success by phase");
  for (const g of [0, 0.25, 0.5, 0.75, 1]) {
    const y = T + (H - T - B) * (1 - g);
    svg.append(el("line", { x1: L, x2: W - R, y1: y, y2: y, class: "grid-line" }), el("text", { x: L - 6, y: y + 4, "text-anchor": "end" }, pct(g)));
  }
  const gw = (W - L - R) / categories.length;
  categories.forEach((cat, i) => {
    const bw = Math.min(26, (gw - 18) / keys.length);
    keys.forEach((k, j) => {
      const v = cat.values[k] ?? 0;
      const h = (H - T - B) * v;
      const x = L + gw * i + (gw - bw * keys.length - (keys.length - 1) * 4) / 2 + j * (bw + 4);
      const y = H - B - h;
      const bar = el("rect", { x, y, width: bw, height: Math.max(h, 1), rx: 4, style: `fill:var(--${k})` });
      bindTip(bar, `<b>${esc(cat.label)}</b><br>${esc(names[k])}: ${pct(v, 1)}`);
      svg.append(bar, el("text", { x: x + bw / 2, y: y - 4, "text-anchor": "middle", class: "strong", style: "font-size:10px" }, pct(v)));
    });
    svg.append(el("text", { x: L + gw * i + gw / 2, y: H - 9, "text-anchor": "middle" }, cat.label));
  });
  return svg;
}

export function radar({ axes, series, names }) {
  const W = 320, H = 270, cx = W / 2, cy = H / 2 + 4, R = 92;
  const svg = root(W, H, "Radar chart of success by task family");
  const pt = (i, v) => { const a = -Math.PI / 2 + (2 * Math.PI * i) / axes.length; return [cx + Math.cos(a) * R * v, cy + Math.sin(a) * R * v]; };
  for (const ring of [0.25, 0.5, 0.75, 1]) svg.append(el("polygon", { points: axes.map((_, i) => pt(i, ring).join(",")).join(" "), fill: "none", class: "grid-line" }));
  axes.forEach((name, i) => {
    const [x, y] = pt(i, 1), [lx, ly] = pt(i, 1.2);
    svg.append(el("line", { x1: cx, y1: cy, x2: x, y2: y, class: "grid-line" }), el("text", { x: lx, y: ly + 4, "text-anchor": Math.abs(lx - cx) < 8 ? "middle" : lx > cx ? "start" : "end" }, name));
  });
  for (const s of series) {
    const poly = el("polygon", { points: s.values.map((v, i) => pt(i, v).join(",")).join(" "), style: `fill:var(--${s.key});fill-opacity:.14;stroke:var(--${s.key});stroke-width:2` });
    svg.append(poly);
    s.values.forEach((v, i) => {
      const [x, y] = pt(i, v);
      const dot = el("circle", { cx: x, cy: y, r: 3.5, style: `fill:var(--${s.key})` });
      bindTip(dot, `<b>${esc(axes[i])}</b><br>${esc(names[s.key])}: ${pct(v)}`);
      svg.append(dot);
    });
  }
  return svg;
}

export function donut({ segments, centerTop, centerBottom }) {
  const W = 220, H = 220, cx = 110, cy = 110, r = 78, sw = 26;
  const svg = root(W, H, "Donut chart of outcomes");
  const total = segments.reduce((a, s) => a + s.value, 0) || 1;
  let a0 = -Math.PI / 2;
  for (const s of segments) {
    if (!s.value) continue;
    const a1 = a0 + (2 * Math.PI * s.value) / total - 0.02;
    const large = a1 - a0 > Math.PI ? 1 : 0;
    const p = (a) => [cx + r * Math.cos(a), cy + r * Math.sin(a)];
    const [x0, y0] = p(a0), [x1, y1] = p(a1);
    const arc = el("path", { d: `M${x0},${y0} A${r},${r} 0 ${large} 1 ${x1},${y1}`, fill: "none", "stroke-width": sw, "stroke-linecap": "butt", style: `stroke:${s.color}` });
    bindTip(arc, `<b>${esc(s.label)}</b><br>${s.value} of ${total} (${pct(s.value / total)})`);
    svg.append(arc);
    a0 += (2 * Math.PI * s.value) / total;
  }
  svg.append(el("text", { x: cx, y: cy + 2, "text-anchor": "middle", class: "strong", style: "font-size:30px" }, centerTop), el("text", { x: cx, y: cy + 22, "text-anchor": "middle" }, centerBottom));
  return svg;
}

export function lines({ series, names, yMax = 1, xLabel }) {
  const W = 540, H = 240, L = 36, B = 30, T = 12, R = 10;
  const svg = root(W, H, "Line chart of first-try success over the experience phase");
  const xs = series.flatMap((s) => s.points.map((p) => p.x));
  const xMin = Math.min(...xs, 1), xMax = Math.max(...xs, 2);
  const X = (x) => L + ((W - L - R) * (x - xMin)) / (xMax - xMin || 1), Y = (y) => T + (H - T - B) * (1 - y / yMax);
  for (const g of [0, 0.25, 0.5, 0.75, 1]) svg.append(el("line", { x1: L, x2: W - R, y1: Y(g * yMax), y2: Y(g * yMax), class: "grid-line" }), el("text", { x: L - 6, y: Y(g * yMax) + 4, "text-anchor": "end" }, pct(g * yMax)));
  for (let x = xMin; x <= xMax; x++) svg.append(el("text", { x: X(x), y: H - 12, "text-anchor": "middle" }, String(x)));
  svg.append(el("text", { x: (L + W - R) / 2, y: H - 0, "text-anchor": "middle" }, xLabel));
  for (const s of series) {
    if (!s.points.length) continue;
    const d = s.points.map((p, i) => `${i ? "L" : "M"}${X(p.x)},${Y(p.y)}`).join(" ");
    svg.append(el("path", { d: `${d} L${X(s.points.at(-1).x)},${Y(0)} L${X(s.points[0].x)},${Y(0)} Z`, style: `fill:var(--${s.key});fill-opacity:.07` }));
    svg.append(el("path", { d, fill: "none", "stroke-width": 2.5, "stroke-linejoin": "round", style: `stroke:var(--${s.key})` }));
    for (const p of s.points) {
      const dot = el("circle", { cx: X(p.x), cy: Y(p.y), r: 3.5, style: `fill:var(--card);stroke:var(--${s.key});stroke-width:2` });
      bindTip(dot, `<b>${esc(names[s.key])}</b><br>after ${p.x} tasks: ${pct(p.y)} first-try (this task alone: ${pct(p.raw ?? p.y)})`);
      svg.append(dot);
    }
  }
  return svg;
}

export function stackedH({ rows, parts, colors, format }) {
  const rowH = 38, W = 520, L = 92, H = rows.length * rowH + 14;
  const svg = root(W, H, "Stacked bars of time per processing step");
  const max = Math.max(...rows.map((r) => parts.reduce((a, p) => a + (r.values[p] || 0), 0)), 1);
  rows.forEach((r, i) => {
    const y = 8 + i * rowH;
    svg.append(el("text", { x: L - 8, y: y + 17, "text-anchor": "end", class: "strong" }, r.label));
    let x = L;
    const total = parts.reduce((a, p) => a + (r.values[p] || 0), 0);
    for (const p of parts) {
      const w = ((W - L - 70) * (r.values[p] || 0)) / max;
      if (w <= 0) continue;
      const seg = el("rect", { x, y, width: Math.max(w, 1.5), height: 24, rx: 3, style: `fill:${colors[p]}` });
      bindTip(seg, `<b>${esc(r.label)}</b><br>${esc(p)}: ${format(r.values[p])}`);
      svg.append(seg);
      x += w;
    }
    svg.append(el("text", { x: x + 8, y: y + 17 }, format(total)));
  });
  return svg;
}

export function whisker({ items, domain }) {
  const rowH = 46, W = 360, L = 8, R = 8, H = items.length * rowH + 26;
  const svg = root(W, H, "Intervals of the difference between conditions");
  const [lo, hi] = domain;
  const X = (v) => L + ((W - L - R) * (v - lo)) / (hi - lo);
  svg.append(el("line", { x1: X(0), x2: X(0), y1: 4, y2: H - 22, style: "stroke:var(--muted);stroke-dasharray:3 3" }));
  for (const t of [lo, 0, hi]) svg.append(el("text", { x: X(t), y: H - 6, "text-anchor": "middle" }, (t > 0 ? "+" : "") + (t * 100).toFixed(0)));
  items.forEach((it, i) => {
    const y = 12 + i * rowH, good = it.lo > 0, bad = it.hi < 0;
    const color = good ? "var(--ok)" : bad ? "var(--bad)" : "var(--muted)";
    svg.append(el("text", { x: L, y: y, class: "strong" }, it.label));
    const g = el("g", {}, [el("line", { x1: X(Math.max(lo, it.lo)), x2: X(Math.min(hi, it.hi)), y1: y + 16, y2: y + 16, "stroke-width": 4, "stroke-linecap": "round", style: `stroke:${color}` }), el("circle", { cx: X(it.mean), cy: y + 16, r: 5.5, style: `fill:${color}` })]);
    bindTip(g, `<b>${esc(it.label)}</b><br>mean ${(it.mean * 100).toFixed(1)} pts<br>95% interval ${(it.lo * 100).toFixed(1)} to ${(it.hi * 100).toFixed(1)}`);
    svg.append(g);
  });
  return svg;
}
