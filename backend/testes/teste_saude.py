from fastapi.testclient import TestClient

from aplicacao.principal import criar_aplicacao


def test_consulta_saude_retorna_operacional() -> None:
    with TestClient(criar_aplicacao()) as cliente:
        resposta = cliente.get("/api/saude")
    assert resposta.status_code == 200
    assert resposta.json() == {"situacao": "operacional"}


def test_rota_desconhecida_retorna_404() -> None:
    with TestClient(criar_aplicacao()) as cliente:
        resposta = cliente.get("/api/inexistente")
    assert resposta.status_code == 404
