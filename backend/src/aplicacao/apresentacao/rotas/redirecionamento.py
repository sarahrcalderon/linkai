from typing import Annotated

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse

from aplicacao.casos_de_uso.obter_destino_whatsapp import ObterDestinoWhatsApp
from aplicacao.casos_de_uso.registrar_acesso import RegistrarAcesso
from aplicacao.infraestrutura.registro_acessos import (
    ConsultaLinkPublicoSQLAlchemy,
    PersistenciaEventoSQLAlchemy,
)

roteador_redirecionamento = APIRouter(tags=["Redirecionamento público"])


def obter_destino(requisicao: Request) -> ObterDestinoWhatsApp:
    banco = requisicao.app.state.banco
    if banco is None:
        raise RuntimeError("Persistência não configurada.")
    return ObterDestinoWhatsApp(
        ConsultaLinkPublicoSQLAlchemy(banco),
        RegistrarAcesso(
            PersistenciaEventoSQLAlchemy(banco),
            requisicao.app.state.configuracao.analytics_prazo_segundos,
        ),
    )


@roteador_redirecionamento.get("/r/{slug:path}", status_code=302, response_class=RedirectResponse)
async def redirecionar_whatsapp(
    slug: str, caso: Annotated[ObterDestinoWhatsApp, Depends(obter_destino)]
) -> RedirectResponse:
    destino = await caso.executar(slug)
    return RedirectResponse(
        destino,
        status_code=302,
        headers={
            "Cache-Control": "no-store, max-age=0",
            "Referrer-Policy": "no-referrer",
            "X-Content-Type-Options": "nosniff",
        },
    )
