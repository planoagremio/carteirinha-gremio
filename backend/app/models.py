from datetime import datetime
from sqlalchemy import String, Text, DateTime, Integer, ForeignKey, Boolean, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Membro(Base):
    __tablename__ = "membros"

    id: Mapped[str] = mapped_column(String(30), primary_key=True)
    username: Mapped[str | None] = mapped_column(String(60), unique=True, index=True, nullable=True)
    nome: Mapped[str] = mapped_column(String(255))
    doc: Mapped[str | None] = mapped_column(String(100), nullable=True)       # CPF formatado (exibição)
    cpf: Mapped[str | None] = mapped_column(String(11), unique=True, index=True, nullable=True)  # só dígitos
    senha_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    foto: Mapped[str | None] = mapped_column(Text, nullable=True)              # base64
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    fone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    matricula_gremio: Mapped[str | None] = mapped_column(String(30), nullable=True)
    socio_gpa_desde: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    aniversario: Mapped[str | None] = mapped_column(String(20), nullable=True)
    cidade: Mapped[str | None] = mapped_column(String(100), nullable=True)
    estado: Mapped[str | None] = mapped_column(String(2), nullable=True)
    ativo: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    criado_em: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class Checkin(Base):
    __tablename__ = "checkins"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    membro_id: Mapped[str] = mapped_column(String(30), ForeignKey("membros.id", ondelete="CASCADE"), index=True)
    nome: Mapped[str] = mapped_column(String(255))
    date: Mapped[str] = mapped_column(String(10), index=True)  # YYYY-MM-DD
    time: Mapped[str] = mapped_column(String(5))               # HH:MM
    ts: Mapped[datetime] = mapped_column(DateTime)
    registrado_por: Mapped[str | None] = mapped_column(String, nullable=True)
