import { donut, fmtMs, groupedBars, lines, pct, radar, stackedH, whisker } from "./charts.js";
import { ATTR_TERMS, G, KIND_DEFS } from "./glossary.js";
import { attachExplain, esc, explainer, infoBtn, initInfo, resetExplainers, term, val } from "./info.js";

const NAMES = { baseline: "Baseline (no memory)", lucifer: "Lucifer (relevant memory)", irrelevant: "Control (irrelevant notes)" };
const SHORT = { baseline: "Baseline", lucifer: "Lucifer", irrelevant: "Control" };
const OP_COLORS = { retrieve_memory: "var(--k-retrieval)", build_prompt: "var(--k-prompt)", "llm.generate": "var(--k-llm)", "sandbox.run_tests": "var(--k-execution)", "memory.write": "var(--k-memory)" };
const OP_INFO = {
  retrieve_memory: "Selects the stored lessons most relevant to the task. Baseline never calls it with lessons; Lucifer picks the best matches, the control the worst.",
  build_prompt: "Assembles the model input from the task text and any lessons. It is effectively instantaneous.",
  "llm.generate": "One call to the model. This is normally the largest share of the time.",
  "sandbox.run_tests": "Runs the model's code against the task's hidden tests in a separate process. A failed run is recorded as an error and its message is returned to the model.",
  "memory.write": "Stores a lesson after a failed attempt (and the fix after a successful retry). Only happens in the experience phase for Lucifer and the control.",
  attempt: "One try at the task. Contains a model call and a test run. Its time overlaps those steps.",
  "solve (whole task)": "The complete solve: retrieval, prompt, every attempt and any memory write. Its time contains all the other steps.",
};
const KIND_COLORS = { root: "var(--k-root)", retrieval: "var(--k-retrieval)", prompt: "var(--k-prompt)", attempt: "var(--k-attempt)", llm: "var(--k-llm)", execution: "var(--k-execution)", memory: "var(--k-memory)" };
const KIND_LABEL = { root: "Solve", retrieval: "Retrieval", prompt: "Prompt", attempt: "Attempt", llm: "Model call", execution: "Test run", memory: "Memory write" };

const state = { runs: [], runId: null, summary: null, tab: "overview", hidden: new Set(), donutCond: null, tf: { condition: "", phase: "", seed: "", q: "", failed: false }, traces: null, traceId: null, spans: null, spanId: null, mem: { condition: "lucifer", seed: "0", data: null }, gloss: "" };
const $ = (s) => document.querySelector(s), view = $("#view");
const api = async (p) => { const r = await fetch(p); if (!r.ok) throw new Error(`${p}: ${r.status}`); return r.json(); };
const pts = (x, d = 0) => `${x > 0 ? "+" : x < 0 ? "−" : ""}${Math.abs(x * 100).toFixed(d)} pts`;
const plural = (n, w) => `${n.toLocaleString()} ${w}${n === 1 ? "" : "s"}`;

