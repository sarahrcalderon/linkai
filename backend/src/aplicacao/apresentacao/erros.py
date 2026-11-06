from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError

from aplicacao.casos_de_uso.contratos_autenticacao import (
    CredenciaisInvalidas,
    CsrfInvalido,
    SessaoInvalida,
)
from aplicacao.casos_de_uso.gerenciar_links import DadosLinkInvalidos
from aplicacao.dominio.repositorio_links import LinkNaoEncontrado, SlugJaUtilizado


def resposta_erro(codigo: str, mensagem: str, status: int, **detalhes) -> JSONResponse:
    return JSONResponse(
        status_code=status,
        content={"erro": {"codigo": codigo, "mensagem": mensagem, **detalhes}},
        headers={"Cache-Control": "no-store"},
    )


def registrar_tratamento_erros(app: FastAPI) -> None:
    @app.exception_handler(LinkNaoEncontrado)
    async def tratar_link_ausente(requisicao: Request, erro: LinkNaoEncontrado):
        return resposta_erro("link_nao_encontrado", "Link não encontrado.", 404)

    @app.exception_handler(SlugJaUtilizado)
    async def tratar_slug(requisicao: Request, erro: SlugJaUtilizado):
        return resposta_erro("slug_indisponivel", "Slug indisponível.", 409)

    @app.exception_handler(DadosLinkInvalidos)
    async def tratar_dados_link(requisicao: Request, erro: DadosLinkInvalidos):
        return resposta_erro("dados_invalidos", "Revise os dados do link.", 422)

    @app.exception_handler(CredenciaisInvalidas)
    async def tratar_credenciais(requisicao: Request, erro: CredenciaisInvalidas):
        return resposta_erro("credenciais_invalidas", "E-mail ou senha inválidos.", 401)

    @app.exception_handler(SessaoInvalida)
    async def tratar_sessao(requisicao: Request, erro: SessaoInvalida):
        return resposta_erro("sessao_invalida", "Autenticação necessária.", 401)

    @app.exception_handler(CsrfInvalido)
    async def tratar_csrf(requisicao: Request, erro: CsrfInvalido):
        return resposta_erro(
            "csrf_invalido", "Não foi possível validar a origem da solicitação.", 403
        )

    @app.exception_handler(RequestValidationError)
    async def tratar_validacao(requisicao: Request, erro: RequestValidationError):
        mensagens = {
            "nome": "Informe um nome com 2 a 100 caracteres, sem caracteres de controle.",
            "email": "Informe um e-mail válido com até 254 caracteres.",
            "senha": "Informe uma senha com 12 a 128 caracteres, sem caracteres de controle.",
        }
        mensagem_corpo = "Envie apenas nome, e-mail e senha em um objeto JSON válido."
        if requisicao.url.path.rstrip("/") == "/api/links" or requisicao.url.path.startswith(
            "/api/links/"
        ):
            mensagens = {
                c: "Revise o campo informado."
                for c in (
                    "nome",
                    "slug",
                    "numero_whatsapp",
                    "mensagem",
                    "ativo",
                    "identificador",
                    "pagina",
                    "tamanho",
                )
            }
            mensagem_corpo = "Envie apenas os campos previstos para links."
        if requisicao.url.path.rstrip("/") in {
            "/api/autenticacao/verificar-email",
            "/api/autenticacao/reenviar-codigo",
        }:
            mensagens = {
                "email": mensagens["email"],
                "codigo": "Informe um código de seis dígitos.",
            }
            mensagem_corpo = "Envie apenas os campos previstos para a verificação."
        if requisicao.url.path.rstrip("/") == "/api/autenticacao/login":
            mensagens.pop("nome")
            mensagens["senha"] = "Informe uma senha com 1 a 128 caracteres."
            mensagem_corpo = "Envie apenas e-mail e senha em um objeto JSON válido."
        campos = []
        for detalhe in erro.errors():
            local = detalhe["loc"]
            campo = local[1] if len(local) > 1 and isinstance(local[1], str) else "corpo"
            # Não inclui input, contexto, conteúdo JSON nem nomes de campos desconhecidos.
            if campo not in mensagens:
                campo = "corpo"
            campos.append(
                {
                    "campo": campo,
                    "mensagem": mensagens.get(campo, mensagem_corpo),
                }
            )
        return resposta_erro("dados_invalidos", "Revise os dados informados.", 422, campos=campos)

    # Exceções de banco são tratadas dentro do ExceptionMiddleware, antes do CORS.
    @app.exception_handler(SQLAlchemyError)
    @app.exception_handler(Exception)
    async def tratar_falha(requisicao: Request, erro: Exception):
        return resposta_erro(
            "servico_indisponivel", "Não foi possível concluir a solicitação. Tente novamente.", 503
        )
