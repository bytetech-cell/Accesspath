"""ACCESSPATH API (FastAPI).

Run:  python run.py      (from the backend folder, inside the venv)
Docs: http://127.0.0.1:8000/docs
"""
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, field_validator

from . import config, pipeline
from .database import Audit, SessionLocal, init_db
from .services import tinyfish

app = FastAPI(title="ACCESSPATH API", version="1.0.0",
              description="Autonomous Accessibility Auditor — TinyFish + Playwright + axe-core + LLM")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
init_db()

app.mount("/evidence", StaticFiles(directory=str(config.EVIDENCE_DIR)), name="evidence")

# ------------------------------------------------------------------ models
class Conditions(BaseModel):
    keyboard: bool = True
    screen_reader: bool = True
    mobile: bool = True


class AuditIn(BaseModel):
    url: str = Field(..., examples=["https://example.com"])
    task: str = Field(..., examples=["Add the wireless headphones to the cart and reach checkout"])
    steps: list[str] | str | None = Field(default=None, description="Optional journey steps, e.g. 'Products > Add to Cart > Cart > Checkout'")
    conditions: Conditions = Conditions()
    use_tinyfish: bool = True
    access_code: str | None = None

    @field_validator("url")
    @classmethod
    def check_url(cls, v):
        v = v.strip()
        if not v.startswith(("http://", "https://")):
            local = v.startswith(("localhost", "127.", "0.0.0.0", "192.168.", "10.", "[::1]"))
            v = ("http://" if local else "https://") + v
        return v

    def step_list(self) -> list[str]:
        if not self.steps:
            return []
        if isinstance(self.steps, str):
            import re
            parts = re.split(r"\s*(?:>|›|→|,|\n)\s*", self.steps)
        else:
            parts = self.steps
        return [p.strip() for p in parts if p and p.strip()]


def audit_summary(a: Audit) -> dict:
    return {"id": a.id, "parent_id": a.parent_id, "url": a.url, "task": a.task, "status": a.status,
            "task_status": a.task_status, "score": a.score, "issue_count": a.issue_count,
            "current_step": a.current_step, "created_at": a.created_at.isoformat() if a.created_at else None}


def audit_full(a: Audit, db) -> dict:
    out = audit_summary(a)
    out.update({"journey_steps": a.journey_steps, "conditions": a.conditions, "use_tinyfish": bool(a.use_tinyfish),
                "progress": a.progress, "result": a.result or {}, "error": a.error,
                "finished_at": a.finished_at.isoformat() if a.finished_at else None})
    if a.parent_id and a.status == "done":
        p = db.get(Audit, a.parent_id)
        if p and p.result:
            before = {f["id"]: f for f in p.result.get("findings", [])}
            after = {f["id"]: f for f in (a.result or {}).get("findings", [])}
            out["comparison"] = {
                "parent_id": p.id,
                "score_before": p.score, "score_after": a.score,
                "task_before": p.task_status, "task_after": a.task_status,
                "fixed": [{"id": k, "title": v["title"], "severity": v["severity"]} for k, v in before.items() if k not in after],
                "new": [{"id": k, "title": v["title"], "severity": v["severity"]} for k, v in after.items() if k not in before],
                "remaining": [{"id": k, "title": v["title"], "severity": v["severity"]} for k, v in after.items() if k in before],
            }
    return out


def _create(db, url, task, steps, conditions, use_tf, parent_id=None) -> Audit:
    a = Audit(url=url, task=task, journey_steps=steps, conditions=conditions, use_tinyfish=1 if use_tf else 0,
              parent_id=parent_id, status="queued", progress=pipeline.initial_progress())
    db.add(a)
    db.commit()
    pipeline.submit(a.id)
    return a


# ------------------------------------------------------------------ API
@app.get("/api/health")
def health():
    return {
        "ok": True,
        "tinyfish": "configured" if tinyfish.is_configured() else "missing TINYFISH_API_KEY",
        "access_required": bool(config.ACCESS_CODE),
        "llm": config.llm_provider(),
        "database": "postgresql" if config.DATABASE_URL.startswith("postgres") else "sqlite",
        "workflow": [{"n": n, "title": t, "subtitle": s} for n, _, t, s in pipeline.WORKFLOW],
    }


def check_code(code: str | None):
    if config.ACCESS_CODE and (code or "").strip() != config.ACCESS_CODE:
        raise HTTPException(403, "Wrong or missing access code. Ask the ACCESSPATH team for the code.")


class RerunIn(BaseModel):
    access_code: str | None = None


@app.post("/api/audits", status_code=201)
def create_audit(body: AuditIn):
    check_code(body.access_code)
    db = SessionLocal()
    try:
        a = _create(db, body.url, body.task.strip(), body.step_list(), body.conditions.model_dump(), body.use_tinyfish)
        return audit_summary(a)
    finally:
        db.close()


