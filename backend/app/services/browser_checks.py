"""Playwright + axe-core checks (workflow steps 2, 5 and 6).

- inspect_site()       step 2: open the page, count controls, take a screenshot
- keyboard_scan()      step 5/6: Tab through the page, find focus traps and missing focus rings
- keyboard_journey()   step 5: replay the journey using ONLY the keyboard
- run_axe()            step 6: automated WCAG rule checks (axe-core)
- screen_reader_checks step 6: names, roles, clickable <div>s, link text
- mobile_checks()      step 6: small screen layout + touch target size

Every check returns "findings" in one common shape (see make_finding).
All functions use the *sync* Playwright API; the pipeline runs them in a
worker thread, which also keeps Playwright happy on Windows.
"""
import re
import time
from pathlib import Path

from playwright.sync_api import Browser, Page

from .. import config

_AXE_SOURCE = None


def _axe_source() -> str:
    global _AXE_SOURCE
    if _AXE_SOURCE is None:
        _AXE_SOURCE = config.AXE_JS_PATH.read_text(encoding="utf-8")
    return _AXE_SOURCE


def make_finding(*, rule, title, severity, condition, source, description, wcag=None,
                 help_url="", elements=None, evidence=None, step=None, extra=None):
    return {
        "id": f"{source}:{rule}",
        "rule": rule,
        "title": title,
        "severity": severity,            # critical | serious | moderate | minor
        "condition": condition,          # keyboard | screen_reader | mobile | general
        "source": source,                # axe | keyboard | screen_reader | mobile | journey
        "description": description,
        "wcag": wcag or [],
        "help_url": help_url,
        "elements": (elements or [])[:8],
        "count": len(elements or []) or 1,
        "evidence": evidence,
        "step": step,
        "extra": extra or {},
    }


DESKTOP_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")
MOBILE_UA = ("Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 "
             "(KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1")
# Many big sites block the default "HeadlessChrome" browser. These settings make the
# audit browser look like a normal Chrome so more real websites open.
STEALTH_JS = """
Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
Object.defineProperty(navigator, 'languages', { get: () => ['en-IN', 'en'] });
Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
window.chrome = window.chrome || { runtime: {} };
"""


class BlockedError(Exception):
    """The website answered, but with a bot-protection or access-denied page."""


def new_context(browser: Browser, mobile=False):
    common = dict(bypass_csp=True, ignore_https_errors=True, locale="en-IN", timezone_id="Asia/Kolkata",
                  extra_http_headers={"Accept-Language": "en-IN,en;q=0.9"})
    if mobile:
        ctx = browser.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2, is_mobile=True,
                                  has_touch=True, user_agent=MOBILE_UA, **common)
    else:
        ctx = browser.new_context(viewport={"width": 1366, "height": 850}, user_agent=DESKTOP_UA, **common)
    ctx.add_init_script(STEALTH_JS)
    ctx.set_default_timeout(config.PAGE_TIMEOUT_MS)
    return ctx


BLOCK_TITLES = ("access denied", "just a moment", "attention required", "are you a robot", "request blocked",
                "pardon our interruption", "403 forbidden", "bot verification", "security check")


def goto(page: Page, url: str):
    last = None
    for attempt in range(2):  # one retry: some sites reset the first connection
        try:
            # return as soon as the server answers; slow or stalling sites are handled below
            resp = page.goto(url, wait_until="commit", timeout=config.PAGE_TIMEOUT_MS)
            break
        except Exception as e:
            last = e
            if attempt == 1 or not any(k in str(e) for k in ("ERR_HTTP2", "ERR_CONNECTION_RESET", "ERR_CONNECTION_CLOSED", "ERR_EMPTY_RESPONSE")):
                raise
            page.wait_for_timeout(1500)
    try:
        page.wait_for_load_state("domcontentloaded", timeout=config.PAGE_TIMEOUT_MS)
    except Exception:
        # still loading: carry on if the page already shows content, otherwise give up
        if not page.evaluate("() => !!document.body && document.body.innerText.trim().length > 20"):
            raise TimeoutError("Timeout: the page never showed any content")
    try:
        page.wait_for_load_state("networkidle", timeout=6000)
    except Exception:
        pass
    page.wait_for_timeout(600)
    title = (page.title() or "").lower()
    status = resp.status if resp else 200
    if status in (401, 403, 429) or any(t in title for t in BLOCK_TITLES):
        raise BlockedError(f"status {status}, page title '{page.title()}'")


