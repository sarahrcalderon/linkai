from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from aplicacao.casos_de_uso.contratos_verificacao import DesafioGerado
from aplicacao.dominio.usuario import agora_utc
from aplicacao.infraestrutura.cifra_outbox import CifraOutbox
from aplicacao.infraestrutura.modelos import ModeloEntregaEmail, ModeloVerificacaoEmail


class AgendadorEmailSQLAlchemy:
    def __init__(self, sessao: AsyncSession, cifra: CifraOutbox) -> None:
        self.sessao = sessao
        self.cifra = cifra

    async def agendar(self, destinatario: str, desafio: DesafioGerado) -> None:
        anteriores = select(ModeloVerificacaoEmail.id).where(
            ModeloVerificacaoEmail.usuario_id == desafio.usuario_id,
            ModeloVerificacaoEmail.id != desafio.id,
        )
        await self.sessao.execute(
            update(ModeloEntregaEmail)
            .where(
                ModeloEntregaEmail.id.in_(anteriores),
                ModeloEntregaEmail.estado.in_(["pendente", "processando"]),
                ModeloEntregaEmail.envio_iniciado_em.is_(None),
            )
            .values(estado="cancelada", dados_cifrados=None, posse=None, arrendado_ate=None)
        )
        self.sessao.add(
            ModeloEntregaEmail(
                id=desafio.id,
                dados_cifrados=self.cifra.cifrar(destinatario, desafio),
                estado="pendente",
                tentativas=0,
                criado_em=agora_utc(),
                expira_em=desafio.expira_em,
                proxima_tentativa=agora_utc(),
            )
        )
        await self.sessao.flush()
