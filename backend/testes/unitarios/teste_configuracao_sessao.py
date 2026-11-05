import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from aplicacao.configuracao import Configuracao
from aplicacao.principal import criar_aplicacao


@pytest.mark.parametrize(
    "ajustes",
    [
        {"origens_permitidas": ["*"]},
        {"origens_permitidas": ["https://*.example.com"]},
        {"origens_permitidas": ["https://app.example.com/caminho"]},
        {"ambiente": "producao", "origens_permitidas": ["http://app.example.com"]},
        {"ambiente": "producao", "sessao_cookie_seguro": False},
        {"sessao_cookie_samesite": "none"},
        {"sessao_duracao_segundos": 0},
        {"ambiente": "producao_digitada_errada"},
    ],
)
def test_rejeita_configuracao_insegura(ajustes):
    with pytest.raises(ValidationError):
        Configuracao(_env_file=None, **ajustes)


def test_producao_ativa_secure_por_padrao():
    configuracao = Configuracao(
        _env_file=None, ambiente="producao", origens_permitidas=["https://app.example.com"]
    )
    assert configuracao.cookie_seguro


def test_sem_banco_login_me_e_logout_nao_tem_fallback():
    app = criar_aplicacao(Configuracao(_env_file=None, url_banco=None))
    with TestClient(app, raise_server_exceptions=False) as cliente:
        respostas = [
            cliente.post(
                "/api/autenticacao/login",
                headers={"Origin": "http://localhost:5173"},
                json={"email": "ana@example.com", "senha": "senha de teste"},
            ),
            cliente.get("/api/usuarios/me"),
            cliente.post("/api/autenticacao/logout", headers={"Origin": "http://localhost:5173"}),
        ]
        for resposta in respostas:
            assert resposta.status_code == 503
            assert "set-cookie" not in resposta.headers
        assert cliente.get("/api/saude").status_code == 200