def shot(page: Page, ev_dir: Path, name: str, full_page=False) -> str | None:
    try:
        path = ev_dir / f"{name}.png"
        page.screenshot(path=str(path), full_page=full_page)
        return f"evidence/{ev_dir.name}/{path.name}"
    except Exception:
        return None


# ---------------------------------------------------------------- JS helpers
JS_HELPERS = r"""
window.__ap = window.__ap || {};
__ap.sel = function(e){
  if(!e || e.nodeType!==1) return '';
  if(e.id) return '#'+CSS.escape(e.id);
  const parts=[];
  while(e && e.nodeType===1 && parts.length<5){
    let p=e.tagName.toLowerCase();
    if(e.id){ parts.unshift(p+'#'+CSS.escape(e.id)); break; }
    const par=e.parentElement;
    if(par){ const sib=[...par.children].filter(c=>c.tagName===e.tagName); if(sib.length>1) p+=':nth-of-type('+(sib.indexOf(e)+1)+')'; }
    parts.unshift(p); e=par;
  }
  return parts.join(' > ');
};
__ap.name = function(e){
  if(!e) return '';
  let n = e.getAttribute('aria-label') || '';
  const lb = e.getAttribute('aria-labelledby');
  if(!n && lb){ n = lb.split(/\s+/).map(id=>document.getElementById(id)).filter(Boolean).map(x=>x.innerText).join(' '); }
  if(!n && e.id){ const l=document.querySelector('label[for="'+CSS.escape(e.id)+'"]'); if(l) n=l.innerText; }
  if(!n && e.closest('label')) n = e.closest('label').innerText;
  if(!n) n = e.innerText || '';
  if(!n && (e.tagName==='INPUT'||e.tagName==='BUTTON')) n = e.value || '';
  if(!n){ const img=e.querySelector && e.querySelector('img[alt]'); if(img) n=img.alt; }
  if(!n) n = e.getAttribute('title') || '';
  return n.trim().replace(/\s+/g,' ').slice(0,100);
};
__ap.visible = function(e){
  const r=e.getBoundingClientRect(); const cs=getComputedStyle(e);
  return r.width>0 && r.height>0 && cs.visibility!=='hidden' && cs.display!=='none' && parseFloat(cs.opacity)>0;
};
__ap.TABBABLE = 'a[href],area[href],button,input:not([type=hidden]),select,textarea,summary,iframe,[tabindex],[contenteditable="true"]';
__ap.tabbables = function(){
  return [...document.querySelectorAll(__ap.TABBABLE)].filter(e=>!e.disabled && e.getAttribute('tabindex')!=='-1' && __ap.visible(e));
};
__ap.container = function(e){
  return e.closest('nav,[role=navigation],[role=menu],[role=menubar],[role=dialog],dialog,aside,header,footer,form,main,[role=main]');
};
__ap.active = function(){
  const el=document.activeElement;
  if(!el || el===document.body || el===document.documentElement) return {kind:'body', selector:'body', name:''};
  const c=__ap.container(el); const r=el.getBoundingClientRect();
  return {kind:'el', selector:__ap.sel(el), tag:el.tagName.toLowerCase(), type:(el.getAttribute('type')||'').toLowerCase(),
          role:el.getAttribute('role')||'', name:__ap.name(el), rect:[Math.round(r.x),Math.round(r.y),Math.round(r.width),Math.round(r.height)],
          container: c? __ap.sel(c):'', containerLabel: c? (c.getAttribute('aria-label')||c.id||c.tagName.toLowerCase()):'',
          html: el.outerHTML.slice(0,180)};
};
__ap.focusStyle = function(){
  const el=document.activeElement; if(!el || el===document.body) return null;
  const props=['outlineStyle','outlineWidth','outlineColor','boxShadow','backgroundColor','color','borderColor','textDecorationLine'];
  const read=()=>{const cs=getComputedStyle(el); return props.map(p=>cs[p]).join('|');};
  const focused=read(); el.blur(); const blurred=read(); el.focus();
  return focused!==blurred;
};
"""


def _ensure_helpers(page: Page):
    page.evaluate("() => { if(!window.__ap || !window.__ap.active){ " + JS_HELPERS + " } }")


def active_info(page: Page) -> dict:
    _ensure_helpers(page)
    return page.evaluate("() => __ap.active()")


