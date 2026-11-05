from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from aplicacao.apresentacao.erros import registrar_tratamento_erros
from aplicacao.apresentacao.protecao_cadastro import ProtecaoCadastro
from aplicacao.apresentacao.rotas.cadastro import roteador_cadastro
from aplicacao.apresentacao.rotas.saude import roteador_saude
from aplicacao.configuracao import Configuracao
from aplicacao.infraestrutura.banco import BancoDados
from aplicacao.infraestrutura.hash_senha import HashSenhaArgon2id


def criar_aplicacao(configuracao: Configuracao | None = None) -> FastAPI:
    configuracao = configuracao or Configuracao()

    @asynccontextmanager
    async def ciclo_vida(app: FastAPI):
        banco = BancoDados(configuracao) if configuracao.url_banco else None
        app.state.banco = banco
        app.state.hash_senha = HashSenhaArgon2id()
        try:
            yield
        finally:
            if banco is not None:
                await banco.encerrar()

    app = FastAPI(title="API de Linkai", version="0.1.0", lifespan=ciclo_vida)
    registrar_tratamento_erros(app)
    app.add_middleware(
        ProtecaoCadastro,
        limite=configuracao.cadastro_limite_tentativas,
        janela=configuracao.cadastro_janela_segundos,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=configuracao.origens_permitidas,
        allow_credentials=False,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type"],
    )
    app.include_router(roteador_saude, prefix="/api")
    app.include_router(roteador_cadastro, prefix="/api")
    return app


app = criar_aplicacao()
