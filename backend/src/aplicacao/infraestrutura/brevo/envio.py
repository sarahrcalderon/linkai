import asyncio
import math
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from time import monotonic

import httpx
from pydantic import ValidationError, validate_email

from aplicacao.casos_de_uso.contratos_verificacao import DesafioGerado
from aplicacao.casos_de_uso.erros_envio_email import (
    EnvioEmailIndeterminado,
    EnvioEmailPermanente,
    EnvioEmailTemporario,
)
from aplicacao.dominio.usuario import agora_utc
from aplicacao.infraestrutura.brevo.configuracao import ConfiguracaoBrevo
from aplicacao.infraestrutura.brevo.diagnostico import registrar_falha
from aplicacao.infraestrutura.brevo.template import montar_template

URL_ENVIO = "https://api.brevo.com/v3/smtp/email"


def ler_retry_after(valor: str | None, agora: datetime) -> float | None:
    if valor is None:
        return None
    try:
        if valor.strip().isascii() and valor.strip().isdigit():
            segundos = float(valor)
            if not math.isfinite(segundos):
                return math.inf
        else:
            data = parsedate_to_datetime(valor)
            data = data.replace(tzinfo=UTC) if data.tzinfo is None else data.astimezone(UTC)
            segundos = (data - agora).total_seconds()
    except (ValueError, TypeError, OverflowError):
        return None
    return max(0.0, segundos) if math.isfinite(segundos) else None


class EnvioEmailBrevo:
    def __init__(
        self,
        configuracao: ConfiguracaoBrevo,
        cliente: httpx.AsyncClient,
        esperar: Callable[[float], Awaitable[None]] = asyncio.sleep,
        cronometro: Callable[[], float] = monotonic,
        relogio: Callable[[], datetime] = agora_utc,
    ) -> None:
        self.configuracao = configuracao
        self.cliente = cliente
        self.esperar = esperar
        self.cronometro = cronometro
        self.relogio = relogio

    async def enviar_verificacao(self, destinatario: str, desafio: DesafioGerado) -> None:
        try:
            _, email = validate_email(destinatario)
        except (ValidationError, ValueError):
            registrar_falha("permanente", categoria="destinatario_invalido")
            raise EnvioEmailPermanente() from None
        mensagem = montar_template(desafio, self.configuracao.nome_remetente)
        payload = {
            "sender": {
                "email": str(self.configuracao.email_remetente),
                "name": self.configuracao.nome_remetente,
            },
            "to": [{"email": email}],
            "subject": mensagem.assunto,
            "htmlContent": mensagem.html.get_secret_value(),
            "textContent": mensagem.texto.get_secret_value(),
            # Defesa adicional: não substitui o controle durável de envio da futura composição.
            "headers": {"idempotencyKey": str(desafio.id)},
        }
        prazo = self.cronometro() + self.configuracao.tempo_total_segundos
        try:
            async with asyncio.timeout(self.configuracao.tempo_total_segundos):
                await self._enviar(payload, desafio, prazo)
        except TimeoutError:
            registrar_falha("indeterminado", categoria="prazo_total")
            raise EnvioEmailIndeterminado() from None

    async def _enviar(self, payload: dict, desafio: DesafioGerado, prazo: float) -> None:
        for tentativa in range(1, self.configuracao.limite_tentativas + 1):
            restante_codigo = (desafio.expira_em - self.relogio()).total_seconds()
            restante = min(prazo - self.cronometro(), restante_codigo)
            if restante <= 0:
                registrar_falha("temporario", categoria="prazo_encerrado")
                raise EnvioEmailTemporario()
            resposta = None
            espera = min(0.5 * 2 ** (tentativa - 1), 4)
            try:
                resposta = await self.cliente.post(
                    URL_ENVIO,
                    json=payload,
                    headers={
                        "api-key": self.configuracao.api_key.get_secret_value(),
                        "Accept": "application/json",
                    },
                    timeout=min(self.configuracao.timeout_segundos, restante),
                    follow_redirects=False,
                )
            except (httpx.ConnectTimeout, httpx.ConnectError, httpx.PoolTimeout):
                # Nenhuma requisição enviada: é seguro tentar conectar novamente.
                pass
            except httpx.RequestError:
                # Timeout de leitura/escrita e desconexão podem ocorrer depois da aceitação.
                registrar_falha("indeterminado", categoria="transporte_ambiguo")
                raise EnvioEmailIndeterminado() from None
            else:
                if resposta.status_code == 201:
                    try:
                        dados = resposta.json()
                    except ValueError:
                        registrar_falha("indeterminado", resposta, "resposta_invalida")
                        raise EnvioEmailIndeterminado() from None
                    if (
                        isinstance(dados, dict)
                        and isinstance(dados.get("messageId"), str)
                        and dados["messageId"].strip()
                    ):
                        return
                    registrar_falha("indeterminado", resposta, "resposta_invalida")
                    raise EnvioEmailIndeterminado()
                if resposta.status_code != 429:
                    if resposta.status_code in {400, 409}:
                        try:
                            erro = resposta.json()
                        except ValueError:
                            erro = None
                        if resposta.status_code == 409 or (
                            isinstance(erro, dict) and erro.get("code") == "duplicate_parameter"
                        ):
                            registrar_falha("indeterminado", resposta, "duplicidade")
                            raise EnvioEmailIndeterminado()
                    if (
                        resposta.status_code >= 500
                        or resposta.status_code < 400
                        or resposta.status_code == 408
                    ):
                        registrar_falha("indeterminado", resposta)
                        raise EnvioEmailIndeterminado()
                    # Não interpreta corpo ou erro duplicate_parameter como confirmação de envio.
                    registrar_falha("permanente", resposta)
                    raise EnvioEmailPermanente()
                espera = ler_retry_after(resposta.headers.get("Retry-After"), self.relogio())
                if espera is None:
                    espera = min(0.5 * 2 ** (tentativa - 1), 4)
            restante = min(
                prazo - self.cronometro(), (desafio.expira_em - self.relogio()).total_seconds()
            )
            if tentativa == self.configuracao.limite_tentativas or espera >= restante:
                registrar_falha("temporario", resposta, None if resposta is not None else "conexao")
                raise EnvioEmailTemporario(aguardar_segundos=espera)
            await self.esperar(espera)
