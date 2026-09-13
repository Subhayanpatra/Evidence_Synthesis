"""Single local server for the MedEvidence Hub applications.

Code lookup remains the existing Flask application and Evidence Synthesis
remains the AI_extract FastAPI application.  They are mounted beneath one
local website so the Hub cards do not require users to manage two URLs.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.wsgi import WSGIMiddleware

BASE_DIR = Path(__file__).resolve().parent
CODE_LOOKUP_DIR = BASE_DIR / "Intelligent Code Lookup"
EVIDENCE_SYNTHESIS_DIR = BASE_DIR / "Evidence Synthesis"
if not CODE_LOOKUP_DIR.is_dir() or not EVIDENCE_SYNTHESIS_DIR.is_dir():
    raise RuntimeError("The Code Lookup or Evidence Synthesis module is missing.")

# Both applications import modules from their own folder. Keep those module
# roots explicit so this launcher remains portable after the reorganization.
sys.path.insert(0, str(CODE_LOOKUP_DIR))
from app import app as code_lookup_app  # noqa: E402

sys.path.insert(0, str(EVIDENCE_SYNTHESIS_DIR))
from main import app as evidence_synthesis_app  # noqa: E402


app = FastAPI(title="MedEvidence Hub", docs_url=None, redoc_url=None)
app.mount("/hub-static", StaticFiles(directory=BASE_DIR / "static"), name="hub-static")
app.mount("/code-lookup", WSGIMiddleware(code_lookup_app), name="code-lookup")
app.mount("/evidence-synthesis", evidence_synthesis_app, name="evidence-synthesis")


@app.get("/", include_in_schema=False)
def hub_home() -> FileResponse:
    return FileResponse(BASE_DIR / "templates" / "hub.html")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "server:app",
        host=os.getenv("MEDEVIDENCE_HOST", "127.0.0.1"),
        port=int(os.getenv("MEDEVIDENCE_PORT", "5000")),
        reload=False,
    )
