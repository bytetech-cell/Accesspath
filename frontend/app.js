
/* ACCESSPATH dashboard — React 18 + htm (no build step needed). */
const { useState, useEffect, useCallback } = React;
const html = htm.bind(React.createElement);

const api = async (path, opts = {}) => {
  const r = await fetch(path, { headers: { "Content-Type": "application/json" }, ...opts });
  if (!r.ok) throw new Error((await r.json().catch(() => ({}))).detail || r.statusText);
  return r.json();
};
const ev = (src) => (src && (src.startsWith("data:") || src.startsWith("/")) ? src : "/" + src);
const CONDS = [["keyboard", "⌨️ Keyboard"], ["screen_reader", "🔊 Screen reader"], ["mobile", "📱 Mobile"]];
const COND_LABEL = { keyboard: "Keyboard", screen_reader: "Screen reader", mobile: "Mobile", general: "General" };

/* ---------------------------------------------------------------- form */
function NewAudit({ onCreated, health }) {
  const [url, setUrl] = useState("");
  const [task, setTask] = useState("");
  const [steps, setSteps] = useState("");
  const [cond, setCond] = useState({ keyboard: true, screen_reader: true, mobile: true });
  const [useTf, setUseTf] = useState(true);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const [code, setCode] = useState(() => { try { return localStorage.getItem("ap_code") || ""; } catch (e) { return ""; } });
  const saveCode = (v) => { setCode(v); window.__apCode = v; try { localStorage.setItem("ap_code", v); } catch (e) {} };
  window.__apCode = code;

  const submit = async (e) => {
    e.preventDefault(); setBusy(true); setErr("");
    try {
      const a = await api("/api/audits", { method: "POST",
        body: JSON.stringify({ url, task, steps, conditions: cond, use_tinyfish: useTf, access_code: code }) });
      onCreated(a.id);
    } catch (ex) { setErr(ex.message); }
    setBusy(false);
  };

  return html`
    <form className="card" onSubmit=${submit} aria-labelledby="newh">
      <h2 id="newh">New audit</h2>
      <p className="sub">Step 1 — enter a website and the task a real user wants to finish.</p>
      <label className="f" htmlFor="url">Website URL</label>
      <input id="url" className="t" required value=${url} onInput=${(e) => setUrl(e.target.value)} placeholder="https://your-site.com" />
      <label className="f" htmlFor="task">User task</label>
      <textarea id="task" className="t" required value=${task} onInput=${(e) => setTask(e.target.value)}
        placeholder="Add the wireless headphones to the cart and reach checkout"></textarea>
      <label className="f" htmlFor="steps">Journey steps <span className="muted" style=${{ textTransform: "none", letterSpacing: 0 }}>(optional — TinyFish can find them)</span></label>
      <input id="steps" className="t" value=${steps} onInput=${(e) => setSteps(e.target.value)} placeholder="Products > Add to Cart > Cart > Checkout" />
      <label className="f" id="condl">Conditions</label>
      <div className="chips" role="group" aria-labelledby="condl">
        ${CONDS.map(([k, l]) => html`<button type="button" key=${k} className="chip" aria-pressed=${cond[k]}
            onClick=${() => setCond({ ...cond, [k]: !cond[k] })}>${l}</button>`)}
      </div>
      <label className="toggle"><input type="checkbox" checked=${useTf} onChange=${(e) => setUseTf(e.target.checked)} />
        Use TinyFish agent (smarter, slower). Off = fast local agent ${false ? html`<span className="tag unknown">no key</span>` : ""}</label>
      ${health && health.access_required && html`<div>
        <label className="f" htmlFor="code">Access code</label>
        <input id="code" className="t" type="password" value=${code} onInput=${(e) => saveCode(e.target.value)} placeholder="Ask the team for the code" />
      </div>`}
      <button className="btn" disabled=${busy}>${busy ? "Starting…" : "Run audit →"}</button>
      ${err && html`<div className="err" role="alert">${err}</div>`}
    </form>`;
}

