from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


def resposta_erro(codigo: str, mensagem: str, status: int, **detalhes) -> JSONResponse:
    return JSONResponse(
        status_code=status, content={"erro": {"codigo": codigo, "mensagem": mensagem, **detalhes}}
    )


def registrar_tratamento_erros(app: FastAPI) -> None:
    @app.exception_handler(RequestValidationError)
    async def tratar_validacao(requisicao: Request, erro: RequestValidationError):
        mensagens = {
            "nome": "Informe um nome com 2 a 100 caracteres, sem caracteres de controle.",
            "email": "Informe um e-mail válido com até 254 caracteres.",
            "senha": "Informe uma senha com 12 a 128 caracteres, sem caracteres de controle.",
        }
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
                    "mensagem": mensagens.get(
                        campo, "Envie apenas nome, e-mail e senha em um objeto JSON válido."
                    ),
                }
            )
        return resposta_erro("dados_invalidos", "Revise os dados informados.", 422, campos=campos)

    @app.exception_handler(Exception)
    async def tratar_falha(requisicao: Request, erro: Exception):
        return resposta_erro(
            "servico_indisponivel", "Não foi possível concluir a solicitação. Tente novamente.", 503
        )
