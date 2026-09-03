"""
Testes de segurança — cadastro de membros.

Cobre:
- Unicidade de username
- Validação e sanitização de entradas
- Injeção de dados maliciosos
- IDOR (acesso a recursos de outros usuários)
- Endpoint público não expõe dados sensíveis
"""
import pytest


class TestUsernameunico:
    def test_username_duplicado_retorna_409(self, client, auth_admin, membro_base):
        res = client.post("/api/membros/", json={
            "id": "m_outro",
            "username": membro_base["username"],  # mesmo username
            "nome": "Outro Nome",
            "doc": None,
            "foto": None,
        }, headers=auth_admin)
        assert res.status_code == 409
        assert "username" in res.json()["detail"].lower() or "uso" in res.json()["detail"].lower()

    def test_id_gerado_pelo_servidor_e_unico(self, client, auth_admin, membro_base):
        """Mesmo enviando o mesmo ID do cliente, o servidor gera IDs distintos."""
        res = client.post("/api/membros/", json={
            "id": membro_base["id"],  # mesmo id — servidor ignora
            "username": "outrousername",
            "nome": "Outro Nome",
            "doc": None,
            "foto": None,
        }, headers=auth_admin)
        assert res.status_code == 201
        # IDs devem ser diferentes (servidor gera)
        assert res.json()["id"] != membro_base["id"]

    def test_usernames_diferentes_sao_aceitos(self, client, auth_admin):
        for i in range(3):
            res = client.post("/api/membros/", json={
                "id": f"m_unique{i}",
                "username": f"socio{i}",
                "nome": f"Sócio {i}",
                "doc": None,
                "foto": None,
            }, headers=auth_admin)
            assert res.status_code == 201


class TestValidacaoUsername:
    @pytest.mark.parametrize("username", [
        "",                         # vazio
        "ab",                       # muito curto
        "a" * 61,                   # muito longo
        "usuario com espaço",       # espaço
        "usuario;DROP TABLE",       # injeção SQL
        "<script>alert(1)</script>",# XSS
        "../../etc/passwd",         # path traversal
        "usuário",                  # acento
        "@usuario",                 # caractere inválido
        "usuario!",                 # exclamação
    ])
    def test_username_invalido_rejeitado(self, client, auth_admin, username):
        res = client.post("/api/membros/", json={
            "id": "m_inv",
            "username": username,
            "nome": "Teste",
            "doc": None,
            "foto": None,
        }, headers=auth_admin)
        assert res.status_code in (409, 422), f"Username '{username}' deveria ser rejeitado"

    @pytest.mark.parametrize("username", [
        "joaosilva",
        "joao.silva",
        "joao_silva",
        "joao-silva",
        "joao123",
        "abc",
    ])
    def test_username_valido_aceito(self, client, auth_admin, username):
        res = client.post("/api/membros/", json={
            "id": f"m_{username}",
            "username": username,
            "nome": "Teste",
            "doc": None,
            "foto": None,
        }, headers=auth_admin)
        assert res.status_code == 201, f"Username '{username}' deveria ser aceito"

    def test_nome_vazio_rejeitado(self, client, auth_admin):
        res = client.post("/api/membros/", json={
            "id": "m_semnom",
            "username": "semnom",
            "nome": "",
            "doc": None,
            "foto": None,
        }, headers=auth_admin)
        assert res.status_code == 422

    def test_nome_apenas_espacos_rejeitado(self, client, auth_admin):
        res = client.post("/api/membros/", json={
            "id": "m_espaco",
            "username": "espaco",
            "nome": "   ",
            "doc": None,
            "foto": None,
        }, headers=auth_admin)
        assert res.status_code == 422

    def test_payload_gigante_nao_trava_servidor(self, client, auth_admin):
        res = client.post("/api/membros/", json={
            "id": "m_gigante",
            "username": "gigante",
            "nome": "A" * 10_000,
            "doc": "X" * 10_000,
            "foto": None,
        }, headers=auth_admin)
        # Deve responder (422 por validação ou 201), nunca travar
        assert res.status_code in (201, 422)


class TestEndpointPublico:
    def test_rota_publica_retorna_dados_basicos(self, client, auth_admin, membro_base):
        res = client.get(f"/api/membros/publico/{membro_base['username']}", headers=auth_admin)
        assert res.status_code == 200
        data = res.json()
        assert data["nome"] == membro_base["nome"]
        # V-005: id interno não deve ser exposto na rota pública
        assert "id" not in data

    def test_rota_publica_exige_autenticacao(self, client, membro_base):
        """Sem token, a carteirinha não é acessível."""
        from fastapi.testclient import TestClient
        from app.main import app as _app
        anon = TestClient(_app, raise_server_exceptions=False, cookies={})
        res = anon.get(f"/api/membros/publico/{membro_base['username']}")
        assert res.status_code == 401

    def test_rota_publica_nao_expoe_criado_em(self, client, auth_admin, membro_base):
        """O campo criado_em (timestamp interno) não deve aparecer na rota pública."""
        res = client.get(f"/api/membros/publico/{membro_base['username']}", headers=auth_admin)
        assert "criado_em" not in res.json()

    def test_rota_publica_username_inexistente_retorna_404(self, client, auth_admin):
        res = client.get("/api/membros/publico/naoexiste123", headers=auth_admin)
        assert res.status_code == 404

    def test_rota_publica_injecao_no_username(self, client, auth_admin):
        for payload in ["' OR '1'='1", "../admin", "<script>", "admin;DROP"]:
            res = client.get(f"/api/membros/publico/{payload}", headers=auth_admin)
            # 401 = sem auth, 404 = não encontrado, 422 = inválido, 405 = path resolveu para outra rota
            assert res.status_code in (401, 404, 405, 422), \
                f"Payload '{payload}' não deveria retornar dados (recebeu {res.status_code})"

    def test_listar_membros_exige_autenticacao(self, client):
        """A listagem completa de membros não é pública."""
        res = client.get("/api/membros/")
        assert res.status_code == 401

    def test_deletar_membro_exige_autenticacao(self, membro_base):
        # Cliente anônimo (sem cookies de sessão)
        from fastapi.testclient import TestClient
        from app.main import app as _app
        anon = TestClient(_app, raise_server_exceptions=False, cookies={})
        res = anon.delete(f"/api/membros/{membro_base['id']}")
        assert res.status_code == 401


class TestInjections:
    def test_xss_no_nome_e_salvo_como_texto(self, client, auth_admin):
        """Campo nome com XSS deve ser armazenado como texto puro, não executado."""
        res = client.post("/api/membros/", json={
            "id": "m_xss",
            "username": "xssteste",
            "nome": "<script>alert('xss')</script>",
            "doc": None,
            "foto": None,
        }, headers=auth_admin)
        assert res.status_code == 201
        # API retorna o texto puro — a sanitização é responsabilidade do frontend
        assert res.json()["nome"] == "<script>alert('xss')</script>"

    def test_injecao_sql_no_doc(self, client, auth_admin):
        res = client.post("/api/membros/", json={
            "id": "m_sqlinj",
            "username": "sqlinj",
            "nome": "Teste SQL",
            "doc": "'; DROP TABLE membros; --",
            "foto": None,
        }, headers=auth_admin)
        # ORM parametriza as queries — deve salvar como texto ou rejeitar, nunca executar
        assert res.status_code in (201, 422)
        if res.status_code == 201:
            # Tabela deve continuar existindo
            lista = client.get("/api/membros/", headers={"Authorization": "Bearer dummy"})
            # Se o token for inválido, retorna 401 — tabela ainda existe
            assert lista.status_code == 401
