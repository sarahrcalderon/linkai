from datetime import UTC, datetime
from uuid import UUID

import pytest

from aplicacao.dominio.usuario import Usuario


def test_normaliza_usuario_e_preserva_privacidade():
    usuario = Usuario(nome=" Ana ", email=" ANA@EXEMPLO.COM ", senha_hash="hash-de-fixture")
    assert usuario.nome == "Ana"
    assert usuario.email == "ana@exemplo.com"
    assert isinstance(usuario.id, UUID)
    assert usuario.ativo and not usuario.email_verificado
    assert usuario.criado_em.tzinfo == UTC
    assert "hash-de-fixture" not in repr(usuario)


@pytest.mark.parametrize(
    "alteracoes",
    [
        {"nome": " "},
        {"nome": "a" * 101},
        {"email": " "},
        {"email": "a" * 255},
        {"senha_hash": ""},
        {"criado_em": datetime(2026, 1, 1)},
    ],
)
def test_rejeita_estado_invalido(alteracoes):
    dados = dict(nome="Ana", email="ana@exemplo.com", senha_hash="hash-de-fixture")
    with pytest.raises(ValueError):
        Usuario(**(dados | alteracoes))
