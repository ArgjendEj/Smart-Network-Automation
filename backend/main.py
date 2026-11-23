"""FastAPI application entrypoint."""
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import urlsplit

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from config import settings
from database import init_db
from routers import (
    auth,
    dashboard,
    devices,
    logs,
    manual_configuration,
    monitoring,
    smart_configuration,
    topology,
)
from seed import seed


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    seed()
    yield


app = FastAPI(title="Smart Network Automation Platform — MVP", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# A browser still running a cached UI from before the X-UI-Build header existed
# gets its HTTP cache wiped and is bounced to /login, which loads the fresh build.
@app.middleware("http")
async def evict_stale_ui(request: Request, call_next):
    path = request.url.path
    # the API docs page calls the API from a browser too, but is not our UI
    from_docs = urlsplit(request.headers.get("referer", "")).path in ("/docs", "/redoc")
    stale = (
        path.startswith("/api/")
        and "sec-fetch-site" in request.headers      # only real browsers send this
        and "x-ui-build" not in request.headers
        and not from_docs
    )
    clear = {"Clear-Site-Data": '"cache"'}
    if stale and not path.startswith(("/api/auth/login", "/api/auth/register")):
        return JSONResponse({"detail": "UI updated, please sign in again"}, 401, headers=clear)
    response = await call_next(request)
    if stale:
        response.headers.update(clear)
    return response

for r in (
    auth, dashboard, devices, topology, smart_configuration, manual_configuration, monitoring, logs
):
    app.include_router(r.router)


@app.get("/api/health")
def health():
    return {"status": "ok"}


# --- serve the built frontend (so the whole app is one instant URL) ----------
_DIST = Path(__file__).resolve().parent.parent / "frontend" / "dist"
if (_DIST / "index.html").exists():
    app.mount("/assets", StaticFiles(directory=_DIST / "assets"), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    def spa(full_path: str):
        if full_path.startswith(("api/", "docs", "redoc", "openapi.json")):
            raise HTTPException(status_code=404)
        candidate = _DIST / full_path
        if candidate.is_file():
            return FileResponse(candidate)
        # no-cache so the browser always picks up a freshly built UI
        return FileResponse(_DIST / "index.html", headers={"Cache-Control": "no-cache"})
