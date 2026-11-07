"""Entrega local real opcional, sem consultar conteúdo ou código no Mailpit."""

import os
from datetime import timedelta
from uuid import uuid4

import httpx
import pytest

from aplicacao.casos_de_uso.contratos_verificacao import DesafioGerado
from aplicacao.configuracao import Configuracao
from aplicacao.dominio.usuario import agora_utc
from aplicacao.infraestrutura.fabrica_envio import criar_servico_email


async def test_entrega_real_smtp_mailpit_sem_extrair_codigo():
    if os.getenv("TESTAR_MAILPIT") != "1":
        pytest.skip("Requer Mailpit local e TESTAR_MAILPIT=1; não usa serviço externo.")
    async with httpx.AsyncClient(base_url="http://127.0.0.1:8025", trust_env=False) as cliente:
        antes = (await cliente.get("/api/v1/messages")).json()["total"]
        config = Configuracao(_env_file=None, email_provedor="mailpit")
        async with criar_servico_email(config) as envio:
            await envio.enviar_verificacao(
                "smtp-fixture@example.com",
                DesafioGerado(
                    id=uuid4(),
                    usuario_id=uuid4(),
                    codigo="012345",
                    expira_em=agora_utc() + timedelta(minutes=10),
                ),
            )
        depois = (await cliente.get("/api/v1/messages")).json()["total"]
        assert depois == antes + 1
