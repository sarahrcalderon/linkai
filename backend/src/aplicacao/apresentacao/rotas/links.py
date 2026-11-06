from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Query, Request, Response

from aplicacao.apresentacao.cookies_sessao import ler_token
from aplicacao.apresentacao.dependencias_autenticacao import (
    TransacaoHTTP,
    obter_consulta,
    validar_origem,
)
from aplicacao.casos_de_uso.consultar_autenticado import ConsultarAutenticado
from aplicacao.casos_de_uso.contratos_autenticacao import CsrfInvalido
from aplicacao.casos_de_uso.gerenciar_links import (
    AtualizarLinkEntrada,
    CriarLinkEntrada,
    GerenciarLinks,
    LinkSaida,
    ListaLinksSaida,
)
from aplicacao.infraestrutura.repositorio_links import RepositorioLinksSQLAlchemy

roteador_links = APIRouter(prefix="/links", tags=["Links"])


def obter_gerenciador(transacao: TransacaoHTTP) -> GerenciarLinks:
    return GerenciarLinks(RepositorioLinksSQLAlchemy(transacao))


async def obter_proprietario(
    requisicao: Request,
    resposta: Response,
    consulta: Annotated[ConsultarAutenticado, Depends(obter_consulta)],
) -> UUID:
    resultado = await consulta.executar(ler_token(requisicao))
    resposta.headers["Cache-Control"] = "no-store"
    return resultado.usuario.id


Proprietario = Annotated[UUID, Depends(obter_proprietario)]
Gerenciador = Annotated[GerenciarLinks, Depends(obter_gerenciador)]


def validar_escrita(
    requisicao: Request,
    proprietario: Proprietario,
    csrf: Annotated[str | None, Header(alias="X-CSRF-Token")] = None,
) -> UUID:
    validar_origem(requisicao)
    if not requisicao.app.state.tokens.verificar_csrf(ler_token(requisicao) or "", csrf or ""):
        raise CsrfInvalido()
    return proprietario


Escritor = Annotated[UUID, Depends(validar_escrita)]


@roteador_links.post("", status_code=201, response_model=LinkSaida)
async def criar_link(entrada: CriarLinkEntrada, usuario: Escritor, caso: Gerenciador):
    return await caso.criar(usuario, entrada)


@roteador_links.get("", response_model=ListaLinksSaida)
async def listar_links(
    usuario: Proprietario,
    caso: Gerenciador,
    pagina: Annotated[int, Query(ge=1, le=1000000)] = 1,
    tamanho: Annotated[int, Query(ge=1, le=100)] = 20,
):
    return await caso.listar(usuario, pagina, tamanho)


@roteador_links.get("/{identificador}", response_model=LinkSaida)
async def consultar_link(identificador: UUID, usuario: Proprietario, caso: Gerenciador):
    return await caso.consultar(usuario, identificador)


@roteador_links.patch("/{identificador}", response_model=LinkSaida)
async def atualizar_link(
    identificador: UUID, entrada: AtualizarLinkEntrada, usuario: Escritor, caso: Gerenciador
):
    return await caso.atualizar(usuario, identificador, entrada)


@roteador_links.delete("/{identificador}", status_code=204)
async def excluir_link(identificador: UUID, usuario: Escritor, caso: Gerenciador):
    await caso.excluir(usuario, identificador)
