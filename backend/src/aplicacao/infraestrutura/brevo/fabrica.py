from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx
from pydantic import ValidationError

from aplicacao.casos_de_uso.erros_envio_email import ConfiguracaoEnvioInvalida
from aplicacao.infraestrutura.brevo.configuracao import ConfiguracaoBrevo
from aplicacao.infraestrutura.brevo.envio import EnvioEmailBrevo


@asynccontextmanager
async def criar_envio_brevo(
    configuracao: ConfiguracaoBrevo | None = None,
    transporte: httpx.AsyncBaseTransport | None = None,
) -> AsyncIterator[EnvioEmailBrevo]:
    try:
        configuracao = configuracao or ConfiguracaoBrevo()
    except ValidationError:
        raise ConfiguracaoEnvioInvalida() from None
    async with httpx.AsyncClient(
        transport=transporte,
        timeout=configuracao.timeout_segundos,
        follow_redirects=False,
        trust_env=False,
    ) as cliente:
        yield EnvioEmailBrevo(configuracao, cliente)
