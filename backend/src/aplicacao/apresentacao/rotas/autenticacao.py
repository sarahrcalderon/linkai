from typing import Annotated

from fastapi import APIRouter, Depends, Header, Request, Response

from aplicacao.apresentacao.cookies_sessao import apagar_cookie, definir_cookie, ler_token
from aplicacao.apresentacao.dependencias_autenticacao import (
    obter_consulta,
    obter_login,
    obter_logout,
    validar_origem,
)
from aplicacao.apresentacao.schemas_autenticacao import AutenticacaoSaidaHTTP, LoginEntradaHTTP
from aplicacao.casos_de_uso.autenticar_usuario import AutenticarUsuario
from aplicacao.casos_de_uso.consultar_autenticado import ConsultarAutenticado
from aplicacao.casos_de_uso.encerrar_sessao import EncerrarSessao

roteador_autenticacao = APIRouter(tags=["Autenticação"])


@roteador_autenticacao.post(
    "/autenticacao/login",
    response_model=AutenticacaoSaidaHTTP,
    dependencies=[Depends(validar_origem)],
)
async def fazer_login(
    entrada: LoginEntradaHTTP,
    requisicao: Request,
    resposta: Response,
    caso: Annotated[AutenticarUsuario, Depends(obter_login)],
) -> AutenticacaoSaidaHTTP:
    resultado = await caso.executar(entrada, ler_token(requisicao))
    definir_cookie(
        resposta, resultado.token, resultado.expira_em, requisicao.app.state.configuracao
    )
    return AutenticacaoSaidaHTTP.do_resultado(resultado)


@roteador_autenticacao.get("/usuarios/me", response_model=AutenticacaoSaidaHTTP)
async def consultar_usuario(
    requisicao: Request,
    resposta: Response,
    caso: Annotated[ConsultarAutenticado, Depends(obter_consulta)],
) -> AutenticacaoSaidaHTTP:
    resultado = await caso.executar(ler_token(requisicao))
    resposta.headers["Cache-Control"] = "no-store"
    return AutenticacaoSaidaHTTP.do_resultado(resultado)


@roteador_autenticacao.post(
    "/autenticacao/logout", status_code=204, dependencies=[Depends(validar_origem)]
)
async def fazer_logout(
    requisicao: Request,
    resposta: Response,
    caso: Annotated[EncerrarSessao, Depends(obter_logout)],
    csrf: Annotated[str | None, Header(alias="X-CSRF-Token")] = None,
) -> None:
    await caso.executar(ler_token(requisicao), csrf or "")
    apagar_cookie(resposta, requisicao.app.state.configuracao)
