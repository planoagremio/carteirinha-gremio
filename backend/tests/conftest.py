"""
Configuração base dos testes — banco SQLite em memória (StaticPool),
sem tocar no banco real. Os env vars são forçados ANTES de qualquer import da app.
"""
import os

# Força env vars antes de qualquer import da aplicação
os.environ["DATABASE_URL"]           = "sqlite:///:memory:"
os.environ["SECRET_KEY"]             = "chave-de-teste-segura-123456789012"
os.environ["USUARIO"]                = "admin"
os.environ["SENHA_HASH"]             = "$2b$12$xBrMkinq54g/FTsx59TG5OyEbHudQh7dbVbnoSA6H7mNsegA9x55i"
os.environ["USUARIO_RECEPCAO"]       = "recepcao"
os.environ["SENHA_HASH_RECEPCAO"]    = "$2b$12$u1vYu5f2Z2GZKyF7QV7ExeTg1s2QidohyDd0yneYNz9KcNKN7/81q"
os.environ["AMBIENTE"]               = "desenvolvimento"
os.environ["CORS_ORIGINS"]           = "*"

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app

# StaticPool: todas as conexões compartilham o mesmo banco em memória
engine_test = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
SessionTest = sessionmaker(bind=engine_test)


def override_get_db():
    db = SessionTest()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db


@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.create_all(bind=engine_test)
    # Limpa rate limiter entre testes
    from app.routers.auth import _login_attempts
    _login_attempts.clear()
    yield
    Base.metadata.drop_all(bind=engine_test)
    _login_attempts.clear()


@pytest.fixture
def client():
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture
def token_admin(client):
    res = client.post("/api/auth/login", json={"username": "admin", "password": "admin123"})
    assert res.status_code == 200, f"Login admin falhou: {res.text}"
    return res.json()["access_token"]


@pytest.fixture
def token_recepcao(client):
    res = client.post("/api/auth/login", json={"username": "recepcao", "password": "recepcao123"})
    assert res.status_code == 200, f"Login recepção falhou: {res.text}"
    return res.json()["access_token"]


@pytest.fixture
def auth_admin(token_admin):
    return {"Authorization": f"Bearer {token_admin}"}


@pytest.fixture
def auth_recepcao(token_recepcao):
    return {"Authorization": f"Bearer {token_recepcao}"}


@pytest.fixture
def membro_base(client, auth_admin):
    """Cria e retorna um membro padrão para uso nos testes."""
    payload = {
        "id": "m_teste001",
        "username": "socioteste",
        "nome": "Sócio Teste",
        "doc": "123.456.789-00",
        "foto": None,
    }
    res = client.post("/api/membros/", json=payload, headers=auth_admin)
    assert res.status_code == 201, f"Criação do membro base falhou: {res.text}"
    return res.json()
