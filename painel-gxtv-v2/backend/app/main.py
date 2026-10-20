"""Painel GXTV v2 — monta API + estáticos em /v2 sem tocar a raiz do painel atual."""

from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.routes.api import router as api_router

ROOT = Path(__file__).resolve().parents[2]
DIST = Path(os.environ.get("PAINEL_V2_DIST", str(ROOT / "frontend" / "dist")))

app = FastAPI(title="MN Tecnologia — painel", version="2.0.0-f7")


@app.on_event("startup")
def _auth_proprio() -> None:
    """Copia o hash do v1 uma vez. Não altera o arquivo do v1."""
    try:
        from app.core.auth import importar_credencial_v1

        importar_credencial_v1()
    except Exception:
        pass

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.environ.get("PAINEL_V2_CORS", "").split(",") if os.environ.get("PAINEL_V2_CORS") else [],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)


@app.get("/v2/api/{rest:path}")
async def alias_under_v2(rest: str):
    """Compat: alguns proxies passam /v2/api/... — redirecionamos mentalmente via rewrite nginx.
    Este handler só documenta; nginx deve mapear /v2/api -> /api/v2.
    """
    from fastapi.responses import JSONResponse

    return JSONResponse(
        {"ok": False, "motivo": "Use /api/v2/... (nginx deve reescrever /v2/api → /api/v2)"},
        status_code=404,
    )


def _index() -> FileResponse:
    index = DIST / "index.html"
    if not index.is_file():
        from fastapi.responses import HTMLResponse

        return HTMLResponse(  # type: ignore[return-value]
            "<h1>MN Tecnologia</h1><p>Build do front ausente. Rode npm run build em frontend/.</p>",
            status_code=503,
        )
    return FileResponse(index)


if DIST.is_dir() and (DIST / "index.html").is_file():
    assets = DIST / "assets"
    if assets.is_dir():
        app.mount("/v2/assets", StaticFiles(directory=str(assets)), name="assets")

    @app.get("/v2")
    @app.get("/v2/")
    async def v2_root():
        return _index()

    @app.get("/v2/{full_path:path}")
    async def v2_spa(full_path: str):
        # não engolir /v2/api — API fica em /api/v2
        if full_path.startswith("api/"):
            from fastapi.responses import JSONResponse

            return JSONResponse({"ok": False, "motivo": "API em /api/v2"}, status_code=404)
        candidate = DIST / full_path
        if candidate.is_file():
            return FileResponse(candidate)
        return _index()


@app.get("/")
async def root_hint():
    return {
        "service": "painel-gxtv-v2",
        "hint": "UI em /v2 — painel atual permanece na raiz",
        "phase": "F7",
    }
