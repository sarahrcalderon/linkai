from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from aplicacao.apresentacao.rotas.saude import roteador_saude
from aplicacao.configuracao import Configuracao


def criar_aplicacao(configuracao: Configuracao | None = None) -> FastAPI:
    configuracao = configuracao or Configuracao()
    app = FastAPI(title="API de Linkai", version="0.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=configuracao.origens_permitidas,
        allow_credentials=False,
        allow_methods=["GET"],
        allow_headers=["Content-Type"],
    )
    app.include_router(roteador_saude, prefix="/api")
    return app


app = criar_aplicacao()
