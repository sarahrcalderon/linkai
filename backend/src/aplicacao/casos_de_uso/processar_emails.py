import asyncio

from aplicacao.casos_de_uso.contratos_entrega import CifraEntrega, ConteudoEntregaInvalido
from aplicacao.casos_de_uso.contratos_verificacao import ServicoEnvioEmail
from aplicacao.casos_de_uso.erros_envio_email import (
    EnvioEmailIndeterminado,
    EnvioEmailPermanente,
    EnvioEmailTemporario,
)
from aplicacao.dominio.entrega_email import RepositorioEntregas


class ProcessarEmails:
    def __init__(
        self, entregas: RepositorioEntregas, cifra: CifraEntrega, envio: ServicoEnvioEmail
    ) -> None:
        self.entregas, self.cifra, self.envio = entregas, cifra, envio

    async def executar_uma(self) -> bool:
        reserva = await self.entregas.reservar()
        if reserva is None:
            return False
        try:
            destinatario, desafio = self.cifra.decifrar(reserva.dados_cifrados, reserva.id)
        except ConteudoEntregaInvalido:
            await self.entregas.concluir(reserva, "falha")
            return True
        if not await self.entregas.iniciar(reserva):
            return True
        aguardar = None
        try:
            # A reserva e a marcação de início já foram commitadas. Nenhuma transação aberta aqui.
            await self.envio.enviar_verificacao(destinatario, desafio)
        except EnvioEmailTemporario as erro:
            resultado = "temporario"
            aguardar = erro.aguardar_segundos
        except EnvioEmailPermanente:
            resultado = "falha"
        except EnvioEmailIndeterminado:
            resultado = "indeterminada"
        except asyncio.CancelledError:
            await asyncio.shield(self.entregas.concluir(reserva, "indeterminada"))
            raise
        except Exception:
            resultado = "indeterminada"
        else:
            resultado = "enviada"
        await self.entregas.concluir(reserva, resultado, aguardar)
        return True
