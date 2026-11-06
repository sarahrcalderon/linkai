from datetime import timedelta
from uuid import uuid4

import pytest
from pydantic import SecretStr

from aplicacao.casos_de_uso.contratos_verificacao import DesafioGerado
from aplicacao.casos_de_uso.erros_envio_email import EnvioEmailPermanente
from aplicacao.configuracao import Configuracao
from aplicacao.dominio.usuario import agora_utc
from testes.homologacao.envio_controlado import EnvioRestrito, validar_banco


@pytest.mark.parametrize(
    "ambiente,url",
    [
        ("producao", "postgresql://localhost/linkai_email_homologacao45"),
        ("teste", "postgresql://localhost/linkai"),
        ("teste", "postgresql://remoto.example/linkai_email_homologacao45"),
        ("teste", None),
    ],
)
def test_recusa_banco_fora_do_escopo(ambiente, url):
    with pytest.raises(ValueError):
        validar_banco(Configuracao(_env_file=None, ambiente=ambiente, url_banco=url))


def test_aceita_somente_banco_local_exclusivo():
    validar_banco(
        Configuracao(
            _env_file=None,
            ambiente="teste",
            url_banco="postgresql://localhost/linkai_email_homologacao45",
        )
    )


async def test_allowlist_e_orcamento_de_uma_chamada(caplog):
    class EnvioFalso:
        quantidade = 0

        async def enviar_verificacao(self, destinatario, desafio):
            self.quantidade += 1

    falso = EnvioFalso()
    envio = EnvioRestrito(SecretStr("controlado@example.com"), falso)
    desafio = DesafioGerado(
        id=uuid4(),
        usuario_id=uuid4(),
        codigo=SecretStr("123456"),
        expira_em=agora_utc() + timedelta(minutes=10),
    )
    with pytest.raises(EnvioEmailPermanente):
        await envio.enviar_verificacao("outro@example.com", desafio)
    assert falso.quantidade == 0
    await envio.enviar_verificacao("controlado@example.com", desafio)
    with pytest.raises(EnvioEmailPermanente):
        await envio.enviar_verificacao("controlado@example.com", desafio)
    assert falso.quantidade == 1
    assert desafio.codigo.get_secret_value() not in caplog.text
