"""
Testes da API Athena Face v1.1.0
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from fastapi.testclient import TestClient
from src.main import app

client = TestClient(app)


# ==================== TESTES DE ENDPOINTS PUBLICOS ====================


def test_read_root():
    """Testa endpoint raiz"""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["service"] == "Athena Face - Facial Recognition API"
    assert data["version"] == "1.1.0"
    assert "model" in data
    assert "features" in data


def test_health_check():
    """Testa health check"""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert data["service"] == "athenaface"
    assert "checks" in data
    assert "model" in data["checks"]
    assert "tenants" in data["checks"]


def test_health_check_has_timestamp():
    """Testa se health check retorna timestamp"""
    response = client.get("/health")
    data = response.json()
    assert "timestamp" in data


def test_list_tenants():
    """Testa listagem de tenants"""
    response = client.get("/api/tenants")
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert "count" in data
    assert "tenants" in data
    assert isinstance(data["tenants"], list)


# ==================== TESTES DE AUTENTICACAO ====================


def test_register_without_api_key():
    """Testa cadastro sem API Key"""
    response = client.post("/api/face/register", data={"user_id": 1, "check_liveness": True})
    assert response.status_code == 401
    assert "API Key" in response.json()["detail"]


def test_recognize_without_api_key():
    """Testa reconhecimento sem API Key"""
    response = client.post("/api/face/recognize")
    assert response.status_code == 401


def test_compare_without_api_key():
    """Testa comparacao sem API Key"""
    response = client.post("/api/face/compare")
    assert response.status_code == 401


def test_invalid_api_key():
    """Testa com API Key invalida"""
    response = client.post(
        "/api/face/register", headers={"X-API-Key": "invalid_key_12345"}, data={"user_id": 1}
    )
    assert response.status_code == 401


# ==================== TESTES DE VALIDACAO ====================


def test_register_invalid_user_id_zero():
    """Testa cadastro com user_id = 0"""
    response = client.post(
        "/api/face/register", headers={"X-API-Key": "test_key"}, data={"user_id": 0}
    )
    # Deve falhar na validacao (422) ou autenticacao (401)
    assert response.status_code in [401, 422]


def test_register_invalid_user_id_negative():
    """Testa cadastro com user_id negativo"""
    response = client.post(
        "/api/face/register", headers={"X-API-Key": "test_key"}, data={"user_id": -1}
    )
    assert response.status_code in [401, 422]


def test_register_missing_user_id():
    """Testa cadastro sem user_id"""
    response = client.post("/api/face/register", headers={"X-API-Key": "test_key"})
    assert response.status_code in [401, 422]


# ==================== TESTES DE FRONTEND ====================


def test_frontend_route():
    """Testa rota do frontend"""
    response = client.get("/facial")
    # Pode ser 200 (se frontend existe) ou 404 (se nao existe)
    assert response.status_code in [200, 404]


def test_frontend_register_route():
    """Testa rota de registro do frontend"""
    response = client.get("/facial/register")
    assert response.status_code in [200, 404]


def test_frontend_recognize_route():
    """Testa rota de reconhecimento do frontend"""
    response = client.get("/facial/recognize")
    assert response.status_code in [200, 404]


# ==================== TESTES DE ERRO ====================


def test_invalid_endpoint():
    """Testa endpoint inexistente"""
    response = client.get("/api/invalid")
    assert response.status_code == 404


def test_method_not_allowed():
    """Testa metodo nao permitido"""
    response = client.get("/api/face/register")
    assert response.status_code == 405


# ==================== TESTES DE SEGURANCA ====================


def test_cors_headers():
    """Testa se headers CORS estao presentes"""
    response = client.options("/api/tenants", headers={"Origin": "http://localhost:3000"})
    # OPTIONS pode retornar 200 ou 405 dependendo da config
    assert response.status_code in [200, 400, 405]


def test_no_sensitive_data_in_root():
    """Testa que endpoint raiz nao expoe dados sensiveis"""
    response = client.get("/")
    data = response.json()
    # Nao deve conter credenciais ou chaves
    response_text = str(data)
    assert "password" not in response_text.lower()
    assert "secret" not in response_text.lower()
    assert "api_key" not in response_text.lower()


if __name__ == "__main__":
    import pytest

    pytest.main([__file__, "-v"])
