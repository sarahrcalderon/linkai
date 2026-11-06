from datetime import timedelta
from unittest.mock import patch
from uuid import uuid4

import pytest
from pydantic import SecretStr, ValidationError

from aplicacao.configuracao import Configuracao
from aplicacao.dominio.usuario import agora_utc
from aplicacao.dominio.verificacao_email import VerificacaoEmail
from aplicacao.infraestrutura.codigos_verificacao import CodigosVerificacaoHMAC


def test_codigo_usa_secrets_e_preserva_zeros():
    servico = CodigosVerificacaoHMAC(SecretStr("s" * 32))
    with patch(
        "aplicacao.infraestrutura.codigos_verificacao.secrets.randbelow", return_value=12
    ) as gerar:
        assert servico.gerar() == "000012"
        gerar.assert_called_once_with(1000000)


def test_hmac_vincula_contexto_e_segredo_sem_expor_codigo():
    servico = CodigosVerificacaoHMAC(SecretStr("s" * 32))
    desafio, usuario = uuid4(), uuid4()
    resumo = servico.resumir("123456", desafio, usuario)
    assert len(resumo) == 64 and resumo != "123456"
    assert servico.conferir("123456", resumo, desafio, usuario)
    assert not servico.conferir("654321", resumo, desafio, usuario)
    assert not servico.conferir("123456", resumo, uuid4(), usuario)
    assert not servico.conferir("123456", resumo, desafio, uuid4())
    assert not CodigosVerificacaoHMAC(SecretStr("t" * 32)).conferir(
        "123456", resumo, desafio, usuario
    )
    assert "s" * 32 not in repr(servico)


@pytest.mark.parametrize("codigo", ["", "12345", "1234567", "１２３４５６", "abcdef"])
def test_formato_invalido(codigo):
    servico = CodigosVerificacaoHMAC(SecretStr("s" * 32))
    assert not servico.conferir(codigo, "a" * 64, uuid4(), uuid4())


def test_regras_de_expiracao_uso_e_tentativas():
    agora = agora_utc()
    desafio = VerificacaoEmail(
        usuario_id=uuid4(),
        codigo_hash="a" * 64,
        criado_em=agora,
        expira_em=agora + timedelta(minutes=10),
    )
    assert desafio.disponivel(agora)
    assert not desafio.disponivel(desafio.expira_em)
    for _ in range(5):
        desafio.registrar_erro(agora)
    assert desafio.tentativas == 5 and desafio.invalidado_em == agora
    assert not desafio.disponivel(agora)
    with pytest.raises(ValueError):
        desafio.utilizar(agora)
    assert "a" * 64 not in repr(desafio)


def test_utilizacao_nao_pode_ser_repetida():
    agora = agora_utc()
    desafio = VerificacaoEmail(
        usuario_id=uuid4(),
        codigo_hash="a" * 64,
        criado_em=agora,
        expira_em=agora + timedelta(minutes=10),
    )
    desafio.utilizar(agora)
    with pytest.raises(ValueError):
        desafio.utilizar(agora)


def test_configuracao_padrao_e_segredo_obrigatorio_para_criptografia():
    configuracao = Configuracao(_env_file=None)
    assert configuracao.verificacao_validade_segundos == 600
    assert configuracao.verificacao_limite_tentativas == 5
    with pytest.raises(ValidationError):
        Configuracao(_env_file=None, verificacao_segredo="curto")
    with pytest.raises(ValueError):
        CodigosVerificacaoHMAC(SecretStr("curto"))