/* ---------------------------------------------------------------- workflow */
function Workflow({ progress }) {
  return html`<div className="flow" aria-label="Audit workflow">
    ${(progress || []).map((p) => html`<div key=${p.n} className=${"stepbox " + p.status}>
      <div><span className="n">${p.n}</span><span className="ti">${p.title}</span></div>
      <div className="st">${p.subtitle} · <i>${p.status}</i></div>
      ${p.detail && html`<div className="d">${p.detail}</div>`}
      ${p.data && p.data.streaming_url && html`<div className="d"><a href=${p.data.streaming_url} target="_blank" rel="noopener">▶ Watch TinyFish live</a></div>`}
    </div>`)}
  </div>`;
}

/* 3D audit line (isometric machine figure, built by workflow3d/build.mjs). It only reads the
   audit object; if the script is missing the dashboard works exactly as before. */
function Workflow3D({ audit }) {
  const ref = React.useRef(null);
  const api = React.useRef(null);
  useEffect(() => {
    if (!window.APWorkflow3D || !ref.current) return undefined;
    try { api.current = window.APWorkflow3D.mount(ref.current); } catch (e) { api.current = null; }
    return () => { if (api.current) api.current.destroy(); api.current = null; };
  }, []);
  useEffect(() => { if (api.current) { try { api.current.update(audit); } catch (e) {} } }, [audit]);
  if (!window.APWorkflow3D) return null;
  return html`<div ref=${ref} className="ap3d-host"></div>`;
}

/* ---------------------------------------------------------------- report */
function Overview({ a }) {
  const r = a.result || {};
  const j = r.journey || {};
  const failed = (j.steps || []).find((s) => s.status === "failed");
  const top = (r.findings || [])[0];
  const ts = a.task_status;
  return html`<div>
    <div className="kpis">
      <div className="kpi"><div className="l">TASK STATUS</div><div className=${"v " + (ts === "passed" ? "green" : ts === "failed" ? "red" : "cyan")}>${(ts || "unknown").toUpperCase()}</div></div>
      <div className="kpi"><div className="l">ISSUES FOUND</div><div className="v amber">${String(a.issue_count || 0).padStart(2, "0")}</div></div>
      <div className="kpi"><div className="l">A11Y SCORE</div><div className="v cyan">${a.score ?? "–"}/100</div></div>
    </div>
    <h3 style=${{ fontSize: 14, margin: "18px 0 0" }}>Journey walkthrough (keyboard only)</h3>
    <${JourneyChips} steps=${j.steps} />
    ${failed && html`<div className="crit"><div className="l">CRITICAL FINDING / KEYBOARD</div><p>${failed.reason}</p></div>`}
    ${r.overall && html`<div className="summary"><div className="l">AI DIAGNOSIS · ${r.overall.provider}</div>
      <p style=${{ margin: "6px 0" }}>${r.overall.summary}</p>
      ${r.overall.root_cause && html`<p style=${{ margin: "6px 0" }}><b>Likely cause:</b> ${r.overall.root_cause}</p>`}
      ${r.overall.priority_fix && html`<p style=${{ margin: "6px 0" }}><b>Fix first:</b> ${r.overall.priority_fix}</p>`}
    </div>`}
    ${r.agent && !r.agent.error && html`<div className="summary"><div className="l">TINYFISH AGENT (MOUSE-STYLE JOURNEY)</div>
      <p style=${{ margin: "6px 0" }}>${r.agent.success ? "✅ The agent completed the task." : "❌ The agent could not complete the task."}
       ${r.agent.blocked_reason ? " " + r.agent.blocked_reason : ""}</p>
      <div className="journey">${(r.agent.steps || []).map((s, i) => html`<div key=${i} className="jstep"><span className="dot passed"></span>${s.label}</div>`)}</div>
      ${!r.agent.success || j.passed !== false ? "" : html`<p className="muted" style=${{ margin: 0, fontSize: 13 }}>A mouse user can finish, a keyboard user cannot — this is an accessibility barrier, not a broken site.</p>`}
    </div>`}
    ${top && !failed && html`<div className="crit"><div className="l">TOP ISSUE / ${COND_LABEL[top.condition].toUpperCase()}</div><p>${top.title} — ${top.description}</p></div>`}
  </div>`;
}

