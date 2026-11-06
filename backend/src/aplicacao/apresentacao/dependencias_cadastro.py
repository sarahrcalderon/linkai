from collections.abc import AsyncIterator

from fastapi import Request

from aplicacao.casos_de_uso.cadastrar_usuario import CadastrarUsuario
from aplicacao.infraestrutura.composicao_verificacao import criar_verificacao_na_transacao
from aplicacao.infraestrutura.repositorio_usuarios import RepositorioUsuariosSQLAlchemy


async def obter_cadastro(requisicao: Request) -> AsyncIterator[CadastrarUsuario]:
    banco = requisicao.app.state.banco
    if banco is None:
        raise RuntimeError("Persistência não configurada.")
    # O commit acontece antes de o endpoint devolver a resposta ao cliente.
    async with banco.transacao() as sessao:
        yield CadastrarUsuario(
            RepositorioUsuariosSQLAlchemy(sessao),
            requisicao.app.state.hash_senha,
            criar_verificacao_na_transacao(sessao, requisicao.app.state.configuracao).gerar_desafio,
        )
