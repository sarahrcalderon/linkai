from datetime import timedelta

from aplicacao.casos_de_uso.contratos_autenticacao import (
    CredenciaisInvalidas,
    EntradaLogin,
    ResultadoLogin,
)
from aplicacao.casos_de_uso.servico_hash import ServicoHashSenha
from aplicacao.casos_de_uso.servico_tokens import ServicoTokens
from aplicacao.dominio.repositorio_sessoes import RepositorioSessoes
from aplicacao.dominio.repositorio_usuarios import RepositorioUsuarios
from aplicacao.dominio.sessao import Sessao
from aplicacao.dominio.usuario import agora_utc


class AutenticarUsuario:
    def __init__(
        self,
        usuarios: RepositorioUsuarios,
        sessoes: RepositorioSessoes,
        hash_senha: ServicoHashSenha,
        tokens: ServicoTokens,
        hash_ficticio: str,
        duracao_segundos: int,
    ) -> None:
        self.usuarios = usuarios
        self.sessoes = sessoes
        self.hash_senha = hash_senha
        self.tokens = tokens
        self.hash_ficticio = hash_ficticio
        self.duracao_segundos = duracao_segundos

    async def executar(self, entrada: EntradaLogin, token_anterior: str | None) -> ResultadoLogin:
        usuario = await self.usuarios.obter_por_email(entrada.email)
        senha_correta = await self.hash_senha.verificar(
            usuario.senha_hash if usuario else self.hash_ficticio,
            entrada.senha.get_secret_value(),
        )
        if (
            not senha_correta
            or usuario is None
            or not usuario.ativo
            or not usuario.email_verificado
        ):
            raise CredenciaisInvalidas()
        agora = agora_utc()
        token = self.tokens.gerar()
        sessao = Sessao(
            usuario_id=usuario.id,
            token_hash=self.tokens.resumir(token),
            criado_em=agora,
            expira_em=agora + timedelta(seconds=self.duracao_segundos),
        )
        if token_anterior:
            await self.sessoes.revogar(self.tokens.resumir(token_anterior), agora)
        await self.sessoes.adicionar(sessao)
        return ResultadoLogin(
            usuario=usuario,
            csrf=self.tokens.gerar_csrf(token),
            token=token,
            expira_em=sessao.expira_em,
        )
