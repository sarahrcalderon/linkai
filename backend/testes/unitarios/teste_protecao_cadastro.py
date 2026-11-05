from unittest.mock import patch

from aplicacao.apresentacao.protecao_cadastro import ProtecaoCadastro


def test_janela_rate_limit_expira_e_isola_enderecos():
    protecao = ProtecaoCadastro(app=None, limite=2, janela=60)
    with patch("aplicacao.apresentacao.protecao_cadastro.monotonic", return_value=100):
        assert protecao.permitir("origem_a") == 0
        assert protecao.permitir("origem_a") == 0
        assert protecao.permitir("origem_a") == 60
        assert protecao.permitir("origem_b") == 0
    with patch("aplicacao.apresentacao.protecao_cadastro.monotonic", return_value=161):
        assert protecao.permitir("origem_a") == 0
        assert "origem_b" not in protecao.tentativas
