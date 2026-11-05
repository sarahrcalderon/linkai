from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from aplicacao.casos_de_uso.autenticar_usuario import AutenticarUsuario
from aplicacao.casos_de_uso.consultar_autenticado import ConsultarAutenticado
from aplicacao.casos_de_uso.contratos_autenticacao import CsrfInvalido
from aplicacao.casos_de_uso.encerrar_sessao import EncerrarSessao
from aplicacao.infraestrutura.repositorio_sessoes import RepositorioSessoesSQLAlchemy
from aplicacao.infraestrutura.repositorio_usuarios import RepositorioUsuariosSQLAlchemy


def validar_origem(requisicao: Request) -> None:
    # Login também exige Origin para evitar login CSRF antes de existir uma sessão.
    origem = requisicao.headers.get("origin")
    if origem not in requisicao.app.state.configuracao.origens_permitidas:
        raise CsrfInvalido()


async def obter_transacao(requisicao: Request) -> AsyncIterator[AsyncSession]:
    banco = requisicao.app.state.banco
    if banco is None:
        raise RuntimeError("Persistência não configurada.")
    async with banco.transacao() as sessao:
        yield sessao


TransacaoHTTP = Annotated[AsyncSession, Depends(obter_transacao, scope="function")]


def obter_login(requisicao: Request, transacao: TransacaoHTTP) -> AutenticarUsuario:
    estado = requisicao.app.state
    return AutenticarUsuario(
        RepositorioUsuariosSQLAlchemy(transacao),
        RepositorioSessoesSQLAlchemy(transacao),
        estado.hash_senha,
        estado.tokens,
        estado.hash_ficticio,
        estado.configuracao.sessao_duracao_segundos,
    )


def obter_consulta(requisicao: Request, transacao: TransacaoHTTP) -> ConsultarAutenticado:
    return ConsultarAutenticado(
        RepositorioUsuariosSQLAlchemy(transacao),
        RepositorioSessoesSQLAlchemy(transacao),
        requisicao.app.state.tokens,
    )


def obter_logout(requisicao: Request, transacao: TransacaoHTTP) -> EncerrarSessao:
    return EncerrarSessao(RepositorioSessoesSQLAlchemy(transacao), requisicao.app.state.tokens)
