from unittest.mock import AsyncMock
from urllib.parse import parse_qs, urlsplit
from uuid import uuid4

import pytest

from aplicacao.casos_de_uso.obter_destino_whatsapp import ObterDestinoWhatsApp
from aplicacao.dominio.link import Link
from aplicacao.dominio.repositorio_links import LinkNaoEncontrado


@pytest.mark.parametrize(
    "mensagem",
    [
        None,
        "",
        "Espaços na mensagem",
        "Olá, ação!",
        "Olá 👋🚀",
        "Linha 1\nLinha 2",
        "&text=outro?url=https://hostil.example/#x",
        "Linha\r\nLocation: https://hostil.example",
    ],
)
async def test_destino_fixo_e_codificacao_sem_injecao(mensagem):
    repo = AsyncMock()
    repo.obter_publico_por_slug.return_value = Link(
        usuario_id=uuid4(),
        nome="Campanha",
        slug="campanha",
        numero_whatsapp="+55 (11) 99999-9999",
        mensagem=mensagem,
    )
    destino = await ObterDestinoWhatsApp(repo).executar("CAMPANHA")
    partes = urlsplit(destino)
    assert partes.scheme == "https" and partes.netloc == "wa.me" and partes.path == "/5511999999999"
    assert partes.fragment == "" and "\r" not in destino and "\n" not in destino
    if mensagem:
        assert parse_qs(partes.query) == {"text": [mensagem]}
    else:
        assert partes.query == ""
    repo.obter_publico_por_slug.assert_awaited_once_with("campanha")


@pytest.mark.parametrize(
    "slug", ["a", "x" * 65, "api", "https://hostil.example", "campanha?text=x", "a\r\nb", "ação"]
)
async def test_slug_invalido_nao_consulta_banco(slug):
    repo = AsyncMock()
    with pytest.raises(LinkNaoEncontrado):
        await ObterDestinoWhatsApp(repo).executar(slug)
    repo.obter_publico_por_slug.assert_not_awaited()


async def test_ausente_nao_redireciona():
    repo = AsyncMock()
    repo.obter_publico_por_slug.return_value = None
    with pytest.raises(LinkNaoEncontrado):
        await ObterDestinoWhatsApp(repo).executar("ausente")
