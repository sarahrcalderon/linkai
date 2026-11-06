from datetime import timedelta
from uuid import uuid4

import pytest
from cryptography.fernet import Fernet
from pydantic import SecretStr

from aplicacao.casos_de_uso.contratos_entrega import ConteudoEntregaInvalido
from aplicacao.casos_de_uso.contratos_verificacao import DesafioGerado
from aplicacao.dominio.usuario import agora_utc
from aplicacao.infraestrutura.cifra_outbox import CifraOutbox


def test_cifra_autenticada_e_vinculo_ao_registro():
    cifra = CifraOutbox(SecretStr(Fernet.generate_key().decode()))
    desafio = DesafioGerado(
        id=uuid4(),
        usuario_id=uuid4(),
        codigo="012345",
        expira_em=agora_utc() + timedelta(minutes=10),
    )
    primeiro = cifra.cifrar("pessoa@example.com", desafio)
    segundo = cifra.cifrar("pessoa@example.com", desafio)
    assert primeiro != segundo and "012345" not in primeiro and "pessoa@example.com" not in primeiro
    assert cifra.decifrar(primeiro, desafio.id)[1].codigo.get_secret_value() == "012345"
    for dado, identificador in ((primeiro, uuid4()), ("alterado" + primeiro, desafio.id)):
        with pytest.raises(ConteudoEntregaInvalido) as erro:
            cifra.decifrar(dado, identificador)
        assert "012345" not in str(erro.value)


@pytest.mark.parametrize("chave", [None, SecretStr("invalida")])
def test_chave_invalida_falha_segura(chave):
    with pytest.raises(ValueError, match="OUTBOX_CHAVE"):
        CifraOutbox(chave)
