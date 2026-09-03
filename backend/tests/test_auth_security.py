"""
Testes de segurança — autenticação e autorização.

Cobre:
- Credenciais inválidas / ataques de força bruta
- Tokens forjados, expirados ou malformados
- Acesso sem autenticação
- Separação de papéis (admin vs recepção)
- Injeções nos campos de login
"""
import pytest
from jose import jwt
from datetime import datetime, timedelta, timezone


# ---------------------------------------------------------------------------
# LOGIN
# ---------------------------------------------------------------------------

class TestLogin:
    def test_login_admin_correto(self, client):
        res = client.post("/api/auth/login", json={"username": "admin", "password": "admin123"})
        assert res.status_code == 200
        data = res.json()
        assert "access_token" in data
        assert data["role"] == "admin"

    def test_login_recepcao_correto(self, client):
        res = client.post("/api/auth/login", json={"username": "recepcao", "password": "recepcao123"})
        assert res.status_code == 200
        assert res.json()["role"] == "recepcao"

    def test_login_senha_errada(self, client):
        res = client.post("/api/auth/login", json={"username": "admin", "password": "errada"})
        assert res.status_code == 401

    def test_login_usuario_inexistente(self, client):
        res = client.post("/api/auth/login", json={"username": "hacker", "password": "qualquer"})
        assert res.status_code == 401

    def test_login_campos_vazios(self, client):
        res = client.post("/api/auth/login", json={"username": "", "password": ""})
        assert res.status_code == 401

    def test_login_injecao_sql_usuario(self, client):
        res = client.post("/api/auth/login", json={"username": "' OR '1'='1", "password": "x"})
        assert res.status_code == 401

    def test_login_injecao_sql_senha(self, client):
        res = client.post("/api/auth/login", json={"username": "admin", "password": "' OR '1'='1"})
        assert res.status_code == 401

    def test_login_payload_malformado(self, client):
        res = client.post("/api/auth/login", content="nao-e-json", headers={"Content-Type": "application/json"})
        assert res.status_code == 422

    def test_login_nao_revela_qual_campo_esta_errado(self, client):
        """Mensagem de erro não deve indicar se foi o usuário ou a senha que falhou."""
        r1 = client.post("/api/auth/login", json={"username": "admin",  "password": "errada"})
        r2 = client.post("/api/auth/login", json={"username": "naoexiste", "password": "admin123"})
        assert r1.status_code == r2.status_code == 401
        assert r1.json()["detail"] == r2.json()["detail"]

    def test_multiplas_tentativas_retornam_401_depois_429(self, client):
        """Primeiras 5 tentativas retornam 401; a partir da 6ª retorna 429 (rate limit)."""
        for i in range(5):
            res = client.post("/api/auth/login", json={"username": "admin", "password": "tentativa"})
            assert res.status_code == 401, f"tentativa {i+1} deveria ser 401"
        # A partir da 6ª tentativa o rate limit deve bloquear
        res = client.post("/api/auth/login", json={"username": "admin", "password": "tentativa"})
        assert res.status_code == 429


# ---------------------------------------------------------------------------
# TOKEN JWT
# ---------------------------------------------------------------------------

class TestToken:
    def test_token_forjado_chave_diferente(self, client):
        token_falso = jwt.encode(
            {"sub": "admin", "role": "admin", "exp": datetime.now(timezone.utc) + timedelta(hours=8)},
            "chave-errada-do-atacante",
            algorithm="HS256",
        )
        res = client.get("/api/membros/", headers={"Authorization": f"Bearer {token_falso}"})
        assert res.status_code == 401

    def test_token_expirado(self, client):
        token_expirado = jwt.encode(
            {"sub": "admin", "role": "admin", "exp": datetime.now(timezone.utc) - timedelta(hours=1)},
            "chave-de-teste-segura-123456789012",
            algorithm="HS256",
        )
        res = client.get("/api/membros/", headers={"Authorization": f"Bearer {token_expirado}"})
        assert res.status_code == 401

    def test_token_sem_campo_sub(self, client):
        token_invalido = jwt.encode(
            {"role": "admin", "exp": datetime.now(timezone.utc) + timedelta(hours=8)},
            "chave-de-teste-segura-123456789012",
            algorithm="HS256",
        )
        res = client.get("/api/membros/", headers={"Authorization": f"Bearer {token_invalido}"})
        assert res.status_code == 401

    def test_token_malformado(self, client):
        res = client.get("/api/membros/", headers={"Authorization": "Bearer nao.e.um.jwt.valido"})
        assert res.status_code == 401

    def test_token_vazio(self, client):
        res = client.get("/api/membros/", headers={"Authorization": "Bearer "})
        assert res.status_code == 401

    def test_sem_token_retorna_401(self, client):
        for path in ["/api/membros/", "/api/checkins/?date=2026-01-01"]:
            res = client.get(path)
            assert res.status_code == 401, f"Esperava 401 em {path}"

    def test_token_com_role_inventada_nao_vira_admin(self, client):
        token = jwt.encode(
            {"sub": "hacker", "role": "superadmin", "exp": datetime.now(timezone.utc) + timedelta(hours=8)},
            "chave-de-teste-segura-123456789012",
            algorithm="HS256",
        )
        res = client.post("/api/membros/", json={
            "id": "m_hack", "username": "hack", "nome": "Hacker", "doc": None, "foto": None,
        }, headers={"Authorization": f"Bearer {token}"})
        # 401 (role invalida) ou 403 (nao admin) — ambos bloqueiam
        assert res.status_code in (401, 403)


# ---------------------------------------------------------------------------
# SEPARAÇÃO DE PAPÉIS
# ---------------------------------------------------------------------------

class TestPapeisAutorizacao:
    def test_recepcao_nao_pode_criar_membro(self, client, auth_recepcao):
        res = client.post("/api/membros/", json={
            "id": "m_novo", "username": "novosocio", "nome": "Novo", "doc": None, "foto": None,
        }, headers=auth_recepcao)
        assert res.status_code == 403

    def test_recepcao_nao_pode_deletar_membro(self, client, auth_recepcao, membro_base):
        res = client.delete(f"/api/membros/{membro_base['id']}", headers=auth_recepcao)
        assert res.status_code == 403

    def test_recepcao_pode_listar_membros(self, client, auth_recepcao):
        res = client.get("/api/membros/", headers=auth_recepcao)
        assert res.status_code == 200

    def test_recepcao_pode_registrar_checkin(self, client, auth_recepcao, membro_base):
        res = client.post("/api/checkins/", json={
            "membro_id": membro_base["id"],
            "date": "2026-08-24",
            "time": "09:00",
            "ts": "2026-08-24T09:00:00Z",
        }, headers=auth_recepcao)
        assert res.status_code == 201

    def test_admin_pode_criar_e_deletar_membro(self, client, auth_admin):
        res = client.post("/api/membros/", json={
            "id": "m_adm_test", "username": "admtest", "nome": "Admin Test", "doc": None, "foto": None,
        }, headers=auth_admin)
        assert res.status_code == 201
        membro_id = res.json()["id"]  # ID gerado pelo servidor
        res = client.delete(f"/api/membros/{membro_id}", headers=auth_admin)
        assert res.status_code == 200
