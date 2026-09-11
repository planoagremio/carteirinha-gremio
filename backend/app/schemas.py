import re
from datetime import datetime
from pydantic import BaseModel, Field, field_validator

MAX_FOTO_BASE64_LEN = 933_000  # ~700KB em base64


class MembroCreate(BaseModel):
    id: str | None = None  # Ignorado pelo servidor — ID gerado internamente
    username: str
    nome: str
    doc: str | None = None
    foto: str | None = None

    @field_validator("nome")
    @classmethod
    def nome_nao_vazio(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Nome não pode ser vazio")
        return v

    @field_validator("username")
    @classmethod
    def username_valido(cls, v: str) -> str:
        v = v.strip().lower()
        if not v:
            raise ValueError("Username não pode ser vazio")
        if not re.match(r'^[a-z0-9_.-]{3,60}$', v):
            raise ValueError("Username só pode ter letras, números, . _ - (mín. 3 caracteres)")
        return v

    @field_validator("foto")
    @classmethod
    def foto_valida(cls, v: str | None) -> str | None:
        if v is None:
            return v
        _MIMES_PERMITIDOS = {"image/jpeg", "image/png", "image/webp"}
        if not v.startswith("data:image/"):
            raise ValueError("Foto deve ser um data URI de imagem")
        mime = v.split(";")[0].split(":")[1] if ";" in v and ":" in v else ""
        if mime not in _MIMES_PERMITIDOS:
            raise ValueError("Tipo de imagem não permitido. Use JPEG, PNG ou WebP")
        if len(v) > MAX_FOTO_BASE64_LEN:
            raise ValueError("Foto excede o tamanho máximo de 700KB")
        return v


class MembroOut(BaseModel):
    id: str
    username: str | None
    nome: str
    doc: str | None
    foto: str | None
    criado_em: datetime
    socio_gpa_desde: datetime | None = None
    matricula_gremio: str | None = None
    numero: int = 0
    ativo: bool = False

    model_config = {"from_attributes": True}


class MembroPublico(BaseModel):
    username: str | None
    nome: str
    doc: str | None
    foto: str | None
    numero: int = 0
    presidente: str = ""
    socio_gpa_desde: datetime | None = None
    matricula_gremio: str | None = None
    ativo: bool = False

    model_config = {"from_attributes": True}


class CheckinCreate(BaseModel):
    membro_id: str
    date: str   # YYYY-MM-DD
    time: str   # HH:MM
    ts: datetime

    @field_validator("membro_id")
    @classmethod
    def membro_id_valido(cls, v: str) -> str:
        if not re.match(r'^m_[a-z0-9]+$', v):
            raise ValueError("membro_id inválido")
        return v


class CheckinOut(BaseModel):
    id: int
    membro_id: str
    nome: str
    date: str
    time: str
    ts: datetime

    model_config = {"from_attributes": True}


class FotoInput(BaseModel):
    foto: str

    @field_validator("foto")
    @classmethod
    def foto_valida(cls, v: str) -> str:
        _MIMES_PERMITIDOS = {"image/jpeg", "image/png", "image/webp"}
        if not v.startswith("data:image/"):
            raise ValueError("Foto deve ser um data URI de imagem")
        mime = v.split(";")[0].split(":")[1] if ";" in v and ":" in v else ""
        if mime not in _MIMES_PERMITIDOS:
            raise ValueError("Tipo de imagem não permitido. Use JPEG, PNG ou WebP")
        if len(v) > MAX_FOTO_BASE64_LEN:
            raise ValueError("Foto excede o tamanho máximo de 700KB")
        return v


class TrocarSenhaInput(BaseModel):
    senha_atual: str = Field(min_length=1, max_length=128)
    nova_senha: str = Field(min_length=8, max_length=128)


class LoginInput(BaseModel):
    username: str
    password: str


class MembroImportItem(BaseModel):
    nome: str
    aniversario: str | None = None
    cidade: str | None = None
    estado: str | None = None
    matricula: str | None = None
    gpa_desde: str | None = None
    fone: str | None = None
    email: str | None = None
    cpf: str | None = None

class ImportarJsonInput(BaseModel):
    membros: list[MembroImportItem]
