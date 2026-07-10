"""
run.py
───────
Dev server launcher.
Production: use `uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4`
"""
import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,        # auto-reload on file changes (dev only)
        log_level="info",
    )
