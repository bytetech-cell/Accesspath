"""All settings come from backend/.env (copy .env.example to .env)."""
import os
from pathlib import Path

from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parent.parent
PROJECT_DIR = BACKEND_DIR.parent
load_dotenv(BACKEND_DIR / ".env")


def _bool(name: str, default: bool) -> bool:
    val = os.getenv(name)
    if val is None or val.strip() == "":
        return default
    return val.strip().lower() in ("1", "true", "yes", "on")


# --- TinyFish (journey agent) ---
TINYFISH_API_KEY = os.getenv("TINYFISH_API_KEY", "").strip()
TINYFISH_BASE_URL = os.getenv("TINYFISH_BASE_URL", "https://agent.tinyfish.ai").rstrip("/")
TINYFISH_TIMEOUT_SECONDS = int(os.getenv("TINYFISH_TIMEOUT_SECONDS", "300"))
# How long an audit waits for TinyFish before switching to the fast local agent.
TINYFISH_MAX_WAIT_SECONDS = int(os.getenv("TINYFISH_MAX_WAIT_SECONDS", "90"))

# --- LLM (explanations + fixes). Provider: auto | gemini | openai | anthropic | none ---
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "auto").strip().lower()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash").strip()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini").strip()
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "").strip()
ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-haiku-4-5").strip()

# --- Database: SQLite by default, PostgreSQL if you set DATABASE_URL ---
DATA_DIR = BACKEND_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)
EVIDENCE_DIR = DATA_DIR / "evidence"
EVIDENCE_DIR.mkdir(exist_ok=True)
DATABASE_URL = os.getenv("DATABASE_URL", "").strip() or f"sqlite:///{(DATA_DIR / 'accesspath.db').as_posix()}"

# --- Browser checks ---
HEADLESS = _bool("HEADLESS", True)
MAX_TABS_PER_STEP = int(os.getenv("MAX_TABS_PER_STEP", "60"))
PAGE_TIMEOUT_MS = int(os.getenv("PAGE_TIMEOUT_MS", "45000"))
# Use the Google Chrome installed on this computer (looks like a normal visitor to bot
# protection). Falls back to Playwright's bundled Chromium if Chrome isn't installed.
USE_SYSTEM_CHROME = _bool("USE_SYSTEM_CHROME", True)
# Some sites break HTTP/2 for automated browsers; set true only if you see ERR_HTTP2 errors.
DISABLE_HTTP2 = _bool("DISABLE_HTTP2", False)

# --- Server ---
HOST = os.getenv("HOST", "127.0.0.1")
PORT = int(os.getenv("PORT", "8000"))
# Public address of this app when hosted (Render sets RENDER_EXTERNAL_URL by itself).
# Used for the demo shop link, so TinyFish (cloud) can open the demo shop too.
PUBLIC_URL = (os.getenv("PUBLIC_URL") or os.getenv("RENDER_EXTERNAL_URL") or "").rstrip("/")
# If set, people must type this code to start an audit (protects your TinyFish credits).
ACCESS_CODE = os.getenv("ACCESS_CODE", "").strip()
# How many audits run at the same time. Use 1 on small servers (512 MB RAM).
AUDIT_WORKERS = int(os.getenv("AUDIT_WORKERS", "2"))

FRONTEND_DIR = PROJECT_DIR / "frontend"
DEMO_DIR = PROJECT_DIR / "demo_site"
AXE_JS_PATH = Path(__file__).resolve().parent / "vendor" / "axe.min.js"


def llm_provider() -> str:
    """Decide which LLM to use. 'none' means built-in fix library only."""
    if LLM_PROVIDER in ("gemini", "openai", "anthropic", "none"):
        return LLM_PROVIDER
    if GEMINI_API_KEY:
        return "gemini"
    if OPENAI_API_KEY:
        return "openai"
    if ANTHROPIC_API_KEY:
        return "anthropic"
    return "none"