function JourneyChips({ steps }) {
  if (!steps || steps.length <= 1) return html`<p className="muted" style=${{ fontSize: 13 }}>No journey steps were given — page-level checks only.</p>`;
  return html`<div className="journey">${steps.map((s) => html`<div key=${s.index} className=${"jstep " + s.status}>
    <span className=${"dot " + s.status}></span>${s.label}${s.status === "failed" ? " ⚠" : ""}</div>`)}</div>`;
}

function Journey({ a }) {
  const j = (a.result || {}).journey || {};
  return html`<div>
    <${JourneyChips} steps=${j.steps} />
    ${(j.steps || []).map((s) => html`<div key=${s.index} className="issue">
      <div className="row"><span className=${"dot " + s.status}></span><h3>${s.index}. ${s.label}</h3><span className="cond">${s.status}</span>
        ${s.tabs ? html`<span className="cond">${s.tabs} Tab press${s.tabs > 1 ? "es" : ""}</span>` : ""}${s.key ? html`<span className="cond">pressed ${s.key}</span>` : ""}</div>
      ${s.reason && html`<p>${s.reason}</p>`}
      ${s.url && html`<p className="mono muted">${s.url}</p>`}
    </div>`)}
    ${j.focus_log && j.focus_log.length > 0 && html`<h3 style=${{ fontSize: 14 }}>Recorded focus path</h3>
      ${j.focus_log.map((f, i) => html`<div key=${i} style=${{ marginBottom: 10 }}><div className="muted" style=${{ fontSize: 12, marginBottom: 4 }}>Looking for “${f.step}”</div>
        <div className="focuslog">${f.path.map((p, k) => html`<span key=${k}>${p || "(no name)"}</span>`)}</div></div>`)}`}
    ${j.scan_stats && j.scan_stats.tabbable !== undefined && html`<p className="muted" style=${{ fontSize: 13 }}>Start page: ${j.scan_stats.tabbable} focusable elements, ${j.scan_stats.tab_presses} Tab presses recorded.</p>`}
  </div>`;
}

function Issues({ a, withFix }) {
  const fs = (a.result || {}).findings || [];
  const [filter, setFilter] = useState("all");
  const shown = fs.filter((f) => filter === "all" || f.condition === filter);
  if (!fs.length) return html`<p>🎉 No issues found.</p>`;
  return html`<div>
    <div className="chips" style=${{ marginBottom: 12 }}>
      ${["all", "keyboard", "screen_reader", "mobile", "general"].map((k) => html`<button key=${k} type="button" className="chip" aria-pressed=${filter === k} onClick=${() => setFilter(k)}>
        ${k === "all" ? "All" : COND_LABEL[k]} (${k === "all" ? fs.length : fs.filter((f) => f.condition === k).length})</button>`)}
    </div>
    ${shown.map((f) => html`<div key=${f.id} className="issue">
      <div className="row"><span className=${"sev " + f.severity}>${f.severity}</span><h3>${f.title}</h3>
        <span className="cond">${COND_LABEL[f.condition]}</span><span className="cond">${f.source}</span>${f.count > 1 ? html`<span className="cond">×${f.count}</span>` : ""}</div>
      <p>${f.description}</p>
      ${f.wcag && f.wcag.length > 0 && html`<p className="muted" style=${{ fontSize: 12 }}>WCAG: ${f.wcag.join(", ")} ${f.help_url ? html` · <a href=${f.help_url} target="_blank" rel="noopener">learn more</a>` : ""}</p>`}
      ${f.elements && f.elements.length > 0 && html`<div className="els">${f.elements.map((e) => (e.selector || "") + (e.text ? "  “" + e.text + "”" : "") + (e.size ? "  " + e.size : "") + (e.html ? "\n  " + e.html : "")).join("\n")}</div>`}
      ${withFix && f.ai && html`<div className="fix">
        <b>WHY IT HURTS USERS</b><p>${f.ai.explanation}</p>
        <b>SUGGESTED FIX ${f.ai_source && f.ai_source !== "library" ? "· AI (" + f.ai_source + ")" : "· fix library"}</b><p>${f.ai.fix}</p>
        ${f.ai.code && html`<pre className="code">${f.ai.code}</pre>`}</div>`}
    </div>`)}
  </div>`;
}

