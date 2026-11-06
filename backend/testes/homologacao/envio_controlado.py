"""Homologação local: diagnóstico por padrão; envio único apenas com autorização."""

import argparse
import asyncio
import logging
import os
from pathlib import Path

from pydantic import SecretStr, validate_email
from sqlalchemy import select, text

from aplicacao.casos_de_uso.contratos_verificacao import DesafioGerado, ServicoEnvioEmail
from aplicacao.casos_de_uso.erros_envio_email import EnvioEmailPermanente
from aplicacao.casos_de_uso.processar_emails import ProcessarEmails
from aplicacao.configuracao import Configuracao
from aplicacao.infraestrutura.banco import BancoDados, preparar_url_banco
from aplicacao.infraestrutura.brevo.configuracao import ConfiguracaoBrevo
from aplicacao.infraestrutura.brevo.diagnostico import registrador
from aplicacao.infraestrutura.brevo.fabrica import criar_envio_brevo
from aplicacao.infraestrutura.cifra_outbox import CifraOutbox
from aplicacao.infraestrutura.modelos import ModeloEntregaEmail, ModeloUsuario
from aplicacao.infraestrutura.repositorio_entregas import RepositorioEntregasSQLAlchemy

BANCO_HOMOLOGACAO = "linkai_email_homologacao45"


def validar_banco(configuracao: Configuracao) -> None:
    if configuracao.url_banco is None or configuracao.ambiente != "teste":
        raise ValueError("Exige configuração de homologação isolada.")
    url = preparar_url_banco(configuracao.url_banco.get_secret_value())
    if url.host not in {"localhost", "127.0.0.1"} or url.database != BANCO_HOMOLOGACAO:
        raise ValueError("Exige banco local exclusivo de homologação.")


class EnvioRestrito:
    """Uma chamada ao adaptador, para uma allowlist unitária mantida em memória."""

    def __init__(self, destinatario: SecretStr, envio: ServicoEnvioEmail) -> None:
        _, endereco = validate_email(destinatario.get_secret_value())
        self._destinatario = SecretStr(endereco)
        self._envio = envio
        self._utilizado = False

    async def enviar_verificacao(self, destinatario: str, desafio: DesafioGerado) -> None:
        if self._utilizado or destinatario != self._destinatario.get_secret_value():
            raise EnvioEmailPermanente()
        self._utilizado = True
        await self._envio.enviar_verificacao(destinatario, desafio)


async def executar(autorizar: bool) -> None:
    configuracao = Configuracao()
    validar_banco(configuracao)
    banco = BancoDados(configuracao)
    try:
        async with banco.transacao() as sessao:
            if await sessao.scalar(text("SHOW server_version")) != "18.6":
                raise ValueError("Exige PostgreSQL 18.6 para esta homologação.")
            usuarios = (await sessao.scalars(select(ModeloUsuario))).all()
            entregas = (await sessao.scalars(select(ModeloEntregaEmail))).all()
        print(f"Diagnóstico local: {len(usuarios)} usuário(s), {len(entregas)} intenção(ões).")
        if not autorizar:
            print("Sem autorização de envio: nenhum adaptador HTTPS foi iniciado.")
            return
        # Não reutiliza fila antiga, não retoma tentativas nem resultados indeterminados.
        destinatario = SecretStr(os.environ.get("HOMOLOGACAO_DESTINATARIO", ""))
        _, endereco = validate_email(destinatario.get_secret_value())
        if (
            len(usuarios) != 1
            or len(entregas) != 1
            or usuarios[0].email != endereco
            or usuarios[0].email_verificado
            or entregas[0].estado != "pendente"
            or entregas[0].tentativas != 0
            or entregas[0].envio_iniciado_em is not None
        ):
            raise ValueError("Fila não elegível para envio único controlado.")
        # Uma mensagem, uma chamada HTTPS. 429 não causa retentativa neste processo.
        brevo = ConfiguracaoBrevo(limite_tentativas=1)
        cifra = CifraOutbox(configuracao.outbox_chave)
        caminho_log = Path(__file__).resolve().parents[3] / ".postgres-teste/brevo-diagnostico.log"
        with logging.FileHandler(caminho_log, encoding="utf-8") as arquivo_log:
            arquivo_log.setFormatter(logging.Formatter("%(asctime)s %(message)s"))
            registrador.addHandler(arquivo_log)
            try:
                async with criar_envio_brevo(brevo) as envio:
                    worker = ProcessarEmails(
                        RepositorioEntregasSQLAlchemy(banco, configuracao),
                        cifra,
                        EnvioRestrito(destinatario, envio),
                    )
                    await worker.executar_uma()
            finally:
                registrador.removeHandler(arquivo_log)
        async with banco.transacao() as sessao:
            estado = await sessao.scalar(select(ModeloEntregaEmail.estado))
        print(f"Processamento único encerrado. Estado local: {estado}.")
        print("Estado enviada significa aceitação pela API; recebimento exige confirmação humana.")
    finally:
        await banco.encerrar()


if __name__ == "__main__":
    argumentos = argparse.ArgumentParser(description=__doc__)
    argumentos.add_argument("--autorizar-envio-real", action="store_true")
    opcoes = argumentos.parse_args()
    try:
        asyncio.run(executar(opcoes.autorizar_envio_real))
    except (Exception, KeyboardInterrupt):
        raise SystemExit(
            "Homologação interrompida ou bloqueada. Confira configuração e estado local; "
            "não repita envios sem revisar o resultado e obter autorização."
        ) from None