def tabbable_count(page: Page) -> int:
    _ensure_helpers(page)
    return page.evaluate("() => __ap.tabbables().length")


def highlight(page: Page, selector: str, label: str):
    try:
        page.evaluate(
            """([sel,label]) => { const el=document.querySelector(sel); if(!el) return;
            el.scrollIntoView({block:'center'});
            const r=el.getBoundingClientRect(); const d=document.createElement('div');
            d.style.cssText=`position:fixed;left:${r.x-4}px;top:${r.y-4}px;width:${r.width+8}px;height:${r.height+8}px;
              border:3px solid #ef4444;border-radius:8px;z-index:2147483647;pointer-events:none;box-shadow:0 0 0 4px rgba(239,68,68,.25)`;
            const t=document.createElement('div'); t.textContent=label;
            t.style.cssText='position:absolute;top:-28px;left:0;background:#ef4444;color:#fff;font:600 12px sans-serif;padding:4px 8px;border-radius:6px;white-space:nowrap';
            d.appendChild(t); d.className='__ap_hl'; document.body.appendChild(d); }""",
            [selector, label],
        )
    except Exception:
        pass


def clear_highlight(page: Page):
    try:
        page.evaluate("() => document.querySelectorAll('.__ap_hl').forEach(e=>e.remove())")
    except Exception:
        pass


# ---------------------------------------------------------------- step 2
def inspect_site(browser: Browser, url: str, ev_dir: Path) -> dict:
    ctx = new_context(browser)
    page = ctx.new_page()
    try:
        goto(page, url)
        _ensure_helpers(page)
        info = page.evaluate(
            """() => ({
              title: document.title,
              lang: document.documentElement.getAttribute('lang') || '',
              links: document.querySelectorAll('a[href]').length,
              buttons: document.querySelectorAll('button,[role=button],input[type=submit],input[type=button]').length,
              inputs: document.querySelectorAll('input:not([type=hidden]),select,textarea').length,
              images: document.querySelectorAll('img').length,
              headings: document.querySelectorAll('h1,h2,h3,h4,h5,h6').length,
              landmarks: [...document.querySelectorAll('header,nav,main,aside,footer,[role=banner],[role=navigation],[role=main],[role=contentinfo]')].map(e=>e.getAttribute('role')||e.tagName.toLowerCase()),
              tabbable: __ap.tabbables().length,
            })"""
        )
        info["final_url"] = page.url
        info["screenshot"] = shot(page, ev_dir, "01_home")
        return info
    finally:
        ctx.close()


# ---------------------------------------------------------------- keyboard
def _match(name: str, label: str) -> bool:
    n = re.sub(r"\s+", " ", (name or "").lower()).strip()
    l = re.sub(r"\s+", " ", (label or "").lower()).strip()
    if not n or not l:
        return False
    return n == l or l in n or (len(n) >= 3 and n in l)


def _detect_cycle(visited: list[dict]):
    """Return (cycle_selectors, start_index) if focus started repeating."""
    seen = {}
    for i, v in enumerate(visited):
        key = v["selector"]
        if key in seen and v["kind"] == "el":
            return [x["selector"] for x in visited[seen[key]:i]], seen[key]
        seen[key] = i
    return None, None


def _common_container(items: list[dict]) -> str:
    conts = {i.get("container") for i in items if i.get("kind") == "el"}
    return conts.pop() if len(conts) == 1 else ""


