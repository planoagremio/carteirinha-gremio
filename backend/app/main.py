import logging
from fastapi import FastAPI, Request, Response, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from starlette.middleware.base import BaseHTTPMiddleware
import os

from app.database import settings, engine, Base
from app.routers import auth, membros, checkins

logger = logging.getLogger(__name__)

Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Controle de Acesso — Grêmio",
    docs_url=None if settings.ambiente == "producao" else "/docs",
    redoc_url=None,
)


# SEC-005: Middleware de headers de seguranca
class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Cache-Control"] = "no-store"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self' cdnjs.cloudflare.com cdn.jsdelivr.net 'unsafe-inline'; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data: blob:; "
            "font-src 'self'; "
            "connect-src 'self'; "
            "frame-ancestors 'none';"
        )
        if settings.ambiente == "producao":
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        return response


app.add_middleware(SecurityHeadersMiddleware)


# SEC-004: CORS — nao permitir * com credentials=true
origins = [o.strip() for o in settings.cors_origins.split(",") if o.strip()]
has_wildcard = "*" in origins
if has_wildcard and settings.ambiente == "producao":
    # Em producao, forcar origens explicitas
    origins = []
if has_wildcard and settings.ambiente != "producao":
    logger.warning("CORS_ORIGINS=* em ambiente não-produção. Considere restringir origens.")

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=not has_wildcard,  # credentials=false quando origins=*
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router,     prefix="/api/auth",     tags=["auth"])
app.include_router(membros.router,  prefix="/api/membros",  tags=["membros"])
app.include_router(checkins.router, prefix="/api/checkins", tags=["checkins"])


@app.get("/health")
def health():
    return {"status": "ok"}

_base = os.path.dirname(os.path.abspath(__file__))
FRONTEND_PATH    = os.path.abspath(os.path.join(_base, "..", "..", "index.html"))
SOCIO_PATH       = os.path.abspath(os.path.join(_base, "..", "..", "socio.html"))
LOGIN_SOCIO_PATH = os.path.abspath(os.path.join(_base, "..", "..", "login-socio.html"))
SCANNER_PATH     = os.path.abspath(os.path.join(_base, "..", "..", "scanner.html"))
ASSETS_PATH      = os.path.abspath(os.path.join(_base, "..", "..", "assets"))

@app.get("/assets/{filename}")
def serve_asset(filename: str):
    if ".." in filename or "/" in filename or "\\" in filename:
        raise HTTPException(status_code=400)
    path = os.path.join(ASSETS_PATH, filename)
    if not os.path.isfile(path):
        raise HTTPException(status_code=404)
    return FileResponse(path)

@app.get("/")
def frontend():
    return FileResponse(FRONTEND_PATH)

@app.get("/login-socio")
def login_socio():
    return FileResponse(LOGIN_SOCIO_PATH)

@app.get("/scanner")
def scanner():
    return FileResponse(SCANNER_PATH)

@app.get("/socio/{username}")
def carteirinha_publica(username: str):
    return FileResponse(SOCIO_PATH)
