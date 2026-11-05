import re
from datetime import datetime

from fastapi import Request, Response

from aplicacao.configuracao import Configuracao

NOME_COOKIE = "linkai_sessao"
CAMINHO_COOKIE = "/api"


def parametros_cookie(configuracao: Configuracao) -> tuple[str, str]:
    # __Host- impede que um subdomínio injete um cookie Domain com o mesmo nome.
    if configuracao.cookie_seguro:
        return "__Host-linkai_sessao", "/"
    return NOME_COOKIE, CAMINHO_COOKIE


def ler_token(requisicao: Request) -> str | None:
    nome, _ = parametros_cookie(requisicao.app.state.configuracao)
    token = requisicao.cookies.get(nome, "")
    return token if re.fullmatch(r"[A-Za-z0-9_-]{43}", token) else None


def definir_cookie(
    resposta: Response, token: str, expira_em: datetime, configuracao: Configuracao
) -> None:
    nome, caminho = parametros_cookie(configuracao)
    resposta.set_cookie(
        nome,
        token,
        max_age=configuracao.sessao_duracao_segundos,
        expires=expira_em,
        path=caminho,
        secure=configuracao.cookie_seguro,
        httponly=True,
        samesite=configuracao.sessao_cookie_samesite,
    )
    resposta.headers["Cache-Control"] = "no-store"


def apagar_cookie(resposta: Response, configuracao: Configuracao) -> None:
    nome, caminho = parametros_cookie(configuracao)
    resposta.delete_cookie(
        nome,
        path=caminho,
        secure=configuracao.cookie_seguro,
        httponly=True,
        samesite=configuracao.sessao_cookie_samesite,
    )
    resposta.headers["Cache-Control"] = "no-store"