def keyboard_scan(page: Page, ev_dir: Path, max_tabs=80) -> tuple[list, dict]:
    """General keyboard check on the start page: focus ring + traps + skip link."""
    findings = []
    _ensure_helpers(page)
    total = tabbable_count(page)
    visited, no_ring = [], []
    for i in range(max_tabs):
        page.keyboard.press("Tab")
        info = active_info(page)
        visited.append(info)
        if info["kind"] == "el" and i < 40:
            try:
                if page.evaluate("() => __ap.focusStyle()") is False:
                    no_ring.append({"selector": info["selector"], "text": info["name"], "html": info["html"]})
            except Exception:
                pass
        cyc, _ = _detect_cycle(visited)
        if cyc:
            break

    cyc, start = _detect_cycle(visited)
    stats = {"tabbable": total, "tab_presses": len(visited), "distinct": len({v["selector"] for v in visited})}
    if cyc and total > 4 and len(set(cyc)) < max(2, int(total * 0.7)):
        cont = _common_container([v for v in visited[start:]]) or "a small group of elements"
        page.keyboard.press("Escape")
        page.keyboard.press("Tab")
        after = active_info(page)
        escaped = after["selector"] not in set(cyc)
        highlight(page, cont if cont.startswith(("#", "nav", "aside", "header", "div", "form")) else cyc[0],
                  "Keyboard focus trapped here")
        ev = shot(page, ev_dir, "02_focus_trap_home")
        clear_highlight(page)
        findings.append(make_finding(
            rule="focus-trap", title="Keyboard focus gets trapped", severity="critical", condition="keyboard",
            source="keyboard",
            description=(f"Pressing Tab keeps cycling through only {len(set(cyc))} elements inside {cont} "
                         f"(page has {total} focusable elements). "
                         + ("Escape releases it." if escaped else "Escape does not release it.")),
            wcag=["2.1.2 No Keyboard Trap (A)"], help_url="https://www.w3.org/WAI/WCAG22/Understanding/no-keyboard-trap",
            elements=[{"selector": s, "text": next((v["name"] for v in visited if v["selector"] == s), "")} for s in dict.fromkeys(cyc)],
            evidence=ev, extra={"container": cont, "escape_releases": escaped},
        ))
    if no_ring:
        findings.append(make_finding(
            rule="focus-visible", title="Focus indicator is not visible", severity="serious", condition="keyboard",
            source="keyboard",
            description=f"{len(no_ring)} element(s) show no visible change when they get keyboard focus, so keyboard users cannot see where they are.",
            wcag=["2.4.7 Focus Visible (AA)"], help_url="https://www.w3.org/WAI/WCAG22/Understanding/focus-visible",
            elements=no_ring,
        ))
    first = next((v for v in visited if v["kind"] == "el"), None)
    if first and total >= 10 and not re.search(r"skip|main content|jump", first.get("name", ""), re.I):
        findings.append(make_finding(
            rule="skip-link", title="No 'Skip to main content' link", severity="minor", condition="keyboard",
            source="keyboard",
            description=f"The first Tab goes to '{first.get('name') or first['selector']}'. Keyboard users must Tab through the whole header on every page.",
            wcag=["2.4.1 Bypass Blocks (A)"], help_url="https://www.w3.org/WAI/WCAG22/Understanding/bypass-blocks",
            elements=[{"selector": first["selector"], "text": first.get("name", "")}],
        ))
    if total == 0:
        findings.append(make_finding(
            rule="no-focusable", title="Nothing on the page can get keyboard focus", severity="critical",
            condition="keyboard", source="keyboard",
            description="Tab never lands on any control. Keyboard users cannot use this page.",
            wcag=["2.1.1 Keyboard (A)"],
        ))
    return findings, stats


def _find_target(page: Page, label: str) -> dict | None:
    """Look for the step's control in the DOM (what a mouse user would click)."""
    _ensure_helpers(page)
    return page.evaluate(
        """(label) => {
          const L = label.toLowerCase().trim();
          const cands = [...document.querySelectorAll('a,button,input,select,summary,[role],[onclick],[tabindex],div,span,li,img')]
            .filter(e => __ap.visible(e));
          let best = null;
          for (const e of cands) {
            const n = __ap.name(e).toLowerCase();
            if (!n) continue;
            if (n === L || (n.includes(L) && n.length < L.length + 25)) {
              if (!best || n.length < __ap.name(best).length) best = e;
            }
          }
          if (!best) return null;
          const tab = __ap.tabbables().includes(best);
          return {selector: __ap.sel(best), tag: best.tagName.toLowerCase(), role: best.getAttribute('role')||'',
                  tabbable: tab, name: __ap.name(best), html: best.outerHTML.slice(0,200)};
        }""",
        label,
    )


