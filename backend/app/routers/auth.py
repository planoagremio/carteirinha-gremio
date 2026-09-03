import os
import time
from collections import defaultdict

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy.orm import Session

from app.auth import verificar_senha, criar_token, get_usuario_atual, get_qualquer_autenticado, TOKEN_EXPIRE_HOURS, pwd_context
from app.database import settings, get_db
from app.models import Membro
from app.schemas import LoginInput, TrocarSenhaInput

router = APIRouter()

TOKEN_EXPIRE_SECONDS = TOKEN_EXPIRE_HOURS * 3600

# SEC-001: Rate limiting simples para login (por IP)
_login_attempts: dict[str, list[float]] = defaultdict(list)
LOGIN_MAX_ATTEMPTS = 5
LOGIN_WINDOW_SECONDS = 300  # 5 minutos


def _check_rate_limit(request: Request):
    """Bloqueia se houve mais de LOGIN_MAX_ATTEMPTS em LOGIN_WINDOW_SECONDS."""
    ip = request.client.host if request.client else "unknown"
    now = time.time()
    _login_attempts[ip] = [t for t in _login_attempts[ip] if now - t < LOGIN_WINDOW_SECONDS]
    if len(_login_attempts[ip]) >= LOGIN_MAX_ATTEMPTS:
        raise HTTPException(status_code=429, detail="Muitas tentativas. Aguarde alguns minutos.")
    _login_attempts[ip].append(now)


def _set_cookie(response: Response, token: str):
    is_prod = os.getenv("AMBIENTE") == "producao"
    response.set_cookie(
        key="gremio_token",
        value=token,
        httponly=True,
        secure=is_prod,
        samesite="lax",
        max_age=TOKEN_EXPIRE_SECONDS,
        path="/",
    )


@router.post("/login")
def login(body: LoginInput, request: Request, response: Response, db: Session = Depends(get_db)):
    _check_rate_limit(request)

    role: str | None = None
    membro_id: str | None = None

    # 1. Verifica admin
    if settings.usuario and body.username == settings.usuario and verificar_senha(body.password, settings.senha_hash):
        role = "admin"

    # 2. Verifica recepção
    elif (
        settings.usuario_recepcao
        and body.username == settings.usuario_recepcao
        and verificar_senha(body.password, settings.senha_hash_recepcao)
    ):
        role = "recepcao"

    # 3. Verifica sócio na tabela de membros
    else:
        membro = db.query(Membro).filter(
            Membro.username == body.username.lower()
        ).first()
        if membro and membro.senha_hash and verificar_senha(body.password, membro.senha_hash):
            if not membro.ativo:
                raise HTTPException(status_code=403, detail="Carteirinha ainda não validada pelo administrador")
            role = "socio"
            membro_id = membro.id
        else:
            # Dummy bcrypt para equalizar timing (SEC-008)
            pwd_context.verify("dummy_password", settings.senha_hash)
            raise HTTPException(status_code=401, detail="Usuário ou senha incorretos")

    token = criar_token(body.username, role, membro_id=membro_id)
    _set_cookie(response, token)

    is_prod = os.getenv("AMBIENTE") == "producao"
    if is_prod:
        return {"ok": True, "role": role, "usuario": body.username}
    return {"access_token": token, "token_type": "bearer", "role": role, "membro_id": membro_id, "usuario": body.username}


@router.post("/logout")
def logout(response: Response):
    response.delete_cookie("gremio_token", path="/")
    return {"ok": True}


@router.get("/me")
def me(usuario: dict = Depends(get_qualquer_autenticado)):
    return {"usuario": usuario["sub"], "role": usuario["role"], "membro_id": usuario.get("membro_id")}


@router.post("/trocar-senha")
def trocar_senha(body: TrocarSenhaInput, usuario: dict = Depends(get_qualquer_autenticado), db: Session = Depends(get_db)):
    if usuario.get("role") != "socio":
        raise HTTPException(status_code=403, detail="Apenas sócios podem trocar a senha por aqui")
    membro = db.get(Membro, usuario["membro_id"])
    if not membro or not membro.ativo:
        raise HTTPException(status_code=403, detail="Conta inativa ou não encontrada")
    if not membro.senha_hash or not verificar_senha(body.senha_atual, membro.senha_hash):
        raise HTTPException(status_code=401, detail="Senha atual incorreta")
    membro.senha_hash = pwd_context.hash(body.nova_senha)
    db.commit()
    return {"ok": True}
