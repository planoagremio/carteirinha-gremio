"""
Auditoria de seguranca - testes automatizados.

Cada teste demonstra uma vulnerabilidade ou confirma uma protecao.
Testes marcados com 'corrigido' verificam que a correcao foi aplicada.
"""
import pytest
from jose import jwt
from datetime import datetime, timedelta, timezone
from fastapi.testclient import TestClient
from app.main import app
from app.routers.auth import _login_attempts


@pytest.fixture(autouse=True)
def limpar_rate_limit():
    """Limpa o rate limiter entre testes."""
    _login_attempts.clear()
    yield
    _login_attempts.clear()


# ===========================================================================
# SEC-001: Rate limiting no login (brute force)
# ===========================================================================

class TestSEC001RateLimitLogin:
    """Verifica que o endpoint de login tem rate limiting contra brute force."""

    def test_muitas_tentativas_login_retorna_429(self, client):
        """Apos 10 tentativas erradas seguidas, deve retornar 429."""
        for i in range(10):
            client.post("/api/auth/login", json={
                "username": "admin", "password": f"tentativa{i}"
            })
        res = client.post("/api/auth/login", json={
            "username": "admin", "password": "tentativa_final"
        })
        # Apos a correcao, deve retornar 429
        assert res.status_code == 429, (
            "SEC-001: Sem rate limiting no login - brute force possivel"
        )


# ===========================================================================
# SEC-002: Falsificacao de checkin (date/time/ts fornecidos pelo cliente)
# ===========================================================================

class TestSEC002FalsificacaoCheckin:
    """Verifica que o servidor controla date/time/ts do checkin."""

    def test_checkin_data_retroativa_usa_data_do_servidor(self, client, auth_admin, membro_base):
        """Cliente nao deve conseguir criar checkin com data retroativa."""
        res = client.post("/api/checkins/", json={
            "membro_id": membro_base["id"],
            "date": "2020-01-01",
            "time": "03:00",
            "ts": "2020-01-01T03:00:00Z",
        }, headers=auth_admin)
        # Apos a correcao: servidor ignora date/time/ts do cliente
        # e usa a data/hora atual
        if res.status_code == 201:
            data = res.json()
            assert data["date"] != "2020-01-01", (
                "SEC-002: Servidor aceitou data retroativa do cliente"
            )

    def test_checkin_data_futura_usa_data_do_servidor(self, client, auth_admin, membro_base):
        """Cliente nao deve conseguir criar checkin com data futura."""
        res = client.post("/api/checkins/", json={
            "membro_id": membro_base["id"],
            "date": "2099-12-31",
            "time": "23:59",
            "ts": "2099-12-31T23:59:00Z",
        }, headers=auth_admin)
        if res.status_code == 201:
            data = res.json()
            assert data["date"] != "2099-12-31", (
                "SEC-002: Servidor aceitou data futura do cliente"
            )


# ===========================================================================
# SEC-003: Mass assignment - cliente fornece o ID do membro
# ===========================================================================

class TestSEC003MassAssignmentId:
    """Verifica que o servidor gera o ID, nao aceita do cliente."""

    def test_servidor_gera_id_do_membro(self, client, auth_admin):
        """O ID do membro deve ser gerado pelo servidor, nao pelo cliente."""
        res = client.post("/api/membros/", json={
            "id": "ID_ESCOLHIDO_PELO_ATACANTE",
            "username": "masstest",
            "nome": "Mass Assignment Test",
            "doc": None,
            "foto": None,
        }, headers=auth_admin)
        if res.status_code == 201:
            data = res.json()
            assert data["id"] != "ID_ESCOLHIDO_PELO_ATACANTE", (
                "SEC-003: Servidor aceitou ID fornecido pelo cliente"
            )


# ===========================================================================
# SEC-004: CORS allow_origins=* com allow_credentials=True
# ===========================================================================

class TestSEC004CorsCredentials:
    """Verifica que CORS nao combina * com credentials."""

    def test_cors_nao_reflete_origin_com_credentials(self, client):
        """Com allow_origins=* e credentials=true, o browser bloqueia.
        O servidor nao deve refletir a origin do atacante."""
        res = client.options(
            "/api/auth/login",
            headers={
                "Origin": "https://evil-site.com",
                "Access-Control-Request-Method": "POST",
            }
        )
        acl_origin = res.headers.get("access-control-allow-origin", "")
        acl_creds = res.headers.get("access-control-allow-credentials", "")
        # Nao deve ser a origin exata do atacante com credentials=true
        if acl_creds.lower() == "true":
            assert acl_origin != "https://evil-site.com", (
                "SEC-004: CORS reflete origin do atacante com credentials=true"
            )


# ===========================================================================
# SEC-005: Headers de seguranca ausentes
# ===========================================================================

class TestSEC005SecurityHeaders:
    """Verifica que headers de seguranca estao presentes."""

    def test_x_content_type_options(self, client, auth_admin):
        res = client.get("/api/membros/", headers=auth_admin)
        header = res.headers.get("x-content-type-options", "")
        assert header == "nosniff", (
            "SEC-005: Header X-Content-Type-Options ausente"
        )

    def test_x_frame_options(self, client, auth_admin):
        res = client.get("/api/membros/", headers=auth_admin)
        header = res.headers.get("x-frame-options", "")
        assert header.upper() in ("DENY", "SAMEORIGIN"), (
            "SEC-005: Header X-Frame-Options ausente"
        )

    def test_cache_control_em_dados_sensiveis(self, client, auth_admin):
        res = client.get("/api/membros/", headers=auth_admin)
        cache = res.headers.get("cache-control", "")
        assert "no-store" in cache.lower() or "no-cache" in cache.lower(), (
            "SEC-005: Dados sensiveis sem Cache-Control restritivo"
        )


