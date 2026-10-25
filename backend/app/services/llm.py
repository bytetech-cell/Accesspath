"""Workflow step 7: Explain & recommend.

Sends the journey result + top findings to an LLM (Gemini / OpenAI / Anthropic)
and asks for plain-language causes and code fixes. If no key is set, or the
LLM call fails, a built-in fix library is used so the report is never empty.
"""
import json
import re

import httpx

from .. import config

# Built-in plain-language fixes for the most common problems.
FIX_LIBRARY = {
    "focus-trap": ("A script catches the Tab key inside a menu and sends focus back to its first item, so keyboard users can never leave.",
                   "Remove the Tab-wrapping code (only modal dialogs should trap focus). Close the menu on Escape and move focus back to the button that opened it.",
                   "menu.addEventListener('keydown', e => {\n  if (e.key === 'Escape') { closeMenu(); menuButton.focus(); }\n  // do NOT call e.preventDefault() for Tab\n});"),
    "journey-focus-trap": ("Keyboard focus is stuck in a menu, so the user can never reach the next step of the journey.",
                           "Let Tab move out of the menu naturally, close it on Escape, and return focus to the trigger button.",
                           "menu.addEventListener('keydown', e => {\n  if (e.key === 'Escape') { closeMenu(); menuButton.focus(); }\n});\n// remove: if (e.key === 'Tab') { e.preventDefault(); items[next].focus(); }"),
    "journey-not-focusable": ("The control is a <div>/<span> with a click handler. Mouse works, but the keyboard and screen readers do not know it is a button.",
                              "Use a real <button> (or <a href> for navigation). If you cannot, add role=\"button\", tabindex=\"0\" and handle Enter/Space.",
                              "<!-- before -->\n<div class=\"btn\" onclick=\"checkout()\">Checkout</div>\n<!-- after -->\n<button type=\"button\" class=\"btn\" onclick=\"checkout()\">Checkout</button>"),
    "journey-too-many-tabs": ("The next control is very far down the Tab order.",
                              "Add a 'Skip to main content' link and keep the DOM order the same as the visual order.",
                              "<a class=\"skip-link\" href=\"#main\">Skip to main content</a>\n<main id=\"main\">...</main>"),
    "focus-visible": ("The CSS removes the focus outline (outline: none) and gives no other focus style.",
                      "Never remove the outline without a replacement. Add a clear :focus-visible style.",
                      ":focus-visible {\n  outline: 3px solid #2563eb;\n  outline-offset: 2px;\n}"),
    "skip-link": ("There is no shortcut to jump past the header and menu.",
                  "Add a skip link as the very first focusable element.",
                  "<a class=\"skip-link\" href=\"#main\">Skip to main content</a>"),
    "clickable-div": ("A generic element is used as a button.", "Replace it with <button> or <a href>.",
                      "<button type=\"button\" onclick=\"...\">Add to cart</button>"),
    "image-alt": ("Images have no alt text, so screen readers read the file name or nothing.",
                  "Add alt text that says what the image shows. Use alt=\"\" for decoration only.",
                  "<img src=\"headphones.jpg\" alt=\"Grey wireless over-ear headphones\">"),
    "label": ("A form field has no label, so screen readers just say 'edit text'.",
              "Connect a visible <label> to the input, or add aria-label.",
              "<label for=\"search\">Search products</label>\n<input id=\"search\" type=\"search\">"),
    "link-name": ("A link has no text (only an icon), so screen readers say just 'link'.",
                  "Add visible text, or an aria-label on the link, and hide the icon from screen readers.",
                  "<a href=\"/cart\" aria-label=\"Cart, 2 items\"><svg aria-hidden=\"true\">...</svg></a>"),
    "button-name": ("A button has no accessible name.", "Give the button text or an aria-label.",
                    "<button aria-label=\"Open menu\"><svg aria-hidden=\"true\">...</svg></button>"),
    "color-contrast": ("Text colour is too close to the background colour, so it is hard to read.",
                       "Use colours with at least 4.5:1 contrast for normal text (3:1 for large text).",
                       ".price-note { color: #4b5563; /* was #aaaaaa on white */ }"),
    "html-has-lang": ("The page does not say which language it is in, so screen readers may use the wrong voice.",
                      "Add a lang attribute to <html>.", "<html lang=\"en\">"),
    "document-title": ("The page has no <title>.", "Add a short, unique title.", "<title>Cart – ShopEasy</title>"),
    "meta-viewport": ("The viewport tag blocks pinch-zoom (user-scalable=no / maximum-scale=1).",
                      "Allow zoom so low-vision users can enlarge the page.",
                      "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">"),
    "small-touch-target": ("Buttons/icons are smaller than 24×24 px, so they are hard to tap.",
                           "Make every tap target at least 24×24 px (44×44 px is better) using padding.",
                           ".icon-btn { min-width: 44px; min-height: 44px; padding: 10px; }"),
    "target-size": ("Buttons/icons are too small or too close together.", "Give each target at least 24×24 px.",
                    ".icon-btn { min-width: 44px; min-height: 44px; }"),
    "horizontal-scroll": ("Some element has a fixed width wider than a phone screen.",
                          "Use max-width:100% and flexible layouts instead of fixed pixel widths.",
                          "img, table, .container { max-width: 100%; }\n.row { flex-wrap: wrap; }"),
    "no-viewport-meta": ("The page has no viewport tag.", "Add the standard viewport tag in <head>.",
                         "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">"),
    "region": ("Some content is not inside a landmark (header, nav, main, footer).",
               "Wrap the page in landmark elements so screen reader users can jump between areas.",
               "<header>...</header>\n<nav aria-label=\"Main\">...</nav>\n<main id=\"main\">...</main>"),
    "landmark-one-main": ("The page has no <main> landmark.", "Wrap the main content in <main>.", "<main id=\"main\">...</main>"),
    "page-has-heading-one": ("The page has no <h1>.", "Add one <h1> that names the page.", "<h1>Wireless Headphones</h1>"),
    "heading-skip": ("Heading levels jump (for example h1 → h3).", "Use headings in order without skipping levels.", "<h1>…</h1>\n<h2>…</h2>"),
    "vague-link-text": ("Link text like 'click here' has no meaning out of context.", "Describe the destination in the link text.",
                        "<a href=\"/returns\">Read our returns policy</a>"),
    "overlapping-controls": ("Two controls overlap on small screens.", "Add spacing or stack them vertically on mobile.",
                             "@media (max-width: 480px) { .actions { flex-direction: column; gap: 12px; } }"),
}


def _fallback(finding: dict) -> dict:
    cause, fix, code = FIX_LIBRARY.get(finding["rule"], (
        finding.get("description", ""),
        "Follow the WCAG guidance linked with this issue." + (f" ({finding['help_url']})" if finding.get("help_url") else ""),
        "",
    ))
    return {"explanation": cause, "fix": fix, "code": code}


def _prompt(context: dict) -> str:
    return (
        "You are an accessibility expert helping a web developer. Use simple, plain English.\n"
        "Below is an automated audit: a user journey attempted by an AI agent (TinyFish), a keyboard-only replay "
        "(Playwright) and rule checks (axe-core).\n\n"
        f"AUDIT DATA (JSON):\n{json.dumps(context, ensure_ascii=False)[:14000]}\n\n"
        "Return ONLY valid JSON with this shape:\n"
        '{"summary": "<2-3 sentences: can everyone finish the task? what is the biggest blocker?>",'
        ' "root_cause": "<1-2 sentences, the most likely technical cause of the journey failure, or empty if it passed>",'
        ' "priority_fix": "<the single most important change>",'
        ' "findings": [{"id": "<finding id from the data>", "explanation": "<why it hurts real users, 1-2 sentences>",'
        ' "fix": "<what to change, 1-2 sentences>", "code": "<short before/after code snippet>"}]}\n'
        "Include every finding id from the data in 'findings'. Keep code snippets under 8 lines."
    )


def _extract_json(text: str) -> dict:
    text = text.strip()
    text = re.sub(r"^```(?:json)?|```$", "", text, flags=re.M).strip()
    try:
        return json.loads(text)
    except Exception:
        m = re.search(r"\{.*\}", text, re.S)
        if m:
            return json.loads(m.group(0))
        raise


def _call_llm(provider: str, prompt: str) -> dict:
    with httpx.Client(timeout=90) as c:
        if provider == "gemini":
            r = c.post(
                f"https://generativelanguage.googleapis.com/v1beta/models/{config.GEMINI_MODEL}:generateContent",
                params={"key": config.GEMINI_API_KEY},
                json={"contents": [{"parts": [{"text": prompt}]}],
                      "generationConfig": {"responseMimeType": "application/json", "temperature": 0.2}},
            )
            r.raise_for_status()
            text = r.json()["candidates"][0]["content"]["parts"][0]["text"]
        elif provider == "openai":
            r = c.post(
                f"{config.OPENAI_BASE_URL}/chat/completions",
                headers={"Authorization": f"Bearer {config.OPENAI_API_KEY}"},
                json={"model": config.OPENAI_MODEL, "temperature": 0.2,
                      "response_format": {"type": "json_object"},
                      "messages": [{"role": "user", "content": prompt}]},
            )
            r.raise_for_status()
            text = r.json()["choices"][0]["message"]["content"]
        elif provider == "anthropic":
            r = c.post(
                "https://api.anthropic.com/v1/messages",
                headers={"x-api-key": config.ANTHROPIC_API_KEY, "anthropic-version": "2023-06-01"},
                json={"model": config.ANTHROPIC_MODEL, "max_tokens": 4000,
                      "messages": [{"role": "user", "content": prompt}]},
            )
            r.raise_for_status()
            text = "".join(b.get("text", "") for b in r.json()["content"] if b.get("type") == "text")
        else:
            raise ValueError("no provider")
    return _extract_json(text)


def explain(task: str, journey: dict, agent: dict | None, findings: list) -> dict:
    """Attach explanation/fix/code to every finding and build an overall summary."""
    for f in findings:
        f["ai"] = _fallback(f)
        f["ai_source"] = "library"

    blocked = next((s for s in journey.get("steps", []) if s.get("status") == "failed"), None)
    if journey.get("passed") is True:
        summary = "A keyboard-only user can finish the task. Fix the remaining issues so screen reader and mobile users have the same experience."
    elif blocked:
        summary = f"A keyboard-only user cannot finish the task. The journey stops at step '{blocked['label']}'. {blocked.get('reason', '')}"
    else:
        summary = "No journey steps were given or found, so only page-level checks were run."
    top = findings[0] if findings else None
    overall = {
        "summary": summary,
        "root_cause": (top["ai"]["explanation"] if top and journey.get("passed") is False else ""),
        "priority_fix": (top["ai"]["fix"] if top else "No issues found."),
        "provider": "built-in fix library",
    }

    provider = config.llm_provider()
    if provider == "none" or not findings:
        return overall

    context = {
        "task": task,
        "agent_journey": {k: (agent or {}).get(k) for k in ("success", "steps", "blocked_reason")} if agent else None,
        "keyboard_journey": [{k: s.get(k) for k in ("label", "status", "reason")} for s in journey.get("steps", [])],
        "findings": [{"id": f["id"], "title": f["title"], "severity": f["severity"], "condition": f["condition"],
                      "description": f["description"], "wcag": f["wcag"],
                      "elements": [e.get("html") or e.get("selector") for e in f["elements"][:3]]} for f in findings[:15]],
    }
    try:
        out = _call_llm(provider, _prompt(context))
    except Exception as e:  # keep the library answers
        overall["provider"] = f"built-in fix library (LLM {provider} failed: {str(e)[:120]})"
        return overall

    by_id = {f["id"]: f for f in findings}
    for item in out.get("findings", []) or []:
        f = by_id.get(item.get("id"))
        if not f:
            continue
        f["ai"] = {
            "explanation": item.get("explanation") or f["ai"]["explanation"],
            "fix": item.get("fix") or f["ai"]["fix"],
            "code": item.get("code") or f["ai"]["code"],
        }
        f["ai_source"] = provider
    overall.update({k: out[k] for k in ("summary", "root_cause", "priority_fix") if out.get(k)})
    overall["provider"] = {"gemini": f"Gemini ({config.GEMINI_MODEL})", "openai": f"OpenAI ({config.OPENAI_MODEL})",
                           "anthropic": f"Anthropic ({config.ANTHROPIC_MODEL})"}[provider]
    return overall