function Evidence({ a, onZoom }) {
  const r = a.result || {};
  const shots = [];
  if (r.site && r.site.screenshot) shots.push([r.site.screenshot, "Start page (desktop)"]);
  ((r.journey || {}).steps || []).forEach((s) => s.screenshot && shots.push([s.screenshot, `Step ${s.index}: ${s.label} — ${s.status}`]));
  (r.findings || []).forEach((f) => f.evidence && !shots.find((x) => x[0] === f.evidence) && shots.push([f.evidence, f.title]));
  if (r.mobile && r.mobile.screenshot && !shots.find((x) => x[0] === r.mobile.screenshot)) shots.push([r.mobile.screenshot, "Mobile view (390px)"]);
  return html`<div>
    <div className="shots">${shots.map(([src, cap]) => html`<figure key=${src} className="shot" style=${{ margin: 0 }}>
      <img src=${ev(src)} alt=${cap} onClick=${() => onZoom(ev(src))} /><figcaption className="c">${cap}</figcaption></figure>`)}</div>
    ${r.aria_tree && html`<h3 style=${{ fontSize: 14 }}>Accessibility tree (what a screen reader gets)</h3><pre className="code" style=${{ maxHeight: 300 }}>${r.aria_tree}</pre>`}
  </div>`;
}

function Compare({ c }) {
  return html`<div className="compare">
    <div className="l" style=${{ fontSize: 11, fontWeight: 700, letterSpacing: ".08em", color: "#6ee7b7" }}>RETEST RESULT (vs previous run)</div>
    <div className="big">Score ${c.score_before ?? "–"} → ${c.score_after ?? "–"} · Task ${c.task_before} → ${c.task_after}</div>
    <div style=${{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(200px,1fr))", gap: 12, marginTop: 8 }}>
      <div><b>✅ Fixed (${c.fixed.length})</b><ul>${c.fixed.map((x) => html`<li key=${x.id}>${x.title}</li>`)}</ul></div>
      <div><b>⚠️ Still open (${c.remaining.length})</b><ul>${c.remaining.map((x) => html`<li key=${x.id}>${x.title}</li>`)}</ul></div>
      <div><b>🆕 New (${c.new.length})</b><ul>${c.new.map((x) => html`<li key=${x.id}>${x.title}</li>`)}</ul></div>
    </div></div>`;
}

function AuditView({ id, onCreated }) {
  const [a, setA] = useState(null);
  const [tab, setTab] = useState("overview");
  const [zoom, setZoom] = useState(null);
  const [err, setErr] = useState("");

  useEffect(() => {
    let stop = false, timer;
    const load = async () => {
      try { const d = await api(`/api/audits/${id}`); if (stop) return; setA(d);
        if (d.status === "queued" || d.status === "running") timer = setTimeout(load, 1500);
      } catch (e) { setErr(e.message); }
    };
    setA(null); setTab("overview"); load();
    return () => { stop = true; clearTimeout(timer); };
  }, [id]);

  if (err) return html`<div className="err">${err}</div>`;
  if (!a) return html`<div className="card">Loading…</div>`;
  const done = a.status === "done";
  const rerun = async () => { try { const n = await api(`/api/audits/${id}/rerun`, { method: "POST", body: JSON.stringify({ access_code: window.__apCode || "" }) }); onCreated(n.id); } catch (e) { setErr(e.message); } };
  const TABS = [["overview", "Overview"], ["journey", "Journey"], ["issues", "Issues"], ["evidence", "Evidence"], ["fixes", "Fix ideas"]];

  return html`<div className="card">
    <div className="head">
      <div><h2>${a.task}</h2><div className="url">${a.url}${a.parent_id ? " · re-run" : ""}</div></div>
      <div className="actions">
        <span className=${"tag " + (done ? a.task_status : a.status)} style=${{ alignSelf: "center" }}>${done ? a.task_status : a.status}</span>
        ${done && html`<button className="btn small" style=${{ width: "auto", margin: 0 }} onClick=${rerun}>↻ Fix & rerun</button>`}
      </div>
    </div>
    ${a.comparison && html`<${Compare} c=${a.comparison} />`}
    <${Workflow3D} audit=${a} />
    <${Workflow} progress=${a.progress} />
    ${a.status === "error" && html`<div className="err" role="alert"><b>Audit failed:</b> ${a.error}</div>`}
    ${done && html`<div>
      <div className="tabs" role="tablist">${TABS.map(([k, l]) => html`<button key=${k} role="tab" aria-selected=${tab === k} onClick=${() => setTab(k)}>${l}</button>`)}</div>
      ${tab === "overview" && html`<${Overview} a=${a} />`}
      ${tab === "journey" && html`<${Journey} a=${a} />`}
      ${tab === "issues" && html`<${Issues} a=${a} withFix=${false} />`}
      ${tab === "evidence" && html`<${Evidence} a=${a} onZoom=${setZoom} />`}
      ${tab === "fixes" && html`<${Issues} a=${a} withFix=${true} />`}
    </div>`}
    ${zoom && html`<div className="lightbox" onClick=${() => setZoom(null)}><img src=${zoom} alt="Evidence screenshot, enlarged" /></div>`}
  </div>`;
}

