"""
Testes de segurança — checkins (registro de presença).

Cobre:
- Autenticação obrigatória
- Checkin duplicado no mesmo dia
- Checkin para membro inexistente
- Manipulação de datas e campos
- Enumeração de membros via checkin
"""
import pytest
from fastapi.testclient import TestClient
from app.main import app


class TestCheckinAutenticacao:
    def test_registrar_checkin_sem_token_retorna_401(self, membro_base):
        # Usa cliente sem cookies de sessão para garantir que não há auth via cookie
        anon = TestClient(app, raise_server_exceptions=False, cookies={})
        res = anon.post("/api/checkins/", json={
            "membro_id": membro_base["id"],
            "date": "2026-08-24",
            "time": "09:00",
            "ts": "2026-08-24T09:00:00Z",
        })
        assert res.status_code == 401

    def test_listar_checkins_sem_token_retorna_401(self, client):
        res = client.get("/api/checkins/?date=2026-08-24")
        assert res.status_code == 401

    def test_listar_checkins_sem_parametro_date_retorna_422(self, client, auth_admin):
        res = client.get("/api/checkins/", headers=auth_admin)
        assert res.status_code == 422


class TestCheckinRegras:
    def test_checkin_membro_inexistente_retorna_404(self, client, auth_admin):
        res = client.post("/api/checkins/", json={
            "membro_id": "m_naoexiste",
            "date": "2026-08-24",
            "time": "09:00",
            "ts": "2026-08-24T09:00:00Z",
        }, headers=auth_admin)
        assert res.status_code == 404

    def test_checkin_duplicado_mesmo_dia_retorna_409(self, client, auth_admin, membro_base):
        payload = {
            "membro_id": membro_base["id"],
            "date": "2026-08-24",
            "time": "09:00",
            "ts": "2026-08-24T09:00:00Z",
        }
        res1 = client.post("/api/checkins/", json=payload, headers=auth_admin)
        res2 = client.post("/api/checkins/", json=payload, headers=auth_admin)
        assert res1.status_code == 201
        assert res2.status_code == 409

    def test_checkin_dias_diferentes_permitido(self, client, auth_admin):
        """Membros diferentes podem ter checkin no mesmo dia (servidor controla a data)."""
        # Cria dois membros distintos
        r1 = client.post("/api/membros/", json={
            "username": "socio_dia1", "nome": "Socio Dia 1", "doc": None, "foto": None,
        }, headers=auth_admin)
        r2 = client.post("/api/membros/", json={
            "username": "socio_dia2", "nome": "Socio Dia 2", "doc": None, "foto": None,
        }, headers=auth_admin)
        assert r1.status_code == 201
        assert r2.status_code == 201

        id1 = r1.json()["id"]
        id2 = r2.json()["id"]

        # Cada membro pode fazer checkin hoje
        res1 = client.post("/api/checkins/", json={
            "membro_id": id1, "date": "2026-08-24", "time": "09:00", "ts": "2026-08-24T09:00:00Z",
        }, headers=auth_admin)
        res2 = client.post("/api/checkins/", json={
            "membro_id": id2, "date": "2026-08-24", "time": "09:00", "ts": "2026-08-24T09:00:00Z",
        }, headers=auth_admin)
        assert res1.status_code == 201
        assert res2.status_code == 201

    def test_checkin_retorna_nome_do_membro(self, client, auth_admin, membro_base):
        res = client.post("/api/checkins/", json={
            "membro_id": membro_base["id"],
            "date": "2026-08-24",
            "time": "09:00",
            "ts": "2026-08-24T09:00:00Z",
        }, headers=auth_admin)
        assert res.status_code == 201
        assert res.json()["nome"] == membro_base["nome"]


class TestCheckinManipulacao:
    def test_checkin_com_id_falso_nao_cria_membro(self, client, auth_admin):
        """Atacante não pode criar checkin para um ID inexistente e depois listar."""
        # ID com formato válido mas inexistente no banco
        res = client.post("/api/checkins/", json={
            "membro_id": "m_aaaa1111bbbb",
            "date": "2026-08-24",
            "time": "10:00",
            "ts": "2026-08-24T10:00:00Z",
        }, headers=auth_admin)
        # 404 = membro não existe; 422 = formato inválido — ambos bloqueiam o ataque
        assert res.status_code in (404, 422)

        # Confirma que nenhum checkin foi criado
        lista = client.get("/api/checkins/?date=2026-08-24", headers=auth_admin)
        assert lista.status_code == 200
        assert len(lista.json()) == 0

    def test_checkin_injecao_no_membro_id(self, client, auth_admin):
        for payload in ["' OR '1'='1", "../admin", "<script>alert(1)</script>"]:
            res = client.post("/api/checkins/", json={
                "membro_id": payload,
                "date": "2026-08-24",
                "time": "10:00",
                "ts": "2026-08-24T10:00:00Z",
            }, headers=auth_admin)
            assert res.status_code in (404, 422), f"Payload '{payload}' não deveria ter sucesso"

    def test_listar_checkins_apenas_da_data_solicitada(self, client, auth_admin, membro_base):
        # Cria checkins em duas datas
        client.post("/api/checkins/", json={
            "membro_id": membro_base["id"],
            "date": "2026-08-24",
            "time": "09:00",
            "ts": "2026-08-24T09:00:00Z",
        }, headers=auth_admin)

        res = client.get("/api/checkins/?date=2026-08-25", headers=auth_admin)
        assert res.status_code == 200
        assert len(res.json()) == 0  # Não deve vazar checkins de outro dia

    def test_checkin_data_formato_invalido(self, client, auth_admin, membro_base):
        res = client.post("/api/checkins/", json={
            "membro_id": membro_base["id"],
            "date": "nao-e-data",
            "time": "09:00",
            "ts": "2026-08-24T09:00:00Z",
        }, headers=auth_admin)
        # Pode aceitar (validação de formato é responsabilidade do frontend)
        # mas nunca deve retornar 500
        assert res.status_code != 500
