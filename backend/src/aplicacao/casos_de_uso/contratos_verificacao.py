from contextlib import AbstractAsyncContextManager
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, SecretStr

from aplicacao.dominio.repositorio_verificacoes import RepositorioVerificacoes
from aplicacao.dominio.usuario import Usuario


class CodigosVerificacao(Protocol):
    def gerar(self) -> str: ...

    def resumir(self, codigo: str, desafio_id: UUID, usuario_id: UUID) -> str: ...

    def conferir(self, codigo: str, resumo: str, desafio_id: UUID, usuario_id: UUID) -> bool: ...


class UsuariosParaVerificacao(Protocol):
    async def obter_para_atualizacao(self, identificador: UUID) -> Usuario | None: ...

    async def marcar_email_verificado(self, identificador: UUID, agora: datetime) -> None: ...


@dataclass
class ContextoVerificacao:
    usuarios: UsuariosParaVerificacao
    verificacoes: RepositorioVerificacoes
    envios: "AgendadorEnvioEmail | None" = None


class TransacoesVerificacao(Protocol):
    def __call__(self) -> AbstractAsyncContextManager[ContextoVerificacao]: ...


class DesafioGerado(BaseModel):
    """Resultado interno para futura entrega; não é schema HTTP nem deve ser logado."""

    model_config = ConfigDict(frozen=True)
    id: UUID
    usuario_id: UUID
    expira_em: datetime
    codigo: SecretStr = Field(repr=False)


class ServicoEnvioEmail(Protocol):
    async def enviar_verificacao(self, destinatario: str, desafio: DesafioGerado) -> None: ...


class AgendadorEnvioEmail(Protocol):
    async def agendar(self, destinatario: str, desafio: DesafioGerado) -> None: ...