/* ---------------------------------------------------------------- app */
function App() {
  const [health, setHealth] = useState(null);
  const [list, setList] = useState([]);
  const [sel, setSel] = useState(null);
  const refresh = useCallback(() => api("/api/audits").then(setList).catch(() => {}), []);
  useEffect(() => { api("/api/health").then(setHealth).catch(() => {}); refresh(); const t = setInterval(refresh, 4000); return () => clearInterval(t); }, []);
  const created = (id) => {
    setSel(id); refresh();
    // bring the running audit into view (on phones the report sits below the form)
    setTimeout(() => {
      const m = document.querySelector("main");
      if (m && m.getBoundingClientRect().top > 80) window.scrollTo({ top: m.getBoundingClientRect().top + window.scrollY - 12, behavior: "auto" });
    }, 250);
  };

  return html`<div>
    <header className="top">
      <div className="logo" aria-hidden="true">A</div>
      <div className="brand">ACCESSPATH<small>Autonomous Accessibility Auditor</small></div>
      ${health && html`<div className="pills">
        <span className=${"pill " + (health.tinyfish === "configured" ? "ok" : "warn")}>TinyFish: <b>${health.tinyfish === "configured" ? "connected" : "no key"}</b></span>
        <span className=${"pill " + (health.llm !== "none" ? "ok" : "warn")}>LLM: <b>${health.llm === "none" ? "fix library" : health.llm}</b></span>
        <span className="pill ok">DB: <b>${health.database}</b></span>
      </div>`}
    </header>
    <div className="wrap">
      <div>
        <${NewAudit} onCreated=${created} health=${health} />
        <nav className="card hist" aria-label="Audit history">
          <h2>History</h2>
          ${list.length === 0 && html`<p className="sub">No audits yet.</p>`}
          ${list.map((x) => html`<button key=${x.id} aria-current=${sel === x.id} onClick=${() => setSel(x.id)}>
            <div className="u">${x.task}</div>
            <div className="m"><span className=${"tag " + (x.status === "done" ? x.task_status : x.status)}>${x.status === "done" ? x.task_status : x.status}</span>
              ${x.score != null ? html`<span>${x.score}/100</span>` : ""}<span>${x.issue_count || 0} issues</span>${x.parent_id ? html`<span>↻ rerun</span>` : ""}</div>
          </button>`)}
        </nav>
      </div>
      <main>
        ${sel ? html`<${AuditView} id=${sel} onCreated=${created} />` : html`<div className="card empty"><div>
          <h1>ACCESS <span>PATH</span></h1>
          <p style=${{ fontSize: 18 }}>Don't just scan websites. Test whether everyone can use them.</p>
          <p>Enter any website and the task a real user wants to finish, then click <b>Run audit</b>.</p></div></div>
          <div className="card" style=${{ marginTop: 16 }}><${Workflow3D} audit=${null} /></div>`}
      </main>
    </div>
  </div>`;
}

ReactDOM.createRoot(document.getElementById("root")).render(html`<${App} />`);

