from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from aplicacao.apresentacao.erros import registrar_tratamento_erros
from aplicacao.apresentacao.protecao_cadastro import ProtecaoCadastro
from aplicacao.apresentacao.protecao_links import ProtecaoCorpoLinks
from aplicacao.apresentacao.protecao_persistente import ProtecaoPersistente
from aplicacao.apresentacao.rotas.autenticacao import roteador_autenticacao
from aplicacao.apresentacao.rotas.cadastro import roteador_cadastro
from aplicacao.apresentacao.rotas.links import roteador_links
from aplicacao.apresentacao.rotas.redirecionamento import roteador_redirecionamento
from aplicacao.apresentacao.rotas.saude import roteador_saude
from aplicacao.apresentacao.rotas.verificacao_email import roteador_verificacao
from aplicacao.configuracao import Configuracao
from aplicacao.infraestrutura.banco import BancoDados
from aplicacao.infraestrutura.hash_senha import HashSenhaArgon2id
from aplicacao.infraestrutura.tokens import TokensSeguros


def criar_aplicacao(configuracao: Configuracao | None = None) -> FastAPI:
    configuracao = configuracao or Configuracao()

    @asynccontextmanager
    async def ciclo_vida(app: FastAPI):
        banco = BancoDados(configuracao) if configuracao.url_banco else None
        app.state.banco = banco
        app.state.hash_senha = HashSenhaArgon2id()
        app.state.tokens = TokensSeguros()
        try:
            app.state.hash_ficticio = await app.state.hash_senha.gerar(app.state.tokens.gerar())
            yield
        finally:
            if banco is not None:
                await banco.encerrar()

    app = FastAPI(title="API de Linkai", version="0.1.0", lifespan=ciclo_vida)
    app.state.configuracao = configuracao
    registrar_tratamento_erros(app)
    app.add_middleware(ProtecaoCorpoLinks)
    app.add_middleware(ProtecaoPersistente)
    for caminho in ("/api/autenticacao/verificar-email", "/api/autenticacao/reenviar-codigo"):
        app.add_middleware(
            ProtecaoCadastro,
            limite=configuracao.verificacao_limite_requisicoes,
            janela=900,
            caminho=caminho,
        )
    app.add_middleware(
        ProtecaoCadastro,
        limite=configuracao.cadastro_limite_tentativas,
        janela=configuracao.cadastro_janela_segundos,
    )
    app.add_middleware(
        ProtecaoCadastro,
        limite=configuracao.login_limite_tentativas,
        janela=configuracao.login_janela_segundos,
        caminho="/api/autenticacao/login",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=configuracao.origens_permitidas,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "DELETE"],
        allow_headers=["Content-Type", "X-CSRF-Token"],
    )
    app.include_router(roteador_saude, prefix="/api")
    app.include_router(roteador_redirecionamento)
    app.include_router(roteador_links, prefix="/api")
    app.include_router(roteador_cadastro, prefix="/api")
    app.include_router(roteador_autenticacao, prefix="/api")
    app.include_router(roteador_verificacao, prefix="/api")
    return app


app = criar_aplicacao()
