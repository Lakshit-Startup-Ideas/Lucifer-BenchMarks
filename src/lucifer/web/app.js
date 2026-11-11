import { bindTip, donut, esc, fmtMs, groupedBars, lines, pct, radar, stackedH, whisker } from "./charts.js";

const NAMES = { baseline: "Baseline (no memory)", lucifer: "Lucifer (relevant memory)", irrelevant: "Control (irrelevant notes)" };
const SHORT = { baseline: "Baseline", lucifer: "Lucifer", irrelevant: "Control" };
const OP_COLORS = { retrieve_memory: "var(--k-retrieval)", build_prompt: "var(--k-prompt)", "llm.generate": "var(--k-llm)", "sandbox.run_tests": "var(--k-execution)", "memory.write": "var(--k-memory)" };
const KIND_COLORS = { root: "var(--k-root)", retrieval: "var(--k-retrieval)", prompt: "var(--k-prompt)", attempt: "var(--k-attempt)", llm: "var(--k-llm)", execution: "var(--k-execution)", memory: "var(--k-memory)" };

const state = { runs: [], runId: null, summary: null, tab: "overview", hidden: new Set(), tf: { condition: "", phase: "", seed: "", q: "", failed: false }, traces: null, traceId: null, spans: null, spanId: null, mem: { condition: "lucifer", seed: "0", data: null } };
const $ = (s) => document.querySelector(s);
const view = $("#view");
const api = async (p) => { const r = await fetch(p); if (!r.ok) throw new Error(`${p}: ${r.status}`); return r.json(); };

