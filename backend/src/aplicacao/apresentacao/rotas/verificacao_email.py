from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response

from aplicacao.apresentacao.erros import resposta_erro
from aplicacao.apresentacao.schemas_verificacao import (
    ConfirmacaoEntradaHTTP,
    ConfirmacaoSaidaHTTP,
    ReenvioEntradaHTTP,
    ReenvioSaidaHTTP,
)
from aplicacao.casos_de_uso.solicitacoes_email import (
    SolicitacoesEmail,
)
from aplicacao.infraestrutura.composicao_verificacao import criar_verificacao_na_transacao
from aplicacao.infraestrutura.repositorio_usuarios import RepositorioUsuariosSQLAlchemy

roteador_verificacao = APIRouter(tags=["Verificação de e-mail"])


async def obter_solicitacoes(requisicao: Request) -> AsyncIterator[SolicitacoesEmail]:
    async with requisicao.app.state.banco.transacao() as sessao:
        yield SolicitacoesEmail(
            RepositorioUsuariosSQLAlchemy(sessao),
            criar_verificacao_na_transacao(
                sessao,
                requisicao.app.state.configuracao,
                incluir_envio=requisicao.url.path.rstrip("/").endswith("/reenviar-codigo"),
            ),
        )


SolicitacoesHTTP = Annotated[SolicitacoesEmail, Depends(obter_solicitacoes, scope="function")]


@roteador_verificacao.post(
    "/autenticacao/reenviar-codigo", status_code=202, response_model=ReenvioSaidaHTTP
)
async def reenviar_codigo(
    entrada: ReenvioEntradaHTTP, solicitacoes: SolicitacoesHTTP, resposta: Response
):
    resposta.headers["Cache-Control"] = "no-store"
    await solicitacoes.reenviar(entrada)
    return ReenvioSaidaHTTP()


@roteador_verificacao.post("/autenticacao/verificar-email", response_model=ConfirmacaoSaidaHTTP)
async def verificar_email(
    entrada: ConfirmacaoEntradaHTTP, solicitacoes: SolicitacoesHTTP, resposta: Response
):
    resposta.headers["Cache-Control"] = "no-store"
    # Não lança exceção: tentativas incorretas precisam ser confirmadas pelo commit.
    if not await solicitacoes.confirmar(entrada):
        return resposta_erro("verificacao_invalida", "Código inválido ou indisponível.", 400)
    return ConfirmacaoSaidaHTTP()
