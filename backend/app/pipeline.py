"""The audit pipeline. It follows the 9 steps from the ACCESSPATH workflow slide:

 1 Enter website URL   -> URL + task saved
 2 Inspect the site    -> Playwright opens the page, counts controls
 3 Select conditions   -> keyboard / screen reader / mobile
 4 Attempt journey     -> TinyFish agent tries the task like a normal user
 5 Record interactions -> Playwright replays the same path with keyboard only
 6 Analyse findings    -> axe-core rules + screen reader + mobile + task result
 7 Explain & recommend -> LLM (or built-in library) explains causes and fixes
 8 Show audit report   -> everything saved for the dashboard
 9 Fix and rerun       -> /api/audits/{id}/rerun runs the same journey again
"""
import threading
import traceback
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeout

from playwright.sync_api import sync_playwright

from . import config
from .database import Audit, SessionLocal, now_utc
from .services import browser_checks as bc
from .services import llm, tinyfish

WORKFLOW = [
    (1, "url", "Enter website URL", "URL + task"),
    (2, "inspect", "Inspect the site", "Page & controls"),
    (3, "conditions", "Select conditions", "Keyboard / screen reader / mobile"),
    (4, "agent", "Attempt journey", "TinyFish agent"),
    (5, "record", "Record interactions", "Keyboard replay + browser evidence"),
    (6, "analyse", "Analyse findings", "Rules + task result"),
    (7, "explain", "Explain & recommend", "LLM suggestions"),
    (8, "report", "Show audit report", "Evidence dashboard"),
    (9, "rerun", "Fix and rerun", "Retest loop"),
]
SEVERITY_RANK = {"critical": 0, "serious": 1, "moderate": 2, "minor": 3}
PENALTY = {"critical": 10, "serious": 5, "moderate": 2, "minor": 1}

_tf_pool = ThreadPoolExecutor(max_workers=4, thread_name_prefix="tinyfish")
_executor = ThreadPoolExecutor(max_workers=max(1, config.AUDIT_WORKERS), thread_name_prefix="audit")
_lock = threading.Lock()


def initial_progress():
    return [{"n": n, "key": k, "title": t, "subtitle": s, "status": "pending", "detail": "", "data": {}}
            for n, k, t, s in WORKFLOW]


class Tracker:
    """Writes step progress to the database so the dashboard can poll it."""

    def __init__(self, audit_id: str):
        self.id = audit_id

    def _update(self, fn):
        with _lock:
            db = SessionLocal()
            try:
                a = db.get(Audit, self.id)
                fn(a)
                db.commit()
            finally:
                db.close()

    def step(self, n: int, status: str, detail: str = "", data: dict | None = None):
        def fn(a):
            prog = [dict(p) for p in (a.progress or initial_progress())]
            p = prog[n - 1]
            p["status"] = status
            if detail:
                p["detail"] = detail
            if data:
                p["data"] = {**p.get("data", {}), **data}
            a.progress = prog
            if status == "running":
                a.current_step = n
        self._update(fn)

    def set(self, **fields):
        def fn(a):
            for k, v in fields.items():
                setattr(a, k, v)
        self._update(fn)


def submit(audit_id: str):
    _executor.submit(run_audit, audit_id)


def _score(findings, journey_passed):
    s = 100
    for f in findings:
        s -= PENALTY.get(f["severity"], 2)
    if journey_passed is False:
        s -= 10
    return max(0, min(100, s))


def launch_browser(pw):
    """Real Chrome if installed (gets past more bot protection), else bundled Chromium."""
    args = ["--disable-dev-shm-usage", "--disable-blink-features=AutomationControlled"]
    if config.DISABLE_HTTP2:
        args.append("--disable-http2")
    if config.USE_SYSTEM_CHROME:
        try:
            return pw.chromium.launch(channel="chrome", headless=config.HEADLESS, args=args)
        except Exception:
            pass
    return pw.chromium.launch(headless=config.HEADLESS, args=args)


def friendly_error(e: Exception, url: str) -> str:
    """Turn browser errors into a message a person can act on."""
    text = str(e)
    if type(e).__name__ == "BlockedError" or any(k in text for k in ("ERR_HTTP2_PROTOCOL_ERROR", "ERR_BLOCKED", "ERR_ACCESS_DENIED")):
        return (f"Couldn't audit {url}. This website blocks automated browsers (bot protection) — common on big shopping sites. "
                "Try setting HEADLESS=false in backend/.env and restarting (a visible Chrome window gets through more often), "
                "or audit a different site or your own website.")
    hints = [
        (("ERR_NAME_NOT_RESOLVED",), "This website address doesn't exist. Check the spelling of the URL."),
        (("ERR_INTERNET_DISCONNECTED", "ERR_TUNNEL_CONNECTION_FAILED", "ERR_PROXY"), "Couldn't reach the internet from this computer. Check your connection and try again."),
        (("ERR_CONNECTION_REFUSED",), "The website refused the connection. Is the site running?"),
        (("ERR_CONNECTION_TIMED_OUT", "Timeout"), "The website didn't finish loading in time. Big shopping sites often do this on purpose to slow down automated browsers. "
          "Try HEADLESS=false in backend/.env (a visible Chrome window), or try again, or audit a different page."),
        (("ERR_CERT", "SSL"), "The website's security certificate isn't valid, so the browser stopped."),
        (("Executable doesn't exist",), "Chromium isn't installed. Run: python -m playwright install chromium"),
    ]
    for keys, msg in hints:
        if any(k in text for k in keys):
            return f"Couldn't audit {url}. {msg}"
    return f"Couldn't audit {url}. {type(e).__name__}: {text.splitlines()[0][:200]}"