def keyboard_journey(browser: Browser, url: str, steps: list[str], ev_dir: Path) -> dict:
    """Replay the journey with only Tab / Shift+Tab / Enter / Space / Escape."""
    ctx = new_context(browser)
    page = ctx.new_page()
    result = {"steps": [], "passed": None, "failed_step": None, "findings": [], "scan_stats": {}, "focus_log": []}
    try:
        goto(page, url)
        # general keyboard scan on the start page, then reload so focus starts fresh
        scan_findings, stats = keyboard_scan(page, ev_dir)
        result["findings"].extend(scan_findings)
        result["scan_stats"] = stats
        goto(page, url)

        result["steps"].append({"index": 0, "label": "Start page", "status": "passed", "url": page.url,
                                "tabs": 0, "screenshot": shot(page, ev_dir, "03_step0_start")})
        if not steps:
            result["passed"] = None
            return result

        for i, label in enumerate(steps, start=1):
            visited = []
            found = None
            for _ in range(config.MAX_TABS_PER_STEP):
                page.keyboard.press("Tab")
                info = active_info(page)
                visited.append(info)
                if info["kind"] == "el" and _match(info["name"], label):
                    found = info
                    break
                cyc, _ = _detect_cycle(visited)
                if cyc and len(visited) > len(set(cyc)) + 2:
                    break
            result["focus_log"].append({"step": label, "path": [v.get("name") or v["selector"] for v in visited][:40]})

            if found:
                key = "Space" if found.get("tag") == "input" and found.get("type") in ("checkbox", "radio") else "Enter"
                before_url = page.url
                page.keyboard.press(key)
                try:
                    page.wait_for_load_state("domcontentloaded", timeout=8000)
                except Exception:
                    pass
                page.wait_for_timeout(700)
                result["steps"].append({
                    "index": i, "label": label, "status": "passed", "tabs": len(visited), "key": key,
                    "focused": found["selector"], "url": page.url, "navigated": page.url != before_url,
                    "screenshot": shot(page, ev_dir, f"04_step{i}_ok"),
                })
                continue

            # ---- step failed: work out WHY
            target = _find_target(page, label)
            cyc, start = _detect_cycle(visited)
            total = tabbable_count(page)
            step_rec = {"index": i, "label": label, "status": "failed", "tabs": len(visited), "url": page.url}
            if cyc and total > 2 and len(set(cyc)) < max(2, total - 1):
                cont = _common_container(visited[start:]) or "a group of elements"
                page.keyboard.press("Escape")
                page.wait_for_timeout(200)
                page.keyboard.press("Tab")
                after = active_info(page)
                escaped = after["selector"] not in set(cyc)
                highlight(page, cont if cont else cyc[0], "Keyboard focus trapped here")
                ev = shot(page, ev_dir, f"05_step{i}_trap")
                clear_highlight(page)
                reason = (f"Focus is trapped in {cont}: Tab cycles through {len(set(cyc))} items "
                          f"({', '.join(dict.fromkeys(v['name'] for v in visited[start:] if v.get('name')))}) "
                          f"and never reaches '{label}'." + ("" if escaped else " Escape does not release focus."))
                step_rec.update({"reason": reason, "kind": "focus_trap", "screenshot": ev})
                result["findings"].append(make_finding(
                    rule="journey-focus-trap", title=f"Journey blocked: focus trapped before '{label}'",
                    severity="critical", condition="keyboard", source="journey", description=reason,
                    wcag=["2.1.2 No Keyboard Trap (A)", "2.1.1 Keyboard (A)"],
                    help_url="https://www.w3.org/WAI/WCAG22/Understanding/no-keyboard-trap",
                    elements=[{"selector": s} for s in dict.fromkeys(cyc)], evidence=ev, step=i,
                    extra={"container": cont, "escape_releases": escaped, "blocked_step": label},
                ))
            elif target and not target["tabbable"]:
                highlight(page, target["selector"], "Mouse can click, keyboard cannot reach")
                ev = shot(page, ev_dir, f"05_step{i}_unfocusable")
                clear_highlight(page)
                reason = (f"'{label}' is a <{target['tag']}> that a mouse can click, but it is not in the Tab order "
                          f"(no tabindex / not a real button or link).")
                step_rec.update({"reason": reason, "kind": "not_focusable", "screenshot": ev})
                result["findings"].append(make_finding(
                    rule="journey-not-focusable", title=f"Journey blocked: '{label}' cannot be reached by keyboard",
                    severity="critical", condition="keyboard", source="journey", description=reason,
                    wcag=["2.1.1 Keyboard (A)", "4.1.2 Name, Role, Value (A)"],
                    help_url="https://www.w3.org/WAI/WCAG22/Understanding/keyboard",
                    elements=[{"selector": target["selector"], "html": target["html"]}], evidence=ev, step=i,
                ))
            elif target:
                ev = shot(page, ev_dir, f"05_step{i}_notreached")
                reason = f"'{label}' is focusable but was not reached after {len(visited)} Tab presses."
                step_rec.update({"reason": reason, "kind": "too_far", "screenshot": ev})
                result["findings"].append(make_finding(
                    rule="journey-too-many-tabs", title=f"'{label}' takes too many Tab presses",
                    severity="serious", condition="keyboard", source="journey", description=reason,
                    wcag=["2.4.3 Focus Order (A)", "2.4.1 Bypass Blocks (A)"],
                    elements=[{"selector": target["selector"]}], evidence=ev, step=i,
                ))
            else:
                ev = shot(page, ev_dir, f"05_step{i}_missing")
                reason = f"Could not find a control called '{label}' on this page (check the journey step names)."
                step_rec.update({"reason": reason, "kind": "not_found", "screenshot": ev})
            result["steps"].append(step_rec)
            result["failed_step"] = i
            result["passed"] = False if step_rec["kind"] != "not_found" else None
            for rest_i, rest in enumerate(steps[i:], start=i + 1):
                result["steps"].append({"index": rest_i, "label": rest, "status": "not_reached"})
            return result

        result["passed"] = True
        return result
    finally:
        ctx.close()


