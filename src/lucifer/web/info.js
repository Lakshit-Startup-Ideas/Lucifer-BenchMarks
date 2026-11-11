// Hover definitions and the detail panel. Any element can opt in:
//   data-term="key"   a glossary term (hover: definition, click: full entry)
//   data-info="key"   an "i" button for a glossary entry
//   data-x="id"       a specific value or chart element with its own explanation (registered with explainer())
import { G } from "./glossary.js";

const registry = new Map();
let counter = 0;
const stack = [];
export const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

/** Register an explanation for one value: {title, tip, lead, rows:[[label,value]], how, read, caution, related:[keys]}. Returns its id. */
export function explainer(obj) {
  const id = `x${++counter}`;
  registry.set(id, obj);
  return id;
}
export function resetExplainers() { registry.clear(); counter = 0; }
export const term = (key, label) => `<span class="term" data-term="${esc(key)}" tabindex="0">${label ?? esc(G[key]?.name ?? key)}</span>`;
export const infoBtn = (key) => `<button type="button" class="info" data-info="${esc(key)}" aria-label="About: ${esc(G[key]?.name ?? key)}">i</button>`;
export const val = (html, id) => `<span class="val" data-x="${id}" tabindex="0" role="button">${html}</span>`;

export function attachExplain(node, obj) {
  node.setAttribute("data-x", explainer(obj));
  node.setAttribute("tabindex", "0");
  node.setAttribute("role", "button");
  node.classList.add("clickable");
}

const tipEl = () => document.getElementById("tip");
function tipFor(el) {
  if (el.dataset.term) { const g = G[el.dataset.term]; return g ? `<b>${esc(g.name)}</b><br>${esc(g.short)}<div class="hint">Click for the full definition</div>` : ""; }
  if (el.dataset.info) { const g = G[el.dataset.info]; return g ? `<b>${esc(g.name)}</b><br>${esc(g.short)}<div class="hint">Click for details</div>` : ""; }
  if (el.dataset.x) { const x = registry.get(el.dataset.x); return x ? `<b>${esc(x.title)}</b><br>${esc(x.tip ?? x.lead ?? "")}<div class="hint">Click for the explanation</div>` : ""; }
  return "";
}
function showTip(el, x, y) {
  const html = tipFor(el); if (!html) return;
  const t = tipEl(); t.innerHTML = html; t.hidden = false;
  const r = t.getBoundingClientRect();
  t.style.left = Math.max(8, Math.min(window.innerWidth - r.width - 8, x + 14)) + "px";
  t.style.top = Math.max(8, Math.min(window.innerHeight - r.height - 8, y + 16)) + "px";
}
const hideTip = () => (tipEl().hidden = true);

const section = (title, text) => (text ? `<section><h4>${esc(title)}</h4><p>${esc(text)}</p></section>` : "");
function drawerHtml(entry) {
  // A value's explanation inherits the full definition of its main term (the first related key), unless it supplies its own text.
  const g = entry.what || entry.how ? null : (entry.related || []).map((k) => G[k]).find(Boolean);
  if (g) entry = { ...entry, what: g.what, how: g.how, read: entry.read || g.read, caution: entry.caution || g.caution, aboutName: g.name };
  const rel = (entry.related || []).filter((k) => G[k]);
  const rows = entry.rows?.length ? `<section class="thisval"><h4>This value</h4><dl>${entry.rows.map(([k, v]) => `<dt>${esc(k)}</dt><dd>${v}</dd>`).join("")}</dl></section>` : "";
  return `<header><div><small>${esc(entry.kicker ?? "Explanation")}</small><h3>${esc(entry.title)}</h3></div><button type="button" class="close" aria-label="Close" data-close>✕</button></header>
    <div class="body">${entry.lead ? `<p class="lead">${esc(entry.lead)}</p>` : ""}${rows}${entry.aboutName ? `<h4 style="margin:0 0 8px;color:var(--ink);font-size:13px;text-transform:none;letter-spacing:0">About: ${esc(entry.aboutName)}</h4>` : ""}${section("What it is", entry.what)}${section("How it is calculated", entry.how)}${section("How to read it", entry.read)}${entry.caution ? `<section class="caution"><h4>Keep in mind</h4><p>${esc(entry.caution)}</p></section>` : ""}
    ${rel.length ? `<section><h4>Related</h4><div class="chips">${rel.map((k) => `<button type="button" class="chip" data-term="${k}">${esc(G[k].name)}</button>`).join("")}</div></section>` : ""}</div>
    ${stack.length > 1 ? `<footer><button type="button" class="ghost" data-back>← Back</button></footer>` : ""}`;
}
function fromGlossary(key) { const g = G[key]; return g ? { kicker: "Definition", title: g.name, lead: g.short, what: g.what, how: g.how, read: g.read, caution: g.caution, related: g.related } : null; }

export function openEntry(entry, push = true) {
  const d = document.getElementById("drawer"), back = document.getElementById("scrim");
  if (push) stack.push(entry);
  d.innerHTML = drawerHtml(entry);
  d.hidden = back.hidden = false;
  requestAnimationFrame(() => { d.classList.add("open"); back.classList.add("open"); d.querySelector("[data-close]")?.focus(); });
}
export function closeDrawer() {
  const d = document.getElementById("drawer"), back = document.getElementById("scrim");
  d.classList.remove("open"); back.classList.remove("open"); stack.length = 0;
  setTimeout(() => { if (!d.classList.contains("open")) d.hidden = back.hidden = true; }, 200);
}

export function initInfo() {
  const pick = (t) => t.closest?.("[data-term],[data-info],[data-x]");
  document.addEventListener("mousemove", (e) => { const el = pick(e.target); if (el) showTip(el, e.clientX, e.clientY); else hideTip(); });
  document.addEventListener("focusin", (e) => { const el = pick(e.target); if (el) { const r = el.getBoundingClientRect(); showTip(el, r.left, r.bottom); } });
  document.addEventListener("focusout", hideTip);
  document.addEventListener("click", (e) => {
    if (e.target.closest("[data-close]") || e.target.id === "scrim") return closeDrawer();
    if (e.target.closest("[data-back]")) { stack.pop(); return openEntry(stack.at(-1), false); }
    const el = pick(e.target); if (!el) return;
    const entry = el.dataset.x ? registry.get(el.dataset.x) : fromGlossary(el.dataset.term || el.dataset.info);
    if (entry) { hideTip(); openEntry(entry); }
  });
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") closeDrawer();
    if ((e.key === "Enter" || e.key === " ") && pick(document.activeElement) && document.activeElement.tagName !== "BUTTON") { e.preventDefault(); document.activeElement.click(); }
  });
}