// ---------- boot ----------
async function boot() {
  const saved = localStorage.getItem("lucifer-theme") || (matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light");
  document.documentElement.dataset.theme = saved;
  $("#themeBtn").onclick = () => { const t = document.documentElement.dataset.theme === "dark" ? "light" : "dark"; document.documentElement.dataset.theme = t; localStorage.setItem("lucifer-theme", t); };
  $("#tabs").onclick = (e) => { const b = e.target.closest("button[data-tab]"); if (b) setTab(b.dataset.tab); };
  $("#runSelect").onchange = (e) => selectRun(e.target.value);
  state.runs = await api("/api/runs");
  $("#runSelect").innerHTML = state.runs.map((r) => `<option value="${esc(r.id)}">${esc(r.id)} · ${esc(r.backend)}</option>`).join("");
  if (!state.runs.length) { view.innerHTML = `<div class="card empty"><h3>No runs yet</h3><p>Create one with <code>lucifer run --backend sim-learner</code>, then reload.</p></div>`; return; }
  const want = new URLSearchParams(location.search).get("run");
  await selectRun(state.runs.find((r) => r.id === want)?.id ?? state.runs[0].id);
}
function setTab(tab) { state.tab = tab; document.querySelectorAll("#tabs button").forEach((b) => b.classList.toggle("active", b.dataset.tab === tab)); render(); }
async function selectRun(id) {
  state.runId = id; $("#runSelect").value = id; state.traces = state.spans = state.traceId = state.spanId = null; state.mem.data = null;
  state.summary = await api(`/api/runs/${encodeURIComponent(id)}/summary`);
  $("#simBadge").hidden = !state.summary.simulated;
  state.hidden = new Set();
  render();
}
function render() { if (!state.summary) return; ({ overview, traces: tracesView, memory: memoryView })[state.tab](); }

// ---------- overview ----------
function delta(a, b, unit = "pts", good = "up") {
  const d = a - b; const v = unit === "pts" ? d * 100 : d;
  const cls = Math.abs(v) < (unit === "pts" ? 0.5 : 1) ? "flat" : (v > 0) === (good === "up") ? "up" : "down";
  const txt = unit === "pts" ? `${v > 0 ? "+" : ""}${v.toFixed(0)} pts` : `${v > 0 ? "+" : ""}${unit === "ms" ? fmtMs(Math.abs(v)).replace(/^/, v < 0 ? "-" : "") : Math.round(v)}`;
  return `<span class="pill ${cls}">${txt}</span>`;
}
function legend(conds) {
  return `<div class="legend">${conds.map((c) => `<button data-c="${c}" class="${state.hidden.has(c) ? "off" : ""}"><span class="dot" style="background:var(--${c})"></span>${esc(NAMES[c])}</button>`).join("")}</div>`;
}
function overview() {
  const s = state.summary, C = s.conditions, vis = C.filter((c) => !state.hidden.has(c)), k = s.kpis, B = k.baseline, L = k.lucifer;
  const kpi = (label, value, foot, hint) => `<div class="card kpi c3"><div class="label"><span>${label}</span><span title="${esc(hint)}">ⓘ</span></div><div class="value">${value}</div><div class="foot">${foot}</div></div>`;
  const has = B && L;
  view.innerHTML = `<div class="grid">
    ${kpi("First-try success (similar + transfer)", pct((L || B).pass_primary), has ? `${delta(L.pass_primary, B.pass_primary)} vs baseline ${pct(B.pass_primary)}` : "single condition", "Share of new, related tasks solved on the first attempt, with memory frozen. The primary measure.")}
    ${kpi("Replay success (tasks seen before)", pct((L || B).pass_replay), has ? `${delta(L.pass_replay, B.pass_replay)} vs baseline ${pct(B.pass_replay)}` : "", "The experience tasks again. High replay with no gain on new tasks means memorising, not learning.")}
    ${kpi("Average time per task", fmtMs((L || B).avg_solve_ms), has ? `${delta(L.avg_solve_ms, B.avg_solve_ms, "ms", "down")} vs baseline ${fmtMs(B.avg_solve_ms)}` : "", "Whole solve: retrieval, model calls, test runs. Simulated runs use a made-up model latency.")}
    ${kpi("Tokens per task", Math.round((L || B).avg_tokens).toLocaleString(), has ? `${delta(L.avg_tokens, B.avg_tokens, "tok", "down")} vs baseline ${Math.round(B.avg_tokens).toLocaleString()}` : "", "Prompt plus completion. Lessons in the prompt cost tokens.")}

    <div class="card c5"><h3>First-try success by phase</h3><div class="sub">Experience = learning phase · the other three run with memory frozen</div>${legend(C)}<div id="ch-bars"></div></div>
    <div class="card c3"><h3>By task family</h3><div class="sub">Evaluation phases only</div><div id="ch-radar"></div></div>
    <div class="card c4"><h3>Promotion gates</h3><div class="sub">Computed from this run's traces</div><div id="gates"></div></div>

    <div class="card c5"><h3>Learning curve</h3><div class="sub">Running average of first-try success as the agent works through the experience tasks (all seeds)</div>${legend(C)}<div id="ch-curve"></div></div>
    <div class="card c3"><h3>Outcomes</h3><div class="sub" id="outcomeSub"></div><div id="ch-donut"></div><div class="legend" id="donutLegend" style="justify-content:center"></div></div>
    <div class="card c4"><h3>Where the time goes</h3><div class="sub">Mean time per processing step, per condition</div><div id="ch-stack"></div><div class="legend" id="stackLegend"></div></div>

    <div class="card c8"><h3>Operations</h3><div class="sub">Every step recorded as a span, like the operations view of a tracing tool</div><div id="ops"></div></div>
    <div class="card c4"><h3>Hardest tasks</h3><div class="sub">Highest first-try failure rate</div><div id="hard"></div></div>
  </div>`;
  view.querySelectorAll(".legend button").forEach((b) => (b.onclick = () => { state.hidden.has(b.dataset.c) ? state.hidden.delete(b.dataset.c) : state.hidden.add(b.dataset.c); overview(); }));
  $("#ch-bars").append(groupedBars({ categories: s.phase_bars.map((p) => ({ label: p.phase, values: p })), keys: vis, names: NAMES }));
  $("#ch-radar").append(radar({ axes: s.radar.axes, series: vis.map((c) => ({ key: c, values: s.radar[c] })), names: NAMES }));
  $("#ch-curve").append(lines({ series: vis.map((c) => ({ key: c, points: s.curve[c].map((p) => ({ x: p.position, y: p.pass, raw: p.raw })) })), names: NAMES, xLabel: "number of experience tasks done" }));
  gatesCard(s);
  donutCard(s, vis[0] || C[0]);
  stackCard(s, vis);
  opsCard(s);
  hardCard(s);
}
function gatesCard(s) {
  const g = s.gates, host = $("#gates");
  if (!g) { host.innerHTML = `<div class="empty">Gates need the baseline and lucifer conditions in the same run.</div>`; return; }
  const g1 = g.gate1_improvement, g2 = g.gate2_retention, g3 = g.gate3_auditability;
  const icon = (ok, na) => `<span class="icon ${na ? "na" : ok ? "pass" : "fail"}">${na ? "–" : ok ? "✓" : "✕"}</span>`;
  const iv = (t) => `${t[0] >= 0 ? "+" : ""}${(t[0] * 100).toFixed(0)} pts (${(t[1] * 100).toFixed(0)} to ${(t[2] * 100).toFixed(0)})`;
  host.innerHTML = `<div class="gate">${icon(g1.passed)}<div><b>1 · Improvement — ${esc(g1.verdict)}</b><small>vs baseline ${iv(g1.lucifer_minus_baseline)}<br>vs control ${iv(g1.lucifer_minus_irrelevant)}</small><div id="whisk"></div></div></div>
    <div class="gate">${icon(g2.passed, g2.inconclusive)}<div><b>2 · Retention — ${g2.inconclusive ? "inconclusive" : g2.passed ? "pass" : "fail"}</b><small>${g2.inconclusive ? "the baseline masters no task, so there is nothing to lose" : `mean drop ${(g2.mean_drop * 100).toFixed(1)} pts over ${g2.mastered_tasks} mastered tasks`}</small></div></div>
    <div class="gate">${icon(g3.passed)}<div><b>3 · Auditability — ${g3.passed ? "pass" : "fail"}</b><small>${g3.runs_audited} memory stores: hash chain, rollback, provenance</small></div></div>`;
  $("#whisk").append(whisker({ domain: [-0.5, 0.75], items: [{ label: "Lucifer − baseline", mean: g1.lucifer_minus_baseline[0], lo: g1.lucifer_minus_baseline[1], hi: g1.lucifer_minus_baseline[2] }, { label: "Lucifer − control", mean: g1.lucifer_minus_irrelevant[0], lo: g1.lucifer_minus_irrelevant[1], hi: g1.lucifer_minus_irrelevant[2] }] }));
}
function donutCard(s, cond) {
  const o = s.outcomes[cond], total = o.first_try + o.fixed_on_retry + o.failed;
  $("#outcomeSub").innerHTML = `${esc(NAMES[cond])} · <select id="donutCond" style="background:var(--soft);color:var(--ink);border:1px solid var(--line);border-radius:6px">${s.conditions.map((c) => `<option value="${c}" ${c === cond ? "selected" : ""}>${esc(SHORT[c])}</option>`).join("")}</select>`;
  $("#donutCond").onchange = (e) => { $("#ch-donut").innerHTML = ""; donutCard(s, e.target.value); };
  const seg = [{ label: "Passed first try", value: o.first_try, color: "var(--ok)" }, { label: "Fixed on the retry", value: o.fixed_on_retry, color: "var(--warn)" }, { label: "Failed after retry", value: o.failed, color: "var(--bad)" }];
  $("#ch-donut").innerHTML = ""; $("#ch-donut").append(donut({ segments: seg.map((x) => ({ ...x, color: x.color })), centerTop: total.toLocaleString(), centerBottom: "tasks solved" }));
  $("#donutLegend").innerHTML = seg.map((x) => `<span style="display:inline-flex;gap:6px;align-items:center"><span class="dot" style="background:${x.color}"></span>${x.label} ${x.value}</span>`).join("");
}
function stackCard(s, vis) {
  const parts = Object.keys(OP_COLORS);
  $("#ch-stack").append(stackedH({ rows: vis.map((c) => ({ label: SHORT[c], values: s.latency_stack[c] })), parts, colors: OP_COLORS, format: fmtMs }));
  $("#stackLegend").innerHTML = parts.map((p) => `<span style="display:inline-flex;gap:6px;align-items:center"><span class="dot" style="background:${OP_COLORS[p]}"></span>${p}</span>`).join("");
}
function opsCard(s) {
  const max = Math.max(...s.operations.map((o) => o.total_ms), 1);
  $("#ops").innerHTML = `<table><thead><tr><th>Operation</th><th class="num">Spans</th><th class="num">Mean</th><th class="num">p50</th><th class="num">p95</th><th class="num">Max</th><th class="num">Errors</th><th>Share of time</th></tr></thead><tbody>${s.operations.map((o) => `<tr><td><b>${esc(o.operation)}</b></td><td class="num">${o.count.toLocaleString()}</td><td class="num">${fmtMs(o.mean_ms)}</td><td class="num">${fmtMs(o.p50_ms)}</td><td class="num">${fmtMs(o.p95_ms)}</td><td class="num">${fmtMs(o.max_ms)}</td><td class="num">${o.errors ? `<span style="color:var(--bad)">${o.errors}</span>` : "0"}</td><td><div class="share"><i style="width:${(o.total_ms / max) * 100}%;background:${OP_COLORS[o.operation] || "var(--brand)"}"></i></div></td></tr>`).join("")}</tbody></table><div class="sub" style="margin-top:8px">“solve” and “attempt” contain the steps below them, so their time overlaps the others. An error means a failed test run or a task that never passed.</div>`;
}
function hardCard(s) {
  $("#hard").innerHTML = `<ul class="rank">${s.hardest.map((h) => `<li><span class="avatar">${esc(h.family.slice(0, 2).toUpperCase())}</span><div class="grow"><div class="name">${esc(h.task_id)}</div><small>${h.solves} solves · ${h.avg_attempts.toFixed(2)} attempts avg</small></div><b style="color:${h.first_try_fail > 0.5 ? "var(--bad)" : "var(--warn)"}">${pct(h.first_try_fail)}</b></li>`).join("")}</ul>`;
}

// ---------- traces ----------
async function loadTraces() {
  const f = state.tf, p = new URLSearchParams({ limit: "250" });
  if (f.condition) p.set("condition", f.condition); if (f.phase) p.set("phase", f.phase); if (f.seed !== "") p.set("seed", f.seed); if (f.q) p.set("q", f.q); if (f.failed) p.set("failed", "1");
  state.traces = await api(`/api/runs/${encodeURIComponent(state.runId)}/traces?${p}`);
}
async function openTrace(id) {
  state.traceId = id; state.spanId = null;
  state.spans = (await api(`/api/runs/${encodeURIComponent(state.runId)}/traces/${id.split("/").map(encodeURIComponent).join("/")}`)).spans;
  state.spanId = state.spans[0]?.span_id;
  renderTraceDetail(); document.querySelectorAll(".titem").forEach((n) => n.classList.toggle("sel", n.dataset.id === id));
}
async function tracesView() {
  const s = state.summary;
  if (!s.totals.spans) { view.innerHTML = `<div class="card empty"><h3>No traces in this run</h3><p>It was saved before tracing was added. Run the experiment again to record every step.</p></div>`; return; }
  if (!state.traces) await loadTraces();
  const f = state.tf, seeds = Array.from({ length: s.totals.seeds }, (_, i) => i);
  view.innerHTML = `<div class="traces"><div class="card"><h3>Traces</h3><div class="sub">One per task solve · ${state.traces.total.toLocaleString()} match</div>
    <div class="filters"><input type="search" id="fq" placeholder="Search task, family…" value="${esc(f.q)}">
      <select id="fc"><option value="">All conditions</option>${s.conditions.map((c) => `<option value="${c}" ${f.condition === c ? "selected" : ""}>${esc(SHORT[c])}</option>`).join("")}</select>
      <select id="fp"><option value="">All phases</option>${["experience", "similar", "transfer", "replay"].map((p) => `<option ${f.phase === p ? "selected" : ""}>${p}</option>`).join("")}</select>
      <select id="fs"><option value="">All seeds</option>${seeds.map((x) => `<option value="${x}" ${String(f.seed) === String(x) ? "selected" : ""}>seed ${x}</option>`).join("")}</select>
      <label style="display:flex;gap:6px;align-items:center"><input type="checkbox" id="ff" ${f.failed ? "checked" : ""}> first try failed</label></div>
    <div class="tlist" id="tlist">${state.traces.items.map((t) => `<div class="titem ${t.trace_id === state.traceId ? "sel" : ""}" data-id="${esc(t.trace_id)}"><span class="status ${t.pass_at_1 ? "" : t.pass_at_2 ? "retry" : "fail"}"></span><div><b>${esc(t.task_id)}</b><div class="meta">${esc(SHORT[t.condition])} · seed ${t.seed} · ${t.phase}${t.lessons_shown ? ` · ${t.lessons_shown} lessons` : ""}</div></div><span class="dur">${fmtMs(t.duration_ms)}</span></div>`).join("") || `<div class="empty">No traces match.</div>`}</div></div>
    <div class="card" id="detail"><div class="empty">Pick a trace on the left to see every step.</div></div></div>`;
  const reload = async () => { await loadTraces(); tracesView(); };
  $("#fq").onchange = (e) => { f.q = e.target.value; reload(); };
  $("#fc").onchange = (e) => { f.condition = e.target.value; reload(); };
  $("#fp").onchange = (e) => { f.phase = e.target.value; reload(); };
  $("#fs").onchange = (e) => { f.seed = e.target.value; reload(); };
  $("#ff").onchange = (e) => { f.failed = e.target.checked; reload(); };
  $("#tlist").onclick = (e) => { const n = e.target.closest(".titem"); if (n) openTrace(n.dataset.id); };
  if (state.traceId && state.spans) renderTraceDetail(); else if (state.traces.items[0]) openTrace(state.traces.items[0].trace_id);
}
function flowOf(spans) {
  const step = (label, err) => `<span class="step ${err ? "err" : ""}">${label}</span>`, out = [];
  for (const sp of spans) {
    if (sp.kind === "retrieval") out.push(step(`retrieve memory · ${sp.attrs.lessons_shown?.length ?? 0} lessons`));
    else if (sp.kind === "prompt") out.push(step("build prompt"));
    else if (sp.kind === "attempt") out.push(step(`attempt ${sp.attrs.attempt} ${sp.attrs.passed ? "✓ passed" : "✕ failed"}`, !sp.attrs.passed));
    else if (sp.kind === "memory") out.push(step(`write memory · ${sp.attrs.lessons_written?.length ?? 0} lessons`));
  }
  return out.join(`<span class="arrow">→</span>`);
}
function renderTraceDetail() {
  const spans = state.spans, host = $("#detail"); if (!spans || !host) return;
  const root = spans[0], total = root.duration_ms || 1, depth = {};
  spans.forEach((sp) => (depth[sp.span_id] = sp.parent_id ? (depth[sp.parent_id] ?? 0) + 1 : 0));
  const A = root.attrs;
  host.innerHTML = `<h3>${esc(root.name)} <span class="chip ${A.pass_at_1 ? "ok" : A.pass_at_2 ? "" : "err"}">${A.pass_at_1 ? "first try" : A.pass_at_2 ? "fixed on retry" : "failed"}</span></h3>
    <div class="sub">${esc(NAMES[A.condition])} · seed ${A.seed} · ${esc(A.phase)} phase · ${esc(A.family)} · ${spans.length} spans · ${fmtMs(total)} total${spans.some((s) => s.attrs.simulated) ? " · <b>simulated model latency</b>" : ""}</div>
    <div class="flow">${flowOf(spans)}</div>
    <div class="wf-head"><span>Span</span><span>Timeline</span><span style="text-align:right">Duration</span></div>
    <div class="wf">${spans.map((sp) => `<div class="wf-row ${sp.span_id === state.spanId ? "sel" : ""}" data-id="${esc(sp.span_id)}"><div class="wf-name" style="padding-left:${depth[sp.span_id] * 16}px"><i>${depth[sp.span_id] ? "└" : "▸"}</i>${esc(sp.name)}</div><div class="wf-track"><div class="wf-bar ${sp.status === "error" ? "error" : ""}" style="left:${(sp.start_ms / total) * 100}%;width:${Math.max((sp.duration_ms / total) * 100, 0.4)}%;background:${KIND_COLORS[sp.kind]}"></div></div><div class="wf-dur">${fmtMs(sp.duration_ms)}</div></div>`).join("")}</div>
    <div class="axis"><span></span><span class="ticks">${[0, 0.25, 0.5, 0.75, 1].map((t) => `<span>${fmtMs(total * t)}</span>`).join("")}</span><span></span></div>
    <div class="attrs" id="attrs"></div>`;
  host.querySelectorAll(".wf-row").forEach((r) => { r.onclick = () => { state.spanId = r.dataset.id; renderTraceDetail(); }; const sp = spans.find((s) => s.span_id === r.dataset.id); bindTip(r.querySelector(".wf-bar"), `<b>${esc(sp.name)}</b><br>start ${fmtMs(sp.start_ms)} · ${fmtMs(sp.duration_ms)}<br>${sp.status}`); });
  renderAttrs(spans.find((s) => s.span_id === state.spanId) || root);
}
function renderAttrs(sp) {
  const a = sp.attrs, big = ["prompt", "reply", "code", "feedback"], skip = new Set([...big, "lessons_shown", "lessons_written"]);
  const kv = Object.entries(a).filter(([k]) => !skip.has(k)).map(([k, v]) => `<dt>${esc(k)}</dt><dd>${typeof v === "boolean" ? `<span class="chip ${v ? "ok" : "err"}">${v}</span>` : esc(typeof v === "object" ? JSON.stringify(v) : v)}</dd>`).join("");
  const lessons = (title, list) => (list?.length ? `<h4>${title}</h4>${list.map((l) => `<div class="lesson ${l.kind}"><div class="head"><span class="chip">${esc(l.kind)}</span><span>v${l.version}</span><span>from ${esc(l.task_id ?? "this task")}</span>${l.hash ? `<span class="hash">${esc(l.hash)}</span>` : ""}</div><p>${esc(l.text)}</p></div>`).join("")}` : "");
  $("#attrs").innerHTML = `<h4>${esc(sp.name)} · ${sp.status} · start ${fmtMs(sp.start_ms)} · ${fmtMs(sp.duration_ms)}</h4><dl class="kv"><dt>kind</dt><dd>${esc(sp.kind)}</dd>${kv}</dl>
    ${lessons("Lessons shown to the model", a.lessons_shown)}${lessons("Lessons written to memory", a.lessons_written)}
    ${big.filter((k) => a[k]).map((k) => `<h4>${k}</h4><pre class="code">${esc(a[k])}</pre>`).join("")}`;
}

// ---------- memory ----------
async function memoryView() {
  const s = state.summary, m = state.mem, conds = s.conditions.filter((c) => c !== "baseline");
  if (!conds.length) { view.innerHTML = `<div class="card empty">This run has no memory conditions.</div>`; return; }
  if (!conds.includes(m.condition)) m.condition = conds[0];
  if (!m.data) m.data = await api(`/api/runs/${encodeURIComponent(state.runId)}/memory?condition=${m.condition}&seed=${m.seed}`);
  const store = m.data[0], seeds = Array.from({ length: s.totals.seeds }, (_, i) => i);
  view.innerHTML = `<div class="card"><h3>Memory explorer</h3><div class="sub">What the agent wrote down during the experience phase. Each lesson is chained to the one before it by a hash, so any change to history is detectable.</div>
    <div class="mem-controls"><select id="mc">${conds.map((c) => `<option value="${c}" ${m.condition === c ? "selected" : ""}>${esc(NAMES[c])}</option>`).join("")}</select>
    <select id="ms">${seeds.map((x) => `<option value="${x}" ${String(m.seed) === String(x) ? "selected" : ""}>seed ${x}</option>`).join("")}</select>
    <span class="chip">${store ? store.lessons.length : 0} lessons</span><span class="chip">${store ? store.lessons.filter((l) => l.kind === "failure").length : 0} failures</span><span class="chip">${store ? store.lessons.filter((l) => l.kind === "fix").length : 0} fixes</span></div>
    ${store && store.lessons.length ? `<div class="chain">${store.lessons.map((l) => `<div class="lesson ${l.kind}"><div class="head"><span class="chip">${esc(l.kind)}</span><b>v${l.version}</b><span>task ${esc(l.task_id)}</span><span>seed ${l.seed}</span><span class="hash" title="${esc(l.hash)}">#${esc(l.hash.slice(0, 12))}</span></div><p>${esc(l.text)}</p></div>`).join("")}</div>` : `<div class="empty">No lessons were written (the agent never failed during the experience phase).</div>`}</div>`;
  const reload = async () => { m.data = null; memoryView(); };
  $("#mc").onchange = (e) => { m.condition = e.target.value; reload(); };
  $("#ms").onchange = (e) => { m.seed = e.target.value; reload(); };
}

boot().catch((e) => { view.innerHTML = `<div class="card empty"><h3>Could not load</h3><p>${esc(e.message)}</p></div>`; });
