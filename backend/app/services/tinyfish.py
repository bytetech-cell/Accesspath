"""TinyFish Web Agent client (workflow step 4: Attempt journey).

TinyFish opens the real website in its cloud browser and tries to finish the
user's task, like a normal mouse user would. We ask it to report back the exact
buttons/links it used. ACCESSPATH then replays that same path with ONLY the
keyboard (Playwright) to see if a keyboard user can finish it too.

Docs: https://docs.tinyfish.ai/key-concepts/endpoints
  POST {base}/v1/automation/run-async   -> {"run_id": ...}
  GET  {base}/v1/runs/{run_id}          -> {"status": PENDING|RUNNING|COMPLETED|FAILED|CANCELLED, "result": ...}
"""
import ipaddress
import json
import re
import time
from urllib.parse import urlparse

import httpx

from .. import config


class TinyFishError(Exception):
    pass


def is_configured() -> bool:
    return bool(config.TINYFISH_API_KEY)


def is_public_url(url: str) -> bool:
    """TinyFish runs in the cloud, so it cannot open localhost or LAN addresses."""
    host = (urlparse(url).hostname or "").lower()
    if not host or host == "localhost" or host.endswith(".local") or host.endswith(".localhost"):
        return False
    try:
        ip = ipaddress.ip_address(host)
        return not (ip.is_private or ip.is_loopback or ip.is_link_local)
    except ValueError:
        return True


def build_goal(task: str, hint_steps: list[str]) -> str:
    hint = ""
    if hint_steps:
        hint = "Expected path (hint, may differ on the real site): " + " > ".join(hint_steps) + ".\n"
    return (
        "You are testing a website for an accessibility audit.\n"
        f"TASK: {task}\n"
        f"{hint}"
        "Try to complete the task by clicking links/buttons like a normal user, using as few actions as possible (8 at most). "
        "Do NOT enter real personal or payment details; stop at the final review/checkout page if a payment is needed.\n"
        "When finished (or if you get blocked) return ONLY this JSON:\n"
        '{"success": true|false, '
        '"steps": [{"label": "<exact visible text of the link or button you clicked>", '
        '"action": "click|type|select", "page_title": "<title of the page you were on>", "url": "<page url>"}], '
        '"final_url": "<url at the end>", '
        '"blocked_reason": "<empty if success, else what stopped you>"}'
    )


def _headers():
    return {"X-API-Key": config.TINYFISH_API_KEY, "Content-Type": "application/json"}


def _parse_result(raw):
    """TinyFish may return a dict, a JSON string, or text with JSON inside it."""
    if raw is None:
        return {}
    if isinstance(raw, dict):
        # sometimes the useful payload is nested
        for key in ("result", "output", "data"):
            if isinstance(raw.get(key), (dict, str)) and "steps" not in raw:
                inner = _parse_result(raw[key])
                if inner.get("steps") is not None or "success" in inner:
                    return inner
        return raw
    if isinstance(raw, list):
        return {"steps": raw}
    if isinstance(raw, str):
        text = raw.strip()
        try:
            return _parse_result(json.loads(text))
        except Exception:
            match = re.search(r"\{.*\}", text, re.S)
            if match:
                try:
                    return _parse_result(json.loads(match.group(0)))
                except Exception:
                    pass
        return {"raw_text": text}
    return {"raw_text": str(raw)}


def run_journey(url: str, task: str, hint_steps: list[str], on_update=None) -> dict:
    """Start a TinyFish run, poll until done, return a clean summary."""
    if not is_configured():
        raise TinyFishError("TINYFISH_API_KEY is not set in backend/.env")

    body = {
        "url": url,
        "goal": build_goal(task, hint_steps),
        "agent_config": {"max_duration_seconds": min(config.TINYFISH_TIMEOUT_SECONDS, config.TINYFISH_MAX_WAIT_SECONDS)},
    }
    started = time.time()
    with httpx.Client(timeout=60) as client:
        r = client.post(f"{config.TINYFISH_BASE_URL}/v1/automation/run-async", headers=_headers(), json=body)
        if r.status_code >= 400:
            raise TinyFishError(f"TinyFish start failed ({r.status_code}): {r.text[:300]}")
        data = r.json()
        if data.get("error"):
            raise TinyFishError(f"TinyFish start failed: {data['error']}")
        run_id = data.get("run_id") or data.get("id")
        if not run_id:
            raise TinyFishError(f"TinyFish did not return a run_id: {str(data)[:300]}")
        if on_update:
            on_update(f"TinyFish run started ({run_id})", {"run_id": run_id})

        run = {}
        streaming_url = None
        last_status = None
        while True:
            if time.time() - started > min(config.TINYFISH_TIMEOUT_SECONDS, config.TINYFISH_MAX_WAIT_SECONDS) + 10:
                try:
                    client.post(f"{config.TINYFISH_BASE_URL}/v1/runs/{run_id}/cancel", headers=_headers())
                except Exception:
                    pass
                raise TinyFishError("TinyFish run timed out")
            time.sleep(2)
            g = client.get(f"{config.TINYFISH_BASE_URL}/v1/runs/{run_id}", headers=_headers())
            if g.status_code >= 400:
                raise TinyFishError(f"TinyFish status check failed ({g.status_code}): {g.text[:300]}")
            run = g.json()
            status = str(run.get("status", "")).upper()
            streaming_url = run.get("streaming_url") or run.get("streamingUrl") or streaming_url
            if on_update and status != last_status:
                on_update(f"TinyFish status: {status.lower()}", {"run_id": run_id, "streaming_url": streaming_url})
                last_status = status
            if status in ("COMPLETED", "FAILED", "CANCELLED", "ERROR"):
                break

    parsed = _parse_result(run.get("result"))
    steps = []
    for s in parsed.get("steps") or []:
        if isinstance(s, str):
            steps.append({"label": s, "action": "click"})
        elif isinstance(s, dict) and (s.get("label") or s.get("text")):
            steps.append({
                "label": str(s.get("label") or s.get("text")).strip(),
                "action": s.get("action", "click"),
                "page_title": s.get("page_title", ""),
                "url": s.get("url", ""),
            })

    if not steps:
        for st in run.get("steps") or []:
            act = str((st or {}).get("action") or "")
            m = re.search(r"['\"“]([^'\"”]{2,60})['\"”]", act)
            if m and re.search(r"click|tap|press|select", act, re.I):
                steps.append({"label": m.group(1).strip(), "action": "click"})
    status = str(run.get("status", "")).upper()
    err = run.get("error")
    if isinstance(err, dict):
        err = err.get("message") or json.dumps(err)
    success = bool(parsed.get("success")) if "success" in parsed else (status == "COMPLETED" and bool(steps))
    return {
        "run_id": run_id,
        "status": status,
        "success": success and status == "COMPLETED",
        "steps": steps,
        "final_url": parsed.get("final_url", ""),
        "blocked_reason": parsed.get("blocked_reason") or (err or ""),
        "streaming_url": streaming_url,
        "raw_text": parsed.get("raw_text", ""),
        "duration_s": round(time.time() - started, 1),
    }
