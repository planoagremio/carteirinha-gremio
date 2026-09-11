import io
import re
import time
import secrets
import unicodedata

from fastapi import APIRouter, Depends, HTTPException
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from sqlalchemy import func
from sqlalchemy.orm import Session

from passlib.context import CryptContext
from app.auth import get_usuario_atual, get_qualquer_autenticado, require_admin, hash_senha

# Custo reduzido apenas para import em lote (membros ficam inativos até validação)
_import_pwd = CryptContext(schemes=["bcrypt"], deprecated="auto", bcrypt__rounds=4)
from app.database import get_db, settings
from app.models import Membro
from app.schemas import MembroCreate, MembroOut, MembroPublico, FotoInput, ImportarJsonInput

router = APIRouter()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _gerar_id() -> str:
    ts = int(time.time() * 1000)
    rand = secrets.token_hex(4)
    digits = "0123456789abcdefghijklmnopqrstuvwxyz"
    result = []
    n = ts
    while n:
        result.append(digits[n % 36])
        n //= 36
    ts36 = "".join(reversed(result)) if result else "0"
    return f"m_{ts36}{rand}"


def _mascarar_doc(doc: str | None) -> str | None:
    if not doc:
        return doc
    digitos = [c for c in doc if c.isdigit()]
    if len(digitos) <= 3:
        return doc
    count_from_end = 0
    resultado = list(doc)
    for i in range(len(resultado) - 1, -1, -1):
        if resultado[i].isdigit():
            count_from_end += 1
            if count_from_end > 3:
                resultado[i] = "*"
    return "".join(resultado)


def _remover_acentos(texto: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFD", texto)
        if unicodedata.category(c) != "Mn"
    )


def _gerar_username(nome: str, db: Session) -> str:
    """Gera username único a partir do nome (primeironome + ultimonome)."""
    partes = _remover_acentos(nome.lower()).split()
    base = partes[0] if len(partes) == 1 else partes[0] + partes[-1]
    base = re.sub(r"[^a-z0-9]", "", base)
    if len(base) < 3:
        base = (base + "socio")[:20]
    username = base
    sufixo = 1
    while db.query(Membro).filter(Membro.username == username).first():
        username = f"{base}{sufixo}"
        sufixo += 1
    return username


def _senha_do_cpf(cpf_digits: str) -> str:
    """3 primeiros + 2 últimos dígitos do CPF."""
    if len(cpf_digits) < 5:
        return cpf_digits
    return cpf_digits[:3] + cpf_digits[-2:]


def _so_digitos(valor: str | None) -> str:
    if not valor:
        return ""
    return re.sub(r"\D", "", str(valor))


def _formatar_cpf(digitos: str) -> str:
    if len(digitos) == 11:
        return f"{digitos[:3]}.{digitos[3:6]}.{digitos[6:9]}-{digitos[9:]}"
    return digitos


# ---------------------------------------------------------------------------
# Rotas
# ---------------------------------------------------------------------------

@router.get("/")
def listar(db: Session = Depends(get_db), usuario: dict = Depends(get_usuario_atual)):
    membros = db.query(Membro).order_by(Membro.criado_em).all()
    result = []
    is_recepcao = usuario.get("role") == "recepcao"
    for i, m in enumerate(membros, 1):
        d = MembroOut.model_validate(m).model_dump()
        d["numero"] = i
        if is_recepcao:
            d["doc"] = _mascarar_doc(d["doc"])
        result.append(d)
    return JSONResponse(content=jsonable_encoder(result))


@router.post("/", response_model=MembroOut, status_code=201)
def criar(body: MembroCreate, db: Session = Depends(get_db), _: dict = Depends(require_admin)):
    novo_id = _gerar_id()
    if db.query(Membro).filter(Membro.username == body.username).first():
        raise HTTPException(status_code=409, detail="Username já está em uso")
    dados = body.model_dump(exclude={"id"})
    membro = Membro(id=novo_id, **dados)
    db.add(membro)
    db.commit()
    db.refresh(membro)
    return membro


