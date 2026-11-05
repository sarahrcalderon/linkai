from datetime import timedelta
from uuid import uuid4

import pytest

from aplicacao.dominio.sessao import Sessao
from aplicacao.dominio.usuario import agora_utc
from aplicacao.infraestrutura.tokens import TokensSeguros


def test_expiracao_revogacao_e_limites():
    agora = agora_utc()
    sessao = Sessao(
        usuario_id=uuid4(),
        token_hash="a" * 64,
        criado_em=agora,
        expira_em=agora + timedelta(seconds=60),
    )
    assert sessao.esta_valida(agora)
    assert not sessao.esta_valida(sessao.expira_em)
    assert not sessao.esta_valida(agora - timedelta(seconds=1))
    sessao.revogado_em = agora
    assert not sessao.esta_valida(agora)
    assert "a" * 64 not in repr(sessao)


def test_tokens_e_csrf_vinculados():
    servico = TokensSeguros()
    primeiro, segundo = servico.gerar(), servico.gerar()
    assert primeiro != segundo and len(primeiro) == 43
    assert len(servico.resumir(primeiro)) == 64
    assert primeiro not in servico.resumir(primeiro)
    csrf = servico.gerar_csrf(primeiro)
    assert servico.verificar_csrf(primeiro, csrf)
    assert not servico.verificar_csrf(segundo, csrf)
    assert not servico.verificar_csrf(primeiro, "á" * 64)
    assert not servico.verificar_csrf(primeiro, "")


def test_rejeita_sessao_sem_fuso():
    agora = agora_utc()
    with pytest.raises(ValueError):
        Sessao(
            usuario_id=uuid4(),
            token_hash="a" * 64,
            criado_em=agora.replace(tzinfo=None),
            expira_em=agora + timedelta(seconds=60),
        )