// ---------- boot ----------
async function boot() {
  initInfo();
  const saved = localStorage.getItem("lucifer-theme") || (matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light");
  document.documentElement.dataset.theme = saved;
  $("#themeBtn").onclick = () => { const t = document.documentElement.dataset.theme === "dark" ? "light" : "dark"; document.documentElement.dataset.theme = t; localStorage.setItem("lucifer-theme", t); };
  $("#tabs").onclick = (e) => { const b = e.target.closest("button[data-tab]"); if (b) setTab(b.dataset.tab); };
  $("#runSelect").onchange = (e) => selectRun(e.target.value);
  state.runs = await api("/api/runs");
  $("#runSelect").innerHTML = state.runs.map((r) => `<option value="${esc(r.id)}">${esc(r.id)}</option>`).join("");
  if (!state.runs.length) { setTab("guide"); return; }
  const want = new URLSearchParams(location.search).get("run"), tab = new URLSearchParams(location.search).get("tab");
  if (tab) state.tab = tab;
  document.querySelectorAll("#tabs button").forEach((b) => b.classList.toggle("active", b.dataset.tab === state.tab));
  await selectRun(state.runs.find((r) => r.id === want)?.id ?? state.runs[0].id);
}
function setTab(tab) { state.tab = tab; document.querySelectorAll("#tabs button").forEach((b) => b.classList.toggle("active", b.dataset.tab === tab)); render(); window.scrollTo(0, 0); }
async function selectRun(id) {
  state.runId = id; $("#runSelect").value = id; state.traces = state.spans = state.traceId = state.spanId = null; state.mem.data = null; state.hidden = new Set();
  state.summary = await api(`/api/runs/${encodeURIComponent(id)}/summary`);
  $("#simBadge").hidden = !state.summary.simulated;
  render();
}
function render() { resetExplainers(); if (state.tab === "guide") return guideView(); if (!state.summary) { view.innerHTML = `<div class="card empty"><h3>No runs yet</h3><p>Create one with <code>lucifer run --backend sim-learner</code>, then reload.</p></div>`; return; } ({ overview, traces: tracesView, memory: memoryView })[state.tab](); }

// ---------- shared pieces ----------
const pagehead = (title, text, extra = "") => `<div class="pagehead"><h1>${title}</h1><p>${text}</p>${extra}</div>`;
const section = (title, text) => `<div class="section"><h2>${title}</h2><p>${text}</p></div>`;
const card = (cls, key, title, sub, body, id = "") => `<div class="card ${cls}" ${id ? `id="${id}"` : ""}><header class="ch"><div><h3>${term(key, title)}${infoBtn(key)}</h3>${sub ? `<div class="sub">${sub}</div>` : ""}</div></header>${body}</div>`;
function legend(conds) { return `<div class="legend">${conds.map((c) => `<button type="button" data-c="${c}" class="${state.hidden.has(c) ? "off" : ""}" aria-pressed="${!state.hidden.has(c)}"><span class="dot" style="background:var(--${c})"></span>${term(c, esc(NAMES[c]))}</button>`).join("")}</div>`; }
function rowsOf(...r) { return r.filter(Boolean); }

// ---------- overview ----------
function overview() {
  const s = state.summary, C = s.conditions, vis = C.filter((c) => !state.hidden.has(c)), k = s.kpis, B = k.baseline, L = k.lucifer, T = s.tasks, seeds = s.totals.seeds;
  const ref = L || B;
  const kpi = (key, title, value, foot, expl) => `<div class="card kpi c3"><div class="label"><span>${term(key, title)}</span>${infoBtn(key)}</div><div class="value">${val(value, explainer(expl))}</div><div class="foot">${foot}</div></div>`;
  const dlt = (a, b, unit, good = "up") => { const d = a - b; const v = unit === "pts" ? d * 100 : d; const neutral = Math.abs(v) < (unit === "pts" ? 0.5 : unit === "ms" ? 1 : 1); const cls = neutral ? "flat" : (v > 0) === (good === "up") ? "up" : "down"; const txt = unit === "pts" ? pts(d) : unit === "ms" ? `${d >= 0 ? "+" : "−"}${fmtMs(Math.abs(d))}` : `${d >= 0 ? "+" : "−"}${Math.abs(Math.round(d)).toLocaleString()}`; return `<span class="pill ${cls}">${txt}</span>`; };
  const has = !!(B && L);
  const kp = (name, v, extra) => ({ title: name, tip: extra, lead: extra, rows: [["Tasks in the measure", T.primary], ["Seeds", seeds], ["Solves behind it", plural(T.primary * seeds, "solve")]] });

  view.innerHTML = pagehead("Run overview", `Does an AI agent that remembers its earlier mistakes solve later, related tasks better than the same model without memory? This page summarises the evidence from run <b>${esc(s.id)}</b>. Hover any underlined term for a definition; click any value, chart element or ⓘ for a full explanation.`,
    `<div class="runstrip"><span class="chip" data-term="simulated" ${s.simulated ? "" : "hidden"}>Simulated agent</span><span class="chip">${esc(s.meta.backend ?? "?")}</span><span class="chip">${plural(seeds, "seed")}</span><span class="chip">${T.experience} experience · ${T.similar} similar · ${T.transfer} transfer tasks</span><span class="chip">${plural(s.totals.traces, "trace")}</span><span class="chip">${plural(s.totals.spans, "span")}</span><span class="chip">${plural(s.totals.lessons, "lesson")} stored</span></div>`)
  + section("Summary of results", "Plain-language findings, generated from this run's data.")
  + `<div class="grid">${card("c8", "gate1", "Findings", "Every figure below is clickable", `<div class="findings" id="findings"></div>`, "findingsCard").replace(/<h3>.*?<\/h3>/, `<h3>Findings</h3>`)}${card("c4", "gate1", "Promotion gates", "Pass / fail criteria for this run", `<div id="gates"></div>`)}</div>`
  + section("Key measures", "Lucifer compared with the baseline on tasks the agent has not seen.")
  + `<div class="grid">
    ${kpi("first_attempt_success", "First-attempt success", pct(ref.pass_primary), has ? `${dlt(L.pass_primary, B.pass_primary, "pts")} vs baseline ${pct(B.pass_primary)}` : "single condition", { title: "First-attempt success · similar + transfer", tip: `${pct(ref.pass_primary, 1)} of new related tasks passed on the first try`, lead: `${pct(ref.pass_primary, 1)} of the new, related tasks were solved on the first attempt${L ? " by Lucifer" : ""}.`, rows: rowsOf(["Tasks (similar + transfer)", T.primary], ["Seeds", seeds], L && ["Lucifer", pct(L.pass_primary, 1)], B && ["Baseline", pct(B.pass_primary, 1)], has && ["Difference", pts(L.pass_primary - B.pass_primary, 1)]), related: ["first_attempt_success", "interval95", "task_level"] })}
    ${kpi("replay_success", "Replay success", pct(ref.pass_replay), has ? `${dlt(L.pass_replay, B.pass_replay, "pts")} vs baseline ${pct(B.pass_replay)}` : "", { title: "Replay success", tip: `${pct(ref.pass_replay, 1)} of previously seen tasks passed on the first try`, lead: `${pct(ref.pass_replay, 1)} of the tasks seen during experience were solved first try when repeated.`, rows: rowsOf(["Tasks (replay)", T.replay], L && ["Lucifer", pct(L.pass_replay, 1)], B && ["Baseline", pct(B.pass_replay, 1)]), related: ["replay_success", "replay"] })}
    ${kpi("avg_solve_time", "Average time per task", fmtMs(ref.avg_solve_ms), has ? `${dlt(L.avg_solve_ms, B.avg_solve_ms, "ms", "down")} vs baseline ${fmtMs(B.avg_solve_ms)}` : "", { title: "Average time per task", tip: `Mean duration of a whole solve: ${fmtMs(ref.avg_solve_ms)}`, lead: s.simulated ? "In this simulated run the model latency is invented, so treat the time as illustrative." : "Mean duration of the root span of each trace.", rows: rowsOf(["Solves averaged", ref.solves], L && ["Lucifer", fmtMs(L.avg_solve_ms)], B && ["Baseline", fmtMs(B.avg_solve_ms)]), related: ["avg_solve_time", "trace", "simulated"] })}
    ${kpi("tokens_per_task", "Tokens per task", Math.round(ref.avg_tokens).toLocaleString(), has ? `${dlt(L.avg_tokens, B.avg_tokens, "tok", "down")} vs baseline ${Math.round(B.avg_tokens).toLocaleString()}` : "", { title: "Tokens per task", tip: `${Math.round(ref.avg_tokens).toLocaleString()} prompt + completion tokens per solve`, lead: "Memory costs tokens because lessons are added to the prompt.", rows: rowsOf(L && ["Lucifer", Math.round(L.avg_tokens).toLocaleString()], B && ["Baseline", Math.round(B.avg_tokens).toLocaleString()], s.conditions.includes("irrelevant") && ["Control", Math.round(k.irrelevant.avg_tokens).toLocaleString()]), related: ["tokens_per_task", "prompt_tokens"] })}
  </div>`
  + section("Performance", "How often each condition solved tasks on the first attempt, by phase and by task family.")
  + `<div class="grid">${card("c7", "first_attempt_success", "First-attempt success by phase", "The experience phase is where memory is written; the other three phases are run with memory frozen", `${legend(C)}<div id="ch-bars"></div>`)}${card("c5", "radar", "Success by task family", "Evaluation phases only", `<div id="ch-radar"></div>`)}</div>`
  + section("Learning and outcomes", "What happened while the agent learned, how each solve ended, and how well memory retrieval worked.")
  + `<div class="grid">${card("c5", "learning_curve", "Learning curve", "Running average of first-attempt success during the experience phase", `${legend(C)}<div id="ch-curve"></div>`)}${card("c3", "outcomes", "Outcomes", "", `<div class="sub" id="outcomeSub" style="margin-bottom:6px"></div><div id="ch-donut"></div><div class="legend" id="donutLegend" style="justify-content:center;margin-top:8px"></div>`)}${card("c4", "retrieval_precision", "Retrieval quality", "Are the lessons shown relevant to the task?", `<div id="retrieval"></div>`)}</div>`
  + section("Processing", "Where the time goes inside a task solve. Every row is built from the recorded spans.")
  + `<div class="grid">${card("c5", "span", "Time per processing step", "Mean time per step, for each condition", `<div id="ch-stack"></div><div class="legend" id="stackLegend" style="margin-top:8px"></div>`)}${card("c7", "operations", "Operations", "Duration statistics for each type of step", `<div id="ops"></div>`)}</div>`
  + section("Task analysis", "Results by phase, and the tasks that were hardest to solve on the first try.")
  + `<div class="grid">${card("c7", "similar", "Results by phase", "First-attempt success and number of tasks", `<div id="phases"></div>`)}${card("c5", "hardest", "Tasks with the highest failure rate", "First-attempt failures across all conditions", `<div id="hard"></div>`)}</div>`;

  view.querySelectorAll(".legend button[data-c]").forEach((b) => (b.onclick = () => { state.hidden.has(b.dataset.c) ? state.hidden.delete(b.dataset.c) : state.hidden.add(b.dataset.c); overview(); }));
  findingsCard(s); gatesCard(s);
  const nTasks = (ph) => ({ experience: T.experience, similar: T.similar, transfer: T.transfer, replay: T.replay })[ph];
  $("#ch-bars").append(groupedBars({ categories: s.phase_bars.map((p) => ({ label: p.phase, values: p })), keys: vis, label: "First-attempt success by phase", explain: (cat, key, v) => ({ title: `${NAMES[key]} · ${cat.label}`, tip: `${pct(v, 1)} first-attempt success`, lead: `${pct(v, 1)} of ${cat.label} tasks were solved on the first attempt.`, rows: [["Tasks in phase", nTasks(cat.label)], ["Seeds", seeds], ["Solves", plural(nTasks(cat.label) * seeds, "solve")], ["Success", pct(v, 1)]], read: cat.label === "experience" ? "This is the learning phase; it is not used for the main comparison." : "Compare the bars within this phase: the higher the bar, the more tasks solved first try.", related: [cat.label, key] }) }));
  $("#ch-radar").append(radar({ axes: s.radar.axes, series: vis.map((c) => ({ key: c, values: s.radar[c] })), explain: (axis, key, v) => ({ title: `${NAMES[key]} · ${axis} tasks`, tip: `${pct(v, 1)} first-attempt success`, lead: `${pct(v, 1)} first-attempt success on ${axis} tasks (similar, transfer and replay phases).`, rows: [["Tasks in family", s.radar_n[axis]], ["Seeds", seeds]], related: ["task_family", "radar", key] }) }));
  $("#ch-curve").append(lines({ series: vis.map((c) => ({ key: c, points: s.curve[c].map((p) => ({ x: p.position, y: p.pass, raw: p.raw })) })), xLabel: "Number of experience tasks completed", explain: (key, p) => ({ title: `${NAMES[key]} · after ${p.x} tasks`, tip: `${pct(p.y, 1)} running first-attempt success`, lead: `After ${p.x} experience tasks the running first-attempt success is ${pct(p.y, 1)}.`, rows: [["Running average", pct(p.y, 1)], ["Task number " + p.x + " alone", pct(p.raw ?? p.y, 1)], ["Seeds", seeds]], related: ["learning_curve", "experience"] }) }));
  donutCard(s, state.donutCond && C.includes(state.donutCond) ? state.donutCond : (vis[0] || C[0])); retrievalCard(s); stackCard(s, vis); opsCard(s); phasesCard(s); hardCard(s);
}

function findingsCard(s) {
  const host = $("#findings"), k = s.kpis, L = k.lucifer, B = k.baseline, g = s.gates, T = s.tasks, ev = (o) => val(o.text, explainer(o.x)), out = [];
  const mk = (cls, sym, html) => `<div class="finding"><span class="mark ${cls}">${sym}</span><p>${html}</p></div>`;
  if (s.simulated) out.push(mk("warn", "!", `<b>This is a simulated run.</b> The agent is a stand-in with known behaviour, used to check that the measuring system works. These results say nothing about any real model. See ${term("simulated")}.`));
  if (g && L && B) {
    const g1 = g.gate1_improvement, [d, lo, hi] = g1.lucifer_minus_baseline, [d2, lo2, hi2] = g1.lucifer_minus_irrelevant;
    const base = ev({ text: pct(B.pass_primary), x: { title: "Baseline first-attempt success", tip: pct(B.pass_primary, 1), lead: `The baseline solved ${pct(B.pass_primary, 1)} of new tasks first try.`, rows: [["Tasks", T.primary], ["Seeds", s.totals.seeds]], related: ["baseline", "first_attempt_success"] } });
    const luc = ev({ text: pct(L.pass_primary), x: { title: "Lucifer first-attempt success", tip: pct(L.pass_primary, 1), lead: `Lucifer solved ${pct(L.pass_primary, 1)} of new tasks first try.`, rows: [["Tasks", T.primary], ["Seeds", s.totals.seeds]], related: ["lucifer", "first_attempt_success"] } });
    const iv1 = ev({ text: `${pts(lo)} to ${pts(hi)}`, x: { title: "95% interval · Lucifer − baseline", tip: `${pts(lo, 1)} to ${pts(hi, 1)}`, lead: "The range in which the true improvement over the baseline very likely lies.", rows: [["Estimate", pts(d, 1)], ["Lower bound", pts(lo, 1)], ["Upper bound", pts(hi, 1)]], read: lo > 0 ? "The whole range is above zero, so the improvement is unlikely to be chance." : hi < 0 ? "The whole range is below zero." : "The range includes zero, so the data cannot separate Lucifer from the baseline.", related: ["interval95", "paired_bootstrap"] } });
    const iv2 = ev({ text: `${pts(lo2)} to ${pts(hi2)}`, x: { title: "95% interval · Lucifer − control", tip: `${pts(lo2, 1)} to ${pts(hi2, 1)}`, lead: "The range in which the true improvement over the irrelevant-notes control lies.", rows: [["Estimate", pts(d2, 1)], ["Lower bound", pts(lo2, 1)], ["Upper bound", pts(hi2, 1)]], read: "This comparison shows whether the gain comes from relevant knowledge rather than from a longer prompt.", related: ["irrelevant", "interval95"] } });
    if (g1.verdict === "improves") out.push(mk("ok", "✓", `<b>Improvement detected.</b> Lucifer solved ${luc} of new related tasks on the first attempt, compared with ${base} for the baseline (${pts(d)}; 95% interval ${iv1}). It also beat the irrelevant-notes control by ${pts(d2)} (interval ${iv2}), so the gain is not explained by a longer prompt.`));
    else if (g1.verdict === "hurts") out.push(mk("bad", "✕", `<b>Memory reduced performance.</b> Lucifer solved ${luc} of new related tasks first try against ${base} for the baseline (${pts(d)}; interval ${iv1}). The whole interval is below zero.`));
    else out.push(mk("info", "i", `<b>No improvement detected.</b> Lucifer solved ${luc} of new related tasks first try against ${base} for the baseline (${pts(d)}; interval ${iv1}), and ${pts(d2)} against the control (interval ${iv2}). At least one interval includes zero, so the data cannot separate the conditions. This is not proof that memory has no effect.`));
  }
  const n = T.primary, powerTxt = n < 20 ? "in about one in three attempts" : n < 40 ? "in about one in two attempts" : "in over 95% of attempts", powerCls = n < 40 ? "warn" : "ok";
  out.push(mk(powerCls, powerCls === "ok" ? "✓" : "!", `<b>Evidence strength.</b> The main comparison uses ${ev({ text: plural(n, "task"), x: { title: "Tasks in the main comparison", tip: `${n} similar + transfer tasks`, lead: `${T.similar} similar tasks and ${T.transfer} transfer tasks.`, read: "More tasks give narrower intervals and a better chance of detecting a real effect.", related: ["power", "similar", "transfer"] } })}. In simulation, a set this size detects a real +20 point effect ${powerTxt} (${term("power", "statistical power")}). ${n < 48 ? "More tasks are needed before a null result can be trusted." : "That is adequate for a firm conclusion either way."}`));
  if (g) {
    const g2 = g.gate2_retention, g3 = g.gate3_auditability;
    out.push(mk(g2.inconclusive ? "na" : g2.passed ? "ok" : "bad", g2.inconclusive ? "–" : g2.passed ? "✓" : "✕", g2.inconclusive ? `<b>Retention could not be assessed.</b> The baseline did not reliably solve any task (at least 80% of the time), so there were no ${term("mastered_tasks")} that learning could have damaged.` : `<b>Retention ${g2.passed ? "preserved" : "lost"}.</b> On ${g2.mastered_tasks} tasks the baseline already solves, Lucifer's average change was ${pts(-g2.mean_drop, 1)}.`));
    out.push(mk(g3.passed ? "ok" : "bad", g3.passed ? "✓" : "✕", `<b>Memory is auditable.</b> ${g3.runs_audited} memory stores were checked: ${g3.passed ? "each has an intact hash chain, restores exactly on rollback, and records where every lesson came from." : "at least one failed the integrity check."}`));
  }
  const R = s.retrieval.lucifer;
  if (R && R.precision != null) { const C2 = s.retrieval.irrelevant; out.push(mk(R.precision >= 0.8 ? "ok" : "warn", R.precision >= 0.8 ? "✓" : "!", `<b>Retrieval quality.</b> ${val(pct(R.precision), explainer({ title: "Retrieval precision · Lucifer", tip: `${pct(R.precision, 1)} of lessons shown were from the same task family`, lead: "Share of the lessons shown to the model that came from the same task family.", rows: [["Precision", pct(R.precision, 1)], ["Coverage", pct(R.coverage, 1)], ["Lessons per task", R.avg_shown.toFixed(2)], C2 && ["Control precision", pct(C2.precision, 1)]].filter(Boolean), related: ["retrieval_precision", "retrieval_coverage"] }))} of the lessons shown to Lucifer came from the same task family as the task${C2 ? ` (the control: ${pct(C2.precision)})` : ""}, covering ${pct(R.coverage)} of tasks. ${R.precision < 0.8 ? "Lessons from unrelated families are being retrieved; a semantic retriever would likely help." : ""}`)); }
  host.innerHTML = out.join("");
}
function gatesCard(s) {
  const g = s.gates, host = $("#gates");
  if (!g) { host.innerHTML = `<div class="empty">Gates need the baseline and Lucifer conditions in the same run.</div>`; return; }
  const g1 = g.gate1_improvement, g2 = g.gate2_retention, g3 = g.gate3_auditability, icon = (ok, na) => `<span class="icon ${na ? "na" : ok ? "pass" : "fail"}">${na ? "–" : ok ? "✓" : "✕"}</span>`;
  const iv = (t) => `${pts(t[0])} (${pts(t[1])} to ${pts(t[2])})`;
  host.innerHTML = `<div class="gate">${icon(g1.passed)}<div><b>${term("gate1", "1 · Improvement")} — ${esc(g1.verdict)}</b><small>vs baseline ${iv(g1.lucifer_minus_baseline)}</small><small>vs control ${iv(g1.lucifer_minus_irrelevant)}</small><div id="whisk"></div></div></div>
    <div class="gate">${icon(g2.passed, g2.inconclusive)}<div><b>${term("gate2", "2 · Retention")} — ${g2.inconclusive ? "inconclusive" : g2.passed ? "pass" : "fail"}</b><small>${g2.inconclusive ? "No task was mastered by the baseline" : `Mean drop ${(g2.mean_drop * 100).toFixed(1)} pts over ${g2.mastered_tasks} mastered tasks`}</small></div></div>
    <div class="gate">${icon(g3.passed)}<div><b>${term("gate3", "3 · Auditability")} — ${g3.passed ? "pass" : "fail"}</b><small>${g3.runs_audited} memory stores: hash chain, rollback, provenance</small></div></div>`;
  const item = (label, t) => ({ label, mean: t[0], lo: t[1], hi: t[2], explain: { title: label, tip: `${pts(t[0], 1)} (${pts(t[1], 1)} to ${pts(t[2], 1)})`, lead: `Estimated difference ${pts(t[0], 1)}, with a 95% interval from ${pts(t[1], 1)} to ${pts(t[2], 1)}.`, read: t[1] > 0 ? "Entirely above zero: a credible improvement." : t[2] < 0 ? "Entirely below zero: a credible decline." : "The interval includes zero.", related: ["interval95", "gate1"] } });
  $("#whisk").append(whisker({ domain: [-0.5, 0.75], items: [item("Lucifer − baseline", g1.lucifer_minus_baseline), item("Lucifer − control", g1.lucifer_minus_irrelevant)] }));
}
function donutCard(s, cond) {
  state.donutCond = cond; const o = s.outcomes[cond], total = o.first_try + o.fixed_on_retry + o.failed;
  $("#outcomeSub").innerHTML = `<select id="donutCond" aria-label="Condition" style="background:var(--soft);color:var(--ink);border:1px solid var(--line);border-radius:7px;padding:4px 6px">${s.conditions.map((c) => `<option value="${c}" ${c === cond ? "selected" : ""}>${esc(NAMES[c])}</option>`).join("")}</select>`;
  $("#donutCond").onchange = (e) => { state.donutCond = e.target.value; $("#ch-donut").innerHTML = ""; donutCard(s, e.target.value); };
  const seg = [{ label: "Passed first try", value: o.first_try, color: "var(--ok)" }, { label: "Fixed on the retry", value: o.fixed_on_retry, color: "var(--warn)" }, { label: "Failed after retry", value: o.failed, color: "var(--bad)" }];
  $("#ch-donut").innerHTML = ""; $("#ch-donut").append(donut({ segments: seg, centerTop: total.toLocaleString(), centerBottom: "tasks solved", explain: (sg, tot) => ({ title: `${NAMES[cond]} · ${sg.label}`, tip: `${sg.value} of ${tot} (${pct(sg.value / tot, 1)})`, lead: `${sg.value} of ${tot} solves ended this way.`, rows: [["Count", sg.value], ["Share", pct(sg.value / tot, 1)]], related: ["outcomes", cond] }) }));
  $("#donutLegend").innerHTML = seg.map((x) => `<span style="display:inline-flex;gap:6px;align-items:center"><span class="dot" style="background:${x.color}"></span>${x.label} ${x.value}</span>`).join("");
}
function retrievalCard(s) {
  const R = s.retrieval, host = $("#retrieval");
  if (!R.lucifer) { host.innerHTML = `<div class="empty">Retrieval is only used by the Lucifer and control conditions.</div>`; return; }
  const row = (c) => { const r = R[c]; if (!r) return ""; return `<div class="stat-row"><span>${esc(SHORT[c])} · ${term("retrieval_precision", "precision")}</span><b>${r.precision == null ? "–" : val(pct(r.precision), explainer({ title: `${NAMES[c]} · precision`, tip: `${pct(r.precision, 1)} of lessons shown were from the same family`, lead: "Share of shown lessons that came from the same task family as the task.", rows: [["Precision", pct(r.precision, 1)], ["Solves measured", r.solves]], related: ["retrieval_precision"] }))}</b></div><div class="stat-row"><span>${esc(SHORT[c])} · ${term("retrieval_coverage", "coverage")}</span><b>${r.coverage == null ? "–" : val(pct(r.coverage), explainer({ title: `${NAMES[c]} · coverage`, tip: `${pct(r.coverage, 1)} of tasks had at least one same-family lesson`, lead: "Share of tasks that were shown at least one lesson from their own family.", rows: [["Coverage", pct(r.coverage, 1)], ["Solves measured", r.solves]], related: ["retrieval_coverage"] }))}</b></div><div class="stat-row"><span>${esc(SHORT[c])} · lessons per task</span><b>${r.avg_shown.toFixed(2)}</b></div>`; };
  host.innerHTML = row("lucifer") + row("irrelevant") + `<div class="sub" style="margin-top:10px">The control should score near zero: it deliberately shows the least relevant lessons. Transfer tasks are excluded because they mix families.</div>`;
}
function stackCard(s, vis) {
  const parts = Object.keys(OP_COLORS);
  $("#ch-stack").append(stackedH({ rows: vis.map((c) => ({ label: SHORT[c], key: c, values: s.latency_stack[c] })), parts, colors: OP_COLORS, format: fmtMs, explain: (r, p, v, total) => ({ title: `${NAMES[r.key]} · ${p}`, tip: `${fmtMs(v)} on average`, lead: OP_INFO[p], rows: [["Mean time", fmtMs(v)], ["Share of the measured steps", pct(total ? v / total : 0, 1)], ["All steps together", fmtMs(total)]], related: ["span", "avg_solve_time"] }) }));
  $("#stackLegend").innerHTML = parts.map((p) => `<span style="display:inline-flex;gap:6px;align-items:center"><span class="dot" style="background:${OP_COLORS[p]}"></span>${p}</span>`).join("");
}
function opsCard(s) {
  const max = Math.max(...s.operations.map((o) => o.total_ms), 1);
  $("#ops").innerHTML = `<table><thead><tr><th>Operation</th><th class="num">Spans</th><th class="num">Mean</th><th class="num">${term("p50", "p50")}</th><th class="num">${term("p95", "p95")}</th><th class="num">Max</th><th class="num">Errors</th><th>Share of time</th></tr></thead><tbody>${s.operations.map((o) => { const id = explainer({ title: o.operation, tip: `${o.count.toLocaleString()} spans, mean ${fmtMs(o.mean_ms)}`, lead: OP_INFO[o.operation] ?? "", rows: [["Spans recorded", o.count.toLocaleString()], ["Mean", fmtMs(o.mean_ms)], ["Median (p50)", fmtMs(o.p50_ms)], ["95th percentile (p95)", fmtMs(o.p95_ms)], ["Slowest", fmtMs(o.max_ms)], ["Total time", fmtMs(o.total_ms)], ["Errors", o.errors]], read: o.errors ? "An error here means a test run failed or a task never passed; it is not a software fault." : "", related: ["operations", "p50", "p95"] }); return `<tr class="clickable" data-x="${id}" tabindex="0" role="button"><td><b>${esc(o.operation)}</b></td><td class="num">${o.count.toLocaleString()}</td><td class="num">${fmtMs(o.mean_ms)}</td><td class="num">${fmtMs(o.p50_ms)}</td><td class="num">${fmtMs(o.p95_ms)}</td><td class="num">${fmtMs(o.max_ms)}</td><td class="num">${o.errors ? `<span style="color:var(--bad)">${o.errors}</span>` : "0"}</td><td><div class="share"><i style="width:${(o.total_ms / max) * 100}%;background:${OP_COLORS[o.operation] || "var(--k-attempt)"}"></i></div></td></tr>`; }).join("")}</tbody></table><div class="sub" style="margin-top:10px">“solve” and “attempt” contain the steps listed above them, so their time overlaps. Click a row for what the step does.</div>`;
}
function phasesCard(s) {
  const C = s.conditions, T = s.tasks, nT = { experience: T.experience, similar: T.similar, transfer: T.transfer, replay: T.replay };
  $("#phases").innerHTML = `<table><thead><tr><th>Phase</th><th class="num">Tasks</th>${C.map((c) => `<th class="num"><span class="dot" style="background:var(--${c});margin-right:6px"></span>${SHORT[c]}</th>`).join("")}</tr></thead><tbody>${s.phase_bars.map((p) => `<tr><td>${term(p.phase)}</td><td class="num">${nT[p.phase]}</td>${C.map((c) => `<td class="num">${val(pct(p[c], 1), explainer({ title: `${NAMES[c]} · ${p.phase}`, tip: `${pct(p[c], 1)} first-attempt success`, lead: `${pct(p[c], 1)} of ${p.phase} tasks solved on the first attempt.`, rows: [["Tasks", nT[p.phase]], ["Seeds", s.totals.seeds]], related: [p.phase, c] }))}</td>`).join("")}</tr>`).join("")}</tbody></table>`;
}
function hardCard(s) {
  $("#hard").innerHTML = `<ul class="rank">${s.hardest.map((h) => `<li data-x="${explainer({ title: h.task_id, tip: `${pct(h.first_try_fail)} first-attempt failures`, lead: `${pct(h.first_try_fail, 1)} of first attempts at this task failed.`, rows: [["Family", h.family], ["Solves", h.solves], ["Average attempts", h.avg_attempts.toFixed(2)]], read: h.first_try_fail > 0.95 ? "A task that nearly always fails may be too hard or may have an unclear specification." : "", related: ["hardest", "task_family"] })}" tabindex="0" role="button"><span class="avatar">${esc(h.family.slice(0, 3).toUpperCase())}</span><div class="grow"><div class="name">${esc(h.task_id)}</div><small>${plural(h.solves, "solve")} · ${h.avg_attempts.toFixed(2)} attempts on average</small></div><b style="color:${h.first_try_fail > 0.5 ? "var(--bad)" : "var(--warn)"}">${pct(h.first_try_fail)}</b></li>`).join("")}</ul>`;
}

// ---------- traces ----------
async function loadTraces() {
  const f = state.tf, p = new URLSearchParams({ limit: "250" });
  if (f.condition) p.set("condition", f.condition); if (f.phase) p.set("phase", f.phase); if (f.seed !== "") p.set("seed", f.seed); if (f.q) p.set("q", f.q); if (f.failed) p.set("failed", "1");
  state.traces = await api(`/api/runs/${encodeURIComponent(state.runId)}/traces?${p}`);
}
async function openTrace(id) {
  state.traceId = id;
  state.spans = (await api(`/api/runs/${encodeURIComponent(state.runId)}/traces/${id.split("/").map(encodeURIComponent).join("/")}`)).spans;
  state.spanId = state.spans[0]?.span_id; renderTraceDetail();
  document.querySelectorAll(".titem").forEach((n) => n.classList.toggle("sel", n.dataset.id === id));
}
async function tracesView() {
  const s = state.summary;
  if (!s.totals.spans) { view.innerHTML = pagehead("Traces", "") + `<div class="card empty"><h3>No traces in this run</h3><p>It was saved before tracing was added. Run the experiment again to record every step.</p></div>`; return; }
  if (!state.traces) await loadTraces();
  const f = state.tf, seeds = Array.from({ length: s.totals.seeds }, (_, i) => i);
  view.innerHTML = pagehead("Traces", `Every task solve is recorded as a ${term("trace")}: the ordered, timed steps (${term("span", "spans")}) that produced the result. Select a trace to see its timeline; select a step to read exactly what it received and produced.`)
  + `<div class="traces"><div class="card"><header class="ch"><div><h3>Task solves${infoBtn("trace")}</h3><div class="sub">${state.traces.total.toLocaleString()} match the filters${state.traces.total > 250 ? " (first 250 shown)" : ""}</div></div></header>
    <div class="filters"><input type="search" id="fq" aria-label="Search" placeholder="Search by task or family" value="${esc(f.q)}">
      <select id="fc" aria-label="Condition"><option value="">All conditions</option>${s.conditions.map((c) => `<option value="${c}" ${f.condition === c ? "selected" : ""}>${esc(SHORT[c])}</option>`).join("")}</select>
      <select id="fp" aria-label="Phase"><option value="">All phases</option>${["experience", "similar", "transfer", "replay"].map((p) => `<option ${f.phase === p ? "selected" : ""}>${p}</option>`).join("")}</select>
      <select id="fs" aria-label="Seed"><option value="">All seeds</option>${seeds.map((x) => `<option value="${x}" ${String(f.seed) === String(x) ? "selected" : ""}>seed ${x}</option>`).join("")}</select>
      <label><input type="checkbox" id="ff" ${f.failed ? "checked" : ""}> first attempt failed</label></div>
    <div class="kinds"><span class="chip"><span class="status"></span>first try</span><span class="chip"><span class="status retry"></span>fixed on retry</span><span class="chip"><span class="status fail"></span>failed</span></div>
    <div class="tlist" id="tlist">${state.traces.items.map((t) => `<div class="titem ${t.trace_id === state.traceId ? "sel" : ""}" data-id="${esc(t.trace_id)}" tabindex="0"><span class="status ${t.pass_at_1 ? "" : t.pass_at_2 ? "retry" : "fail"}"></span><div><b>${esc(t.task_id)}</b><div class="meta">${esc(SHORT[t.condition])} · seed ${t.seed} · ${t.phase}${t.lessons_shown ? ` · ${plural(t.lessons_shown, "lesson")} shown` : ""}</div></div><span class="dur">${fmtMs(t.duration_ms)}</span></div>`).join("") || `<div class="empty">No traces match these filters.</div>`}</div></div>
    <div class="card" id="detail"><div class="empty">Select a trace on the left.</div></div></div>`;
  const reload = async () => { await loadTraces(); tracesView(); };
  $("#fq").onchange = (e) => { f.q = e.target.value; reload(); }; $("#fc").onchange = (e) => { f.condition = e.target.value; reload(); }; $("#fp").onchange = (e) => { f.phase = e.target.value; reload(); };
  $("#fs").onchange = (e) => { f.seed = e.target.value; reload(); }; $("#ff").onchange = (e) => { f.failed = e.target.checked; reload(); };
  $("#tlist").onclick = (e) => { const n = e.target.closest(".titem"); if (n) openTrace(n.dataset.id); };
  $("#tlist").onkeydown = (e) => { if (e.key === "Enter") e.target.closest(".titem")?.click(); };
  if (state.traceId && state.spans) renderTraceDetail(); else if (state.traces.items[0]) openTrace(state.traces.items[0].trace_id);
}
function flowOf(spans) {
  const step = (label, cls = "") => `<span class="step ${cls}">${label}</span>`, out = [];
  for (const sp of spans) {
    if (sp.kind === "retrieval") out.push(step(`Retrieve memory · ${plural(sp.attrs.lessons_shown?.length ?? 0, "lesson")}`));
    else if (sp.kind === "prompt") out.push(step("Build prompt"));
    else if (sp.kind === "attempt") out.push(step(`Attempt ${sp.attrs.attempt}: ${sp.attrs.passed ? "passed" : "failed"}`, sp.attrs.passed ? "good" : "err"));
    else if (sp.kind === "memory") out.push(step(`Write memory · ${plural(sp.attrs.lessons_written?.length ?? 0, "lesson")}`));
  }
  return out.join(`<span class="arrow">→</span>`);
}
function renderTraceDetail() {
  const spans = state.spans, host = $("#detail"); if (!spans || !host) return;
  const root = spans[0], total = root.duration_ms || 1, depth = {}; spans.forEach((sp) => (depth[sp.span_id] = sp.parent_id ? (depth[sp.parent_id] ?? 0) + 1 : 0));
  const A = root.attrs, kinds = [...new Set(spans.map((s) => s.kind))];
  host.innerHTML = `<header class="ch"><div><h3>${esc(root.name)} <span class="chip ${A.pass_at_1 ? "ok" : A.pass_at_2 ? "warn" : "bad"}">${A.pass_at_1 ? "Passed first try" : A.pass_at_2 ? "Fixed on retry" : "Failed"}</span></h3><div class="sub">${esc(NAMES[A.condition])} · seed ${A.seed} · ${term(A.phase)} · ${term("task_family", esc(A.family))} family · ${plural(spans.length, "span")} · ${fmtMs(total)} in total${spans.some((s) => s.attrs.simulated) ? ` · ${term("simulated", "simulated model latency")}` : ""}</div></div></header>
    <div class="flow">${flowOf(spans)}</div>
    <div class="kinds">${kinds.map((k) => `<span class="swatch" style="display:inline-flex;align-items:center;gap:6px"><span class="dot" style="background:${KIND_COLORS[k]}"></span>${term(KIND_DEFS[k], KIND_LABEL[k])}</span>`).join("")}</div>
    <div class="wf-head"><span>Step</span><span>Timeline</span><span style="text-align:right">Duration</span></div>
    <div class="wf">${spans.map((sp) => `<div class="wf-row ${sp.span_id === state.spanId ? "sel" : ""}" data-id="${esc(sp.span_id)}" tabindex="0"><div class="wf-name" style="padding-left:${depth[sp.span_id] * 16}px"><i>${depth[sp.span_id] ? "└" : "▸"}</i>${esc(sp.name)}</div><div class="wf-track"><div class="wf-bar ${sp.status === "error" ? "error" : ""}" data-sid="${esc(sp.span_id)}" style="left:${(sp.start_ms / total) * 100}%;width:${Math.max((sp.duration_ms / total) * 100, 0.4)}%;background:${KIND_COLORS[sp.kind]}"></div></div><div class="wf-dur">${fmtMs(sp.duration_ms)}</div></div>`).join("")}</div>
    <div class="axis"><span></span><span class="ticks">${[0, 0.25, 0.5, 0.75, 1].map((t) => `<span>${fmtMs(total * t)}</span>`).join("")}</span><span></span></div>
    <div class="attrs" id="attrs"></div>`;
  host.querySelectorAll(".wf-row").forEach((r) => { r.onclick = () => { state.spanId = r.dataset.id; renderTraceDetail(); }; r.onkeydown = (e) => { if (e.key === "Enter") r.click(); }; });
  host.querySelectorAll(".wf-bar").forEach((b) => { const sp = spans.find((x) => x.span_id === b.dataset.sid); attachExplain(b, { title: `${sp.name} (${KIND_LABEL[sp.kind]})`, tip: `${fmtMs(sp.duration_ms)}, starts at ${fmtMs(sp.start_ms)}${sp.status === "error" ? " · failed" : ""}`, lead: `${KIND_LABEL[sp.kind]} step: ${sp.status === "error" ? "ended in an error (a failed test or a task that never passed)" : "completed normally"}.`, rows: [["Starts at", fmtMs(sp.start_ms)], ["Duration", fmtMs(sp.duration_ms)], ["Share of the solve", pct(sp.duration_ms / total, 1)]], related: [KIND_DEFS[sp.kind], "span"] }); });
  renderAttrs(spans.find((s) => s.span_id === state.spanId) || root);
}
function renderAttrs(sp) {
  const a = sp.attrs, big = ["prompt", "reply", "code", "feedback"], skip = new Set([...big, "lessons_shown", "lessons_written"]);
  const kv = Object.entries(a).filter(([k]) => !skip.has(k)).map(([k, v]) => `<dt>${ATTR_TERMS[k] ? term(ATTR_TERMS[k], esc(k)) : esc(k)}</dt><dd>${typeof v === "boolean" ? `<span class="chip ${v ? "ok" : "bad"}">${v}</span>` : esc(typeof v === "object" ? JSON.stringify(v) : v)}</dd>`).join("");
  const lessons = (title, list) => (list?.length ? `<h4>${title}</h4>${list.map((l) => `<div class="lesson ${l.kind}"><div class="head"><span class="chip">${esc(l.kind)}</span><span>version ${l.version}</span><span>from ${esc(l.task_id ?? "this task")}</span>${l.hash ? `<span class="hash">#${esc(l.hash)}</span>` : ""}</div><p>${esc(l.text)}</p></div>`).join("")}` : "");
  const label = { prompt: "Prompt sent to the model", reply: "Model reply", code: "Code that was tested", feedback: "Test feedback returned" };
  $("#attrs").innerHTML = `<h4>${esc(sp.name)} · ${sp.status === "error" ? "ended in an error" : "completed"} · starts at ${fmtMs(sp.start_ms)} · ${fmtMs(sp.duration_ms)}</h4><dl class="kv"><dt>type</dt><dd>${term(KIND_DEFS[sp.kind], KIND_LABEL[sp.kind])}</dd>${kv}</dl>
    ${lessons("Lessons shown to the model", a.lessons_shown)}${lessons("Lessons written to memory", a.lessons_written)}${big.filter((k) => a[k]).map((k) => `<h4>${label[k]}</h4><pre class="code">${esc(a[k])}</pre>`).join("")}`;
}

// ---------- memory ----------
async function memoryView() {
  const s = state.summary, m = state.mem, conds = s.conditions.filter((c) => c !== "baseline");
  if (!conds.length) { view.innerHTML = pagehead("Memory", "") + `<div class="card empty">This run has no memory conditions.</div>`; return; }
  if (!conds.includes(m.condition)) m.condition = conds[0];
  if (!m.data) m.data = await api(`/api/runs/${encodeURIComponent(state.runId)}/memory?condition=${m.condition}&seed=${m.seed}`);
  const store = m.data[0], seeds = Array.from({ length: s.totals.seeds }, (_, i) => i), L = store?.lessons ?? [];
  view.innerHTML = pagehead("Memory", `What the agent wrote down during the ${term("experience")} phase. Each ${term("lesson")} is linked to the previous one by a ${term("hash_chain", "hash")}, so any change to history is detectable. Each lesson records its ${term("provenance")}.`)
  + `<div class="card"><header class="ch"><div><h3>${term("memory_store")}${infoBtn("memory_store")}</h3><div class="sub">Lessons are shown oldest first, as they were written</div></div></header>
    <div class="mem-controls"><select id="mc" aria-label="Condition">${conds.map((c) => `<option value="${c}" ${m.condition === c ? "selected" : ""}>${esc(NAMES[c])}</option>`).join("")}</select>
    <select id="ms" aria-label="Seed">${seeds.map((x) => `<option value="${x}" ${String(m.seed) === String(x) ? "selected" : ""}>seed ${x}</option>`).join("")}</select>
    <span class="chip">${plural(L.length, "lesson")}</span><span class="chip bad">${L.filter((l) => l.kind === "failure").length} failure notes</span><span class="chip ok">${L.filter((l) => l.kind === "fix").length} fixes</span></div>
    ${L.length ? `<div class="chain">${L.map((l) => `<div class="lesson ${l.kind}"><div class="head"><span class="chip ${l.kind === "fix" ? "ok" : "bad"}">${l.kind === "fix" ? "fix" : "failure"}</span><b>version ${l.version}</b><span>task ${esc(l.task_id)}</span><span>seed ${l.seed}</span><span class="hash" title="${esc(l.hash)}">#${esc(l.hash.slice(0, 12))}</span></div><p>${esc(l.text)}</p></div>`).join("")}</div>` : `<div class="empty">No lessons were written: the agent never failed during the experience phase.</div>`}</div>`;
  const reload = () => { m.data = null; memoryView(); };
  $("#mc").onchange = (e) => { m.condition = e.target.value; reload(); }; $("#ms").onchange = (e) => { m.seed = e.target.value; reload(); };
}

// ---------- guide ----------
function guideView() {
  const sw = (c, label) => `<span class="swatch"><i style="background:${c}"></i>${label}</span>`;
  const q = state.gloss.toLowerCase(), items = Object.entries(G).filter(([k, g]) => !q || (g.name + " " + g.short).toLowerCase().includes(q));
  view.innerHTML = pagehead("Guide", "How to read this dashboard, what each measure means, and the limits of what it can show.")
  + `<div class="guide"><nav class="toc"><a href="#g-purpose">Purpose</a><a href="#g-run">How a run works</a><a href="#g-cond">Conditions</a><a href="#g-phase">Phases</a><a href="#g-measure">Measures</a><a href="#g-gates">Gates</a><a href="#g-trace">Reading a trace</a><a href="#g-colour">Colour key</a><a href="#g-limits">Limitations</a><a href="#g-gloss">Glossary</a></nav>
  <div class="prose card">
    <h2 id="g-purpose">Purpose</h2><p>Lucifer tests one claim: an ordinary language model that keeps notes on its own earlier failures will solve <i>later, related</i> tasks more often than the same model without notes. This dashboard shows whether the evidence supports the claim, and lets you inspect every step behind each number.</p>
    <h2 id="g-run">How a run works</h2><ol><li>A set of small programming tasks, each with hidden tests, is prepared. Tasks are grouped into families that share one kind of pitfall.</li><li>For each ${term("seed", "seed")} and each condition the agent works through the ${term("experience", "experience")} tasks. After a failure, Lucifer and the control write a ${term("lesson", "lesson")}.</li><li>Memory is then ${term("frozen_memory", "frozen")} and the agent solves ${term("similar", "similar")}, ${term("transfer", "transfer")} and ${term("replay", "replay")} tasks. Lucifer is shown the most relevant lessons; the control is shown irrelevant ones.</li><li>Every solve is recorded as a ${term("trace", "trace")} of timed ${term("span", "spans")}. All figures are computed from these records.</li></ol>
    <h2 id="g-cond">Conditions</h2><p>All three use the same model, prompts and retry rule.</p><div class="swatches">${sw("var(--baseline)", term("baseline"))}${sw("var(--lucifer)", term("lucifer"))}${sw("var(--irrelevant)", term("irrelevant"))}</div><p>Lucifer is credible only if it beats both the baseline and the control.</p>
    <h2 id="g-phase">Phases</h2><p>${term("experience")} is for learning. ${term("similar")} and ${term("transfer", "transfer")} are the main measure. ${term("replay")} checks retention.</p>
    <h2 id="g-measure">Measures</h2><p>The primary measure is ${term("first_attempt_success", "first-attempt success")} on similar and transfer tasks. Secondary measures: ${term("pass_at_2", "success within two attempts")}, ${term("replay_success", "replay success")}, ${term("tokens_per_task", "tokens per task")}, ${term("avg_solve_time", "average time per task")} and ${term("retrieval_precision", "retrieval precision")}. Differences are reported with a ${term("interval95", "95% interval")}, because a point estimate alone cannot show whether a difference is real.</p>
    <h2 id="g-gates">Gates</h2><p>${term("gate1")} requires a credible improvement over both baseline and control. ${term("gate2")} requires that learning does not damage tasks already solved. ${term("gate3")} requires tamper-evident, reversible memory.</p>
    <h2 id="g-trace">Reading a trace</h2><p>Open the Traces tab. The waterfall shows each step's start and duration on a clock local to the trace. Steps are nested: an attempt contains its model call and test run. A red outline marks a failed step. Select a step to read its prompt, reply, code, test feedback and the lessons involved.</p><div class="swatches">${["root", "retrieval", "prompt", "attempt", "llm", "execution", "memory"].map((k) => sw(KIND_COLORS[k], term(KIND_DEFS[k], KIND_LABEL[k]))).join("")}</div>
    <h2 id="g-colour">Colour key</h2><p>Colours carry one meaning each.</p><div class="swatches">${sw("var(--baseline)", "Baseline")}${sw("var(--lucifer)", "Lucifer")}${sw("var(--irrelevant)", "Control")}${sw("var(--ok)", "Success / pass")}${sw("var(--warn)", "Caution / fixed on retry")}${sw("var(--bad)", "Failure / fail")}</div>
    <h2 id="g-limits">Limitations</h2><ul><li>Few tasks give wide intervals; a null result on a small task set is weak evidence. See ${term("power", "statistical power")}.</li><li>Simulated runs only verify the measuring system.</li><li>Retrieval is word-based and can retrieve lessons from the wrong family.</li><li>Code written by the model is run in a ${term("sandbox", "sandbox")} that is not a hardened security boundary.</li><li>Hosted models can change under the same name; results are tied to the date of the run.</li></ul>
    <h2 id="g-gloss">Glossary</h2><input class="searchbox" id="gsearch" type="search" placeholder="Search terms" aria-label="Search the glossary" value="${esc(state.gloss)}"><div class="gloss">${items.map(([k, g]) => `<button type="button" data-term="${k}"><b>${esc(g.name)}</b><span>${esc(g.short)}</span></button>`).join("") || `<div class="empty">No matching terms.</div>`}</div>
  </div></div>`;
  const input = $("#gsearch"); input.oninput = (e) => { state.gloss = e.target.value; const pos = e.target.selectionStart; guideView(); const i2 = $("#gsearch"); i2.focus(); i2.setSelectionRange(pos, pos); };
}

boot().catch((e) => { view.innerHTML = `<div class="card empty"><h3>Could not load</h3><p>${esc(e.message)}</p></div>`; });
