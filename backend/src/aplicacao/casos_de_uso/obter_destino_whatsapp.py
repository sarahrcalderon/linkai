from urllib.parse import quote

from aplicacao.casos_de_uso.registrar_acesso import RegistradorAcesso
from aplicacao.dominio.evento_acesso import EventoDeAcesso
from aplicacao.dominio.link import normalizar_slug
from aplicacao.dominio.repositorio_links import ConsultaLinkPublico, LinkNaoEncontrado


class ObterDestinoWhatsApp:
    def __init__(
        self, links: ConsultaLinkPublico, acessos: RegistradorAcesso | None = None
    ) -> None:
        self.links = links
        self.acessos = acessos

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
        if self.acessos is not None:
            await self.acessos.registrar(EventoDeAcesso(link_id=link.id))
        return destino
