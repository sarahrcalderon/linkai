from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from pydantic import ValidationError

from aplicacao.casos_de_uso.gerenciar_links import (
    AtualizarLinkEntrada,
    CriarLinkEntrada,
    DadosLinkInvalidos,
    GerenciarLinks,
)
from aplicacao.dominio.link import Link
from aplicacao.dominio.repositorio_links import LinkNaoEncontrado


def link_valido():
    return Link(
        usuario_id=uuid4(),
        nome="Campanha",
        slug="campanha",
        numero_whatsapp="+5511999999999",
        mensagem="Texto",
    )


async def test_caso_criar_aplica_dominio_e_sessao():
    repo = AsyncMock()
    usuario = uuid4()
    resultado = await GerenciarLinks(repo).criar(
        usuario,
        CriarLinkEntrada(
            nome=" Campanha ", slug=" CAMPANHA ", numero_whatsapp="55 (11) 99999-9999"
        ),
    )
    persistido = repo.adicionar.call_args.args[0]
    assert persistido.usuario_id == usuario and resultado.slug == "campanha"
    assert (
        "usuario_id" not in resultado.model_dump() and "excluido_em" not in resultado.model_dump()
    )


async def test_caso_invalido_nao_persiste():
    repo = AsyncMock()
    with pytest.raises(DadosLinkInvalidos):
        await GerenciarLinks(repo).criar(
            uuid4(), CriarLinkEntrada(nome="a", slug="api", numero_whatsapp="abc")
        )
    repo.adicionar.assert_not_awaited()


async def test_patch_somente_campos_enviados_e_null():
    link = link_valido()
    repo = AsyncMock()
    repo.obter_para_atualizacao.return_value = link
    resultado = await GerenciarLinks(repo).atualizar(
        link.usuario_id, link.id, AtualizarLinkEntrada(mensagem=None)
    )
    assert (
        resultado.mensagem is None and resultado.nome == link.nome and resultado.slug == link.slug
    )
    repo.obter_para_atualizacao.assert_awaited_once_with(link.id, link.usuario_id)
    assert resultado.atualizado_em >= link.atualizado_em


@pytest.mark.parametrize("ausente", [True, False])
async def test_ausente_e_excluido_recusados(ausente):
    link = link_valido()
    repo = AsyncMock()
    repo.obter_por_id.return_value = None if ausente else link.excluir()
    with pytest.raises(LinkNaoEncontrado):
        await GerenciarLinks(repo).consultar(link.usuario_id, link.id)


@pytest.mark.parametrize("dados", [{}, {"ativo": None}, {"nome": None}, {"ativo": "false"}])
def test_dto_patch_rejeita_campos_invalidos(dados):
    with pytest.raises(ValidationError):
        AtualizarLinkEntrada(**dados)


async def test_paginacao_limitada_na_aplicacao():
    with pytest.raises(DadosLinkInvalidos):
        await GerenciarLinks(AsyncMock()).listar(uuid4(), 1, 101)
