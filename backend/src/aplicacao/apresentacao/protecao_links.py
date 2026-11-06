from starlette.types import ASGIApp, Receive, Scope, Send

from aplicacao.apresentacao.erros import resposta_erro


class ProtecaoCorpoLinks:
    """Limita bytes reais, mesmo sem Content-Length, sem registrar o conteúdo."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        caminho = scope.get("path", "").rstrip("/")
        if (
            scope["type"] != "http"
            or not (caminho == "/api/links" or caminho.startswith("/api/links/"))
            or scope["method"] not in {"POST", "PATCH", "DELETE"}
        ):
            await self.app(scope, receive, send)
            return
        corpo = bytearray()
        while True:
            mensagem = await receive()
            if mensagem["type"] == "http.disconnect":
                return
            parte = mensagem.get("body", b"")
            if len(corpo) + len(parte) > 16384:
                await resposta_erro(
                    "corpo_excedido", "A requisição deve ter no máximo 16384 bytes.", 413
                )(scope, receive, send)
                return
            corpo.extend(parte)
            if not mensagem.get("more_body", False):
                break
        entregue = False

        async def receber_limitado():
            nonlocal entregue
            if not entregue:
                entregue = True
                return {"type": "http.request", "body": bytes(corpo), "more_body": False}
            return await receive()

        await self.app(scope, receber_limitado, send)
