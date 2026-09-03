from datetime import datetime, timedelta, timezone

from fastapi import Cookie, Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
import jwt
from jwt.exceptions import InvalidTokenError as JWTError
from passlib.context import CryptContext

from app.database import settings

ALGORITHM = "HS256"
TOKEN_EXPIRE_HOURS = 8

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)


def verificar_senha(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def hash_senha(plain: str) -> str:
    return pwd_context.hash(plain)


def criar_token(username: str, role: str, membro_id: str | None = None) -> str:
    expire = datetime.now(timezone.utc) + timedelta(hours=TOKEN_EXPIRE_HOURS)
    payload: dict = {"sub": username, "role": role, "exp": expire}
    if membro_id:
        payload["membro_id"] = membro_id
    return jwt.encode(payload, settings.secret_key, algorithm=ALGORITHM)


def _decode(token: str) -> dict:
    try:
        return jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM])
    except JWTError:
        raise HTTPException(status_code=401, detail="Token inválido ou expirado")


def _get_token(
    token: str | None = Depends(oauth2_scheme),
    token_cookie: str | None = Cookie(None, alias="gremio_token"),
) -> str | None:
    return token or token_cookie


def get_usuario_atual(
    token: str | None = Depends(oauth2_scheme),
    token_cookie: str | None = Cookie(None, alias="gremio_token"),
) -> dict:
    """Aceita admin e recepcao (painel interno)."""
    t = token or token_cookie
    if not t:
        raise HTTPException(status_code=401, detail="Não autenticado")
    payload = _decode(t)
    if not payload.get("sub"):
        raise HTTPException(status_code=401, detail="Token inválido")
    role = payload.get("role")
    if role not in ("admin", "recepcao"):
        raise HTTPException(status_code=401, detail="Token inválido — role ausente ou inválida")
    return {"sub": payload["sub"], "role": role}


def get_qualquer_autenticado(
    token: str | None = Depends(oauth2_scheme),
    token_cookie: str | None = Cookie(None, alias="gremio_token"),
) -> dict:
    """Aceita admin, recepcao ou socio."""
    t = token or token_cookie
    if not t:
        raise HTTPException(status_code=401, detail="Não autenticado")
    payload = _decode(t)
    if not payload.get("sub"):
        raise HTTPException(status_code=401, detail="Token inválido")
    role = payload.get("role")
    if role not in ("admin", "recepcao", "socio"):
        raise HTTPException(status_code=401, detail="Token inválido")
    return {
        "sub": payload["sub"],
        "role": role,
        "membro_id": payload.get("membro_id"),
    }


def get_socio_atual(
    token: str | None = Depends(oauth2_scheme),
    token_cookie: str | None = Cookie(None, alias="gremio_token"),
) -> dict:
    """Aceita apenas socio."""
    t = token or token_cookie
    if not t:
        raise HTTPException(status_code=401, detail="Não autenticado")
    payload = _decode(t)
    if payload.get("role") != "socio":
        raise HTTPException(status_code=403, detail="Acesso restrito a sócios")
    return {
        "sub": payload["sub"],
        "role": "socio",
        "membro_id": payload.get("membro_id"),
    }


def require_admin(usuario: dict = Depends(get_usuario_atual)) -> dict:
    if usuario.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Acesso restrito a administradores")
    return usuario
