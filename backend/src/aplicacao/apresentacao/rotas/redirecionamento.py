from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.responses import RedirectResponse

from aplicacao.apresentacao.dependencias_autenticacao import TransacaoHTTP
from aplicacao.casos_de_uso.obter_destino_whatsapp import ObterDestinoWhatsApp
from aplicacao.infraestrutura.repositorio_links import RepositorioLinksSQLAlchemy

roteador_redirecionamento = APIRouter(tags=["Redirecionamento público"])


def obter_destino(transacao: TransacaoHTTP) -> ObterDestinoWhatsApp:
    return ObterDestinoWhatsApp(RepositorioLinksSQLAlchemy(transacao))


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