def run_audit(audit_id: str):
    t = Tracker(audit_id)
    db = SessionLocal()
    a = db.get(Audit, audit_id)
    url, task = a.url, a.task
    user_steps = list(a.journey_steps or [])
    cond = a.conditions or {}
    use_tf = bool(a.use_tinyfish)
    db.close()

    ev_dir = config.EVIDENCE_DIR / audit_id
    ev_dir.mkdir(parents=True, exist_ok=True)
    t.set(status="running")
    report = {"url": url, "task": task, "conditions": cond}
    tf_future = None

    try:
        # ---- 1. URL + task
        t.step(1, "done", f"{url} — “{task}”")

        # TinyFish works in the cloud, so start it now: it runs while the local browser
        # inspects and checks the page, and its result counts even if the site blocks us locally.
        tf_future = None
        why = ""
        if not use_tf:
            why = "TinyFish is off for this audit"
        elif not tinyfish.is_configured():
            why = "No TINYFISH_API_KEY in backend/.env"
        elif not tinyfish.is_public_url(url):
            why = "TinyFish can't open localhost"
        else:
            why = ""
            t.step(4, "running", "TinyFish agent is attempting the task in the cloud (other checks run at the same time)…")
            tf_future = _tf_pool.submit(tinyfish.run_journey, url, task, user_steps,
                                        lambda msg, d: t.step(4, "running", msg + " · other checks running", d))

        with sync_playwright() as pw:
            browser = launch_browser(pw)
            try:
                # ---- 2. Inspect
                t.step(2, "running", "Opening the page in Chromium…")
                site = bc.inspect_site(browser, url, ev_dir)
                report["site"] = site
                t.step(2, "done", f"“{site['title'] or 'untitled'}”: {site['links']} links, {site['buttons']} buttons, "
                                  f"{site['inputs']} inputs, {site['tabbable']} focusable", {"screenshot": site["screenshot"]})

                # ---- 3. Conditions
                names = [n for k, n in (("keyboard", "Keyboard"), ("screen_reader", "Screen reader"), ("mobile", "Mobile"))
                         if cond.get(k)]
                t.step(3, "done", ", ".join(names) or "Rules only")

                # ---- 4. Attempt journey. TinyFish runs in the background while the page
                # checks run here, so its wait time is mostly hidden. If it is off, not
                # allowed (localhost) or too slow, the fast local agent finds the path.
                agent = None
                steps = user_steps

                # page checks that don't need the journey (part of step 6, done early)
                pre = []
                ctx = bc.new_context(browser)
                page = ctx.new_page()
                try:
                    bc.goto(page, url)
                    pre += bc.run_axe(page)
                    if cond.get("screen_reader", True):
                        sr, tree = bc.screen_reader_checks(page)
                        pre += sr
                        report["aria_tree"] = tree
                finally:
                    ctx.close()
                if cond.get("mobile", True):
                    mob, mob_info = bc.mobile_checks(browser, url, ev_dir)
                    pre += mob
                    report["mobile"] = mob_info

                tf_note = ""
                if tf_future:
                    try:
                        agent = tf_future.result(timeout=config.TINYFISH_MAX_WAIT_SECONDS + 15)
                        clicks = [s["label"] for s in agent["steps"] if s.get("action", "click") != "type"]
                        clicks = [c for i, c in enumerate(clicks) if i == 0 or c.lower() != clicks[i - 1].lower()]
                        if clicks and not user_steps:
                            steps = clicks
                        verdict = "completed the task" if agent["success"] else "could not complete the task"
                        tf_note = (f"TinyFish {verdict} in {agent['duration_s']}s "
                                   f"({len(agent['steps'])} actions): {' › '.join(clicks) or '—'}")
                    except FutureTimeout:
                        agent = {"error": "timed out", "success": False, "steps": []}
                        tf_note = f"TinyFish took longer than {config.TINYFISH_MAX_WAIT_SECONDS}s"
                    except Exception as e:
                        agent = {"error": str(e), "success": False, "steps": []}
                        tf_note = f"TinyFish error: {str(e)[:120]}"

                if steps:
                    if tf_future and not agent.get("error"):
                        t.step(4, "done", tf_note, {"run_id": agent.get("run_id"), "streaming_url": agent.get("streaming_url")})
                    elif tf_future:
                        t.step(4, "failed", tf_note + " — using your journey steps.")
                    else:
                        t.step(4, "skipped", why + " — using your journey steps.")
                else:
                    lead = tf_note or why
                    t.step(4, "running", (lead + " — " if lead else "") + "fast local agent is finding the path…")
                    fast = bc.fast_agent(browser, url, task)
                    steps = fast["steps"]
                    report["fast_agent"] = fast
                    found = ("found " + str(len(steps)) + " steps: " + " › ".join(steps)) if steps else "found no clear path (page-level checks only)"
                    t.step(4, "done", (lead + " — " if lead else "") + f"fast local agent {found} in {fast['duration_s']}s.")
                report["agent"] = agent
                report["journey_steps"] = steps
                t.set(journey_steps=steps)

                # ---- 5. Keyboard replay
                t.step(5, "running", "Replaying the journey with keyboard only (Tab / Enter / Escape)…")
                if cond.get("keyboard", True):
                    journey = bc.keyboard_journey(browser, url, steps, ev_dir)
                else:
                    journey = {"steps": [], "passed": None, "findings": [], "scan_stats": {}, "focus_log": []}
                report["journey"] = {k: v for k, v in journey.items() if k != "findings"}
                done_steps = sum(1 for s in journey["steps"] if s["status"] == "passed") - 1
                if journey["passed"] is True:
                    detail = f"Keyboard user completed all {len(steps)} steps."
                elif journey["passed"] is False:
                    fs = next(s for s in journey["steps"] if s["status"] == "failed")
                    detail = f"Blocked at step {fs['index']} “{fs['label']}” after {max(done_steps, 0)} step(s)."
                elif not steps:
                    detail = "No journey steps — ran a page-level keyboard scan."
                else:
                    detail = "Journey step names not found on the page."
                t.step(5, "done", detail)

                # ---- 6. Analyse (rule checks already ran during step 4)
                t.step(6, "running", "Combining rule checks, screen reader, mobile and journey results…")
                findings = list(journey["findings"]) + pre
            finally:
                browser.close()

        # filter by chosen conditions + de-duplicate
        allowed = {"general"} | {c for c in ("keyboard", "screen_reader", "mobile") if cond.get(c, True)}
        seen, clean = set(), []
        for f in findings:
            if f["condition"] in allowed and f["id"] not in seen:
                seen.add(f["id"])
                clean.append(f)
        clean.sort(key=lambda f: (SEVERITY_RANK.get(f["severity"], 4), 0 if f["source"] == "journey" else 1))

        if cond.get("keyboard", True) and journey["passed"] is not None:
            task_status = "passed" if journey["passed"] else "failed"
        elif agent and "success" in agent and not agent.get("error"):
            task_status = "passed" if agent["success"] else "failed"
        else:
            task_status = "unknown"
        score = _score(clean, journey["passed"])
        counts = {s: sum(1 for f in clean if f["severity"] == s) for s in SEVERITY_RANK}
        breakdown = ", ".join(f"{v} {k}" for k, v in counts.items() if v)
        t.step(6, "done", f"{len(clean)} issues" + (f" — {breakdown}" if breakdown else "") + f". Score {score}/100.")

        # ---- 7. Explain
        provider = config.llm_provider()
        t.step(7, "running", f"Asking {provider if provider != 'none' else 'built-in fix library'} for causes and fixes…")
        overall = llm.explain(task, journey, agent, clean)
        t.step(7, "done", f"Explained by {overall['provider']}.")

        # ---- 8. Report
        report.update({"findings": clean, "counts": counts, "overall": overall, "task_status": task_status,
                       "score": score})
        t.set(result=report, task_status=task_status, score=score, issue_count=len(clean))
        t.step(8, "done", "Report ready.")
        t.step(9, "ready", "Fix the site, then press “Fix & rerun” to test the same journey again.")
        t.set(status="done", finished_at=now_utc())

    except Exception as e:
        tb = traceback.format_exc()
        print(tb)
        tf_msg = ""
        if tf_future is not None:
            try:
                ag = tf_future.result(timeout=config.TINYFISH_MAX_WAIT_SECONDS + 15)
                verdict = "completed the task" if ag.get("success") else "could not complete the task"
                labels = " › ".join(x["label"] for x in ag.get("steps", [])) or "—"
                tf_msg = f" TinyFish opened the site in the cloud and {verdict} ({labels}), but the local keyboard and rule checks need the page to open on this computer."
                report["agent"] = ag
                t.step(4, "done" if not ag.get("error") else "failed", f"TinyFish {verdict} in {ag.get('duration_s', '?')}s: {labels}",
                       {"run_id": ag.get("run_id"), "streaming_url": ag.get("streaming_url")})
            except Exception as te:
                tf_msg = f" TinyFish also didn't finish: {str(te)[:120]}"
        def fail(a):
            prog = [dict(p) for p in (a.progress or initial_progress())]
            for p in prog:
                if p["status"] == "running" and p["n"] != 4:
                    p["status"] = "failed"
                    p["detail"] = str(e)[:300]
            a.progress = prog
            a.status = "error"
            a.error = friendly_error(e, url) + tf_msg
            a.result = report
            a.finished_at = now_utc()
        t._update(fail)
