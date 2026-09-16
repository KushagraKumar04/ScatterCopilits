import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from . import db
from .config import APP_NAME, APP_VERSION, CORS_ORIGINS
from .routers.api import router as api_router

import time
import uuid
from fastapi import Request

app = FastAPI(title=APP_NAME, version=APP_VERSION)


@app.middleware("http")
async def _log_requests(request: Request, call_next):
    rid = uuid.uuid4().hex[:8]
    start = time.time()
    try:
        response = await call_next(request)
    except Exception as e:
        print(f"[{rid}] {request.method} {request.url.path} → EXC {type(e).__name__}: {e}")
        raise
    elapsed = (time.time() - start) * 1000
    print(f"[{rid}] {request.method} {request.url.path} → {response.status_code} ({elapsed:.0f}ms)")
    response.headers["X-Request-Id"] = rid
    return response

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def _startup():
    db.init_db()
    # Startup banner — one line answers "which provider is live?"
    from .deps import get_ai_settings
    from .services.ai_client import settings_from_env
    import os
    env = settings_from_env()
    print("─" * 60)
    print(f"  BPMN Copilot {APP_VERSION}")
    print(f"  DB              : {os.environ.get('BPMN_DB_PATH', 'default')}")
    print(f"  Default provider: {env.provider} / {env.model}")
    print(f"  LLMaaS env vars : "
          + ", ".join(f"{k}={'set' if os.environ.get(k) else 'MISSING'}"
                      for k in ("LLMAAS_API_KEY", "LLMAAS_CLIENT_ID",
                                "LLMAAS_CLIENT_SECRET", "LLMAAS_IDP_URL",
                                "LLMAAS_BASE_URL")))
    print("─" * 60)


app.include_router(api_router)

_DIST = os.path.join(os.path.dirname(__file__), "..", "..", "frontend", "dist")
if os.path.isdir(_DIST):
    app.mount("/assets", StaticFiles(directory=os.path.join(_DIST, "assets")), name="assets")

    @app.get("/{full_path:path}")
    def spa(full_path: str):
        candidate = os.path.join(_DIST, full_path)
        if full_path and os.path.isfile(candidate):
            return FileResponse(candidate)
        return FileResponse(os.path.join(_DIST, "index.html"))