# ---------------------------------------------------------------- axe-core
AXE_CONDITION = {
    "keyboard": {"tabindex", "scrollable-region-focusable", "focus-order-semantics", "nested-interactive",
                 "frame-focusable-content", "accesskeys"},
    "mobile": {"target-size", "meta-viewport", "meta-viewport-large", "css-orientation-lock"},
    "general": {"color-contrast", "color-contrast-enhanced", "link-in-text-block"},
}


def _axe_condition(rule_id: str) -> str:
    for cond, ids in AXE_CONDITION.items():
        if rule_id in ids:
            return cond
    return "screen_reader"


def _wcag_from_tags(tags):
    out = []
    for t in tags:
        m = re.fullmatch(r"wcag(\d)(\d)(\d+)", t)
        if m:
            out.append(f"{m.group(1)}.{m.group(2)}.{m.group(3)}")
    return out


def run_axe(page: Page, ev_dir: Path | None = None, tag: str = "desktop") -> list:
    page.evaluate(_axe_source())
    res = page.evaluate(
        """async () => { const r = await axe.run(document, {resultTypes:['violations']});
           return r.violations.map(v => ({id:v.id, impact:v.impact, help:v.help, description:v.description,
             helpUrl:v.helpUrl, tags:v.tags,
             nodes:v.nodes.slice(0,10).map(n=>({target:n.target.join(' '), html:n.html.slice(0,200), summary:n.failureSummary})),
             total:v.nodes.length })); }"""
    )
    findings = []
    for v in res:
        f = make_finding(
            rule=v["id"], title=v["help"], severity=v.get("impact") or "moderate",
            condition=_axe_condition(v["id"]), source="axe", description=v["description"],
            wcag=_wcag_from_tags(v["tags"]), help_url=v["helpUrl"],
            elements=[{"selector": n["target"], "html": n["html"], "summary": n["summary"]} for n in v["nodes"]],
            extra={"viewport": tag},
        )
        f["count"] = v["total"]
        findings.append(f)
    return findings


