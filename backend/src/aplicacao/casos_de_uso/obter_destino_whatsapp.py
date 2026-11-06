from urllib.parse import quote

from aplicacao.dominio.link import normalizar_slug
from aplicacao.dominio.repositorio_links import LinkNaoEncontrado, RepositorioLinks


class ObterDestinoWhatsApp:
    def __init__(self, links: RepositorioLinks) -> None:
        self.links = links

    async def executar(self, slug: str) -> str:
        if not isinstance(slug, str) or len(slug) > 64:
            raise LinkNaoEncontrado()
        try:
            normalizado = normalizar_slug(slug)
        except ValueError:
            raise LinkNaoEncontrado() from None
        link = await self.links.obter_publico_por_slug(normalizado)
        if link is None or not link.disponivel_para_redirecionamento:
            raise LinkNaoEncontrado()
        destino = "https://wa.me/" + link.numero_whatsapp[1:]
        if link.mensagem:
            destino += "?text=" + quote(link.mensagem, safe="", encoding="utf-8")
        return destino
