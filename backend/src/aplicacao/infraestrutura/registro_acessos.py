from sqlalchemy.exc import DBAPIError, IntegrityError, OperationalError
from sqlalchemy.exc import TimeoutError as PrazoPoolExcedido

from aplicacao.casos_de_uso.registrar_acesso import FalhaPersistenciaEvento
from aplicacao.dominio.evento_acesso import EventoDeAcesso
from aplicacao.dominio.link import Link
from aplicacao.infraestrutura.banco import BancoDados
from aplicacao.infraestrutura.repositorio_eventos_acesso import RepositorioEventosAcessoSQLAlchemy
from aplicacao.infraestrutura.repositorio_links import RepositorioLinksSQLAlchemy


class ConsultaLinkPublicoSQLAlchemy:
    def __init__(self, banco: BancoDados) -> None:
        self.banco = banco

    async def obter_publico_por_slug(self, slug: str) -> Link | None:
        async with self.banco.transacao() as sessao:
            return await RepositorioLinksSQLAlchemy(sessao).obter_publico_por_slug(slug)


class PersistenciaEventoSQLAlchemy:
    def __init__(self, banco: BancoDados) -> None:
        self.banco = banco

    async def persistir(self, evento: EventoDeAcesso) -> None:
        try:
            async with self.banco.transacao() as sessao:
                await RepositorioEventosAcessoSQLAlchemy(sessao).adicionar(evento)
        except IntegrityError:
            raise FalhaPersistenciaEvento("integridade") from None
        except OperationalError:
            raise FalhaPersistenciaEvento("conexao") from None
        except PrazoPoolExcedido:
            raise FalhaPersistenciaEvento("pool") from None
        except OSError:
            raise FalhaPersistenciaEvento("conexao") from None
        except DBAPIError:
            raise FalhaPersistenciaEvento("banco") from None
