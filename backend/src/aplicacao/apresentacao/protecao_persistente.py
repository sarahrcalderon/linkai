from starlette.types import ASGIApp, Receive, Scope, Send

from aplicacao.apresentacao.erros import resposta_erro
from aplicacao.infraestrutura.limite_persistente import permitir_requisicao


class ProtecaoPersistente:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        caminho = scope.get("path", "").rstrip("/")
        if (
            scope["type"] != "http"
            or scope["method"] != "POST"
            or caminho
            not in {
                "/api/autenticacao/cadastro",
                "/api/autenticacao/login",
                "/api/autenticacao/verificar-email",
                "/api/autenticacao/reenviar-codigo",
            }
        ):
            await self.app(scope, receive, send)
            return
        estado = scope["app"].state
        configuracao = estado.configuracao
        origem_http = dict(scope.get("headers", [])).get(b"origin")
        if (
            origem_http is not None
            and origem_http.decode("latin-1") not in configuracao.origens_permitidas
        ):
            await resposta_erro(
                "csrf_invalido", "Não foi possível validar a origem da solicitação.", 403
            )(scope, receive, send)
            return
        if caminho.endswith("/cadastro"):
            limite, janela = (
                configuracao.cadastro_limite_tentativas,
                configuracao.cadastro_janela_segundos,
            )
        elif caminho.endswith("/login"):
            limite, janela = (
                configuracao.login_limite_tentativas,
                configuracao.login_janela_segundos,
            )
        else:
            limite, janela = configuracao.verificacao_limite_requisicoes, 900
        try:
            permitido = await permitir_requisicao(
                estado.banco,
                configuracao,
                (scope.get("client") or ("desconhecida", 0))[0],
                caminho,
                limite,
                janela,
            )
        except Exception:
            # Executado antes do parsing; não registra payload ou exceção de infraestrutura.
            await resposta_erro(
                "servico_indisponivel",
                "Não foi possível concluir a solicitação. Tente novamente.",
                503,
            )(scope, receive, send)
            return
        if not permitido:
            resposta = resposta_erro(
                "limite_excedido", "Muitas tentativas. Aguarde antes de tentar novamente.", 429
            )
            resposta.headers["Retry-After"] = str(janela)
            await resposta(scope, receive, send)
            return
        await self.app(scope, receive, send)
