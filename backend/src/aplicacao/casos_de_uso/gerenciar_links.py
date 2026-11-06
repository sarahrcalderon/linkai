from dataclasses import replace
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, model_validator

from aplicacao.dominio.link import Link
from aplicacao.dominio.repositorio_links import LinkNaoEncontrado, RepositorioLinks
from aplicacao.dominio.usuario import agora_utc


class DadosLinkInvalidos(Exception):
    """Dados recusados pelo domínio, sem refletir valores enviados."""


class CriarLinkEntrada(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    nome: str
    slug: str
    numero_whatsapp: str
    mensagem: str | None = None


class AtualizarLinkEntrada(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    nome: str | None = None
    slug: str | None = None
    numero_whatsapp: str | None = None
    mensagem: str | None = None
    ativo: bool | None = None

    @model_validator(mode="after")
    def validar_campos(self):
        if not self.model_fields_set or any(
            getattr(self, c) is None for c in self.model_fields_set - {"mensagem"}
        ):
            raise ValueError("Informe campos alteráveis; apenas mensagem aceita null.")
        return self


class LinkSaida(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    nome: str
    slug: str
    numero_whatsapp: str
    mensagem: str | None
    ativo: bool
    criado_em: datetime
    atualizado_em: datetime


class ListaLinksSaida(BaseModel):
    itens: list[LinkSaida]
    total: int
    pagina: int
    tamanho: int


class GerenciarLinks:
    def __init__(self, links: RepositorioLinks) -> None:
        self.links = links

    async def criar(self, usuario_id: UUID, entrada: CriarLinkEntrada) -> LinkSaida:
        try:
            link = Link(usuario_id=usuario_id, **entrada.model_dump())
        except ValueError:
            raise DadosLinkInvalidos() from None
        await self.links.adicionar(link)
        return LinkSaida.model_validate(link)

    async def consultar(self, usuario_id: UUID, identificador: UUID) -> LinkSaida:
        return LinkSaida.model_validate(await self._obter(usuario_id, identificador))

    async def listar(self, usuario_id: UUID, pagina: int, tamanho: int) -> ListaLinksSaida:
        if not 1 <= pagina <= 1000000 or not 1 <= tamanho <= 100:
            raise DadosLinkInvalidos()
        itens, total = await self.links.listar_por_usuario(
            usuario_id, (pagina - 1) * tamanho, tamanho
        )
        return ListaLinksSaida(
            itens=[LinkSaida.model_validate(i) for i in itens],
            total=total,
            pagina=pagina,
            tamanho=tamanho,
        )

    async def atualizar(
        self, usuario_id: UUID, identificador: UUID, entrada: AtualizarLinkEntrada
    ) -> LinkSaida:
        link = await self._obter(usuario_id, identificador, bloquear=True)
        try:
            alterado = replace(
                link, **entrada.model_dump(exclude_unset=True), atualizado_em=agora_utc()
            )
        except ValueError:
            raise DadosLinkInvalidos() from None
        await self.links.atualizar(alterado)
        return LinkSaida.model_validate(alterado)

    async def excluir(self, usuario_id: UUID, identificador: UUID) -> None:
        link = await self._obter(usuario_id, identificador, bloquear=True)
        await self.links.atualizar(link.excluir())

    async def _obter(self, usuario_id: UUID, identificador: UUID, bloquear: bool = False) -> Link:
        metodo = self.links.obter_para_atualizacao if bloquear else self.links.obter_por_id
        link = await metodo(identificador, usuario_id)
        if link is None or link.excluido_em is not None:
            raise LinkNaoEncontrado()
        return link
