import math
from datetime import timedelta
from uuid import uuid4

from sqlalchemy import select, update

from aplicacao.configuracao import Configuracao
from aplicacao.dominio.entrega_email import EntregaReservada
from aplicacao.dominio.usuario import agora_utc
from aplicacao.infraestrutura.banco import BancoDados
from aplicacao.infraestrutura.modelos import (
    ModeloEntregaEmail,
    ModeloUsuario,
    ModeloVerificacaoEmail,
)
from aplicacao.infraestrutura.repositorio_sessoes import converter_utc


class RepositorioEntregasSQLAlchemy:
    def __init__(self, banco: BancoDados, configuracao: Configuracao) -> None:
        self.banco = banco
        self.configuracao = configuracao

    async def reservar(self) -> EntregaReservada | None:
        agora = agora_utc()
        async with self.banco.transacao() as sessao:
            # Recuperação sem reenviar mensagens cujo HTTPS pode ter sido iniciado.
            for iniciou, estado in ((False, "pendente"), (True, "indeterminada")):
                consulta = (
                    update(ModeloEntregaEmail)
                    .where(
                        ModeloEntregaEmail.estado == "processando",
                        ModeloEntregaEmail.arrendado_ate <= agora,
                        ModeloEntregaEmail.envio_iniciado_em.is_not(None)
                        if iniciou
                        else ModeloEntregaEmail.envio_iniciado_em.is_(None),
                    )
                    .values(
                        estado=estado,
                        posse=None,
                        arrendado_ate=None,
                        ultima_falha="worker_interrompido",
                    )
                )
                if iniciou:
                    consulta = consulta.values(dados_cifrados=None)
                await sessao.execute(consulta)
            await sessao.execute(
                update(ModeloEntregaEmail)
                .where(
                    ModeloEntregaEmail.estado == "pendente",
                    ModeloEntregaEmail.expira_em <= agora,
                )
                .values(estado="cancelada", dados_cifrados=None, ultima_falha="prazo_encerrado")
            )
            modelo = await sessao.scalar(
                select(ModeloEntregaEmail)
                .where(
                    ModeloEntregaEmail.estado == "pendente",
                    ModeloEntregaEmail.proxima_tentativa <= agora,
                    ModeloEntregaEmail.tentativas < self.configuracao.outbox_limite_tentativas,
                )
                .order_by(ModeloEntregaEmail.criado_em, ModeloEntregaEmail.id)
                .with_for_update(skip_locked=True)
                .limit(1)
            )
            if modelo is None:
                return None
            modelo.estado = "processando"
            modelo.posse = uuid4()
            modelo.arrendado_ate = agora + timedelta(
                seconds=self.configuracao.outbox_lease_segundos
            )
            return EntregaReservada(modelo.id, modelo.posse, modelo.dados_cifrados or "")

    async def iniciar(self, reserva: EntregaReservada) -> bool:
        agora = agora_utc()
        async with self.banco.transacao() as sessao:
            verificacao = await sessao.get(ModeloVerificacaoEmail, reserva.id)
            if verificacao is None:
                return False
            usuario = await sessao.scalar(
                select(ModeloUsuario)
                .where(ModeloUsuario.id == verificacao.usuario_id)
                .with_for_update()
            )
            modelo = await sessao.scalar(
                select(ModeloEntregaEmail)
                .where(ModeloEntregaEmail.id == reserva.id)
                .with_for_update()
            )
            if (
                modelo is None
                or modelo.estado != "processando"
                or modelo.posse != reserva.posse
                or converter_utc(modelo.arrendado_ate) <= agora
            ):
                return False
            # Recarrega o desafio após obter o bloqueio do usuário.
            await sessao.refresh(verificacao)
            if (
                usuario is None
                or not usuario.ativo
                or usuario.email_verificado
                or verificacao.utilizado_em is not None
                or verificacao.invalidado_em is not None
                or verificacao.tentativas >= verificacao.limite_tentativas
                or converter_utc(verificacao.expira_em) <= agora
            ):
                modelo.estado, modelo.dados_cifrados = "cancelada", None
                modelo.posse = modelo.arrendado_ate = None
                return False
            modelo.envio_iniciado_em = agora
            modelo.tentativas += 1
        return True

    async def concluir(
        self, reserva: EntregaReservada, resultado: str, aguardar_segundos: float | None = None
    ) -> None:
        agora = agora_utc()
        async with self.banco.transacao() as sessao:
            modelo = await sessao.scalar(
                select(ModeloEntregaEmail)
                .where(ModeloEntregaEmail.id == reserva.id)
                .with_for_update()
            )
            if modelo is None or modelo.posse != reserva.posse or modelo.estado != "processando":
                return
            if resultado == "temporario":
                espera = min(30 * 2 ** min(modelo.tentativas - 1, 5), 900)
                espera = max(espera, aguardar_segundos or 0)
                if (
                    not math.isfinite(espera)
                    or espera >= (converter_utc(modelo.expira_em) - agora).total_seconds()
                ):
                    modelo.estado, modelo.dados_cifrados = "falha", None
                    modelo.ultima_falha = "prazo_encerrado"
                    modelo.posse = modelo.arrendado_ate = None
                    return
                proxima = agora + timedelta(seconds=espera)
                if modelo.tentativas < self.configuracao.outbox_limite_tentativas and (
                    proxima < converter_utc(modelo.expira_em)
                ):
                    modelo.estado = "pendente"
                    modelo.proxima_tentativa = proxima
                    modelo.envio_iniciado_em = None
                else:
                    modelo.estado = "falha"
            else:
                modelo.estado = resultado
            modelo.ultima_falha = None if resultado == "enviada" else resultado
            modelo.posse = modelo.arrendado_ate = None
            if modelo.estado != "pendente":
                modelo.dados_cifrados = None