@router.post("/importar", status_code=201)
def importar_xlsx(
    body: ImportarJsonInput,
    db: Session = Depends(get_db),
    _: dict = Depends(require_admin),
):
    """Importa sócios a partir de dados pré-parseados pelo frontend (SheetJS)."""
    import datetime as dt

    criados = []
    erros = []

    for idx, item in enumerate(body.membros, start=2):
        nome = (item.nome or "").strip()
        if not nome:
            erros.append({"linha": idx, "erro": "Nome vazio"})
            continue

        cpf_digits = _so_digitos(item.cpf or "")
        if cpf_digits and len(cpf_digits) != 11:
            erros.append({"linha": idx, "nome": nome, "erro": f"CPF inválido: {item.cpf}"})
            cpf_digits = ""

        if cpf_digits and db.query(Membro).filter(Membro.cpf == cpf_digits).first():
            erros.append({"linha": idx, "nome": nome, "erro": "CPF já cadastrado"})
            continue

        doc_formatado = _formatar_cpf(cpf_digits) if cpf_digits else None
        senha_plain   = _senha_do_cpf(cpf_digits) if cpf_digits else secrets.token_hex(4)
        senha_hash    = _import_pwd.hash(senha_plain)

        socio_desde = None
        if item.gpa_desde:
            try:
                socio_desde = dt.datetime.strptime(item.gpa_desde[:10], "%Y-%m-%d")
            except ValueError:
                pass

        username = _gerar_username(nome, db)
        membro = Membro(
            id=_gerar_id(),
            username=username,
            nome=nome,
            doc=doc_formatado,
            cpf=cpf_digits or None,
            senha_hash=senha_hash,
            email=item.email,
            fone=item.fone,
            matricula_gremio=item.matricula,
            socio_gpa_desde=socio_desde,
            aniversario=item.aniversario,
            cidade=item.cidade,
            estado=item.estado,
            ativo=True,
        )
        db.add(membro)
        try:
            db.flush()
            criados.append({"username": username, "nome": nome})
        except Exception as e:
            db.rollback()
            erros.append({"linha": idx, "nome": nome, "erro": "Erro ao salvar — verifique dados duplicados"})
            continue

    db.commit()
    return {"criados": len(criados), "erros": len(erros), "socios": criados, "detalhes_erros": erros}


@router.patch("/{membro_id}/validar")
def validar(membro_id: str, db: Session = Depends(get_db), _: dict = Depends(require_admin)):
    """Admin ativa ou desativa a carteirinha de um sócio."""
    membro = db.get(Membro, membro_id)
    if not membro:
        raise HTTPException(status_code=404, detail="Sócio não encontrado")
    membro.ativo = not membro.ativo
    db.commit()
    return {"id": membro_id, "ativo": membro.ativo}


@router.delete("/{membro_id}")
def remover(membro_id: str, db: Session = Depends(get_db), _: dict = Depends(require_admin)):
    membro = db.get(Membro, membro_id)
    if not membro:
        raise HTTPException(status_code=404, detail="Sócio não encontrado")
    db.delete(membro)
    db.commit()
    return {"ok": True}


@router.post("/minha-foto")
def atualizar_minha_foto(body: FotoInput, usuario: dict = Depends(get_usuario_atual), db: Session = Depends(get_db)):
    """Sócio atualiza a própria foto."""
    if usuario.get("role") != "socio":
        raise HTTPException(status_code=403, detail="Apenas sócios podem usar este endpoint")
    membro = db.get(Membro, usuario["membro_id"])
    if not membro or not membro.ativo:
        raise HTTPException(status_code=403, detail="Conta inativa ou não encontrada")
    membro.foto = body.foto
    db.commit()
    return {"ok": True}


@router.get("/publico/{username}", response_model=MembroPublico)
def publico(
    username: str,
    db: Session = Depends(get_db),
    usuario: dict = Depends(get_qualquer_autenticado),
):
    """
    Retorna dados da carteirinha.
    - Admin/Recepção: veem qualquer sócio
    - Sócio: vê apenas a própria carteirinha
    """
    membro = db.query(Membro).filter(Membro.username == username.lower()).first()
    if not membro:
        raise HTTPException(status_code=404, detail="Sócio não encontrado")

    # Sócio só pode ver a própria carteirinha
    if usuario["role"] == "socio" and usuario["sub"] != username.lower():
        raise HTTPException(status_code=403, detail="Acesso não autorizado")

    if not membro.ativo and usuario["role"] == "socio":
        raise HTTPException(status_code=403, detail="Carteirinha ainda não validada pelo administrador")

    dados = MembroPublico.model_validate(membro)
    dados.doc = _mascarar_doc(dados.doc)
    dados.numero = db.query(func.count(Membro.id)).filter(Membro.criado_em <= membro.criado_em).scalar() or 1
    dados.presidente = settings.presidente_gpa
    return dados