# ===========================================================================
# SEC-010: Mass assignment - criado_em nao deve ser aceito
# ===========================================================================

class TestSEC010MassAssignmentCriadoEm:
    """Verifica que o campo criado_em nao pode ser enviado pelo cliente."""

    def test_criado_em_ignorado_no_payload(self, client, auth_admin):
        """O campo criado_em deve ser gerado pelo servidor."""
        res = client.post("/api/membros/", json={
            "id": "m_criado",
            "username": "criadotest",
            "nome": "Teste Criado Em",
            "doc": None,
            "foto": None,
            "criado_em": "2000-01-01T00:00:00",
        }, headers=auth_admin)
        # Pydantic deve rejeitar (422) ou ignorar o campo extra
        if res.status_code == 201:
            data = res.json()
            assert data["criado_em"] != "2000-01-01T00:00:00", (
                "SEC-010: Servidor aceitou criado_em do cliente"
            )
        # 422 = campo extra rejeitado (tambem aceitavel)


# ===========================================================================
# SEC-013: Token sem role defaults para admin
# ===========================================================================

class TestSEC013TokenRoleDefault:
    """Verifica que token sem campo role nao recebe admin por default."""

    def test_token_sem_role_nao_e_admin(self, client):
        """Se o token nao tiver role, nao deve ser tratado como admin."""
        token = jwt.encode(
            {"sub": "testuser", "exp": datetime.now(timezone.utc) + timedelta(hours=8)},
            "chave-de-teste-segura-123456789012",
            algorithm="HS256",
        )
        res = client.post("/api/membros/", json={
            "id": "m_norole",
            "username": "norole",
            "nome": "Sem Role",
            "doc": None,
            "foto": None,
        }, headers={"Authorization": f"Bearer {token}"})
        # 401 (token invalido) ou 403 (nao admin) sao aceitaveis
        assert res.status_code in (401, 403), (
            "SEC-013: Token sem role foi tratado como admin"
        )


# ===========================================================================
# SEC-014: Endpoint publico nao vaza doc (CPF) - risco de privacidade
# ===========================================================================

class TestSEC014EndpointPublicoPrivacidade:
    """Verifica que dados sensiveis nao sao expostos no endpoint publico."""

    def test_endpoint_publico_expoe_doc(self, client, membro_base):
        """O campo doc (CPF) e exposto publicamente - verificar se e intencional."""
        res = client.get(f"/api/membros/publico/{membro_base['username']}")
        assert res.status_code == 200
        data = res.json()
        # doc (CPF) esta exposto na rota publica via MembroPublico schema
        # Isso pode ser um risco de privacidade
        if "doc" in data and data["doc"]:
            # Verifica que o CPF esta mascarado (contem *)
            doc = data["doc"]
            assert "*" in doc, (
                "SEC-014: CPF/documento exposto sem mascara no endpoint publico"
            )


# ===========================================================================
# SEC-015: Logout nao requer autenticacao (nao e critico mas deve funcionar)
# ===========================================================================

class TestSEC015Logout:
    def test_logout_sem_token_funciona(self, client):
        """Logout sem token nao deve retornar erro (idempotente)."""
        res = client.post("/api/auth/logout")
        assert res.status_code == 200


# ===========================================================================
# SEC-016: Checkin para qualquer membro_id (sem restricao de ownership)
# ===========================================================================

class TestSEC016CheckinQualquerMembro:
    """Qualquer usuario autenticado pode criar checkin para qualquer membro."""

    def test_recepcao_cria_checkin_para_qualquer_membro(self, client, auth_recepcao, membro_base):
        """Recepcionista pode registrar entrada de qualquer socio - por design."""
        res = client.post("/api/checkins/", json={
            "membro_id": membro_base["id"],
            "date": "2026-08-24",
            "time": "09:00",
            "ts": "2026-08-24T09:00:00Z",
        }, headers=auth_recepcao)
        assert res.status_code == 201


# ===========================================================================
# SEC-017: Frontend escapeHtml protege contra XSS
# ===========================================================================

class TestSEC017XSSProtection:
    """Verifica que dados com XSS sao armazenados como texto puro."""

    def test_nome_com_html_retorna_texto_puro(self, client, auth_admin):
        xss_payload = '<img src=x onerror="alert(1)">'
        res = client.post("/api/membros/", json={
            "id": "m_xss2",
            "username": "xsstest2",
            "nome": xss_payload,
            "doc": None,
            "foto": None,
        }, headers=auth_admin)
        assert res.status_code == 201
        data = res.json()
        # API retorna JSON, nao HTML — XSS depende do frontend usar escapeHtml
        assert data["nome"] == xss_payload


# ===========================================================================
# SEC-018: /health nao requer auth (por design)
# ===========================================================================

class TestSEC018Health:
    def test_health_publico(self, client):
        res = client.get("/health")
        assert res.status_code == 200
        assert res.json() == {"status": "ok"}
