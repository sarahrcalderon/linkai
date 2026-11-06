import json

import httpx
import pytest

from aplicacao.casos_de_uso.erros_envio_email import (
    EnvioEmailIndeterminado,
    EnvioEmailPermanente,
    EnvioEmailTemporario,
)
from aplicacao.infraestrutura.brevo.fabrica import criar_envio_brevo
from testes.unitarios.teste_envio_brevo import (
    CHAVE,
    CODIGO,
    DESTINATARIO,
    configurar,
)
from testes.unitarios.teste_envio_brevo import (
    desafio as desafio,
)


@pytest.mark.parametrize(
    "status,codigo,categoria,resultado,excecao",
    [
        (400, "invalid_parameter", "dados_invalidos", "permanente", EnvioEmailPermanente),
        (401, "unauthorized", "autenticacao", "permanente", EnvioEmailPermanente),
        (403, "permission_denied", "permissao", "permanente", EnvioEmailPermanente),
        (429, "too_many_requests", "limite_requisicoes", "temporario", EnvioEmailTemporario),
        (500, "internal_error", "provedor", "indeterminado", EnvioEmailIndeterminado),
        (503, "internal_error", "provedor", "indeterminado", EnvioEmailIndeterminado),
    ],
)
async def test_classificacao_http_segura(
    desafio, caplog, status, codigo, categoria, resultado, excecao
):
    chamadas = 0

    def responder(requisicao):
        nonlocal chamadas
        chamadas += 1
        return httpx.Response(
            status,
            json={"code": codigo, "message": f"{CHAVE} {CODIGO} {DESTINATARIO}"},
            headers={"Retry-After": "90", "X-Privado": CHAVE},
        )

    async with criar_envio_brevo(
        configurar(limite_tentativas=1), httpx.MockTransport(responder)
    ) as envio:
        with pytest.raises(excecao):
            await envio.enviar_verificacao(DESTINATARIO, desafio)
    registros = [r for r in caplog.records if r.name.endswith("brevo.diagnostico")]
    assert chamadas == 1 and len(registros) == 1
    registro = registros[0]
    assert registro.status_http == status
    assert registro.codigo_provedor == codigo
    assert registro.categoria == categoria
    assert registro.resultado == resultado
    for segredo in [CHAVE, CODIGO, DESTINATARIO, "message", "X-Privado"]:
        assert segredo not in caplog.text


@pytest.mark.parametrize(
    "corpo",
    [
        {"code": f"unauthorized {CHAVE} {DESTINATARIO} {CODIGO}"},
        {"code": {"segredo": CHAVE}},
        {"code": [CHAVE]},
        {"code": "codigo_desconhecido"},
        [CHAVE],
        None,
    ],
)
async def test_descarta_codigos_nao_permitidos_e_corpos_arbitrarios(desafio, caplog, corpo):
    transporte = httpx.MockTransport(lambda _: httpx.Response(401, content=json.dumps(corpo)))
    async with criar_envio_brevo(configurar(limite_tentativas=1), transporte) as envio:
        with pytest.raises(EnvioEmailPermanente):
            await envio.enviar_verificacao(DESTINATARIO, desafio)
    registro = next(r for r in caplog.records if r.name.endswith("brevo.diagnostico"))
    assert registro.codigo_provedor is None and registro.status_http == 401
    for segredo in [CHAVE, CODIGO, DESTINATARIO, "codigo_desconhecido"]:
        assert segredo not in caplog.text


async def test_resposta_nao_json_e_diagnostico_sem_corpo(desafio, caplog):
    transporte = httpx.MockTransport(lambda _: httpx.Response(403, text=CHAVE))
    async with criar_envio_brevo(configurar(limite_tentativas=1), transporte) as envio:
        with pytest.raises(EnvioEmailPermanente):
            await envio.enviar_verificacao(DESTINATARIO, desafio)
    assert CHAVE not in caplog.text
    assert "status_http=403" in caplog.text
