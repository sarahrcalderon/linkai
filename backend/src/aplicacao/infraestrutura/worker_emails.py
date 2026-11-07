"""Execute com python -m aplicacao.infraestrutura.worker_emails, em processo separado."""

import asyncio
import signal

from aplicacao.casos_de_uso.processar_emails import ProcessarEmails
from aplicacao.configuracao import Configuracao
from aplicacao.infraestrutura.banco import BancoDados
from aplicacao.infraestrutura.cifra_outbox import CifraOutbox
from aplicacao.infraestrutura.fabrica_envio import criar_servico_email
from aplicacao.infraestrutura.repositorio_entregas import RepositorioEntregasSQLAlchemy


async def executar_worker() -> None:
    configuracao = Configuracao()
    cifra = CifraOutbox(configuracao.outbox_chave)
    banco = BancoDados(configuracao)
    parar = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sinal in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sinal, lambda *_: loop.call_soon_threadsafe(parar.set))
    try:
        async with criar_servico_email(configuracao) as envio:
            worker = ProcessarEmails(
                RepositorioEntregasSQLAlchemy(banco, configuracao), cifra, envio
            )
            while not parar.is_set():
                try:
                    trabalhou = await worker.executar_uma()
                except Exception:
                    # Erro de infraestrutura: aguarda e recupera por lease, sem despejar segredos.
                    trabalhou = False
                if not trabalhou:
                    try:
                        await asyncio.wait_for(parar.wait(), configuracao.outbox_intervalo_worker)
                    except TimeoutError:
                        pass
    finally:
        await banco.encerrar()


if __name__ == "__main__":
    try:
        asyncio.run(executar_worker())
    except Exception:
        raise SystemExit(
            "Worker de e-mails indisponível. Revise configuração e infraestrutura."
        ) from None
