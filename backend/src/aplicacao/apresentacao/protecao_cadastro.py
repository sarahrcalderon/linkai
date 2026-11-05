import math
from collections import deque
from time import monotonic

from starlette.types import ASGIApp, Receive, Scope, Send

from aplicacao.apresentacao.erros import resposta_erro


class ProtecaoCadastro:
    def __init__(self, app: ASGIApp, limite: int, janela: int) -> None:
        self.app = app
        self.limite = limite
        self.janela = janela
        self.tentativas: dict[str, deque[float]] = {}

    def permitir(self, origem: str) -> int:
        agora = monotonic()
        # Guarda somente endereços com tentativas dentro da janela.
        expirados = [
            chave for chave, fila in self.tentativas.items() if fila[-1] <= agora - self.janela
        ]
        for chave in expirados:
            del self.tentativas[chave]
        fila = self.tentativas.get(origem)
        if fila is None:
            if len(self.tentativas) >= 10000:
                return self.janela
            fila = self.tentativas.setdefault(origem, deque())
        while fila and fila[0] <= agora - self.janela:
            fila.popleft()
        if len(fila) >= self.limite:
            return max(1, math.ceil(fila[0] + self.janela - agora))
        fila.append(agora)
        return 0

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if (
            scope["type"] != "http"
            or scope["method"] != "POST"
            or (scope["path"].rstrip("/") != "/api/autenticacao/cadastro")
        ):
            await self.app(scope, receive, send)
            return
        origem = scope.get("client")
        espera = self.permitir(origem[0] if origem else "desconhecida")
        if espera:
            resposta = resposta_erro(
                "limite_excedido", "Muitas tentativas. Aguarde antes de tentar novamente.", 429
            )
            resposta.headers["Retry-After"] = str(espera)
            await resposta(scope, receive, send)
            return
        # Conta bytes efetivamente recebidos, inclusive sem Content-Length ou em chunks.
        corpo = bytearray()
        while True:
            mensagem = await receive()
            if mensagem["type"] == "http.disconnect":
                return
            parte = mensagem.get("body", b"")
            if len(corpo) + len(parte) > 8192:
                await resposta_erro(
                    "corpo_excedido", "A requisição deve ter no máximo 8192 bytes.", 413
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
