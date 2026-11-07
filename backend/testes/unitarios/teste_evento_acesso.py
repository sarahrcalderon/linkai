from dataclasses import FrozenInstanceError, fields
from datetime import UTC, datetime, timedelta, timezone
from uuid import UUID, uuid4

import pytest

from aplicacao.dominio.evento_acesso import EventoDeAcesso


def test_evento_minimo_uuid_utc_imutavel():
    instante = datetime(2026, 1, 2, 12, tzinfo=timezone(timedelta(hours=-3)))
    evento = EventoDeAcesso(link_id=uuid4(), acessado_em=instante)
    assert isinstance(evento.id, UUID)
    assert evento.acessado_em == datetime(2026, 1, 2, 15, tzinfo=UTC)
    assert evento.acessado_em.tzinfo is UTC
    assert {c.name for c in fields(evento)} == {"id", "link_id", "acessado_em"}
    with pytest.raises(FrozenInstanceError):
        evento.link_id = uuid4()


@pytest.mark.parametrize(
    "ajustes",
    [
        {"id": "invalido"},
        {"link_id": None},
        {"acessado_em": None},
        {"acessado_em": datetime(2026, 1, 1)},
        {"acessado_em": "2026-01-01"},
    ],
)
def test_campos_invalidos(ajustes):
    with pytest.raises(ValueError):
        EventoDeAcesso(**({"link_id": uuid4()} | ajustes))


@pytest.mark.parametrize(
    "campo",
    [
        "ip",
        "user_agent",
        "cookie",
        "token",
        "sessao_id",
        "numero_whatsapp",
        "localizacao",
        "dispositivo_id",
        "slug",
        "mensagem",
    ],
)
def test_nao_aceita_metadados_pessoais(campo):
    with pytest.raises(TypeError):
        EventoDeAcesso(link_id=uuid4(), **{campo: "dado-nao-admitido"})
