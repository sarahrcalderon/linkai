from collections.abc import Awaitable, Callable
from uuid import UUID

from aplicacao.casos_de_uso.contratos_cadastro import EntradaCadastro
from aplicacao.casos_de_uso.servico_hash import ServicoHashSenha
from aplicacao.dominio.repositorio_usuarios import EmailJaCadastrado, RepositorioUsuarios
from aplicacao.dominio.usuario import Usuario


class CadastrarUsuario:
    def __init__(
        self,
        repositorio: RepositorioUsuarios,
        hash_senha: ServicoHashSenha,
        solicitar_verificacao: Callable[[UUID], Awaitable[object]] | None = None,
    ) -> None:
        self.repositorio = repositorio
        self.hash_senha = hash_senha
        self.solicitar_verificacao = solicitar_verificacao

    async def executar(self, entrada: EntradaCadastro) -> None:
        # Calcula o hash também para duplicatas, sem caminho rápido que revele contas.
        senha_hash = await self.hash_senha.gerar(entrada.senha.get_secret_value())
        usuario = Usuario(nome=entrada.nome, email=entrada.email, senha_hash=senha_hash)
        try:
            await self.repositorio.adicionar(usuario)
        except EmailJaCadastrado:
            # A resposta pública é a mesma; o índice único decide disputas concorrentes.
            return
        if self.solicitar_verificacao is not None:
            await self.solicitar_verificacao(usuario.id)