# ---------------------------------------------------------------- screen reader
def screen_reader_checks(page: Page) -> tuple[list, str]:
    _ensure_helpers(page)
    data = page.evaluate(
        """() => {
          const NATIVE = 'a,button,input,select,textarea,summary,label,option';
          const clickable = [...document.querySelectorAll('div,span,li,img,p,td')].filter(e => {
            if (!__ap.visible(e) || e.closest(NATIVE) || e.getAttribute('role')) return false;
            const hasHandler = e.hasAttribute('onclick') || typeof e.onclick === 'function';
            const pointer = getComputedStyle(e).cursor === 'pointer' && (!e.parentElement || getComputedStyle(e.parentElement).cursor !== 'pointer');
            return hasHandler || pointer;
          }).slice(0,10).map(e => ({selector:__ap.sel(e), text:__ap.name(e), html:e.outerHTML.slice(0,160)}));
          const vague = [...document.querySelectorAll('a[href]')].filter(a => /^(click here|here|read more|more|link|learn more)$/i.test(__ap.name(a)))
            .slice(0,10).map(a => ({selector:__ap.sel(a), text:__ap.name(a)}));
          const h1 = document.querySelectorAll('h1').length;
          const levels = [...document.querySelectorAll('h1,h2,h3,h4,h5,h6')].map(h=>+h.tagName[1]);
          let skipped = [];
          for (let i=1;i<levels.length;i++) if (levels[i]-levels[i-1]>1) skipped.push('h'+levels[i-1]+' → h'+levels[i]);
          return {clickable, vague, h1, skipped};
        }"""
    )
    findings = []
    if data["clickable"]:
        findings.append(make_finding(
            rule="clickable-div", title="Clickable elements without a role", severity="serious",
            condition="screen_reader", source="screen_reader",
            description="These elements act like buttons for mouse users, but screen readers announce them as plain text and keyboards skip them.",
            wcag=["4.1.2 Name, Role, Value (A)", "2.1.1 Keyboard (A)"],
            help_url="https://www.w3.org/WAI/WCAG22/Understanding/name-role-value", elements=data["clickable"],
        ))
    if data["vague"]:
        findings.append(make_finding(
            rule="vague-link-text", title="Links with unclear text", severity="minor", condition="screen_reader",
            source="screen_reader",
            description="Screen reader users often list all links. 'Click here' or 'Read more' says nothing out of context.",
            wcag=["2.4.4 Link Purpose (A)"], elements=data["vague"],
        ))
    if data["skipped"]:
        findings.append(make_finding(
            rule="heading-skip", title="Heading levels are skipped", severity="minor", condition="screen_reader",
            source="screen_reader",
            description="Heading order jumps (" + ", ".join(data["skipped"][:4]) + "). Screen reader users navigate by headings.",
            wcag=["1.3.1 Info and Relationships (A)"],
        ))
    tree = ""
    try:
        tree = page.locator("body").aria_snapshot()[:4000]
    except Exception:
        pass
    return findings, tree


# ---------------------------------------------------------------- mobile
def mobile_checks(browser: Browser, url: str, ev_dir: Path) -> tuple[list, dict]:
    ctx = new_context(browser, mobile=True)
    page = ctx.new_page()
    findings = []
    try:
        goto(page, url)
        _ensure_helpers(page)
        data = page.evaluate(
            """() => {
              const vw = window.innerWidth;
              const overflow = document.documentElement.scrollWidth - vw;
              const small = []; const rects = [];
              for (const e of __ap.tabbables()) {
                if (e.tagName==='A' && e.closest('p')) continue;   // inline text links are exempt
                const r = e.getBoundingClientRect();
                if (r.width < 24 || r.height < 24) small.push({selector:__ap.sel(e), text:__ap.name(e), size:Math.round(r.width)+'x'+Math.round(r.height)});
                rects.push({e, r});
              }
              const overlap = [];
              for (let i=0;i<rects.length && overlap.length<6;i++) for (let j=i+1;j<rects.length;j++){
                const a=rects[i].r, b=rects[j].r;
                if (rects[i].e.contains(rects[j].e) || rects[j].e.contains(rects[i].e)) continue;
                const ix=Math.max(0,Math.min(a.right,b.right)-Math.max(a.left,b.left)), iy=Math.max(0,Math.min(a.bottom,b.bottom)-Math.max(a.top,b.top));
                if (ix*iy > 40) { overlap.push({selector:__ap.sel(rects[i].e)+'  ⟷  '+__ap.sel(rects[j].e), text:__ap.name(rects[i].e)+' / '+__ap.name(rects[j].e)}); break; }
              }
              const offscreen = __ap.tabbables().filter(e => { const r=e.getBoundingClientRect(); return r.right > vw + 2 && r.left < vw*3; })
                 .slice(0,8).map(e=>({selector:__ap.sel(e), text:__ap.name(e)}));
              const meta = document.querySelector('meta[name=viewport]');
              return {vw, overflow, small: small.slice(0,15), smallTotal: small.length, overlap, offscreen,
                      viewport: meta ? meta.getAttribute('content') : ''};
            }"""
        )
        ev = shot(page, ev_dir, "06_mobile")
        if not data["viewport"]:
            findings.append(make_finding(
                rule="no-viewport-meta", title="Page is not set up for phones", severity="serious", condition="mobile",
                source="mobile", description="There is no <meta name=\"viewport\"> tag, so phones show a tiny zoomed-out desktop page.",
                wcag=["1.4.10 Reflow (AA)"], evidence=ev,
            ))
        if data["overflow"] > 4:
            findings.append(make_finding(
                rule="horizontal-scroll", title="Page scrolls sideways on a phone", severity="serious", condition="mobile",
                source="mobile",
                description=f"At {data['vw']}px wide the page is {data['overflow']}px too wide. Users must scroll left/right to read and reach controls.",
                wcag=["1.4.10 Reflow (AA)"], help_url="https://www.w3.org/WAI/WCAG22/Understanding/reflow",
                elements=data["offscreen"], evidence=ev,
            ))
        if data["small"]:
            f = make_finding(
                rule="small-touch-target", title="Touch targets are too small", severity="serious", condition="mobile",
                source="mobile",
                description=f"{data['smallTotal']} control(s) are smaller than 24×24 px, so they are hard to tap with a finger.",
                wcag=["2.5.8 Target Size (Minimum) (AA)"], help_url="https://www.w3.org/WAI/WCAG22/Understanding/target-size-minimum",
                elements=data["small"], evidence=ev,
            )
            f["count"] = data["smallTotal"]
            findings.append(f)
        if data["overlap"]:
            findings.append(make_finding(
                rule="overlapping-controls", title="Controls overlap on a phone", severity="serious", condition="mobile",
                source="mobile", description="Two controls sit on top of each other, so a tap may hit the wrong one.",
                wcag=["2.5.8 Target Size (Minimum) (AA)"], elements=data["overlap"], evidence=ev,
            ))
        try:
            for f in run_axe(page, tag="mobile"):
                if f["condition"] == "mobile":
                    f["evidence"] = ev
                    findings.append(f)
        except Exception:
            pass
        return findings, {"viewport_width": data["vw"], "screenshot": ev, "meta_viewport": data["viewport"]}
    finally:
        ctx.close()


