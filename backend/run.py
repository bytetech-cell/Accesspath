"""Start ACCESSPATH:  python run.py   (inside the venv, from the backend folder)."""
import uvicorn

from app import config

if __name__ == "__main__":
    print(f"\n  ACCESSPATH running at  http://{config.HOST}:{config.PORT}\n  API docs:              http://{config.HOST}:{config.PORT}/docs\n")
    # reload=False on purpose: Playwright + reload can break on Windows
    uvicorn.run("app.main:app", host=config.HOST, port=config.PORT, reload=False)