@app.get("/api/audits")
def list_audits(limit: int = 30):
    db = SessionLocal()
    try:
        rows = db.query(Audit).order_by(Audit.created_at.desc()).limit(limit).all()
        return [audit_summary(a) for a in rows]
    finally:
        db.close()


@app.get("/api/audits/{audit_id}")
def get_audit(audit_id: str):
    db = SessionLocal()
    try:
        a = db.get(Audit, audit_id)
        if not a:
            raise HTTPException(404, "Audit not found")
        return audit_full(a, db)
    finally:
        db.close()


@app.post("/api/audits/{audit_id}/rerun", status_code=201)
def rerun_audit(audit_id: str, body: RerunIn | None = None):
    """Workflow step 9: run the SAME journey again after the developer changed the site."""
    check_code(body.access_code if body else None)
    db = SessionLocal()
    try:
        a = db.get(Audit, audit_id)
        if not a:
            raise HTTPException(404, "Audit not found")
        if a.status in ("queued", "running"):
            raise HTTPException(409, "This audit is still running")
        new = _create(db, a.url, a.task, list(a.journey_steps or []), a.conditions or {}, bool(a.use_tinyfish),
                      parent_id=a.id)
        return audit_summary(new)
    finally:
        db.close()


@app.delete("/api/audits/{audit_id}")
def delete_audit(audit_id: str, code: str | None = None):
    check_code(code)
    db = SessionLocal()
    try:
        a = db.get(Audit, audit_id)
        if not a:
            raise HTTPException(404, "Audit not found")
        db.delete(a)
        db.commit()
        return {"deleted": audit_id}
    finally:
        db.close()


# ------------------------------------------------------------------ demo shop
# A small shop with real accessibility bugs (a keyboard trap in the side menu,
# missing alt text, unlabeled search, tiny icons). Flip "fixed" to simulate the
# developer fixing the site, then press "Fix & rerun".
DEMO_STATE = {"fixed": False}


class DemoState(BaseModel):
    fixed: bool
    access_code: str | None = None


def _demo_base() -> str:
    host = "127.0.0.1" if config.HOST in ("0.0.0.0", "", "::") else config.HOST
    return f"{config.PUBLIC_URL}/demo/" if config.PUBLIC_URL else f"http://{host}:{config.PORT}/demo/"


def _demo_sites() -> list[dict]:
    """ShopEasy + the generated fictional sites (demo_site/sites/sites.json)."""
    base = _demo_base()
    sites = [{"slug": "shopeasy", "name": "ShopEasy", "kind": "Online shop", "url": base,
              "task": "Add the wireless headphones to the cart and reach checkout",
              "steps": "Wireless Headphones > Add to Cart > Cart > Checkout"}]
    meta = config.DEMO_DIR / "sites" / "sites.json"
    if meta.is_file():
        import json
        for m in json.loads(meta.read_text(encoding="utf-8")):
            sites.append({"slug": m["slug"], "name": m["name"], "kind": m["kind"], "url": f"{base}{m['slug']}/",
                          "task": m["task"], "steps": m["steps"]})
    return sites


@app.get("/api/demo")
def demo_state():
    sites = _demo_sites()
    return {**DEMO_STATE, "url": sites[0]["url"], "task": sites[0]["task"], "steps": sites[0]["steps"], "sites": sites}


@app.post("/api/demo")
def set_demo_state(body: DemoState):
    check_code(body.access_code)
    DEMO_STATE["fixed"] = body.fixed
    return DEMO_STATE


@app.get("/demo/{page:path}")
def demo_page(page: str = ""):
    state = "fixed" if DEMO_STATE["fixed"] else "broken"
    parts = page.strip("/").split("/", 1)
    sites_dir = config.DEMO_DIR / "sites"
    if parts[0] and (sites_dir / parts[0]).is_dir():
        if len(parts) == 1 and not page.endswith("/"):
            return RedirectResponse(f"/demo/{parts[0]}/")
        folder = sites_dir / parts[0] / state
        name = parts[1] if len(parts) > 1 and parts[1] else "index.html"
    else:
        folder = config.DEMO_DIR / state
        name = page.strip("/") or "index.html"
    path = (folder / name).resolve()
    if not str(path).startswith(str(folder.resolve())) or not path.is_file():
        raise HTTPException(404, "Not found")
    return FileResponse(path, headers={"Cache-Control": "no-store"})


# ------------------------------------------------------------------ dashboard
@app.get("/", response_class=HTMLResponse)
def index():
    return FileResponse(config.FRONTEND_DIR / "index.html")


app.mount("/static", StaticFiles(directory=str(config.FRONTEND_DIR)), name="static")
