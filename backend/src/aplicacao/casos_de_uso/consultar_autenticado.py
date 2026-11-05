from aplicacao.casos_de_uso.contratos_autenticacao import ResultadoAutenticacao, SessaoInvalida
from aplicacao.casos_de_uso.servico_tokens import ServicoTokens
from aplicacao.dominio.repositorio_sessoes import RepositorioSessoes
from aplicacao.dominio.repositorio_usuarios import RepositorioUsuarios
from aplicacao.dominio.usuario import agora_utc


class ConsultarAutenticado:
    def __init__(
        self, usuarios: RepositorioUsuarios, sessoes: RepositorioSessoes, tokens: ServicoTokens
    ) -> None:
        self.usuarios = usuarios
        self.sessoes = sessoes
        self.tokens = tokens

    async def executar(self, token: str | None) -> ResultadoAutenticacao:
        if not token:
            raise SessaoInvalida()
        sessao = await self.sessoes.obter_por_hash(self.tokens.resumir(token))
        if sessao is None or not sessao.esta_valida(agora_utc()):
            raise SessaoInvalida()
        usuario = await self.usuarios.obter_por_id(sessao.usuario_id)
        if usuario is None or not usuario.ativo or not usuario.email_verificado:
            raise SessaoInvalida()
        return ResultadoAutenticacao(usuario=usuario, csrf=self.tokens.gerar_csrf(token))
