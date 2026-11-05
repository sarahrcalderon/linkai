from aplicacao.casos_de_uso.contratos_autenticacao import CsrfInvalido
from aplicacao.casos_de_uso.servico_tokens import ServicoTokens
from aplicacao.dominio.repositorio_sessoes import RepositorioSessoes
from aplicacao.dominio.usuario import agora_utc


class EncerrarSessao:
    def __init__(self, sessoes: RepositorioSessoes, tokens: ServicoTokens) -> None:
        self.sessoes = sessoes
        self.tokens = tokens

    async def executar(self, token: str | None, csrf: str) -> None:
        if not token:
            return
        if not self.tokens.verificar_csrf(token, csrf):
            raise CsrfInvalido()
        await self.sessoes.revogar(self.tokens.resumir(token), agora_utc())