# ---------------------------------------------------------------- fast local agent
STOP_WORDS = {"the", "and", "for", "with", "then", "into", "from", "that", "this", "your", "you", "our", "its", "page",
              "website", "site", "user", "users", "reach", "open", "find", "go", "get", "click", "able", "should", "will"}
ACTION_WORDS = {"cart", "checkout", "buy", "add", "book", "apply", "submit", "continue", "next", "pay", "send", "search",
                "login", "sign", "register", "enroll", "order", "confirm", "start", "play", "contact", "subscribe", "basket"}


def _words(text: str) -> list[str]:
    return [w for w in re.findall(r"[a-z0-9]+", (text or "").lower()) if len(w) > 2 and w not in STOP_WORDS]


def fast_agent(browser: Browser, url: str, task: str, max_steps: int = 6) -> dict:
    """A quick built-in agent: on each page it clicks the link or button whose words best
    match the task, like a mouse user would, and records the path. Takes seconds."""
    started = time.time()
    want = set(_words(task))
    stems = {w[:5] for w in want}
    ctx = new_context(browser)
    page = ctx.new_page()
    steps: list[str] = []
    try:
        goto(page, url)
        for _ in range(max_steps):
            _ensure_helpers(page)
            cands = page.evaluate(
                """() => [...document.querySelectorAll('a[href],button,[role=button],[role=link],input[type=submit],input[type=button],[onclick]')]
                     .filter(e => __ap.visible(e)).slice(0, 500)
                     .map((e, i) => { e.setAttribute('data-ap-c', i); return { i, name: __ap.name(e) }; })
                     .filter(c => c.name && c.name.length < 80)"""
            )
            done = {x.lower() for x in steps}
            best, best_score = None, 0.0
            for c in cands:
                if c["name"].lower() in done:
                    continue
                cw = _words(c["name"])
                if not cw:
                    continue
                hits = [w for w in cw if w in want or w[:5] in stems]
                score = 2 * len(hits) + sum(1 for w in hits if w in ACTION_WORDS)
                score = score / (1 + 0.15 * len(cw))      # prefer short, exact labels
                if score > best_score:
                    best, best_score = c, score
            if not best or best_score < 1:
                break
            steps.append(best["name"])
            try:
                page.click(f'[data-ap-c="{best["i"]}"]', timeout=5000)
            except Exception:
                break
            try:
                page.wait_for_load_state("domcontentloaded", timeout=8000)
            except Exception:
                pass
            page.wait_for_timeout(700)
    except Exception:
        pass
    finally:
        ctx.close()
    return {"steps": steps, "duration_s": round(time.time() - started, 1)}
