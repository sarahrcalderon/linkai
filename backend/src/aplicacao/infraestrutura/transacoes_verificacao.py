from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from aplicacao.casos_de_uso.contratos_verificacao import ContextoVerificacao
from aplicacao.casos_de_uso.verificar_email import VerificarEmail
from aplicacao.configuracao import Configuracao
from aplicacao.infraestrutura.banco import BancoDados
from aplicacao.infraestrutura.codigos_verificacao import CodigosVerificacaoHMAC
from aplicacao.infraestrutura.repositorio_usuarios import RepositorioUsuariosSQLAlchemy
from aplicacao.infraestrutura.repositorio_verificacoes import RepositorioVerificacoesSQLAlchemy


class TransacoesVerificacaoSQLAlchemy:
    def __init__(self, banco: BancoDados) -> None:
        self.banco = banco

    @asynccontextmanager
    async def __call__(self) -> AsyncIterator[ContextoVerificacao]:
        async with self.banco.transacao() as sessao:
            yield ContextoVerificacao(
                usuarios=RepositorioUsuariosSQLAlchemy(sessao),
                verificacoes=RepositorioVerificacoesSQLAlchemy(sessao),
            )


def criar_verificacao_email(banco: BancoDados, configuracao: Configuracao) -> VerificarEmail:
    if configuracao.verificacao_segredo is None:
        raise ValueError("Configure VERIFICACAO_SEGREDO antes de utilizar a verificação.")
    return VerificarEmail(
        TransacoesVerificacaoSQLAlchemy(banco),
        CodigosVerificacaoHMAC(configuracao.verificacao_segredo),
        validade_segundos=configuracao.verificacao_validade_segundos,
        limite_tentativas=configuracao.verificacao_limite_tentativas,
        intervalo_reenvio=configuracao.verificacao_intervalo_reenvio,
        limite_envios=configuracao.verificacao_limite_envios,
        janela_envios=configuracao.verificacao_janela_envios,
    )
