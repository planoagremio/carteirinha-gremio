from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.auth import get_usuario_atual
from app.database import get_db
from app.models import Checkin, Membro
from app.schemas import CheckinCreate, CheckinOut

router = APIRouter()


@router.get("/", response_model=list[CheckinOut])
def listar(
    date: str = Query(..., description="Data no formato YYYY-MM-DD"),
    db: Session = Depends(get_db),
    _: dict = Depends(get_usuario_atual),
):
    try:
        datetime.strptime(date, "%Y-%m-%d")
    except ValueError:
        raise HTTPException(status_code=422, detail="Formato de data inválido. Use YYYY-MM-DD")
    return (
        db.query(Checkin)
        .filter(Checkin.date == date)
        .order_by(Checkin.time)
        .all()
    )


@router.post("/", response_model=CheckinOut, status_code=201)
def registrar(body: CheckinCreate, db: Session = Depends(get_db), usuario: dict = Depends(get_usuario_atual)):
    membro = db.get(Membro, body.membro_id)
    if not membro:
        raise HTTPException(status_code=404, detail="Sócio não encontrado")
    if not membro.ativo:
        raise HTTPException(status_code=403, detail="Carteirinha inativa")

    # SEC-002: Servidor controla date/time/ts — ignora valores do cliente
    agora = datetime.now()
    date_servidor = agora.strftime("%Y-%m-%d")
    time_servidor = agora.strftime("%H:%M")

    # Impede entrada duplicada no mesmo dia
    ja_entrou = (
        db.query(Checkin)
        .filter(Checkin.membro_id == body.membro_id, Checkin.date == date_servidor)
        .first()
    )
    if ja_entrou:
        raise HTTPException(status_code=409, detail="Sócio já registrou entrada hoje")

    checkin = Checkin(
        membro_id=body.membro_id,
        nome=membro.nome,
        date=date_servidor,
        time=time_servidor,
        ts=agora,
        registrado_por=usuario.get("sub"),
    )
    db.add(checkin)
    db.commit()
    db.refresh(checkin)
    return checkin
