from typing import Protocol
from uuid import UUID

from aplicacao.casos_de_uso.contratos_verificacao import DesafioGerado


class CifraEntrega(Protocol):
    def decifrar(self, dados: str, identificador: UUID) -> tuple[str, DesafioGerado]: ...


class ConteudoEntregaInvalido(Exception):
    def __init__(self) -> None:
        super().__init__("Conteúdo de entrega indisponível.")
