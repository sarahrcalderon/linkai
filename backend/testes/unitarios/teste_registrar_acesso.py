import asyncio
import logging
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from aplicacao.casos_de_uso.registrar_acesso import FalhaPersistenciaEvento, RegistrarAcesso
from aplicacao.dominio.evento_acesso import EventoDeAcesso


async def test_sucesso_uma_tentativa_sem_identificadores_no_log(caplog):
    caplog.set_level(logging.INFO, logger="aplicacao.casos_de_uso.registrar_acesso")
    persistencia = AsyncMock()
    evento = EventoDeAcesso(link_id=uuid4())
    await RegistrarAcesso(persistencia).registrar(evento)
    persistencia.persistir.assert_awaited_once_with(evento)
    assert "evento_acesso_registrado" in caplog.text
    assert str(evento.id) not in caplog.text and str(evento.link_id) not in caplog.text


@pytest.mark.parametrize(
    "categoria", ["integridade", "conexao", "banco", "pool", "conteudo-privado"]
)
async def test_falha_sanitizada_sem_retry(categoria, caplog):
    persistencia = AsyncMock()
    persistencia.persistir.side_effect = FalhaPersistenciaEvento(categoria)
    await RegistrarAcesso(persistencia).registrar(EventoDeAcesso(link_id=uuid4()))
    assert persistencia.persistir.await_count == 1
    assert "evento_acesso_nao_confirmado" in caplog.text and "conteudo-privado" not in caplog.text


async def test_timeout_cancela_e_nao_repete(caplog):
    finalizou = asyncio.Event()

    async def aguardar(evento):
        try:
            await asyncio.Event().wait()
        finally:
            finalizou.set()

    persistencia = AsyncMock()
    persistencia.persistir.side_effect = aguardar
    await RegistrarAcesso(persistencia, 0.01).registrar(EventoDeAcesso(link_id=uuid4()))
    assert finalizou.is_set() and persistencia.persistir.await_count == 1
    assert "categoria=timeout" in caplog.text


async def test_erro_programacao_nao_ocultado():
    persistencia = AsyncMock()
    persistencia.persistir.side_effect = TypeError("Falha de programação.")
    with pytest.raises(TypeError):
        await RegistrarAcesso(persistencia).registrar(EventoDeAcesso(link_id=uuid4()))
    persistencia.persistir.assert_awaited_once()
