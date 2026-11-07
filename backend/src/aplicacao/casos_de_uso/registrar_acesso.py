import asyncio
import logging
from typing import Literal, Protocol

from aplicacao.dominio.evento_acesso import EventoDeAcesso

registrador = logging.getLogger(__name__)
CategoriaFalha = Literal["integridade", "conexao", "banco", "pool"]


class FalhaPersistenciaEvento(Exception):
    def __init__(self, categoria: CategoriaFalha) -> None:
        self.categoria = categoria
        super().__init__("Registro de acesso não confirmado.")


class PersistenciaEvento(Protocol):
    async def persistir(self, evento: EventoDeAcesso) -> None:
        """Retorna somente após commit; cada operação possui sua própria transação."""
        ...


class RegistradorAcesso(Protocol):
    async def registrar(self, evento: EventoDeAcesso) -> None: ...


class RegistrarAcesso:
    def __init__(self, persistencia: PersistenciaEvento, prazo_segundos: float = 0.5) -> None:
        self.persistencia = persistencia
        self.prazo_segundos = prazo_segundos

    async def registrar(self, evento: EventoDeAcesso) -> None:
        try:
            async with asyncio.timeout(self.prazo_segundos):
                await self.persistencia.persistir(evento)
        except FalhaPersistenciaEvento as erro:
            # Lista fechada: nem mesmo mensagem arbitrária de exceção vai para o log.
            categoria = (
                erro.categoria
                if erro.categoria in {"integridade", "conexao", "banco", "pool"}
                else "banco"
            )
            registrador.warning("evento_acesso_nao_confirmado categoria=%s", categoria)
        except TimeoutError:
            registrador.warning("evento_acesso_nao_confirmado categoria=timeout")
        else:
            registrador.info("evento_acesso_registrado")
