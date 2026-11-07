from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from aplicacao.casos_de_uso.contratos_verificacao import ServicoEnvioEmail
from aplicacao.casos_de_uso.erros_envio_email import ConfiguracaoEnvioInvalida
from aplicacao.configuracao import Configuracao
from aplicacao.infraestrutura.brevo.configuracao import ConfiguracaoBrevo
from aplicacao.infraestrutura.brevo.fabrica import criar_envio_brevo
from aplicacao.infraestrutura.smtp_local import EnvioEmailSMTPLocal


@asynccontextmanager
async def criar_servico_email(configuracao: Configuracao) -> AsyncIterator[ServicoEnvioEmail]:
    if configuracao.email_provedor == "mailpit":
        if configuracao.outbox_lease_segundos <= configuracao.smtp_timeout_segundos * 8 + 15:
            raise ConfiguracaoEnvioInvalida()
        yield EnvioEmailSMTPLocal(configuracao)
    elif configuracao.email_provedor == "brevo" and configuracao.ambiente == "producao":
        brevo = ConfiguracaoBrevo()
        if configuracao.outbox_lease_segundos <= brevo.tempo_total_segundos + 15:
            raise ConfiguracaoEnvioInvalida()
        async with criar_envio_brevo(brevo) as envio:
            yield envio
    else:
        # Nenhum fallback para Brevo, inclusive se suas credenciais existirem no ambiente.
        raise ConfiguracaoEnvioInvalida()
