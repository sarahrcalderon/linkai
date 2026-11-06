from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import AsyncSession

from aplicacao.casos_de_uso.contratos_verificacao import ContextoVerificacao
from aplicacao.casos_de_uso.verificar_email import VerificarEmail
from aplicacao.configuracao import Configuracao
from aplicacao.infraestrutura.agendador_email import AgendadorEmailSQLAlchemy
from aplicacao.infraestrutura.cifra_outbox import CifraOutbox
from aplicacao.infraestrutura.codigos_verificacao import CodigosVerificacaoHMAC
from aplicacao.infraestrutura.repositorio_usuarios import RepositorioUsuariosSQLAlchemy
from aplicacao.infraestrutura.repositorio_verificacoes import RepositorioVerificacoesSQLAlchemy


def criar_verificacao_na_transacao(
    sessao: AsyncSession, configuracao: Configuracao, incluir_envio: bool = True
) -> VerificarEmail:
    if configuracao.verificacao_segredo is None:
        raise ValueError("Configure VERIFICACAO_SEGREDO para solicitação de verificação.")
    envios = (
        AgendadorEmailSQLAlchemy(sessao, CifraOutbox(configuracao.outbox_chave))
        if incluir_envio
        else None
    )

    @asynccontextmanager
    async def contexto():
        # Não abre outra transação: cadastro, desafio e outbox compartilham o commit externo.
        yield ContextoVerificacao(
            RepositorioUsuariosSQLAlchemy(sessao),
            RepositorioVerificacoesSQLAlchemy(sessao),
            envios,
        )

    return VerificarEmail(
        contexto,
        CodigosVerificacaoHMAC(configuracao.verificacao_segredo),
        validade_segundos=configuracao.verificacao_validade_segundos,
        limite_tentativas=configuracao.verificacao_limite_tentativas,
        intervalo_reenvio=configuracao.verificacao_intervalo_reenvio,
        limite_envios=configuracao.verificacao_limite_envios,
        janela_envios=configuracao.verificacao_janela_envios,
    )
